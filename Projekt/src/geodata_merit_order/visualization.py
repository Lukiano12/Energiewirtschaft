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
import matplotlib as mpl
from matplotlib.animation import PillowWriter, FFMpegWriter, FuncAnimation

# --- FFMPEG KONFIGURATION ---
# Wir prüfen, ob die Datei im resources-Ordner liegt und sagen das Matplotlib
if config.FFMPEG_BINARY.exists():
    plt.rcParams['animation.ffmpeg_path'] = str(config.FFMPEG_BINARY)
    print(f"  FFmpeg gefunden: {config.FFMPEG_BINARY}")

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
        month_data = hourly_prices[hourly_prices.index.month == month]
        if month_data.empty: continue
        
        daily_profile_mean = month_data.groupby(month_data.index.hour).mean()
        monthly_profiles.append((month_names[month-1], daily_profile_mean))

        for h in range(24):
            if h not in daily_profile_mean.index: continue
            price_row = daily_profile_mean.loc[h]
            gdf_frame = gdf.copy()
            gdf_frame['price'] = gdf_frame['zone'].map(price_row)
            label_text = f"{month_names[month-1]} | {h:02d}:00 Uhr"
            gdf_frame['label_title'] = label_text
            gdf_list.append(gdf_frame)

    print(f"  -> {len(gdf_list)} Frames generiert (12 Monate x 24 Stunden).")
    return gdf_list, monthly_profiles

def run_visualization(gdf_list, monthly_profiles, zone_names, scenario_id, script_dir):
    """Startet die Visualisierung (Single View)."""
    
    is_diff_scenario = 'diff' in scenario_id
    
    try:
        world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world_map.clip(box(3, 46, 17, 56))
    except:
        bg_map = None

    if is_diff_scenario:
        vmin = -config.DIFF_SCALE['vmax']
        vmax = config.DIFF_SCALE['vmax']
        cmap = config.DIFF_SCALE['cmap']
        cbar_label = 'Preisdifferenz [EUR/MWh]'
    else:
        vmin = config.PRICE_SCALE['vmin']
        vmax = config.PRICE_SCALE['vmax']
        cmap = config.PRICE_SCALE['cmap']
        cbar_label = 'Strompreis [EUR/MWh]'
    
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))

    fig = plt.figure(figsize=(12, 10))
    fig.canvas.manager.set_window_title(f'Merit-Order Visualisierung - {scenario_id}')
    
    ax = plt.subplot(111) 
    ax_slider = plt.axes([0.2, 0.02, 0.6, 0.03])
    
    cbar_ax = fig.add_axes([0.2, 0.08, 0.6, 0.02])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
    cbar.set_label(cbar_label, fontsize=10)

    # --- STATISTIKEN BERECHNEN (Gesamtes Jahr) ---
    all_prices = []
    for frame_gdf in gdf_list:
        if 'price' in frame_gdf.columns:
            vals = frame_gdf['price'].dropna().values
            if len(vals) > 0:
                all_prices.append(vals)
    
    stats_text_str = "Keine Daten"
    if all_prices:
        flat_prices = np.concatenate(all_prices)
        s_min = np.min(flat_prices)
        s_max = np.max(flat_prices)
        s_mean = np.mean(flat_prices)
        stats_text_str = (f"STATISTIK (JAHR):\n"
                          f"Min: {s_min:6.1f} €\n"
                          f"Max: {s_max:6.1f} €\n"
                          f"Ø:   {s_mean:6.1f} €")

    def update_plot(frame_idx):
        frame_idx = int(frame_idx)
        ax.clear()
        
        data = gdf_list[frame_idx]
        title_str = data['label_title'].iloc[0]
        
        if bg_map is not None:
            bg_map.plot(ax=ax, facecolor='#dce6f2', edgecolor='#999999', linewidth=0.5)
        
        data.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
                  alpha=0.85, edgecolor='#005b96', linewidth=2,
                  missing_kwds={'color': '#cccccc'})
        
        # --- STATISCHE INFO BOX ---
        ax.text(0.02, 0.98, stats_text_str, transform=ax.transAxes, fontsize=10, 
                fontfamily='monospace', verticalalignment='top', 
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#cccccc'),
                zorder=100)

        for _, geo_row in data.iterrows():
            zone_name = geo_row['zone']
            p = geo_row['price']
            pt = geo_row['geometry'].representative_point()
            
            # Positionierung Optimierung
            offsets = {"TenneT": (0, -0.6), "50Hertz": (0.3, -0.4), "north": (0, 0.6), "south": (0, -0.4)}
            dx, dy = offsets.get(zone_name, (0, 0))
            
            val_txt = f"{p:+.0f}" if is_diff_scenario else f"{p:.0f}"
            if pd.isna(p): val_txt = "-"
            
            ax.text(pt.x + dx, pt.y + dy, f"{val_txt} €", ha='center', va='center',
                    fontsize=11, fontweight='bold', color='black',
                    path_effects=[pe.withStroke(linewidth=2, foreground='white')], zorder=10)

        ax.set_title(f"Szenario: {scenario_id}\n{title_str}", fontsize=14, fontweight='bold')
        ax.axis('off')
        ax.set_xlim(5, 16)
        ax.set_ylim(47, 55.5)

    slider = Slider(ax_slider, 'Zeit', 0, len(gdf_list) - 1, valinit=0, valstep=1)
    slider.on_changed(lambda val: (update_plot(val), fig.canvas.draw_idle()))

    def save_video():
        format_choice = gui.ask_video_format()
        if not format_choice: return

        print("Start Video-Export...")
        # FIX: Nutze VIDEOS_DIR aus config
        config.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{scenario_id}_video"
        
        # Animations-Objekt erstellen
        anim = FuncAnimation(fig, update_plot, frames=len(gdf_list), interval=200)

        if format_choice in ['mp4', 'both']:
            # Direkte Nutzung der ffmpeg.exe wenn vorhanden
            mp4_path = config.VIDEOS_DIR / f"{filename}.mp4"
            if config.FFMPEG_BINARY.exists() or shutil.which("ffmpeg"):
                writer = FFMpegWriter(fps=5, bitrate=3000)
                try:
                    print(f"  Speichere MP4: {mp4_path}")
                    anim.save(str(mp4_path), writer=writer, dpi=100)
                    print("  MP4 gespeichert.")
                except Exception as e:
                    print(f"  Fehler MP4: {e}")
            else:
                print("  FFmpeg nicht gefunden. Kein MP4.")

        if format_choice in ['gif', 'both']:
            gif_path = config.VIDEOS_DIR / f"{filename}.gif"
            print(f"  Speichere GIF: {gif_path}")
            writer = PillowWriter(fps=5)
            anim.save(str(gif_path), writer=writer)

        gui.show_info("Export fertig", f"Dateien in:\n{config.VIDEOS_DIR}")

    def on_key(event):
        if event.key == 'right': slider.set_val(min(slider.val + 1, slider.valmax))
        elif event.key == 'left': slider.set_val(max(slider.val - 1, slider.valmin))
        elif event.key == 'v': save_video()

    fig.canvas.mpl_connect('key_press_event', on_key)
    update_plot(0)
    plt.show()

