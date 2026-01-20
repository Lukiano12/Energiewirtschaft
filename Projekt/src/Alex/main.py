# main.py
"""
Strompreiszonen-Modell – Hauptprogramm

Unterstützte Szenarien (config.SCENARIO):
- "DE_SINGLE"   : Deutschland als eine Zone (Aggregation der 4 ÜNB)
- "Z4_INSEL"    : 4 ÜNB-Zonen, Inselbetrieb (kein Handel)
- "Z4_COUPLED"  : 4 ÜNB-Zonen, Market Coupling (LP) mit NTC
- "NS_INSEL"    : Nord/Süd, Inselbetrieb (Last+EE aus 4Z abgeleitet)
- "NS_COUPLED"  : Nord/Süd, Market Coupling (LP) mit NTC

Jahre (config.MODEL_YEAR):
- 2024 : SMARD Last + EE
- 2037/2045 : Lastprofile aus data/Last_errechnet, EE-Shape aus 2024 skaliert (EE_FACTORS_*)

WICHTIG für NS-Aufteilung "nach Technologie":
- config.NS_LOAD_SHARE muss Tupel (n, s) sein, z.B. (0.6, 0.4)
- config.NS_SHARES muss Dict tech -> (n, s) sein, z.B. {"Wind Offshore": (1.0, 0.0), ...}
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

from io_smard import build_zone_timeseries
from load_profiles import read_lastprofile_excel

from plants import load_plants_excel, build_plants_stack_for_zone, guess_zone_column
from island import run_island_model
from coupling import run_market_coupling
from scenarios import (
    build_de_single_from_4zones,
    build_ns_from_4zones,
    build_ntc_edges_4zone,
    build_ntc_edges_ns,
)

from kpi import kpi_island, kpi_coupled
from export_excel import export_all
from reporting import print_kpi_table

# optional plots (wenn MAKE_PLOTS=True)
from plots import (
    plot_island_zone_overview,
    plot_island_price_heatmaps,
    plot_ee_stack,
    plot_coupled_comparisons,
    plot_load_weighted_price_de,
    plot_coupled_price_heatmaps,
)


# -----------------------------------------------------------------------------
# Helper: robust float conversion (für Shares aus config)
# -----------------------------------------------------------------------------
def _to_float(x):
    if isinstance(x, str):
        x = x.strip().replace(",", ".")
    return float(x)


# -----------------------------------------------------------------------------
# 1) Zeitreihen: 4Z für gewünschtes Modelljahr bauen
# -----------------------------------------------------------------------------
def build_4zone_timeseries_for_year():
    """
    Gibt zurück:
      zone_results_4: dict(zone -> ts DataFrame)
      zone_vre_tech_4: dict(zone -> EE-by-tech DataFrame)
      dt_hours: float
    """
    # --- Basis: 2024 SMARD laden (immer, weil Future EE-Shape daraus kommt) ---
    zone_results_4_2024 = {}
    zone_vre_tech_4_2024 = {}
    meta_2024 = {}

    print("=" * 90)
    print("BAUE 4-ZONEN SMARD-ZEITREIHEN 2024 (Basis)")
    print("=" * 90)

    for z, cfg in C.ZONES_4.items():
        ts, vre_by_tech, meta = build_zone_timeseries(
            cfg["load_xlsx"],
            cfg["gen_xlsx"],
            time_freq=C.TIME_FREQ,
            ee_needles=C.EE_NEEDLES,
        )
        zone_results_4_2024[z] = ts
        zone_vre_tech_4_2024[z] = vre_by_tech
        meta_2024[z] = meta
        print(f"[2024 {z}] load_col={meta['load_col']} | missing_ee={meta['missing_ee']}")

    any_zone = next(iter(meta_2024.keys()))
    dt_hours_2024 = meta_2024[any_zone]["dt_hours"]

    # --- Modelljahr 2024: direkt zurück ---
    if C.MODEL_YEAR == 2024:
        print("\nModelljahr 2024 -> nutze direkt SMARD-Daten.")
        return zone_results_4_2024, zone_vre_tech_4_2024, dt_hours_2024

    # --- Future Jahre: Lastprofile + EE-Skalierung ---
    year = int(C.MODEL_YEAR)

    print("\n" + "=" * 90)
    print(f"BAUE 4-ZONEN ZEITREIHEN FÜR MODELLJAHR {year}")
    print("Last: data/Last_errechnet, EE: 2024-Shape * Faktoren")
    print("=" * 90)

    zone_results_4 = {}
    zone_vre_tech_4 = {}

    # Faktoren bestimmen
    def factors_for(zone_name):
        if C.EE_SCALING_MODE == "none":
            return {}
        if C.EE_SCALING_MODE == "global":
            return dict(C.EE_FACTORS_GLOBAL.get(year, {}))
        if C.EE_SCALING_MODE == "per_zone":
            base = dict(C.EE_FACTORS_GLOBAL.get(year, {}))
            base.update(dict(C.EE_FACTORS_PER_ZONE.get(year, {}).get(zone_name, {})))
            return base
        raise ValueError(f"Unbekannter EE_SCALING_MODE: {C.EE_SCALING_MODE}")

    for z in C.ZONES_4.keys():
        # Lastprofil
        if z not in C.LASTPROFILE_FILES:
            raise KeyError(f"Kein Lastprofil in config.LASTPROFILE_FILES für Zone '{z}' definiert.")
        load_path = C.LASTPROFILE_FILES[z]
        load_s = read_lastprofile_excel(load_path, year=year, time_freq=C.TIME_FREQ).astype(float)

        # EE Shape aus 2024 (reindex auf Last-Index)
        ee_2024 = zone_vre_tech_4_2024[z].reindex(load_s.index, method="nearest")

        # Skalieren
        fac = factors_for(z)
        ee_scaled = pd.DataFrame(index=ee_2024.index)
        for tech in ee_2024.columns:
            f = float(fac.get(tech, 1.0))
            ee_scaled[tech] = ee_2024[tech] * f

        vre_mw = ee_scaled.sum(axis=1)

        # ts bauen wie SMARD-Format
        ts = pd.DataFrame(index=load_s.index)
        ts["load_mw"] = load_s
        ts["vre_mw"] = vre_mw
        ts["residual_raw_mw"] = ts["load_mw"] - ts["vre_mw"]
        ts["abregelung_mw"] = (-ts["residual_raw_mw"]).clip(lower=0.0)
        ts["konv_bedarf_mw"] = (ts["residual_raw_mw"]).clip(lower=0.0)

        dt_hours = (ts.index[1] - ts.index[0]).total_seconds() / 3600.0
        ts["load_mwh"] = ts["load_mw"] * dt_hours
        ts["vre_mwh"] = ts["vre_mw"] * dt_hours
        ts["konv_mwh"] = ts["konv_bedarf_mw"] * dt_hours
        ts["abregel_mwh"] = ts["abregelung_mw"] * dt_hours

        zone_results_4[z] = ts
        zone_vre_tech_4[z] = ee_scaled

        print(f"[{year} {z}] Last={Path(load_path).name} | EE_Faktoren={fac if fac else '1.0 (none)'}")

    # dt_hours aus einer Zone
    any_z = next(iter(zone_results_4.keys()))
    dt_hours = (zone_results_4[any_z].index[1] - zone_results_4[any_z].index[0]).total_seconds() / 3600.0
    return zone_results_4, zone_vre_tech_4, dt_hours


# -----------------------------------------------------------------------------
# 2) Plants: Stacks je Zone laden (4Z / DE / NS)
# -----------------------------------------------------------------------------
def build_plants_for_z4():
    plants_raw = load_plants_excel(C.PLANTS_XLSX_Z4, sheet_name=C.PLANTS_SHEET_Z4)
    zone_plants = {}

    # In 4Z-Liste ist die Zone i.d.R. in der Spalte "ÜNB"
    zone_col = "ÜNB" if "ÜNB" in plants_raw.columns else guess_zone_column(plants_raw)

    for z in C.ZONES_4.keys():
        uenb_name = C.ZONES_4[z]["uenb"]
        zone_plants[z] = build_plants_stack_for_zone(
            plants_raw,
            zone_name=uenb_name,
            zone_col=zone_col,
            cap_mode=C.CAP_MODE,
            filter_active_only=C.FILTER_ACTIVE_ONLY,
        )
    return zone_plants


def build_plants_for_de():
    plants_raw = load_plants_excel(C.PLANTS_XLSX_Z4, sheet_name=C.PLANTS_SHEET_Z4).copy()
    # alles zu einer Zone "DE"
    plants_raw["DE_ZONE"] = "DE"
    zone_plants = {
        "DE": build_plants_stack_for_zone(
            plants_raw,
            zone_name="DE",
            zone_col="DE_ZONE",
            cap_mode=C.CAP_MODE,
            filter_active_only=C.FILTER_ACTIVE_ONLY,
        )
    }
    return zone_plants


def build_plants_for_ns():
    """
    Kraftwerks-Stacks für Nord/Süd aufbauen.

    Unterstützt zwei Varianten:
    - Zukunftslisten (2037/2045): Spalte 'NS_Zone' vorhanden
    - 2024-Liste: Spalte 'ÜNB' enthält bereits 'Nord' / 'Süd'
    """

    plants_raw = load_plants_excel(C.PLANTS_XLSX_NS, sheet_name=C.PLANTS_SHEET_NS)

    cols = list(plants_raw.columns)

    # 1) Präferenz: explizite NS_Zone-Spalte (2037/2045)
    if "NS_Zone" in cols:
        zone_col = "NS_Zone"

    # 2) 2024-Liste: ÜNB-Spalte enthält 'Nord' / 'Süd'
    elif "ÜNB" in cols:
        zone_col = "ÜNB"

    # 3) Fallback: versuche config.NS_PLANTS_ZONE_COL oder guess_zone_column
    elif hasattr(C, "NS_PLANTS_ZONE_COL") and C.NS_PLANTS_ZONE_COL in cols:
        zone_col = C.NS_PLANTS_ZONE_COL
    else:
        # letzter Versuch: heuristisch (sollte im NS-Fall eigentlich nicht nötig sein)
        zone_col = guess_zone_column(plants_raw)

    # Zonennamen normalisieren
    plants_raw[zone_col] = plants_raw[zone_col].astype(str).str.strip()
    z_cf = plants_raw[zone_col].str.casefold()

    # alles, was "nord" enthält → NORD
    plants_raw.loc[z_cf.str.contains("nord", na=False), zone_col] = "NORD"
    # alles mit "süd", "sued", "sud" → SUED
    plants_raw.loc[z_cf.str.contains("süd|sued|sud", regex=True, na=False), zone_col] = "SUED"

    print("[NS] verwendete Zone-Spalte:", zone_col)
    print("[NS] Einzigartige Zonenwerte nach Mapping:",
          sorted(plants_raw[zone_col].dropna().unique().tolist()))

    zone_plants = {}
    for z in ["NORD", "SUED"]:
        zone_plants[z] = build_plants_stack_for_zone(
            plants_raw,
            zone_name=z,
            zone_col=zone_col,
            cap_mode=C.CAP_MODE,
            filter_active_only=C.FILTER_ACTIVE_ONLY,
        )
    return zone_plants


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    print("=> Modelljahr:", C.MODEL_YEAR)
    print("=> Plants-Datei 4Z :", C.PLANTS_XLSX_Z4)
    print("=> Plants-Datei NS :", C.PLANTS_XLSX_NS)

    # 1) Zeitreihen (4Z)
    zone_results_4, zone_vre_tech_4, dt_hours_4 = build_4zone_timeseries_for_year()

    # 2) Szenario-Transformation
    print("\n" + "=" * 90)
    print("SCENARIO:", C.SCENARIO, "| MODEL_YEAR:", C.MODEL_YEAR)
    print("=" * 90)

    if C.SCENARIO in ("Z4_INSEL", "Z4_COUPLED"):
        zone_results = zone_results_4
        zone_vre_tech = zone_vre_tech_4
        zones = list(C.ZONES_4.keys())
        dt_hours = dt_hours_4
        zone_plants = build_plants_for_z4()

    elif C.SCENARIO == "DE_SINGLE":
        zone_results, zone_vre_tech, dt_hours = build_de_single_from_4zones(zone_results_4, zone_vre_tech_4)
        zones = ["DE"]
        zone_plants = build_plants_for_de()

    elif C.SCENARIO in ("NS_INSEL", "NS_COUPLED"):
        # NS Zeitreihen aus 4Z (Last & EE splitten; Tech-Shares aus config)
        # Erwartet: NS_LOAD_SHARE = (n, s) und NS_SHARES = tech -> (n, s)
        # (Wenn du diese beiden in config noch als Dict/anderes Format hast: bitte entsprechend ändern.)
        zone_results, zone_vre_tech, dt_hours = build_ns_from_4zones(
            zone_results_4,
            zone_vre_tech_4,
            ns_shares=C.NS_SHARES,
            ns_load_share=C.NS_LOAD_SHARE,
        )
        zones = ["NORD", "SUED"]
        zone_plants = build_plants_for_ns()

    else:
        raise ValueError(f"Unbekanntes SCENARIO: {C.SCENARIO}")

    # 3) Inselmodell
    print("\n" + "=" * 90)
    print("RUN INSEL-MODELL")
    print("=" * 90)

    for z in zones:
        zone_results[z] = run_island_model(
            zone_results[z],
            plants_info=zone_plants[z],
            dt_hours=dt_hours,
            voll=C.VOLL,
            scarcity_pricing_in_price=C.SCARCITY_PRICING_IN_PRICE,
            price_nan_when_no_conv=C.PRICE_NAN_WHEN_NO_CONV,
            reserve_price_max=C.RESERVE_PRICE_MAX,
        )

    kpi_island_df = kpi_island(zone_results, zone_plants)
    print("\nKPIs (INSEL):")
    print_kpi_table(kpi_island_df, f"KPIs (INSEL) – {C.SCENARIO}")

    # Plots (Insel)
    if getattr(C, "MAKE_PLOTS", False):
        print("\n" + "=" * 90)
        print("PLOTS (INSEL)")
        print("=" * 90)
        plot_island_zone_overview(zone_results, zone_plants)
        plot_island_price_heatmaps(zone_results)
        plot_ee_stack(zone_vre_tech)

    # 4) Market Coupling optional
    coupled = None
    kpi_coupled_df = None

    if C.SCENARIO in ("Z4_COUPLED", "NS_COUPLED"):
        print("\n" + "=" * 90)
        print("RUN MARKET COUPLING (LP)")
        print("=" * 90)

        if C.SCENARIO == "Z4_COUPLED":
            ntc_edges = build_ntc_edges_4zone(
                C.NTC_BASE_MID,
                C.NTC_SCALE,
                C.DEFAULT_TRADE_COST,
                C.EDGE_TRADE_COSTS,
            )
        else:
            ntc_edges = build_ntc_edges_ns(C.NS_NTC_MW, C.NS_TRADE_COST)

        coupled = run_market_coupling(
            zones=zones,
            zone_ts=zone_results,
            zone_plants=zone_plants,
            ntc_edges=ntc_edges,
            dt_hours=dt_hours,
            voll=C.VOLL,
            scarcity_pricing_in_price=C.SCARCITY_PRICING_IN_PRICE,
            price_nan_when_no_conv=C.PRICE_NAN_WHEN_NO_CONV,
            reserve_price_max=C.RESERVE_PRICE_MAX,
        )

        kpi_coupled_df = kpi_coupled(coupled, zones, dt_hours)
        print("\nKPIs (COUPLED):")
        print_kpi_table(kpi_coupled_df, f"KPIs (COUPLED) – {C.SCENARIO}")

        # Plots (Coupled)
        if getattr(C, "MAKE_PLOTS", False):
            print("\n" + "=" * 90)
            print("PLOTS (COUPLED)")
            print("=" * 90)
            plot_coupled_comparisons(zone_results, coupled, zones, dt_hours)
            plot_load_weighted_price_de(zone_results, coupled, zones)
            plot_coupled_price_heatmaps(coupled, zones)

    # 5) Export
    out_xlsx = C.out_xlsx_name()
    export_all(
        out_xlsx=out_xlsx,
        kpi_island_df=kpi_island_df,
        zone_results=zone_results,
        zone_vre_tech=zone_vre_tech,
        zone_plants=zone_plants,
        coupled=coupled,
        kpi_coupled_df=kpi_coupled_df,
    )

    print("\nFertig. Excel geschrieben:", out_xlsx)


if __name__ == "__main__":
    main()