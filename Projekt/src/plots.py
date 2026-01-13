# plots.py
"""
Plot-Funktionen für das Projekt.

Ziel:
- Plots sollen "optional" sein (nicht zwingend fürs Rechnen/Excel).
- Funktioniert für verschiedene Szenarien:
  - DE_SINGLE (eine Zone: "DE")
  - Z4_* (vier Zonen)
  - NS_* (zwei Zonen: "NORD", "SUED")

Wir plotten:
1) Tagesmax/mean Konv.-Bedarf vs Abgedeckt vs Unserved (Insel)
2) Preis-Heatmap (Monat x Stunde) (Insel)
3) EE-Aufteilung nach Tech (Tagesmittel)
4) Wenn Coupled vorhanden:
   - Preisvergleich Insel vs Coupled
   - Unserved Vergleich Insel vs Coupled (MWh/Tag)
   - Curtailment Vergleich Insel vs Coupled (MWh/Tag)
   - Nettoimport (MWh/Tag)
   - optional: Deckungsgrad Coupled (Tagesmittel)
   - optional: "DE-Preis" load-gewichtet (wenn mehrere Zonen)

Hinweis:
- Diese Plots sind relativ "leichtgewichtig". Wenn du sehr viele Daten
  (15min über ein ganzes Jahr) plottest, resamplen wir auf Tageswerte
  oder stündlich für Heatmaps -> spart viel Zeit und RAM.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# -----------------------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------------------
def _daily_mean(series: pd.Series) -> pd.Series:
    """Tagesmittel aus einer Zeitreihe."""
    return series.resample("D").mean()


def _daily_sum_mwh_from_mw(series_mw: pd.Series, dt_hours: float) -> pd.Series:
    """
    Wandelt MW Zeitreihe in MWh pro Zeitschritt um (MW * dt_hours)
    und summiert dann pro Tag.
    """
    return (series_mw * dt_hours).resample("D").sum()


def _price_heatmap(ts_price: pd.Series, title: str):
    """
    Heatmap: Monat (x) vs Stunde (y) mit stündlichem Mittelpreis.
    Erwartet eine Zeitreihe mit DateTimeIndex.
    """
    # stündliches Mittel für klare Heatmap
    hp = ts_price.resample("h").mean().to_frame("p")

    # Wenn Preis NaN ist (z.B. nur EE), bleibt er NaN -> Heatmap zeigt Lücken.
    hp["month"] = hp.index.month
    hp["hour"] = hp.index.hour

    pivot = hp.pivot_table(index="hour", columns="month", values="p", aggfunc="mean")

    fig, ax = plt.subplots(figsize=(9, 4))
    im = ax.imshow(pivot.values, aspect="auto", origin="lower")

    ax.set_title(title)
    ax.set_ylabel("Stunde")
    ax.set_xlabel("Monat")
    ax.set_xticks(range(12))
    ax.set_xticklabels(range(1, 13))

    plt.colorbar(im, ax=ax, label="€/MWh")
    plt.tight_layout()
    plt.show()


# -----------------------------------------------------------------------------
# Plots: Insel (pro Zone)
# -----------------------------------------------------------------------------
def plot_island_zone_overview(zone_results: dict, zone_plants: dict):
    """
    Für jede Zone:
    - Tages-Max/Mean Konv.-Bedarf vs Abdeckung vs Unserved
    - Kapazitätslinie (wirksame Kapazität, nur Anlagen mit mc)
    """
    for z, ts in zone_results.items():
        # Falls abgedeckt/unserved nicht vorhanden sind, skip (sollte aber da sein)
        needed_cols = {"konv_bedarf_mw", "abgedeckt_mw", "unserved_mw", "abregelung_mw"}
        if not needed_cols.issubset(set(ts.columns)):
            print(f"[plots] Skip overview for {z}: missing columns {needed_cols - set(ts.columns)}")
            continue

        cap = float(zone_plants[z]["stack_cap_effective"])

        daily = pd.DataFrame({
            "need_max": ts["konv_bedarf_mw"].resample("D").max(),
            "need_mean": ts["konv_bedarf_mw"].resample("D").mean(),
            "cover_max": ts["abgedeckt_mw"].resample("D").max(),
            "cover_mean": ts["abgedeckt_mw"].resample("D").mean(),
            "unserved_max": ts["unserved_mw"].resample("D").max(),
            "unserved_mean": ts["unserved_mw"].resample("D").mean(),
            "curtail_mean": ts["abregelung_mw"].resample("D").mean(),
        })

        # --- Tages-Max ---
        fig, ax = plt.subplots(figsize=(12, 4))
        daily["need_max"].plot(ax=ax, label="Konv. Bedarf (Tages-Max)", linewidth=0.9)
        daily["cover_max"].plot(ax=ax, label="Abgedeckt (Tages-Max)", linewidth=0.9, linestyle="--")
        daily["unserved_max"].plot(ax=ax, label="Unserved (Tages-Max)", linewidth=0.9, linestyle=":")
        ax.axhline(cap, linestyle=":", linewidth=1.2, label=f"Kapazität (nur mc) = {cap:.0f} MW")
        ax.set_title(f"{z}: Konv. Bedarf vs Abdeckung (Tages-Max) – INSEL")
        ax.set_ylabel("MW")
        ax.legend()
        plt.tight_layout()
        plt.show()

        # --- Tages-Mittel ---
        fig, ax = plt.subplots(figsize=(12, 4))
        daily["need_mean"].plot(ax=ax, label="Konv. Bedarf (Tages-Mittel)", linewidth=0.9)
        daily["cover_mean"].plot(ax=ax, label="Abgedeckt (Tages-Mittel)", linewidth=0.9, linestyle="--")
        daily["unserved_mean"].plot(ax=ax, label="Unserved (Tages-Mittel)", linewidth=0.9, linestyle=":")
        ax.axhline(cap, linestyle=":", linewidth=1.2, label=f"Kapazität (nur mc) = {cap:.0f} MW")
        ax.set_title(f"{z}: Konv. Bedarf vs Abdeckung (Tages-Mittel) – INSEL")
        ax.set_ylabel("MW")
        ax.legend()
        plt.tight_layout()
        plt.show()


def plot_island_price_heatmaps(zone_results: dict):
    """
    Preis-Heatmap für jede Zone (Insel-Preis).
    """
    for z, ts in zone_results.items():
        if "price_eur_mwh" not in ts.columns:
            print(f"[plots] Skip price heatmap for {z}: no price_eur_mwh")
            continue
        _price_heatmap(
            ts["price_eur_mwh"],
            title=f"{z}: Preis-Heatmap (Monat x Stunde, stündl. Mittel) – INSEL"
        )


def plot_ee_stack(zone_vre_tech: dict):
    """
    EE-Aufteilung nach Technologie (Tagesmittel) pro Zone.
    """
    for z, ee in zone_vre_tech.items():
        if ee.empty:
            print(f"[plots] Skip EE stack for {z}: empty DataFrame")
            continue

        ee_daily = ee.resample("D").mean()

        fig, ax = plt.subplots(figsize=(12, 4))
        ee_daily.plot.area(ax=ax, linewidth=0, alpha=0.9)
        ax.set_title(f"{z}: Erneuerbare – Aufteilung nach Technologie (Tagesmittel)")
        ax.set_ylabel("MW")
        ax.legend(loc="upper left", ncol=3)
        plt.tight_layout()
        plt.show()


# -----------------------------------------------------------------------------
# Plots: Coupled Vergleiche (wenn coupled vorhanden)
# -----------------------------------------------------------------------------
def plot_coupled_comparisons(
    zone_results: dict,
    coupled: pd.DataFrame,
    zones: list,
    dt_hours: float
):
    """
    Vergleich Insel vs Coupled für:
    - Preis (Tagesmittel)
    - Unserved (MWh/Tag)
    - Curtailment (MWh/Tag)
    - Nettoimport (MWh/Tag)
    - Deckungsgrad (Tagesmittel)
    """

    # --- Preisvergleich ---
    for z in zones:
        if "price_eur_mwh" not in zone_results[z].columns:
            continue
        if f"{z}_price_eur_mwh" not in coupled.columns:
            continue

        p_island = zone_results[z]["price_eur_mwh"]
        p_c = coupled[f"{z}_price_eur_mwh"]

        fig, ax = plt.subplots(figsize=(12, 4))
        _daily_mean(p_island).plot(ax=ax, linewidth=1.0, label="INSEL: Tagesmittel Preis")
        _daily_mean(p_c).plot(ax=ax, linewidth=1.0, linestyle="--", label="COUPLED: Tagesmittel Preis")
        ax.set_title(f"{z}: Preisvergleich Insel vs Coupled (Tagesmittel)")
        ax.set_ylabel("€/MWh")
        ax.legend()
        plt.tight_layout()
        plt.show()

    # --- Unserved Vergleich ---
    for z in zones:
        if "unserved_mw" not in zone_results[z].columns:
            continue
        if f"{z}_unserved_mw" not in coupled.columns:
            continue

        u_island_mw = zone_results[z]["unserved_mw"]
        u_c_mw = coupled[f"{z}_unserved_mw"]

        fig, ax = plt.subplots(figsize=(12, 4))
        _daily_sum_mwh_from_mw(u_island_mw, dt_hours).plot(ax=ax, linewidth=1.0, label="INSEL: Unserved (MWh/Tag)")
        _daily_sum_mwh_from_mw(u_c_mw, dt_hours).plot(ax=ax, linewidth=1.0, linestyle="--", label="COUPLED: Unserved (MWh/Tag)")
        ax.set_title(f"{z}: Unserved – Insel vs Coupled (Tagessumme)")
        ax.set_ylabel("MWh pro Tag")
        ax.legend()
        plt.tight_layout()
        plt.show()

    # --- Curtailment Vergleich ---
    for z in zones:
        if "abregelung_mw" not in zone_results[z].columns:
            continue
        if f"{z}_curtail_mw" not in coupled.columns:
            continue

        cur_island_mw = zone_results[z]["abregelung_mw"]
        cur_c_mw = coupled[f"{z}_curtail_mw"]

        fig, ax = plt.subplots(figsize=(12, 4))
        _daily_sum_mwh_from_mw(cur_island_mw, dt_hours).plot(ax=ax, linewidth=1.0, label="INSEL: Curtailment (MWh/Tag)")
        _daily_sum_mwh_from_mw(cur_c_mw, dt_hours).plot(ax=ax, linewidth=1.0, linestyle="--", label="COUPLED: Curtailment (MWh/Tag)")
        ax.set_title(f"{z}: Abregelung EE – Insel vs Coupled (Tagessumme)")
        ax.set_ylabel("MWh pro Tag")
        ax.legend()
        plt.tight_layout()
        plt.show()

    # --- Deckungsgrad im Coupled ---
    for z in zones:
        if f"{z}_unserved_mw" not in coupled.columns:
            continue
        # load kommt aus zone_results
        load_mw = zone_results[z]["load_mw"]
        u_c_mw = coupled[f"{z}_unserved_mw"]

        coverage = 1.0 - (u_c_mw / load_mw.replace(0, np.nan))
        coverage = coverage.clip(lower=0.0, upper=1.0)

        fig, ax = plt.subplots(figsize=(12, 3.5))
        _daily_mean(coverage).plot(ax=ax, linewidth=1.0)
        ax.set_title(f"{z}: Deckungsgrad im Coupled-Fall (Tagesmittel)")
        ax.set_ylabel("Anteil gedeckt (0..1)")
        ax.set_ylim(0, 1.01)
        plt.tight_layout()
        plt.show()

    # --- Nettoimport im Coupled ---
    for z in zones:
        if f"{z}_import_mw" not in coupled.columns or f"{z}_export_mw" not in coupled.columns:
            continue

        imp_mw = coupled[f"{z}_import_mw"]
        exp_mw = coupled[f"{z}_export_mw"]
        net_mw = imp_mw - exp_mw

        fig, ax = plt.subplots(figsize=(12, 4))
        _daily_sum_mwh_from_mw(net_mw, dt_hours).plot(ax=ax, linewidth=1.0)
        ax.axhline(0, linewidth=1)
        ax.set_title(f"{z}: Nettoimport im Coupled-Fall (MWh/Tag, positiv = Import)")
        ax.set_ylabel("MWh pro Tag")
        plt.tight_layout()
        plt.show()


def plot_load_weighted_price_de(zone_results: dict, coupled: pd.DataFrame, zones: list):
    """
    Deutschland-Preis (load-gewichtet) als Vergleich Insel vs Coupled.
    Sinnvoll, wenn mehr als 1 Zone existiert.
    """
    if len(zones) < 2:
        return

    # Insel-Preise und Loads
    loads = [zone_results[z]["load_mw"] for z in zones]
    p_islands = [zone_results[z]["price_eur_mwh"] for z in zones]

    # Coupled-Preise
    p_coups = [coupled[f"{z}_price_eur_mwh"] for z in zones if f"{z}_price_eur_mwh" in coupled.columns]
    if len(p_coups) != len(zones):
        # falls eine Zone fehlt, skip
        return

    load_total = sum(loads)

    p_island_de = sum(p_islands[i] * loads[i] for i in range(len(zones))) / load_total
    p_coup_de = sum(p_coups[i] * loads[i] for i in range(len(zones))) / load_total

    fig, ax = plt.subplots(figsize=(12, 4))
    _daily_mean(p_island_de).plot(ax=ax, linewidth=1.0, label="DE: INSEL (load-gewichtet)")
    _daily_mean(p_coup_de).plot(ax=ax, linewidth=1.0, linestyle="--", label="DE: COUPLED (load-gewichtet)")
    ax.set_title("Deutschland gesamt: load-gewichteter Preis (Tagesmittel) – Insel vs Coupled")
    ax.set_ylabel("€/MWh")
    ax.legend()
    plt.tight_layout()
    plt.show()
    
def plot_coupled_price_heatmaps(coupled: pd.DataFrame, zones: list):
    """
    Preis-Heatmap (Monat x Stunde) für COUPLED-Preise pro Zone.
    Analog zu den Insel-Heatmaps, aber Daten kommen aus coupled[f"{z}_price_eur_mwh"].
    """
    if coupled is None:
        print("[plots] coupled is None -> skip coupled price heatmaps.")
        return

    for z in zones:
        col = f"{z}_price_eur_mwh"
        if col not in coupled.columns:
            print(f"[plots] Skip coupled heatmap for {z}: missing column {col}")
            continue

        _price_heatmap(
            coupled[col],
            title=f"{z}: Preis-Heatmap (Monat x Stunde, stündl. Mittel) – COUPLED"
        )

