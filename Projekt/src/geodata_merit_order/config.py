"""
Konfiguration für die Merit-Order Visualisierung.
Definiert alle verfügbaren Szenarien und deren Parameter.
"""

# Szenario-Konfigurationen
SCENARIOS = {
    # Deutschland als einzelne Zone
    'de_single': {
        'file_keyword': 'DE_SINGLE',
        'sheet': 'timeseries_insel',
        'zones': ['de'],
        'description': 'Deutschland (eine Zone)'
    },
    
    # 4-Zonen-Modell (ÜNB-Gebiete)
    'z4_insel': {
        'file_keyword': 'Z4_INSEL',
        'sheet': 'timeseries_insel',
        'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
        'description': '4 Zonen - Inselbetrachtung'
    },
    'z4_coupled': {
        'file_keyword': 'Z4_COUPLED',
        'sheet': 'timeseries_coupled',
        'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
        'description': '4 Zonen - Gekoppelt'
    },
    'z4_diff': {
        'file_keyword': 'Z4_COUPLED',
        'sheet': 'timeseries_coupled',
        'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
        'description': '4 Zonen - Preisdifferenz (Coupled - Insel)'
    },
    
    # Nord-Süd-Modell
    'ns_insel': {
        'file_keyword': 'NS_INSEL',
        'sheet': 'timeseries_insel',
        'zones': ['north', 'south'],
        'description': 'Nord-Süd - Inselbetrachtung'
    },
    'ns_coupled': {
        'file_keyword': 'NS_COUPLED',
        'sheet': 'timeseries_coupled',
        'zones': ['north', 'south'],
        'description': 'Nord-Süd - Gekoppelt'
    },
    'ns_diff': {
        'file_keyword': 'NS_COUPLED',
        'sheet': 'timeseries_coupled',
        'zones': ['north', 'south'],
        'description': 'Nord-Süd - Preisdifferenz (Coupled - Insel)'
    },
}

# Mapping von Zonennamen zu Bundesländern (für Geodaten)
ZONE_BUNDESLAENDER = {
    '50Hertz': ['Brandenburg', 'Mecklenburg-Vorpommern', 'Sachsen', 'Sachsen-Anhalt', 'Thüringen', 'Berlin'],
    'TenneT': ['Schleswig-Holstein', 'Niedersachsen', 'Bremen', 'Hamburg', 'Bayern'],
    'Amprion': ['Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Hessen'],
    'TransnetBW': ['Baden-Württemberg'],
    'north': ['Schleswig-Holstein', 'Niedersachsen', 'Bremen', 'Hamburg', 'Mecklenburg-Vorpommern', 
              'Brandenburg', 'Berlin', 'Sachsen-Anhalt'],
    'south': ['Bayern', 'Baden-Württemberg', 'Hessen', 'Thüringen', 'Sachsen', 
              'Rheinland-Pfalz', 'Saarland', 'Nordrhein-Westfalen'],
    'de': ['alle']
}

# ============================================================================
# EINHEITLICHE FARBSKALA FÜR ALLE PREIS-SZENARIEN
# ============================================================================
# Diese Werte werden für ALLE Szenarien verwendet (außer Differenz-Szenarien)
# So sind die Visualisierungen direkt vergleichbar!

PRICE_SCALE = {
    'vmin': 0,        # Minimaler Preis (€/MWh)
    'vmax': 500,      # Maximaler Preis (€/MWh) - Erhöht für Inselbetrachtung
    'cmap': 'YlOrRd'  # Farbskala: Gelb (günstig) -> Orange -> Rot (teuer)
}

# Farbskala für Differenz-Szenarien (symmetrisch um 0)
DIFF_SCALE = {
    'vmax': 50,         # Maximale Differenz (±€/MWh)
    'cmap': 'RdYlGn_r'  # Rot (teurer) -> Gelb (gleich) -> Grün (günstiger)
}

# ============================================================================
# VISUALISIERUNGS-EINSTELLUNGEN
# ============================================================================
VIS_SETTINGS = {
    'figsize': (14, 10),
    'dpi': 150,
    'background_color': '#1e1e1e',
    'map_background': '#2d2d2d',
    'border_color': '#ffffff',
    'text_color': '#ffffff',
    'accent_color': '#4a9eff',
}

# ============================================================================
# VIDEO-EXPORT EINSTELLUNGEN
# ============================================================================
VIDEO_SETTINGS = {
    'fps': 8,           # Frames pro Sekunde
    'dpi': 150,         # Auflösung
    'bitrate': 5000,    # Bitrate für Qualität
}