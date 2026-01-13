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

# --- 1. Geodaten generieren (Bundesländer-Mapping) ---
def create_germany_zones():
    print("Generiere Deutschland-Karte (mit Glättung)...")
    
    url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
    
    try:
        states_gdf = gpd.read_file(url)
        name_col = next((c for c in states_gdf.columns if c.lower() in ['name', 'name_1', 'gen', 'bundesland']), None)
        if not name_col: return create_fallback_rectangles()
    except Exception:
        return create_fallback_rectangles()

    # Mapping: Bundesland -> Regelzone (TSO)
    tso_mapping = {
        'Baden-Württemberg': 'TransnetBW',
        'Bayern': 'TenneT',
        'Berlin': '50Hertz',
        'Brandenburg': '50Hertz',
        'Bremen': 'TenneT',
        'Hamburg': '50Hertz', 
        'Hessen': 'TenneT',
        'Mecklenburg-Vorpommern': '50Hertz',
        'Niedersachsen': 'TenneT',
        'Nordrhein-Westfalen': 'Amprion',
        'Rheinland-Pfalz': 'Amprion',
        'Saarland': 'Amprion',
        'Sachsen': '50Hertz',
        'Sachsen-Anhalt': '50Hertz',
        'Schleswig-Holstein': 'TenneT',
        'Thüringen': '50Hertz'
    }

    states_gdf['zone'] = states_gdf[name_col].map(tso_mapping)
    
    # 1. Zusammenfassen (Dissolve)
    zones_gdf = states_gdf.dropna(subset=['zone']).dissolve(by='zone').reset_index()
    
    # 2. Bereinigen: Explode -> Filter kleine Inseln -> Re-Dissolve
    #    Dies entfernt visuelles "Rauschen" an den Küsten
    zones_exploded = zones_gdf.explode(index_parts=False)
    # Behalte nur Polygone mit relevanter Größe (Grad^2)
    zones_exploded = zones_exploded[zones_exploded.geometry.area > 0.02] 
    zones_gdf = zones_exploded.dissolve(by='zone').reset_index()
    
    # 3. Glätten (Simplify) für den "Comic-Look" der Referenzgrafik
    #    Toleranz 0.05 sorgt für glatte Kanten ohne Details
    zones_gdf['geometry'] = zones_gdf.simplify(0.05)
    
    return zones_gdf[['zone', 'geometry']]

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

# --- 5. Preise berechnen (Hourly -> dann Monthly Average) ---
print("Berechne stündliche Preise...")
hourly_prices = pd.DataFrame(index=res_loads.index)

for zone in ZONE_NAMES:
    if zone not in res_loads.columns: continue
    stack = merit_orders.get(zone)
    if stack is None or stack.empty:
        hourly_prices[zone] = np.nan
        continue
    
    x_cap = stack['acum_mw'].values
    y_price = stack['mc'].values
    
    loads = res_loads[zone].fillna(0).values
    
    # Indizes finden
    loads_clipped = np.clip(loads, 0, x_cap[-1])
    indices = np.searchsorted(x_cap, loads_clipped)
    indices = np.clip(indices, 0, len(y_price)-1)
    
    prices = y_price[indices]
    
    # Optional: Bei negativer Last Preis auf 0 setzen
    prices[loads <= 0] = 0
    
    hourly_prices[zone] = prices

# --- 5b. Aggregation auf typische 24h-Profile pro Monat ---
print("Berechne typische Tagesverläufe (Ø pro Stunde je Monat)...")

# Wir fügen temporäre Spalten hinzu, um danach zu gruppieren
hourly_prices['year'] = hourly_prices.index.year
hourly_prices['month'] = hourly_prices.index.month
hourly_prices['hour'] = hourly_prices.index.hour

# Gruppieren nach Jahr, Monat, Stunde -> Mittelwert
# Das erzeugt für jedes Jahr 12 Monate * 24 Stunden = 288 Datenpunkte
monthly_profiles = hourly_prices.groupby(['year', 'month', 'hour']).mean()

# --- 6. Visualisierung (Profil-Animation) ---
print("Starte Animation (Stunden-Profile pro Monat)...")

gdf_list = []

# Dictionary für deutsche Monatsnamen
german_months = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
}

