"""SAP CSV parser: parse energy consumption exports into ParseResult records.

Returns list[ParseResult] (one per CSV data row). Reuses ParseResult and
LineItem from pdf_parser.py for polymorphic pipeline integration.

Never raises. All errors wrapped in ParseResult.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
from pathlib import Path

from chemtrace.pdf_parser import LineItem, ParseResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# kWh per m3, H-gas average (DVGW G 260)
GAS_CALORIFIC_VALUE = 10.55

# Header keywords: field_name -> list of DE + EN keywords (lowercase)
HEADER_KEYWORDS: dict[str, list[str]] = {
    "site": ["werk", "standort", "plant", "site", "location"],
    "period": ["zeitraum", "periode", "monat", "period", "month"],
    "energy_type": ["energieart", "energietraeger", "energy_type", "energy_source"],
    "energy_amount": ["verbrauch", "menge", "consumption", "amount", "quantity"],
    "unit": ["einheit", "unit"],
    "total_eur": ["kosten", "betrag", "cost", "total"],
    "currency": ["waehrung", "currency"],
    "meter_id": ["zaehler_id", "meter_id", "meter"],
    "cost_center": ["kostenstelle", "cost_center"],
    "remarks": ["bemerkung", "kommentar", "remarks", "comment", "note"],
}

# Energy type keyword -> canonical name (case-insensitive substring match)
ENERGY_TYPE_MAP: dict[str, str] = {
    "strom": "electricity",
    "elektrizitaet": "electricity",
    "elektrisch": "electricity",
    "electricity": "electricity",
    "electric": "electricity",
    "power": "electricity",
    "erdgas": "natural_gas",
    "naturgas": "natural_gas",
    "natural gas": "natural_gas",
    "gas": "natural_gas",
    "diesel": "diesel",
    "kraftstoff": "diesel",
    "heizoel": "diesel",
    "fuel oil": "diesel",
    "heating oil": "diesel",
    "fernwaerme": "district_heating",
    "district heating": "district_heating",
}

# German month names -> MM (zero-padded)
MONTH_MAP_DE: dict[str, str] = {
    "januar": "01", "februar": "02", "maerz": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "dezember": "12",
}

# English month names + abbreviations -> MM
MONTH_MAP_EN: dict[str, str] = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08", "sep": "09",
    "oct": "10", "nov": "11", "dec": "12",
    # German abbreviations
    "maer": "03", "mrz": "03",
}

# Normalize unit strings to canonical form
UNIT_NORMALIZE: dict[str, str] = {
    "kwh": "kWh",
    "mwh": "MWh",
    "liter": "Liter",
    "litre": "Liter",
    "l": "Liter",
    "m3": "m3",
}

# All known header keywords flattened for _detect_headers
_ALL_HEADER_WORDS: set[str] = set()
for _kw_list in HEADER_KEYWORDS.values():
    _ALL_HEADER_WORDS.update(_kw_list)
# Add variants with special chars that might appear in cp1252
_ALL_HEADER_WORDS.update(["waehrung", "zaehler", "zaehler_id"])


# ---------------------------------------------------------------------------
# Encoding / delimiter / number format detection
# ---------------------------------------------------------------------------

def _detect_encoding(file_path: Path) -> str:
    """Detect file encoding. Returns codec name suitable for open().

    H-03: ALWAYS return 'utf-8-sig' for UTF-8 files (strips BOM automatically).
    """
    raw = file_path.read_bytes()

    # 1. Check BOM
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"

    # 2. Try UTF-8 strict
    try:
        raw.decode("utf-8", errors="strict")
        return "utf-8-sig"
    except UnicodeDecodeError:
        pass

    # 3. Try cp1252
    try:
        raw.decode("cp1252", errors="strict")
        return "cp1252"
    except UnicodeDecodeError:
        pass

    # 4. Fallback
    return "iso-8859-1"


def _detect_delimiter(sample_text: str) -> str:
    """Auto-detect CSV delimiter from sample text.

    H-02: Primary = character frequency (robust against German number commas).
    Secondary = csv.Sniffer (handles quoted fields but confused by commas in numbers).
    Default = ';'.
    """
    # Count occurrences in first 3 non-empty lines
    lines = [ln for ln in sample_text.splitlines() if ln.strip()][:3]
    if not lines:
        return ";"

    counts: dict[str, list[int]] = {";": [], ",": [], "\t": []}
    for line in lines:
        for ch in counts:
            counts[ch].append(line.count(ch))

    # Pick delimiter with highest consistent (minimum) count
    best_delim = ";"
    best_count = 0
    for ch, cnt_list in counts.items():
        if cnt_list and min(cnt_list) > 0 and min(cnt_list) > best_count:
            best_count = min(cnt_list)
            best_delim = ch

    # If counting is ambiguous (best_count == 0), try Sniffer
    if best_count == 0:
        try:
            dialect = csv.Sniffer().sniff(sample_text)
            if dialect.delimiter in (";", ",", "\t"):
                return dialect.delimiter
        except csv.Error:
            pass

    return best_delim


def _detect_number_format(data_rows: list[list[str]]) -> str:
    """Detect number format at FILE level (H-04: not per-number).

    Scans numeric-looking fields in first data row.
    Returns 'german' or 'english'.  Default: 'german'.
    """
    if not data_rows:
        return "german"

    for cell in data_rows[0]:
        cell = cell.strip()
        if not cell:
            continue
        # Only check cells that look numeric (digits + separators)
        cleaned = cell.replace(" ", "")
        if not re.match(r"^[\d.,]+$", cleaned):
            continue
        # Check last separator character
        last_comma = cleaned.rfind(",")
        last_dot = cleaned.rfind(".")
        if last_comma > last_dot:
            return "german"
        if last_dot > last_comma and last_comma == -1:
            # Dot present, no comma -> could be english decimal or german thousands
            # Check if digits after dot <= 3 (likely decimal)
            after_dot = cleaned[last_dot + 1:]
            if len(after_dot) <= 2:
                return "english"
    return "german"


def _parse_number(text: str, number_format: str) -> float | None:
    """Parse number using file-level format. Never raises."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        if number_format == "german":
            # German: dots are thousands sep, comma is decimal
            text = text.replace(".", "").replace(",", ".")
        else:
            # English: commas are thousands sep, dot is decimal
            text = text.replace(",", "")
        return float(text)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Header detection and column mapping
