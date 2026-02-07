from pathlib import Path
from . import gui, config, data_loader, geodata, visualization

def run_epex_comparison(script_dir, output_dir):
    """
    Führt den EPEX-Vergleich aus: Modell 2024 vs. echte EPEX-Preise.
    Erstellt ein Profil des durchschnittlichen Tagesverlaufs (0-24 Uhr).
    """
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    
    print("\n" + "="*70)
    print("EPEX-VERGLEICH: DURCHSCHNITTLICHER TAGESVERLAUF (0-24h)")
    print("="*70)
    
    # WICHTIG: Resources aus Config holen
    data_dir = config.RESOURCES_DIR
    
    # 1) Lade Modellpreise
    cfg = config.SCENARIOS['de_single_2024']
    excel_path = data_loader.find_scenario_excel(data_dir, cfg['file_keyword'])
    
    if not excel_path:
        print("FEHLER: Keine Modell-Datei für 2024 DE_SINGLE gefunden!")
        gui.show_error("Datei nicht gefunden", 
                      "Bitte zuerst das Modell für 2024 DE_SINGLE ausführen!")
        return
    
    merit_orders = data_loader.load_merit_orders(excel_path, ['de'])
    res_loads, direct_prices = data_loader.load_timeseries(excel_path, cfg['sheet'], ['de'])
    
    # Berechne Modellpreise
    model_prices = visualization.calculate_hourly_prices(
        res_loads, merit_orders, ['de'], direct_prices=direct_prices
    )
    
    if model_prices.empty or 'de' not in model_prices.columns:
        print("FEHLER: Keine Modellpreise berechnet!")
        return
    
    model = model_prices['de']
    
    # 2) Lade EPEX-Preise
    epex = data_loader.load_epex_prices(config.EPEX_PRICE_FILE)
    
    if epex is None:
        print("\nEPEX-Datei nicht gefunden!")
        gui.show_error("EPEX-Datei fehlt", "Bitte EPEX-Preise laden (siehe Konsole).")
        return
    
    # 3) Gemeinsamer Index
    common_idx = model.index.intersection(epex.index)
    if len(common_idx) == 0:
        print("FEHLER: Keine gemeinsamen Zeitpunkte!")
        return
    
    model = model.loc[common_idx]
    epex = epex.loc[common_idx]
    
    # Statistiken
    diff = model - epex
    mae = np.abs(diff).mean()
    bias = diff.mean()
    
    # Jahresdurchschnitte berechnen
    avg_model = model.mean()
    avg_epex = epex.mean()

    print(f"Vergleich über {len(common_idx)} Stunden.")
    print(f"  Ø Modellpreis: {avg_model:.2f} €/MWh")
    print(f"  Ø EPEX-Preis:  {avg_epex:.2f} €/MWh")
    
    # -------------------------------------------------------------------------
    # BERECHNUNG: Durchschnittlicher Tagesgang (0-23 Uhr)
    # -------------------------------------------------------------------------
    # Gruppieren nach Stunde des Tages (0, 1, ..., 23) und Mittelwert bilden
    model_daily_profile = model.groupby(model.index.hour).mean()
    epex_daily_profile = epex.groupby(epex.index.hour).mean()
    
    hours = model_daily_profile.index
    
    # -------------------------------------------------------------------------
    # PLOTTING
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Titel mit Durchschnittswerten
    fig.suptitle(f'Durchschnittlicher Tagesverlauf (2024)', fontsize=16, fontweight='bold')
    
    subtitle = (f'Ø Modell: {avg_model:.2f} €/MWh  |  Ø EPEX: {avg_epex:.2f} €/MWh\n'
                f'Abweichung (Bias): {bias:+.2f} €/MWh')
    ax.set_title(subtitle, fontsize=11)
    
    # Linien plots
    ax.plot(hours, model_daily_profile.values, label=f"Modell (Ø {avg_model:.1f} €)", 
            color="#1f77b4", linewidth=2.5, marker='o', markersize=5)
    ax.plot(hours, epex_daily_profile.values, label=f"EPEX Spot (Ø {avg_epex:.1f} €)", 
            color="#ff7f0e", linewidth=2.5, marker='o', markersize=5)
    
    # Differenzfläche füllen
    ax.fill_between(hours, model_daily_profile.values, epex_daily_profile.values, 
                    color='gray', alpha=0.15, label='Differenz')
    
    # Achsen-Beschriftung
    ax.set_xlabel("Stunde des Tages", fontsize=12)
    ax.set_ylabel("Durchschnittspreis [€/MWh]", fontsize=12)
    ax.set_xticks(hours)  # Zeige jede Stunde auf der x-Achse
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45)
    ax.legend(loc="upper left", frameon=True, fontsize=11)
    
    # Skala anpassen (0 bis 150 €/MWh)
    ax.set_ylim(0, 150)

    # Gitter
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Speichern
    output_path = output_dir / "Vergleich_Tagesprofil_2024.png"
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"\nGrafik gespeichert unter: {output_path}")
    
    plt.show()


