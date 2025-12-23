import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import messagebox
from tkcalendar import Calendar
from datetime import datetime, date

# --- 1. DATEN LADEN ---

# Pfad zur Kraftwerksliste
kw_file_path = 'Projekt/Datensätze/Kraftwerksliste_Regelzonen(Kraftwerksliste_Miri).csv'
# Pfad zum SMARD-Lastgang für die 50Hertz-Zone
lastgang_file_path = 'Projekt/Datensätze/Realisierter_Stromverbrauch_202401010000_202501010000_Viertelstunde.csv'

# Kraftwerksliste einlesen
try:
    df_kw = pd.read_csv(kw_file_path, sep=';', encoding='latin1', decimal=',')
except FileNotFoundError:
    print(f"Fehler: Die Kraftwerksliste wurde nicht unter '{kw_file_path}' gefunden.")
    exit()

# Lastgangdaten einlesen
try:
    df_last = pd.read_csv(lastgang_file_path, sep=';', decimal=',', thousands='.')
    # Spalten umbenennen für einfacheren Zugriff
    df_last.rename(columns={
        'Datum von': 'Zeitstempel',
        'Netzlast [MWh] Originalauflösungen': 'Last [MWh]'
    }, inplace=True)
    # Zeitstempel in Datumsformat umwandeln und als Index setzen
    df_last['Zeitstempel'] = pd.to_datetime(df_last['Zeitstempel'], format='%d.%m.%Y %H:%M')
    df_last.set_index('Zeitstempel', inplace=True)
    # Umrechnung von MWh pro 15min in durchschnittliche Leistung in MW (Wert * 4)
    df_last['Last [MW]'] = df_last['Last [MWh]'] * 4
except FileNotFoundError:
    print(f"Fehler: Der Lastgang wurde nicht unter '{lastgang_file_path}' gefunden.")
    exit()


# --- 2. MERIT-ORDER ERSTELLEN ---

df_kw.columns = df_kw.columns.str.strip()
unb_col = 'ÜNB'
merit_order_col = 'Teil der Merit-Order?'
grenzkosten_col = 'Grenzkosten [EUR/MWHel]'
leistung_col = 'Netto-Nennleistung\n(elektrische Wirkleistung) [MW]'
energietraeger_col = 'Auswertung Energieträger'

df_filtered = df_kw[(df_kw[unb_col] == '50Hertz') & (df_kw[merit_order_col] == 'Ja')].copy()
df_filtered[grenzkosten_col] = pd.to_numeric(df_filtered[grenzkosten_col], errors='coerce')
df_filtered[leistung_col] = pd.to_numeric(df_filtered[leistung_col], errors='coerce')
df_filtered.dropna(subset=[grenzkosten_col, leistung_col], inplace=True)
df_sorted = df_filtered.sort_values(by=grenzkosten_col)
df_sorted['Kumulierte Leistung [MW]'] = df_sorted[leistung_col].cumsum()


# --- 3. PREISERMITTLUNG UND GRAFISCHE DARSTELLUNG (GUI-BASIERT) ---

def analyze_and_plot_for_date(selected_date):
    """
    Diese Funktion führt die Analyse für ein ausgewähltes Datum durch
    und erstellt die grafische Darstellung.
    """
    tag = selected_date

    # Lastdaten für den gewählten Tag filtern
    last_am_tag = df_last[df_last.index.date == tag]

    if last_am_tag.empty:
        messagebox.showinfo("Keine Daten", f"Für den {tag.strftime('%d.%m.%Y')} wurden keine Lastdaten gefunden.")
        return

    # Spitzenlast (maximale Last) an diesem Tag ermitteln
    spitzenlast_mw = last_am_tag['Last [MW]'].max()

    # Finde das preissetzende Kraftwerk für die Spitzenlast
    preissetzendes_kw = df_sorted[df_sorted['Kumulierte Leistung [MW]'] >= spitzenlast_mw]

    if preissetzendes_kw.empty:
        strompreis = df_sorted[grenzkosten_col].max()
        print(f"\nWarnung: Die Spitzenlast von {spitzenlast_mw:.2f} MW übersteigt die verfügbare Gesamtleistung.")
    else:
        strompreis = preissetzendes_kw.iloc[0][grenzkosten_col]

    print("-" * 50)
    print(f"Analyse für den {tag.strftime('%d.%m.%Y')}:")
    print(f"Spitzenlast an diesem Tag: {spitzenlast_mw:.2f} MW")
    print(f"Resultierender Spitzen-Strompreis: {strompreis:.2f} EUR/MWh")
    print("-" * 50)

    # --- Grafische Darstellung ---
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(15, 8))

    farben = {
        'Abfall': 'saddlebrown', 'Braunkohle': 'black', 'Erdgas': 'skyblue',
        'Mineralölprodukte': 'orange', 'Steinkohle': 'dimgray', 'Wärme': 'magenta',
        'Sonstige Energieträger (nicht erneuerbar)': 'purple', 'Sonstige': 'lightgrey'
    }

    vorherige_kumulierte_leistung = 0
    labels_hinzugefuegt = set()

    for index, row in df_sorted.iterrows():
        energietraeger = row[energietraeger_col]
        grenzkosten = row[grenzkosten_col]
        leistung = row[leistung_col]
        if leistung <= 0: continue
        farbe = farben.get(energietraeger, 'grey')
        label = energietraeger if energietraeger not in labels_hinzugefuegt else None
        ax.bar(x=vorherige_kumulierte_leistung, height=grenzkosten, width=leistung,
               color=farbe, label=label, align='edge')
        if label: labels_hinzugefuegt.add(energietraeger)
        vorherige_kumulierte_leistung += leistung

    ax.axvline(x=spitzenlast_mw, color='red', linestyle='--', linewidth=2, label=f'Spitzenlast ({spitzenlast_mw:.0f} MW)')
    ax.axhline(y=strompreis, color='red', linestyle='--', linewidth=2, xmax=spitzenlast_mw / ax.get_xlim()[1])

    ax.set_title(f'Merit-Order und Preisfindung für den {tag.strftime("%d.%m.%Y")}', fontsize=18, fontweight='bold')
    ax.set_xlabel('Kumulierte Leistung [MW]', fontsize=12)
    ax.set_ylabel('Grenzkosten [EUR/MWh]', fontsize=12)
    ax.set_ylim(bottom=0)
    ax.legend(title='Legende')
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

def on_date_selected():
    """Wird aufgerufen, wenn der Benutzer auf den Button klickt."""
    # Rufe das Datum als datetime.date-Objekt ab.
    selected_date = cal.selection_get()
    
    # Manuelle Überprüfung, ob das Datum im Jahr 2024 liegt.
    if selected_date and selected_date.year == 2024:
        analyze_and_plot_for_date(selected_date)
    else:
        messagebox.showwarning("Ungültiges Datum", "Bitte wählen Sie ein Datum im Jahr 2024 aus.")

# --- 4. GUI ERSTELLEN UND STARTEN ---
root = tk.Tk()
root.title("Datumsauswahl für Merit-Order")

# Kalender-Widget erstellen. Die Größe wird über die Schriftart angepasst.
# Die Datumseinschränkung (mindate/maxdate) wird entfernt, um das Auswahlproblem zu beheben.
cal = Calendar(root, selectmode='day', year=2024, month=1, day=1,
               font="Arial 14")
cal.pack(pady=20, padx=20)

# Button zum Bestätigen der Auswahl
select_button = tk.Button(root, text="Analyse für ausgewähltes Datum starten", command=on_date_selected)
select_button.pack(pady=10)

# Start der GUI-Schleife
root.mainloop()
