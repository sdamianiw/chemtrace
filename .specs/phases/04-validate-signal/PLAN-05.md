# PLAN-05.md — SAP CSV Connector (FINAL AUDITED)
**Phase:** 04-validate-signal (Track 3, Week 4)
**Duration:** ~3.5h execution + 30min verify
**Budget:** Within Week 4 allocation (5.75h total)
**Gate:** SAP CSV parsed correctly + all tests pass + tag v0.5.0-sap-connector pushed
**Depends on:** Phase 04 Tracks 1+2 COMPLETE (v0.4.0-optimized, compute_analytics done, b90b9c3)
**SDD Gate:** Plan → Execute → Verify
**Audit:** Level 3 PASS | 12 findings (1 CRITICAL, 4 HIGH, 4 MEDIUM, 3 LOW) | All fixed
**Confidence:** 0.95

---

## 1. OBJECTIVE

Add SAP CSV parsing as second data input path to ChemTrace pipeline. German SMEs using SAP ECC or S/4HANA export energy consumption data as ad-hoc CSV files (SE16N, ALV grids, custom Z-reports). This connector broadens the addressable market beyond PDF-only invoices.

**Key constraint:** No standard CSV format exists in SAP for energy data. Parser must handle messy, variable, German-locale files.

---

## 2. ARCHITECTURAL DECISIONS

| ID | Decision | Source |
|---|---|---|
| D-021 | SAP CSV parser returns same ParseResult as PDF parser (polymorphic input) | CONTEXT_Phase04 TD-06 |
| D-022 | Auto-detection by file extension in etl.py, no abstract connector (YAGNI) | CONTEXT_Phase04 TD-06 |
| D-032 | cp1252 encoding primary (not ISO-8859-1). Detection: UTF-8 BOM → cp1252 → ISO-8859-1 | RESEARCH Task 3.6 |
| D-041 | parse_sap_csv returns list[ParseResult] (one per CSV row), not single ParseResult | Session 13 |
| D-042 | CO2_Faktor column ignored for MVP. ChemTrace always applies own emission factors. If column present, log info. | Audit H-07 |

---

## 3. SAP CSV FORMAT SPEC (validated by Task 3.6 research, confidence 0.91)

### 3.1 Encoding Detection Chain
```
1. Read first 4 bytes. Check for UTF-8 BOM (EF BB BF) → UTF-8
2. Try decode full file as UTF-8 strict → if success, UTF-8
3. Default → cp1252 (SAP codepage 1160)
4. Fallback → ISO-8859-1 (legacy non-Unicode SAP ECC)

CRITICAL: When UTF-8 detected (with or without BOM), use encoding='utf-8-sig'
(NOT 'utf-8'). utf-8-sig strips BOM automatically. Without this, BOM character
U+FEFF contaminates the first header field and breaks header detection.
```

### 3.2 Delimiter Auto-Detection
→ PRIMARY: Use `csv.Sniffer().sniff(sample)` on first 3 lines (handles quoting correctly)
→ FALLBACK: If csv.Sniffer raises csv.Error, count occurrences of ; , \t in first 3 non-empty lines
→ Delimiter = character with highest consistent count across lines
→ Default if ambiguous: semicolon (SAP_CONVERT_TO_CSV_FORMAT hardcodes it)

### 3.3 Number Format (FILE-LEVEL detection, not per-number)
→ Step 1: Scan ALL numeric-looking fields in first data row
→ Step 2: Detect file-level format:
  → If any field matches `\d+,\d+` (comma as last separator) → German format for entire file
  → If any field matches `\d+\.\d+` with no comma → English format for entire file
  → Default if ambiguous: German (SAP default for German locale)
→ Step 3: Apply detected format consistently to ALL numbers in file
→ German: remove dots (thousands), replace comma with dot (decimal)
→ English: remove commas (thousands), keep dot (decimal)

### 3.4 Headers
→ Detection: check if first row contains ≥3 known keywords from HEADER_KEYWORDS
→ CRITICAL: strip any BOM character from first field before keyword matching
→ If headers detected: use keyword matching to map columns (position-independent)
→ If headerless: use column inference (see Section 3.7)

### 3.5 Period Format Normalization
→ Normalize to YYYY-MM. Accept:
  "2024-01", "01.2024", "202401", "Jan 2024", "Januar 2024",
  "January 2024", "P01/2024", "01/2024"
