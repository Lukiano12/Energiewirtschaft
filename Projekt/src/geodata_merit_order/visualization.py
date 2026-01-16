import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects
from matplotlib.widgets import Slider
from matplotlib.animation import FuncAnimation
from shapely.geometry import box
import geopandas as gpd
from . import gui

def calculate_hourly_prices(res_loads, merit_orders, zone_names, direct_prices=None):
    """
    Berechnet die stündlichen Preise.
    
    - Wenn direct_prices vorhanden: Verwende diese (für COUPLED-Szenarien)
    - Sonst: Berechne über Merit-Order-Lookup (für INSEL-Szenarien)
    """
    print("Berechne stündliche Preise...")
    hourly_prices = pd.DataFrame(index=res_loads.index)
    
    for zone in zone_names:
        # Option 1: Direkte Preise verwenden (COUPLED)
        if direct_prices is not None and zone in direct_prices.columns:
            prices = direct_prices[zone].values
            # NaN-Werte durch 0 ersetzen (kein konv. Bedarf = Preis 0)
            prices = np.nan_to_num(prices, nan=0.0)
            hourly_prices[zone] = prices
            valid_prices = prices[prices > 0]
            if len(valid_prices) > 0:
                print(f"  Zone '{zone}': Direkte Preise verwendet, Bereich {valid_prices.min():.1f} - {valid_prices.max():.1f} €/MWh")
            else:
                print(f"  Zone '{zone}': Direkte Preise verwendet, alle Werte 0 oder NaN")
            continue
        
        # Option 2: Merit-Order-Lookup (INSEL)
        if zone not in res_loads.columns:
            print(f"  WARNUNG: Zone '{zone}' nicht in Residuallast-Daten")
            hourly_prices[zone] = np.nan
            continue
            
        stack = merit_orders.get(zone)
        if stack is None or stack.empty:
            print(f"  WARNUNG: Kein Merit-Order-Stack für Zone '{zone}'")
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
        print(f"  Zone '{zone}': Merit-Order-Lookup, Bereich {prices.min():.1f} - {prices.max():.1f} €/MWh")
    
    return hourly_prices

def create_animation_frames(gdf, hourly_prices):
    """Erstellt die Daten für jeden Frame der Animation."""
    print("Berechne typische Tagesverläufe (Ø pro Stunde je Monat)...")
    
    # Zonennamen aus GeoDataFrame
    gdf_zones = list(gdf['zone'].unique())
    
    hourly_prices = hourly_prices.copy()
    hourly_prices['year'] = hourly_prices.index.year
    hourly_prices['month'] = hourly_prices.index.month
    hourly_prices['hour'] = hourly_prices.index.hour
    
    # Nur die Zonen-Spalten für die Gruppierung verwenden
    zone_cols = [c for c in hourly_prices.columns if c in gdf_zones]
    
    if not zone_cols:
        print(f"  FEHLER: Keine übereinstimmenden Zonen gefunden!")
        print(f"    GDF Zonen: {gdf_zones}")
        print(f"    Preis-Spalten: {[c for c in hourly_prices.columns if c not in ['year', 'month', 'hour']]}")
        return [], pd.DataFrame()
    
    print(f"  Zonen für Animation: {zone_cols}")
    
    monthly_profiles = hourly_prices.groupby(['year', 'month', 'hour'])[zone_cols].mean()
    
    print("Starte Animation (Stunden-Profile pro Monat)...")
    gdf_list = []
    german_months = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }

    for (year, month, hour), row in monthly_profiles.iterrows():
        temp_gdf = gdf.copy()
        
        # Preise für jede Zone zuweisen
        prices = []
        for zone in temp_gdf['zone']:
            if zone in row.index:
                prices.append(row[zone])
            else:
                prices.append(np.nan)
        
        temp_gdf['price'] = prices
        
        m_name = german_months.get(month, str(month))
        temp_gdf['label_title'] = f"{m_name} {year} – Durchschnitt {hour:02d}:00 Uhr"
        
        gdf_list.append(temp_gdf)
    
    # Debug: Ersten Frame prüfen
    if gdf_list:
        first_frame = gdf_list[0]
        print(f"  Erster Frame - Zonen: {list(first_frame['zone'])}, Preise: {list(first_frame['price'])}")
    
    return gdf_list, monthly_profiles

