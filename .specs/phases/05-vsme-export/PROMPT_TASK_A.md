# PROMPT — PLAN-06 Task A: VSME B3 Export Module
# Re-audited: 2026-04-02 s16 | Fixes: F-01 (sheet count), F-02 (unit column)

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\Chemtrace\src" python ...
PYTHONPATH="C:\Chemtrace\src" pytest ...
This is a known workaround (pip install -e . fails on this machine).

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
→ src/chemtrace/cli.py (current export implementation)
→ src/chemtrace/config.py (Config dataclass, output_dir, paths)
→ src/chemtrace/etl.py (PipelineResult, CSV columns)
→ output/invoices.csv (if exists, check column names)
→ data/emission_factors/factors.json (energy_type canonical values)
→ .skills/PROMPT_CONTRACT.md

AUDIT CORRECTIONS (from fresh Level 3 re-audit):
→ FIX F-01: Template has 13 sheets (not 14 as earlier specs stated). Do NOT validate or assert sheet count.
→ FIX F-02: CSV may or may not have a 'unit' column. Do NOT depend on it. Use energy_type to infer units: electricity/natural_gas → energy_amount is kWh, diesel → energy_amount is litres. Always read actual CSV columns before coding.

GOAL: Create VSME B3 XLSX export module + tests.

================================================================
TASK A1: Copy VSME template to data/vsme_templates/
================================================================

Copy the file from data source. The template file MUST be at:
  data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx

NOTE: Sebas will manually place the BLANK template file before execution.
The file MUST be the BLANK template (631KB), NOT the pre-filled mock-up sample (640KB).
Download from: https://www.efrag.org/en/vsme-digital-template-and-xbrl-taxonomy
Select: "VSME Digital Template Version 1.2.0 (XLSX, 631KB)"
Do NOT use: "Mock-up example of pre-filled VSME Digital Template Version 1.2.0 (XLSX, 640KB)"
Create the directory if it doesn't exist:
  mkdir -p data/vsme_templates

================================================================
TASK A2: Create src/chemtrace/vsme_export.py
================================================================

Module with ONE public function:

```python
def export_vsme_b3(
    csv_path: Path,
    template_path: Path,
    output_path: Path,
    turnover: float | None = None,
) -> VSMEExportResult:
```

@dataclass VSMEExportResult:
    output_path: Path
    records_count: int
    period_start: str          # YYYY-MM
    period_end: str            # YYYY-MM
    total_energy_mwh: float
    scope1_tco2eq: float
    scope2_tco2eq: float
    turnover_eur: float | None
    warnings: list[str]

IMPLEMENTATION LOGIC (step by step):

1. READ CSV:
   → pd.read_csv(csv_path) with appropriate types
   → Validate required columns exist: energy_type, energy_amount, emissions_tco2
   → If CSV empty or missing → raise FileNotFoundError with clear message

2. AGGREGATE (monthly → annual):
   → Group by energy_type
   → For each group: sum energy_amount, sum emissions_tco2
   → Detect period range: min(period), max(period)
   → If periods span > 12 months → append warning

3. CONVERT UNITS (kWh/litres → MWh):
   → electricity_mwh = electricity_kwh / 1000
   → natural_gas_mwh = gas_kwh / 1000
   → diesel_mwh = diesel_litres * 0.010033  # EFRAG NCV: 43 TJ/Gg, density 0.84 kg/L
   → total_mwh = electricity_mwh + natural_gas_mwh + diesel_mwh
   → For unknown energy types: log warning, skip MWh, keep emissions
   → IMPORTANT (FIX F-02): Determine unit from energy_type, NOT from a 'unit' column.
     electricity → kWh, natural_gas → kWh, diesel → litres.

4. CLASSIFY EMISSIONS:
   → scope1 = sum(emissions where type in ['natural_gas', 'diesel'])
   → scope2 = sum(emissions where type == 'electricity')

5. LOAD TEMPLATE:
   → shutil.copy(template_path, output_path)  # Work on copy, never modify original
   → wb = openpyxl.load_workbook(output_path)

6. WRITE TO NAMED RANGES (use helper function):
   Helper: _write_named_range(wb, name: str, value)
   → Gets DefinedName from wb.defined_names[name]
   → Extracts (sheet_title, cell_range) from .destinations
   → Writes value to wb[sheet_title][cell_range]
   → If named range not found → log warning, skip (forward compatibility)

   Cells to write:
   → TotalEnergyConsumption → total_mwh (float, rounded to 2 decimals)
   → EnergyConsumptionFromElectricity_NonRenewableEnergyMember → electricity_mwh
   → EnergyConsumptionFromElectricity_RenewableEnergyMember → 0
   → EnergyConsumptionFromSelfGeneratedElectricity_RenewableEnergyMember → 0
   → EnergyConsumptionFromSelfGeneratedElectricity_NonRenewableEnergyMember → 0
   → GrossScope1GreenhouseGasEmissions → scope1 (float, rounded to 2 decimals)
   → GrossLocationBasedScope2GreenhouseGasEmissions → scope2 (float, rounded to 2 decimals)
   → Turnover → turnover (if provided, else skip)