# ---------------------------------------------------------------------------

def _detect_headers(first_row: list[str]) -> bool:
    """Check if first row contains >=3 known header keywords."""
    matches = 0
    for cell in first_row:
        # Strip whitespace and BOM char (U+FEFF)
        cleaned = cell.strip().strip("\ufeff").lower()
        # Check against known keywords (exact match or underscore-normalized)
        normalized = cleaned.replace("\u00e4", "ae").replace("\u00f6", "oe").replace(
            "\u00fc", "ue"
        ).replace("\u00e9", "e")
        if cleaned in _ALL_HEADER_WORDS or normalized in _ALL_HEADER_WORDS:
            matches += 1
    return matches >= 3


def _map_columns(header_row: list[str]) -> dict[str, int]:
    """Map header keywords to column indices. Position-independent."""
    col_map: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        cleaned = cell.strip().strip("\ufeff").lower()
        # Normalize umlauts for matching
        normalized = cleaned.replace("\u00e4", "ae").replace("\u00f6", "oe").replace(
            "\u00fc", "ue"
        ).replace("\u00e9", "e")
        for field_name, keywords in HEADER_KEYWORDS.items():
            if field_name in col_map:
                continue  # First match wins per field
            for kw in keywords:
                if cleaned == kw or normalized == kw:
                    col_map[field_name] = idx
                    break
    return col_map


