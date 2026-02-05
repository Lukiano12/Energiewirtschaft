# plots.py
"""
Plot-Funktionen für das Projekt.

Ziel:
- Plots sind optional (nicht zwingend fürs Rechnen/Excel).
- Funktioniert für verschiedene Szenarien:
  - DE_SINGLE (eine Zone: "DE")
  - Z4_* (vier Zonen)
  - NS_* (zwei Zonen: "NORD", "SUED")

Wir plotten:
1) Tagesmax/mean Konv.-Bedarf vs Abgedeckt vs Unserved (Insel)
2) Preis-Heatmap (Monat x Stunde) (Insel & Coupled)
3) EE-Aufteilung nach Tech (Tagesmittel)
4) Bei Coupling:
   - Vergleich Insel vs Coupled (Unserved & Preis)
   - Load-gewichteter Preis für ganz DE

WICHTIG:
- Skalen (y-Achse / Farben) sollen über Zonen vergleichbar sein.
- Alle einstellbaren Parameter kommen aus config.py (falls vorhanden),
  ansonsten greifen sinnvolle Defaults.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import config as C


# ---------------------------------------------------------------------------
# Hilfsfunktionen & Config-Helper
# ---------------------------------------------------------------------------


def _cfg(name: str, default):
    """
    Hilfsfunktion: Wert aus config holen, ansonsten Default verwenden.

    Beispiel:
        vmin = _cfg("PRICE_HEATMAP_VMIN", None)
    """
    return getattr(C, name, default)


def _prepare_series(s: pd.Series) -> pd.Series:
    """
    Zeitreihe säubern:
    - Index sortieren
    - in float umwandeln
    - ±inf -> NaN
    - optional interpolieren (PLOT_INTERPOLATE_SERIES)
    """
    if s is None:
        return s
    s = s.copy()
    s = s.sort_index()
    s = s.astype(float)
    s = s.replace([np.inf, -np.inf], np.nan)

    if _cfg("PLOT_INTERPOLATE_SERIES", True):
        s = s.interpolate(limit_direction="both")

    return s


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame spaltenweise mit _prepare_series säubern.
    """
    if df is None:
        return df
    df = df.copy()
    df = df.sort_index()
    for col in df.columns:
        df[col] = _prepare_series(df[col])
    return df


def _daily_sum_mwh_from_mw(power_mw: pd.Series, dt_hours: float) -> pd.Series:
    """
    Wandelt eine Leistungs-Zeitreihe (MW) in eine Tages-Energie (MWh/Tag) um.
    """
    p = _prepare_series(power_mw)
    energy_mwh = p * float(dt_hours)
    return energy_mwh.resample("D").sum()


# ---------------------------------------------------------------------------
# 1) Insel: Konv.-Bedarf / Abdeckung / Unserved (Tagesmax)
# ---------------------------------------------------------------------------


