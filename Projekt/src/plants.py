# plants.py
"""
Kraftwerksliste einlesen und Angebots-Stack (Merit Order) pro Zone bauen.

Fix (wichtig für NS):
- pd.read_excel(..., sheet_name=None) kann (je nach Pandas) ein dict von DataFrames liefern.
  Wir wollen aber EIN DataFrame -> wir nehmen dann das erste Sheet.

Wichtige Modellentscheidung:
- Anlagen ohne Grenzkosten (mc) werden NICHT eingesetzt.
  Sie werden nur als Check/Export ausgegeben.
"""

import numpy as np
import pandas as pd


def load_plants_excel(path, sheet_name=None) -> pd.DataFrame:
    """
    Lädt die Kraftwerksliste als DataFrame.

    Parameter:
    - path: Pfad zur Excel-Datei
    - sheet_name:
        - None      -> erstes Sheet (robust)
        - "Name"    -> bestimmtes Sheet
        - 0 / 1 ... -> Sheet-Index

    Warum robust?
    - In manchen Pandas-Versionen führt sheet_name=None dazu,
      dass ein dict mit allen Sheets zurückkommt.
      Das wollen wir NICHT. Wir nehmen dann das erste Sheet.
    """
    obj = pd.read_excel(path, sheet_name=sheet_name)

    # Falls ein dict zurückkommt (alle Sheets), nimm das erste DataFrame
    if isinstance(obj, dict):
        if len(obj) == 0:
            raise ValueError(f"Excel-Datei enthält keine Sheets: {path}")
        first_key = next(iter(obj.keys()))
        df = obj[first_key].copy()
    else:
        df = obj.copy()

    df.columns = [str(c).strip() for c in df.columns]
    return df


def _derive_cap_mw(df: pd.DataFrame, cap_mode: str) -> pd.Series:
    """
    Ermittelt cap_mw aus mehreren möglichen Kapazitätsspalten.
    """
    cap_cols = [
        "Mittlere verfügbare\nNetto-Nennleistung [MW]",
        "Netto-Nennleistung\n(elektrische Wirkleistung) [MW]",
        "Bruttoleistung [MW]",
    ]

    for c in cap_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].replace("-", np.nan), errors="coerce")

    # Helper: wenn eine Spalte fehlt, gib Series voller NaN zurück
    def col_or_nan(name):
        if name in df.columns:
            return df[name]
        return pd.Series(np.nan, index=df.index)

    if cap_mode == "priority":
        mean_av = col_or_nan(cap_cols[0]).where(col_or_nan(cap_cols[0]) > 0, np.nan)
        netto = col_or_nan(cap_cols[1]).where(col_or_nan(cap_cols[1]) > 0, np.nan)
        brutto = col_or_nan(cap_cols[2]).where(col_or_nan(cap_cols[2]) > 0, np.nan)
        return mean_av.combine_first(netto).combine_first(brutto)

    if cap_mode == "mean_available":
        return col_or_nan(cap_cols[0]).where(col_or_nan(cap_cols[0]) > 0, np.nan)

    if cap_mode == "netto":
        netto = col_or_nan(cap_cols[1]).where(col_or_nan(cap_cols[1]) > 0, np.nan)
        brutto = col_or_nan(cap_cols[2]).where(col_or_nan(cap_cols[2]) > 0, np.nan)
        return netto.combine_first(brutto)

    raise ValueError("cap_mode muss 'priority', 'mean_available' oder 'netto' sein.")


