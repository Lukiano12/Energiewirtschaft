# config.py
"""
Zentrale Konfiguration für das ÜNB-/Zonenmodell.

Hier stellst du ein:
- Szenario (DE_SINGLE, Z4_INSEL, Z4_COUPLED, NS_INSEL, NS_COUPLED)
- Modelljahr (2024 / 2037 / 2045)
- Pfade zu Daten (SMARD, Last_errechnet, Kraftwerkslisten)
- NTC-Szenarien und Handelskosten
- EE-Ausbau-Faktoren (direkt hier eingeben!)
"""
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
# OLD: BASE_DIR = SRC_DIR.parent  <-- This pointed to 'src', causing 'src/data'
# NEW: Go up two levels from 'Alex' -> 'src' -> 'Projekt'
BASE_DIR = SRC_DIR.parent.parent

DATA_DIR   = BASE_DIR / "data"
SMARD_DIR  = DATA_DIR / "smard"
PLANTS_DIR = DATA_DIR / "plants"

# ---------------------------------------------------------------------------
# Kraftwerkslisten (immer im Unterordner data/plants)
# ---------------------------------------------------------------------------
PLANTS_XLSX_Z4 = PLANTS_DIR / "Kraftwerksliste_Regelzonen.xlsx"
PLANTS_SHEET_Z4 = "Kraftwerksliste_Miri"   # ggf. anpassen an deinen Tab-Namen

PLANTS_XLSX_NS = PLANTS_DIR / "Kraftwerksliste_Sued_Nord.xlsx"
PLANTS_SHEET_NS = "Kraftwerksliste_Sued_Nord"  # ggf. anpassen




# =============================================================================
# Szenario-Auswahl
# =============================================================================
# Mögliche Werte:
#   "DE_SINGLE"   -> Deutschland als eine Preiszone
#   "Z4_INSEL"    -> 4 ÜNB-Zonen, Insel (kein Handel)
#   "Z4_COUPLED"  -> 4 ÜNB-Zonen, mit Handel (Market Coupling)
#   "NS_INSEL"    -> Nord/Süd-Szenario, Insel
#   "NS_COUPLED"  -> Nord/Süd-Szenario, mit Handel
SCENARIO = "Z4_COUPLED"

# Modelljahr (steuert u.a. Lastprofile):
#   2024 -> SMARD-Last
#   2037 -> Lastprofile aus data/Last_errechnet/... (total_MW)
#   2045 -> Lastprofile aus data/Last_errechnet/... (total_MW)
MODEL_YEAR = 2037  # 2024, 2037 oder 2045

# Zeitauflösung im Modell: "15min" oder "h"
TIME_FREQ = "15min"

# Plots ein-/ausschalten
MAKE_PLOTS = False

# =============================================================================
# SMARD-Input für 4 ÜNB-Zonen (Basis 2024)
# =============================================================================
# Erwartet werden die originalen SMARD-Dateien im data/ Ordner.
# Passe die Dateinamen ggf. an deine echten an.

