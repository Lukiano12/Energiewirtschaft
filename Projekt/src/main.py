# main.py
"""
Hauptprogramm:
- liest config
- baut 4-Zonen SMARD-Zeitreihen (Basis)
- transformiert je nach Szenario (4Z / DE / NordSüd)
- lädt passende Kraftwerksliste
- baut Plants-Stacks pro Modellzone
- rechnet Inselmodell
- optional: Market Coupling (LP)
- exportiert alles nach Excel
- optional: Plots

WICHTIG:
- Coupled-Plots werden NUR ausgeführt, wenn coupled != None
  (sonst: Fehler wie bei dir: 'NoneType' object has no attribute 'columns')
"""

import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# Damit Imports in Spyder zuverlässig funktionieren:
# Wir fügen src/ zum Python-Pfad hinzu.
# -----------------------------------------------------------------------------
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import config as C

from io_smard import build_zone_timeseries
from plants import load_plants_excel, build_plants_stack_for_zone, guess_zone_column
from island import run_island_model
from coupling import run_market_coupling
from scenarios import (
    build_ntc_edges_4zone,
    build_ntc_edges_ns,
    build_de_single_from_4zones,
    build_ns_from_4zones,
)
from kpi import kpi_island, kpi_coupled
from export_excel import export_all

# Plot-Funktionen (optional)
from plots import (
    plot_island_zone_overview,
    plot_island_price_heatmaps,
    plot_ee_stack,
    plot_coupled_comparisons,
    plot_load_weighted_price_de,
    plot_coupled_price_heatmaps
)
from reporting import print_kpi_table


