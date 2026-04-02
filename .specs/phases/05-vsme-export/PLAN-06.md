# PLAN-06.md — EFRAG VSME B3 XLSX Export
**Phase:** 04-validate-signal (final technical track)
**Duration:** ~4-5h execution + 1h verify
**Budget:** Within remaining Phase 04 allocation (~5.5h available)
**Gate:** `chemtrace export --format vsme` produces valid XLSX + 10+ new tests pass + tag v0.6.0-vsme-export pushed
**Depends on:** v0.5.0-sap-connector COMPLETE ✓ (f3043e9), Gate PASS ✓ (0.92)
**SDD Gate:** Plan (this file) → Execute → Verify
**Audit:** Level 3 applied (see §7)
**Confidence:** [pending post-audit]

---

## 1. OBJECTIVE

Implement `chemtrace export --format vsme` that fills the official EFRAG VSME Digital Template (v1.2.0) with Disclosure B3 (Energy and GHG Emissions) data from ChemTrace's processed records.

---

## 2. TASK BREAKDOWN (2 tasks, max 3 per plan rule)

### TASK A: vsme_export.py + tests + template (3-4h, Claude Code)
### TASK B: CLI integration + Docker e2e + README + tag (1-2h, Claude Code)

---

## 3. TASK A: Core VSME Export Module

### Goal
Create `vsme_export.py` that reads the invoices CSV, aggregates data, and fills the EFRAG template.

### Pre-flight reads (Claude Code MUST read before coding):
→ `src/chemtrace/cli.py` (understand current export command structure)
→ `src/chemtrace/config.py` (understand Config paths, output_dir)
→ `src/chemtrace/etl.py` (understand PipelineResult, CSV output format)
→ `output/invoices.csv` or equivalent (understand column names and types)
→ `data/emission_factors/factors.json` (understand energy_type canonical values)
→ `.skills/PROMPT_CONTRACT.md`

### Claude Code Prompt (copy-paste ready)

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

GROUP 4: XLSX output
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

### Acceptance Criteria (Task A)
→ [ ] vsme_export.py: export_vsme_b3() runs without error on sample data
→ [ ] vsme_export.py: XLSX output has 13 sheets (template preserved)
→ [ ] vsme_export.py: TotalEnergyConsumption named range has correct MWh value
→ [ ] vsme_export.py: GrossScope1 and GrossScope2 have correct tCO2eq values
→ [ ] vsme_export.py: G10=True, G29=False, FuelConverter D23=False
→ [ ] vsme_export.py: Turnover written when provided, empty when not
→ [ ] vsme_export.py: diesel correctly converted (litres × 0.010033 = MWh)
→ [ ] test_vsme_export.py: 12+ tests, all pass
→ [ ] All 135 existing tests still pass (zero regressions)
→ [ ] openpyxl in requirements.txt

### Post-Task A
```bash
git add .
git commit -m "feat: VSME B3 XLSX export module + tests (v0.6.0)"
# /clear in Claude Code for fresh context
```

---

## 4. TASK B: CLI Integration + Docker e2e + README + Tag

### Goal
Wire vsme_export into CLI, test in Docker, update README, tag v0.6.0.

### Pre-flight reads:
→ `src/chemtrace/cli.py` (current _cmd_export implementation)
→ `src/chemtrace/vsme_export.py` (just created in Task A)
→ `README.md` (current structure, find insertion points)

### Claude Code Prompt (copy-paste ready)

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\Chemtrace\src" python ...
PYTHONPATH="C:\Chemtrace\src" pytest ...

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
→ src/chemtrace/cli.py (current _cmd_export, argparse setup)
→ src/chemtrace/vsme_export.py (export_vsme_b3 interface)
→ src/chemtrace/config.py (Config, output_dir)
→ README.md (current structure)
→ .skills/PROMPT_CONTRACT.md

GOAL: Wire VSME export into CLI. Docker e2e test. README update. Tag.

================================================================
TASK B1: Modify src/chemtrace/cli.py
================================================================

Changes to argparse setup:
→ Add --format flag to export subcommand: choices=['csv', 'vsme'], default='csv'
→ Add --turnover flag to export subcommand: type=float, default=None, help='Annual turnover in EUR for GHG intensity calculation'

