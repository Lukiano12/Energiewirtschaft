import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path

def find_scenario_excel(directory, keyword):
    """
    Findet die neueste Excel-Datei, die den Keyword enthält.
    Sucht auch in Unterordnern.
    """
    # Suche direkt im Verzeichnis
    files = glob.glob(str(directory / f"*{keyword}*.xlsx"), recursive=False)
    
    # Suche auch in Unterordnern
    if not files:
        files = glob.glob(str(directory / "**" / f"*{keyword}*.xlsx"), recursive=True)
    
    # Suche mit case-insensitive
    if not files:
        all_xlsx = glob.glob(str(directory / "**" / "*.xlsx"), recursive=True)
        files = [f for f in all_xlsx if keyword.lower() in f.lower()]
    
    if not files:
        print(f"WARNUNG: Keine Datei mit Keyword '{keyword}' gefunden.")
        print(f"  Gesucht in: {directory}")
        all_xlsx = glob.glob(str(directory / "**" / "*.xlsx"), recursive=True)
        if all_xlsx:
            print(f"  Gefundene Excel-Dateien:")
            for f in all_xlsx[:10]:
                print(f"    - {Path(f).name}")
        return None
    
    result = Path(max(files, key=os.path.getmtime))
    print(f"  Gefunden: {result.name}")
    return result

def load_merit_orders(excel_path, zone_names):
    """Lädt die Merit-Order-Stacks aus der Excel-Datei."""
    merit_orders = {}
    print("Lade Merit-Order-Stacks...")
    xl = pd.ExcelFile(excel_path)
    
    # Mapping für verschiedene Zonennamen in den Sheet-Namen
    # WICHTIG: Jede Zone hat ihr eigenes, eindeutiges Mapping
    zone_sheet_map = {
        'north': ['nord'],           # NUR 'nord', nicht 'n' (zu unspezifisch)
        'south': ['sued', 'süd'],    # NUR 'sued'/'süd', nicht 'south' oder 's'
        'de': ['de', 'deutschland', 'germany'],
        '50hertz': ['50hertz', '50hz'],
        'tennet': ['tennet'],
        'amprion': ['amprion'],
        'transnetbw': ['transnetbw', 'enbw']
    }
    
    # Bereits verwendete Sheets tracken, um Duplikate zu vermeiden
    used_sheets = set()
    
    for zone in zone_names:
        sheet_name = None
        zone_lower = zone.lower()
        possible_names = zone_sheet_map.get(zone_lower, [zone_lower])
        
        # Suche nach dem EXAKTEN Sheet für diese Zone
        for sheet in xl.sheet_names:
            if sheet in used_sheets:
                continue  # Sheet bereits verwendet
                
            sheet_lower = sheet.lower()
            
            # Prüfe ob es ein Kraftwerks-Sheet ist
            is_plant_sheet = any(x in sheet_lower for x in ['stack', 'plant', 'cap', 'merit'])
            if not is_plant_sheet:
                continue
            
            # Prüfe auf EXAKTE Übereinstimmung mit dem Zonennamen
            for pn in possible_names:
                # Suche nach "_ZONE" oder "ZONE_" im Sheet-Namen für exakte Zuordnung
                if f'_{pn}' in sheet_lower or f'{pn}_' in sheet_lower or sheet_lower.endswith(pn):
                    sheet_name = sheet
                    break
            
            if sheet_name:
                break
        
        if not sheet_name:
            print(f"  WARNUNG: Kein Merit-Order-Sheet für Zone '{zone}' gefunden.")
            print(f"    Gesucht nach: {possible_names}")
            print(f"    Verfügbare Sheets: {[s for s in xl.sheet_names if s not in used_sheets]}")
            continue
        
        # Sheet als verwendet markieren
        used_sheets.add(sheet_name)
            
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            df.columns = df.columns.astype(str).str.lower()
            
            # Finde Kapazitäts- und Grenzkostenspalten
            cap_col = next((c for c in df.columns if 'cap' in c and 'cum' not in c), None)
            if not cap_col:
                cap_col = next((c for c in df.columns if 'mw' in c and 'cum' not in c), None)
            mc_col = next((c for c in df.columns if 'mc' in c or 'grenz' in c or 'cost' in c), None)
            
            if not cap_col or not mc_col:
                print(f"  WARNUNG: Keine Kapazitäts-/Kostenspalten in '{sheet_name}'")
                print(f"    Spalten: {list(df.columns)}")
                continue
            
            df = df[[cap_col, mc_col]].dropna()
            df = df.sort_values(by=mc_col)
            df['acum_mw'] = df[cap_col].cumsum()
            df['mc'] = df[mc_col]
            
            stack = df[['acum_mw', 'mc']].copy()
            start_row = pd.DataFrame({'acum_mw': [0], 'mc': [stack['mc'].iloc[0] if not stack.empty else 0]})
            stack = pd.concat([start_row, stack], ignore_index=True)
            
            merit_orders[zone] = stack
            print(f"  Zone '{zone}' geladen aus Sheet '{sheet_name}': {len(stack)} Einträge, max {stack['acum_mw'].max():.0f} MW")
            
        except Exception as e:
            print(f"  FEHLER beim Laden von '{sheet_name}': {e}")
    
    return merit_orders