def _infer_columns(data_rows: list[list[str]]) -> dict[str, int] | None:
    """Infer column mapping from data patterns (headerless files).

    H-05: strict priority order.
    Returns None if <3 columns identifiable.
    """
    if not data_rows or not data_rows[0]:
        return None

    num_cols = len(data_rows[0])
    col_map: dict[str, int] = {}
    used: set[int] = set()

    # 1. Unit column: cell contains kWh, MWh, Liter, Litre, m3
    unit_keywords = {"kwh", "mwh", "liter", "litre", "l", "m3"}
    for idx in range(num_cols):
        cell = data_rows[0][idx].strip().lower()
        if cell in unit_keywords:
            col_map["unit"] = idx
            used.add(idx)
            break

    # 2. Energy type: cell contains Strom, Erdgas, Diesel, Electricity, Gas
    energy_keywords = {"strom", "erdgas", "diesel", "electricity", "gas",
                       "natural_gas", "fernwaerme", "district_heating"}
    for idx in range(num_cols):
        if idx in used:
            continue
        cell = data_rows[0][idx].strip().lower()
        if cell in energy_keywords:
            col_map["energy_type"] = idx
            used.add(idx)
            break

    # 3. Period: date patterns
    period_re = re.compile(
        r"^\d{4}-\d{2}$|^\d{2}\.\d{4}$|^\d{6}$|^P?\d{2}/\d{4}$",
    )
    for idx in range(num_cols):
        if idx in used:
            continue
        cell = data_rows[0][idx].strip()
        if period_re.match(cell):
            col_map["period"] = idx
            used.add(idx)
            break

    # 4. Site: remaining text column (no numbers, no unit/energy keywords)
    for idx in range(num_cols):
        if idx in used:
            continue
        cell = data_rows[0][idx].strip()
        if cell and not re.match(r"^[\d.,\s]+$", cell):
            cell_lower = cell.lower()
            if cell_lower not in unit_keywords and cell_lower not in energy_keywords:
                col_map["site"] = idx
                used.add(idx)
                break

    # 5 + 6. Consumption (largest numeric) and Cost (next numeric)
    numeric_cols: list[tuple[int, float]] = []
    for idx in range(num_cols):
        if idx in used:
            continue
        cell = data_rows[0][idx].strip()
        # Try parse as number (assume german for inference)
        val = _parse_number(cell, "german")
        if val is not None:
            numeric_cols.append((idx, abs(val)))

    numeric_cols.sort(key=lambda x: x[1], reverse=True)
    if len(numeric_cols) >= 1:
        col_map["energy_amount"] = numeric_cols[0][0]
        used.add(numeric_cols[0][0])
    if len(numeric_cols) >= 2:
        col_map["total_eur"] = numeric_cols[1][0]
        used.add(numeric_cols[1][0])

    if len(col_map) < 3:
        return None
    return col_map


# ---------------------------------------------------------------------------
# Period normalization
# ---------------------------------------------------------------------------

def _normalize_period(text: str) -> str | None:
    """Normalize period string to YYYY-MM. Returns None if unparseable.

    H-06: validate 2000 <= year <= 2030.
    """
    if not text:
        return None
    text = text.strip()

    def _validate_year_month(year: int, month: int) -> str | None:
        if not (2000 <= year <= 2030):
            logger.warning("Period year %d out of range [2000-2030]: %s", year, text)
            return None
        if not (1 <= month <= 12):
            return None
        return f"{year:04d}-{month:02d}"

    # YYYY-MM
    m = re.match(r"^(\d{4})-(\d{2})$", text)
    if m:
        return _validate_year_month(int(m.group(1)), int(m.group(2)))

    # MM.YYYY
    m = re.match(r"^(\d{2})\.(\d{4})$", text)
    if m:
        return _validate_year_month(int(m.group(2)), int(m.group(1)))

    # YYYYMM (compact)
    m = re.match(r"^(\d{4})(\d{2})$", text)
    if m:
        return _validate_year_month(int(m.group(1)), int(m.group(2)))

    # P01/2024 (SAP fiscal period)
    m = re.match(r"^P(\d{2})/(\d{4})$", text)
    if m:
        return _validate_year_month(int(m.group(2)), int(m.group(1)))

    # 01/2024
    m = re.match(r"^(\d{2})/(\d{4})$", text)
    if m:
        return _validate_year_month(int(m.group(2)), int(m.group(1)))

    # Month name (DE/EN) + year: "Januar 2024", "Jan 2024", "January 2024"
    m = re.match(r"^([A-Za-z\u00e4\u00f6\u00fc]+)\s+(\d{4})$", text)
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        # Normalize umlauts for lookup
        month_normalized = month_name.replace("\u00e4", "ae").replace(
            "\u00f6", "oe"
        ).replace("\u00fc", "ue")
        month_num = (
            MONTH_MAP_DE.get(month_name)
            or MONTH_MAP_DE.get(month_normalized)
            or MONTH_MAP_EN.get(month_name)
        )
        if month_num:
            return _validate_year_month(year, int(month_num))

    return None


