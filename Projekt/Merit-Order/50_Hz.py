
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Pfad zur CSV-Datei
file_path = 'Projekt/Datensätze/Kraftwerksliste_Regelzonen(Kraftwerksliste_Miri).csv'

# Daten mit Pandas einlesen.
# Wir verwenden 'latin1'-Kodierung wegen der Sonderzeichen und ';' als Trennzeichen.
# Das Dezimaltrennzeichen wird auf ',' gesetzt.
try:
    df = pd.read_csv(file_path, sep=';', encoding='latin1', decimal=',')
except FileNotFoundError:
    print(f"Fehler: Die Datei wurde nicht unter dem Pfad '{file_path}' gefunden.")
    print("Bitte stellen Sie sicher, dass der Pfad zur CSV-Datei korrekt ist.")
    exit()

# Entfernen von führenden/nachfolgenden Leerzeichen in den Spaltennamen
df.columns = df.columns.str.strip()

# Definition der Spaltennamen für den einfacheren Zugriff
unb_col = 'ÜNB'
merit_order_col = 'Teil der Merit-Order?'
grenzkosten_col = 'Grenzkosten [EUR/MWHel]'
leistung_col = 'Netto-Nennleistung\n(elektrische Wirkleistung) [MW]'
energietraeger_col = 'Auswertung Energieträger'

# Überprüfen, ob alle benötigten Spalten in der Datei vorhanden sind
required_cols = [unb_col, merit_order_col, grenzkosten_col, leistung_col, energietraeger_col]
if not all(col in df.columns for col in required_cols):
    print("Fehler: Nicht alle benötigten Spalten sind in der CSV-Datei vorhanden.")
    print(f"Benötigt werden: {required_cols}")
    print(f"Gefunden wurden: {df.columns.tolist()}")
    exit()

# 1. Filtern der Daten
# Nur Kraftwerke, die zur 50Hertz-Zone gehören und Teil der Merit-Order sind
df_filtered = df[(df[unb_col] == '50Hertz') & (df[merit_order_col] == 'Ja')].copy()

# 2. Datenbereinigung und -konvertierung
# Konvertiere die Kosten- und Leistungsspalten in numerische Werte.
# Fehlerhafte Werte (z.B. Text) werden zu NaN (Not a Number) und dann entfernt.
df_filtered[grenzkosten_col] = pd.to_numeric(df_filtered[grenzkosten_col], errors='coerce')
df_filtered[leistung_col] = pd.to_numeric(df_filtered[leistung_col], errors='coerce')
df_filtered.dropna(subset=[grenzkosten_col, leistung_col], inplace=True)

# 3. Sortieren nach Grenzkosten
# Die Kraftwerke werden aufsteigend nach ihren Grenzkosten sortiert.
df_sorted = df_filtered.sort_values(by=grenzkosten_col)

# 4. Kumulierte Leistung berechnen
# Dies ist die Summe der Leistung der Kraftwerke in der sortierten Reihenfolge.
df_sorted['Kumulierte Leistung [MW]'] = df_sorted[leistung_col].cumsum()

# Vorbereitung für das Plotten
# Erstellen von Stufen für die Treppenfunktion der Merit-Order
x_values = np.zeros(len(df_sorted) * 2)
y_values = np.zeros(len(df_sorted) * 2)

# Die erste Stufe beginnt bei 0 Leistung
x_values[0] = 0
y_values[0] = df_sorted[grenzkosten_col].iloc[0]

# Erzeugen der Treppenstufen
for i in range(len(df_sorted) - 1):
    x_values[2 * i + 1] = df_sorted['Kumulierte Leistung [MW]'].iloc[i]
    y_values[2 * i + 1] = df_sorted[grenzkosten_col].iloc[i]
    x_values[2 * i + 2] = df_sorted['Kumulierte Leistung [MW]'].iloc[i]
    y_values[2 * i + 2] = df_sorted[grenzkosten_col].iloc[i+1]

# Letzter Punkt der Kurve
x_values[-1] = df_sorted['Kumulierte Leistung [MW]'].iloc[-1]
y_values[-1] = df_sorted[grenzkosten_col].iloc[-1]


# 5. Grafische Darstellung mit Matplotlib
plt.style.use('seaborn-v0_8-whitegrid')
fig, ax = plt.subplots(figsize=(15, 8))

# Zeichnen der Merit-Order-Kurve
ax.plot(x_values, y_values, drawstyle='steps-post', label='Merit-Order Kurve', color='royalblue', linewidth=2)

# Titel und Achsenbeschriftungen
ax.set_title('Merit-Order für die 50Hertz Regelzone', fontsize=18, fontweight='bold')
ax.set_xlabel('Kumulierte Leistung [MW]', fontsize=12)
ax.set_ylabel('Grenzkosten [EUR/MWh]', fontsize=12)

# Gitternetz und Layout
ax.grid(True, which='both', linestyle='--', linewidth=0.5)
plt.tight_layout()

# Speichern der Grafik
output_filename = 'Merit_Order_50Hz.png'
plt.savefig(output_filename, dpi=300)

# Anzeigen der Grafik
plt.show()

print(f"Die Merit-Order-Grafik wurde erfolgreich als '{output_filename}' gespeichert.")