def run_single_scenario(scenario_id, cfg, script_dir, output_dir):
    """Führt ein einzelnes Szenario aus."""
    # WICHTIG: Resources aus Config holen
    data_dir = config.RESOURCES_DIR
    
    print(f"\nSzenario '{scenario_id}' wird geladen...")
    
    zone_names = cfg['zones']
    
    # Basis-Szenario-ID für Geodaten (ohne Jahr)
    base_scenario = scenario_id.rsplit('_', 1)[0]  # z.B. "z4_insel_2024" -> "z4_insel"
    if base_scenario.endswith('_2024') or base_scenario.endswith('_2037') or base_scenario.endswith('_2045'):
        base_scenario = base_scenario.rsplit('_', 1)[0]
    
    gdf = geodata.create_germany_zones(base_scenario, zone_names)
    
    # --- Differenz-Szenario ---
    if '_diff_' in scenario_id:
        print("Lade Daten für Differenz-Analyse...")
        year = cfg.get('year', 2024)
        base_type = scenario_id.split('_diff_')[0]  # z.B. "z4" oder "ns"
        
        # INSEL-Daten
        insel_id = f'{base_type}_insel_{year}'
        cfg_insel = config.SCENARIOS.get(insel_id)
        if not cfg_insel:
            print(f"FEHLER: Szenario {insel_id} nicht gefunden!")
            return
            
        excel_insel = data_loader.find_scenario_excel(data_dir, cfg_insel['file_keyword'])
        if not excel_insel:
            print(f"FEHLER: Excel für {insel_id} nicht gefunden!")
            return
        
        merit_orders = data_loader.load_merit_orders(excel_insel, zone_names)
        res_loads_insel, _ = data_loader.load_timeseries(excel_insel, cfg_insel['sheet'], zone_names)
        
        hourly_prices_insel = visualization.calculate_hourly_prices(
            res_loads_insel, merit_orders, zone_names, direct_prices=None
        )
        
        # COUPLED-Daten
        coupled_id = f'{base_type}_coupled_{year}'
        cfg_coupled = config.SCENARIOS.get(coupled_id)
        excel_coupled = data_loader.find_scenario_excel(data_dir, cfg_coupled['file_keyword'])
        
        res_loads_coupled, direct_prices_coupled = data_loader.load_timeseries(
            excel_coupled, cfg_coupled['sheet'], zone_names
        )
        
        if not direct_prices_coupled.empty:
            hourly_prices_coupled = visualization.calculate_hourly_prices(
                res_loads_coupled, merit_orders, zone_names, direct_prices=direct_prices_coupled
            )
        else:
            hourly_prices_coupled = visualization.calculate_hourly_prices(
                res_loads_coupled, merit_orders, zone_names, direct_prices=None
            )
        
        hourly_prices = hourly_prices_coupled - hourly_prices_insel
        print(f"Preisdifferenz berechnet für {len(hourly_prices)} Stunden")
    
    # --- Einzelnes Szenario ---
    else:
        excel_path = data_loader.find_scenario_excel(data_dir, cfg['file_keyword'])
        if not excel_path:
            print(f"FEHLER: Keine Datei für Szenario '{scenario_id}' gefunden!")
            return
        
        print(f"Lade Daten aus: {excel_path.name}")
        merit_orders = data_loader.load_merit_orders(excel_path, zone_names)
        res_loads, direct_prices = data_loader.load_timeseries(excel_path, cfg['sheet'], zone_names)
        
        if res_loads.empty and direct_prices.empty:
            print("FEHLER: Keine Zeitreihen-Daten geladen.")
            return
        
        is_coupled = 'coupled' in scenario_id.lower()
        
        if is_coupled and not direct_prices.empty:
            hourly_prices = visualization.calculate_hourly_prices(
                res_loads, merit_orders, zone_names, direct_prices=direct_prices
            )
        else:
            hourly_prices = visualization.calculate_hourly_prices(
                res_loads, merit_orders, zone_names, direct_prices=None
            )
    
    if hourly_prices.empty or hourly_prices.isna().all().all():
        print("FEHLER: Keine gültigen Preisdaten!")
        return
    
    gdf_list, monthly_profiles = visualization.create_animation_frames(gdf, hourly_prices)
    
    if not gdf_list:
        print("FEHLER: Keine Animations-Frames erstellt!")
        return
    
    visualization.run_visualization(gdf_list, monthly_profiles, zone_names, scenario_id, script_dir)


