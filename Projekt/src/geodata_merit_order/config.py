"""
Konfiguration für die Merit-Order Visualisierung.
Definiert alle verfügbaren Szenarien und deren Parameter.
"""
from pathlib import Path
import os
import sys

# ============================================================================
# ORTSBESTIMMUNG & PFADE
# ============================================================================

# Bestimmen, ob wir als EXE oder als Python-Skript laufen
if getattr(sys, 'frozen', False):
    # FALL: Fertige .EXE Datei
    # Der temporäre Ordner des Entpackers (PyInstaller _MEI...)
    # ODER der Ordner wo die EXE liegt, je nach Bündelung.
    # Sicherer Ansatz für Daten: sys.executable parent
    APP_DIR = Path(sys.executable).parent
    IS_FROZEN = True
    
    # Speicherort auf Desktop zwingen (wegen Schreibrechten)
    OUTPUT_DIR = Path.home() / "Desktop" / "Energiewirtschaft_Output"
    
    # FFMPEG Pfad in der EXE (muss beim Bauen mit --add-binary hinzugefügt werden)
    # Wenn wir es in 'resources' legen, finden wir es so:
    FFMPEG_PATH = APP_DIR / "resources" / "ffmpeg.exe"
    
else:
    # FALL: Python Entwicklung
    APP_DIR = Path(__file__).resolve().parent
    IS_FROZEN = False
    OUTPUT_DIR = APP_DIR / "output"
    
    # Pfad im Entwicklungsmodus
    FFMPEG_PATH = APP_DIR / "resources" / "ffmpeg.exe"

# Ressourcen-Ordner
RESOURCES_DIR = APP_DIR / "resources"

# Sicherstellen, dass Output-Ordner existiert
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Pfad zur EPEX-Datei
EPEX_PRICE_FILE = RESOURCES_DIR / "Day_Ahead_Auktion_202401010000_202501010000_Viertelstunde.xlsx"

# Kompatibilitäts-Variablen
SCRIPT_DIR = APP_DIR
DATA_DIR = APP_DIR
SMARD_DIR = APP_DIR

# ============================================================================
# SZENARIEN & EINSTELLUNGEN
# ============================================================================

AVAILABLE_YEARS = [2024, 2037, 2045]

def generate_scenarios():
    """Generiert Szenario-Konfigurationen für alle Jahre."""
    scenarios = {}
    
    for year in AVAILABLE_YEARS:
        # DE Single
        scenarios[f'de_single_{year}'] = {
            'file_keyword': f'{year}_DE_SINGLE',
            'sheet': 'timeseries_insel',
            'zones': ['de'],
            'description': f'Deutschland {year} (eine Zone)',
            'year': year
        }
        
        # NS Coupled
        scenarios[f'ns_coupled_{year}'] = {
            'file_keyword': f'{year}_NS_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['north', 'south'],
            'description': f'Nord-Süd {year} (Gekoppelt)',
            'year': year
        }

        # NS Insel
        scenarios[f'ns_insel_{year}'] = {
            'file_keyword': f'{year}_NS_INSEL',
            'sheet': 'timeseries_insel',
            'zones': ['north', 'south'],
            'description': f'Nord-Süd {year} (Inselbetrieb)',
            'year': year
        }

        # Z4 Coupled
        scenarios[f'z4_coupled_{year}'] = {
            'file_keyword': f'{year}_Z4_COUPLED',
            'sheet': 'timeseries_coupled',
            'zones': ['Amprion', 'TenneT', '50Hertz', 'TransnetBW'],
            'description': f'4-Zonen {year} (Gekoppelt)',
            'year': year
        }

        # Z4 Insel
        scenarios[f'z4_insel_{year}'] = {
            'file_keyword': f'{year}_Z4_INSEL',
            'sheet': 'timeseries_insel',
            'zones': ['Amprion', 'TenneT', '50Hertz', 'TransnetBW'],
            'description': f'4-Zonen {year} (Inselbetrieb)',
            'year': year
        }

    # Spezial-Szenarien
    scenarios['ns_diff_2024'] = {
        'base': 'ns_insel_2024',
        'compare': 'ns_coupled_2024',
        'zones': ['north', 'south'],
        'description': 'Preisdifferenz Nord-Süd 2024',
        'year': 2024,
        'mode': 'diff'
    }

    scenarios['epex_comparison_2024'] = {
        'file_keyword': '2024_DE_SINGLE',
        'sheet': 'timeseries_insel',
        'zones': ['de'],
        'description': '📊 EPEX-Vergleich 2024',
        'year': 2024,
        'is_epex_comparison': True
    }
    
    return scenarios

SCENARIOS = generate_scenarios()

# Mapping Zonen zu Bundesländern
ZONE_BUNDESLAENDER = {
    '50Hertz': ['Brandenburg', 'Mecklenburg-Vorpommern', 'Sachsen', 'Sachsen-Anhalt', 'Thüringen', 'Berlin'],
    'TenneT': ['Schleswig-Holstein', 'Niedersachsen', 'Bremen', 'Hamburg', 'Bayern'],
    'Amprion': ['Nordrhein-Westfalen', 'Rheinland-Pfalz', 'Saarland', 'Hessen'],
    'TransnetBW': ['Baden-Württemberg'],
    'north': ['Schleswig-Holstein', 'Niedersachsen', 'Bremen', 'Hamburg', 'Mecklenburg-Vorpommern', 'Brandenburg', 'Berlin', 'Sachsen-Anhalt'],
    'south': ['Bayern', 'Baden-Württemberg', 'Hessen', 'Thüringen', 'Sachsen', 'Rheinland-Pfalz', 'Saarland', 'Nordrhein-Westfalen'],
    'de': ['alle']
}

# Visualisierungs-Einstellungen
PRICE_SCALE = {'vmin': 0, 'vmax': 500, 'cmap': 'YlOrRd'}
DIFF_SCALE = {'vmax': 50, 'cmap': 'RdYlGn_r'}
EPEX_COMPARISON_SCALE = {'vmax': 100, 'cmap': 'RdBu_r'}

VIS_SETTINGS = {
    'figsize': (14, 10),
    'dpi': 150,
    'background_color': '#1e1e1e',
    'map_background': '#2d2d2d',
    'border_color': '#ffffff',
    'text_color': '#ffffff',
    'accent_color': '#4a9eff',
}

VIDEO_SETTINGS = {'fps': 8, 'dpi': 150, 'bitrate': 5000}