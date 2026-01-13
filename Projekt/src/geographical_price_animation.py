"""
Geografische Preis-Animation auf Deutschland-Karte.

Methode: "Geometric Cutting"
- Lädt Deutschland-Umriss (Lokal oder Online-Backup für Geopandas 1.0+).
- Schneidet Deutschland geometrisch in die 4 Regelzonen (Approximation).
- Berechnet Preise basierend auf Excel-Daten.
"""
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from shapely.geometry import Polygon, box
import numpy as np
import matplotlib.patheffects
from pathlib import Path
import sys
import glob
import os
import warnings

warnings.filterwarnings("ignore")

# --- 0. Setup & Pfade ---
script_dir = Path(__file__).resolve().parent
output_dir = script_dir.parent / "output" / "excel"

# --- Konfiguration ---
ZONE_NAMES = ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW']

# --- 1. Geodaten generieren (Cutting-Methode) ---
def create_germany_zones():
    print("Generiere Deutschland-Karte...")
    germany = None
    
    # VERSUCH 1: GeoPandas intern (für ältere Versionen < 1.0)
    try:
        # Dies wirft in neuen Versionen einen Fehler, den fangen wir ab
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        germany = world[world.name == "Germany"].geometry.iloc[0]
    except Exception:
        pass # Weiter zu Versuch 2

    # VERSUCH 2: Fallback Online Download (für GeoPandas 1.0+)
    if germany is None:
        print("  -> GeoPandas Dataset fehlt. Lade Deutschland-Umriss online...")
        try:
            # Stabile URL für Ländergrenzen (High Def nicht nötig, Low Res reicht)
            url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
            world = gpd.read_file(url)
            # In diesem Datensatz heißt Deutschland meist "Germany" oder Code "DEU"
            row = world[world['name'] == 'Germany']
            if row.empty:
                row = world[world['id'] == 'DEU']
            
            if not row.empty:
                germany = row.geometry.iloc[0]
            else:
                print("  -> FEHLER: Deutschland in Online-Daten nicht gefunden.")
        except Exception as e:
            print(f"  -> FEHLER beim Download: {e}")

    # Notfall-Fallback
    if germany is None:
        print("  -> WARNUNG: Konnte keine Karte laden. Nutze Rechtecke.")
        return create_fallback_rectangles()

    print("  -> Karte geladen. Schneide Zonen...")

    # 2. Schnitt-Boxen definieren (Wir 'schneiden' Deutschland in Stücke)
    # Die Koordinaten sind visuelle Annäherungen.
    
    # 50Hertz: Der Osten.
    box_50hertz = box(10.8, 50.2, 16.0, 55.0)
    
    # TransnetBW: Der Südwesten (BaWü). 
    box_transnet = box(7.0, 47.0, 10.2, 49.6) 
    
    # Amprion: Der Westen. Wir definieren eine Box und ziehen TransnetBW später ab.
    box_amprion = box(5.5, 49.6, 9.8, 52.4) 
    
    # 3. Zonen ausschneiden (Intersection mit Deutschland-Form)
    poly_50hertz = germany.intersection(box_50hertz)
    poly_transnet = germany.intersection(box_transnet)
    
    # Amprion ohne Überlappung zu Transnet
    poly_amprion = germany.intersection(box_amprion).difference(poly_transnet)
    
    # 4. TenneT ist der Rest (Norden + Bayern)
    # Wir nehmen gesamt Deutschland und subtrahieren die anderen drei Teile.
    others = poly_50hertz.union(poly_transnet).union(poly_amprion)
    poly_tennet = germany.difference(others)
    
    # 5. Zusammenbauen
    data = {
        'zone': ['50Hertz', 'TransnetBW', 'Amprion', 'TenneT'],
        'geometry': [poly_50hertz, poly_transnet, poly_amprion, poly_tennet]
    }
    
    gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
    
    # Cleanup von Geometrie-Artefakten
    gdf['geometry'] = gdf.simplify(0.01)
    
    return gdf