def run_visualization(gdf_list, monthly_profiles, zone_names, scenario_id, script_dir):
    """Initialisiert und startet die Matplotlib-Visualisierung."""
    is_diff_scenario = 'diff' in scenario_id

    try:
        world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        bg_map = world_map.clip(box(3, 46, 17, 56))
    except:
        bg_map = None

    fig, ax = plt.subplots(figsize=(10, 12))
    fig.patch.set_facecolor('#dce6f2')
    ax.set_facecolor('#dce6f2')
    plt.subplots_adjust(bottom=0.15, top=0.9, left=0.05, right=0.95)

    # Werte für die Farbskala aus allen Frames sammeln
    all_vals = []
    for frame in gdf_list:
        if 'price' in frame.columns:
            vals = frame['price'].dropna().tolist()
            all_vals.extend(vals)
    
    all_vals = np.array(all_vals)
    
    if len(all_vals) == 0:
        print("FEHLER: Keine Preiswerte für Visualisierung vorhanden!")
        plt.close()
        return
    
    print(f"  Preiswerte für Visualisierung: Min={all_vals.min():.1f}, Max={all_vals.max():.1f}")

    if is_diff_scenario:
        vmax = np.percentile(np.abs(all_vals), 98) if len(all_vals) > 0 else 50
        vmin = -vmax
        cmap = 'RdYlGn_r'
        cbar_label = 'Preisdifferenz (Gekoppelt - Insel) [€/MWh]'
    else:
        vmax = np.percentile(all_vals, 98) if len(all_vals) > 0 else 150
        vmin = max(0, np.min(all_vals)) if len(all_vals) > 0 else 0
        cmap = 'YlOrRd'  # Geändert zu einer besseren Farbskala für Preise
        cbar_label = 'Ø Stundenpreis [€/MWh]'

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', pad=0.02, aspect=50)
    cbar.set_label(cbar_label)
    cbar.outline.set_visible(False)

    def update_plot(val):
        frame = int(val)
        ax.clear()
        ax.set_axis_off()
        
        data = gdf_list[frame]
        title_str = data['label_title'].iloc[0]
        
        if bg_map is not None:
            bg_map.plot(ax=ax, facecolor='#e0e0e0', edgecolor='white', linewidth=0.5)

        # Plot mit Preis-Spalte
        data.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, 
                  alpha=0.9, edgecolor=None, missing_kwds={'color': 'lightgray'})
        
        data.boundary.plot(ax=ax, edgecolor='#005b96', linewidth=2.5)
        
        # Labels für jede Zone
        for _, geo_row in data.iterrows():
            zone_name = geo_row['zone']
            p = geo_row['price']
            
            pt = geo_row['geometry'].representative_point()
            pt_x, pt_y = pt.x, pt.y
            
            # Positionsanpassungen
            if zone_name == "TenneT": 
                pt_y -= 0.5
            elif zone_name == "50Hertz": 
                pt_x += 0.2
                pt_y -= 0.3
            elif zone_name in ["de", "DE"]:
                pt_x, pt_y = 10.0, 51.0
            elif zone_name in ["north", "NORD"]:
                pt_y += 0.5
            elif zone_name in ["south", "SUED"]:
                pt_y -= 0.3
            
            # Zonennamen formatieren
            display_name = zone_name.upper() if zone_name in ['de', 'north', 'south'] else zone_name
            
            val_txt = f"{p:+.1f} €" if is_diff_scenario and pd.notna(p) else (f"{p:.1f} €" if pd.notna(p) else "-")
            
            ax.text(pt_x, pt_y + 0.15, display_name, ha='center', va='bottom', 
                    fontsize=9, color='#004a7c', fontweight='bold', zorder=10)
            ax.text(pt_x, pt_y - 0.15, val_txt, ha='center', va='top', 
                    fontsize=11, fontweight='bold', color='black', 
                    path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground='white')], 
                    zorder=10)
        
        # Titel anpassen je nach Szenario
        if is_diff_scenario:
            title_prefix = "Preisdifferenz (Gekoppelt - Insel)"
        elif 'coupled' in scenario_id:
            title_prefix = "Strompreis (Marktgebiet gekoppelt)"
        elif 'insel' in scenario_id:
            title_prefix = "Strompreis (Inselbetrachtung)"
        else:
            title_prefix = "Strompreis (Merit-Order)"
        
        ax.set_title(f"{title_prefix}\n{title_str}", fontsize=14, color='#333333', fontweight='bold')

    ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
    slider = Slider(ax_slider, 'Zeit', 0, len(gdf_list)-1, valinit=0, valstep=1)
    slider.on_changed(lambda v: (update_plot(v), fig.canvas.draw_idle()))

    def on_key(event):
        curr = slider.val
        if event.key == 'right': slider.set_val(min(curr + 1, slider.valmax))
        elif event.key == 'left': slider.set_val(max(curr - 1, slider.valmin))
        elif event.key == 'up': slider.set_val(min(curr + 24, slider.valmax))
        elif event.key == 'down': slider.set_val(max(curr - 24, slider.valmin))
        elif event.key == 'v': save_animation()

    def save_animation():
        if not gui.ask_save_video():
            print("Speichern abgebrochen.")
            return
        print("Starte Video-Export (bitte warten)...")
        anim = FuncAnimation(fig, update_plot, frames=len(gdf_list), interval=150)
        video_filename = f"animation_{scenario_id}_{pd.Timestamp.now():%Y%m%d}.mp4"
        output_path = script_dir.parent.parent / "output" / "figures" / video_filename
        output_path.parent.mkdir(exist_ok=True)
        anim.save(str(output_path), writer='ffmpeg', dpi=150)
        print(f"Video erfolgreich gespeichert unter: {output_path}")

    fig.canvas.mpl_connect('key_press_event', on_key)
    print("GUI gestartet.")
    print("Steuerung: [Links/Rechts] = Stunde ±1 | [Hoch/Runter] = Monat ±1 | [v] = Video speichern")
    update_plot(0)
    plt.show()