def run_multi_year_visualization(data_packages, scenario_base_id, script_dir):
    """Startet die Visualisierung für MEHRERE JAHRE (Vergleich)."""
    
    # Sicherstellen, dass data_packages eine Liste ist
    if isinstance(data_packages, dict):
        years = sorted(data_packages.keys())
        packages_sorted = [data_packages[y] for y in years]
    else:
        packages_sorted = data_packages
        years = [2024, 2037, 2045][:len(packages_sorted)]

    is_diff_scenario = 'diff' in scenario_base_id
    
    try:
        world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world_map.clip(box(3, 46, 17, 56))
    except:
        bg_map = None

    if is_diff_scenario:
        vmin = -config.DIFF_SCALE['vmax']
        vmax = config.DIFF_SCALE['vmax']
        cmap = config.DIFF_SCALE['cmap']
        cbar_label = 'Preisdifferenz [EUR/MWh]'
    else:
        vmin = config.PRICE_SCALE['vmin']
        vmax = config.PRICE_SCALE['vmax']
        cmap = config.PRICE_SCALE['cmap']
        cbar_label = 'Strompreis [EUR/MWh]'
    
    # --- STATISTIKEN BERECHNEN (PRO JAHR) ---
    stats_per_year = []
    for pkg in packages_sorted:
        all_prices = []
        # Datenzugriff vereinheitlichen
        gdf_list = pkg['gdf_list'] if isinstance(pkg, dict) else pkg
        
        for frame_gdf in gdf_list:
            if 'price' in frame_gdf.columns:
                vals = frame_gdf['price'].dropna().values
                if len(vals) > 0:
                    all_prices.append(vals)
        
        if all_prices:
            flat = np.concatenate(all_prices)
            txt = (f"STATISTIK (JAHR):\n"
                   f"Min: {np.min(flat):4.0f} €\n"
                   f"Max: {np.max(flat):4.0f} €\n"
                   f"Ø:   {np.mean(flat):4.0f} €")
        else:
            txt = "-"
        stats_per_year.append(txt)

    # Setup Plot
    cols = len(packages_sorted)
    fig, axes = plt.subplots(1, cols, figsize=(5 * cols, 8))
    if cols == 1: axes = [axes]
    
    fig.canvas.manager.set_window_title(f'Multi-Year Vergleich - {scenario_base_id}')
    plt.subplots_adjust(bottom=0.2, top=0.85, wspace=0.1)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    cbar_ax = fig.add_axes([0.2, 0.1, 0.6, 0.02])
    cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
    cbar.set_label(cbar_label, fontsize=10)

    num_frames = len(packages_sorted[0]['gdf_list']) if isinstance(packages_sorted[0], dict) else len(packages_sorted[0])

    def update_all(val):
        frame_idx = int(val)
        
        # Titel (Datum aus erstem Paket nehmen)
        first_pkg_data = packages_sorted[0]['gdf_list'] if isinstance(packages_sorted[0], dict) else packages_sorted[0]
        time_label = first_pkg_data[frame_idx]['label_title'].iloc[0]
        fig.suptitle(f"Vergleich: {scenario_base_id.upper()}\n{time_label}", fontsize=16, fontweight='bold')

        for i, pkg in enumerate(packages_sorted):
            ax = axes[i]
            ax.clear()
            
            gdf_list = pkg['gdf_list'] if isinstance(pkg, dict) else pkg
            # Jahr ermitteln (Fallback)
            year_lbl = pkg['year'] if isinstance(pkg, dict) else years[i]
            
            gdf = gdf_list[frame_idx]
            
            if bg_map is not None:
                bg_map.plot(ax=ax, facecolor='#eeeeee', edgecolor='#bbbbbb', linewidth=0.5)
            
            gdf.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
                     edgecolor='#666666', linewidth=0.5)
            
            # --- STATISTISCHE BOX (STATIC MIN/MAX/AVG) ---
            ax.text(0.03, 0.97, stats_per_year[i], transform=ax.transAxes,
                    fontsize=10, fontfamily='monospace', va='top', ha='left',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='#cccccc'),
                    zorder=100)

            # Labels in Karte
            for _, row in gdf.iterrows():
                if not pd.isna(row['price']):
                    pt = row['geometry'].representative_point()
                    py = pt.y
                    if row.get('zone') == 'north': py += 0.3 # Verschieben für Lesbarkeit
                    
                    # FIX: Euro-Symbol hinzufügen
                    val_txt = f"{row['price']:.0f} €"
                    ax.annotate(val_txt, (pt.x, py), ha='center', va='center', fontsize=9, fontweight='bold',
                                path_effects=[pe.withStroke(linewidth=2, foreground='white')])

            ax.set_title(f"Jahr {year_lbl}", fontsize=14, fontweight='bold')
            ax.axis('off')
            ax.set_xlim(5.5, 15.5)
            ax.set_ylim(47, 55.5)

    slider_ax = plt.axes([0.2, 0.05, 0.6, 0.03])
    slider = Slider(slider_ax, 'Zeit', 0, num_frames - 1, valinit=0, valstep=1)
    slider.on_changed(lambda val: (update_all(val), fig.canvas.draw_idle()))

    def save_video_multi():
        format_choice = gui.ask_video_format()
        if not format_choice: return
        
        print(f"\nStarte Multi-Year Video Export ({num_frames} Frames)...")
        filename = f"Multi_{scenario_base_id}"
        
        # FIX: Nutze VIDEOS_DIR aus config
        config.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

        anim = FuncAnimation(fig, update_all, frames=num_frames, interval=200)

        if format_choice in ['mp4', 'both']:
            mp4_path = config.VIDEOS_DIR / f"{filename}.mp4"
            # Nutze FFmpeg Binary falls vorhanden
            if config.FFMPEG_BINARY.exists() or shutil.which("ffmpeg"):
                try:
                    print(f"  Speichere MP4: {mp4_path}")
                    writer = FFMpegWriter(fps=5, bitrate=4000)
                    anim.save(str(mp4_path), writer=writer, dpi=100)
                    print("  MP4 gespeichert.")
                except Exception as e:
                    print(f"  Fehler MP4: {e}")
            else:
                 print("  FFmpeg nicht gefunden. Kein MP4.")

        if format_choice in ['gif', 'both']:
            gif_path = config.VIDEOS_DIR / f"{filename}.gif"
            print(f"  Speichere GIF: {gif_path}")
            writer = PillowWriter(fps=5)
            anim.save(str(gif_path), writer=writer)

        gui.show_info("Export fertig", f"Dateien in:\n{config.VIDEOS_DIR}")

    def on_key(event):
        if event.key == 'right': slider.set_val(min(slider.val + 1, slider.valmax))
        elif event.key == 'left': slider.set_val(max(slider.val - 1, slider.valmin))
        elif event.key == 'v': save_video_multi()

    fig.canvas.mpl_connect('key_press_event', on_key)
    update_all(0)
    plt.show()