def plot_island_zone_overview(
    zone_results: Dict[str, pd.DataFrame],
    zone_plants: Dict[str, dict],
) -> None:
    """
    Für jede Zone:
    - Tagesmax Konv.-Bedarf, Abdeckung, Unserved (MW)
    - y-Achse über alle Zonen vergleichbar.

    Erwartete Spalten in zone_results[z]:
        "konv_bedarf_mw", "abgedeckt_mw", "unserved_mw"
    Erwarteter Key in zone_plants[z]:
        "stack_cap_effective" (MW)
    """
    if not zone_results:
        print("[plots] plot_island_zone_overview: zone_results leer, skip.")
        return

    # dt_hours aus einer beliebigen Zone ableiten
    any_z = next(iter(zone_results.keys()))
    ts_any = zone_results[any_z]
    ts_any = _prepare_df(ts_any)
    if len(ts_any.index) < 2:
        print("[plots] plot_island_zone_overview: zu wenige Zeitschritte.")
        return
    dt_hours = (ts_any.index[1] - ts_any.index[0]).total_seconds() / 3600.0

    # 1) globales y-Max bestimmen (falls nicht in config vorgegeben)
    global_ymax = _cfg("ISLAND_CONV_YMAX", None)
    if global_ymax is None:
        ymax = 0.0
        for z, ts in zone_results.items():
            ts = _prepare_df(ts)
            needed_cols = {"konv_bedarf_mw", "abgedeckt_mw", "unserved_mw"}
            if not needed_cols.issubset(ts.columns):
                continue
            daily_max = ts[list(needed_cols)].resample("D").max()
            if not daily_max.empty:
                ymax = max(ymax, float(daily_max.max().max()))
        global_ymax = ymax * 1.05 if ymax > 0 else None

    # 2) Plots je Zone erstellen
    for z, ts in zone_results.items():
        ts = _prepare_df(ts)
        needed_cols = {"konv_bedarf_mw", "abgedeckt_mw", "unserved_mw"}
        if not needed_cols.issubset(ts.columns):
            print(f"[plots] plot_island_zone_overview: skip {z}, Spalten fehlen.")
            continue

        daily = pd.DataFrame({
            "need_max": ts["konv_bedarf_mw"].resample("D").max(),
            "cover_max": ts["abgedeckt_mw"].resample("D").max(),
            "unserved_max": ts["unserved_mw"].resample("D").max(),
        }).fillna(0.0)

        cap = None
        zp = zone_plants.get(z)
        if isinstance(zp, dict):
            cap = zp.get("stack_cap_effective", None)
            if cap is not None:
                cap = float(cap)

        fig, ax = plt.subplots(figsize=(12, 4))
        daily["need_max"].plot(ax=ax, label="Konv. Bedarf (Tages-Max)", linewidth=0.9)
        daily["cover_max"].plot(ax=ax, label="Abgedeckt (Tages-Max)", linewidth=0.9, linestyle="--")
        daily["unserved_max"].plot(ax=ax, label="Unserved (Tages-Max)", linewidth=0.9, linestyle=":")

        if cap is not None:
            ax.axhline(cap, linestyle=":", linewidth=1.2, label=f"Kapazität (nur mc) = {cap:.0f} MW")

        ax.set_title(f"{z}: Konv. Bedarf vs Abdeckung – INSEL (Tages-Max)")
        ax.set_ylabel("MW")
        if global_ymax is not None:
            ax.set_ylim(0.0, global_ymax)

        ax.legend()
        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------------------------
# 2) Preis-Heatmaps (Monat x Stunde) – Insel & Coupled
# ---------------------------------------------------------------------------


def _price_heatmap(
    ts_price: pd.Series,
    title: str,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> None:
    """
    Heatmap: Monat (x) vs Stunde (y) mit stündlichem Mittelpreis.
    Erwartet eine Zeitreihe mit DateTimeIndex.
    """
    if ts_price is None or ts_price.empty:
        print(f"[plots] _price_heatmap: {title} – leere Preiszeitreihe, skip.")
        return

    price = _prepare_series(ts_price)

    # auf Stundenmittel resamplen
    hp = price.resample("h").mean().to_frame("p")

    # NaNs/Infs behandeln
    hp["p"] = hp["p"].replace([np.inf, -np.inf], np.nan)

    fill_mode = _cfg("PRICE_HEATMAP_FILL_NA_MODE", "interpolate")  # "interpolate", "zero", "none"
    if fill_mode == "zero":
        hp["p"] = hp["p"].fillna(0.0)
    elif fill_mode == "interpolate":
        hp["p"] = hp["p"].interpolate(limit_direction="both")
    # bei "none": NaNs bleiben → Lücken in der Heatmap (bewusst)

    hp["month"] = hp.index.month
    hp["hour"] = hp.index.hour

    pivot = hp.pivot_table(
        index="hour",
        columns="month",
        values="p",
        aggfunc="mean",
    )

    # letzte Interpolationsebene direkt auf der Pivot-Matrix
    if fill_mode == "interpolate":
        pivot = (
            pivot.replace([np.inf, -np.inf], np.nan)
                 .interpolate(axis=0, limit_direction="both")
                 .interpolate(axis=1, limit_direction="both")
        )

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(
        pivot.values,
        aspect="auto",
        origin="lower",
        vmin=vmin,
        vmax=vmax,
    )

    fig.colorbar(im, ax=ax, label="Preis [€/MWh]")
    ax.set_title(title)
    ax.set_xlabel("Monat")
    ax.set_ylabel("Stunde")
    ax.set_yticks(range(0, 24, 3))
    # einfache Monatslabels (1..12)
    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns)
    plt.tight_layout()
    plt.show()


