# load_profiles.py
"""
Hilfsfunktionen zum Einlesen der synthetischen Lastprofile
aus dem Ordner data/Last_errechnet.

Die Dateien enthalten bereits fertige Zeitreihen in MW (total_MW)
für:
- Deutschland gesamt (DE)
- 50Hertz, Amprion, TenneT, TransnetBW

In den Dateien liegen i.d.R. mehrere Sheets, z.B.:
- "2024"
- "2037"
- "2045"

Dieses Modul stellt eine Funktion bereit, um
das passende Sheet anhand des Modelljahres zu wählen
und eine Zeitreihe in MW zurückzugeben, die zur
Modell-Zeitachse (z.B. 15min) passt.
"""

from pathlib import Path
from typing import Union

import pandas as pd


def _detect_time_and_value_cols(df: pd.DataFrame) -> tuple[str, str]:
    """
    Versucht heuristisch die Zeit- und Wertspalte zu finden.

    Annahmen (aus generate_loadprofiles.py / Excel-Dateien):
    - eine Spalte mit Datum/Zeit (z.B. 'Datum bis', 'time', 'timestamp')
    - eine Spalte mit der Gesamtlast in MW (z.B. 'total_MW')

    Rückgabe:
        (time_col, value_col)
    """
    # Kandidaten für Zeitspalte
    time_candidates = [
        "Datum bis",
        "Datum von",
        "time",
        "Time",
        "timestamp",
        "Timestamp",
        "Datum",
        "datetime",
    ]
    value_candidates = [
        "total_MW",
        "Total_MW",
        "Last_MW",
        "load_MW",
    ]

    time_col = None
    for c in df.columns:
        if str(c) in time_candidates:
            time_col = c
            break

    # Fallback: erste Spalte, wenn sie wie ein Datum aussieht
    if time_col is None:
        for c in df.columns:
            try:
                pd.to_datetime(df[c].iloc[:10])
                time_col = c
                break
            except Exception:
                continue

    if time_col is None:
        raise KeyError("Konnte keine Zeitspalte in Lastprofil-Excel erkennen.")

    value_col = None
    for c in df.columns:
        if str(c) in value_candidates:
            value_col = c
            break

    # Fallback: zweite Spalte als Werte
    if value_col is None:
        if len(df.columns) >= 2:
            value_col = df.columns[1]
        else:
            raise KeyError(
                "Konnte keine Wertspalte (MW) in Lastprofil-Excel erkennen."
            )

    return str(time_col), str(value_col)


def read_lastprofile_excel(
    path: Union[str, Path],
    year: int,
    time_freq: str,
    tz: str = "Europe/Berlin",
) -> pd.Series:
    """
    Liest ein synthetisches Lastprofil (z.B. aus data/Last_errechnet)
    und gibt eine Zeitreihe in MW zurück, die zur Modell-Zeitachse passt.

    WICHTIG:
    - Die Excel-Datei enthält bereits MW-Werte (keine MWh!).
    - Es gibt i.d.R. mehrere Sheets mit Namen "2024", "2037", "2045".
      -> Das Sheet mit Namen == str(year) wird bevorzugt.
      -> Falls nicht vorhanden, wird auf das erste Sheet zurückgefallen.

    Parameter
    ---------
    path : str | Path
        Pfad zur Excel-Datei (z.B. data/Last_errechnet/Szenario_Lastprofile_Amprion.xlsx)
    year : int
        Modelljahr (2024, 2037, 2045, ...).
    time_freq : str
        Zielauflösung ('h' oder '15min').
    tz : str
        Zeitzone, standardmäßig 'Europe/Berlin'.

    Rückgabe
    --------
    s : pd.Series
        Zeitreihe der Last in MW, mit tz-aware DatetimeIndex.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lastprofil-Datei nicht gefunden: {path}")

    # ---------------------------------------------------------
    # 1) Passendes Sheet anhand des Jahres wählen
    # ---------------------------------------------------------
    xls = pd.ExcelFile(path)
    year_str = str(year)

    if year_str in xls.sheet_names:
        sheet_to_use = year_str
    else:
        # Falls es das Jahr nicht als Sheet gibt, nimm das erste
        sheet_to_use = xls.sheet_names[0]

    df = pd.read_excel(path, sheet_name=sheet_to_use)

    # ---------------------------------------------------------
    # 2) Zeit- und Wertspalte erkennen
    # ---------------------------------------------------------
    time_col, value_col = _detect_time_and_value_cols(df)

    # In DatetimeIndex umwandeln
    s = df.set_index(time_col)[value_col]
    s = pd.to_numeric(s, errors="coerce")
    s.index = pd.to_datetime(s.index)
    s = s.sort_index()

    # ---------------------------------------------------------
    # 3) Zeitzone robust setzen
    # ---------------------------------------------------------
    if s.index.tz is None:
        # doppelte Zeitstempel (z.B. durch Sommer/Winterzeit) entfernen
        s = s[~s.index.duplicated(keep="first")]

        # Zeitzone setzen:
        # - ambiguous="NaT": doppelte Zeiten -> NaT
        # - nonexistent="NaT": nicht existente Zeiten -> NaT (Sommerzeit-Sprung)
        s.index = s.index.tz_localize(
            tz,
            ambiguous="NaT",
            nonexistent="NaT",
        )
        # Alle NaT-Zeitpunkte rauswerfen
        s = s[~s.index.isna()]

    # ---------------------------------------------------------
    # 4) Auf gewünschte Auflösung bringen
    # ---------------------------------------------------------
    # MW-Werte werden gemittelt (passend zur Interpretation als Leistung)
    s = s.resample(time_freq).mean()

    # Lücken schließen (zur Sicherheit)
    s = s.interpolate("time").ffill().bfill().astype(float)

    return s