# ---------------------------------------------------------------------------
# Energy type mapping
# ---------------------------------------------------------------------------

def _map_energy_type(text: str) -> str:
    """Map DE/EN energy keyword to canonical type. Case-insensitive substring match."""
    if not text:
        return "unknown"
    text_lower = text.strip().lower()
    # Normalize umlauts for matching
    text_normalized = text_lower.replace("\u00e4", "ae").replace(
        "\u00f6", "oe"
    ).replace("\u00fc", "ue")

    for keyword, canonical in ENERGY_TYPE_MAP.items():
        if keyword in text_lower or keyword in text_normalized:
            return canonical

    logger.warning("Unknown energy type: '%s' -> mapped to 'unknown'", text)
    return "unknown"


# ---------------------------------------------------------------------------
# Row conversion
# ---------------------------------------------------------------------------

def _safe_get(row: list[str], col_map: dict[str, int], field: str) -> str:
    """Safely get a cell value from row by column map. Returns '' if missing."""
    idx = col_map.get(field)
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def _normalize_unit(raw_unit: str) -> str:
    """Normalize unit string to canonical form."""
    if not raw_unit:
        return "kWh"
    key = raw_unit.strip().lower()
    # Handle m3 with superscript
    if key in ("\u00b3", "m\u00b3"):
        return "m3"
    return UNIT_NORMALIZE.get(key, raw_unit.strip())


