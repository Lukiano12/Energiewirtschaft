from pathlib import Path
import pandas as pd
import numpy as np
import glob
import os
from . import config

def find_scenario_excel(directory, keyword):
    """
    Findet die Excel-Datei, die den Keyword enthält.
    """
    parts = keyword.split('_')
    all_xlsx = glob.glob(str(directory / "**" / "*.xlsx"), recursive=True)
    
    matching = []
    for f in all_xlsx:
        fname_lower = Path(f).name.lower()
        if all(part.lower() in fname_lower for part in parts):
            matching.append(f)
    
    if not matching:
        print(f"WARNUNG: Keine Datei mit Keyword '{keyword}' gefunden.")
        return None
    
    result = Path(max(matching, key=os.path.getmtime))
    print(f"  Gefunden: {result.name}")
    return result


def load_epex_prices(epex_path: Path) -> pd.Series:
    """
    Lädt EPEX-Spotpreise aus SMARD-Export.
    """
    print(f"Lade EPEX-Preise aus: {epex_path}")
    
    if not epex_path.exists():
        print(f"  WARNUNG: Datei existiert nicht: {epex_path}")
        return None
    
    # 1. Datei ohne Header lesen um Header-Zeile zu finden
    try:
        df_temp = pd.read_excel(epex_path, header=None)
    except Exception as e:
        print(f"  FEHLER beim Lesen der Datei: {e}")
        return None
    
    header_row = None
    
    # Suche Header-Zeile
    for i, row in df_temp.iterrows():
        row_str = " ".join(row.astype(str).tolist()).lower()
        
        if "originalauflösung" in row_str or "version" in row_str:
            continue
            
        # Wir suchen Zeile mit Datum
        if 'datum' in row_str:
            # Prio 1: Mit Währung
            if '€/mwh' in row_str or 'eur/mwh' in row_str:
                header_row = i
                break
            # Prio 2: Datum von / Datum bis
            elif 'datum von' in row_str:
                header_row = i
                # Wir breaken hier nicht sofort, falls noch eine bessere Zeile kommt,
                # aber speichern es als Kandidat.
                
    if header_row is None:
        print("  WARNUNG: Konnte Header-Zeile nicht finden. Versuche Zeile 0.")
        header_row = 0
    else:
        print(f"  Header in Zeile {header_row + 1} gefunden.")

    # 2. Richtig einlesen
    try:
        df = pd.read_excel(epex_path, header=header_row)
    except Exception as e: 
         print(f"  FEHLER beim Laden mit Header: {e}")
         return None

    # --- DateTime-Index Logik verbessern ---
    # Fall A: Separate Spalten "Datum" und "Uhrzeit" (oder "Anfang")
    date_col = next((c for c in df.columns if "datum" in str(c).lower() and "von" not in str(c).lower() and "bis" not in str(c).lower()), None)
    time_col = next((c for c in df.columns if "uhrzeit" in str(c).lower() or "anfang" in str(c).lower()), None)
    
    # Fall B: Kombinierte Spalte oder "Datum von" (enthält oft Datum+Zeit)
    date_from_col = next((c for c in df.columns if "datum von" in str(c).lower()), None)
    
    df["datetime"] = pd.NaT

    if date_col and time_col:
        # Klassisches Format: Datum | Uhrzeit
        try:
            dt_str = df[date_col].astype(str) + " " + df[time_col].astype(str)
            df["datetime"] = pd.to_datetime(dt_str, format="%d.%m.%Y %H:%M", errors="coerce")
            if df["datetime"].isna().all():
                 df["datetime"] = pd.to_datetime(dt_str, errors="coerce")
        except:
            pass
            
    elif date_from_col:
        # Format: Datum von (enthält z.B. "01.01.2024 00:00")
        try:
            # Versuche direktes Parsing
            df["datetime"] = pd.to_datetime(df[date_from_col], format="%d.%m.%Y %H:%M", errors="coerce")
            
            # Falls fehlgeschlagen (vielleicht ist das Format anders oder enthält nur Datum?),
            # versuche generisch
            if df["datetime"].isna().sum() > len(df) * 0.5: # Wenn mehr als 50% fehlen
                 df["datetime"] = pd.to_datetime(df[date_from_col], errors="coerce")
        except:
            pass

    # Prüfen ob wir valide Daten haben
    df = df.dropna(subset=["datetime"])
    
    if df.empty:
        print(f"  WARNUNG: Konnte Datum/Zeit nicht parsen. Spalten: {df.columns.tolist()}")
        return None
        
    df = df.set_index("datetime")
    
    # Preis-Spalte finden
    price_cols = [c for c in df.columns if "deutschland" in str(c).lower() and ("€" in str(c) or "eur" in str(c).lower())]
    
    if not price_cols:
        price_cols = [c for c in df.columns if "€/mwh" in str(c).lower() or "eur/mwh" in str(c).lower()]
    
    if not price_cols:
        print(f"  Verfügbare Spalten: {df.columns.tolist()}")
        raise ValueError("Keine EPEX-Preis-Spalte gefunden")
    
    price_col = price_cols[0]
    
    # Konvertiere Preise
    prices = df[price_col].replace("-", np.nan)
    if prices.dtype == object:
        prices = prices.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        
    prices = pd.to_numeric(prices, errors="coerce")
    prices.name = "EPEX"
    
    # Resample zu stündlich
    prices = prices.resample('h').mean()
    
    print(f"  -> {len(prices)} Stunden geladen")
    return prices