→ Validation: 2000 ≤ year ≤ 2030. Outside range → None + warning.

### 3.6 Energy Type Keyword Mapping (bilingual, case-insensitive, substring match)

| DE keyword | EN keyword | ChemTrace canonical |
|---|---|---|
| Strom, Elektrizität, Elektrisch | Electricity, Electric, Power | electricity |
| Erdgas, Naturgas, Gas | Natural Gas, Gas | natural_gas |
| Diesel, Kraftstoff, Heizöl | Diesel, Fuel Oil, Heating Oil | diesel |
| Fernwärme | District Heating | district_heating |

→ Unknown → "unknown" + log warning

### 3.7 Headerless Column Inference (strict priority order)
1. **Unit column:** contains kWh, MWh, Liter, m³, or similar unit strings
2. **Energy type column:** contains Strom, Erdgas, Diesel, Electricity, Gas keywords
3. **Period column:** matches date-like patterns (digits with separators, month names)
4. **Site column:** remaining text column with no numbers
5. **Consumption column:** numbers (largest magnitude among remaining numeric columns)
6. **Cost column:** remaining numeric column

→ Require ≥3 columns identified → proceed
→ <3 columns → ParseResult(success=False, error="Cannot infer column mapping")

### 3.8 Expected Header Keywords (bilingual)

| DE Header | EN Header | ChemTrace field | Required |
|---|---|---|---|
| Werk, Standort, Plant | Plant, Site, Location | site | YES |
| Zeitraum, Periode, Monat | Period, Month | period | YES |
| Energieart, Energieträger | Energy_Type, Energy_Source | energy_type | YES |
| Verbrauch, Menge | Consumption, Amount, Quantity | energy_amount | YES |
| Einheit | Unit | unit | YES |
| Kosten, Betrag | Cost, Amount, Total | total_eur | YES |
| Waehrung, Währung | Currency | currency | NO (default EUR) |
| Zaehler_ID, Zähler | Meter_ID, Meter | meter_id | NO |
| Kostenstelle | Cost_Center | cost_center | NO |
| Bemerkung, Kommentar | Remarks, Comment, Note | remarks | NO |
| CO2_Faktor | Emission_Factor | (ignored, log info) | NO (D-042) |

---

## 4. SYNTHETIC SAMPLE CSV

File 1: `data/sample_sap/energy_export_essen_2024.csv`
Encoding: cp1252 (intentionally NOT UTF-8, to test encoding detection)

```
Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung;Zaehler_ID;Bemerkung
Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR;DE-ESS-001;Hauptzähler Produktion
Essen Blending;2024-01;Erdgas;310800,0;kWh;24864,00;EUR;DE-ESS-G01;Kessel + Trockner
Essen Blending;2024-02;Diesel;8500,0;Liter;13600,00;EUR;;Interne Logistik
Essen Blending;2024-03;Strom;420000,0;kWh;108096,61;EUR;DE-ESS-001;Hauptzähler Produktion
```

File 2: `data/sample_sap/energy_export_headerless.csv` (also cp1252, no header row)
```
Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR
Essen Blending;2024-02;Erdgas;285000,0;kWh;22800,00;EUR
```

File 3: `data/sample_sap/energy_export_bom.csv` (UTF-8 with BOM, English numbers)
```
[BOM: EF BB BF]Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung
Essen Blending;2024-01;Strom;478800.0;kWh;116461.40;EUR
```

→ Create via `scripts/generate_sample_sap.py` to ensure correct encodings.

---

## 5. TASK BREAKDOWN (3 tasks)

### Task 1: sap_parser.py + synthetic samples (Claude Code, ~1.5h)
→ Create `src/chemtrace/sap_parser.py`
→ Create `scripts/generate_sample_sap.py` + run it → 3 sample CSVs
→ Pre-flight: read pdf_parser.py, etl.py, vector_store.py, config.py

### Task 2: Unit tests + etl.py integration (Claude Code, ~1.5h)
→ Create `tests/test_sap_parser.py` (≥14 tests)
→ Modify `src/chemtrace/etl.py` (add CSV loop after PDF loop)
→ Run ALL tests (80 existing + 14+ new = 94+, zero regressions)

### Task 3: Docker e2e + README + commit (Manual + Git, ~30min)
→ Docker test: parse SAP CSV → ask → correct answer
→ README: add CSV support section
→ Commit + tag v0.5.0-sap-connector + push

