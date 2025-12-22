import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

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


# --- 3. BENUTZEREINGABE UND PREISERMITTLUNG FÜR EINEN TAG ---

while True:
    try:
        datum_str = input("Bitte geben Sie einen Tag ein (Format: YYYY-MM-DD): ")
        tag = pd.to_datetime(datum_str).date()
        
        # Lastdaten für den gewählten Tag filtern
        last_am_tag = df_last[df_last.index.date == tag]
        
        if last_am_tag.empty:
            print(f"Für den {tag.strftime('%d.%m.%Y')} wurden keine Lastdaten gefunden. Bitte versuchen Sie es erneut.")
            continue

        # Spitzenlast (maximale Last) an diesem Tag ermitteln
        spitzenlast_mw = last_am_tag['Last [MW]'].max()
        break
    except ValueError:
        print("Ungültiges Datumsformat. Bitte verwenden Sie 'YYYY-MM-DD'.")

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


# --- 4. GRAFISCHE DARSTELLUNG ---

plt.style.use('seaborn-v0_8-whitegrid')
fig, ax = plt.subplots(figsize=(15, 8))

# Definition der Farben für die verschiedenen Energieträger
# Sie können diese Farben nach Belieben anpassen
farben = {
    'Abfall': 'saddlebrown',
    'Braunkohle': 'black',
    'Erdgas': 'skyblue',
    'Mineralölprodukte': 'orange',
    'Steinkohle': 'dimgray',
    'Wärme': 'magenta',
    'Sonstige Energieträger (nicht erneuerbar)': 'purple',
    'Sonstige': 'lightgrey'
}

# Vorbereitung für das Plotten
vorherige_kumulierte_leistung = 0
labels_hinzugefuegt = set()

# Zeichnen der Merit-Order als Balkendiagramm
for index, row in df_sorted.iterrows():
    energietraeger = row[energietraeger_col]
    grenzkosten = row[grenzkosten_col]
    leistung = row[leistung_col]  # Individuelle Leistung des Kraftwerks
    
    # Überspringe Kraftwerke ohne Leistung, um Fehler zu vermeiden
    if leistung <= 0:
        continue

    farbe = farben.get(energietraeger, 'grey')  # Standardfarbe
    
    label = energietraeger if energietraeger not in labels_hinzugefuegt else None
    
    # Zeichne einen Balken für das Kraftwerk
    ax.bar(x=vorherige_kumulierte_leistung,
           height=grenzkosten,
           width=leistung,
           color=farbe,
           label=label,
           align='edge')  # 'edge' richtet den Balken an der linken Kante aus

    if label:
        labels_hinzugefuegt.add(energietraeger)
        
    # Aktualisiere die kumulierte Leistung für die Position des nächsten Balkens
    vorherige_kumulierte_leistung += leistung

# NEU: Spitzenlast und Preis einzeichnen
ax.axvline(x=spitzenlast_mw, color='red', linestyle='--', linewidth=2, label=f'Spitzenlast ({spitzenlast_mw:.0f} MW)')
ax.axhline(y=strompreis, color='red', linestyle='--', linewidth=2, xmax=spitzenlast_mw / ax.get_xlim()[1])

# Titel und Achsenbeschriftungen
ax.set_title(f'Merit-Order und Preisfindung für den {tag.strftime("%d.%m.%Y")}', fontsize=18, fontweight='bold')
ax.set_xlabel('Kumulierte Leistung [MW]', fontsize=12)
ax.set_ylabel('Grenzkosten [EUR/MWh]', fontsize=12)

# Y-Achse bei 0 beginnen lassen
ax.set_ylim(bottom=0)

# Legende hinzufügen
ax.legend(title='Legende')

# Gitternetz und Layout
ax.grid(True, which='both', linestyle='--', linewidth=0.5)
plt.tight_layout()

# Anzeigen der Grafik
plt.show()