7. SET BOOLEAN GATES (direct cell access, no named range):
   → wb['Environmental Disclosures']['G10'] = True   # has breakdown
   → wb['Environmental Disclosures']['G29'] = False   # no Scope 3
   → wb['Fuel Converter']['D23'] = False              # bypass fuel converter

8. SAVE:
   → wb.save(output_path)
   → Return VSMEExportResult with all computed values + warnings

CONSTRAINTS:
→ Files to CREATE: src/chemtrace/vsme_export.py
→ Files NOT to touch: etl.py, cli.py (Task B), pdf_parser.py, sap_parser.py, rag_client.py
→ Max ~250 lines for vsme_export.py
→ Type hints on ALL public functions
→ Docstrings on module and public function
→ import openpyxl only inside vsme_export.py (isolate dependency)

DIESEL CONVERSION CONSTANT:
```python
# EFRAG Fuel Conversion Parameters, Row 16 (Gas/Diesel oil)
# NCV: 43 TJ/Gg, Density: 0.84 kg/L
# 43 TJ/Gg × 0.84 kg/L = 36.12 MJ/L ÷ 3600 MJ/MWh = 0.010033 MWh/L
DIESEL_MWH_PER_LITRE = 0.010033
```

ERROR HANDLING:
→ CSV not found → FileNotFoundError("No data found at {path}. Run `chemtrace parse` first.")
→ CSV empty (0 rows) → ValueError("CSV contains no records. Run `chemtrace parse` first.")
→ Template not found → FileNotFoundError("VSME template not found at {path}. Reinstall ChemTrace or check data/vsme_templates/.")
→ Named range not found → log warning, skip (don't crash)
→ openpyxl write error → propagate with context message

================================================================
TASK A3: Create tests/test_vsme_export.py
================================================================

Minimum 12 test cases. Use tmp_path fixture.

Test groups:

GROUP 1: Unit conversion
→ test_electricity_kwh_to_mwh: 478800 kWh → 478.8 MWh
→ test_natural_gas_kwh_to_mwh: 310800 kWh → 310.8 MWh
→ test_diesel_litres_to_mwh: 8500 L → 85.28 MWh (8500 × 0.010033)

GROUP 2: Scope classification
→ test_scope1_includes_gas_and_diesel: gas+diesel emissions summed
→ test_scope2_is_electricity_only: electricity emissions only
→ test_mixed_types_correct_split: all 3 types, verify split

GROUP 3: Aggregation
→ test_multiple_months_summed: 3 months electricity → single total
→ test_period_range_detection: min/max period extracted correctly
→ test_span_warning_over_12_months: warning logged for >12 months

GROUP 4: XLSX output (FIX F-01: template has 13 sheets, not 14)
→ test_output_is_valid_xlsx: file opens with openpyxl, has 13 sheets
→ test_named_ranges_have_values: TotalEnergyConsumption, Scope1, Scope2 not None
→ test_turnover_written_when_provided: Turnover cell has value
→ test_turnover_empty_when_not_provided: Turnover cell is None
→ test_scope3_checkbox_false: G29 is False
→ test_fuel_converter_bypass: Fuel Converter D23 is False

GROUP 5: Error handling
→ test_missing_csv_raises_error: FileNotFoundError
→ test_empty_csv_raises_error: ValueError
→ test_missing_template_raises_error: FileNotFoundError

CRITICAL: Tests need the actual EFRAG template file. Use a fixture that copies it from data/vsme_templates/. If template doesn't exist in test environment, skip with pytest.mark.skipif.

For CSV test data, create small in-memory CSVs using io.StringIO or tmp_path writes matching the exact column format of invoices.csv.

================================================================
TASK A4: Add openpyxl to requirements.txt
================================================================

Add to requirements.txt:
  openpyxl>=3.1.0

Verify it doesn't conflict with existing deps:
  pip install openpyxl>=3.1.0 --dry-run

After all files created, run:
  PYTHONPATH="C:\Chemtrace\src" pytest tests/test_vsme_export.py -v
  PYTHONPATH="C:\Chemtrace\src" pytest tests/ -v  (regression check)

After completion, apply .skills/CODE_VERIFIER.md protocol.
```
