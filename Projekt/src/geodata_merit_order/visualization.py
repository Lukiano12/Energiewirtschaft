import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm
from . import gui, config
import shutil
from matplotlib.widgets import Slider
from shapely.geometry import box
import numpy as np
import pandas as pd
import imageio
import tempfile
import os
import matplotlib.patheffects

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

    # --- GLOBALE STATISTIK BERECHNEN (STATISCH) ---
    all_prices = []
    for frame_gdf in gdf_list:
        if 'price' in frame_gdf.columns:
            vals = frame_gdf['price'].dropna().values
            if len(vals) > 0:
                all_prices.append(vals)
    
    if all_prices:
        flat_prices = np.concatenate(all_prices)
        s_min = np.min(flat_prices)
        s_max = np.max(flat_prices)
        s_mean = np.mean(flat_prices)
        
        # Statische Info-Box
        stats_text_str = (f"STATISTIK (GESAMT):\n"
                          f"Min: {s_min:6.1f} €\n"
                          f"Max: {s_max:6.1f} €\n"
                          f"Ø:   {s_mean:6.1f} €")
    else:
        stats_text_str = "Keine Daten"

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
        
        # --- STATISCHE INFO BOX DISPLAY ---
        ax.text(
            0.02, 0.98, stats_text_str, 
            transform=ax.transAxes, 
            fontsize=9, 
            fontfamily='monospace',
            verticalalignment='top', 
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#cccccc'),
            zorder=100
        )

        for _, geo_row in data.iterrows():
            zone_name = geo_row['zone']
            p = geo_row['price']
            
            pt = geo_row['geometry'].representative_point()
            pt_x, pt_y = pt.x, pt.y
            
            offsets = {
                "TenneT": (0, -0.5),
                "50Hertz": (0.2, -0.3),
                "de": (0, 0),
                "north": (0, 0.5),
                "south": (0, -0.3),
            }
            dx, dy = offsets.get(zone_name, (0, 0))
            pt_x += dx
            pt_y += dy
            
            display_names = {
                'de': 'DEUTSCHLAND',
                'north': 'NORD',
                'south': 'SUED',
            }
            display_name = display_names.get(zone_name, zone_name)
            
            if pd.notna(p):
                if is_diff_scenario:
                    val_txt = f"{p:+.1f} EUR/MWh"
                else:
                    val_txt = f"{p:.1f} EUR/MWh"
            else:
                val_txt = "-"
            
            ax.text(
                pt_x, pt_y + 0.3, 
                display_name, 
                ha='center', va='bottom',
                fontsize=10, 
                color='#000000', 
                fontweight='bold',
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground='white')],
                zorder=10
            )
            
            ax.text(
                pt_x, pt_y - 0.2, 
                val_txt, 
                ha='center', va='top',
                fontsize=12, 
                fontweight='bold', 
                color='#000000',
                path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground='white')],
                zorder=10
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
        """Speichert Video als MP4 oder GIF mittels imageio (ohne externe FFmpeg-Installation)."""
        format_choice = gui.ask_video_format()
        if not format_choice:
            return

        filename = f"Video_{scenario_id}"
        mp4_path = script_dir.parent.parent / "output" / "videos" / f"{filename}.mp4"
        gif_path = script_dir.parent.parent / "output" / "videos" / f"{filename}.gif"
        
        mp4_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\nStarte Video-Export ({len(gdf_list)} Frames)...")
        print("Bitte warten, dies kann einen Moment dauern.")
        
        # Temporäres Verzeichnis für Einzelbilder
        with tempfile.TemporaryDirectory() as temp_dir:
            # --- TEIL 1: FRAMES RENDERN ---
            frame_paths = []
            
            # Separate Figure für Export (sauberer als GUI-Figure)
            fig_video, ax_video = plt.subplots(figsize=(10, 14), dpi=100)
            
            cbar_video = fig_video.colorbar(sm, ax=ax_video, orientation='horizontal', 
                                            pad=0.05, aspect=40, shrink=0.8)
            cbar_video.set_label(cbar_label, fontsize=10)
            
            print("  Rendere Frames...")
            # Deaktiviere Interactivity für schnelleres Rendering
            plt.ioff()
            
            for i in tqdm(range(len(gdf_list)), desc="  Fortschritt", unit="frame", ncols=80):
                ax_video.clear()
                data = gdf_list[i]
                title_str = data['label_title'].iloc[0]
                scenario_title = scenario_titles.get(scenario_id, scenario_id)
                
                # Plotting Logic kopiert
                if bg_map is not None:
                    bg_map.plot(ax=ax_video, facecolor='#dce6f2', edgecolor='#999999', linewidth=0.5)
                
                data.plot(column='price', ax=ax_video, cmap=cmap, vmin=vmin, vmax=vmax,
                         alpha=0.85, edgecolor='#005b96', linewidth=2, missing_kwds={'color': '#cccccc'})

                # Statische Info-Box auch im Video
                ax_video.text(
                    0.02, 0.98, stats_text_str, 
                    transform=ax_video.transAxes, 
                    fontsize=10, fontfamily='monospace', verticalalignment='top', 
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#cccccc')
                )

                # Labels
                for _, geo_row in data.iterrows():
                    zone_name = geo_row['zone']
                    val = geo_row['price']
                    pt = geo_row['geometry'].representative_point()
                    pt_x, pt_y = pt.x, pt.y
                    
                    if pd.isna(val): val_txt = "n/a"
                    else: val_txt = f"{val:.1f} €"

                    if zone_name == 'node_north': pt_y += 0.5
                    
                    ax_video.text(pt_x, pt_y, f"{zone_name}\n{val_txt}", ha='center', fontsize=9,
                                  fontweight='bold',
                                  path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground='white')])

                ax_video.set_xlim(5, 16)
                ax_video.set_ylim(47, 55.5)
                ax_video.set_title(f"{scenario_title}\n{title_str}", fontsize=14, fontweight='bold')
                ax_video.axis('off')

                # Frame speichern
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                fig_video.savefig(frame_path, dpi=100, bbox_inches='tight', pad_inches=0.1)
                frame_paths.append(frame_path)
            
            plt.close(fig_video)
            plt.ion() # Interactivity wieder an
            
            # --- TEIL 2: VIDEO ZUSAMMENSETZEN ---
            print("  Erstelle Videodatei(en)...")
            
            # Erstes Bild laden für Dimensionen
            first_img = imageio.imread(frame_paths[0])
            h, w = first_img.shape[:2]
            
            # Dimensionen müssen für Codecs oft durch 16 teilbar sein (wichtig für MP4)
            new_h = h - (h % 16)
            new_w = w - (w % 16)
            
            if format_choice in ['mp4', 'both']:
                try:
                    writer = imageio.get_writer(
                        str(mp4_path), 
                        fps=8, 
                        codec='libx264', 
                        quality=8,
                        pixelformat='yuv420p',
                        macro_block_size=None # Tolerant gegenüber ungeraden Größen
                    )
                    
                    for fpath in frame_paths:
                        img = imageio.imread(fpath)
                        # Zuschneiden auf kompatible Größe
                        img_cropped = img[:new_h, :new_w]
                        writer.append_data(img_cropped)
                        
                    writer.close()
                    print(f"  ✅ MP4 gespeichert: {mp4_path}")
                except Exception as e:
                    print(f"  ❌ MP4 Fehler: {e}")
            
            if format_choice in ['gif', 'both']:
                try:
                    images = [imageio.imread(f) for f in frame_paths]
                    imageio.mimsave(str(gif_path), images, fps=8, loop=0)
                    print(f"  ✅ GIF gespeichert: {gif_path}")
                except Exception as e:
                    print(f"  ❌ GIF Fehler: {e}")

        gui.show_info("Export abgeschlossen", "Video-Dateien wurden erstellt.")

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