def _row_to_parse_result(
    row: list[str],
    col_map: dict[str, int],
    csv_path: Path,
    row_index: int,
    number_format: str,
) -> ParseResult:
    """Convert a single CSV row to a ParseResult."""
    warnings: list[str] = []

    # Extract raw values
    site = _safe_get(row, col_map, "site")
    period_raw = _safe_get(row, col_map, "period")
    energy_type_raw = _safe_get(row, col_map, "energy_type")
    energy_amount_raw = _safe_get(row, col_map, "energy_amount")
    unit_raw = _safe_get(row, col_map, "unit")
    total_eur_raw = _safe_get(row, col_map, "total_eur")
    currency = _safe_get(row, col_map, "currency") or "EUR"
    meter_id = _safe_get(row, col_map, "meter_id") or None

    # Normalize
    period = _normalize_period(period_raw)
    if period is None and period_raw:
        warnings.append(f"Could not parse period: '{period_raw}'")

    energy_type = _map_energy_type(energy_type_raw)
    consumption_raw = _parse_number(energy_amount_raw, number_format)
    total_eur = _parse_number(total_eur_raw, number_format)
    unit = _normalize_unit(unit_raw)

    if consumption_raw is None and energy_amount_raw:
        warnings.append(f"Could not parse consumption: '{energy_amount_raw}'")
    if total_eur is None and total_eur_raw:
        warnings.append(f"Could not parse cost: '{total_eur_raw}'")

    # Unit conversion for downstream emission calculation
    consumption_kwh = consumption_raw
    if consumption_raw is not None:
        if unit == "MWh":
            consumption_kwh = consumption_raw * 1000.0
        elif unit == "m3":
            consumption_kwh = consumption_raw * GAS_CALORIFIC_VALUE

    # Build LineItem (H-12: set consumption_unit to actual unit from CSV)
    line_item = LineItem(
        meter_id=meter_id,
        energy_type=energy_type,
        period_from=period,
        period_to=period,
        consumption_kwh=consumption_kwh,
        unit_price=None,
        amount_eur=total_eur,
        consumption_unit=unit,
    )

    # Blob name for content text
    blob_name = f"{csv_path.name}:row_{row_index}"

    # Per-row unique hash (H-01: unique ChromaDB document ID)
    row_hash = hashlib.sha256(
        f"{csv_path.name}:row_{row_index}".encode()
    ).hexdigest()

    # Build data dict with SAME keys as pdf_parser for _build_record() compat
    data = {
        "raw_text": ";".join(row),
        "vendor_name": "SAP Export",
        "customer_name": None,
        "site_address": site or None,
        "address": None,
        "invoice_number": f"SAP-{csv_path.stem}-R{row_index}",
        "invoice_date": None,
        "currency": currency,
        "billing_period_from": period,
        "billing_period_to": period,
        "line_items": [line_item],
        "subtotal": None,
        "network_levies": None,
        "vat_amount": None,
        "total_amount": total_eur,
        "blob_name": blob_name,
        "row_hash": row_hash,
    }

    return ParseResult(success=True, data=data, warnings=warnings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_sap_csv(csv_path: Path) -> list[ParseResult]:
    """Parse a SAP CSV export. Returns one ParseResult per data row.

    Returns empty list if file is empty or fully unparseable.
    Never raises.
    """
    try:
        if not csv_path.exists():
            logger.warning("CSV file not found: %s", csv_path)
            return [ParseResult(success=False, data=None,
                                error=f"File not found: {csv_path.name}")]

        if csv_path.stat().st_size == 0:
            logger.warning("Empty CSV file: %s", csv_path)
            return []

        # Detect encoding
        encoding = _detect_encoding(csv_path)

        # Read file content
        content = csv_path.read_text(encoding=encoding)
        if not content.strip():
            return []

        # Detect delimiter
        delimiter = _detect_delimiter(content[:4096])

        # Parse all rows
        reader = csv.reader(content.splitlines(), delimiter=delimiter)
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]

        if not all_rows:
            return []

        # Detect headers
        has_headers = _detect_headers(all_rows[0])

        if has_headers:
            header_row = all_rows[0]
            data_rows = all_rows[1:]
            col_map = _map_columns(header_row)
        else:
            data_rows = all_rows
            col_map_or_none = _infer_columns(data_rows)
            if col_map_or_none is None:
                logger.warning(
                    "Cannot infer columns for headerless CSV: %s", csv_path.name
                )
                return [ParseResult(
                    success=False, data=None,
                    error=f"Cannot infer column mapping for {csv_path.name} "
                          f"(fewer than 3 columns identifiable)",
                )]
            col_map = col_map_or_none

        if not data_rows:
            logger.info("CSV has headers but no data rows: %s", csv_path.name)
            return []

        # Detect number format at file level (H-04)
        number_format = _detect_number_format(data_rows)

        # Convert each data row
        results: list[ParseResult] = []
        for idx, row in enumerate(data_rows):
            row_num = idx + 1  # Human-readable (1-based)
            # Skip rows with fewer columns than expected
            min_col = max(col_map.values()) + 1 if col_map else 0
            if len(row) < min_col:
                logger.warning(
                    "Row %d in %s has %d columns (expected >= %d), skipping",
                    row_num, csv_path.name, len(row), min_col,
                )
                continue

            result = _row_to_parse_result(row, col_map, csv_path, row_num, number_format)
            results.append(result)

        return results

    except Exception as exc:
        logger.error("Unexpected error parsing CSV %s: %s", csv_path, exc)
        return [ParseResult(
            success=False, data=None,
            error=f"Unexpected error: {exc}",
        )]
