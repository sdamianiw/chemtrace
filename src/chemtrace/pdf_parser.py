"""PDF invoice parser using pdfplumber with configurable regex patterns.

Strategy: two-pass extraction.
  Pass 1: page.extract_text()  → regex for header fields and footer totals
  Pass 2: page.extract_tables() → dynamic column mapping for line items
  Fallback: regex on full text if table extraction yields nothing

Never raises. Always returns ParseResult.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from chemtrace.parser_patterns import COLUMN_ALIASES, PATTERNS
from chemtrace.utils import clean_number

logger = logging.getLogger(__name__)

_MAX_PDF_BYTES = 10_000_000  # 10 MB guard (per ARCHITECTURE.md §6)


@dataclass
class LineItem:
    meter_id: str | None = None
    energy_type: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    consumption_kwh: float | None = None
    unit_price: float | None = None
    amount_eur: float | None = None
    consumption_unit: str = "kWh"


@dataclass
class ParseResult:
    success: bool
    data: dict | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_invoice(pdf_path: Path) -> ParseResult:
    """Parse a single PDF invoice. Returns ParseResult — never raises."""
    warnings: list[str] = []

    # --- Guard: file validation ---
    if not pdf_path.exists():
        return ParseResult(success=False, data=None, error=f"File not found: {pdf_path}")
    if pdf_path.stat().st_size == 0:
        return ParseResult(success=False, data=None, error=f"Empty file: {pdf_path}")
    if pdf_path.stat().st_size > _MAX_PDF_BYTES:
        return ParseResult(success=False, data=None, error=f"File too large (>10 MB): {pdf_path}")

    # --- Extract raw content ---
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return ParseResult(success=False, data=None, error="PDF has no pages")
            page = pdf.pages[0]
            full_text: str = page.extract_text() or ""
            tables: list = page.extract_tables() or []
    except Exception as exc:
        return ParseResult(success=False, data=None, error=f"PDF read error: {exc}")

    if not full_text.strip():
        return ParseResult(success=False, data=None, error="No text extracted from PDF")

    # --- Parse header ---
    data: dict = {"raw_text": full_text}
    data["vendor_name"] = _extract_vendor_name(full_text)
    data["customer_name"] = _extract_field(full_text, PATTERNS["customer"])
    data["site_address"] = _extract_field(full_text, PATTERNS["site"])
    data["address"] = _extract_field(full_text, PATTERNS["address"])
    data["invoice_number"] = _extract_field(full_text, PATTERNS["invoice_number"])
    data["invoice_date"] = _extract_field(full_text, PATTERNS["invoice_date"])
    data["currency"] = _extract_field(full_text, PATTERNS["currency"])
    period_from, period_to = _extract_billing_period(full_text)
    data["billing_period_from"] = period_from
    data["billing_period_to"] = period_to

    # Early exit if no invoice number — likely a non-invoice document (e.g. ESG report)
    if data["invoice_number"] is None:
        return ParseResult(
            success=False,
            data=data,
            warnings=warnings,
            error="No invoice number found - file may not be an invoice",
        )

    # --- Parse line items (table-first, regex fallback) ---
    line_items = _extract_line_items_from_tables(tables, warnings)
    if not line_items:
        line_items = _extract_line_items_from_text(full_text, warnings)
    if not line_items:
        warnings.append("No line items extracted from table or text")
    data["line_items"] = line_items

    # --- Parse footer totals ---
    data["subtotal"] = _extract_amount(full_text, PATTERNS["subtotal"])
    data["network_levies"] = _extract_amount(full_text, PATTERNS["network_levies"])
    data["vat_amount"] = _extract_amount(full_text, PATTERNS["vat"])
    data["total_amount"] = _extract_amount(full_text, PATTERNS["total"])

    if data["total_amount"] is None:
        warnings.append("Could not extract total amount")

    return ParseResult(success=True, data=data, warnings=warnings)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_vendor_name(text: str) -> str | None:
    """Return the first non-empty line as vendor name.

    Design note: these synthetic invoices have no 'Vendor:' label — the vendor
    name is the bold heading at the top. Positional extraction is more reliable
    than regex here. If a future invoice format adds a label, add a regex to
    PATTERNS["vendor_name"] and call _extract_field first.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _extract_field(text: str, patterns: list[str]) -> str | None:
    """Try each regex pattern in order. Return first captured group, or None."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_billing_period(text: str) -> tuple[str | None, str | None]:
    """Extract billing period start and end dates. Returns (from, to) in ISO format."""
    for pattern in PATTERNS["billing_period"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_from = m.group(1)
            date_to = m.group(2)
            # Convert German DD.MM.YYYY to ISO YYYY-MM-DD if needed
            if "." in date_from:
                date_from = _de_date_to_iso(date_from)
                date_to = _de_date_to_iso(date_to)
            return date_from, date_to
    return None, None


def _de_date_to_iso(date_str: str) -> str:
    """Convert 'DD.MM.YYYY' to 'YYYY-MM-DD'."""
    parts = date_str.split(".")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


def _extract_amount(text: str, patterns: list[str]) -> float | None:
    """Extract a monetary amount via regex, cleaned to float."""
    raw = _extract_field(text, patterns)
    return clean_number(raw)


def _map_columns(header_row: list[str | None]) -> dict[str, int]:
    """Build {canonical_name: column_index} by matching header cells against COLUMN_ALIASES."""
    mapping: dict[str, int] = {}
    for col_idx, cell in enumerate(header_row):
        if cell is None:
            continue
        cell_lower = cell.lower().strip()
        for canonical, aliases in COLUMN_ALIASES.items():
            if canonical in mapping:
                continue
            if any(alias in cell_lower for alias in aliases):
                mapping[canonical] = col_idx
    return mapping


def _classify_energy_type(raw: str) -> str | None:
    """Map raw 'Energy type' cell text to canonical name via keyword matching."""
    raw_lower = raw.lower()
    for canonical, keywords in PATTERNS["energy_type_keywords"].items():
        if any(kw in raw_lower for kw in keywords):
            return canonical
    return raw  # Return raw value if no match rather than None


def _extract_line_items_from_tables(
    tables: list,
    warnings: list[str],
) -> list[LineItem]:
    """Primary extraction path: structured table rows with dynamic column mapping."""
    items: list[LineItem] = []
    for table in tables:
        if not table or len(table) < 2:
            continue
        # Find the header row: the first row that contains a recognized column name
        header_idx = None
        col_map: dict[str, int] = {}
        for row_idx, row in enumerate(table):
            col_map = _map_columns([c for c in row])
            if len(col_map) >= 3:  # At least 3 recognized columns = valid header
                header_idx = row_idx
                break
        if header_idx is None:
            continue
        # Detect consumption unit from column header text (H10 fix)
        consumption_unit = "kWh"
        cons_idx = col_map.get("consumption")
        if cons_idx is not None:
            header_cell = str(table[header_idx][cons_idx] or "").lower()
            if "litre" in header_cell or "liter" in header_cell:
                consumption_unit = "litres"
        # Parse data rows
        for row in table[header_idx + 1 :]:
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            def get(name: str) -> str | None:
                idx = col_map.get(name)
                if idx is None or idx >= len(row):
                    return None
                val = row[idx]
                return str(val).strip() if val is not None else None

            raw_energy = get("energy_type")
            energy_type = _classify_energy_type(raw_energy) if raw_energy else None

            # H1 audit: force litres for diesel regardless of header
            item_unit = "litres" if energy_type == "diesel" else consumption_unit

            items.append(LineItem(
                meter_id=get("meter_id"),
                energy_type=energy_type,
                period_from=get("period_from"),
                period_to=get("period_to"),
                consumption_kwh=clean_number(get("consumption")),
                unit_price=clean_number(get("unit_price")),
                amount_eur=clean_number(get("amount")),
                consumption_unit=item_unit,
            ))
    return items


def _extract_line_items_from_text(
    text: str,
    warnings: list[str],
) -> list[LineItem]:
    """Fallback: extract line items via regex when table extraction yields nothing."""
    warnings.append("Falling back to text-based line item extraction")
    items: list[LineItem] = []
    # Pattern: line_num  meter_id  energy_type_words  date  date  consumption  unit_price  amount
    pattern = (
        r"^\s*\d+\s+"                        # line number
        r"(\S+-\S+)\s+"                       # meter ID (e.g. E-ESSEN-PLANT-01)
        r"(.+?)\s+"                           # energy type (lazy)
        r"(\d{4}-\d{2}-\d{2})\s+"            # period from
        r"(\d{4}-\d{2}-\d{2})\s+"            # period to
        r"([\d,]+)\s+"                        # consumption
        r"([\d.]+)\s+"                        # unit price
        r"([\d,]+\.?\d*)$"                    # amount
    )
    for m in re.finditer(pattern, text, re.MULTILINE):
        raw_energy = m.group(2).strip()
        energy_type = _classify_energy_type(raw_energy)
        # H1 audit: force litres for diesel regardless of context
        item_unit = "litres" if energy_type == "diesel" else "kWh"
        items.append(LineItem(
            meter_id=m.group(1),
            energy_type=energy_type,
            period_from=m.group(3),
            period_to=m.group(4),
            consumption_kwh=clean_number(m.group(5)),
            unit_price=clean_number(m.group(6)),
            amount_eur=clean_number(m.group(7)),
            consumption_unit=item_unit,
        ))
    return items
