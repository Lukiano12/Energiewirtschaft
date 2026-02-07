import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe  # Wir importieren es als 'pe'
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm
from . import gui, config
import shutil
from matplotlib.widgets import Slider
from shapely.geometry import box

# Matplotlib Animation Importe explizit
from matplotlib.animation import PillowWriter, FFMpegWriter, FuncAnimation
import os
import imageio

def calculate_hourly_prices(res_loads, merit_orders, zone_names, direct_prices=None):
    """Berechnet die stuendlichen Preise."""
    print("Berechne stuendliche Preise...")
    hourly_prices = pd.DataFrame(index=res_loads.index)
    
    for zone in zone_names:
        if direct_prices is not None and zone in direct_prices.columns:
            prices = direct_prices[zone].values
            prices = np.nan_to_num(prices, nan=0.0)
            hourly_prices[zone] = prices
            valid_prices = prices[prices > 0]
            if len(valid_prices) > 0:
                print(f"  Zone '{zone}': Direkte Preise, Bereich {valid_prices.min():.1f} - {valid_prices.max():.1f} EUR/MWh")
            continue
        
        if zone not in res_loads.columns:
            hourly_prices[zone] = np.nan
            continue
            
        stack = merit_orders.get(zone)
        if stack is None or stack.empty:
            hourly_prices[zone] = np.nan
            continue
        
        x_cap = stack['acum_mw'].values
        y_price = stack['mc'].values
        
        loads = res_loads[zone].fillna(0).values
        loads_clipped = np.clip(loads, 0, x_cap[-1])
        
        indices = np.searchsorted(x_cap, loads_clipped)
        indices = np.clip(indices, 0, len(y_price) - 1)
        
        prices = y_price[indices].copy()
        prices[loads <= 0] = 0
        
        hourly_prices[zone] = prices
        print(f"  Zone '{zone}': Merit-Order-Lookup, Bereich {prices.min():.1f} - {prices.max():.1f} EUR/MWh")
    
    return hourly_prices

def create_animation_frames(gdf, hourly_prices):
    """
    Erstellt die Daten für jeden Frame der Animation.
    NEU: 24 Stunden pro Monat (Durchschnittstag) = 288 Frames.
    """
    print("Berechne Animation-Frames (24h-Durchschnitt pro Monat)...")
    
    if not isinstance(hourly_prices.index, pd.DatetimeIndex):
        hourly_prices.index = pd.to_datetime(hourly_prices.index)
    
    monthly_profiles = []
    gdf_list = []
    
    months = range(1, 13)
    month_names = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 
                   'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
    
    for month in months:
        # Daten für diesen Monat filtern
        month_data = hourly_prices[hourly_prices.index.month == month]
        if month_data.empty: continue
        
        # Durchschnittlichen Tagesverlauf berechnen (0..23 Uhr)
        # Erzeugt DataFrame mit Index 0..23 und Spalten (Zonen)
        daily_profile_mean = month_data.groupby(month_data.index.hour).mean()
        
        monthly_profiles.append((month_names[month-1], daily_profile_mean))

        # Frames für jede Stunde (0 bis 23) erstellen
        for h in range(24):
            # Falls Stunde im Datenbestand fehlt (unwahrscheinlich), überspringen
            if h not in daily_profile_mean.index: continue
            
            price_row = daily_profile_mean.loc[h]
            
            # Merge mit Geodaten
            gdf_frame = gdf.copy()
            gdf_frame['price'] = gdf_frame['zone'].map(price_row)
            
            # Formatierung: "Januar | 14:00 Uhr"
            label_text = f"{month_names[month-1]} | {h:02d}:00 Uhr"
            gdf_frame['label_title'] = label_text
            
            gdf_list.append(gdf_frame)

    print(f"  -> {len(gdf_list)} Frames generiert (12 Monate x 24 Stunden).")
    return gdf_list, monthly_profiles

