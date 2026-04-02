"""Tests for sap_parser.py: SAP CSV energy export parsing.

Covers encoding detection, delimiter detection, number parsing,
period normalization, energy type mapping, and full parse integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemtrace.sap_parser import (
    _detect_delimiter,
    _detect_encoding,
    _detect_number_format,
    _map_energy_type,
    _normalize_period,
    _parse_number,
    parse_sap_csv,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_sap"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(tmp_path: Path, name: str, content: str,
               encoding: str = "cp1252", bom: bool = False) -> Path:
    """Write a CSV file with specified encoding. Returns path."""
    path = tmp_path / name
    raw = content.encode(encoding)
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    path.write_bytes(raw)
    return path


# === Encoding Detection ===

class TestDetectEncoding:
    def test_utf8_bom(self, tmp_path: Path) -> None:
        """File with BOM -> 'utf-8-sig'."""
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbfWerk;Zeitraum\n")
        assert _detect_encoding(path) == "utf-8-sig"

    def test_cp1252(self, tmp_path: Path) -> None:
        """File with umlauts in cp1252 -> 'cp1252'."""
        path = tmp_path / "cp.csv"
        # \xe4 = a-umlaut in cp1252, invalid in UTF-8
        path.write_bytes(b"Hauptz\xe4hler;test\n")
        assert _detect_encoding(path) == "cp1252"

    def test_utf8_no_bom(self, tmp_path: Path) -> None:
        """Pure ASCII / valid UTF-8 without BOM -> 'utf-8-sig'."""
        path = tmp_path / "ascii.csv"
        path.write_bytes(b"Werk;Zeitraum;Strom\n")
        assert _detect_encoding(path) == "utf-8-sig"


# === Delimiter Detection ===

class TestDetectDelimiter:
    def test_semicolon(self) -> None:
        """Standard SAP semicolon-delimited."""
        sample = "Werk;Zeitraum;Energieart\nEssen;2024-01;Strom\n"
        assert _detect_delimiter(sample) == ";"

    def test_comma(self) -> None:
        """Comma-delimited lines."""
        sample = "Plant,Period,Energy\nEssen,2024-01,Electricity\n"
        assert _detect_delimiter(sample) == ","

    def test_tab(self) -> None:
        """Tab-delimited lines."""
        sample = "Plant\tPeriod\tEnergy\nEssen\t2024-01\tStrom\n"
        assert _detect_delimiter(sample) == "\t"

    def test_german_numbers_semicolon(self) -> None:
        """Semicolons win over commas in German number format."""
        sample = "Essen;2024-01;Strom;478800,0;kWh;116461,40;EUR\n"
        assert _detect_delimiter(sample) == ";"


# === Number Format Detection + Parsing ===

class TestNumberFormat:
    def test_detect_german(self) -> None:
        """Row with '478800,0' -> 'german'."""
        rows = [["Essen", "2024-01", "Strom", "478800,0", "kWh", "116461,40"]]
        assert _detect_number_format(rows) == "german"

    def test_detect_english(self) -> None:
        """Row with '478800.0' -> 'english'."""
        rows = [["Essen", "2024-01", "Strom", "478800.0", "kWh", "116461.40"]]
        assert _detect_number_format(rows) == "english"


class TestParseNumber:
    def test_german_with_thousands(self) -> None:
        """'1.234,56' with format='german' -> 1234.56."""
        assert _parse_number("1.234,56", "german") == pytest.approx(1234.56)

    def test_german_no_thousands(self) -> None:
        """'234,56' with format='german' -> 234.56."""
        assert _parse_number("234,56", "german") == pytest.approx(234.56)

    def test_german_integer(self) -> None:
        """'478800,0' with format='german' -> 478800.0."""
        assert _parse_number("478800,0", "german") == pytest.approx(478800.0)

    def test_english(self) -> None:
        """'1,234.56' with format='english' -> 1234.56."""
        assert _parse_number("1,234.56", "english") == pytest.approx(1234.56)

    def test_invalid(self) -> None:
        """'abc' -> None."""
        assert _parse_number("abc", "german") is None

    def test_empty(self) -> None:
        """Empty string -> None."""
        assert _parse_number("", "german") is None

    def test_none(self) -> None:
        """None -> None."""
        assert _parse_number(None, "german") is None


# === Period Normalization ===

class TestNormalizePeriod:
    def test_iso(self) -> None:
        """'2024-01' -> '2024-01'."""
        assert _normalize_period("2024-01") == "2024-01"

    def test_german(self) -> None:
        """'01.2024' -> '2024-01'."""
        assert _normalize_period("01.2024") == "2024-01"

    def test_compact(self) -> None:
        """'202401' -> '2024-01'."""
        assert _normalize_period("202401") == "2024-01"

    def test_month_de(self) -> None:
        """'Januar 2024' -> '2024-01'."""
        assert _normalize_period("Januar 2024") == "2024-01"

    def test_month_en(self) -> None:
        """'January 2024' -> '2024-01'."""
        assert _normalize_period("January 2024") == "2024-01"

    def test_month_abbrev(self) -> None:
        """'Jan 2024' -> '2024-01'."""
        assert _normalize_period("Jan 2024") == "2024-01"

    def test_sap_fiscal(self) -> None:
        """'P01/2024' -> '2024-01'."""
        assert _normalize_period("P01/2024") == "2024-01"

    def test_slash(self) -> None:
        """'01/2024' -> '2024-01'."""
        assert _normalize_period("01/2024") == "2024-01"

    def test_out_of_range_low(self) -> None:
        """Year < 2000 -> None."""
        assert _normalize_period("1999-01") is None

    def test_out_of_range_high(self) -> None:
        """Year > 2030 -> None."""
        assert _normalize_period("2031-01") is None

    def test_unparseable(self) -> None:
        """Garbage -> None."""
        assert _normalize_period("not-a-date") is None


# === Energy Type Mapping ===

class TestMapEnergyType:
    def test_strom(self) -> None:
        assert _map_energy_type("Strom") == "electricity"

    def test_erdgas(self) -> None:
        assert _map_energy_type("Erdgas") == "natural_gas"

    def test_diesel(self) -> None:
        assert _map_energy_type("Diesel") == "diesel"

    def test_substring(self) -> None:
        """'Stromverbrauch' -> 'electricity' (substring match)."""
        assert _map_energy_type("Stromverbrauch") == "electricity"

    def test_unknown(self) -> None:
        """'Dampf' -> 'unknown'."""
        assert _map_energy_type("Dampf") == "unknown"

    def test_district_heating(self) -> None:
        assert _map_energy_type("Fernwaerme") == "district_heating"

    def test_english(self) -> None:
        assert _map_energy_type("Electricity") == "electricity"


# === Full Parse (Integration) ===

class TestParseSapCsvHappyPath:
    """Parse the main synthetic CSV with headers (4 data rows)."""

    def setup_method(self) -> None:
        self.results = parse_sap_csv(DATA_DIR / "energy_export_essen_2024.csv")

    def test_row_count(self) -> None:
        assert len(self.results) == 4

    def test_all_success(self) -> None:
        assert all(r.success for r in self.results)

    def test_first_row_values(self) -> None:
        """First row: Essen Blending, Jan 2024, electricity, 478800 kWh."""
        r = self.results[0]
        assert r.data["site_address"] == "Essen Blending"
        assert r.data["billing_period_from"] == "2024-01"
        li = r.data["line_items"][0]
        assert li.energy_type == "electricity"
        assert li.consumption_kwh == pytest.approx(478800.0)
        assert li.consumption_unit == "kWh"

    def test_cost(self) -> None:
        """First row cost = 116461.40 EUR."""
        assert self.results[0].data["total_amount"] == pytest.approx(116461.40, abs=0.01)

    def test_vendor_name(self) -> None:
        assert self.results[0].data["vendor_name"] == "SAP Export"

    def test_invoice_number(self) -> None:
        assert self.results[0].data["invoice_number"] == "SAP-energy_export_essen_2024-R1"


class TestParseSapCsvHeaderless:
    """Parse headerless CSV -> columns inferred."""

    def setup_method(self) -> None:
        self.results = parse_sap_csv(DATA_DIR / "energy_export_headerless.csv")

    def test_row_count(self) -> None:
        assert len(self.results) == 2

    def test_all_success(self) -> None:
        assert all(r.success for r in self.results)

    def test_values(self) -> None:
        li = self.results[0].data["line_items"][0]
        assert li.energy_type == "electricity"
        assert li.consumption_kwh == pytest.approx(478800.0)


class TestParseSapCsvBom:
    """Parse UTF-8 BOM CSV."""

    def setup_method(self) -> None:
        self.results = parse_sap_csv(DATA_DIR / "energy_export_bom.csv")

    def test_row_count(self) -> None:
        assert len(self.results) == 1

    def test_success(self) -> None:
        assert self.results[0].success

    def test_english_numbers(self) -> None:
        """English number format parsed correctly."""
        li = self.results[0].data["line_items"][0]
        assert li.consumption_kwh == pytest.approx(478800.0)

    def test_header_clean(self) -> None:
        """First header field has no BOM character contamination."""
        # If BOM was not stripped, site_address parsing would fail
        assert self.results[0].data["site_address"] == "Essen Blending"


class TestParseSapCsvEdgeCases:
    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file -> empty list."""
        path = tmp_path / "empty.csv"
        path.write_bytes(b"")
        assert parse_sap_csv(path) == []

    def test_headers_only(self, tmp_path: Path) -> None:
        """File with only headers, no data -> empty list."""
        path = _write_csv(tmp_path, "headers_only.csv",
                          "Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten\n")
        assert parse_sap_csv(path) == []

    def test_missing_columns(self, tmp_path: Path) -> None:
        """Row with fewer columns -> row skipped, others still parsed."""
        content = (
            "Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung\r\n"
            "Essen;2024-01;Strom;478800,0;kWh;116461,40;EUR\r\n"
            "Short;Row\r\n"
            "Essen;2024-02;Erdgas;310800,0;kWh;24864,00;EUR\r\n"
        )
        path = _write_csv(tmp_path, "short_row.csv", content)
        results = parse_sap_csv(path)
        assert len(results) == 2  # short row skipped
        assert all(r.success for r in results)

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent file -> list with one failed ParseResult."""
        results = parse_sap_csv(tmp_path / "nope.csv")
        assert len(results) == 1
        assert not results[0].success
        assert "not found" in results[0].error.lower()


class TestParseSapCsvIdentifiers:
    """Verify document IDs and naming conventions."""

    def setup_method(self) -> None:
        self.results = parse_sap_csv(DATA_DIR / "energy_export_essen_2024.csv")

    def test_blob_name(self) -> None:
        """blob_name follows '{filename}:row_{N}' format, N starts at 1."""
        assert self.results[0].data["blob_name"] == "energy_export_essen_2024.csv:row_1"
        assert self.results[1].data["blob_name"] == "energy_export_essen_2024.csv:row_2"

    def test_unique_ids(self) -> None:
        """4 rows -> 4 different row_hash values (unique ChromaDB IDs)."""
        hashes = {r.data["row_hash"] for r in self.results}
        assert len(hashes) == 4

    def test_hash_is_sha256_hex(self) -> None:
        """Hash is 64 hex chars (SHA-256)."""
        h = self.results[0].data["row_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestParseSapCsvUnits:
    """Verify consumption_unit handling."""

    def setup_method(self) -> None:
        self.results = parse_sap_csv(DATA_DIR / "energy_export_essen_2024.csv")

    def test_electricity_unit(self) -> None:
        li = self.results[0].data["line_items"][0]
        assert li.consumption_unit == "kWh"

    def test_diesel_unit(self) -> None:
        """Diesel row has consumption_unit='Liter', not default 'kWh'."""
        li = self.results[2].data["line_items"][0]
        assert li.consumption_unit == "Liter"
        assert li.energy_type == "diesel"
        assert li.consumption_kwh == pytest.approx(8500.0)

    def test_values_match_pdf(self) -> None:
        """SAP electricity Jan 2024 = 478,800 kWh (matches PDF invoice oracle value)."""
        li = self.results[0].data["line_items"][0]
        assert li.consumption_kwh == pytest.approx(478800.0, abs=1.0)
