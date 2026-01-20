# src/build_ns_plants_lists.py
from __future__ import annotations

from pathlib import Path
import pandas as pd


CAP_COLS = [
    "Bruttoleistung [MW]",
    "Netto-Nennleistung\n(elektrische Wirkleistung) [MW]",
    "Mittlere verfügbare\nNetto-Nennleistung [MW]",
]


def _read_plants(path: Path, sheet_name: str) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    use_sheet = sheet_name if sheet_name in xls.sheet_names else xls.sheet_names[0]
    df = pd.read_excel(path, sheet_name=use_sheet)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _ensure_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def build_ns_from_z4(
    df_z4: pd.DataFrame,
    tennet_share_nord: float = 0.5,
    zone_col_uenb: str = "ÜNB",
    ns_zone_col: str = "NS_Zone",
) -> pd.DataFrame:
    """
    Erzeugt eine Nord/Süd-Kraftwerksliste aus einer 4Z-ÜNB-Kraftwerksliste.
    - 50Hertz -> NORD
    - Amprion -> SUED
    - TransnetBW -> SUED
    - TenneT -> split: Anteil NORD = tennet_share_nord, Anteil SUED = 1 - Anteil

    Die Leistungsspalten (CAP_COLS) werden für TenneT skaliert.
    """
    df = df_z4.copy()
    df[zone_col_uenb] = df[zone_col_uenb].astype(str).str.strip()

    _ensure_numeric(df, CAP_COLS)

    # fixe Zuordnung
    mapping = {
        "50Hertz": "NORD",
        "Amprion": "SUED",
        "TransnetBW": "SUED",
    }

    # alles außer TenneT zuerst mappen
    df[ns_zone_col] = df[zone_col_uenb].map(mapping)

    # --- TenneT splitten ---
    is_tennet = df[zone_col_uenb].str.casefold().eq("tennet".casefold())
    df_t = df.loc[is_tennet].copy()
    df_rest = df.loc[~is_tennet].copy()

    if not df_t.empty:
        share_n = float(tennet_share_nord)
        share_s = 1.0 - share_n

        # Nord-Teil
        df_n = df_t.copy()
        df_n[ns_zone_col] = "NORD"
        for c in CAP_COLS:
            if c in df_n.columns:
                df_n[c] = df_n[c] * share_n

        # Süd-Teil
        df_s = df_t.copy()
        df_s[ns_zone_col] = "SUED"
        for c in CAP_COLS:
            if c in df_s.columns:
                df_s[c] = df_s[c] * share_s

        df_out = pd.concat([df_rest, df_n, df_s], ignore_index=True)
    else:
        df_out = df_rest

    # Falls irgendwo noch NaN in NS_Zone ist (unerwarteter ÜNB), setze Default
    df_out[ns_zone_col] = df_out[ns_zone_col].fillna("NORD")

    return df_out


def main():
    # Passe diese Pfade ggf. an dein Projekt an (hier: relativ zu src/)
    project_root = Path(__file__).resolve().parents[1]
    plants_dir = project_root / "data" / "plants"

    sheet = "Kraftwerksliste_Miri"

    # Welche Jahre sollen erzeugt werden?
    years = [2037, 2045]

    # Default: 50/50 Split für TenneT (kannst du später in config spiegeln)
    tennet_share_nord = 0.5

    for y in years:
        src = plants_dir / f"Kraftwerksliste_{y}.xlsx"
        if not src.exists():
            raise FileNotFoundError(f"Nicht gefunden: {src}")

        df_z4 = _read_plants(src, sheet_name=sheet)
        df_ns = build_ns_from_z4(df_z4, tennet_share_nord=tennet_share_nord)

        out = plants_dir / f"Kraftwerksliste_NS_{y}.xlsx"
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df_ns.to_excel(writer, sheet_name=sheet, index=False)

        print(f"[OK] geschrieben: {out.name}  (rows={len(df_ns)})")


if __name__ == "__main__":
    main()