def create_fallback_rectangles():
    zones_geodata = {
        'zone': ZONE_NAMES,
        'geometry': [
            Polygon([(11.5, 50.5), (15, 50.5), (15, 54.5), (11.5, 54.5)]),
            Polygon([(8.5, 52), (11.5, 52), (11.5, 55), (8.5, 55)]),
            Polygon([(6, 50), (11, 50), (11, 52.5), (6, 52.5)]),
            Polygon([(7.5, 47.5), (10.5, 47.5), (10.5, 50), (7.5, 50)])
        ]
    }
    return gpd.GeoDataFrame(zones_geodata, crs="EPSG:4326")

# Karte erstellen
gdf = create_germany_zones()

# --- 2. Excel-Datei finden ---
def find_latest_excel(directory):
    files = glob.glob(str(directory / "UENB_Model_*.xlsx"))
    if not files: files = glob.glob(str(directory / "*.xlsx"))
    return Path(max(files, key=os.path.getmtime)) if files else None

excel_path = find_latest_excel(output_dir)
if not excel_path:
    print("FEHLER: Keine Excel-Datei gefunden.")
    sys.exit(1)

print(f"Lade Daten aus: {excel_path.name}")

# --- 3. Merit Order laden ---
merit_orders = {}
print("Lade Merit-Order-Stacks...")
xl = pd.ExcelFile(excel_path)

for zone in ZONE_NAMES:
    sheet_name = f"plants_stack_{zone}"
    if sheet_name not in xl.sheet_names:
        merit_orders[zone] = pd.DataFrame(columns=['acum_mw', 'mc'])
        continue
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet_name)
        df.columns = df.columns.astype(str).str.lower()
        mc_col = next((c for c in df.columns if "grenzkosten" in c or "mc" in c), None)
        cap_col = next((c for c in df.columns if "effective" in c or ("cap" in c and "mw" in c)), None)
        if not cap_col: cap_col = df.columns[-1]

        if mc_col and cap_col:
            df = df.sort_values(by=mc_col)
            df['acum_mw'] = df[cap_col].cumsum()
            df['mc'] = df[mc_col]
            stack = df[['acum_mw', 'mc']].copy()
            start_row = pd.DataFrame({'acum_mw': [0], 'mc': [stack['mc'].iloc[0] if not stack.empty else 0]})
            stack = pd.concat([start_row, stack], ignore_index=True)
            merit_orders[zone] = stack
        else:
            merit_orders[zone] = None
    except Exception:
        merit_orders[zone] = None

# --- 4. Zeitreihen laden ---
print("Lade Zeitreihen...")
try:
    ts_raw = pd.read_excel(excel_path, sheet_name='timeseries_insel')
    ts_raw.columns = ts_raw.columns.astype(str).str.lower()
    res_loads = pd.DataFrame()
    if 'zone' in ts_raw.columns:
        time_col = next((c for c in ts_raw.columns if 'date' in c or 'time' in c or 'zeit' in c), ts_raw.columns[0])
        ts_raw[time_col] = pd.to_datetime(ts_raw[time_col])
        load_col = next((c for c in ts_raw.columns if 'load' in c or 'last' in c), None)
        ee_col = next((c for c in ts_raw.columns if 'ee_' in c or 'vre' in c or 'wind' in c), None)
        
        if load_col:
            cols = [time_col, 'zone', load_col]
            if ee_col: cols.append(ee_col)
            data = ts_raw[cols].copy()
            for zone in ZONE_NAMES:
                z_data = data[data['zone'].str.lower() == zone.lower()].set_index(time_col).sort_index()
                if not z_data.empty:
                    res_loads[zone] = z_data[load_col] - (z_data[ee_col] if ee_col else 0)
    
    res_loads.index = pd.to_datetime(res_loads.index)
    res_loads = res_loads.resample('h').mean() 
    print(f"Zeitreihen geladen: {len(res_loads)} Stunden")
except Exception as e:
    print(f"FEHLER: {e}")
    sys.exit(1)

# --- 5. Preise berechnen (Merit Order) ---
print("Berechne Preise...")
calculated_prices = pd.DataFrame(index=res_loads.index)

