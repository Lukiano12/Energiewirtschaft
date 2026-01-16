# island.py
"""
Inselmodell:
- Preisbildung (Merit-Order Heuristik)
- Unserved = max(konv_bedarf - cap, 0)
- Abgedeckt = min(konv_bedarf, cap)
- Schalter: Scarcity pricing und NaN bei nur-EE
"""

import numpy as np


def make_island_price_rule(cumcap_mo, mc_mo, max_mc_reserve, max_mc_all, reserve_price_max: bool):
    """
    Preisregel:
    - Bedarf innerhalb MO-Kapazität -> mc der marginalen MO-Anlage
    - Bedarf größer als MO -> Reserve max mc (wenn vorhanden) sonst max mc
    - Bedarf <=0 -> NaN
    """
    def price_rule(need_mw: float) -> float:
        if need_mw <= 0:
            return np.nan

        # innerhalb MO-Kapazität
        if len(cumcap_mo) and need_mw <= cumcap_mo[-1]:
            i = np.searchsorted(cumcap_mo, need_mw, side="left")
            return float(mc_mo[i])

        # außerhalb MO -> Reserve / max
        if reserve_price_max and not np.isnan(max_mc_reserve):
            return float(max_mc_reserve)

        if not np.isnan(max_mc_all):
            return float(max_mc_all)

        return np.nan

    return price_rule


def run_island_model(ts, plants_info, dt_hours: float, voll: float,
                     scarcity_pricing_in_price: bool,
                     price_nan_when_no_conv: bool,
                     reserve_price_max: bool):
    """
    Nimmt ts (mit konv_bedarf_mw) und ergänzt:
    - price_eur_mwh
    - unserved_mw/mwh
    - abgedeckt_mw/mwh
    """

    ts = ts.copy()

    # Preisregel bauen und anwenden
    pr = make_island_price_rule(
        plants_info["cumcap_mo"],
        plants_info["mc_mo"],
        plants_info["max_mc_reserve"],
        plants_info["max_mc_all"],
        reserve_price_max=reserve_price_max
    )
    ts["price_eur_mwh"] = ts["konv_bedarf_mw"].apply(pr)

    # Kapazität (nur mit mc)
    cap = float(plants_info["stack_cap_effective"])

    # Unserved = Bedarf - Kapazität
    ts["unserved_mw"] = (ts["konv_bedarf_mw"] - cap).clip(lower=0.0)
    ts["unserved_mwh"] = ts["unserved_mw"] * dt_hours

    # Abgedeckt = min(Bedarf, Kapazität)
    ts["abgedeckt_mw"] = np.minimum(ts["konv_bedarf_mw"].to_numpy(), cap)
    ts["abgedeckt_mwh"] = ts["abgedeckt_mw"] * dt_hours

    # Optional: Scarcity pricing im Preis sichtbar machen
    if scarcity_pricing_in_price:
        ts.loc[ts["unserved_mw"] > 0, "price_eur_mwh"] = voll

    # Optional: wenn kein konv Bedarf -> Preis = NaN (statt 0)
    if price_nan_when_no_conv:
        ts.loc[ts["konv_bedarf_mw"] <= 0, "price_eur_mwh"] = np.nan

    return ts
