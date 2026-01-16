from pathlib import Path

from . import gui, config, data_loader, geodata, visualization

def run_single_scenario(scenario_id, cfg, script_dir, output_dir):
    """Führt ein einzelnes Szenario aus."""
    print(f"\nSzenario '{scenario_id}' wird geladen...")
    
    zone_names = cfg['zones']
    gdf = geodata.create_germany_zones(scenario_id, zone_names)
    
    # GEÄNDERT: Daten liegen jetzt im resources-Ordner
    data_dir = script_dir / "resources"
    
    # --- Differenz-Szenario ---
    if scenario_id.endswith('_diff'):
        print("Lade Daten für Differenz-Analyse...")
        base_scenario = scenario_id.replace('_diff', '')
        
        # INSEL-Daten
        cfg_insel = config.SCENARIOS[f"{base_scenario}_insel"]
        excel_insel = data_loader.find_scenario_excel(data_dir, cfg_insel['file_keyword'])
        if not excel_insel:
            print(f"FEHLER: Excel für {base_scenario}_insel nicht gefunden!")
            return
        
        merit_orders = data_loader.load_merit_orders(excel_insel, zone_names)
        res_loads_insel, _ = data_loader.load_timeseries(excel_insel, cfg_insel['sheet'], zone_names)
        
        if res_loads_insel.empty:
            print("FEHLER: Keine INSEL-Zeitreihen geladen!")
            return
        
        hourly_prices_insel = visualization.calculate_hourly_prices(
            res_loads_insel, merit_orders, zone_names, direct_prices=None
        )
        
        # COUPLED-Daten
        cfg_coupled = config.SCENARIOS[f"{base_scenario}_coupled"]
        excel_coupled = data_loader.find_scenario_excel(data_dir, cfg_coupled['file_keyword'])
        if not excel_coupled:
            print(f"FEHLER: Excel für {base_scenario}_coupled nicht gefunden!")
            return
        
        res_loads_coupled, direct_prices_coupled = data_loader.load_timeseries(
            excel_coupled, cfg_coupled['sheet'], zone_names
        )
        
        # Für COUPLED: Verwende direkte Preise wenn vorhanden
        if not direct_prices_coupled.empty:
            hourly_prices_coupled = visualization.calculate_hourly_prices(
                res_loads_coupled, merit_orders, zone_names, direct_prices=direct_prices_coupled
            )
        else:
            hourly_prices_coupled = visualization.calculate_hourly_prices(
                res_loads_coupled, merit_orders, zone_names, direct_prices=None
            )
        
        # Differenz berechnen
        hourly_prices = hourly_prices_coupled - hourly_prices_insel
        print(f"Preisdifferenz berechnet für {len(hourly_prices)} Stunden")
    
    # --- Einzelnes Szenario (INSEL oder COUPLED) ---
    else:
        excel_path = data_loader.find_scenario_excel(data_dir, cfg['file_keyword'])
        if not excel_path:
            print(f"FEHLER: Keine Datei für Szenario '{scenario_id}' gefunden!")
            return
        
        print(f"Lade Daten aus: {excel_path.name}")
        merit_orders = data_loader.load_merit_orders(excel_path, zone_names)
        res_loads, direct_prices = data_loader.load_timeseries(excel_path, cfg['sheet'], zone_names)
        
        if res_loads.empty and direct_prices.empty:
            print("FEHLER: Es konnten keine Zeitreihen-Daten geladen werden.")
            return
        
        # Prüfe ob COUPLED-Szenario mit direkten Preisen
        is_coupled = 'coupled' in scenario_id.lower()
        
        if is_coupled and not direct_prices.empty:
            print("Verwende direkte Preise aus COUPLED-Simulation...")
            hourly_prices = visualization.calculate_hourly_prices(
                res_loads, merit_orders, zone_names, direct_prices=direct_prices
            )
        else:
            print("Berechne Preise über Merit-Order-Lookup...")
            hourly_prices = visualization.calculate_hourly_prices(
                res_loads, merit_orders, zone_names, direct_prices=None
            )
    
    if hourly_prices.empty or hourly_prices.isna().all().all():
        print("FEHLER: Keine gültigen Preisdaten berechnet!")
        return
    
    gdf_list, monthly_profiles = visualization.create_animation_frames(gdf, hourly_prices)
    
    if not gdf_list:
        print("FEHLER: Keine Animations-Frames erstellt!")
        return
    
    visualization.run_visualization(gdf_list, monthly_profiles, zone_names, scenario_id, script_dir)

def main():
    script_dir = Path(__file__).parent
    output_dir = script_dir.parent.parent / "output" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    scenario_ids = list(config.SCENARIOS.keys())
    
    while True:
        selected_id = gui.scenario_selection(scenario_ids)
        if selected_id is None:
            print("Programm beendet.")
            break
        
        cfg = config.SCENARIOS[selected_id]
        run_single_scenario(selected_id, cfg, script_dir, output_dir)

if __name__ == "__main__":
    main()