def main():
    # =============================================================================
    # 1) SMARD Zeitreihen für 4 ÜNB bauen (Basis für alle Szenarien)
    # =============================================================================
    zone_results_4 = {}
    zone_vre_tech_4 = {}
    meta_4 = {}

    print("=" * 90)
    print("BAUE 4-ZONEN SMARD-ZEITREIHEN")
    print("=" * 90)

    for z, cfg in C.ZONES_4.items():
        ts, vre_by_tech, meta = build_zone_timeseries(
            cfg["load_xlsx"],
            cfg["gen_xlsx"],
            time_freq=C.TIME_FREQ,
            ee_needles=C.EE_NEEDLES,
        )
        zone_results_4[z] = ts
        zone_vre_tech_4[z] = vre_by_tech
        meta_4[z] = meta

        print(f"[{z}] load_col={meta['load_col']} | missing_ee={meta['missing_ee']}")

    # dt_hours ist konstant (abhängig von TIME_FREQ)
    any_zone = next(iter(meta_4.keys()))
    dt_hours_4 = meta_4[any_zone]["dt_hours"]

    # =============================================================================
    # 2) Szenario wählen: Welche Modellzonen sollen gerechnet werden?
    # =============================================================================
    print("\n" + "=" * 90)
    print("SCENARIO:", C.SCENARIO)
    print("=" * 90)

    # Diese Variablen müssen wir am Ende gefüllt haben:
    # - zone_results: dict zone -> ts
    # - zone_vre_tech: dict zone -> ee_by_tech
    # - zone_plants: dict zone -> stack-info
    # - zones: Liste der Zonennamen
    # - dt_hours: Zeitschritt in Stunden
    zone_results = None
    zone_vre_tech = None
    zone_plants = None
    zones = None
    dt_hours = None

    if C.SCENARIO in ("Z4_INSEL", "Z4_COUPLED"):
        # --- 4 Zonen unverändert ---
        zone_results = zone_results_4
        zone_vre_tech = zone_vre_tech_4
        zones = list(zone_results.keys())
        dt_hours = dt_hours_4

        # Plants-Liste 4Z laden
        plants_raw = load_plants_excel(C.PLANTS_XLSX_Z4, sheet_name=C.PLANTS_SHEET_Z4)

        # In 4Z ist die Zonen-Spalte typischerweise "ÜNB"
        zone_col = "ÜNB"

        # Stacks bauen
        zone_plants = {}
        for z in zones:
            uenb_name = C.ZONES_4[z]["uenb"]
            zone_plants[z] = build_plants_stack_for_zone(
                plants_raw,
                zone_name=uenb_name,
                zone_col=zone_col,
                cap_mode=C.CAP_MODE,
                filter_active_only=C.FILTER_ACTIVE_ONLY,
            )

    elif C.SCENARIO == "DE_SINGLE":
        # --- Deutschland als eine Zone ---
        zone_results, zone_vre_tech, dt_hours = build_de_single_from_4zones(
            zone_results_4, zone_vre_tech_4
        )
        zones = ["DE"]

        # Plants: wir nehmen 4Z Liste und labeln alles als "DE"
        plants_raw = load_plants_excel(C.PLANTS_XLSX_Z4, sheet_name=C.PLANTS_SHEET_Z4).copy()
        plants_raw["ÜNB"] = "DE"

        zone_plants = {
            "DE": build_plants_stack_for_zone(
                plants_raw,
                zone_name="DE",
                zone_col="ÜNB",
                cap_mode=C.CAP_MODE,
                filter_active_only=C.FILTER_ACTIVE_ONLY,
            )
        }

    elif C.SCENARIO in ("NS_INSEL", "NS_COUPLED"):
        # --- Nord/Süd aus 4Z ableiten ---
        zone_results, zone_vre_tech, dt_hours = build_ns_from_4zones(
            zone_results_4,
            zone_vre_tech_4,
            ns_shares=C.NS_SHARES,
            ns_load_share=C.NS_LOAD_SHARE,
        )
        zones = ["NORD", "SUED"]

        # Plants: NS Liste laden
        plants_raw = load_plants_excel(C.PLANTS_XLSX_NS, sheet_name=C.PLANTS_SHEET_NS)

        # Welche Spalte enthält die Zone?
        zone_col = C.NS_PLANTS_ZONE_COL or guess_zone_column(plants_raw)
        
        # ------------------------------------------------------------
        # Zonennamen in der NS-Kraftwerksliste normalisieren:
        #   Excel enthält z.B. "Süd" -> wir mappen auf "SUED"
        # ------------------------------------------------------------
        plants_raw[zone_col] = plants_raw[zone_col].astype(str).str.strip()

        # casefold ist robuster als lower() (u.a. bei Umlauten/Sonderzeichen)
        z_cf = plants_raw[zone_col].str.casefold()

        # Mapping: "nord" -> NORD, "süd"/"sued" -> SUED
        plants_raw.loc[z_cf.str.contains("nord", na=False), zone_col] = "NORD"
        plants_raw.loc[z_cf.str.contains("süd|sued|sud", regex=True, na=False), zone_col] = "SUED"
        
        print("[NS] Einzigartige Zonenwerte nach Mapping:", sorted(plants_raw[zone_col].dropna().unique().tolist()))


        zone_plants = {}
        for z in zones:
            zone_plants[z] = build_plants_stack_for_zone(
                plants_raw,
                zone_name=z,
                zone_col=zone_col,
                cap_mode=C.CAP_MODE,
                filter_active_only=C.FILTER_ACTIVE_ONLY,
            )
    else:
        raise ValueError(f"Unbekanntes SCENARIO: {C.SCENARIO}")

    # Double-check: alles gesetzt?
    assert zone_results is not None and zone_vre_tech is not None and zone_plants is not None
    assert zones is not None and dt_hours is not None

    # =============================================================================
    # 3) Inselmodell pro Zone laufen lassen
    # =============================================================================
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


    # =============================================================================
    # 4) Insel-Plots (optional)
    # =============================================================================
    if getattr(C, "MAKE_PLOTS", False):
        print("\n" + "=" * 90)
        print("PLOTS (INSEL)")
        print("=" * 90)

        plot_island_zone_overview(zone_results, zone_plants)
        plot_island_price_heatmaps(zone_results)
        plot_ee_stack(zone_vre_tech)

    # =============================================================================
    # 5) Optional: Market Coupling (nur bei *_COUPLED Szenarien)
    # =============================================================================
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

    # =============================================================================
    # 6) Coupled-Plots (optional) - ABER NUR wenn coupled wirklich existiert!
    # =============================================================================
    if getattr(C, "MAKE_PLOTS", False) and (coupled is not None):
        print("\n" + "=" * 90)
        print("PLOTS (COUPLED)")
        print("=" * 90)

        plot_coupled_comparisons(zone_results, coupled, zones, dt_hours)
        plot_load_weighted_price_de(zone_results, coupled, zones)
        plot_coupled_price_heatmaps(coupled, zones)

    # =============================================================================
    # 7) Export Excel
    # =============================================================================
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
