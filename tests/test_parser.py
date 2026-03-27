"""Integration tests for pdf_parser.py using real sample invoice PDFs.

Oracle values from CONTEXT.md S5 + Task 3 specs:
  Electricity Jan2024: total=116,461.40 EUR, consumption=478,800 kWh, 2 line items
  Electricity Mar2024: total=108,096.61 EUR, consumption=453,100 kWh, 2 line items
  NaturalGas  Jan2024: total= 26,925.23 EUR, consumption=310,800 kWh, 1 line item
  Diesel      Feb2024: total= 15,081.47 EUR, consumption=  8,500 litres, 1 line item
  Stadtwerke  Feb2024: total=100,185.65 EUR, consumption=415,300 kWh, 1 line item
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chemtrace.pdf_parser import parse_invoice

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_invoices"


def _total_consumption(data: dict) -> float:
    return sum(li.consumption_kwh or 0.0 for li in data["line_items"])


class TestParseElectricityJan:
    def setup_method(self):
        pdf = DATA_DIR / "Invoice_Electricity_Jan2024_RuhrChem.pdf"
        self.result = parse_invoice(pdf)

    def test_success(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_total_amount(self):
        assert self.result.data["total_amount"] == pytest.approx(116_461.40, abs=0.01)

    def test_consumption(self):
        assert _total_consumption(self.result.data) == pytest.approx(478_800.0, abs=1.0)

    def test_line_items(self):
        items = self.result.data["line_items"]
        assert len(items) == 2

    def test_energy_type(self):
        types = {li.energy_type for li in self.result.data["line_items"]}
        assert types == {"electricity"}

    def test_consumption_unit(self):
        for li in self.result.data["line_items"]:
            assert li.consumption_unit == "kWh"


class TestParseElectricityMar:
    def setup_method(self):
        pdf = DATA_DIR / "Invoice_Electricity_Mar2024_RuhrChem.pdf"
        self.result = parse_invoice(pdf)

    def test_success(self):
        assert self.result.success is True

    def test_total_amount(self):
        assert self.result.data["total_amount"] == pytest.approx(108_096.61, abs=0.01)

    def test_consumption(self):
        assert _total_consumption(self.result.data) == pytest.approx(453_100.0, abs=1.0)

    def test_line_items(self):
        assert len(self.result.data["line_items"]) == 2

    def test_consumption_unit(self):
        for li in self.result.data["line_items"]:
            assert li.consumption_unit == "kWh"


class TestParseNaturalGasJan:
    def setup_method(self):
        pdf = DATA_DIR / "Invoice_NaturalGas_Jan2024_RuhrChem.pdf"
        self.result = parse_invoice(pdf)

    def test_success(self):
        assert self.result.success is True

    def test_total_amount(self):
        assert self.result.data["total_amount"] == pytest.approx(26_925.23, abs=0.01)

    def test_consumption(self):
        assert _total_consumption(self.result.data) == pytest.approx(310_800.0, abs=1.0)

    def test_line_items(self):
        assert len(self.result.data["line_items"]) == 1

    def test_energy_type(self):
        assert self.result.data["line_items"][0].energy_type == "natural_gas"

    def test_consumption_unit(self):
        assert self.result.data["line_items"][0].consumption_unit == "kWh"


class TestParseDieselFeb:
    def setup_method(self):
        pdf = DATA_DIR / "Invoice_Diesel_Feb2024_RuhrChem.pdf"
        self.result = parse_invoice(pdf)

    def test_success(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_total_amount(self):
        assert self.result.data["total_amount"] == pytest.approx(15_081.47, abs=0.01)

    def test_consumption(self):
        assert _total_consumption(self.result.data) == pytest.approx(8_500.0, abs=1.0)

    def test_line_items(self):
        assert len(self.result.data["line_items"]) == 1

    def test_energy_type(self):
        assert self.result.data["line_items"][0].energy_type == "diesel"

    def test_consumption_unit(self):
        assert self.result.data["line_items"][0].consumption_unit == "litres"

    def test_vendor(self):
        assert self.result.data["vendor_name"] == "NRW Energie Versorgung GmbH"

    def test_invoice_number(self):
        assert self.result.data["invoice_number"] == "DI-2024-001"


class TestParseStadtwerkeElectricityFeb:
    def setup_method(self):
        pdf = DATA_DIR / "Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf"
        self.result = parse_invoice(pdf)

    def test_success(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_total_amount(self):
        assert self.result.data["total_amount"] == pytest.approx(100_185.65, abs=0.01)

    def test_consumption(self):
        assert _total_consumption(self.result.data) == pytest.approx(415_300.0, abs=1.0)

    def test_line_items(self):
        assert len(self.result.data["line_items"]) == 1

    def test_energy_type(self):
        assert self.result.data["line_items"][0].energy_type == "electricity"

    def test_consumption_unit(self):
        assert self.result.data["line_items"][0].consumption_unit == "kWh"

    def test_vendor(self):
        assert self.result.data["vendor_name"] == "Stadtwerke Essen AG"

    def test_invoice_number(self):
        assert self.result.data["invoice_number"] == "SWE-2024-0847"

    def test_billing_period(self):
        assert self.result.data["billing_period_from"] == "2024-02-01"
        assert self.result.data["billing_period_to"] == "2024-02-28"


def test_parse_esg_report_fails():
    """ESG report has no invoice number -> must return success=False."""
    pdf = DATA_DIR / "ESG_Report_Energy_Emissions_RuhrChem_2024.pdf"
    result = parse_invoice(pdf)
    assert result.success is False
    assert result.error is not None
    assert "invoice" in result.error.lower()


def test_parse_nonexistent_file():
    result = parse_invoice(DATA_DIR / "does_not_exist.pdf")
    assert result.success is False
    assert result.error is not None
    assert "not found" in result.error.lower()