def find_col(df, keywords):
    """Hilfsfunktion: Findet die erste Spalte in df, deren Name einen der Keywords enthält."""
    for key in keywords:
        for col in df.columns:
            if key in col.lower():
                return col
    return None

def load_timeseries(excel_path, sheet_name, zone_names):
    """
    Lädt und verarbeitet Zeitreihendaten aus der angegebenen Excel-Datei.
    
    Gibt zurück:
        - res_loads: DataFrame mit Residuallast pro Zone (für Merit-Order-Berechnung)
        - direct_prices: DataFrame mit direkten Preisen (falls vorhanden in COUPLED-Sheets)
    """
    print("Lade Zeitreihen...")
    
    try:
        ts_raw = pd.read_excel(excel_path, sheet_name=sheet_name)
        ts_raw.columns = ts_raw.columns.astype(str).str.lower()
    except Exception as e:
        print(f"  FEHLER: Sheet '{sheet_name}' konnte nicht geladen werden: {e}")
        try:
            xl = pd.ExcelFile(excel_path)
            print(f"    Verfügbare Sheets: {xl.sheet_names}")
        except:
            pass
        return pd.DataFrame(), pd.DataFrame()

    # Finde Zeitspalte
    time_col = find_col(ts_raw, ['time', 'date', 'zeit', 'timestamp'])
    if not time_col:
        time_col = ts_raw.columns[0]
    
    ts_raw[time_col] = pd.to_datetime(ts_raw[time_col], errors='coerce')
    ts_raw = ts_raw.dropna(subset=[time_col])
    ts_raw = ts_raw.set_index(time_col)
    
    # Mapping von zone_names zu tatsächlichen Spaltenpräfixen
    zone_prefix_map = {
        'north': 'nord',
        'south': 'sued',
        'de': 'de'
    }
    
    res_loads = pd.DataFrame()
    direct_prices = pd.DataFrame()
    
    # --- Fall 1: "Langes" Format (INSEL - mit 'zone'-Spalte) ---
    if 'zone' in ts_raw.columns:
        print("  Format erkannt: INSEL (langes Format mit zone-Spalte)")
        
        for zone in zone_names:
            # Mapping für Zonennamen - EXAKT
            if zone.lower() == 'north':
                search_names = ['nord']
            elif zone.lower() == 'south':
                search_names = ['sued', 'süd']
            else:
                search_names = [zone.lower()]
            
            # Filtere Daten für diese Zone
            zone_mask = ts_raw['zone'].astype(str).str.lower().isin(search_names)
            zone_df = ts_raw[zone_mask].copy()
            
            if zone_df.empty:
                print(f"  WARNUNG: Keine Daten für Zone '{zone}' gefunden.")
                print(f"    Gesucht nach: {search_names}")
                print(f"    Verfügbare Zonen: {ts_raw['zone'].unique()}")
                continue
            
            # Finde Spalten für Residuallast-Berechnung
            load_col = find_col(zone_df, ['load_mw', 'load', 'last'])
            ee_col = find_col(zone_df, ['ee_used_mw', 'vre_mw', 'ee_'])
            konv_col = find_col(zone_df, ['konv_bedarf_mw', 'conv_demand', 'residual'])
            
            # Option 1: Direkt konv_bedarf_mw verwenden (falls vorhanden)
            if konv_col:
                residual = zone_df[konv_col]
                print(f"  Zone '{zone}': Verwende direkt '{konv_col}'")
            # Option 2: Berechne Last - EE
            elif load_col and ee_col:
                residual = zone_df[load_col] - zone_df[ee_col]
                print(f"  Zone '{zone}': Berechne Residuallast aus {load_col} - {ee_col}")
            elif load_col:
                residual = zone_df[load_col]
                print(f"  Zone '{zone}': Verwende nur Last (keine EE-Spalte)")
            else:
                print(f"  WARNUNG: Keine verwertbaren Spalten für Zone '{zone}'")
                print(f"    Verfügbare Spalten: {list(zone_df.columns)}")
                continue
            
            # Aggregiere falls mehrere Einträge pro Zeitstempel
            residual = residual.groupby(residual.index).mean()
            res_loads[zone] = residual
            
            # Prüfe auf direkte Preisspalte
            price_col = find_col(zone_df, ['price_eur_mwh', 'price', 'preis'])
            if price_col:
                prices = zone_df[price_col].groupby(zone_df.index).mean()
                direct_prices[zone] = prices
    
    # --- Fall 2: "Breites" Format (COUPLED - Spalten mit Zonen-Präfix) ---
    else:
        print("  Format erkannt: COUPLED (breites Format mit Zonen-Präfixen)")
        print(f"    Verfügbare Spalten: {list(ts_raw.columns)[:20]}...")
        
        for zone in zone_names:
            prefix = zone_prefix_map.get(zone.lower(), zone.lower())
            
            # Suche nach direkter Preisspalte (WICHTIG für COUPLED!)
            price_col = find_col(ts_raw, [f'{prefix}_price_eur_mwh', f'{prefix}_price'])
            
            if price_col:
                # COUPLED: Verwende direkt die berechneten Preise aus dem LP
                direct_prices[zone] = ts_raw[price_col].values
                print(f"  Zone '{zone}': Direkte Preisspalte '{price_col}' gefunden")
            
            # Berechne auch Residuallast für Fallback/Vergleich
            gen_conv_col = find_col(ts_raw, [f'{prefix}_gen_conv', f'{prefix}_conv'])
            import_col = find_col(ts_raw, [f'{prefix}_import'])
            export_col = find_col(ts_raw, [f'{prefix}_export'])
            
            if gen_conv_col:
                residual = ts_raw[gen_conv_col].copy()
                if import_col:
                    residual = residual + ts_raw[import_col]
                if export_col:
                    residual = residual - ts_raw[export_col]
                res_loads[zone] = residual.values
                print(f"  Zone '{zone}': Residuallast aus gen_conv berechnet")
    
    # Index wiederherstellen
    if not res_loads.empty and not isinstance(res_loads.index, pd.DatetimeIndex):
        res_loads.index = ts_raw.index[:len(res_loads)]
    if not direct_prices.empty and not isinstance(direct_prices.index, pd.DatetimeIndex):
        direct_prices.index = ts_raw.index[:len(direct_prices)]
    
    # Resample zu stündlichen Werten
    if not res_loads.empty:
        res_loads = res_loads.resample('h').mean()
    if not direct_prices.empty:
        direct_prices = direct_prices.resample('h').mean()
    
    total_hours = max(len(res_loads), len(direct_prices)) if not res_loads.empty or not direct_prices.empty else 0
    print(f"Zeitreihen geladen: {total_hours} Stunden")
    
    if not direct_prices.empty:
        print(f"  Direkte Preise verfügbar für: {list(direct_prices.columns)}")
    
    return res_loads, direct_prices


def load_timeseries_simple(excel_path, sheet_name, zone_names):
    """
    Vereinfachte Version für Abwärtskompatibilität.
    Gibt nur res_loads zurück.
    """
    res_loads, _ = load_timeseries(excel_path, sheet_name, zone_names)
    return res_loads