Changes to _cmd_export():
→ If args.format == 'csv': existing behavior (unchanged)
→ If args.format == 'vsme':
  1. Determine csv_path: config.output_dir / "invoices.csv"
  2. If not csv_path.exists(): print error, exit 1
  3. Determine template_path from config:
     Add to Config dataclass: vsme_template_path (with env var CHEMTRACE_VSME_TEMPLATE)
     Default: Path("data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx")
     This works in both local dev (CWD=C:\Chemtrace) and Docker (WORKDIR=/app)
     If path doesn't exist: print error, exit 1
  4. Determine output_path: args.output if provided, else config.output_dir / "vsme_report.xlsx"
  5. Call export_vsme_b3(csv_path, template_path, output_path, args.turnover)
  6. Print summary from VSMEExportResult
  7. If result.warnings: print each warning to stderr

CONSTRAINTS:
→ Files to MODIFY: src/chemtrace/cli.py (only _cmd_export + argparse), src/chemtrace/config.py (add vsme_template_path), .env.example
→ Files NOT to touch: vsme_export.py (already done), etl.py
→ Backward compatibility: `chemtrace export --output x.csv` must still work identically

TEMPLATE PATH RESOLUTION:
→ Use config.vsme_template_path (env var CHEMTRACE_VSME_TEMPLATE)
→ Default: "data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx" (relative to CWD)
→ Works in local (CWD=C:\Chemtrace) and Docker (WORKDIR=/app)
→ Add to config.py and .env.example

================================================================
TASK B2: Update README.md
================================================================

Add VSME export section. Surgical edits (same approach as SAP CSV README update):

