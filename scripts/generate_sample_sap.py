"""Generate synthetic SAP CSV exports for ChemTrace testing.

Dev-only script. No external dependencies.
Output: data/sample_sap/*.csv (3 files with specific encodings).
"""

from __future__ import annotations

from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_sap"


def _write_cp1252_with_headers() -> None:
    """File 1: cp1252, semicolon, German numbers, with headers (4 data rows)."""
    lines = [
        "Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung;Zaehler_ID;Bemerkung",
        "Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR;DE-ESS-001;Hauptz\u00e4hler Produktion",
        "Essen Blending;2024-01;Erdgas;310800,0;kWh;24864,00;EUR;DE-ESS-G01;Kessel + Trockner",
        "Essen Blending;2024-02;Diesel;8500,0;Liter;13600,00;EUR;;Interne Logistik",
        "Essen Blending;2024-03;Strom;420000,0;kWh;108096,61;EUR;DE-ESS-001;Hauptz\u00e4hler Produktion",
    ]
    content = "\r\n".join(lines) + "\r\n"
    path = OUTPUT_DIR / "energy_export_essen_2024.csv"
    path.write_bytes(content.encode("cp1252"))
    print(f"  Created {path.name} (cp1252, headers, 4 data rows)")


def _write_cp1252_headerless() -> None:
    """File 2: cp1252, semicolon, German numbers, NO headers (2 data rows)."""
    lines = [
        "Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR",
        "Essen Blending;2024-02;Erdgas;285000,0;kWh;22800,00;EUR",
    ]
    content = "\r\n".join(lines) + "\r\n"
    path = OUTPUT_DIR / "energy_export_headerless.csv"
    path.write_bytes(content.encode("cp1252"))
    print(f"  Created {path.name} (cp1252, no headers, 2 data rows)")


def _write_utf8_bom() -> None:
    """File 3: UTF-8 with BOM, semicolon, English numbers, with headers (1 data row)."""
    lines = [
        "Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung",
        "Essen Blending;2024-01;Strom;478800.0;kWh;116461.40;EUR",
    ]
    content = "\r\n".join(lines) + "\r\n"
    bom = b"\xef\xbb\xbf"
    path = OUTPUT_DIR / "energy_export_bom.csv"
    path.write_bytes(bom + content.encode("utf-8"))
    print(f"  Created {path.name} (UTF-8 + BOM, headers, 1 data row)")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating SAP CSV samples in {OUTPUT_DIR}")
    _write_cp1252_with_headers()
    _write_cp1252_headerless()
    _write_utf8_bom()
    print("Done.")


if __name__ == "__main__":
    main()
