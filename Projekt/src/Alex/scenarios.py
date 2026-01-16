# scenarios.py
"""
Szenario-Logik:
- baut aus den 4 ÜNB-Zeitreihen (zone_results_4, zone_vre_tech_4)
  je nach Szenario:
  - 4Z unverändert
  - DE Single (Aggregation)
  - Nord/Süd (Aggregation + TenneT Split)
- baut NTC-Kanten je nach Szenario
"""

import numpy as np
import pandas as pd


def build_ntc_edges_4zone(ntc_base_mid, ntc_scale, default_cost, edge_costs):
    """
    Aus einer ungerichteten Basis (A,B) bauen wir gerichtete Kanten:
      (A->B) und (B->A)
    """
    edges = []
    for (a, b), base in ntc_base_mid.items():
        ntc = float(base) * float(ntc_scale)
        if ntc <= 0:
            continue
        tc = float(edge_costs.get((a, b), default_cost))
        edges.append((a, b, ntc, tc))
        edges.append((b, a, ntc, tc))
    return edges


def build_ntc_edges_ns(ns_ntc_mw, ns_trade_cost):
    """
    Nord/Süd: nur eine Verbindung in beide Richtungen.
    """
    return [
        ("NORD", "SUED", float(ns_ntc_mw), float(ns_trade_cost)),
        ("SUED", "NORD", float(ns_ntc_mw), float(ns_trade_cost)),
    ]


def build_de_single_from_4zones(zone_results_4, zone_vre_tech_4):
    """
    Aggregiert 4 ÜNB-Zeitreihen zu einer Deutschland-Zeitreihe.
    """
    idx = next(iter(zone_results_4.values())).index

    load = sum(zone_results_4[z]["load_mw"] for z in zone_results_4.keys())
    ee_by_tech = sum(zone_vre_tech_4[z] for z in zone_vre_tech_4.keys())
    vre = ee_by_tech.sum(axis=1)

    ts = pd.DataFrame({"load_mw": load, "vre_mw": vre}, index=idx)
    ts["residual_raw_mw"] = ts["load_mw"] - ts["vre_mw"]
    ts["abregelung_mw"] = (-ts["residual_raw_mw"]).clip(lower=0.0)
    ts["konv_bedarf_mw"] = (ts["residual_raw_mw"]).clip(lower=0.0)

    dt_hours = (ts.index[1] - ts.index[0]).total_seconds() / 3600.0
    ts["load_mwh"] = ts["load_mw"] * dt_hours
    ts["vre_mwh"] = ts["vre_mw"] * dt_hours
    ts["konv_mwh"] = ts["konv_bedarf_mw"] * dt_hours
    ts["abregel_mwh"] = ts["abregelung_mw"] * dt_hours

    return {"DE": ts}, {"DE": ee_by_tech}, dt_hours


def build_ns_from_4zones(zone_results_4, zone_vre_tech_4, ns_shares, ns_load_share):
    """
    Nord/Süd-Szenario:
    - Amprion + TransnetBW komplett SÜD
    - 50Hertz komplett NORD
    - TenneT wird nach Shares aufgeteilt (pro Tech und Load)
    """
    idx = zone_results_4["50Hertz"].index
    n_load, s_load = ns_load_share

    # --- Load split (TenneT anteilig) ---
    load_n = zone_results_4["50Hertz"]["load_mw"] + n_load * zone_results_4["TenneT"]["load_mw"]
    load_s = zone_results_4["Amprion"]["load_mw"] + zone_results_4["TransnetBW"]["load_mw"] + s_load * zone_results_4["TenneT"]["load_mw"]

    # --- EE split by tech (TenneT anteilig nach Tech-Shares) ---
    ee_n = pd.DataFrame(index=idx)
    ee_s = pd.DataFrame(index=idx)

    ten_cols = list(zone_vre_tech_4["TenneT"].columns)
    for tech in ten_cols:
        # Wenn tech nicht im ns_shares: fallback = load share
        n_share, s_share = ns_shares.get(tech, ns_load_share)

        ee_n[tech] = zone_vre_tech_4["50Hertz"].get(tech, 0.0) + n_share * zone_vre_tech_4["TenneT"][tech]
        ee_s[tech] = (
            zone_vre_tech_4["Amprion"].get(tech, 0.0)
            + zone_vre_tech_4["TransnetBW"].get(tech, 0.0)
            + s_share * zone_vre_tech_4["TenneT"][tech]
        )

    vre_n = ee_n.sum(axis=1)
    vre_s = ee_s.sum(axis=1)

    def make_ts(load_mw, vre_mw):
        ts = pd.DataFrame({"load_mw": load_mw, "vre_mw": vre_mw}, index=idx)
        ts["residual_raw_mw"] = ts["load_mw"] - ts["vre_mw"]
        ts["abregelung_mw"] = (-ts["residual_raw_mw"]).clip(lower=0.0)
        ts["konv_bedarf_mw"] = (ts["residual_raw_mw"]).clip(lower=0.0)

        dt_hours = (ts.index[1] - ts.index[0]).total_seconds() / 3600.0
        ts["load_mwh"] = ts["load_mw"] * dt_hours
        ts["vre_mwh"] = ts["vre_mw"] * dt_hours
        ts["konv_mwh"] = ts["konv_bedarf_mw"] * dt_hours
        ts["abregel_mwh"] = ts["abregelung_mw"] * dt_hours
        return ts, dt_hours

    ts_n, dt_hours = make_ts(load_n, vre_n)
    ts_s, _ = make_ts(load_s, vre_s)

    return {"NORD": ts_n, "SUED": ts_s}, {"NORD": ee_n, "SUED": ee_s}, dt_hours
