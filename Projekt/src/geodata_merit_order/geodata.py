import geopandas as gpd
from shapely.geometry import Polygon, box
from pathlib import Path

def create_germany_zones(scenario_id, zone_names):
    """Erstellt die Geometrien für die Zonen basierend auf den Bundesländern."""
    print("Generiere Deutschland-Karte aus Bundesländern...")
    try:
        # Pfad zur lokalen Bundesländer-GeoJSON-Datei
        script_dir = Path(__file__).resolve().parent
        # Korrigierter Dateiname, passend zu Ihrer Projektstruktur
        local_geojson_path = script_dir / "resources" / "3_mittel.geo.json"
        
        if not local_geojson_path.exists():
            raise FileNotFoundError("Lokale Bundesländer-GeoJSON-Datei nicht gefunden.")

        # Lokale Datei laden
        gdf_bl = gpd.read_file(local_geojson_path)
        
        # Mapping von Bundesland zu Regelzone (TSO)
        # Dies ist eine Standardzuordnung und kann angepasst werden
        tso_map = {
            'Baden-Württemberg': 'TransnetBW', 'Bayern': 'TenneT',
            'Berlin': '50Hertz', 'Brandenburg': '50Hertz',
            'Bremen': 'TenneT', 'Hamburg': '50Hertz',
            'Hessen': 'TenneT', 'Mecklenburg-Vorpommern': '50Hertz',
            'Niedersachsen': 'TenneT', 'Nordrhein-Westfalen': 'Amprion',
            'Rheinland-Pfalz': 'Amprion', 'Saarland': 'Amprion',
            'Sachsen': '50Hertz', 'Sachsen-Anhalt': '50Hertz',
            'Schleswig-Holstein': 'TenneT', 'Thüringen': '50Hertz'
        }
        
        # Neue 'zone'-Spalte basierend auf dem Mapping erstellen
        gdf_bl['zone'] = gdf_bl['name'].map(tso_map)
        
        # Die Geometrien der Bundesländer pro Regelzone zusammenfassen
        zones_gdf = gdf_bl.dissolve(by='zone').reset_index()

    except Exception as e:
        print(f"WARNUNG: Geodaten konnten nicht geladen werden ({e}). Nutze Fallback-Rechtecke.")
        return create_fallback_rectangles(zone_names)

    # --- Szenario-spezifische Anpassung ---
    if scenario_id.startswith('ns_'):
        # Nord/Süd-Aufteilung, die die geteilte TenneT-Zone visuell annähert.
        # Amprion+TransnetBW=SÜD, 50Hertz=NORD, TenneT wird geteilt.
        
        # 1. Zonen den Basis-Regionen zuordnen
        ns_mapping = {
            '50Hertz': 'north', 'TenneT': 'north', # TenneT wird erstmal NORD zugeordnet
            'Amprion': 'south', 'TransnetBW': 'south'
        }
        zones_gdf['base_zone'] = zones_gdf['zone'].map(ns_mapping)
        
        # 2. TenneT-Geometrie isolieren und teilen
        tennet_geom = zones_gdf[zones_gdf['zone'] == 'TenneT'].geometry.iloc[0]
        min_y, max_y = tennet_geom.bounds[1], tennet_geom.bounds[3]
        split_y = min_y + (max_y - min_y) * 0.5  # Horizontale Teilung bei 50%
        south_cutter = box(zones_gdf.total_bounds[0], zones_gdf.total_bounds[1], zones_gdf.total_bounds[2], split_y)
        tennet_south_part = tennet_geom.intersection(south_cutter)

        # 3. Alle Geometrien nach Basis-Regionen zusammenfassen
        zones_gdf = zones_gdf.dissolve(by='base_zone').reset_index()
        
        # 4. Unteren TenneT-Teil von Nord abziehen und zu Süd hinzufügen
        north_geom = zones_gdf[zones_gdf['base_zone'] == 'north'].geometry.iloc[0]
        south_geom = zones_gdf[zones_gdf['base_zone'] == 'south'].geometry.iloc[0]
        
        final_north = north_geom.difference(tennet_south_part)
        final_south = south_geom.union(tennet_south_part)
        
        # 5. Finalen GeoDataFrame erstellen
        zones_gdf = gpd.GeoDataFrame(
            {'zone': ['north', 'south'], 'geometry': [final_north, final_south]},
            crs=zones_gdf.crs
        )

    elif scenario_id == 'de_single':
        # Deutschland gesamt: Alle Zonen zu einer verschmelzen
        germany_boundary = zones_gdf.unary_union
        zones_gdf = gpd.GeoDataFrame({'zone': ['de'], 'geometry': [germany_boundary]})

    return zones_gdf[['zone', 'geometry']]

def create_fallback_rectangles(zone_names):
    """Erstellt eine variable Anzahl von Fallback-Rechtecken."""
    geometries = [
        Polygon([(11.5, 50.5), (15, 50.5), (15, 54.5), (11.5, 54.5)]),
        Polygon([(8.5, 52), (11.5, 52), (11.5, 55), (8.5, 55)]),
        Polygon([(6, 50), (11, 50), (11, 52.5), (6, 52.5)]),
        Polygon([(7.5, 47.5), (10.5, 47.5), (10.5, 50), (7.5, 50)])
    ]
    num_zones = len(zone_names)
    zones_geodata = {
        'zone': zone_names,
        'geometry': geometries[:num_zones]
    }
    return gpd.GeoDataFrame(zones_geodata, crs="EPSG:4326")