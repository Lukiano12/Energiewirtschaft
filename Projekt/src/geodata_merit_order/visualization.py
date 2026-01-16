import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects
from matplotlib.widgets import Slider
from shapely.geometry import box
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm
import imageio
import tempfile
import os
from . import gui, config

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
    """Erstellt die Daten fuer jeden Frame der Animation."""
    print("Berechne typische Tagesverlaeufe (Durchschnitt pro Stunde je Monat)...")
    
    gdf_zones = list(gdf['zone'].unique())
    
    hourly_prices = hourly_prices.copy()
    hourly_prices['year'] = hourly_prices.index.year
    hourly_prices['month'] = hourly_prices.index.month
    hourly_prices['hour'] = hourly_prices.index.hour
    
    zone_cols = [c for c in hourly_prices.columns if c in gdf_zones]
    
    if not zone_cols:
        print(f"  FEHLER: Keine uebereinstimmenden Zonen gefunden!")
        return [], pd.DataFrame()
    
    print(f"  Zonen fuer Animation: {zone_cols}")
    
    monthly_profiles = hourly_prices.groupby(['year', 'month', 'hour'])[zone_cols].mean()
    
    print("Erstelle Animations-Frames...")
    gdf_list = []
    german_months = {
        1: "Januar", 2: "Februar", 3: "Maerz", 4: "April", 
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }

    for (year, month, hour), row in monthly_profiles.iterrows():
        temp_gdf = gdf.copy()
        
        prices = []
        for zone in temp_gdf['zone']:
            if zone in row.index:
                prices.append(row[zone])
            else:
                prices.append(np.nan)
        
        temp_gdf['price'] = prices
        
        m_name = german_months.get(month, str(month))
        temp_gdf['label_title'] = f"{m_name} {year} - {hour:02d}:00 Uhr"
        temp_gdf['month'] = month
        temp_gdf['hour'] = hour
        
        gdf_list.append(temp_gdf)
    
    if gdf_list:
        print(f"  {len(gdf_list)} Frames erstellt")
    
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
        """Exportiert die Animation als MP4-Video."""
        if not gui.ask_save_video():
            print("Video-Export abgebrochen.")
            return
        
        print("\n" + "="*60)
        print("VIDEO-EXPORT GESTARTET")
        print("="*60)
        
        # Output-Pfad im geodata_merit_order Ordner
        output_dir = script_dir / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"merit_order_{scenario_id}_{timestamp}.mp4"
        output_path = output_dir / video_filename
        
        print(f"  Ziel: {output_path}")
        print(f"  Frames: {len(gdf_list)}")
        print(f"  FPS: {config.VIDEO_SETTINGS['fps']}")
        print("-"*60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            frame_paths = []
            
            # Figure mit fester Groesse (durch 2 teilbar fuer H.264!)
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
                
                data.plot(
                    column='price', 
                    ax=ax_video, 
                    cmap=cmap, 
                    vmin=vmin, 
                    vmax=vmax,
                    alpha=0.85, 
                    edgecolor='#005b96',
                    linewidth=2,
                    missing_kwds={'color': '#cccccc'}
                )
                
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
                    
                    ax_video.text(pt_x, pt_y + 0.3, display_name, ha='center', va='bottom',
                                 fontsize=10, color='black', fontweight='bold',
                                 path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground='white')])
                    ax_video.text(pt_x, pt_y - 0.2, val_txt, ha='center', va='top',
                                 fontsize=12, fontweight='bold', color='black',
                                 path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground='white')])
                
                ax_video.set_xlim(5, 16)
                ax_video.set_ylim(47, 55.5)
                ax_video.set_title(f"{scenario_title}\n{title_str}", fontsize=14, fontweight='bold')
                ax_video.axis('off')
                
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                fig_video.savefig(frame_path, dpi=100, bbox_inches='tight', pad_inches=0.1)
                frame_paths.append(frame_path)
            
            plt.close(fig_video)
            
            # Bilder laden und Groesse anpassen (durch 2 teilbar)
            print("\nErstelle Video...")
            
            # Erstes Bild laden um Groesse zu pruefen
            first_frame = imageio.imread(frame_paths[0])
            h, w = first_frame.shape[:2]
            
            # Auf gerade Zahlen runden (H.264 Anforderung)
            new_h = h if h % 2 == 0 else h - 1
            new_w = w if w % 2 == 0 else w - 1
            
            print(f"  Bildgroesse: {w}x{h} -> {new_w}x{new_h} (H.264 kompatibel)")
            
            try:
                writer = imageio.get_writer(
                    str(output_path), 
                    fps=config.VIDEO_SETTINGS['fps'],
                    codec='libx264',
                    quality=8,
                    pixelformat='yuv420p',
                    output_params=['-vf', f'scale={new_w}:{new_h}']
                )
                
                for frame_path in tqdm(frame_paths, desc="  Encoding", unit="frame",
                                      ncols=70, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'):
                    frame = imageio.imread(frame_path)
                    # Zuschneiden auf gerade Groesse
                    frame = frame[:new_h, :new_w]
                    writer.append_data(frame)
                
                writer.close()
                
                file_size = output_path.stat().st_size / 1024 / 1024
                duration = len(gdf_list) / config.VIDEO_SETTINGS['fps']
                
                print("\n" + "="*60)
                print("VIDEO ERFOLGREICH GESPEICHERT!")
                print("="*60)
                print(f"  Pfad: {output_path}")
                print(f"  Groesse: {file_size:.1f} MB")
                print(f"  Dauer: {duration:.1f} Sekunden")
                print("="*60 + "\n")
                
                gui.show_info(
                    "Video-Export erfolgreich", 
                    f"Video gespeichert unter:\n\n{output_path}\n\n"
                    f"Groesse: {file_size:.1f} MB\n"
                    f"Dauer: {duration:.1f} Sekunden"
                )
                
            except Exception as e:
                print(f"\nFEHLER beim Video-Export: {e}")
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