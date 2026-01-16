# export_excel.py
"""
Excel-Export: schreibt Insel- und optional Coupled-Daten.
Wichtig: Zeitzonen entfernen, sonst meckert Excel.
"""

import pandas as pd


def export_all(out_xlsx,
               kpi_island_df,
               zone_results,
               zone_vre_tech,
               zone_plants,
               coupled=None,
               kpi_coupled_df=None):
    # Insel TS long-form (zone + time)
    ts_long = []
    for z, ts in zone_results.items():
        tmp = ts.copy()
        tmp.insert(0, "time", tmp.index.tz_localize(None))  # tz entfernen
        tmp.insert(1, "zone", z)
        ts_long.append(tmp.reset_index(drop=True))
    timeseries_all = pd.concat(ts_long, ignore_index=True)

    # EE by tech long-form
    ee_long = []
    for z, ee in zone_vre_tech.items():
        tmp = ee.copy()
        tmp.insert(0, "time", tmp.index.tz_localize(None))
        tmp.insert(1, "zone", z)
        ee_long.append(tmp.reset_index(drop=True))
    ee_by_tech_all = pd.concat(ee_long, ignore_index=True)

    coupled_export = None
    if coupled is not None:
        coupled_export = coupled.copy()
        coupled_export.insert(0, "time", coupled_export.index.tz_localize(None))
        coupled_export = coupled_export.reset_index(drop=True)

    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        # KPIs + Zeitreihen
        kpi_island_df.to_excel(writer, index=False, sheet_name="kpi_zone_insel")
        timeseries_all.to_excel(writer, index=False, sheet_name="timeseries_insel")
        ee_by_tech_all.to_excel(writer, index=False, sheet_name="ee_by_tech_mw")

        # Plants exports
        for z in zone_plants.keys():
            zone_plants[z]["plants_cap"].to_excel(writer, index=False, sheet_name=f"plants_cap_{z}"[:31])
            zone_plants[z]["plants_stack"].to_excel(writer, index=False, sheet_name=f"plants_stack_{z}"[:31])
            zone_plants[z]["plants_no_mc"].to_excel(writer, index=False, sheet_name=f"plants_no_mc_{z}"[:31])
            zone_plants[z]["plants_with_cap"].to_excel(writer, index=False, sheet_name=f"plants_with_cap_{z}"[:31])

        # Coupled exports
        if kpi_coupled_df is not None:
            kpi_coupled_df.to_excel(writer, index=False, sheet_name="kpi_zone_coupled")
        if coupled_export is not None:
            coupled_export.to_excel(writer, index=False, sheet_name="timeseries_coupled")