---

## 6. CLAUDE CODE EXECUTION PROMPT (FINAL — Tasks 1+2 combined)

```
Before touching any file, reason step by step about:
1. What the root cause is (pipeline only accepts PDFs, SMEs need CSV support)
2. What the minimal change solves it (new parser module + second glob loop in etl.py)
3. What could break downstream (existing PDF parsing must not regress)
Then apply the fix.

Read these files first (PRE-FLIGHT, mandatory — do NOT skip):
→ src/chemtrace/pdf_parser.py (ParseResult + LineItem exact fields)
→ src/chemtrace/etl.py (current PDF glob pattern, record processing, pdf_hash usage)
→ src/chemtrace/vector_store.py (line ~41: uses r["pdf_hash"] as ChromaDB document ID)
→ src/chemtrace/config.py (EMISSION_FACTORS structure, Config class)
→ src/chemtrace/parser_patterns.py (energy type keywords reference)
→ src/chemtrace/utils.py (build_content, compute_pdf_hash functions)
→ tests/test_pdf_parser.py (testing patterns, fixture usage)

GOAL: Add SAP CSV parsing as second data input to ChemTrace pipeline.

================================================================
TASK A: Create src/chemtrace/sap_parser.py
================================================================

New module. Returns list[ParseResult] (same dataclass from pdf_parser.py).
Each CSV row = 1 ParseResult = 1 ChromaDB record.

VERIFIED FACTS FROM DIAGNOSTICS (do not assume, these are confirmed):
→ ParseResult fields: success (bool), data (dict|None), warnings (list[str]), error (str|None)
→ LineItem fields: meter_id, energy_type, period_from, period_to,
  consumption_kwh, unit_price, amount_eur, consumption_unit (str, default "kWh")
→ etl.py uses: config.input_dir.glob("*.pdf") — NOT iterdir()
→ etl.py stores: "pdf_hash" key in record dict → used by vector_store.py as ChromaDB ID
→ vector_store.py line 41: ids = [r["pdf_hash"] for r in records]
→ Current test count: 80 tests

CRITICAL CONSTRAINTS:

1. DOCUMENT ID (H-01 fix): Each CSV row MUST get a UNIQUE ID.
   Generate: hashlib.sha256(f"{csv_path.name}:row_{row_index}".encode()).hexdigest()
   Store under key "pdf_hash" in the record dict — YES the key says "pdf" but
   vector_store.py line 41 uses r["pdf_hash"] as ChromaDB document ID.
   Do NOT rename the key. Do NOT modify vector_store.py.

2. CONSUMPTION_UNIT (H-12 fix): LineItem has a consumption_unit field (default "kWh").
   Set it to the ACTUAL unit from CSV: "kWh", "Liter", "MWh", "m³".
   Do NOT leave default "kWh" for diesel rows (unit is "Liter").

Functions to implement:

def parse_sap_csv(csv_path: Path) → list[ParseResult]:
    """Main entry point. One ParseResult per data row.
    Returns empty list if file is empty or fully unparseable."""

def _detect_encoding(file_path: Path) → str:
    """Detect file encoding.
    1. Check first 3 bytes for UTF-8 BOM (EF BB BF) → return 'utf-8-sig'
    2. Try decode full content as UTF-8 strict → if success, return 'utf-8-sig'
    3. Default → return 'cp1252'
    4. If cp1252 decode fails → return 'iso-8859-1'
    CRITICAL (H-03): ALWAYS return 'utf-8-sig' for UTF-8 files (not 'utf-8').
    utf-8-sig strips BOM automatically. Without this, BOM char U+FEFF
    contaminates first header field → header detection breaks."""

def _detect_delimiter(sample_text: str) → str:
    """Auto-detect CSV delimiter.
    PRIMARY (H-02): Use csv.Sniffer().sniff(sample_text).delimiter
    This handles quoted fields correctly (semicolons inside quotes).
    FALLBACK: If csv.Sniffer raises csv.Error:
      count occurrences of ; , \\t in first 3 non-empty lines
      highest consistent count wins
    DEFAULT if ambiguous or all zero: ';' (SAP hardcodes semicolon)"""

def _detect_number_format(data_rows: list[list[str]]) → str:
    """Detect number format at FILE level, not per-number (H-04 fix).
    Scan numeric-looking fields in first data row:
    → If any field has comma as last separator (e.g., '478800,0') → 'german'
    → If any field has dot as last separator with no comma → 'english'
    → Default if ambiguous: 'german' (SAP German locale default)
    Returns: 'german' or 'english'
    This is called ONCE and the result is passed to all _parse_number calls."""

def _parse_number(text: str, number_format: str) → float | None:
    """Parse number using the file-level format detected by _detect_number_format.
    DO NOT auto-detect format per number — use the format parameter.
    German: remove dots (thousands), replace comma with dot (decimal)
    English: remove commas (thousands), keep dot (decimal)
    Returns None if text is empty or unparseable. Never raise."""

def _detect_headers(first_row: list[str]) → bool:
    """Check if first row contains ≥3 known header keywords.
    Keywords (case-insensitive): Werk, Zeitraum, Energieart, Verbrauch,
    Einheit, Kosten, Waehrung, Plant, Period, Energy, Consumption,
    Unit, Cost, Currency, Standort, Location, Bemerkung, Meter, Remarks.
    IMPORTANT: Strip whitespace and any BOM char from each field before matching."""

def _map_columns(header_row: list[str]) → dict[str, int]:
    """Map header keywords to column indices. Position-independent.
    Returns {field_name: col_index} where field_name is one of:
    'site', 'period', 'energy_type', 'energy_amount', 'unit',
    'total_eur', 'currency', 'meter_id', 'cost_center', 'remarks'
    Keyword mapping (case-insensitive, first match wins):
      site: Werk, Standort, Plant, Site, Location
      period: Zeitraum, Periode, Monat, Period, Month
      energy_type: Energieart, Energieträger, Energy_Type, Energy_Source
      energy_amount: Verbrauch, Menge, Consumption, Amount, Quantity
      unit: Einheit, Unit
      total_eur: Kosten, Betrag, Cost, Total
      currency: Waehrung, Währung, Currency
      meter_id: Zaehler_ID, Zähler, Meter_ID, Meter
      cost_center: Kostenstelle, Cost_Center
      remarks: Bemerkung, Kommentar, Remarks, Comment, Note"""

def _infer_columns(data_rows: list[list[str]]) → dict[str, int] | None:
    """Infer column mapping from data patterns (headerless files).
    Use this STRICT PRIORITY ORDER (H-05 fix):
    1. Unit column: cell contains kWh, MWh, Liter, Litre, m³, m3
    2. Energy type: cell contains Strom, Erdgas, Diesel, Electricity, Gas
    3. Period: cell matches date patterns (YYYY-MM, MM.YYYY, YYYYMM, month names)
    4. Site: remaining text column (no numbers, no unit/energy keywords)
    5. Consumption: largest-magnitude numeric column among remaining
    6. Cost: next numeric column after consumption
    Require ≥3 columns identified → return mapping dict.
    <3 columns identifiable → return None."""

def _normalize_period(text: str) → str | None:
    """Normalize period string to YYYY-MM. Accepts 8+ formats:
    '2024-01' → '2024-01'
    '01.2024' → '2024-01'
    '202401' → '2024-01'
    'Jan 2024' → '2024-01'
    'Januar 2024' → '2024-01'
    'January 2024' → '2024-01'
    'P01/2024' → '2024-01'
    '01/2024' → '2024-01'
    Validate (H-06 fix): 2000 ≤ year ≤ 2030. Outside range → None + warning.
    Returns None if unparseable."""

def _map_energy_type(text: str) → str:
    """Map DE/EN energy keyword to ChemTrace canonical type.
    Case-insensitive SUBSTRING match (e.g., 'Stromverbrauch' → 'electricity').
    Mapping:
      Strom, Elektrizität, Elektrisch, Electricity, Electric, Power → electricity
      Erdgas, Naturgas, Natural Gas → natural_gas
      Diesel, Kraftstoff, Heizöl, Fuel Oil, Heating Oil → diesel
      Fernwärme, District Heating → district_heating
    NOTE: 'Gas' alone also maps to natural_gas. If this causes false positives
    in production, tighten to require 'Erdgas' or 'Natural Gas'.
    Unmatched → 'unknown' + log warning."""

def _generate_content_text(row, col_map, csv_path, row_idx, number_format) → str:
    """Generate human-readable text for ChromaDB embedding + RAG retrieval.
    PRE-FLIGHT: Read how utils.build_content() generates content text for PDFs.
    Match that style for consistent RAG retrieval quality.
    Example output:
    'SAP Export: Essen Blending, January 2024.
     Electricity consumption: 478,800.0 kWh. Cost: EUR 116,461.40.
     Meter: DE-ESS-001. Source: energy_export_essen_2024.csv row 1.'
    Include blob_name and all available fields."""

def _row_to_parse_result(row, col_map, csv_path, row_index, number_format) → ParseResult:
    """Convert single CSV row to ParseResult.
    blob_name: '{csv_filename}:row_{N}' (N starts at 1, human-readable)
    invoice_number: 'SAP-{csv_stem}-R{N}'
    vendor_name: 'SAP Export' (fixed)
    currency: from CSV column, default 'EUR' if missing
    
    LineItem construction:
      meter_id = from CSV or None
      energy_type = _map_energy_type(csv_value)
      consumption_kwh = parsed number (NOTE: even for Liter, store raw value here)
      consumption_unit = ACTUAL unit from CSV ('kWh', 'Liter', 'MWh', 'm³')
      amount_eur = parsed cost
      unit_price = None (not calculable from SAP export)
    
    Unit handling for downstream emission calculation:
      kWh → use emission factor directly
      Liter/Litre/l → diesel factor (tCO2e/litre)
      MWh → convert to kWh (*1000) before storing in consumption_kwh
      m³ (gas) → convert to kWh using GAS_CALORIFIC_VALUE before storing
    """

Constants at module level:
→ HEADER_KEYWORDS: dict mapping field names to lists of DE+EN keywords
→ ENERGY_TYPE_MAP: dict mapping lowercase keywords to canonical types
→ MONTH_MAP_DE: {"januar": "01", "februar": "02", "märz": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "dezember": "12"}
→ MONTH_MAP_EN: {"january": "01", ..., "december": "12"}
  Also abbreviations: {"jan": "01", ..., "dec": "12", "mär": "03", "mrz": "03"}
→ GAS_CALORIFIC_VALUE = 10.55  # kWh/m³, H-gas average (DVGW G 260) [Pendiente verificación]
→ UNIT_NORMALIZE: {"kwh": "kWh", "mwh": "MWh", "liter": "Liter", "litre": "Liter",
    "l": "Liter", "m³": "m³", "m3": "m³"}

Graceful error handling (NEVER crash, NEVER raise):
→ Empty file → return empty list + log warning
→ File with only headers, no data → return empty list
→ Row with fewer columns than expected → skip row, log warning, continue
→ Unparseable number → set to None, log warning, continue
→ Unknown energy type → set to "unknown", log warning, continue
→ <3 columns identifiable (headerless) → return [ParseResult(success=False, error=...)]

================================================================
TASK B: Create synthetic CSV samples
================================================================

Create scripts/generate_sample_sap.py that generates all 3 test files.
This ensures encodings are byte-perfect (don't rely on editor settings).

The script should:
1. Create data/sample_sap/ directory if it doesn't exist
2. Write File 1 (cp1252, semicolon, German numbers, with headers)
3. Write File 2 (cp1252, semicolon, German numbers, NO headers)
4. Write File 3 (UTF-8 with BOM, semicolon, English numbers, with headers)

File 1: data/sample_sap/energy_export_essen_2024.csv
Encoding: cp1252. Content:
Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung;Zaehler_ID;Bemerkung
Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR;DE-ESS-001;Hauptzähler Produktion
Essen Blending;2024-01;Erdgas;310800,0;kWh;24864,00;EUR;DE-ESS-G01;Kessel + Trockner
Essen Blending;2024-02;Diesel;8500,0;Liter;13600,00;EUR;;Interne Logistik
Essen Blending;2024-03;Strom;420000,0;kWh;108096,61;EUR;DE-ESS-001;Hauptzähler Produktion

File 2: data/sample_sap/energy_export_headerless.csv
Encoding: cp1252. NO header row:
Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR
Essen Blending;2024-02;Erdgas;285000,0;kWh;22800,00;EUR

File 3: data/sample_sap/energy_export_bom.csv
Encoding: UTF-8 with BOM (write bytes EF BB BF first). English numbers:
Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung
Essen Blending;2024-01;Strom;478800.0;kWh;116461.40;EUR

Run the script after creating it:
  PYTHONPATH="C:\Chemtrace\src" python scripts/generate_sample_sap.py
Verify files exist and check encoding:
  file data/sample_sap/*.csv

================================================================
TASK C: Create tests/test_sap_parser.py
================================================================

Minimum 14 test cases. Use tmp_path fixture for test CSV files with
specific encodings. Group tests logically.

# === Encoding Detection ===
def test_detect_encoding_utf8_bom(tmp_path):
    """File with BOM → 'utf-8-sig'"""

def test_detect_encoding_cp1252(tmp_path):
    """File with ä/ö/ü chars in cp1252 → 'cp1252'"""

def test_detect_encoding_utf8_no_bom(tmp_path):
    """Pure ASCII or valid UTF-8 without BOM → 'utf-8-sig'"""

# === Delimiter Detection ===
def test_detect_delimiter_semicolon():
    """Standard SAP semicolon-delimited → ';'"""

def test_detect_delimiter_comma():
    """Comma-delimited lines → ','"""

def test_detect_delimiter_tab():
    """Tab-delimited lines → '\\t'"""

# === Number Format Detection + Parsing ===
def test_detect_number_format_german():
    """Row with '478800,0' → 'german'"""

def test_detect_number_format_english():
    """Row with '478800.0' → 'english'"""

def test_parse_number_german_with_thousands():
    """'1.234,56' with format='german' → 1234.56"""

def test_parse_number_german_no_thousands():
    """'234,56' with format='german' → 234.56"""

def test_parse_number_german_integer():
    """'478800,0' with format='german' → 478800.0"""

def test_parse_number_english():
    """'1,234.56' with format='english' → 1234.56"""

def test_parse_number_invalid():
    """'abc' → None"""

# === Period Normalization ===
def test_normalize_period_iso():
    """'2024-01' → '2024-01'"""

def test_normalize_period_german():
    """'01.2024' → '2024-01'"""

def test_normalize_period_compact():
    """'202401' → '2024-01'"""

def test_normalize_period_month_de():
    """'Januar 2024' → '2024-01'"""

def test_normalize_period_month_en():
    """'January 2024' → '2024-01'"""

def test_normalize_period_sap_fiscal():
    """'P01/2024' → '2024-01'"""

def test_normalize_period_out_of_range():
    """Year < 2000 or > 2030 → None"""

# === Energy Type Mapping ===
def test_map_energy_type_strom():
    """'Strom' → 'electricity'"""

def test_map_energy_type_erdgas():
    """'Erdgas' → 'natural_gas'"""

def test_map_energy_type_diesel():
    """'Diesel' → 'diesel'"""

def test_map_energy_type_substring():
    """'Stromverbrauch' → 'electricity' (substring match)"""

def test_map_energy_type_unknown():
    """'Dampf' → 'unknown'"""

# === Full Parse (Integration) ===
def test_parse_sap_csv_happy_path(tmp_path):
    """Parse synthetic CSV with headers → 4 ParseResults with correct values.
    Verify: results[0].data has correct site, period, energy_type, amounts."""

def test_parse_sap_csv_headerless(tmp_path):
    """Parse headerless CSV → columns inferred, 2 results, values correct."""

def test_parse_sap_csv_bom(tmp_path):
    """Parse UTF-8 BOM CSV → first header clean (no U+FEFF), English numbers parsed."""

def test_parse_sap_csv_empty(tmp_path):
    """Empty file → empty list returned, no exception."""

def test_parse_sap_csv_missing_columns(tmp_path):
    """Row with fewer columns → row skipped, others still parsed."""

def test_parse_sap_csv_blob_name(tmp_path):
    """blob_name follows '{filename}:row_{N}' format, N starts at 1."""

def test_parse_sap_csv_unique_ids(tmp_path):
    """4 rows → 4 different pdf_hash values (unique ChromaDB IDs)."""

def test_parse_sap_csv_consumption_unit(tmp_path):
    """Diesel row has consumption_unit='Liter', not default 'kWh'."""

def test_parse_sap_csv_values_match_pdf():
    """SAP electricity Jan 2024 = 478,800 kWh (matches PDF invoice value)."""

================================================================
TASK D: Modify src/chemtrace/etl.py (MINIMAL CHANGE)
================================================================

VERIFIED: etl.py uses config.input_dir.glob("*.pdf"), NOT iterdir().
Do NOT change the existing PDF glob or PDF processing loop.
Do NOT refactor. Only ADD a second loop for CSV files.

Changes:
1. Add import at top: from chemtrace.sap_parser import parse_sap_csv
2. Add SECOND loop AFTER the entire PDF processing block:

    # === SAP CSV Processing (added for v0.5.0) ===
    csv_files = sorted(config.input_dir.glob("*.csv"))
    for csv_path in csv_files:
        csv_results = parse_sap_csv(csv_path)
        for result in csv_results:
            if result.success:
                # Process the result using the SAME pattern as PDF records.
                # The record dict must include "pdf_hash" key with the per-row hash
                # (already set by sap_parser in the ParseResult).
                # Apply emission calculation, build content text, append to records.
                # Follow the exact same flow as the PDF processing block above.
            else:
                # Log error using same pattern as PDF errors.
                pass

3. CRITICAL: The per-row hash from sap_parser must be placed under key "pdf_hash"
   in the record dict. vector_store.py expects r["pdf_hash"] as document ID.
   Do NOT call compute_pdf_hash(csv_path) — that would give all rows the same hash.
   Instead, extract the hash that sap_parser already computed and stored in ParseResult.

4. HOW to get the per-row hash into the record dict: Check how the PDF processing
   block creates the record dict. It likely does something like:
     record["pdf_hash"] = compute_pdf_hash(pdf_path)
   For CSV rows, replace with:
     record["pdf_hash"] = result.data.get("row_hash") or compute_fallback_hash(...)
   The exact key depends on how you store the hash in ParseResult.data within sap_parser.

5. IMPORTANT: Ensure invoices_summary_v2.csv (in output/) is NOT in input_dir.
   The glob only searches config.input_dir, so this should be safe if output/ != input_dir.
   Verify during pre-flight by checking config.input_dir path.

After etl.py change, run ALL existing tests:
  PYTHONPATH="C:\Chemtrace\src" python -m pytest tests/ -v
Zero regressions. 80 existing tests must still pass. If ANY fails → STOP and diagnose.

================================================================
VERIFICATION (after all tasks)
================================================================

1. Run SAP parser tests:
   PYTHONPATH="C:\Chemtrace\src" python -m pytest tests/test_sap_parser.py -v
   → All 14+ tests pass

2. Run ALL tests (regression check):
   PYTHONPATH="C:\Chemtrace\src" python -m pytest tests/ -v
   → 94+ tests pass (80 existing + 14+ new), zero failures

3. Smoke test:
   PYTHONPATH="C:\Chemtrace\src" python -c "
from pathlib import Path
from chemtrace.sap_parser import parse_sap_csv
results = parse_sap_csv(Path('data/sample_sap/energy_export_essen_2024.csv'))
print(f'Parsed {len(results)} rows')
assert len(results) == 4, f'Expected 4, got {len(results)}'
hashes = set()
for r in results:
    if r.success:
        h = r.data.get('row_hash') or r.data.get('pdf_hash', 'NO_HASH')
        hashes.add(h)
        items = r.data['line_items']
        for item in items:
            print(f'  {item.energy_type}: {item.consumption_kwh} {item.consumption_unit}')
assert len(hashes) == 4, f'Expected 4 unique hashes, got {len(hashes)}'
print('ALL OK — 4 rows, 4 unique IDs')
"

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

---

## 7. MANUAL VERIFICATION (Task 3, post-Claude Code)

```bash
# 1. Close Cursor (free RAM for Docker)
# 2. Start Docker
docker compose up -d

