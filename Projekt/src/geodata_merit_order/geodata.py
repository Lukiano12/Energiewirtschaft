"""
Geodaten-Modul für die Merit-Order Visualisierung.
Liest GeoJSON OHNE Fiona-Abhängigkeit (nutzt json + shapely direkt).
"""
import json
import geopandas as gpd
from shapely.geometry import shape, Polygon, box
from pathlib import Path
from . import config


def load_geojson_without_fiona(filepath):
    """
    Lädt eine GeoJSON-Datei OHNE Fiona.
    Nutzt Python's json-Modul und Shapely direkt.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data.get('features', [])
    
    records = []
    for feature in features:
        props = feature.get('properties', {})
        geom = feature.get('geometry')
        
        if geom:
            # Shapely's shape() konvertiert GeoJSON-Geometry zu Shapely-Objekt
            shapely_geom = shape(geom)
            record = {**props, 'geometry': shapely_geom}
            records.append(record)
    
    # GeoDataFrame erstellen
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    return gdf


def create_germany_zones(scenario_id, zone_names):
    """Erstellt die Geometrien für die Zonen basierend auf den Bundesländern."""
    print("Generiere Deutschland-Karte aus Bundesländern...")
    
    local_geojson_path = config.RESOURCES_DIR / "3_mittel.geo.json"
    print(f"  Lade GeoJSON von: {local_geojson_path}")
    
    if not local_geojson_path.exists():
        print(f"  FEHLER: Datei nicht gefunden!")
        return create_fallback_rectangles(zone_names)

    try:
        # NEUE METHODE: Ohne Fiona laden!
        gdf_bl = load_geojson_without_fiona(local_geojson_path)
        print(f"  ✓ GeoJSON geladen: {len(gdf_bl)} Bundesländer")
        
        # Prüfen ob 'name' Spalte existiert
        if 'name' not in gdf_bl.columns:
            # Versuche alternative Spaltennamen
            name_col = None
            for col in ['NAME', 'Name', 'NAME_1', 'GEN']:
                if col in gdf_bl.columns:
                    name_col = col
                    break
            
            if name_col:
                gdf_bl['name'] = gdf_bl[name_col]
            else:
                print(f"  WARNUNG: Keine 'name'-Spalte gefunden. Spalten: {gdf_bl.columns.tolist()}")
                return create_fallback_rectangles(zone_names)
        
        # Mapping von Bundesland zu Regelzone (TSO)
        tso_map = {
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
        
        # Neue 'zone'-Spalte basierend auf dem Mapping erstellen
        gdf_bl['zone'] = gdf_bl['name'].map(tso_map)
        
        # Zeilen ohne Zuordnung entfernen
        gdf_bl = gdf_bl.dropna(subset=['zone'])
        
        if gdf_bl.empty:
            print(f"  WARNUNG: Keine Bundesländer konnten zugeordnet werden.")
            print(f"  Vorhandene Namen: {gdf_bl['name'].tolist()[:5]}...")
            return create_fallback_rectangles(zone_names)
        
        # Die Geometrien der Bundesländer pro Regelzone zusammenfassen
        zones_gdf = gdf_bl.dissolve(by='zone').reset_index()

    except Exception as e:
        print(f"  FEHLER beim Verarbeiten der Geodaten: {e}")
        import traceback
        traceback.print_exc()
        return create_fallback_rectangles(zone_names)

    # --- Szenario-spezifische Anpassung ---
    try:
        if scenario_id.startswith('ns_') or scenario_id == 'ns':
            # Nord/Süd-Aufteilung
            ns_mapping = {
                '50Hertz': 'north', 
                'TenneT': 'north',
                'Amprion': 'south', 
                'TransnetBW': 'south'
            }
            zones_gdf['base_zone'] = zones_gdf['zone'].map(ns_mapping)
            
            # TenneT-Geometrie isolieren und teilen
            tennet_rows = zones_gdf[zones_gdf['zone'] == 'TenneT']
            if not tennet_rows.empty:
                tennet_geom = tennet_rows.geometry.iloc[0]
                min_y, max_y = tennet_geom.bounds[1], tennet_geom.bounds[3]
                split_y = min_y + (max_y - min_y) * 0.5
                
                south_cutter = box(
                    zones_gdf.total_bounds[0], 
                    zones_gdf.total_bounds[1], 
                    zones_gdf.total_bounds[2], 
                    split_y
                )
                tennet_south_part = tennet_geom.intersection(south_cutter)

                # Alle Geometrien nach Basis-Regionen zusammenfassen
                zones_gdf = zones_gdf.dissolve(by='base_zone').reset_index()
                
                # Unteren TenneT-Teil von Nord abziehen und zu Süd hinzufügen
                north_rows = zones_gdf[zones_gdf['base_zone'] == 'north']
                south_rows = zones_gdf[zones_gdf['base_zone'] == 'south']
                
                if not north_rows.empty and not south_rows.empty:
                    north_geom = north_rows.geometry.iloc[0]
                    south_geom = south_rows.geometry.iloc[0]
                    
                    final_north = north_geom.difference(tennet_south_part)
                    final_south = south_geom.union(tennet_south_part)
                    
                    zones_gdf = gpd.GeoDataFrame(
                        {'zone': ['north', 'south'], 'geometry': [final_north, final_south]},
                        crs=zones_gdf.crs
                    )
                else:
                    zones_gdf = zones_gdf.rename(columns={'base_zone': 'zone'})
            else:
                zones_gdf = zones_gdf.dissolve(by='base_zone').reset_index()
                zones_gdf = zones_gdf.rename(columns={'base_zone': 'zone'})

        elif scenario_id == 'de_single' or scenario_id.startswith('de_'):
            # Deutschland gesamt: Alle Zonen zu einer verschmelzen
            germany_boundary = zones_gdf.unary_union
            zones_gdf = gpd.GeoDataFrame(
                {'zone': ['de'], 'geometry': [germany_boundary]},
                crs="EPSG:4326"
            )
            
    except Exception as e:
        print(f"  WARNUNG bei Szenario-Anpassung: {e}")
        # Fallback: Originale Zonen zurückgeben
        pass

    print(f"  ✓ {len(zones_gdf)} Zonen erstellt: {zones_gdf['zone'].tolist()}")
    return zones_gdf[['zone', 'geometry']]


def create_fallback_rectangles(zone_names):
    """Erstellt eine variable Anzahl von Fallback-Rechtecken."""
    print("  -> Erstelle Fallback-Rechtecke...")
    
    # Vordefinierte Rechtecke für verschiedene Zonen
    zone_rectangles = {
        'de': Polygon([(6, 47), (15, 47), (15, 55), (6, 55)]),
        'north': Polygon([(6, 52), (15, 52), (15, 55), (6, 55)]),
        'south': Polygon([(6, 47), (15, 47), (15, 52), (6, 52)]),
        '50Hertz': Polygon([(11.5, 50.5), (15, 50.5), (15, 54.5), (11.5, 54.5)]),
        'TenneT': Polygon([(8.5, 52), (11.5, 52), (11.5, 55), (8.5, 55)]),
        'Amprion': Polygon([(6, 50), (11, 50), (11, 52.5), (6, 52.5)]),
        'TransnetBW': Polygon([(7.5, 47.5), (10.5, 47.5), (10.5, 50), (7.5, 50)])
    }
    
    geometries = []
    for zone in zone_names:
        if zone in zone_rectangles:
            geometries.append(zone_rectangles[zone])
        else:
            # Generisches Rechteck
            geometries.append(Polygon([(8, 49), (12, 49), (12, 53), (8, 53)]))
    
    gdf = gpd.GeoDataFrame(
        {'zone': zone_names, 'geometry': geometries},
        crs="EPSG:4326"
    )
    
    return gdf