def run_visualization(gdf_list, monthly_profiles, zone_names, scenario_id, script_dir):
    """Startet die Matplotlib-Visualisierung."""
    
    is_diff_scenario = 'diff' in scenario_id
    
    # Hintergrundkarte laden
    try:
        world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world_map.clip(box(3, 46, 17, 56))
    except:
        bg_map = None

    # Einheitliche Farbskala aus config.py
    if is_diff_scenario:
        vmax = config.DIFF_SCALE['vmax']
        vmin = -vmax
        cmap = config.DIFF_SCALE['cmap']
        cbar_label = 'Preisdifferenz (Coupled - Insel) [EUR/MWh]'
    else:
        vmin = config.PRICE_SCALE['vmin']
        vmax = config.PRICE_SCALE['vmax']
        cmap = config.PRICE_SCALE['cmap']
        cbar_label = 'Strompreis [EUR/MWh]'
    
    print(f"  Farbskala: {vmin} - {vmax} EUR/MWh (einheitlich fuer Vergleichbarkeit)")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))

    scenario_titles = {
        'de_single': 'Deutschland (eine Zone)',
        'z4_insel': '4 Zonen - Inselbetrachtung',
        'z4_coupled': '4 Zonen - Gekoppelt',
        'z4_diff': '4 Zonen - Preisdifferenz',
        'ns_insel': 'Nord-Sued - Inselbetrachtung',
        'ns_coupled': 'Nord-Sued - Gekoppelt',
        'ns_diff': 'Nord-Sued - Preisdifferenz',
    }

    fig, ax = plt.subplots(figsize=(10, 12))
    fig.canvas.manager.set_window_title(f'Merit-Order Visualisierung - {scenario_id}')
    
    plt.subplots_adjust(bottom=0.15)
    ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
    
    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', pad=0.02, aspect=40, shrink=0.8)
    cbar.set_label(cbar_label, fontsize=10)

    def update_plot(frame_idx):
        frame_idx = int(frame_idx)
        ax.clear()
        
        data = gdf_list[frame_idx]
        title_str = data['label_title'].iloc[0]
        scenario_title = scenario_titles.get(scenario_id, scenario_id)
        
        if bg_map is not None:
            bg_map.plot(ax=ax, facecolor='#dce6f2', edgecolor='#999999', linewidth=0.5)
        
        data.plot(
            column='price', 
            ax=ax, 
            cmap=cmap, 
            vmin=vmin, 
            vmax=vmax,
            alpha=0.85, 
            edgecolor='#005b96',
            linewidth=2,
            missing_kwds={'color': '#cccccc'}
        )
        
        # Labels
        for _, geo_row in data.iterrows():
            zone_name = geo_row['zone']
            p = geo_row['price']
            pt = geo_row['geometry'].representative_point()
            offsets = {
                "TenneT": (0, -0.6), "50Hertz": (0.3, -0.4), "de": (0, 0), 
                "north": (0, 0.6), "south": (0, -0.4), "Amprion": (-0.2, 0), "TransnetBW": (0.1, -0.1)
            }
            dx, dy = offsets.get(zone_name, (0, 0))
            
            val_txt = f"{p:+.0f}" if is_diff_scenario else f"{p:.0f}"
            if pd.isna(p): val_txt = "-"
            
            ax.text(
                pt.x + dx, pt.y + dy, f"{val_txt} €", ha='center', va='center',
                fontsize=11, fontweight='bold', color='black',
                path_effects=[pe.withStroke(linewidth=2, foreground='white')], zorder=10
            )

        ax.set_xlim(5, 16)
        ax.set_ylim(47, 55.5)
        ax.set_title(f"{scenario_title}\n{title_str}", fontsize=14, fontweight='bold')
        ax.axis('off')

    slider = Slider(ax_slider, 'Frame', 0, len(gdf_list) - 1, valinit=0, valstep=1)
    
    def on_slider_change(val):
        update_plot(val)
        fig.canvas.draw_idle()
    
    slider.on_changed(on_slider_change)

    def save_video():
        """Exportiert die Animation als MP4-Video und/oder GIF."""
        
        # FRAGE NACH FORMAT
        format_choice = gui.ask_video_format()
        if not format_choice:
            print("Export abgebrochen.")
            return
            
        print("\n" + "="*60)
        print(f"EXPORT GESTARTET ({format_choice.upper()})")
        print("="*60)
        
        # Output-Pfad im geodata_merit_order Ordner
        output_dir = script_dir / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"merit_order_{scenario_id}_{timestamp}"
        
        # Pfade definieren
        mp4_path = output_dir / f"{base_filename}.mp4"
        gif_path = output_dir / f"{base_filename}.gif"
        
        print(f"  Verzeichnis: {output_dir}")
        print(f"  Frames: {len(gdf_list)}")
        print(f"  FPS: {config.VIDEO_SETTINGS['fps']}")
        print("-"*60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # --- TEIL 1: FRAMES RENDERN (Gleich für MP4 und GIF) ---
            frame_paths = []
            
            # Figure mit fester Groesse
            fig_video, ax_video = plt.subplots(figsize=(10, 14), dpi=100)
            
            cbar_video = fig_video.colorbar(sm, ax=ax_video, orientation='horizontal', 
                                            pad=0.05, aspect=40, shrink=0.8)
            cbar_video.set_label(cbar_label, fontsize=10)
            
            print("\nErstelle Frames...")
            for i in tqdm(range(len(gdf_list)), desc="  Rendering", unit="frame", 
                         ncols=70, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'):
                
                ax_video.clear()
                data = gdf_list[i]
                title_str = data['label_title'].iloc[0]
                scenario_title = scenario_titles.get(scenario_id, scenario_id)
                
                if bg_map is not None:
                    bg_map.plot(ax=ax_video, facecolor='#dce6f2', edgecolor='#999999', linewidth=0.5)
                
                data.plot(column='price', ax=ax_video, cmap=cmap, vmin=vmin, vmax=vmax,
                    alpha=0.85, edgecolor='#005b96', linewidth=2, missing_kwds={'color': '#cccccc'})
                
                # Labels plotten (stark verkürzt hier dargestellt, Code bleibt gleich)
                for _, geo_row in data.iterrows():
                    zone_name = geo_row['zone']
                    p = geo_row['price']
                    pt = geo_row['geometry'].representative_point()
                    pt_x, pt_y = pt.x, pt.y
                    
                    offsets = {"TenneT": (0, -0.5), "50Hertz": (0.2, -0.3), 
                              "north": (0, 0.5), "south": (0, -0.3)}
                    dx, dy = offsets.get(zone_name, (0, 0))
                    pt_x += dx
                    pt_y += dy
                    
                    display_names = {'de': 'DEUTSCHLAND', 'north': 'NORD', 'south': 'SUED'}
                    display_name = display_names.get(zone_name, zone_name)
                    
                    if pd.notna(p):
                        val_txt = f"{p:+.1f} EUR/MWh" if is_diff_scenario else f"{p:.1f} EUR/MWh"
                    else:
                        val_txt = "-"
                    
                    ax_video.text(
                        pt_x, pt_y + 0.3, 
                        display_name, 
                        ha='center', va='bottom',
                        fontsize=10, 
                        color='#000000', 
                        fontweight='bold',
                        path_effects=[pe.withStroke(linewidth=3, foreground='white')],
                        zorder=10
                    )
                    
                    ax_video.text(
                        pt_x, pt_y - 0.2, 
                        val_txt, 
                        ha='center', va='top',
                        fontsize=12, 
                        fontweight='bold', 
                        color='#000000',
                        path_effects=[pe.withStroke(linewidth=3, foreground='white')],
                        zorder=10
                    )
        
        ax_video.set_xlim(5, 16)
        ax_video.set_ylim(47, 55.5)
        ax_video.set_title(f"{scenario_title}\n{title_str}", fontsize=14, fontweight='bold')
        ax_video.axis('off')

        # Frame speichern
        frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
        fig_video.savefig(frame_path, dpi=100, bbox_inches='tight', pad_inches=0.1)
        frame_paths.append(frame_path)
            
    plt.close(fig_video)
            
    # --- TEIL 2: DATEIEN ERSTELLEN ---
    print("\nErstelle Ausgabedateien...")
    
    # Bilder vorbereiten (gerade Dimensionen für MP4 wichtig)
    first_frame = imageio.imread(frame_paths[0])
    h, w = first_frame.shape[:2]
    new_h = h if h % 2 == 0 else h - 1
    new_w = w if w % 2 == 0 else w - 1
    
    saved_files_info = []

    try:
        # ---------------- MP4 EXPORT ----------------
        if format_choice in ['mp4', 'both']:
            print(f"  Encoding MP4 ({new_w}x{new_h})...")
            writer = imageio.get_writer(
                str(mp4_path), 
                fps=config.VIDEO_SETTINGS['fps'],
                codec='libx264',
                quality=8,
                pixelformat='yuv420p',
                output_params=['-vf', f'scale={new_w}:{new_h}']
            )
            
            for frame_path in tqdm(frame_paths, desc="  MP4 Writing", unit="frame", ncols=70):
                frame = imageio.imread(frame_path)
                frame = frame[:new_h, :new_w] # Zuschneiden
                writer.append_data(frame)
            
            writer.close()
            size_mb = mp4_path.stat().st_size / 1024 / 1024
            saved_files_info.append(f"MP4: {mp4_path.name} ({size_mb:.1f} MB)")

        # ---------------- GIF EXPORT ----------------
        if format_choice in ['gif', 'both']:
            print(f"  Encoding GIF...")
            # GIFs lesen alle Frames ein
            images = []
            for frame_path in tqdm(frame_paths, desc="  GIF Writing", unit="frame", ncols=70):
                 images.append(imageio.imread(frame_path))
            
            # loop=0 bedeutet Endlosschleife
            imageio.mimsave(str(gif_path), images, fps=config.VIDEO_SETTINGS['fps'], loop=0)
            
            size_mb = gif_path.stat().st_size / 1024 / 1024
            saved_files_info.append(f"GIF: {gif_path.name} ({size_mb:.1f} MB)")

        # ---------------- ABSCHLUSS ----------------
        duration = len(gdf_list) / config.VIDEO_SETTINGS['fps']
        
        print("\n" + "="*60)
        print("EXPORT ERFOLGREICH!")
        print("="*60)
        for info in saved_files_info:
            print(f"  {info}")
        print(f"  Dauer: {duration:.1f} Sekunden")
        print("="*60 + "\n")
        
        gui.show_info(
            "Export erfolgreich", 
            f"Gespeichert in:\n{output_dir}\n\n" + "\n".join(saved_files_info)
        )
        
    except Exception as e:
        print(f"\nFEHLER beim Export: {e}")
        gui.show_error("Export fehlgeschlagen", f"Fehler: {e}")

    def on_key(event):
        curr = slider.val
        if event.key == 'right':
            slider.set_val(min(curr + 1, slider.valmax))
        elif event.key == 'left':
            slider.set_val(max(curr - 1, slider.valmin))
        elif event.key == 'up':
            slider.set_val(min(curr + 24, slider.valmax))
        elif event.key == 'down':
            slider.set_val(max(curr - 24, slider.valmin))
        elif event.key == 'home':
            slider.set_val(0)
        elif event.key == 'end':
            slider.set_val(slider.valmax)
        elif event.key == 'v':
            save_video()

    fig.canvas.mpl_connect('key_press_event', on_key)
    
    update_plot(0)
    
    print("\n" + "="*50)
    print("VISUALISIERUNG GESTARTET")
    print("="*50)
    print(f"Szenario: {scenario_id}")
    print(f"Farbskala: {vmin} - {vmax} EUR/MWh (EINHEITLICH)")
    print("-"*50)
    print("Steuerung:")
    print("  <- ->    Stunde vor/zurueck")
    print("  Pfeil hoch/runter  Monat vor/zurueck (+/-24 Frames)")
    print("  Home     Zum Anfang")
    print("  End      Zum Ende")
    print("  V        VIDEO EXPORTIEREN (MP4)")
    print("="*50 + "\n")
    
    plt.show()

def run_multi_year_visualization(data_packages, scenario_base_id, script_dir):
    """
    Visualisiert mehrere Jahre (2024, 2037, 2045) nebeneinander.
    data_packages: Dictionary {year: gdf_list}
    """
    years = sorted(data_packages.keys())
    if not years:
        print("Keine Daten für Multi-View vorhanden.")
        return

    is_diff_scenario = 'diff' in scenario_base_id

    # Hintergrundkarte laden
    try:
        world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world_map.clip(box(3, 46, 17, 56))
    except:
        bg_map = None

    # --- SKALIERUNG ---
    if is_diff_scenario:
        vmax = config.DIFF_SCALE['vmax']
        vmin = -vmax
        cmap = config.DIFF_SCALE['cmap']
        cbar_label = 'Preisdifferenz (Coupled - Insel) [EUR/MWh]'
    else:
        vmin = config.PRICE_SCALE['vmin']
        vmax = config.PRICE_SCALE['vmax']
        cmap = config.PRICE_SCALE['cmap']
        cbar_label = 'Strompreis [EUR/MWh]'
        
    print(f"  Multi-View Skalierung: {vmin} bis {vmax} (einheitlich)")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))

    # Figure Setup: WICHTIG - constrained_layout=False verhindert den Konflikt mit subplots_adjust
    fig, axes = plt.subplots(1, len(years), figsize=(18, 10), constrained_layout=False)
    
    if len(years) == 1: axes = [axes]
    
    fig.canvas.manager.set_window_title(f'Merit-Order Vergleich: {scenario_base_id}')
    
    # Manuelles Layout: Platz unten reservieren
    plt.subplots_adjust(left=0.05, right=0.95, top=0.90, bottom=0.2, wspace=0.15)
    
    num_frames = len(data_packages[years[0]])

    def plot_single_year(ax, year, frame_idx):
        ax.clear()
        gdf_list = data_packages[year]
        if frame_idx >= len(gdf_list): return ""

        data = gdf_list[frame_idx]
        title_common = data['label_title'].iloc[0] 
        
        if bg_map is not None:
            bg_map.plot(ax=ax, facecolor='#dce6f2', edgecolor='#999999', linewidth=0.5)
        
        data.plot(
            column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
            alpha=0.9, edgecolor='#005b96', linewidth=1.5,
            missing_kwds={'color': '#cccccc'}
        )
        
        # Labels
        for _, geo_row in data.iterrows():
            zone_name = geo_row['zone']
            p = geo_row['price']
            pt = geo_row['geometry'].representative_point()
            offsets = {
                "TenneT": (0, -0.6), "50Hertz": (0.3, -0.4), "de": (0, 0), 
                "north": (0, 0.6), "south": (0, -0.4), "Amprion": (-0.2, 0), "TransnetBW": (0.1, -0.1)
            }
            dx, dy = offsets.get(zone_name, (0, 0))
            
            val_txt = f"{p:+.0f}" if is_diff_scenario else f"{p:.0f}"
            if pd.isna(p): val_txt = "-"
            
            ax.text(
                pt.x + dx, pt.y + dy, f"{val_txt} €", ha='center', va='center',
                fontsize=11, fontweight='bold', color='black',
                path_effects=[pe.withStroke(linewidth=2, foreground='white')], zorder=10
            )

        ax.set_xlim(5, 16)
        ax.set_ylim(47, 55.5)
        ax.set_title(f"Jahr {year}", fontsize=16, fontweight='bold', color='#333333')
        ax.axis('off')
        return title_common

    def update_all(val):
        frame_idx = int(val)
        main_title = ""
        for i, year in enumerate(years):
            t = plot_single_year(axes[i], year, frame_idx)
            if i == 0: main_title = t
        fig.suptitle(f"Vergleich: {scenario_base_id.upper()}\n{main_title}", fontsize=15, fontweight='bold')

    update_all(0)

    # Colorbar
    cbar = fig.colorbar(sm, ax=axes, orientation='horizontal', fraction=0.05, pad=0.05, shrink=0.6)
    cbar.set_label(cbar_label, fontsize=12)

    # Slider
    ax_slider = plt.axes([0.2, 0.05, 0.6, 0.03])
    slider = Slider(ax_slider, 'Zeit', 0, num_frames - 1, valinit=0, valstep=1)
    slider.on_changed(lambda val: (update_all(val), fig.canvas.draw_idle()))
    
    # --- VIDEO EXPORT ---
    def save_video_multi():
        target_format = gui.ask_video_format()  # mp4, gif, both, None
        if not target_format: return

        print("Start Video-Export... (Bitte warten)")
        base_filename = script_dir.parent.parent / "output" / "figures" / f"Multi_{scenario_base_id.replace('multi_', '')}"
        
        anim = FuncAnimation(fig, update_all, frames=num_frames, interval=500, blit=False)
        
        # FFmpeg Check
        ffmpeg_available = shutil.which("ffmpeg") is not None
        
        if target_format in ['mp4', 'both']:
            if ffmpeg_available:
                try:
                    mp4_path = f"{base_filename}.mp4"
                    print(f"  Speichere MP4: {mp4_path}")
                    writer = FFMpegWriter(fps=2, bitrate=3000)
                    anim.save(mp4_path, writer=writer)
                    print("  -> MP4 OK.")
                except Exception as e:
                    print(f"  FEHLER beim MP4-Export: {e}")
            else:
                print("  WARNUNG: FFmpeg nicht gefunden. MP4 übersprungen.")
                gui.show_error("Fehler", "FFmpeg fehlt. MP4 kann nicht erstellt werden.")

        if target_format in ['gif', 'both'] or (target_format == 'mp4' and not ffmpeg_available):
            try:
                gif_path = f"{base_filename}.gif"
                print(f"  Speichere GIF: {gif_path}")
                writer_gif = PillowWriter(fps=2)
                anim.save(gif_path, writer=writer_gif)
                print("  -> GIF OK.")
            except Exception as e:
                print(f"  FEHLER beim GIF-Export: {e}")

        gui.show_info("Export fertig", "Dateien im output-Ordner gespeichert.")

    def on_key(event):
        if event.key == 'right': slider.set_val(min(slider.val + 1, slider.valmax))
        elif event.key == 'left': slider.set_val(max(slider.val - 1, slider.valmin))
        elif event.key.lower() == 'v': save_video_multi()

    fig.canvas.mpl_connect('key_press_event', on_key)
    plt.show()