# 3. Parse SAP CSV
docker compose run --rm chemtrace python -m chemtrace parse data/sample_sap/

# 4. Check status (should show increased document count)
docker compose run --rm chemtrace python -m chemtrace status

# 5. Ask about SAP data
docker compose run --rm chemtrace python -m chemtrace ask "What was electricity consumption in January 2024?"
# Expected: answer cites both PDF and SAP sources

# 6. Ask SAP-specific data
docker compose run --rm chemtrace python -m chemtrace ask "What was the natural gas cost in January 2024?"
# Expected: EUR 24,864.00 from SAP export

# 7. Export and verify
docker compose run --rm chemtrace python -m chemtrace export output/sap_test.csv
# Check CSV has SAP rows with correct values

# 8. Shutdown
docker compose down
```

**README update (brief):**
→ Add "Supports SAP CSV energy exports (auto-detected)" to feature list
→ Add `chemtrace parse data/sample_sap/` to Quick Start examples
→ Note: "SAP CSV format: semicolon-delimited, cp1252 or UTF-8 encoding, German number format supported"

**Git (from Git Bash T1):**
```bash
cd /c/Chemtrace
grep -rn "secret\|password\|key\|token" src/chemtrace/sap_parser.py | grep -v "keyword"
git add -A
git status
git diff --cached --stat
git commit -m "feat: SAP CSV connector with auto-detection and bilingual parsing (v0.5.0)"
git tag v0.5.0-sap-connector
git push origin main --tags
```

---

## 8. RISKS

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| etl.py record processing differs from assumption | Medium | High | Pre-flight reads exact code. Claude Code adapts. |
| ParseResult.data key for hash differs | Medium | Medium | Claude Code inspects during pre-flight. Adapts key name. |
| Headerless inference false-positives | Medium | Low | Require ≥3 matches. Log when inference used. |
| German number regex misses edge cases | Medium | Low | 7 unit tests for numbers. Extend as discovered. |
| Existing tests break after etl.py change | Low | High | Full test suite post-modification. STOP if failures. |
| Time overrun (>3.5h) | Medium | Low | 80/20: defer headerless + BOM to v0.5.1. Core = headers + German numbers + semicolon. |

---

## 9. DEFINITION OF DONE

| # | Criterion | Verification |
|---|---|---|
| DoD-01 | sap_parser.py imports cleanly | `python -c "from chemtrace.sap_parser import parse_sap_csv"` |
| DoD-02 | 3 synthetic CSVs exist with correct encodings | `file data/sample_sap/*.csv` |
| DoD-03 | parse_sap_csv returns 4 ParseResults from main sample | Smoke test |
| DoD-04 | 4 UNIQUE ChromaDB IDs (not 1) | Smoke test hash check |
| DoD-05 | ≥14 unit tests pass | `pytest tests/test_sap_parser.py -v` |
| DoD-06 | Zero regressions (80 existing tests pass) | `pytest tests/ -v` |
| DoD-07 | German numbers: 478800,0 → 478800.0 | Unit test |
| DoD-08 | Period: ≥6 formats normalized | Unit tests |
| DoD-09 | Headerless CSV parsed via inference | Unit test |
| DoD-10 | BOM CSV: first header clean, parsed correctly | Unit test |
| DoD-11 | Diesel row: consumption_unit = "Liter" | Unit test |
| DoD-12 | Docker e2e: parse SAP → ask → correct answer | Manual test |
| DoD-13 | Tag v0.5.0-sap-connector pushed | `git log` |

---

## 10. AUDIT TRAIL

| ID | Severity | Finding | Status |
|---|---|---|---|
| H-01 | CRÍTICO | ChromaDB row ID collision (all rows same file hash) | ✅ FIXED: per-row hash under "pdf_hash" key |
| H-02 | ALTO | csv.Sniffer missing from Claude Code prompt | ✅ FIXED: added to _detect_delimiter |
| H-03 | ALTO | BOM not stripped (utf-8 vs utf-8-sig) | ✅ FIXED: utf-8-sig specified everywhere |
| H-04 | ALTO | Number format per-number vs per-file ambiguity | ✅ FIXED: _detect_number_format + _parse_number(text, fmt) |
| H-10 | ALTO | etl.py uses glob("*.pdf") not iterdir() | ✅ FIXED: second glob loop, not elif |
| H-11 | ALTO | vector_store uses r["pdf_hash"] hardcoded | ✅ FIXED: store under "pdf_hash" key |
| H-12 | MEDIO | LineItem.consumption_unit not set for Liter/m³ | ✅ FIXED: set actual unit in prompt |
| H-05 | MEDIO | Headerless priority order missing from prompt | ✅ FIXED: 6-step priority in _infer_columns |
| H-06 | MEDIO | Year range validation missing | ✅ FIXED: 2000-2030 in _normalize_period |
| H-07 | MEDIO | CO2_Faktor dropped without decision | ✅ FIXED: D-042 documented |
| H-08 | BAJO | m³ conversion lacks DVGW source | ✅ FIXED: GAS_CALORIFIC_VALUE with source |
| H-09 | BAJO | Budget zero buffer | Accepted: 80/20 fallback defined |

**Level 3 Audit: PASS**
**Confidence: 0.95**

---

*Plan generated: 2026-04-02 | Session 13 | Level 3 audit (3 roles) + diagnostic validation + 12 findings fixed | Budget: 3.5h execute + 30min verify*
