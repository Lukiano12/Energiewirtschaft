import pandas as pd
import matplotlib.pyplot as plt
import os
import io

# --- Load and process Experimental.csv ---
# Pfad zur CSV-Datei
file_path_exp = r'c:\Users\User\Desktop\Energiewirtschaft\ECPS\Experimental.csv'

# CSV-Datei einlesen
# Der Separator ist ein Semikolon und das Dezimaltrennzeichen ein Punkt.
df_exp = pd.read_csv(file_path_exp, delimiter=';', decimal='.')

# Daten für die Achsen extrahieren
x_exp = df_exp['mean current density in A/cm^2']
y_exp = df_exp['cell voltage in V']


# --- Load and process Polcurve.csv ---
# Path to the new CSV file
file_path_pol = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Polcurve.csv')

# Read the CSV file. Note: The delimiter is a comma and the decimal separator is also a comma.
df_pol = pd.read_csv(file_path_pol, delimiter=',', decimal=',')

# Calculate the mean of 'CellVoltage [V]' for each unique 'CellCurrentDensity [A/cm2]'
df_pol_mean = df_pol.groupby('CellCurrentDensity [A/cm2]')['CellVoltage [V]'].mean().reset_index()

# --- Create the combined plot ---
plt.figure(figsize=(12, 7))
plt.plot(x_exp, y_exp, marker='o', linestyle='-', label='Average Curve')
plt.plot(df_pol_mean['CellCurrentDensity [A/cm2]'], df_pol_mean['CellVoltage [V]'], marker='.', linestyle='--', label='Experimental Curve')
plt.title('Combined Plot: Experimental vs. Averaged Polcurve')
plt.xlabel('Current Density [A/cm²]')
plt.ylabel('Cell Voltage [V]')
plt.legend()
plt.grid(True)

# Plot anzeigen
plt.show()

# --- Additional Data Processing and Plotting ---
# Data from the user
data = """I [mA]	U [V]	P (mW)	Efficiency
0	0,75	0	60,98%
5	0,731	3,655	59,43%
10	0,713	7,13	57,97%
15	0,698	10,47	56,75%
20	0,683	13,66	55,53%
25	0,671	16,775	54,55%
30	0,659	19,77	53,58%
35	0,647	22,645	52,60%
40	0,635	25,4	51,63%
45	0,624	28,08	50,73%
50	0,614	30,7	49,92%
55	0,604	33,22	49,11%
60	0,595	35,7	48,37%
65	0,585	38,025	47,56%
70	0,576	40,32	46,83%
75	0,567	42,525	46,10%
80	0,557	44,56	45,28%
85	0,547	46,495	44,47%
90	0,536	48,24	43,58%
"""

# Read the data into a pandas DataFrame
# The decimal separator is a comma, so we need to specify that.
# The separator between columns is a tab.
df = pd.read_csv(io.StringIO(data), sep='\\t', decimal=',')

# Clean up column names
df.columns = [col.strip() for col in df.columns]
df = df.rename(columns={'I [mA]': 'Current (mA)', 'U [V]': 'Voltage (V)', 'P (mW)': 'Power (mW)'})


# Convert 'Efficiency' from string with '%' to float
df['Efficiency'] = df['Efficiency'].str.replace('%', '', regex=False).str.replace(',', '.', regex=False).astype(float) / 100

# Create the plot
fig, ax1 = plt.subplots(figsize=(10, 6))

# Plot Voltage vs Current on the first y-axis
color = 'tab:blue'
ax1.set_xlabel('Current (mA)')
ax1.set_ylabel('Voltage (V)', color=color)
ax1.plot(df['Current (mA)'], df['Voltage (V)'], color=color, marker='o', label='Voltage (V)')
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(True)

# Create a second y-axis for Efficiency
ax2 = ax1.twinx()
color = 'tab:red'
ax2.set_ylabel('Efficiency', color=color)
ax2.plot(df['Current (mA)'], df['Efficiency'], color=color, marker='x', linestyle='--', label='Efficiency')
ax2.tick_params(axis='y', labelcolor=color)

# Format the efficiency axis to show percentages
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))


# Add a title
plt.title('Voltage and Efficiency vs. Current')

# Add legends
# To combine legends from both axes, we get handles and labels from both
handles1, labels1 = ax1.get_legend_handles_labels()
handles2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(handles1 + handles2, labels1 + labels2, loc='upper right')


# Show the plot
plt.show()