# Durch das gruppierte Profil iterieren
for (year, month, hour), row in monthly_profiles.iterrows():
    temp = gdf.copy()
    vals = []
    
    # Preisdaten für diese Stunde mappen
    for idx, geo_row in temp.iterrows():
        z_name = geo_row['zone']
        vals.append(row.get(z_name, np.nan))
    
    temp['price'] = vals
    
    # Label erstellen: z.B. "Januar 2024 | 14:00 Uhr"
    m_name = german_months.get(month, str(month))
    title_text = f"{m_name} {year} – Durchschnitt {hour:02d}:00 Uhr"
    temp['label_title'] = title_text
    
    gdf_list.append(temp)

# Hintergrund laden
try:
    world_map = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    europe_box = box(3, 46, 17, 56)
    bg_map = world_map.clip(europe_box)
except:
    bg_map = None

fig, ax = plt.subplots(figsize=(10, 12)) 
fig.patch.set_facecolor('#dce6f2')
ax.set_facecolor('#dce6f2')
plt.subplots_adjust(bottom=0.15, top=0.9, left=0.05, right=0.95)

# Colorbar Skalierung anpassen
# Da wir Stundenwerte betrachten (Morgenspitze/Abendspitze), sind die Preise dynamischer als beim Monatsmittel
zone_cols = [c for c in monthly_profiles.columns if c in ZONE_NAMES]
all_vals = monthly_profiles[zone_cols].values.flatten()
all_vals = all_vals[~np.isnan(all_vals)]

if len(all_vals) > 0:
    vmax = np.percentile(all_vals, 98) # Spitzen besser abdecken
    vmin = max(0, np.min(all_vals))
else:
    vmax = 150
    vmin = 0

cmap = 'Blues'
sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', pad=0.02, aspect=50)
cbar.set_label('Ø Stundenpreis (Typical Day) [€/MWh]')
cbar.outline.set_visible(False)

def update_plot(val):
    frame = int(val)
    ax.clear()
    ax.set_axis_off()
    
    data = gdf_list[frame]
    title_str = data['label_title'].iloc[0]
    
    if bg_map is not None:
        bg_map.plot(ax=ax, facecolor='#e0e0e0', edgecolor='white', linewidth=0.5)

    data.plot(column='price', ax=ax, cmap=cmap, vmin=vmin, vmax=vmax,
              alpha=0.9, edgecolor=None)
    
    data.boundary.plot(ax=ax, edgecolor='#005b96', linewidth=2.5)
    
    for _, geo_row in data.iterrows():
        zone_name = geo_row['zone']
        p = geo_row['price']
        
        pt = geo_row['geometry'].representative_point()
        pt_x, pt_y = pt.x, pt.y
        
        if zone_name == "TenneT": pt_y -= 0.5 
        elif zone_name == "50Hertz": pt_x += 0.2; pt_y -= 0.3
        
        if pd.isna(p): val_txt = "-"
        else: val_txt = f"{p:.1f} €"

        ax.text(pt_x, pt_y + 0.15, zone_name, ha='center', va='bottom', 
                fontsize=9, color='#004a7c', fontweight='bold', zorder=10)
        
        ax.text(pt_x, pt_y - 0.15, val_txt, ha='center', va='top', 
                fontsize=11, fontweight='bold', color='black', 
                path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground='white')],
                zorder=10)
        
    ax.set_title(f"Typisches Tagesprofil (Monat)\n{title_str}", fontsize=14, color='#333333', fontweight='bold')

# Slider Setup
ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
slider = Slider(ax_slider, 'Zeit', 0, len(gdf_list)-1, valinit=0, valstep=1)
slider.on_changed(lambda v: (update_plot(v), fig.canvas.draw_idle()))

# Erweiterte Tastensteuerung
def on_key(event):
    curr = slider.val
    if event.key == 'right':
        # Eine Stunde vor
        new_val = min(curr + 1, slider.valmax)
        slider.set_val(new_val)
    elif event.key == 'left':
        # Eine Stunde zurück
        new_val = max(curr - 1, slider.valmin)
        slider.set_val(new_val)
    elif event.key == 'up':
        # Einen Monat vor (ca. +24 Schritte)
        new_val = min(curr + 24, slider.valmax)
        slider.set_val(new_val)
    elif event.key == 'down':
        # Einen Monat zurück
        new_val = max(curr - 24, slider.valmin)
        slider.set_val(new_val)

fig.canvas.mpl_connect('key_press_event', on_key)

print("GUI gestartet.")
print("Steuerung: [Links/Rechts] = Stunde ±1 | [Hoch/Runter] = Monat ±1")
update_plot(0)
plt.show()
