"""
Konfiguration für die Merit-Order Visualisierung.
Definiert alle verfügbaren Szenarien und deren Parameter.
"""
from pathlib import Path

# Basis-Verzeichnisse
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SMARD_DIR = DATA_DIR / "smard"
RESOURCES_DIR = SCRIPT_DIR / "resources"

# NEU: Ordner für Video-Exports definieren
VIDEOS_DIR = SCRIPT_DIR / "videos"

# NEU: Pfad zur manuell heruntergeladenen ffmpeg.exe
FFMPEG_BINARY = RESOURCES_DIR / "ffmpeg.exe"

# Verfügbare Jahre
AVAILABLE_YEARS = [2024, 2037, 2045]

# EPEX-Preisdatei (jetzt im resources-Ordner!)
EPEX_PRICE_FILE = RESOURCES_DIR / "Day_Ahead_Auktion_202401010000_202501010000_Viertelstunde.xlsx"

# Szenario-Konfigurationen - dynamisch für alle Jahre generiert
def generate_scenarios():
    """Generiert Szenario-Konfigurationen für alle Jahre."""
    scenarios = {}
    
    for year in AVAILABLE_YEARS:
        year_suffix = f"_{year}" if year != 2024 else "_2024"
        
        # Deutschland als einzelne Zone
        scenarios[f'de_single_{year}'] = {
            'file_keyword': f'{year}_DE_SINGLE',
            'sheet': 'timeseries_insel',
            'zones': ['de'],
            'description': f'Deutschland {year} (eine Zone)',
            'year': year
        }
        
        # 4-Zonen-Modell (ÜNB-Gebiete)
        scenarios[f'z4_insel_{year}'] = {
            'file_keyword': f'{year}_Z4_INSEL',
            'sheet': 'timeseries_insel',
            'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
            'description': f'4 Zonen {year} - Inselbetrachtung',
            'year': year
        }
        scenarios[f'z4_coupled_{year}'] = {
            'file_keyword': f'{year}_Z4_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
            'description': f'4 Zonen {year} - Gekoppelt',
            'year': year
        }
        scenarios[f'z4_diff_{year}'] = {
            'file_keyword': f'{year}_Z4_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['50Hertz', 'TenneT', 'Amprion', 'TransnetBW'],
            'description': f'4 Zonen {year} - Preisdifferenz',
            'year': year
        }
        
        # Nord-Süd-Modell
        scenarios[f'ns_insel_{year}'] = {
            'file_keyword': f'{year}_NS_INSEL',
            'sheet': 'timeseries_insel',
            'zones': ['north', 'south'],
            'description': f'Nord-Süd {year} - Inselbetrachtung',
            'year': year
        }
        scenarios[f'ns_coupled_{year}'] = {
            'file_keyword': f'{year}_NS_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['north', 'south'],
            'description': f'Nord-Süd {year} - Gekoppelt',
            'year': year
        }
        scenarios[f'ns_diff_{year}'] = {
            'file_keyword': f'{year}_NS_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['north', 'south'],
            'description': f'Nord-Süd {year} - Preisdifferenz',
            'year': year
        }
    
    # Spezielles Szenario: EPEX-Vergleich (nur 2024)
    scenarios['epex_comparison_2024'] = {
        'file_keyword': '2024_DE_SINGLE',
        'sheet': 'timeseries_insel',
        'zones': ['de'],
        'description': '📊 EPEX-Vergleich 2024 (Modell vs. Realität)',
        'year': 2024,
        'is_epex_comparison': True
    }
    
    return scenarios

SCENARIOS = generate_scenarios()

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
PRICE_SCALE = {
    'vmin': 0,
    'vmax': 500,
    'cmap': 'YlOrRd'
}

# Farbskala für Differenz-Szenarien (symmetrisch um 0)
DIFF_SCALE = {
    'vmax': 50,
    'cmap': 'RdYlGn_r'
}

# Farbskala für EPEX-Vergleich
EPEX_COMPARISON_SCALE = {
    'vmax': 100,  # ±100 €/MWh Abweichung
    'cmap': 'RdBu_r'  # Rot = Modell teurer, Blau = Modell günstiger
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
    'fps': 8,
    'dpi': 150,
    'bitrate': 5000,
}