for zone in ZONE_NAMES:
    if zone not in res_loads.columns: continue
    stack = merit_orders.get(zone)
    if stack is None or stack.empty:
        calculated_prices[zone] = np.nan
        continue
    x_cap = stack['acum_mw'].values
    y_price = stack['mc'].values
    loads = res_loads[zone].fillna(0).values
    loads_clipped = np.clip(loads, 0, x_cap[-1])
    indices = np.searchsorted(x_cap, loads_clipped)
    indices = np.clip(indices, 0, len(y_price)-1)
    prices = y_price[indices]
    prices[loads > x_cap[-1]] = 500
    prices[loads <= 0] = 0
    calculated_prices[zone] = prices

# --- 6. Visualisierung ---
print("Starte Animation...")
# Frames reduzieren
step = 1 if len(calculated_prices) <= 2000 else (len(calculated_prices) // 500)
if step < 1: step = 1
gdf_list = []

subset = calculated_prices.iloc[::step]
for timestamp, row in subset.iterrows():
    temp = gdf.copy()
    vals = []
    for idx, geo_row in temp.iterrows():
        z_name = geo_row['zone']
        vals.append(row.get(z_name, np.nan))
    temp['price'] = vals
    temp['timestamp'] = timestamp
    gdf_list.append(temp)

fig, ax = plt.subplots(figsize=(10, 12)) 
plt.subplots_adjust(bottom=0.15, top=0.9, left=0.05, right=0.95)

valid_p = calculated_prices.values.flatten()
valid_p = valid_p[~np.isnan(valid_p)]
vmax = np.percentile(valid_p, 98) if len(valid_p) > 0 else 150
if vmax < 20: vmax = 100

cmap = 'jet'
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=vmax))
cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', pad=0.02, aspect=50)
cbar.set_label('Marktpreis (berechnet) [€/MWh]')

def update_plot(val):
    frame = int(val)
    ax.clear()
    ax.set_axis_off()
    
    data = gdf_list[frame]
    ts = data['timestamp'].iloc[0]
    
    # 1. Gefüllte Karte
    data.plot(column='price', ax=ax, cmap=cmap, vmin=0, vmax=vmax,
              edgecolor='white', linewidth=0.5, alpha=0.9)
    
    # 2. Umrisse
    try:
        data.dissolve().plot(ax=ax, facecolor="none", edgecolor="black", linewidth=1.5)
        data.dissolve(by='zone').plot(ax=ax, facecolor="none", edgecolor="black", linewidth=0.5, alpha=0.5)
    except: pass
    
    # Labels
    for zone_name in ZONE_NAMES:
        zone_rows = data[data['zone'] == zone_name]
        if zone_rows.empty: continue
        
        combined_geo = zone_rows.dissolve().geometry.iloc[0]
        pt = combined_geo.representative_point()
        
        # Kleine Korrektur für TenneT
        if zone_name == "TenneT":
            pt_y = pt.y + 0.8 # Höher in den Norden schieben
            pt_x = pt.x 
        else:
            pt_y, pt_x = pt.y, pt.x

        p = zone_rows.iloc[0]['price']
        
        if pd.isna(p):
            val_txt, txt_col = "-", "black"
        elif p >= 499:
            val_txt, txt_col = "MAX", "white"
        else:
            val_txt = f"{p:.0f} €"
            txt_col = 'white' if (p < vmax*0.3 or p > vmax*0.7) else 'black'

        ax.text(pt_x, pt_y + 0.20, zone_name, ha='center', va='center', fontsize=10, color='black', alpha=0.7, fontweight='bold')
        ax.text(pt_x, pt_y - 0.20, val_txt, ha='center', va='center', fontsize=13, fontweight='bold', color=txt_col,
                path_effects=[matplotlib.patheffects.withStroke(linewidth=1.7, foreground='black' if txt_col=='white' else 'white')])
        
    ax.set_title(f"Strompreis-Monitor (Zonen)\n{ts.strftime('%d.%m.%Y %H:%M')}", fontsize=16)

ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
slider = Slider(ax_slider, 'Zeit', 0, len(gdf_list)-1, valinit=0, valstep=1)
slider.on_changed(lambda v: (update_plot(v), fig.canvas.draw_idle()))

update_plot(0)
plt.show()
