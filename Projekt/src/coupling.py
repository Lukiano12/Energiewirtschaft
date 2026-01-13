# coupling.py
"""
Market Coupling (Handel) als lineares Programm (LP) pro Zeitschritt.

Variablen:
- ee_used_z in [0, EE_av]
- g_zk in [0, cap_zk] (konventionelle Segmente)
- unserved_z >= 0 (sehr teuer, VOLL)
- flow_a->b in [0, ntc_a->b] (Handelsflüsse)

Bilanz pro Zone:
ee_used + sum(g) + imports - exports + unserved = load

Preisreporting:
- Dualpreis (Schattenpreis) oder MO-like Proxy (aus Dispatch)
"""

import numpy as np
import pandas as pd


def run_market_coupling(
    zones, zone_ts, zone_plants, ntc_edges, dt_hours,
    voll: float,
    scarcity_pricing_in_price: bool,
    price_nan_when_no_conv: bool,
    reserve_price_max: bool
):
    """
    Löst pro Zeitschritt ein LP mit scipy.optimize.linprog.
    Gibt DataFrame 'coupled' zurück.
    """
    try:
        from scipy.optimize import linprog
    except Exception as e:
        raise ImportError("Für Market Coupling brauchst du scipy: pip install scipy") from e

    # Konventionelle Segmente pro Zone (cap, mc)
    def supply_segments_for(z):
        ps = zone_plants[z]["plants_stack"].copy()
        ps = ps.dropna(subset=["cap_mw", "mc"])
        ps = ps[ps["cap_mw"] > 0].sort_values("mc").reset_index(drop=True)
        return list(zip(ps["cap_mw"].to_numpy(), ps["mc"].to_numpy()))

    supply = {z: supply_segments_for(z) for z in zones}

    # Hilfsfunktion: "MO-like" Preis aus tatsächlich genutzten Segmenten
    def molike_price_from_dispatch(z, x, idx_g, supply_segments, eps=1e-6):
        used_mcs = []
        for local_i, var_i in enumerate(idx_g[z]):
            if float(x[var_i]) > eps:
                used_mcs.append(float(supply_segments[z][local_i][1]))
        return float(max(used_mcs)) if used_mcs else np.nan

    time_index = zone_ts[zones[0]].index
    rows = []

    for t in time_index:
        # Last und EE-Verfügbarkeit (MW)
        L = {z: float(zone_ts[z].loc[t, "load_mw"]) for z in zones}
        EE_av = {z: float(zone_ts[z].loc[t, "vre_mw"]) for z in zones}

        # Wir bauen LP-Variablen als Vektor x:
        # [ee_used_z, g_zk..., unserved_z] für alle z
        # plus [flows...] für alle gerichteten Kanten
        var_names, bounds, c = [], [], []

        idx_ee = {}
        idx_unserved = {}
        idx_g = {z: [] for z in zones}
        idx_flow = {}

        # --- Variablen pro Zone ---
        for z in zones:
            # EE Nutzung (0..EE_av)
            idx_ee[z] = len(var_names)
            var_names.append(f"ee_used_{z}")
            bounds.append((0.0, EE_av[z]))
            c.append(0.0)

            # Konventionelle Segmente
            for k, (cap, mc) in enumerate(supply[z]):
                idx_g[z].append(len(var_names))
                var_names.append(f"g_{z}_{k}")
                bounds.append((0.0, float(cap)))
                c.append(float(mc))

            # Unserved (sehr teuer)
            idx_unserved[z] = len(var_names)
            var_names.append(f"unserved_{z}")
            bounds.append((0.0, None))
            c.append(float(voll))

        # --- Flussvariablen pro Kante (a->b) ---
        for (a, b, ntc, tc) in ntc_edges:
            idx_flow[(a, b)] = len(var_names)
            var_names.append(f"f_{a}_to_{b}")
            bounds.append((0.0, float(ntc)))
            c.append(float(tc))

        n = len(var_names)

        # --- Bilanzgleichungen A_eq x = b_eq ---
        A_eq, b_eq = [], []
        for z in zones:
            row = np.zeros(n)

            # lokale Quellen
            row[idx_ee[z]] = 1.0
            for gi in idx_g[z]:
                row[gi] = 1.0
            row[idx_unserved[z]] = 1.0

            # Flüsse: Import +, Export -
            for (a, b, ntc, tc) in ntc_edges:
                if b == z:
                    row[idx_flow[(a, b)]] += 1.0
                if a == z:
                    row[idx_flow[(a, b)]] -= 1.0

            A_eq.append(row)
            b_eq.append(L[z])

        A_eq = np.vstack(A_eq)
        b_eq = np.array(b_eq)

        # --- LP lösen ---
        res = linprog(c=c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
        if not res.success:
            raise RuntimeError(f"LP failed at {t}: {res.message}")

        x = res.x
        out = {"time": t}

        # --- Ergebnisse pro Zone ---
        for z in zones:
            ee_used = float(x[idx_ee[z]])
            gen_conv = float(sum(x[gi] for gi in idx_g[z]))
            unserved = float(x[idx_unserved[z]])
            curtail = float(max(EE_av[z] - ee_used, 0.0))

            imp = 0.0
            exp = 0.0
            for (a, b, ntc, tc) in ntc_edges:
                f = float(x[idx_flow[(a, b)]])
                if b == z:
                    imp += f
                if a == z:
                    exp += f

            out[f"{z}_ee_used_mw"] = ee_used
            out[f"{z}_curtail_mw"] = curtail
            out[f"{z}_gen_conv_mw"] = gen_conv
            out[f"{z}_unserved_mw"] = unserved
            out[f"{z}_import_mw"] = imp
            out[f"{z}_export_mw"] = exp

        # --- Preisberechnung: Dual vs MO-like ---
        # A) Dualpreise (Schattenpreise der Bilanzrestriktionen)
        dual_price = {}
        try:
            duals = res.eqlin.marginals
            for i, z in enumerate(zones):
                dual_price[z] = float(duals[i])
        except Exception:
            for z in zones:
                dual_price[z] = np.nan

        # B) MO-like Preis
        mo_like_price = {}
        for z in zones:
            unserved = float(x[idx_unserved[z]])
            conv_gen = float(sum(x[gi] for gi in idx_g[z]))

            if unserved > 1e-6:
                # Unserved -> nicht VOLL (wenn scarcity_pricing_in_price=False),
                # sondern "Insel-Fallback" (Reserve max oder max overall).
                max_mc_res = zone_plants[z]["max_mc_reserve"]
                max_mc_all = zone_plants[z]["max_mc_all"]

                if reserve_price_max and not np.isnan(max_mc_res):
                    mo_like_price[z] = float(max_mc_res)
                else:
                    mo_like_price[z] = float(max_mc_all) if not np.isnan(max_mc_all) else np.nan
            else:
                if conv_gen > 1e-6:
                    mo_like_price[z] = molike_price_from_dispatch(z, x, idx_g, supply)
                else:
                    # nur EE / keine konv. Erzeugung
                    mo_like_price[z] = np.nan if price_nan_when_no_conv else 0.0

        # Reporteter Preis je nach Schalter
        for z in zones:
            out[f"{z}_price_eur_mwh"] = dual_price[z] if scarcity_pricing_in_price else mo_like_price[z]
            # Debug: beide Preisreihen mitschreiben
            out[f"{z}_price_dual_eur_mwh"] = dual_price[z]
            out[f"{z}_price_molike_eur_mwh"] = mo_like_price[z]

        rows.append(out)

    coupled = pd.DataFrame(rows).set_index("time")
    return coupled
