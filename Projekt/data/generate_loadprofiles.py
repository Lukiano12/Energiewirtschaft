#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_loadprofiles.py

Erzeugt Viertelstunden-Lastprofile für 2024, 2037 und 2045
für:
- Deutschland gesamt (DE)
- 50Hertz, Amprion, TenneT, TransnetBW

Jeweils aufgeteilt in:
    * base_MW  (Haushalte, Industrie, sonstige Restlast)
    * wp_MW    (Wärmepumpen)
    * ev_MW    (Elektromobilität PKW + LKW)
    * dc_MW    (Rechenzentren, konstantes Profil)
    * total_MW (Summe)

Datenquellen (alle relativ zu diesem Skript):
- data/smard/*.xlsx         : SMARD Stromverbrauch Viertelstunde 2024
- data/Szenarien.xlsx       : NEP-/Szenariozahlen (Sheet "NEP-Zahlen"), Werte in TWh!
- data/Lastprofil Wärmepumpe_trend.xlsx
- data/Lastprofil_Elektromobilitaet_trend.xlsx

Methodik:
- 2024: base = SMARD_total - wp - ev - dc  (viertelstündlich)
- 2037/2045:
    * WP/EV/DC über normierte Profile + Szenario-Energie (TWh -> GWh) verteilt auf Zonen
    * Basislast: Form wie 2024, skaliert mit alpha pro Jahr/Zone, so dass Jahresenergie passt:
        alpha = (E_total - E_wp - E_ev - E_dc) / E_base_2024
        base_y(t) = alpha * base_2024(t)
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Basis-Pfade (alles relativ zu diesem Skript)
# ---------------------------------------------------------------------------

DELTA_H = 0.25  # 15 Minuten in Stunden

THIS_FILE = Path(__file__).resolve()  # .../data/generate_loadprofiles.py
DATA_DIR = THIS_FILE.parent           # .../data
SMARD_DIR = DATA_DIR / "smard"        # .../data/smard
OUTPUT_DIR = DATA_DIR / "Last_errechnet"  # .../data/Last_errechnet

# Eingabedateien (alle im selben Ordner wie das Skript)
SCENARIO_FILE = DATA_DIR / "Szenarien.xlsx"
WP_PROFILE_FILE = DATA_DIR / "Lastprofil Wärmepumpe_trend.xlsx"
EV_PROFILE_FILE = DATA_DIR / "Lastprofil_Elektromobilitaet_trend.xlsx"

# SMARD-Dateien je Zone (Dateinamen ggf. exakt anpassen!)
ZONE_FILES: dict[str, Path] = {
    "DE":         SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde (1).xlsx",
    "50Hertz":    SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_50Hertz.xlsx",
    "Amprion":    SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_Amprion.xlsx",
    "TenneT":     SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TenneT.xlsx",
    "TransnetBW": SMARD_DIR / "Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde_TransnetBW.xlsx",
}

TSO_ZONES = ["50Hertz", "Amprion", "TenneT", "TransnetBW"]

# ---------------------------------------------------------------------------
# Manuelle Verteilung der Szenario-Energien auf ÜNB-Zonen
# ---------------------------------------------------------------------------
# Leer lassen => Verteilung proportional zur 2024er Energie (aus SMARD)
#
# Beispiel für manuelle Verteilung:
# MANUAL_ZONE_SHARES = {
#     "50Hertz": 0.25,
#     "Amprion": 0.30,
#     "TenneT": 0.25,
#     "TransnetBW": 0.20,
# }
MANUAL_ZONE_SHARES: dict[str, float] = {}


# ---------------------------------------------------------------------------
# Helper-Funktionen
# ---------------------------------------------------------------------------

def assert_exists(p: Path) -> None:
    if not p.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {p}")


def read_smard_load_mw(path: Path) -> pd.Series:
    """
    Liest SMARD-Stromverbrauch (Viertelstunde) und gibt Last in MW zurück.

    Robust:
    - sucht zuerst die Zeile mit "Datum bis" und verwendet diese als Header
    - sucht die Zeitspalte mit "Datum bis"
    - sucht bevorzugt die Spalte mit "Pumpspeicher" (z.B. "Netzlast inkl. Pumpspeicher [MWh]")
      und sonst eine generische "Netzlast [MWh]"-Spalte
    - fasst doppelte Zeitstempel zusammen (Summe der Leistungen -> Energieerhaltung)
    """
    assert_exists(path)

    # 1) Erst ohne Header einlesen, um Header-Zeile zu finden
    df0 = pd.read_excel(path, header=None)

    # Header-Zeile suchen (irgendeine Zelle == "Datum bis")
    header_row_candidates = df0.index[(df0 == "Datum bis").any(axis=1)]
    if len(header_row_candidates) == 0:
        raise ValueError(f'Keine Zeile mit "Datum bis" in Datei {path} gefunden.')
    header_row = int(header_row_candidates[0])

    # 2) Datei mit dieser Zeile als Header einlesen
    df = pd.read_excel(path, header=header_row)

    # Spalte mit "Datum bis" finden
    col_to = None
    for c in df.columns:
        if isinstance(c, str) and "Datum bis" in c:
            col_to = c
            break
    if col_to is None:
        col_to = df.columns[1]

    # 3) Spalte mit Energie in MWh wählen
    #    a) Bevorzugt: irgendwas mit "Pumpspeicher"
    col_net = None
    for c in df.columns:
        if isinstance(c, str) and "pumpspeicher" in c.lower():
            col_net = c
            break

    #    b) Wenn nichts mit Pumpspeicher gefunden wurde:
    if col_net is None:
        for c in df.columns:
            if isinstance(c, str) and "netzlast" in c.lower() and "[mwh]" in c.lower():
                col_net = c
                break

    #    c) Falls immer noch nichts: Fallback dritte Spalte
    if col_net is None:
        col_net = df.columns[2]

    # 4) Zeitstempel und Energie einlesen
    ts = pd.to_datetime(df[col_to], dayfirst=True, errors="coerce")
    mwh = pd.to_numeric(df[col_net], errors="coerce")

    mask = ts.notna() & mwh.notna()
    ts = ts[mask]
    mwh = mwh[mask]

    # 5) MWh -> MW (E = P * 0.25 h => P = E / 0.25)
    mw = mwh / DELTA_H
    mw.index = ts

    # 6) Doppelte Zeitstempel zusammenfassen (Summe, nicht Mittelwert)
    mw = mw[~mw.index.isna()]
    if not mw.index.is_unique:
        mw = mw.groupby(level=0).sum()

    return mw.rename("load_MW")


def read_norm_profile_kw(path: Path) -> pd.Series:
    """
    Liest normiertes Profil (1.000.000 kWh = 1 GWh) aus Excel.
    Erwartet Spalten: 'Datum', 'Zeit', 'Lastprofil 1000000kWh'.
    Rückgabe: Serie in kW mit eindeutigem DatetimeIndex.
    """
    assert_exists(path)
    df = pd.read_excel(path)
    dt = pd.to_datetime(
        df["Datum"].astype(str) + " " + df["Zeit"].astype(str),
        format="%d.%m.%Y %H:%M:%S",
        dayfirst=True,
        errors="coerce",
    )
    prof_kw = pd.to_numeric(df["Lastprofil 1000000kWh"], errors="coerce")
    prof_kw.index = dt

    # Ungültige Datumswerte raus
    prof_kw = prof_kw[prof_kw.index.notna()]

    # Doppelte Zeitstempel aggregieren (Mittelwert)
    if not prof_kw.index.is_unique:
        prof_kw = prof_kw.groupby(level=0).mean()

    return prof_kw.rename(path.stem)


def build_dc_norm_profile_kw(index: pd.DatetimeIndex) -> pd.Series:
    """
    Konstantes Rechenzentrumsprofil, normiert auf 1.000.000 kWh pro Jahr (=1 GWh).
    """
    n = len(index)
    p_const_kw = 1_000_000.0 / (n * DELTA_H)
    return pd.Series(p_const_kw, index=index, name="DC_norm_1GWh_kW")


def energy_gwh_from_kw(series_kw: pd.Series) -> float:
    return float(series_kw.sum() * DELTA_H / 1e6)


def read_scenario_energies_gwh(path: Path) -> dict[int, dict[str, float]]:
    """
    Liest 'Szenarien.xlsx', Sheet 'NEP-Zahlen'.

    WICHTIG: Die Werte in der Datei werden hier als TWh interpretiert
    (z.B. 464,4 => 464,4 TWh) und intern in GWh umgerechnet (× 1000).

    Erwartet in Spalte 'Unnamed: 1' Zeilen mit Schlüsseln:
      - 'Netto Stromverbrauch [GWh]'
      - 'Elektromobilität'
      - 'Wärmepumpen'
      - 'Rechenzentren'
      - 'Restlast (Haushalte, Industrie,…)'

    und in Spalten:
      2024 -> 'Unnamed: 3'
      2037 -> 'Unnamed: 5'
      2045 -> 'Unnamed: 8'

    Rückgabe:
        energies[year] = {
            "total", "ev", "wp", "dc", "rest"
        }  (alles in GWh)
    """
    assert_exists(path)
    df = pd.read_excel(path, sheet_name="NEP-Zahlen")

    rows = {}
    for _, r in df.iterrows():
        key = str(r.get("Unnamed: 1"))
        if key != "nan":
            rows[key] = r

    years = {2024: "Unnamed: 3", 2037: "Unnamed: 5", 2045: "Unnamed: 8"}
    out: dict[int, dict[str, float]] = {}

    for y, col in years.items():
        # Werte als TWh lesen und in GWh umrechnen
        total_twh = float(rows["Netto Stromverbrauch [GWh]"][col])
        ev_twh    = float(rows["Elektromobilität"][col])
        wp_twh    = float(rows["Wärmepumpen"][col])
        dc_twh    = float(rows["Rechenzentren"][col])
        rest_twh  = float(rows["Restlast (Haushalte, Industrie,…)"][col])

        out[y] = {
            "total": total_twh * 1000.0,
            "ev":    ev_twh * 1000.0,
            "wp":    wp_twh * 1000.0,
            "dc":    dc_twh * 1000.0,
            "rest":  rest_twh * 1000.0,
        }

    return out


def compute_zone_shares(load_kw_by_zone: dict[str, pd.Series]) -> dict[str, float]:
    """
    Liefert Zonenanteile für die vier ÜNB-Zonen.

    - Wenn MANUAL_ZONE_SHARES gesetzt ist: diese werden geprüft und benutzt.
    - Sonst: Anteile proportional zur 2024er Energie aus SMARD.
    """
    if MANUAL_ZONE_SHARES:
        missing = [z for z in TSO_ZONES if z not in MANUAL_ZONE_SHARES]
        if missing:
            raise ValueError(f"MANUAL_ZONE_SHARES fehlt für Zonen: {missing}")
        s = sum(MANUAL_ZONE_SHARES.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"MANUAL_ZONE_SHARES sum={s:.6f} (muss 1.0 sein)")
        print("\nZonenverteilung: MANUELL")
        for z in TSO_ZONES:
            print(f"  {z}: {MANUAL_ZONE_SHARES[z]:.4f}")
        return dict(MANUAL_ZONE_SHARES)

    # proportional nach Energie 2024
    energies = {z: energy_gwh_from_kw(load_kw_by_zone[z]) for z in TSO_ZONES}
    total = sum(energies.values())
    shares = {z: energies[z] / total for z in TSO_ZONES}
    print("\nZonenverteilung: PROPORTIONAL nach 2024er Energie")
    for z in TSO_ZONES:
        print(f"  {z}: {shares[z]:.4f}")
    return shares


# ---------------------------------------------------------------------------
# Hauptpipeline
# ---------------------------------------------------------------------------

def main():
    # Output-Ordner anlegen
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Pfade checken
    for z, p in ZONE_FILES.items():
        assert_exists(p)
    assert_exists(SCENARIO_FILE)
    assert_exists(WP_PROFILE_FILE)
    assert_exists(EV_PROFILE_FILE)

    print("=== Pfad-Check OK ===")
    print("DATA_DIR   :", DATA_DIR)
    print("SMARD_DIR  :", SMARD_DIR)
    print("OUTPUT_DIR :", OUTPUT_DIR)
    print("=====================\n")

    # 1) SMARD-Lasten laden (MW -> kW)
    load_kw_by_zone: dict[str, pd.Series] = {}
    for zone, path in ZONE_FILES.items():
        s_mw = read_smard_load_mw(path)
        load_kw_by_zone[zone] = s_mw * 1000.0
        print(f"[{zone}] SMARD-Last: {len(s_mw)} Schritte ({s_mw.index[0]} .. {s_mw.index[-1]})")

    # gemeinsamen Zeitindex (DE) verwenden
    idx = load_kw_by_zone["DE"].index
    for z in list(load_kw_by_zone.keys()):
        load_kw_by_zone[z] = load_kw_by_zone[z].reindex(idx)

    # 2) Normprofile laden (WP & EV) + konstantes DC-Profil
    wp_norm_kw = read_norm_profile_kw(WP_PROFILE_FILE).reindex(idx)
    ev_norm_kw = read_norm_profile_kw(EV_PROFILE_FILE).reindex(idx)
    dc_norm_kw = build_dc_norm_profile_kw(idx)

    # 3) Szenario-Energien national (jetzt in GWh)
    energies_nat = read_scenario_energies_gwh(SCENARIO_FILE)
    print("\nSzenario-Energien national [TWh]:")
    for y in [2024, 2037, 2045]:
        e = energies_nat[y]
        print(
            f"  {y}: total={e['total']/1000:.1f}, rest={e['rest']/1000:.1f}, "
            f"wp={e['wp']/1000:.1f}, ev={e['ev']/1000:.1f}, dc={e['dc']/1000:.1f}"
        )

    # 4) Zonenanteile bestimmen
    zone_shares = compute_zone_shares(load_kw_by_zone)

    # 5) 2024: Basislast je Zone berechnen
    base_2024_kw: dict[str, pd.Series] = {}
    base_2024_energy_gwh: dict[str, float] = {}

    print("\n--- 2024 Basislast-Berechnung ---")
    for zone in ZONE_FILES.keys():
        share = 1.0 if zone == "DE" else zone_shares[zone]
        load_2024_kw = load_kw_by_zone[zone]

        E_wp = energies_nat[2024]["wp"] * share
        E_ev = energies_nat[2024]["ev"] * share
        E_dc = energies_nat[2024]["dc"] * share

        wp_2024 = wp_norm_kw * E_wp
        ev_2024 = ev_norm_kw * E_ev
        dc_2024 = dc_norm_kw * E_dc

        base = (load_2024_kw - wp_2024 - ev_2024 - dc_2024).clip(lower=0.0)

        # Rekonstruktionscheck für 2024
        recon = base + wp_2024 + ev_2024 + dc_2024
        err = (recon - load_2024_kw).abs()
        print(
            f"[{zone}] 2024 Rekonstruktion: "
            f"mean error = {err.mean()/1000:.6f} MW, "
            f"max error = {err.max()/1000:.6f} MW"
        )

        base_2024_kw[zone] = base
        base_2024_energy_gwh[zone] = energy_gwh_from_kw(base)
        print(f"[{zone}] Base 2024 Energie: {base_2024_energy_gwh[zone]:.3f} GWh")

       # 6) Szenarien 2024/2037/2045 je Zone erzeugen und speichern
    print("\n--- Szenario-Profile erzeugen ---")

    # Dictionaries für Energiebilanz (in GWh)
    energy_target: dict[tuple[str, int], dict[str, float]] = {}
    energy_calc: dict[tuple[str, int], dict[str, float]] = {}

    for zone in ZONE_FILES.keys():
        share = 1.0 if zone == "DE" else zone_shares[zone]
        frames: dict[int, pd.DataFrame] = {}

        for year in [2024, 2037, 2045]:
            E_nat = energies_nat[year]
            E_total = E_nat["total"] * share
            E_wp = E_nat["wp"] * share
            E_ev = E_nat["ev"] * share
            E_dc = E_nat["dc"] * share

            # Ziel-Basisenergie für dieses Jahr (GWh)
            E_base_y = E_total - (E_wp + E_ev + E_dc)

            # Komponenten-Leistungen (kW)
            wp_y = wp_norm_kw * E_wp
            ev_y = ev_norm_kw * E_ev
            dc_y = dc_norm_kw * E_dc

            if year == 2024:
                base_y = base_2024_kw[zone]
            else:
                E_base_2024 = base_2024_energy_gwh[zone]
                if E_base_2024 <= 0:
                    alpha = 0.0
                else:
                    alpha = E_base_y / E_base_2024
                base_y = base_2024_kw[zone] * alpha

            total_y = base_y + wp_y + ev_y + dc_y

            # Energiesummen aus den Profilen (GWh)
            E_base_calc = energy_gwh_from_kw(base_y)
            E_wp_calc = energy_gwh_from_kw(wp_y)
            E_ev_calc = energy_gwh_from_kw(ev_y)
            E_dc_calc = energy_gwh_from_kw(dc_y)
            E_total_calc = energy_gwh_from_kw(total_y)

            key = (zone, year)

            energy_target[key] = {
                "base": E_base_y,
                "wp": E_wp,
                "ev": E_ev,
                "dc": E_dc,
                "total": E_total,
            }

            energy_calc[key] = {
                "base": E_base_calc,
                "wp": E_wp_calc,
                "ev": E_ev_calc,
                "dc": E_dc_calc,
                "total": E_total_calc,
            }

            # DataFrame in MW für die Excel-Ausgabe
            df = pd.DataFrame(
                {
                    "base_MW":   base_y / 1000.0,
                    "wp_MW":     wp_y / 1000.0,
                    "ev_MW":     ev_y / 1000.0,
                    "dc_MW":     dc_y / 1000.0,
                    "total_MW":  total_y / 1000.0,
                },
                index=idx,
            )
            frames[year] = df

        out_path = OUTPUT_DIR / f"Szenario_Lastprofile_{zone}.xlsx"
        # openpyxl als Engine benutzen (ist schon installiert)
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            for year in [2024, 2037, 2045]:
                frames[year].to_excel(writer, sheet_name=str(year))

        print(f"[{zone}] geschrieben: {out_path}")

    # 7) Energiebilanz-Prüfung
    print("\n--- Energiebilanz-Check (Total je Zone/Jahr) ---")
    TOL = 2.0  # Toleranz in Prozent, ab der eine Warnung ausgegeben wird

    for zone in ZONE_FILES.keys():
        for year in [2024, 2037, 2045]:
            key = (zone, year)
            tgt = energy_target[key]["total"]
            calc = energy_calc[key]["total"]

            if tgt != 0:
                rel = 100.0 * (calc - tgt) / tgt
            else:
                rel = float("nan")

            status = "OK"
            if abs(rel) > TOL:
                status = "WARNUNG"

            print(
                f"[{zone} {year}] total: "
                f"berechnet = {calc/1000:.2f} TWh, "
                f"soll = {tgt/1000:.2f} TWh, "
                f"Abw = {rel:+.2f} %  {status}"
            )

    print("\nFertig.")



if __name__ == "__main__":
    main()
