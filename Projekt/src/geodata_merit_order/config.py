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
        'file_keyword': 'Z4_COUPLED',  # Wird nicht direkt verwendet
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
        'file_keyword': 'NS_COUPLED',  # Wird nicht direkt verwendet
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
    'de': ['alle']  # Alle Bundesländer
}

# Visualisierungs-Einstellungen
VIS_SETTINGS = {
    'figsize': (10, 12),
    'dpi': 150,
    'cmap_price': 'YlOrRd',
    'cmap_diff': 'RdYlGn_r',
    'background_color': '#dce6f2',
    'border_color': '#005b96',
}