Edit 1: In "What is ChemTrace?" paragraph → add "exports to EFRAG VSME format"
Edit 2: New section "VSME Export" after existing export docs:
  ### VSME Export (EFRAG Digital Template)
  ChemTrace can export energy and emissions data to the official EFRAG VSME
  Digital Template (v1.2.0). This fills Disclosure B3 (Energy and GHG Emissions)
  for CSRD/VSME compliance reporting.

  Docker:
  docker compose run --rm chemtrace export --format vsme --output output/vsme_report.xlsx
  docker compose run --rm chemtrace export --format vsme --output output/vsme_report.xlsx --turnover 5000000

  Local:
  chemtrace export --format vsme --output vsme_report.xlsx --turnover 5000000

  The exported XLSX can be uploaded to EFRAG's online XBRL converter
  (https://xbrl.efrag.org/convert/) for machine-readable reporting.

Edit 3: DE Schnellstart section → add equivalent German text

================================================================
TASK B3: Update .env.example
================================================================

Add:
  # VSME Export
  # CHEMTRACE_VSME_TEMPLATE=data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx

================================================================
TASK B4: Run tests
================================================================

  PYTHONPATH="C:\Chemtrace\src" pytest tests/ -v
  Expected: 135 + 12+ = 147+ tests, 0 failures

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Docker e2e test (Sebas executes manually post-Claude Code):

```bash
# Close Cursor first (free RAM)
# Rebuild Docker image (openpyxl added)
docker compose build --no-cache

# Parse all data (PDF + CSV)
MSYS_NO_PATHCONV=1 docker compose run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/output:/app/output" \
  chemtrace parse

# Export VSME (no turnover)
MSYS_NO_PATHCONV=1 docker compose run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/output:/app/output" \
  chemtrace export --format vsme --output output/vsme_report.xlsx

# Export VSME (with turnover)
MSYS_NO_PATHCONV=1 docker compose run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/output:/app/output" \
  chemtrace export --format vsme --output output/vsme_report_full.xlsx --turnover 5000000

# Verify CSV export still works (regression)
MSYS_NO_PATHCONV=1 docker compose run --rm \
  -v "$(pwd)/output:/app/output" \
  chemtrace export --output output/regression_test.csv

# Open vsme_report.xlsx in Excel → verify:
#   G5 (TotalEnergy) has MWh value
#   D22 (Scope 1) has tCO2eq value
#   D23 (Scope 2) has tCO2eq value
#   G10 = TRUE, G29 = FALSE
#   D25 auto-calculates (D22+D23)
#   G66 shows intensity (if turnover provided) or "-" (if not)
```

### Acceptance Criteria (Task B)
→ [ ] `chemtrace export --format csv --output x.csv` works (backward compatible)
→ [ ] `chemtrace export --format vsme --output x.xlsx` produces valid XLSX
→ [ ] `chemtrace export --format vsme --output x.xlsx --turnover 5000000` fills Turnover
→ [ ] Docker e2e: parse → export vsme works end-to-end
→ [ ] README updated (EN + DE)
→ [ ] .env.example updated with CHEMTRACE_VSME_TEMPLATE
→ [ ] 147+ tests pass, 0 regressions

### Post-Task B
```bash
git add .
git commit -m "feat: VSME B3 CLI + Docker e2e + README (v0.6.0)"
git tag v0.6.0-vsme-export
# Push manual from Git Bash T1 after grep secrets check
```

---

## 5. RISK REGISTER

| # | Risk | Prob | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | openpyxl strips Data Validation, user sees degraded template in Excel | Medium | Low | Document in README. Values correct. Cosmetic only. |
| R-02 | Template path resolution fails in Docker vs local | Medium | High | Use env var CHEMTRACE_VSME_TEMPLATE with sensible default. Test both. |
| R-03 | Named range name changes in future EFRAG template version | Low | Medium | Pin to v1.2.0. _write_named_range logs warning on missing range, doesn't crash. |
| R-04 | CSV column names don't match expected (schema drift) | Low | High | Validate required columns upfront. Fail fast with clear error. |
| R-05 | Diesel unit detection wrong (kWh vs litres) | Medium | Medium | Check 'unit' column in CSV. If unit='kWh' for diesel → divide by 1000 (not multiply by NCV). |
| R-06 | Budget overrun (>5.5h available) | Medium | Medium | Task A is self-contained. If Task B runs out of time, defer README/GIF to next session. Core export still works. |
| R-07 | Large CSV (1000+ rows) slow with pandas | Low | Low | 1000 rows is tiny for pandas. Not a concern. |

---

## 6. VERIFICATION CHECKLIST (DoD)

### Automated (pytest):
→ [ ] test_vsme_export.py: 12+ tests PASS
→ [ ] tests/ full suite: 147+ tests PASS, 0 regressions

### Manual (Sebas in terminal):
→ [ ] `chemtrace export --format vsme --output test.xlsx` → file created
→ [ ] `chemtrace export --format vsme --output test.xlsx --turnover 5000000` → file created
→ [ ] `chemtrace export --output test.csv` → backward compatible
→ [ ] Open test.xlsx in Excel → G5 has MWh value
→ [ ] Open test.xlsx in Excel → D22 has Scope 1, D23 has Scope 2
→ [ ] Open test.xlsx in Excel → D25 auto-calculates (should = D22+D23)
→ [ ] Open test.xlsx in Excel → G66 shows intensity (with turnover) or "-" (without)

### Docker e2e:
→ [ ] docker compose build succeeds (openpyxl installed)
→ [ ] docker compose run chemtrace export --format vsme works
→ [ ] VSME XLSX inside Docker has correct values

### Git:
→ [ ] git status clean
→ [ ] tag v0.6.0-vsme-export on correct commit
→ [ ] pushed to GitHub

---

## 7. LEVEL 3 AUDIT

### Roles: Senior Architect + QA/Operations + Bias Auditor

### HALLAZGOS

| ID | Sev | Hallazgo | Archivo | Fix | Status |
|---|---|---|---|---|---|
| H-01 | CRÍTICO | Sebas uploaded the pre-filled SAMPLE template (640KB, "Sample" in filename). Production MUST use the BLANK template (631KB). Using the sample would leave "Lorem ipsum" and fictional data in B1, B2, B4-B11 sections. | data/vsme_templates/ | Download blank from EFRAG page. Verify filesize ~631KB. | FIXED in CONTEXT TD-01 + PLAN Task A1 |
| H-02 | ALTO | PLAN Task B had inconsistent template path resolution: first suggested Path(__file__) resolution (wrong for installed packages), then pivoted to env var. Confusing for Claude Code. | cli.py / config.py | Unified to config.vsme_template_path with env var default. | FIXED in PLAN Task B1 |
| H-03 | ALTO | CSV has no 'unit' column. Diesel is in litres, electricity/gas in kWh, but this is IMPLICIT from energy_type. vsme_export.py must use energy_type to determine conversion, not look for a unit column. | vsme_export.py | Added TD-10 clarifying unit convention. Prompt explicitly states type-based conversion. | FIXED in CONTEXT TD-10 |
| H-04 | MEDIO | .dockerignore might exclude data/ directory, preventing template from being included in Docker image. | .dockerignore | Claude Code must verify: grep "data" .dockerignore. If excluded, add exception for data/vsme_templates/. | PENDING (diagnóstico en ejecución) |
| H-05 | MEDIO | Diesel test: 8500 L × 0.010033 = 85.28 MWh. But sample CSV has diesel as "Liter" unit which becomes energy_amount=8500 in output CSV. If upstream changed to store diesel in kWh (via NCV), conversion would double-count. | vsme_export.py | Document the convention clearly. The emission factor diesel=0.00268 tCO2/litre confirms energy_amount=litres. Add assertion/comment in code. | FIXED in TD-10 |
| H-06 | MEDIO | config.py modification (add vsme_template_path) not listed in CONTEXT "Files to MODIFY" | CONTEXT §2 | Add config.py to modified files list. | FIXED below |
| H-07 | BAJO | Template v1.2.0 includes ArrayFormula objects (Fuel Converter B29, B32). openpyxl handles these but doesn't evaluate them. Since we bypass Fuel Converter (D23=FALSE), irrelevant. | N/A | No action. Documented for awareness. |
| H-08 | BAJO | No .gitignore entry for output/*.xlsx. VSME reports might get committed accidentally. | .gitignore | Add *.xlsx to output/ ignore pattern. Low priority. | PENDING |

### SIMULACIÓN E2E (5 escenarios)

| # | Scenario | Expected Result | Risk |
|---|---|---|---|
| S1 | Happy path: parse 12 docs → export vsme with turnover | XLSX with G5, D22, D23, E281 filled. D25 auto-calc. G66 shows intensity. | Low |
| S2 | No turnover flag | XLSX with G5, D22, D23 filled. E281 empty. G66 shows "-". | Low |
| S3 | Only electricity data (no gas/diesel) | G5 = electricity MWh. D22 = 0. D23 = electricity emissions. | Low (need to handle Scope1=0 gracefully) |
| S4 | Empty CSV (0 records) | ValueError with clear message. No XLSX created. | Low |
| S5 | Docker: template not in image | FileNotFoundError. Clear message pointing to data/vsme_templates/. | Medium (H-04) |

### BIAS AUDIT
→ Am I over-scoping? No. The module is ~200-300 lines. 2 tasks. Focused scope.
→ Am I under-estimating Data Validation stripping? Possibly. But EFRAG's own converter uses openpyxl. If their tool works, ours will too.
→ Am I ignoring the blank vs sample template? CAUGHT and FIXED (H-01, CRITICAL).
→ Am I optimistic about budget? 4-5h for a new module + tests + CLI + README is tight but achievable. SAP CSV connector was similar scope and done in ~4h.

### VEREDICTO: PASS CONDICIONAL

Ejecutar después de:
1. ✅ H-01 FIXED: Blank template specified in TD-01 and PLAN Task A1
2. ✅ H-02 FIXED: Path resolution unified to config.vsme_template_path
3. ✅ H-03 FIXED: Unit convention documented in TD-10
4. ⏳ H-04 PENDING: Verify .dockerignore during Claude Code execution
5. ✅ H-06 FIXED: config.py added to modified files list

### DoD (post-execution verification)
→ [ ] Blank template (631KB) placed in data/vsme_templates/ (NOT the sample)
→ [ ] `chemtrace export --format vsme --output test.xlsx` produces file
→ [ ] Open test.xlsx in Excel: G5 has MWh, D22 has Scope 1, D23 has Scope 2
→ [ ] D25 auto-calculates correctly (= D22 + D23)
→ [ ] G66: shows intensity if turnover, "-" if not
→ [ ] G10=TRUE, G29=FALSE in the exported file
→ [ ] `chemtrace export --output test.csv` still works (regression)
→ [ ] pytest: 147+ tests, 0 failures
→ [ ] Docker build succeeds, docker compose run export vsme works
→ [ ] git grep "lorem\|Lorem\|sample\|Sample" output/ → 0 matches in XLSX

### CONFIDENCE: 0.91
Justification: All CRITICAL/HIGH findings fixed. One MEDIUM pending (H-04, .dockerignore) requires runtime verification. Template cell mapping verified with actual data. NCV constant sourced from EFRAG's own parameters.

---

*Plan generated: 2026-04-02 | SDD Gate: Plan | Budget: ~4-5h | Depends on: Gate PASS (0.92)*