def _collect_price_bounds_from_series(series_list: List[pd.Series]) -> (float, float):
    """
    Liefert (min, max) über alle gegebenen Preisserien.
    """
    vals = []
    for s in series_list:
        if s is None:
            continue
        s = _prepare_series(s)
        s = s.replace([np.inf, -np.inf], np.nan)
        vals.append(s.values)
    if not vals:
        return 0.0, 0.0
    all_vals = np.concatenate(vals)
    all_vals = all_vals[~np.isnan(all_vals)]
    if all_vals.size == 0:
        return 0.0, 0.0
    return float(all_vals.min()), float(all_vals.max())


def plot_island_price_heatmaps(zone_results: Dict[str, pd.DataFrame]) -> None:
    """
    Preis-Heatmap für jede Zone (Insel-Preis) mit gemeinsamer Farblegende.
    """

    # Config-Werte lesen
    cfg_vmin = _cfg("PRICE_HEATMAP_VMIN", None)
    cfg_vmax = _cfg("PRICE_HEATMAP_VMAX", None)
    auto_from_data = _cfg("PRICE_HEATMAP_AUTO_FROM_DATA", False)

    if auto_from_data:
        # -> IMMER aus Daten bestimmen, Config dient dann nur optional zum "Clampen"
        series_list: List[pd.Series] = []
        for ts in zone_results.values():
            if "price_eur_mwh" in ts.columns:
                series_list.append(ts["price_eur_mwh"])

        data_min, data_max = _collect_price_bounds_from_series(series_list)

        # Wenn du hier noch die Möglichkeit haben willst, die Skala zu begrenzen:
        vmin = data_min if cfg_vmin is None else cfg_vmin
        vmax = data_max if cfg_vmax is None else cfg_vmax
    else:
        # reine Config-Skala (z.B. fix 0..350)
        vmin = cfg_vmin
        vmax = cfg_vmax

    if vmin is not None and vmax is not None:
        print(f"[plots] Insel-Heatmaps: vmin={vmin:.1f}, vmax={vmax:.1f}")
    else:
        print("[plots] Insel-Heatmaps: keine einheitlichen vmin/vmax gesetzt (individuelle Skalen).")

    # 2) Heatmaps zeichnen
    for z, ts in zone_results.items():
        if "price_eur_mwh" not in ts.columns:
            print(f"[plots] Skip price heatmap for {z}: no price_eur_mwh")
            continue
        _price_heatmap(
            ts["price_eur_mwh"],
            title=f"{z}: Preis-Heatmap (Monat x Stunde, stündl. Mittel) – INSEL",
            vmin=vmin,
            vmax=vmax,
        )



def plot_coupled_price_heatmaps(
    coupled: pd.DataFrame,
    zones: List[str],
) -> None:
    """
    Preis-Heatmap für jede Zone (Coupled-Preis) mit gemeinsamer Farblegende.
    """
    if coupled is None:
        print("[plots] plot_coupled_price_heatmaps: coupled is None -> skip.")
        return

    cfg_vmin = _cfg("PRICE_HEATMAP_VMIN", None)
    cfg_vmax = _cfg("PRICE_HEATMAP_VMAX", None)
    auto_from_data = _cfg("PRICE_HEATMAP_AUTO_FROM_DATA", False)

    if auto_from_data:
        series_list: List[pd.Series] = []
        for z in zones:
            col = f"{z}_price_eur_mwh"
            if col in coupled.columns:
                series_list.append(coupled[col])

        data_min, data_max = _collect_price_bounds_from_series(series_list)
        vmin = data_min if cfg_vmin is None else cfg_vmin
        vmax = data_max if cfg_vmax is None else cfg_vmax
    else:
        vmin = cfg_vmin
        vmax = cfg_vmax

    if vmin is not None and vmax is not None:
        print(f"[plots] Coupled-Heatmaps: vmin={vmin:.1f}, vmax={vmax:.1f}")
    else:
        print("[plots] Coupled-Heatmaps: keine einheitlichen vmin/vmax gesetzt (individuelle Skalen).")

    for z in zones:
        col = f"{z}_price_eur_mwh"
        if col not in coupled.columns:
            print(f"[plots] Skip coupled heatmap for {z}: missing column {col}")
            continue

        _price_heatmap(
            coupled[col],
            title=f"{z}: Preis-Heatmap (Monat x Stunde, stündl. Mittel) – COUPLED",
            vmin=vmin,
            vmax=vmax,
        )