ZONES_4 = {
    "TransnetBW": {
        "load_xlsx": str(SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TransnetBW.xlsx"),
        "gen_xlsx":  str(SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_TransnetBW.xlsx"),
        "uenb": "TransnetBW",
    },
    "Amprion": {
        "load_xlsx": str(SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_Amprion.xlsx"),
        "gen_xlsx":  str(SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_Amprion.xlsx"),
        "uenb": "Amprion",
    },
    "TenneT": {
        "load_xlsx": str(SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TenneT.xlsx"),
        "gen_xlsx":  str(SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_TenneT.xlsx"),
        "uenb": "TenneT",
    },
    "50Hertz": {
        "load_xlsx": str(SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_50Hertz.xlsx"),
        "gen_xlsx":  str(SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_50Hertz.xlsx"),
        "uenb": "50Hertz",
    },
}


# =============================================================================
# Lastprofile (errechnet) – Gesamtlast total_MW je Jahr
# =============================================================================
# Diese Dateien wurden mit deinem generate_loadprofiles.py erstellt.
# Sie liegen in data/Last_errechnet/.

LAST_ERRECHNET_DIR = DATA_DIR / "Last_errechnet"

LASTPROFILE_FILES = {
    "DE":         str(LAST_ERRECHNET_DIR / "Szenario_Lastprofile_DE.xlsx"),
    "50Hertz":    str(LAST_ERRECHNET_DIR / "Szenario_Lastprofile_50Hertz.xlsx"),
    "TenneT":     str(LAST_ERRECHNET_DIR / "Szenario_Lastprofile_TenneT.xlsx"),
    "Amprion":    str(LAST_ERRECHNET_DIR / "Szenario_Lastprofile_Amprion.xlsx"),
    "TransnetBW": str(LAST_ERRECHNET_DIR / "Szenario_Lastprofile_TransnetBW.xlsx"),
}

# =============================================================================
# Erneuerbare (EE) aus SMARD: Mapping von SMARD-Spalten auf Modell-Tech-Namen
# =============================================================================
EE_NEEDLES = {
    "Biomasse":        "Biomasse",
    "Wasser":          "Wasserkraft",
    "Wind Offshore":   "Wind Offshore",
    "Wind Onshore":    "Wind Onshore",
    "PV":              "Photovoltaik",
    "Sonstige EE":     "Sonstige Erneuerbare",
}

# =============================================================================
# Kraftwerkslisten / Merit-Order (jahrabhängig)
# =============================================================================

# Gemeinsame Sheet-Namen
PLANTS_SHEET_Z4 = "Kraftwerksliste_Miri"
PLANTS_SHEET_NS = "Kraftwerksliste_Miri"

# 4-Zonen-Kraftwerkslisten je Jahr
PLANTS_XLSX_Z4_BY_YEAR = {
    2024: PLANTS_DIR / "Kraftwerksliste_Regelzonen.xlsx",
    2037: PLANTS_DIR / "Kraftwerksliste_2037.xlsx",
    2045: PLANTS_DIR / "Kraftwerksliste_2045.xlsx",
}
# Fallback, falls ein anderes Jahr gewählt wird
PLANTS_XLSX_Z4_DEFAULT = PLANTS_DIR / "Kraftwerksliste_Regelzonen.xlsx"

# Nord/Süd-Kraftwerkslisten je Jahr
PLANTS_XLSX_NS_BY_YEAR = {
    2024: PLANTS_DIR / "Kraftwerksliste_Sued_Nord.xlsx",
    2037: PLANTS_DIR / "Kraftwerksliste_NS_2037.xlsx",
    2045: PLANTS_DIR / "Kraftwerksliste_NS_2045.xlsx",
}
PLANTS_XLSX_NS_DEFAULT = PLANTS_DIR / "Kraftwerksliste_Sued_Nord.xlsx"

# In der NS-Liste steht die Zone in dieser Spalte
NS_PLANTS_ZONE_COL = "NS_Zone"

# Endgültige Auswahl der Kraftwerksliste je nach Modelljahr
PLANTS_XLSX_Z4 = PLANTS_XLSX_Z4_BY_YEAR.get(MODEL_YEAR, PLANTS_XLSX_Z4_DEFAULT)
PLANTS_XLSX_NS = PLANTS_XLSX_NS_BY_YEAR.get(MODEL_YEAR, PLANTS_XLSX_NS_DEFAULT)

# Kapazitätsmodus:
# - "priority": Mittlere verfügbare -> Netto -> Brutto
# - "mean_available": nur mittlere verfügbare Nettoleistung
# - "netto": Netto bevorzugt, sonst Brutto
CAP_MODE = "priority"

# Nur aktive Anlagen verwenden (Status-Feld in der Kraftwerksliste)
FILTER_ACTIVE_ONLY = False

# Wenn Merit-Order nicht reicht: Preis = max(mc) aus Netzreserve (falls vorhanden)
RESERVE_PRICE_MAX = True


# =============================================================================
# EE-Ausbau-Faktoren (manuell in config)
# =============================================================================
# Du kannst wählen:
#   EE_SCALING_MODE = "none"    -> keine Skallierung, EE bleibt wie 2024
#   EE_SCALING_MODE = "global"  -> pro Jahr ein Faktor-Set für ALLE Zonen gleich
#   EE_SCALING_MODE = "per_zone"-> pro Jahr und Zone eigene Faktoren
#
# Tech-Keys: "PV", "Wind Onshore", "Wind Offshore", "Biomasse", "Wasser", "Sonstige EE"

EE_SCALING_MODE = "global"  # "none" | "global" | "per_zone"

# Globale EE-Faktoren (für alle Zonen gleich)
# Beispielwerte (1.0 = kein Ausbau ggü. 2024):
EE_FACTORS_GLOBAL = {
    2037: {
        "PV":           3.46,
        "Wind Onshore": 2.49,
        "Wind Offshore":6.09,
        "Biomasse":     0.55,
        "Wasser":       1.0,
        "Sonstige EE":  1.11,
    },
    2045: {
        "PV":           4.01,
        "Wind Onshore": 2.52,
        "Wind Offshore":7.61,
        "Biomasse":     0.33,
        "Wasser":       1.0,
        "Sonstige EE":  1.11,
    },
}

# Zonen-spezifische EE-Faktoren (nur relevant, wenn EE_SCALING_MODE = "per_zone")
# Keys müssen zu den Modellzonen passen: "TransnetBW", "Amprion", "TenneT", "50Hertz",
# "DE", "NORD", "SUED" je nach SCENARIO.
EE_FACTORS_PER_ZONE = {
    2037: {
        # Beispiel:
        # "TransnetBW": {"PV": 1.2, "Wind Onshore": 1.1, ...},
        # "Amprion":    {"PV": 1.1, ...},
    },
    2045: {
        # Beispiel:
        # "TransnetBW": {"PV": 1.5, "Wind Onshore": 1.3, ...},
    },
}

# =============================================================================
# Preis-Reporting / Knappheit
# =============================================================================

SCARCITY_PRICING_IN_PRICE = False
# True  -> Unserved führt zu VOLL im Preis (Insel + Coupled)
# False -> Preis bleibt Merit-Order-artig; Unserved ist nur Mengen-KPI

PRICE_NAN_WHEN_NO_CONV = True
# True  -> Wenn keine konv. Erzeugung läuft (nur EE), Preis = NaN
# False -> Dann wird Preis auf 0 gesetzt

# Strafkosten (Value of Lost Load) für nicht bediente Last (Unserved)
VOLL = 10000.0  # €/MWh

# =============================================================================
# Handel / Netz (4 Zonen & NS)
# =============================================================================

# Baseline-NTC (MID) für 4-Zonen-Fall (MW)
NTC_BASE_MID = {
    ("50Hertz", "TenneT"): 2500.0,
    ("TenneT", "Amprion"): 3000.0,
    ("Amprion", "TransnetBW"): 2500.0,
    ("TenneT", "TransnetBW"): 2000.0,
}

# Szenario-Skalierung LOW / MID / HIGH
SCEN_SCALE = {"LOW": 0.5, "MID": 1.0, "HIGH": 1.5}
NTC_SCENARIO = "MID"
NTC_SCALE = SCEN_SCALE.get(NTC_SCENARIO, 1.0)

# Default-Handelskosten pro MWh und Kante (€/MWh)
DEFAULT_TRADE_COST = 5.0

# Optionale individuelle Handelskosten je Kante
EDGE_TRADE_COSTS = {
    # ("50Hertz", "TenneT"): 8.0,
    # ("TenneT", "Amprion"): 10.0,
    # ...
}

# Nord/Süd-NTC (MW) – für NS_COUPLED
NS_NTC_MW = 10000.0
NS_TRADE_COST = 0.0

# =============================================================================
# Nord/Süd-Aufteilung von TenneT: nach Technologie
# =============================================================================
# NS_SHARES definiert, wie die EE-Erzeugung von TenneT zwischen NORD und SUED
# aufgeteilt wird – und zwar je Technologie.
#
# Wichtig:
# - Schlüssel müssen zu deinen Tech-Namen in EE_NEEDLES passen (Spaltennamen von zone_vre_tech_4["TenneT"]).
# - Werte sind Tupel: (NORD-Anteil, SUED-Anteil).
# - Summe pro Tech sollte ~ 1.0 ergeben.
# - Wenn eine Tech hier NICHT steht, wird ns_load_share als Default benutzt.

NS_SHARES = {
    # Kein Offshore im Süden:
    "Wind Offshore": (1.0, 0.0),

    # Beispielannahmen, kannst du anpassen:
    "Wind Onshore":  (0.6, 0.4),
    "PV":            (0.5, 0.5),
    "Biomasse":      (0.5, 0.5),
    "Wasser":        (0.4, 0.6),
    "Sonstige EE":   (0.5, 0.5),
}

# Aufteilung der TenneT-Last (fallback, und für Techs ohne eigenen Eintrag):
# (NORD-Anteil, SUED-Anteil)
NS_LOAD_SHARE = (0.6, 0.4)

# =============================================================================
# Excel-Ausgabename
# =============================================================================

def out_xlsx_name() -> str:
    """
    Erzeugt einen sinnvollen Dateinamen für den Excel-Export,
    z.B. "UNB_Modelle_15min_2024_Z4_INSEL.xlsx".
    """
    base = "UNB_Modelle"
    return f"{base}_{TIME_FREQ}_{MODEL_YEAR}_{SCENARIO}.xlsx"


