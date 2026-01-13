# kpi.py
"""
KPI-Berechnungen für Insel und Coupled.
"""

import numpy as np
import pandas as pd


def kpi_island(zone_results, zone_plants):
    """
    KPIs pro Zone aus dem Inselmodell.
    Achtung: Preis kann NaN sein -> wird bei mean/p95 ignoriert.
    """
    rows = []

    for z, ts in zone_results.items():
        dt_hours = (ts.index[1] - ts.index[0]).total_seconds() / 3600.0

        load_mwh = float(ts["load_mwh"].sum())
        ee_mwh = float(ts["vre_mwh"].sum())
        curtail_mwh = float(ts["abregel_mwh"].sum())
        unserved_mwh = float(ts["unserved_mwh"].sum())
        conv_need_mwh = float(ts["konv_mwh"].sum())

        p = ts["price_eur_mwh"].to_numpy()
        p = p[~np.isnan(p)]

        rows.append({
            "zone": z,
            "cap_effective_mw": float(zone_plants[z]["stack_cap_effective"]),
            "cap_physical_mw": float(zone_plants[z]["stack_cap_physical"]),
            "cap_missing_mc_mw": float(zone_plants[z]["missing_mc_cap"]),
            "load_mwh": load_mwh,
            "ee_mwh": ee_mwh,
            "curtail_mwh": curtail_mwh,
            "curtail_share_of_ee": (curtail_mwh / ee_mwh) if ee_mwh > 0 else 0.0,
            "conv_need_mwh": conv_need_mwh,
            "unserved_mwh": unserved_mwh,
            "unserved_share_of_load": (unserved_mwh / load_mwh) if load_mwh > 0 else np.nan,
            "price_mean": float(np.mean(p)) if len(p) else np.nan,
            "price_p95": float(np.quantile(p, 0.95)) if len(p) else np.nan,
        })

    return pd.DataFrame(rows).sort_values("zone").reset_index(drop=True)


def kpi_coupled(coupled, zones, dt_hours):
    """
    KPIs pro Zone aus dem Coupled-Ergebnis.
    """
    rows = []

    for z in zones:
        curtail_mwh = float((coupled[f"{z}_curtail_mw"] * dt_hours).sum())
        unserved_mwh = float((coupled[f"{z}_unserved_mw"] * dt_hours).sum())
        imp_mwh = float((coupled[f"{z}_import_mw"] * dt_hours).sum())
        exp_mwh = float((coupled[f"{z}_export_mw"] * dt_hours).sum())

        p = coupled[f"{z}_price_eur_mwh"].to_numpy()
        p = p[~np.isnan(p)]

        rows.append({
            "zone": z,
            "curtail_mwh": curtail_mwh,
            "unserved_mwh": unserved_mwh,
            "import_mwh": imp_mwh,
            "export_mwh": exp_mwh,
            "net_import_mwh": imp_mwh - exp_mwh,
            "price_mean": float(np.mean(p)) if len(p) else np.nan,
            "price_p95": float(np.quantile(p, 0.95)) if len(p) else np.nan,
        })

    return pd.DataFrame(rows).sort_values("zone").reset_index(drop=True)