# ---------------------------------------------------------------------------
# 3) EE-Aufteilung (Tagesmittel)
# ---------------------------------------------------------------------------


def plot_ee_stack(zone_vre_tech: Dict[str, pd.DataFrame]) -> None:
    """
    Für jede Zone:
    - Tagesmittel der EE nach Technologie (Stackplot).

    Erwartet:
        zone_vre_tech[z] = DataFrame mit Spalten je Technologie (MW),
        Index = DateTimeIndex (stündlich o.ä.).
    """
    if not zone_vre_tech:
        print("[plots] plot_ee_stack: zone_vre_tech leer, skip.")
        return

    for z, df in zone_vre_tech.items():
        if df is None or df.empty:
            print(f"[plots] plot_ee_stack: {z} leer, skip.")
            continue

        df = _prepare_df(df)
        daily = df.resample("D").mean().fillna(0.0)

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.stackplot(
            daily.index,
            [daily[c].values for c in daily.columns],
            labels=daily.columns,
            linewidth=0.0,
        )
        ax.set_title(f"{z}: EE-Aufteilung nach Technologie (Tagesmittel)")
        ax.set_ylabel("MW")
        ax.legend(loc="upper right", ncol=2, fontsize=8)
        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------------------------
# 4) Coupled-Vergleiche (Unserved & Preis)
# ---------------------------------------------------------------------------


def plot_coupled_comparisons(
    zone_results: Dict[str, pd.DataFrame],
    coupled: pd.DataFrame,
    zones: List[str],
    dt_hours: float,
) -> None:
    """
    Vergleicht für jede Zone Insel vs Coupled:
    - Unserved (MWh/Tag)
    - Preis (€/MWh, ggf. Tagesmittel)

    Erwartete Spalten:
        zone_results[z]["unserved_mw"]
        coupled[f"{z}_unserved_mw"]
        zone_results[z]["price_eur_mwh"]
        coupled[f"{z}_price_eur_mwh"]
    """
    if coupled is None:
        print("[plots] plot_coupled_comparisons: coupled is None -> skip.")
        return

    # --- Unserved Vergleich (MWh/Tag) ---
    for z in zones:
        if z not in zone_results:
            continue
        ts = zone_results[z]
        if "unserved_mw" not in ts.columns:
            continue
        col_c = f"{z}_unserved_mw"
        if col_c not in coupled.columns:
            continue

        u_island_mw = _prepare_series(ts["unserved_mw"])
        u_c_mw = _prepare_series(coupled[col_c])

        fig, ax = plt.subplots(figsize=(12, 4))
        _daily_sum_mwh_from_mw(u_island_mw, dt_hours).plot(
            ax=ax,
            linewidth=1.0,
            label="INSEL: Unserved (MWh/Tag)",
        )
        _daily_sum_mwh_from_mw(u_c_mw, dt_hours).plot(
            ax=ax,
            linewidth=1.0,
            linestyle="--",
            label="COUPLED: Unserved (MWh/Tag)",
        )
        ax.set_title(f"{z}: Unserved Vergleich – INSEL vs COUPLED")
        ax.set_ylabel("MWh/Tag")
        ax.legend()
        plt.tight_layout()
        plt.show()

    # --- Preisvergleich (Tagesmittel) ---
    for z in zones:
        if z not in zone_results:
            continue
        ts = zone_results[z]
        if "price_eur_mwh" not in ts.columns:
            continue
        col_c = f"{z}_price_eur_mwh"
        if col_c not in coupled.columns:
            continue

        p_island = _prepare_series(ts["price_eur_mwh"])
        p_c = _prepare_series(coupled[col_c])

        d_island = p_island.resample("D").mean()
        d_c = p_c.resample("D").mean()

        fig, ax = plt.subplots(figsize=(12, 4))
        d_island.plot(ax=ax, linewidth=1.0, label="INSEL: Tagesmittel Preis")
        d_c.plot(ax=ax, linewidth=1.0, linestyle="--", label="COUPLED: Tagesmittel Preis")
        ax.set_title(f"{z}: Preisvergleich – INSEL vs COUPLED (Tagesmittel)")
        ax.set_ylabel("€/MWh")
        ax.legend()
        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------------------------
