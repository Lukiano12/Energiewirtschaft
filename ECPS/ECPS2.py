import pandas as pd
import matplotlib.pyplot as plt
import os  # NEW IMPORT for os

# Pfad zur CSV-Datei
file_path = r'c:\Users\User\Desktop\Energiewirtschaft\ECPS\Task2.csv'

# CSV-Datei einlesen
# Der Separator ist ein Semikolon und das Dezimaltrennzeichen ein Punkt.
df = pd.read_csv(file_path, delimiter=';', decimal='.')

# Daten für die Achsen extrahieren
x_axis = df['mean current density in A/cm^2']
y_axis = df['cell voltage in V']

# Plot erstellen
plt.figure(figsize=(10, 6))
plt.plot(x_axis, y_axis, marker='o', linestyle='-')

# Titel und Achsenbeschriftungen hinzufügen
plt.title('Cell Voltage vs. Current Density')
plt.xlabel('Mean Current Density in A/cm²')
plt.ylabel('Cell Voltage in V')

# Gitter hinzufügen
plt.grid(True)


# --- NEW TASK: Plot and analyze Polcurve.csv ---

# Path to the new CSV file
file_path_pol = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Polcurve.csv')

# Read the CSV file. Note: The delimiter is a comma and the decimal separator is also a comma.
df_pol = pd.read_csv(file_path_pol, delimiter=',', decimal=',')

# Extract data for the axes
x_pol = df_pol['CellCurrentDensity [A/cm2]']
y_pol = df_pol['CellVoltage [V]']

# Create the new plot
plt.figure(figsize=(10, 6))
plt.plot(x_pol, y_pol, marker='o', linestyle='--', label='Experimental Data')

# Add title and labels
plt.title('Fuel Cell Polarization Curve')
plt.xlabel('Current Density [A/cm²]')
plt.ylabel('Cell Voltage [V]')
plt.legend()
plt.grid(True)

# --- Analysis and Answers ---
#
# What do you notice? Why are there two “branches”?
#
# You notice that the plot has two distinct curves or "branches", creating a loop. This is called hysteresis.
# The experiment was likely run by first increasing the current from 0 to a maximum value (measuring the "forward" branch)
# and then decreasing it back to 0 (measuring the "backward" branch).
# The cell's voltage response is different in each direction because its internal state (e.g., water content in the
# membrane, catalyst state) changes during operation and does not immediately return to its initial state.
# This memory effect causes the two different branches.
#
# Why is current density [A/cm²] used and not current [A]?
#
# Current density (Current / Area) is used to make the performance of different fuel cells comparable.
# A large fuel cell will naturally produce a higher current [A] than a small one, even if they are built
# with the same technology. By normalizing the current by the cell's active area, we get an intrinsic
# performance metric (A/cm²) that is independent of the cell's physical size. This allows engineers
# and scientists to compare the quality of different materials and designs on a level playing field.


# Plot anzeigen
plt.show()