def run_multi_year_scenario(multi_id, script_dir, output_dir):
    """
    Lädt Daten für alle Jahre (2024, 2037, 2045) für einen Basis-Typ
    und visualisiert sie gemeinsam.
    multi_id format: 'multi_base_scenario' (z.B. 'multi_z4_insel')
    """
    base_type_raw = multi_id.replace("multi_", "") # z.B. z4_insel
    
    print(f"\n" + "="*60)
    print(f"MULTI-YEAR VERGLEICH: {base_type_raw.upper()}")
    print("="*60)
    
    data_packages = {}
    
    # Wir iterieren durch die fest definierten Jahre
    for year in config.AVAILABLE_YEARS:
        # Rekonstruiere die echte Scenario-ID
        scenario_id = f"{base_type_raw}_{year}"
        
        # Prüfen ob Szenario existiert
        if scenario_id not in config.SCENARIOS:
            print(f"WARNUNG: Szenario {scenario_id} nicht in Config gefunden. Überspringe.")
            continue
            
        cfg = config.SCENARIOS[scenario_id]
        print(f"\n--- Lade Jahr {year} ---")
        
        # === IDENTISCHE LOGIK WIE Single Scenario (Kopiert & Angepasst) ===
        zone_names = cfg['zones']
        data_dir = script_dir / "resources"
        
        # Geodaten (abhängig vom Jahr, weil Zonen gleich bleiben, aber um sicher zu sein)
        gdf = geodata.create_germany_zones(base_type_raw, zone_names)
        
        # Unterscheidung Diff vs Normal
        if '_diff_' in scenario_id:
            # Differenz berechnen
            sub_base = base_type_raw.replace("_diff", "") # z4 oder ns
            
            # 1. Insel
            id_insel = f'{sub_base}_insel_{year}'
            cfg_insel = config.SCENARIOS.get(id_insel)
            exc_insel = data_loader.find_scenario_excel(data_dir, cfg_insel['file_keyword'])
            mo_insel = data_loader.load_merit_orders(exc_insel, zone_names)
            load_insel, _ = data_loader.load_timeseries(exc_insel, cfg_insel['sheet'], zone_names)
            p_insel = visualization.calculate_hourly_prices(load_insel, mo_insel, zone_names, None)
            
            # 2. Coupled
            id_coup = f'{sub_base}_coupled_{year}'
            cfg_coup = config.SCENARIOS.get(id_coup)
            exc_coup = data_loader.find_scenario_excel(data_dir, cfg_coup['file_keyword'])
            load_coup, dp_coup = data_loader.load_timeseries(exc_coup, cfg_coup['sheet'], zone_names)
            
            # Check direct prices
            dp_arg = dp_coup if not dp_coup.empty else None
            p_coup = visualization.calculate_hourly_prices(load_coup, mo_insel, zone_names, dp_arg)
            
            hourly_prices = p_coup - p_insel
            
        else:
            # Normales Szenario
            excel_path = data_loader.find_scenario_excel(data_dir, cfg['file_keyword'])
            if not excel_path: continue
            
            merit_orders = data_loader.load_merit_orders(excel_path, zone_names)
            res_loads, direct_prices = data_loader.load_timeseries(excel_path, cfg['sheet'], zone_names)
            
            is_coupled = 'coupled' in scenario_id
            dp_arg = direct_prices if (is_coupled and not direct_prices.empty) else None
            
            hourly_prices = visualization.calculate_hourly_prices(
                res_loads, merit_orders, zone_names, direct_prices=dp_arg
            )

        if hourly_prices.empty:
            print(f"FEHLER: Keine Preise für {year} berechnet.")
            continue
            
        # Frames erstellen
        gdf_list, _ = visualization.create_animation_frames(gdf, hourly_prices)
        
        if gdf_list:
            data_packages[year] = gdf_list
            
    # Visualisierung starten, wenn Daten vorhanden
    if data_packages:
        visualization.run_multi_year_visualization(data_packages, base_type_raw, script_dir)
    else:
        print("Keine Daten geladen. Abbruch.")
        gui.show_error("Fehler", "Konnte keine Daten für den Vergleich laden.")


def main():
    """Hauptfunktion - Einstiegspunkt des Programms."""
    # WICHTIG: Pfade aus Config nutzen
    script_dir = config.APP_DIR
    output_dir = config.OUTPUT_DIR / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    scenario_ids = list(config.SCENARIOS.keys())
    
    # Dialog für Szenario-Auswahl
    while True:
        selected_id = gui.scenario_selection(scenario_ids)
        if selected_id is None:
            print("Programm beendet.")
            break
        
        # Fall 1: EPEX
        if selected_id == 'epex_comparison_2024':
            run_epex_comparison(script_dir, output_dir)
            continue
            
        # Fall 2: NEU - Multi-Year
        if selected_id.startswith('multi_'):
            run_multi_year_scenario(selected_id, script_dir, output_dir)
            continue
        
        # Fall 3: Single Scenario
        cfg = config.SCENARIOS[selected_id]
        run_single_scenario(selected_id, cfg, script_dir, output_dir)


if __name__ == "__main__":
    main()