# 5) Load-gewichteter Preis für ganz DE
# ---------------------------------------------------------------------------


def plot_load_weighted_price_de(
    zone_results: Dict[str, pd.DataFrame],
    coupled: Optional[pd.DataFrame],
    zones: List[str],
) -> None:
    """
    Plot des load-gewichteten DE-Preises (Insel vs Coupled).

    Erwartete Spalten:
        zone_results[z]["load_mw"]
        zone_results[z]["price_eur_mwh"]
        coupled[f"{z}_price_eur_mwh"]   (nur für Coupled Plot)
    """
    # Insel: load-gewichteter Preis
    prices_island = []
    loads = []
    for z in zones:
        if z not in zone_results:
            continue
        ts = _prepare_df(zone_results[z])
        if "load_mw" not in ts.columns or "price_eur_mwh" not in ts.columns:
            continue
        prices_island.append(ts["price_eur_mwh"])
        loads.append(ts["load_mw"])

    if not prices_island or not loads:
        print("[plots] plot_load_weighted_price_de: keine vollständigen Daten für Insel.")
        return

    # alle auf gemeinsamen Index bringen
    idx = prices_island[0].index
    for s in prices_island[1:] + loads:
        idx = idx.intersection(s.index)

    if idx.empty:
        print("[plots] plot_load_weighted_price_de: leerer Schnittmengen-Index.")
        return

    p_mat = np.vstack([s.reindex(idx).values for s in prices_island])
    l_mat = np.vstack([s.reindex(idx).values for s in loads])

    lw_price_island = (p_mat * l_mat).sum(axis=0) / np.clip(l_mat.sum(axis=0), 1e-9, None)
    lw_price_island = pd.Series(lw_price_island, index=idx, name="INSEL")

    # Coupled: load-gewichteter Preis
    lw_price_coupled = None
    if coupled is not None:
        prices_c = []
        loads_c = []
        for z in zones:
            if z not in zone_results:
                continue
            col_p = f"{z}_price_eur_mwh"
            if col_p not in coupled.columns:
                continue
            s_p = _prepare_series(coupled[col_p])

            s_load = _prepare_series(zone_results[z].get("load_mw"))
            if s_load is None:
                continue

            prices_c.append(s_p)
            loads_c.append(s_load)

        if prices_c and loads_c:
            idx_c = prices_c[0].index
            for s in prices_c[1:] + loads_c:
                idx_c = idx_c.intersection(s.index)

            if not idx_c.empty:
                p_mat_c = np.vstack([s.reindex(idx_c).values for s in prices_c])
                l_mat_c = np.vstack([s.reindex(idx_c).values for s in loads_c])
                lw_price_c = (p_mat_c * l_mat_c).sum(axis=0) / np.clip(l_mat_c.sum(axis=0), 1e-9, None)
                lw_price_coupled = pd.Series(lw_price_c, index=idx_c, name="COUPLED")

    # Plot
    fig, ax = plt.subplots(figsize=(12, 4))
    lw_price_island.resample("D").mean().plot(
        ax=ax,
        linewidth=1.0,
        label="INSEL: load-gewichteter Preis (Tagesmittel)",
    )
    if lw_price_coupled is not None:
        lw_price_coupled.resample("D").mean().plot(
            ax=ax,
            linewidth=1.0,
            linestyle="--",
            label="COUPLED: load-gewichteter Preis (Tagesmittel)",
        )

    ax.set_title("DE: Load-gewichteter Preis – INSEL vs COUPLED (Tagesmittel)")
    ax.set_ylabel("€/MWh")
    ax.legend()
    plt.tight_layout()
    plt.show()