def build_plants_stack_for_zone(
    plants_raw: pd.DataFrame,
    zone_name: str,
    zone_col: str = "ÜNB",
    cap_mode: str = "priority",
    filter_active_only: bool = True,
) -> dict:
    """
    Baut Angebotsstack für zone_name.

    Wichtig:
    - Filtert nach plants_raw[zone_col] == zone_name (case-insensitive)
    - Berechnet cap_mw
    - Liest mc
    - Anlagen ohne mc werden NICHT genutzt, aber exportiert
    """

    if zone_col not in plants_raw.columns:
        raise KeyError(
            f"Zone-Spalte '{zone_col}' nicht in Kraftwerksliste vorhanden. "
            f"Verfügbare Spalten: {list(plants_raw.columns)}"
        )

    # Filter auf Zone
    mask = (
        plants_raw[zone_col]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(str(zone_name).casefold())
    )
    df = plants_raw.loc[mask].copy()

    # Statusfilter (heuristisch)
    if filter_active_only and "Status" in df.columns:
        status_tmp = df["Status"].astype(str).str.casefold()
        df = df[
            status_tmp.str.contains("betrieb", na=False)
            & ~status_tmp.str.contains("außer", na=False)
            & ~status_tmp.str.contains("ausser", na=False)
            & ~status_tmp.str.contains("still", na=False)
        ].copy()

    # cap_mw
    df["cap_mw"] = _derive_cap_mw(df, cap_mode=cap_mode)

    # mc
    mc_col = "Grenzkosten [EUR/MWHel]"
    if mc_col not in df.columns:
        raise KeyError(f"mc-Spalte '{mc_col}' nicht gefunden in Kraftwerksliste.")
    df["mc"] = pd.to_numeric(df[mc_col].replace("-", np.nan), errors="coerce")

    # Netzreserve erkennen
    status = df["Status"].astype(str).str.casefold() if "Status" in df.columns else pd.Series("", index=df.index)
    is_reserve = status.str.contains("netzreserve", na=False)

    # Merit-Order Flag (wenn vorhanden, sonst default True)
    if "Teil der Merit-Order?" in df.columns:
        is_mo = df["Teil der Merit-Order?"].astype(str).str.strip().str.casefold().eq("ja")
    else:
        is_mo = pd.Series(True, index=df.index)

    # Physikalische Kapazität (inkl. ohne mc)
    plants_with_cap = df.dropna(subset=["cap_mw"]).copy()
    plants_with_cap = plants_with_cap[plants_with_cap["cap_mw"] > 0].copy()
    stack_cap_physical = float(plants_with_cap["cap_mw"].sum())

    # Anlagen ohne mc (nicht genutzt)
    plants_no_mc = plants_with_cap[plants_with_cap["mc"].isna()].copy()
    missing_mc_cap = float(plants_no_mc["cap_mw"].sum())

    # Effektiv nutzbar: cap>0 UND mc vorhanden
    plants_cap = plants_with_cap.dropna(subset=["mc"]).copy()
    stack_cap_effective = float(plants_cap["cap_mw"].sum())

    # Stacks
    mo_stack = plants_cap[is_mo & ~is_reserve].copy()
    reserve_stack = plants_cap[is_reserve].copy()

    mo_stack["stack_class"] = "MERIT_ORDER"
    reserve_stack["stack_class"] = "NETZRESERVE"

    mo_stack = mo_stack.sort_values("mc").reset_index(drop=True)
    reserve_stack = reserve_stack.sort_values("mc").reset_index(drop=True)

    plants_stack = pd.concat([mo_stack, reserve_stack], ignore_index=True)
    plants_stack = plants_stack.sort_values("mc").reset_index(drop=True)
    plants_stack["cumcap_mw"] = plants_stack["cap_mw"].cumsum()

    cumcap_mo = mo_stack["cap_mw"].cumsum().to_numpy() if len(mo_stack) else np.array([])
    mc_mo = mo_stack["mc"].to_numpy() if len(mo_stack) else np.array([])

    max_mc_reserve = float(reserve_stack["mc"].max()) if len(reserve_stack) else np.nan
    max_mc_all = float(plants_stack["mc"].max()) if len(plants_stack) else np.nan

    return {
        "plants_with_cap": plants_with_cap,
        "plants_no_mc": plants_no_mc,
        "missing_mc_cap": missing_mc_cap,

        "plants_cap": plants_cap,
        "plants_stack": plants_stack,

        "stack_cap_physical": stack_cap_physical,
        "stack_cap_effective": stack_cap_effective,

        "mo_cap": float(mo_stack["cap_mw"].sum()),
        "res_cap": float(reserve_stack["cap_mw"].sum()),

        "cumcap_mo": cumcap_mo,
        "mc_mo": mc_mo,
        "max_mc_reserve": max_mc_reserve,
        "max_mc_all": max_mc_all,
    }


def guess_zone_column(df: pd.DataFrame):
    """
    Heuristik: finde eine Spalte, die wie eine Zonen-Spalte aussieht.
    (für NS-Kraftwerksliste)
    """
    candidates = [
        "ÜNB", "UENB", "Zone", "REGION", "Region", "Gebiet",
        "Marktgebiet", "Preiszone", "North/South", "Nord/Süd"
    ]
    for c in candidates:
        if c in df.columns:
            return c
    return df.columns[0]
