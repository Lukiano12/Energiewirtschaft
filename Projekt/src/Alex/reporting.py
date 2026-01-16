# reporting.py
"""
Schöne Konsolen-Ausgabe für KPI-Tabellen.
"""

import pandas as pd


def print_kpi_table(df: pd.DataFrame, title: str, float_fmt="{:,.3f}".format):
    """
    Druckt ein DataFrame als schön formatierte Tabelle in die Konsole.
    - float_fmt: Formatierung für floats (Standard: 3 Nachkommastellen, Tausendertrennzeichen)
    """
    if df is None or df.empty:
        print(f"\n{title}\n(keine Daten)")
        return

    # Wir formatieren floats hübsch, lassen ints wie ints
    fmt_df = df.copy()

    for col in fmt_df.columns:
        if pd.api.types.is_float_dtype(fmt_df[col]):
            fmt_df[col] = fmt_df[col].map(lambda x: "" if pd.isna(x) else float_fmt(x))

    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    print(fmt_df.to_string(index=False))
