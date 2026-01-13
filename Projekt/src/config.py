# config.py
"""
Zentrale Konfiguration (alles, was man typischerweise ändert).
Hier stellst du Szenario, Pfade, NTCs, Preis-Schalter etc. ein.
"""

from pathlib import Path

# =============================================================================
# 0) Projektpfade
# =============================================================================
# Wir bauen Pfade relativ zum Projekt-Root:
# .../UENB_MeritOrder_Project/src/config.py  -> Root ist ein Ordner höher als src/
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
SMARD_DIR = DATA_DIR / "smard"
PLANTS_DIR = DATA_DIR / "plants"

OUT_DIR = PROJECT_ROOT / "output" / "excel"
OUT_DIR.mkdir(parents=True, exist_ok=True)  # Output-Ordner sicher erstellen

# =============================================================================
# Plot-Einstellungen
# =============================================================================
MAKE_PLOTS = True  # True = Plots anzeigen, False = ohne Plots laufen lassen

FIG_DIR = PROJECT_ROOT / "output" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)  # falls du später speichern willst

# =============================================================================
# 1) Szenario-Auswahl
# =============================================================================
# Erlaubte Szenarien:
# - "DE_SINGLE"   : Deutschland als eine Zone (kein Handel)
# - "Z4_INSEL"    : 4 ÜNB-Zonen ohne Handel
# - "Z4_COUPLED"  : 4 ÜNB-Zonen mit Handel (LP)
# - "NS_INSEL"    : Nord/Süd ohne Handel (Amprion+TransnetBW Süd; 50Hertz Nord; TenneT split)
# - "NS_COUPLED"  : Nord/Süd mit Handel (LP)
SCENARIO = "Z4_INSEL"

# Zeitauflösung: "15min" oder "h"
TIME_FREQ = "15min"


# =============================================================================
# 2) SMARD Input-Dateien (4 ÜNB)
# =============================================================================
# Diese Dateien müssen in data/smard liegen.
ZONES_4 = {
    "TransnetBW": {
        "load_xlsx": SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TransnetBW.xlsx",
        "gen_xlsx":  SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_TransnetBW.xlsx",
        "uenb": "TransnetBW",
    },
    "Amprion": {
        "load_xlsx": SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_Amprion.xlsx",
        "gen_xlsx":  SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_Amprion.xlsx",
        "uenb": "Amprion",
    },
    "TenneT": {
        "load_xlsx": SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TenneT.xlsx",
        "gen_xlsx":  SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_TenneT.xlsx",
        "uenb": "TenneT",
    },
    "50Hertz": {
        "load_xlsx": SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_50Hertz.xlsx",
        "gen_xlsx":  SMARD_DIR / "Realisierte_Erzeugung_202401010000_202501010000_Viertelstunde_50Hertz.xlsx",
        "uenb": "50Hertz",
    },
}


# =============================================================================
# 3) EE-Technologien aus SMARD (werden als EE gezählt)
# =============================================================================
# Links: interne Tech-Namen (wie sie in vre_by_tech Spalten heißen)
# Rechts: Suchstring, der im SMARD-Spaltennamen vorkommen muss
EE_NEEDLES = {
    "Biomasse":        "Biomasse",
    "Wasser":          "Wasserkraft",
    "Wind Offshore":   "Wind Offshore",
    "Wind Onshore":    "Wind Onshore",
    "PV":              "Photovoltaik",
    "Sonstige EE":     "Sonstige Erneuerbare",
}


# =============================================================================
# 4) Kraftwerkslisten (Pfad + Sheet)
# =============================================================================
# Für 4-Zonen Szenarien:
PLANTS_XLSX_Z4 = PLANTS_DIR / "Kraftwerksliste_Regelzonen.xlsx"
PLANTS_SHEET_Z4 = "Kraftwerksliste_Miri"  # anpassen, falls anders

# Für Nord/Süd Szenarien:
PLANTS_XLSX_NS = PLANTS_DIR / "Kraftwerksliste_Sued_Nord.xlsx"
PLANTS_SHEET_NS = None  # None = erstes Sheet automatisch; sonst Namen eintragen

# Wie heißt die Spalte, die die Zone/Region enthält?
# - Wenn die NS-Liste bereits "NORD"/"SUED" enthält: z.B. "Zone" oder "ÜNB"
# - Wenn nicht sicher: wir suchen im Code heuristisch.
NS_PLANTS_ZONE_COL = None  # None = automatisch suchen (ÜNB/Zone/Region/...)


# =============================================================================
# 5) Kraftwerks-Stack Einstellungen
# =============================================================================
# CAP_MODE:
# - "priority": mean_available -> netto -> brutto
# - "mean_available"
# - "netto"
CAP_MODE = "priority"

# Heuristischer Statusfilter (versucht aktive Anlagen zu behalten)
FILTER_ACTIVE_ONLY = False

# Inselpreis-Fallback: wenn MO nicht reicht -> Reserve max mc (falls vorhanden)
RESERVE_PRICE_MAX = True


# =============================================================================
# 6) Preis-Schalter
# =============================================================================
SCARCITY_PRICING_IN_PRICE = False
# True  -> bei Unserved Preis ~VOLL sichtbar
# False -> Preis bleibt MO-like, Unserved nur Mengen-KPI

PRICE_NAN_WHEN_NO_CONV = True
# True  -> wenn kein konv. Bedarf/keine konv. Erzeugung -> Preis=NaN
# False -> sonst 0 (kann Mittelwerte drücken)

# Value of Lost Load
VOLL = 10000.0


# =============================================================================
# 7) Handel / NTC (4-Zonen)
# =============================================================================
NTC_SCENARIO = "MID"  # "LOW" | "MID" | "HIGH"
SCEN_SCALE = {"LOW": 0.5, "MID": 1.0, "HIGH": 1.5}
NTC_SCALE = SCEN_SCALE.get(NTC_SCENARIO, 1.0)

# Adjacency-only Topologie
NTC_BASE_MID = {
    ("50Hertz", "TenneT"): 2500.0,
    ("TenneT", "Amprion"): 3000.0,
    ("Amprion", "TransnetBW"): 2500.0,
    ("TenneT", "TransnetBW"): 2000.0,
}

DEFAULT_TRADE_COST = 5.0
EDGE_TRADE_COSTS = {}  # optional: {("A","B"): cost}


# =============================================================================
# 8) Nord/Süd-Shares (TenneT-Split gemäß Screenshot)
# =============================================================================
# (Nord-Anteil, Süd-Anteil) pro Technologie
NS_SHARES = {
    "Wind Onshore": (0.926, 0.074),
    "Wind Offshore": (1.0, 0.0),
    "PV": (0.36, 0.64),
    "Biomasse": (0.365, 0.635),
    "Wasser": (0.085, 0.915),
    "Sonstige EE": (0.66, 0.34),
}

# Netzlast-Split für TenneT (und fallback)
NS_LOAD_SHARE = (0.565, 0.435)  # (Nord, Süd)

# NTC für Nord<->Süd Szenario (Beispielwert; anpassen)
NS_NTC_MW = 8000.0
NS_TRADE_COST = 5.0


# =============================================================================
# 9) Output-Dateiname
# =============================================================================
def out_xlsx_name() -> str:
    return str(OUT_DIR / f"UENB_Model_{TIME_FREQ}_{SCENARIO}.xlsx")
