# io_smard.py
"""
Alles rund um SMARD-Excel einlesen und Zeitreihen pro Zone bauen.
"""

import numpy as np
import pandas as pd


def read_smard_excel(path, sheet=0) -> pd.DataFrame:
    """
    SMARD-Exports haben oft mehrere Kopfzeilen.
    Wir suchen die Zeile, in der "Datum von" vorkommt und nutzen sie als Header.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header_row = None

    for i in range(len(raw)):
        if raw.iloc[i].astype(str).str.contains("Datum von", case=False, na=False).any():
            header_row = i
            break

    if header_row is None:
        raise ValueError(f"Headerzeile mit 'Datum von' nicht gefunden in {path}")

    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def to_num(s: pd.Series) -> pd.Series:
    """
    Konvertiert SMARD-Strings nach float.
    '-' wird als fehlend interpretiert -> 0.0
    """
    return pd.to_numeric(s.replace("-", np.nan), errors="coerce").fillna(0.0)


def find_col_contains_optional(df: pd.DataFrame, needle: str):
    """
    Sucht die erste Spalte, deren Name 'needle' enthält (case-insensitive).
    Gibt None zurück, wenn nicht gefunden.
    """
    n = needle.casefold()
    for c in df.columns:
        if n in str(c).casefold():
            return c
    return None


def find_col_contains_required(df: pd.DataFrame, needle: str) -> str:
    """
    Wie optional, aber wirft Fehler wenn nicht gefunden.
    """
    c = find_col_contains_optional(df, needle)
    if c is None:
        raise KeyError(f"Keine Spalte gefunden, die '{needle}' enthält.")
    return c


def build_zone_timeseries(load_xlsx, gen_xlsx, time_freq: str, ee_needles: dict):
    """
    Baut Zeitreihen pro Zone (MW + abgeleitete MWh).

    Output:
    - ts: DataFrame mit load_mw, vre_mw, residual_raw_mw, abregelung_mw, konv_bedarf_mw + MWh-Spalten
    - vre_by_tech: DataFrame mit EE-Leistung pro Technologie (MW)
    - meta: dict mit Debug-Infos (dt_hours, fehlende Techs, ...)
    """
    load_df = read_smard_excel(load_xlsx)
    gen_df = read_smard_excel(gen_xlsx)

    # Erwarteter Viertelstundenindex für 2024 (Berlin TZ)
    idx_15 = pd.date_range(
        "2024-01-01 00:00", "2025-01-01 00:00",
        freq="15min", tz="Europe/Berlin", inclusive="left"
    )

    load_df = load_df.reset_index(drop=True)
    gen_df = gen_df.reset_index(drop=True)

    # Wichtiger Safety Check: SMARD-Dateien müssen exakt 2024 in 15min enthalten
    assert len(idx_15) == len(load_df) == len(gen_df), f"Längen passen nicht: {load_xlsx} / {gen_xlsx}"

    load_df.index = idx_15
    gen_df.index = idx_15

    # Lastspalte robust finden
    load_col = find_col_contains_optional(load_df, "Netzlast inkl. Pumpspeicher")
    if load_col is None:
        load_col = find_col_contains_required(load_df, "Netzlast")

    # SMARD: MWh pro 15min -> MW = *4
    load_mw_15 = to_num(load_df[load_col]) * 4.0

    # EE-Spalten suchen
    ee_cols = {}
    missing = []
    for tech, needle in ee_needles.items():
        c = find_col_contains_optional(gen_df, needle)
        if c is None:
            missing.append(tech)
        else:
            ee_cols[tech] = c

    # EE nach Tech
    vre_by_tech_mw_15 = pd.DataFrame(index=idx_15)
    for tech in ee_needles.keys():
        if tech in ee_cols:
            vre_by_tech_mw_15[tech] = to_num(gen_df[ee_cols[tech]]) * 4.0
        else:
            vre_by_tech_mw_15[tech] = 0.0

    # EE-Summe
    vre_mw_15 = vre_by_tech_mw_15.sum(axis=1)

    # Grund-TS
    ts_15 = pd.DataFrame({"load_mw": load_mw_15, "vre_mw": vre_mw_15}, index=idx_15)

    # Resample auf gewünschte Auflösung
    ts = ts_15.resample(time_freq).mean()
    vre_by_tech = vre_by_tech_mw_15.resample(time_freq).mean()

    # Abgeleitete Größen
    ts["residual_raw_mw"] = ts["load_mw"] - ts["vre_mw"]
    ts["abregelung_mw"] = (-ts["residual_raw_mw"]).clip(lower=0.0)   # max(EE-Last, 0)
    ts["konv_bedarf_mw"] = (ts["residual_raw_mw"]).clip(lower=0.0)    # max(Last-EE, 0)

    # Schrittweite in Stunden (für MWh)
    dt_hours = (ts.index[1] - ts.index[0]).total_seconds() / 3600.0

    # Energie-Spalten
    ts["load_mwh"] = ts["load_mw"] * dt_hours
    ts["vre_mwh"] = ts["vre_mw"] * dt_hours
    ts["konv_mwh"] = ts["konv_bedarf_mw"] * dt_hours
    ts["abregel_mwh"] = ts["abregelung_mw"] * dt_hours

    meta = {
        "load_col": load_col,
        "missing_ee": missing,
        "dt_hours": dt_hours,
        "tech_max_mw": vre_by_tech.max().to_dict(),
        "tech_mean_mw": vre_by_tech.mean().to_dict(),
        "all_gen_cols": list(gen_df.columns),
    }
    return ts, vre_by_tech, meta