def load_merit_orders(excel_path, zone_names):
    """Lädt die Merit-Order-Stacks aus der Excel-Datei."""
    merit_orders = {}
    print("Lade Merit-Order-Stacks...")
    try:
        xl = pd.ExcelFile(excel_path)
    except Exception as e:
        print(f"  FEHLER beim Öffnen der Excel-Datei: {e}")
        return {}
    
    zone_sheet_map = {
        'north': ['nord'],
        'south': ['sued', 'süd'],
        'de': ['de', 'deutschland', 'germany'],
        '50hertz': ['50hertz', '50hz'],
        'tennet': ['tennet'],
        'amprion': ['amprion'],
        'transnetbw': ['transnetbw', 'enbw']
    }
    
    used_sheets = set()
    
    for zone in zone_names:
        sheet_name = None
        zone_lower = zone.lower()
        possible_names = zone_sheet_map.get(zone_lower, [zone_lower])
        
        for sheet in xl.sheet_names:
            if sheet in used_sheets:
                continue
                
            sheet_lower = sheet.lower()
            is_plant_sheet = any(x in sheet_lower for x in ['stack', 'plant', 'cap', 'merit'])
            if not is_plant_sheet:
                continue
            
            for pn in possible_names:
                if f'_{pn}' in sheet_lower or f'{pn}_' in sheet_lower or sheet_lower.endswith(pn):
                    sheet_name = sheet
                    break
            
            if sheet_name:
                break
        
        if not sheet_name:
            # print(f"  WARNUNG: Kein Merit-Order-Sheet für Zone '{zone}' gefunden.")
            continue
        
        used_sheets.add(sheet_name)
            
        try:
            df = pd.read_excel(excel_path, sheet_name=sheet_name)
            df.columns = df.columns.astype(str).str.lower()
            
            cap_col = next((c for c in df.columns if 'cap' in c and 'cum' not in c), None)
            if not cap_col:
                cap_col = next((c for c in df.columns if 'mw' in c and 'cum' not in c), None)
            mc_col = next((c for c in df.columns if 'mc' in c or 'grenz' in c or 'cost' in c), None)
            
            if not cap_col or not mc_col:
                continue
            
            df = df[[cap_col, mc_col]].dropna()
            df = df.sort_values(by=mc_col)
            df['acum_mw'] = df[cap_col].cumsum()
            df['mc'] = df[mc_col]
            
            stack = df[['acum_mw', 'mc']].copy()
            start_row = pd.DataFrame({'acum_mw': [0], 'mc': [stack['mc'].iloc[0] if not stack.empty else 0]})
            stack = pd.concat([start_row, stack], ignore_index=True)
            
            merit_orders[zone] = stack
            print(f"  Zone '{zone}' geladen: {len(stack)} Einträge, max {stack['acum_mw'].max():.0f} MW")
            
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
    """
    print("Lade Zeitreihen...")
    
    try:
        ts_raw = pd.read_excel(excel_path, sheet_name=sheet_name)
        ts_raw.columns = ts_raw.columns.astype(str).str.lower()
    except Exception as e:
        print(f"  FEHLER: Sheet '{sheet_name}' konnte nicht geladen werden: {e}")
        return pd.DataFrame(), pd.DataFrame()

    time_col = find_col(ts_raw, ['time', 'date', 'zeit', 'timestamp'])
    if not time_col:
        time_col = ts_raw.columns[0]
    
    ts_raw[time_col] = pd.to_datetime(ts_raw[time_col], errors='coerce')
    ts_raw = ts_raw.dropna(subset=[time_col])
    ts_raw = ts_raw.set_index(time_col)
    
    zone_prefix_map = {
        'north': 'nord',
        'south': 'sued',
        'de': 'de'
    }
    
    res_loads = pd.DataFrame()
    direct_prices = pd.DataFrame()
    
    # --- Fall 1: "Langes" Format (INSEL) ---
    if 'zone' in ts_raw.columns:
        
        for zone in zone_names:
            if zone.lower() == 'north':
                search_names = ['nord']
            elif zone.lower() == 'south':
                search_names = ['sued', 'süd']
            else:
                search_names = [zone.lower()]
            
            zone_mask = ts_raw['zone'].astype(str).str.lower().isin(search_names)
            zone_df = ts_raw[zone_mask].copy()
            
            if zone_df.empty:
                continue
            
            load_col = find_col(zone_df, ['load_mw', 'load', 'last'])
            ee_col = find_col(zone_df, ['ee_used_mw', 'vre_mw', 'ee_'])
            konv_col = find_col(zone_df, ['konv_bedarf_mw', 'conv_demand', 'residual'])
            
            if konv_col:
                residual = zone_df[konv_col]
            elif load_col and ee_col:
                residual = zone_df[load_col] - zone_df[ee_col]
            elif load_col:
                residual = zone_df[load_col]
            else:
                continue
            
            residual = residual.groupby(residual.index).mean()
            res_loads[zone] = residual
            
            price_col = find_col(zone_df, ['price_eur_mwh', 'price', 'preis'])
            if price_col:
                prices = zone_df[price_col].groupby(zone_df.index).mean()
                direct_prices[zone] = prices
    
    # --- Fall 2: "Breites" Format (COUPLED) ---
    else:
        for zone in zone_names:
            prefix = zone_prefix_map.get(zone.lower(), zone.lower())
            
            price_col = find_col(ts_raw, [f'{prefix}_price_eur_mwh', f'{prefix}_price'])
            if price_col:
                direct_prices[zone] = ts_raw[price_col].values
            
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
    
    # Index wiederherstellen
    if not res_loads.empty and not isinstance(res_loads.index, pd.DatetimeIndex):
        valid_len = min(len(ts_raw.index), len(res_loads))
        res_loads.index = ts_raw.index[:valid_len]
        res_loads = res_loads.iloc[:valid_len]

    if not direct_prices.empty and not isinstance(direct_prices.index, pd.DatetimeIndex):
        valid_len = min(len(ts_raw.index), len(direct_prices))
        direct_prices.index = ts_raw.index[:valid_len]
        direct_prices = direct_prices.iloc[:valid_len]
    
    # Resample zu stündlichen Werten
    if not res_loads.empty:
        res_loads = res_loads.resample('h').mean()
    if not direct_prices.empty:
        direct_prices = direct_prices.resample('h').mean()
    
    total_hours = max(len(res_loads), len(direct_prices)) if not res_loads.empty or not direct_prices.empty else 0
    print(f"Zeitreihen geladen: {total_hours} Stunden")
    
    return res_loads, direct_prices