def run_multi_year_visualization(data_packages, scenario_base_id, script_dir):
    """
    Visualisiert mehrere Jahre nebeneinander (z.B. 2024, 2037, 2045) mit Statistiken.
    """
    import matplotlib.pyplot as plt
    import geopandas as gpd
    import numpy as np

    # Einheitliche Farbskala ermitteln
    is_diff = 'diff' in scenario_base_id
    scale_cfg = config.DIFF_SCALE if is_diff else config.PRICE_SCALE
    vmin = scale_cfg.get('vmin', -50 if is_diff else 0)
    vmax = scale_cfg['vmax']
    cmap = scale_cfg['cmap']

    # Hintergrundkarte laden (optional)
    bg_map = None
    try:
        # Versuch, lokale oder Online-Daten zu laden
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world.cx[5:16, 47:56]
    except:
        pass

    n_years = len(data_packages)
    # Figure erstellen (Breite abhängig von Anzahl der Jahre)
    fig, axes = plt.subplots(1, n_years, figsize=(5 * n_years, 8))
    if n_years == 1: 
        axes = [axes]
    
    plt.subplots_adjust(bottom=0.2, top=0.85, wspace=0.1, left=0.05, right=0.95)
    
    # Gemeinsame Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    cbar_ax = fig.add_axes([0.2, 0.12, 0.6, 0.02])
    fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
    cbar_ax.set_label("Strompreis [EUR/MWh]" if not is_diff else "Preisdifferenz [EUR/MWh]", fontsize=10)

    # --- STATISTIKEN BERECHNEN (PRO JAHR) ---
    stats_per_year = []
    for pkg in data_packages:
        all_prices = []
        # Alle Frames durchgehen, um Min/Max/Avg für das ganze Jahr zu finden
        for frame_gdf in pkg['gdf_list']:
            if 'price' in frame_gdf.columns:
                vals = frame_gdf['price'].dropna().values
                if len(vals) > 0:
                    all_prices.append(vals)
        
        if all_prices:
            flat = np.concatenate(all_prices)
            # Textblock erstellen
            txt = (f"Min: {np.min(flat):.0f}\n"
                   f"Max: {np.max(flat):.0f}\n"
                   f"Ø:   {np.mean(flat):.0f} €")
        else:
            txt = "-"
        stats_per_year.append(txt)

    # Slider Steuerung
    ax_slider = plt.axes([0.2, 0.05, 0.6, 0.03])
    num_frames = len(data_packages[0]['gdf_list'])
    slider = Slider(ax_slider, 'Stunde', 0, num_frames - 1, valinit=0, valstep=1)

    def update_plot(val):
        frame_idx = int(val)
        
        # Titel basierend auf Zeit von erstem Datensatz
        time_label = data_packages[0]['gdf_list'][frame_idx]['label_title'].iloc[0]
        fig.suptitle(f"Szenario-Vergleich: {scenario_base_id}\n{time_label}", fontsize=16, fontweight='bold')

        for i, pkg in enumerate(data_packages):
            ax = axes[i]
            ax.clear()
            
            gdf = pkg['gdf_list'][frame_idx]
            year = pkg['year']
            
            # Hintergrund
            if bg_map is not None:
                bg_map.plot(ax=ax, facecolor='#eeeeee', edgecolor='#bbbbbb', linewidth=0.5)
            
            # Daten plotten
            gdf.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
                     edgecolor='#666666', linewidth=0.5)
            
            # --- STATISTIK-BOX ANZEIGEN ---
            # Oben links in jedem Subplot
            ax.text(0.03, 0.97, stats_per_year[i], transform=ax.transAxes,
                    fontsize=10, fontfamily='monospace', va='top', ha='left',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#cccccc'),
                    zorder=100)

            # Werte in die Karte schreiben (Preise)
            for _, row in gdf.iterrows():
                if not pd.isna(row['price']):
                    pt = row['geometry'].representative_point()
                    # Bei Nord-Sued Layout etwas verschieben
                    py = pt.y
                    if row.get('zone') == 'north': py += 0.3
                    
                    ax.annotate(f"{row['price']:.0f}", (pt.x, py), 
                                ha='center', va='center', fontsize=9, fontweight='bold',
                                path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground='white')])

            ax.set_title(f"Jahr {year}", fontsize=14)
            ax.axis('off')
            # Zoom auf Deutschland (ungefähr)
            ax.set_xlim(5.5, 15.5)
            ax.set_ylim(47, 55.5)
            
        fig.canvas.draw_idle()

    slider.on_changed(update_plot)
    update_plot(0) # Initial draw

    # --- VIDEO EXPORT (Robust/ImageIO) ---
    def save_video_multi():
        format_choice = gui.ask_video_format()
        if not format_choice: return
        
        print(f"\nStarte Multi-Year Video Export ({num_frames} Frames)...")
        filename = f"Zeitreihe_{scenario_base_id}"
        out_path_mp4 = script_dir.parent.parent / "output" / "videos" / f"{filename}.mp4"
        out_path_gif = script_dir.parent.parent / "output" / "videos" / f"{filename}.gif"
        out_path_mp4.parent.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                frame_paths = []
                # Eigene Figure für Export (sauberer)
                f_ex, ax_ex = plt.subplots(1, n_years, figsize=(6 * n_years, 8), dpi=100)
                if n_years == 1: ax_ex = [ax_ex]
                
                plt.ioff() # Keine GUI Updates
                
                for fi in tqdm(range(num_frames), desc="  Rendering", ncols=80):
                    time_lbl = data_packages[0]['gdf_list'][fi]['label_title'].iloc[0]
                    f_ex.suptitle(f"{scenario_base_id} : {time_lbl}", fontsize=16)
                    
                    for i, pkg in enumerate(data_packages):
                        ax = ax_ex[i]
                        ax.clear()
                        gdf = pkg['gdf_list'][fi]
                        
                        if bg_map is not None: bg_map.plot(ax=ax, facecolor='#eee', edgecolor='#bbb')
                        
                        gdf.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, edgecolor='#555')
                        
                        # Stats auch im Video
                        ax.text(0.03, 0.97, stats_per_year[i], transform=ax.transAxes,
                                fontsize=11, fontfamily='monospace', va='top',
                                bbox=dict(facecolor='white', alpha=0.8))
                        
                        # Labels
                        for _, row in gdf.iterrows():
                             if not pd.isna(row['price']):
                                pt = row['geometry'].representative_point()
                                ax.text(pt.x, pt.y, f"{row['price']:.0f}", ha='center', fontsize=9, fontweight='bold',
                                        path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground='white')])
                        
                        ax.set_title(f"{pkg['year']}")
                        ax.axis('off')
                        ax.set_xlim(5.5, 15.5)
                        ax.set_ylim(47, 55.5)

                    path = os.path.join(temp_dir, f"f_{fi:04d}.png")
                    f_ex.savefig(path, bbox_inches='tight')
                    frame_paths.append(path)
                
                plt.close(f_ex)
                plt.ion()

                # Speichern mit imageio
                print("  Erstelle Videodatei...")
                img0 = imageio.imread(frame_paths[0])
                h, w = img0.shape[:2]
                nh, nw = h - (h%16), w - (w%16) # Dimensionen gerade machen

                if format_choice in ['mp4', 'both']:
                    writer = imageio.get_writer(str(out_path_mp4), fps=8, codec='libx264', quality=8, pixelformat='yuv420p', macro_block_size=None)
                    for p in frame_paths:
                        im = imageio.imread(p)
                        writer.append_data(im[:nh, :nw])
                    writer.close()
                    print(f"  MP4 gespeichert: {out_path_mp4.name}")

                if format_choice in ['gif', 'both']:
                    # GIF speichern (vereinfacht)
                    images = [imageio.imread(p) for p in frame_paths]
                    imageio.mimsave(str(out_path_gif), images, fps=8)
                    print(f"  GIF gespeichert: {out_path_gif.name}")

            gui.show_info("Export fertig", f"Video gespeichert in output/videos")

        except Exception as e:
            print(f"ERROR: {e}")
            gui.show_error("Fehler", str(e))


    def on_key_multi(event):
        if event.key == 'right':
            slider.set_val(min(slider.val + 1, slider.valmax))
        elif event.key == 'left':
            slider.set_val(max(slider.val - 1, slider.valmin))
        elif event.key == 'v':
            save_video_multi()

    fig.canvas.mpl_connect('key_press_event', on_key_multi)
    
    print("\n" + "="*50)
    print("ZEITREISE VISUALISIERUNG GESTARTET")
    print("Taste 'v' druecken fuer Video-Export")
    print("="*50)

    plt.show()