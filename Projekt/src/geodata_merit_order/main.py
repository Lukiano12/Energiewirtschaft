from pathlib import Path

from . import gui, config, data_loader, geodata, visualization

def run_epex_comparison(script_dir, output_dir):
    """
    Führt den EPEX-Vergleich aus: Modell 2024 vs. echte EPEX-Preise.
    Zeigt ein Liniendiagramm mit Statistiken.
    """
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    
    print("\n" + "="*70)
    print("EPEX-VERGLEICH: MODELL 2024 vs. EPEX SPOT")
    print("="*70)
    
    data_dir = script_dir / "resources"
    
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
        print(f"Erwartet: {config.EPEX_PRICE_FILE}")
        print("\nBitte lade von SMARD herunter:")
        print("  https://www.smard.de/home/downloadcenter")
        print("  -> Großhandelspreise -> Day-Ahead Auktion")
        print("  -> Deutschland/Luxemburg, 2024, Viertelstunde")
        gui.show_error("EPEX-Datei fehlt", 
                      f"Bitte EPEX-Preise herunterladen und hier speichern:\n\n{config.EPEX_PRICE_FILE}")
        return
    
    # 3) Gemeinsamer Index
    common_idx = model.index.intersection(epex.index)
    if len(common_idx) == 0:
        print("FEHLER: Keine gemeinsamen Zeitpunkte!")
        return
    
    model = model.loc[common_idx]
    epex = epex.loc[common_idx]
    
    print(f"\nVergleich über {len(common_idx)} Stunden")
    print(f"Zeitraum: {common_idx[0]} bis {common_idx[-1]}")
    
    # 4) Statistiken
    diff = model - epex
    mae = np.abs(diff).mean()
    rmse = np.sqrt((diff ** 2).mean())
    corr = model.corr(epex)
    bias = diff.mean()
    
    print(f"\n--- Statistiken ---")
    print(f"  MAE (mittlerer Fehler):     {mae:.2f} €/MWh")
    print(f"  RMSE:                       {rmse:.2f} €/MWh")
    print(f"  Korrelation:                {corr:.3f}")
    print(f"  Bias (Modell - EPEX):       {bias:+.2f} €/MWh")
    
    # 5) Plots erstellen
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle('Merit-Order Modell 2024 vs. EPEX Spot', fontsize=16, fontweight='bold')
    
    # Plot 1: Wochenmittel über Jahr
    model_weekly = model.resample("W").mean()
    epex_weekly = epex.resample("W").mean()
    
    ax = axes[0]
    ax.plot(model_weekly.index, model_weekly.values, 
            label="Modell (Merit-Order)", color="steelblue", linewidth=1.5)
    ax.plot(epex_weekly.index, epex_weekly.values, 
            label="EPEX Spot", color="darkorange", linewidth=1.5, alpha=0.8)
    ax.fill_between(model_weekly.index, model_weekly.values, epex_weekly.values,
                   alpha=0.2, color='gray', label='Differenz')
    ax.set_ylabel("Preis [€/MWh]")
    ax.set_title("Jahresverlauf (Wochenmittel)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    
    # Plot 2: Beispielwoche
    sample_start = "2024-01-15"
    sample_end = "2024-01-22"
    mask = (model.index >= sample_start) & (model.index < sample_end)
    
    ax = axes[1]
    ax.plot(model.index[mask], model.values[mask], 
            label="Modell", color="steelblue", linewidth=1)
    ax.plot(epex.index[mask], epex.values[mask], 
            label="EPEX", color="darkorange", linewidth=1, alpha=0.8)
    ax.set_ylabel("Preis [€/MWh]")
    ax.set_title(f"Beispielwoche: {sample_start} bis {sample_end}")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Scatter + Statistiken
    ax = axes[2]
    
    # Stichprobe für Scatter
    sample_size = min(3000, len(model))
    idx = np.random.choice(len(model), sample_size, replace=False)
    
    ax.scatter(epex.iloc[idx], model.iloc[idx], alpha=0.3, s=8, c="steelblue")
    
    # Diagonale
    lims = [max(0, min(epex.min(), model.min()) - 10), 
            min(300, max(epex.max(), model.max()) + 10)]
    ax.plot(lims, lims, "r--", linewidth=1.5, label="Perfekte Übereinstimmung")
    
    # Statistik-Box
    stats_text = (f"MAE = {mae:.1f} €/MWh\n"
                  f"RMSE = {rmse:.1f} €/MWh\n"
                  f"Korrelation = {corr:.2f}\n"
                  f"Bias = {bias:+.1f} €/MWh")
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    ax.set_xlabel("EPEX Spot [€/MWh]")
    ax.set_ylabel("Modell [€/MWh]")
    ax.set_title("Scatter-Plot: Modell vs. EPEX")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    
    plt.tight_layout()
    
    # Speichern
    output_path = output_dir / "Vergleich_Modell_vs_EPEX_2024.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot gespeichert: {output_path}")
    
    plt.show()
    
    # Zusätzlich: Dauerlinie
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    
    model_sorted = np.sort(model.values)[::-1]
    epex_sorted = np.sort(epex.values)[::-1]
    hours = np.arange(len(model_sorted))
    
    ax2.plot(hours, model_sorted, label="Modell", color="steelblue", linewidth=1.5)
    ax2.plot(hours, epex_sorted, label="EPEX", color="darkorange", linewidth=1.5, alpha=0.8)
    
    ax2.set_xlabel("Stunden (sortiert)")
    ax2.set_ylabel("Preis [€/MWh]")
    ax2.set_title("Preisdauerlinie 2024: Modell vs. EPEX")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(-20, 250)
    
    plt.tight_layout()
    
    duration_path = output_dir / "Preisdauerlinie_Modell_vs_EPEX_2024.png"
    plt.savefig(duration_path, dpi=150, bbox_inches="tight")
    print(f"Dauerlinie gespeichert: {duration_path}")
    
    plt.show()


def run_single_scenario(scenario_id, cfg, script_dir, output_dir):
    """Führt ein einzelnes Szenario aus."""
    print(f"\nSzenario '{scenario_id}' wird geladen...")
    
    zone_names = cfg['zones']
    
    # Basis-Szenario-ID für Geodaten (ohne Jahr)
    base_scenario = scenario_id.rsplit('_', 1)[0]  # z.B. "z4_insel_2024" -> "z4_insel"
    if base_scenario.endswith('_2024') or base_scenario.endswith('_2037') or base_scenario.endswith('_2045'):
        base_scenario = base_scenario.rsplit('_', 1)[0]
    
    gdf = geodata.create_germany_zones(base_scenario, zone_names)
    
    data_dir = script_dir / "resources"
    
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
        
        # Spezialfall: EPEX-Vergleich
        if selected_id == 'epex_comparison_2024':
            run_epex_comparison(script_dir, output_dir)
            continue
        
        cfg = config.SCENARIOS[selected_id]
        run_single_scenario(selected_id, cfg, script_dir, output_dir)


if __name__ == "__main__":
    main()