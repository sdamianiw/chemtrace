# CONTEXT.md — Phase 05 Track 2: EFRAG VSME B3 XLSX Export
**Phase:** 04-validate-signal (extension, final technical track)
**Duration:** ~4-6h execution + 1h verify
**Budget:** Within remaining Phase 04 allocation
**Gate:** `chemtrace export --format vsme` produces valid XLSX with B3 data + all tests pass + tag v0.6.0-vsme-export pushed
**Depends on:** v0.5.0-sap-connector COMPLETE ✓ (12 docs e2e, 135 tests, f3043e9)
**SDD Gate:** 3 of 5 (Specify ✓ → Design (this file) → Plan → Execute → Verify)

---

## 1. OBJECTIVE

Add EFRAG VSME B3 (Energy and GHG Emissions) XLSX export to ChemTrace. The export fills the official EFRAG Digital Template (v1.2.0, Feb 2026) with aggregated energy consumption and emission data already processed by the pipeline. This makes ChemTrace the first open-source tool that exports directly to the EU's official SME sustainability reporting format.

**Why now (not Day 61-90):** The template is a published standard with fixed cell structure (815 named ranges). No user feedback needed to implement. Having this before follow-up emails (Apr 8-9) changes the outreach pitch from "interesting tool" to "compliance-ready solution."

---

## 2. WHAT EXISTS (from Phases 01-04)

### Relevant current state:
→ `src/chemtrace/cli.py` → `export` command with `--output` flag, `--format` not yet implemented
→ `src/chemtrace/etl.py` → `run_pipeline()` returns PipelineResult with records list
→ `output/invoices.csv` → CSV with columns: blob_name, site, billing_period_from, billing_period_to, energy_type, consumption_kwh, currency, total_eur, emissions_tco2, content, pdf_hash
→ `src/chemtrace/config.py` → Config dataclass with all paths
→ `data/emission_factors/factors.json` → emission factors with sources (electricity: 0.000380, gas: 0.000202, diesel: 0.00268)
→ `requirements.txt` → current dependencies (NO openpyxl)
→ 135 tests passing, 0 regressions

### Files to CREATE:
→ `src/chemtrace/vsme_export.py` → VSME B3 export module (~200-300 lines)
→ `tests/test_vsme_export.py` → unit tests (~10-15 tests)
→ `data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx` → official EFRAG template (631KB, MIT license)

### Files to MODIFY:
→ `src/chemtrace/cli.py` → add `--format` flag (csv|vsme), add `--turnover` flag
→ `src/chemtrace/config.py` → add vsme_template_path field (env var CHEMTRACE_VSME_TEMPLATE)
→ `requirements.txt` → add openpyxl>=3.1.0
→ `README.md` → add VSME export section (both EN and DE)
→ `.env.example` → add CHEMTRACE_VSME_TEMPLATE
→ `Dockerfile` → openpyxl auto-included via requirements.txt rebuild

### Files NOT to touch:
→ `src/chemtrace/etl.py` → no changes needed, CSV output is the data source
→ `src/chemtrace/pdf_parser.py`, `sap_parser.py` → upstream, unrelated
→ `src/chemtrace/rag_client.py`, `prompts.py` → RAG, unrelated
→ `src/chemtrace/vector_store.py` → ChromaDB, unrelated

---

## 3. TECHNICAL DECISIONS

### TD-01: Template Source and Versioning
→ Use the BLANK EFRAG VSME Digital Template v1.2.0 (631KB, published 27 Feb 2026)
→ CRITICAL: EFRAG publishes TWO files: the blank template (631KB) and a pre-filled mock-up sample (640KB). ChemTrace MUST use the BLANK template. The sample contains "Lorem ipsum" and fictional data in B1, B2, B4-B11 sections that would pollute real reports.
→ Download URL: https://www.efrag.org/en/vsme-digital-template-and-xbrl-taxonomy (select "VSME Digital Template Version 1.2.0", NOT the "Mock-up example")
→ Store in `data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx` (MIT license per EFRAG GitHub)
→ Pin to v1.2.0. Future EFRAG updates require explicit migration.
→ Include ONLY the English template for MVP. German template as post-MVP (same structure, different labels).
→ Sebas must download the BLANK template manually before Claude Code execution.

### TD-02: openpyxl as XLSX Writer
→ EFRAG's own converter uses openpyxl (confirmed in their GitHub repo dependencies)
→ Gate test confirmed: write+save preserves 13 sheets and 815 named ranges
→ Known limitation: openpyxl strips Data Validation extensions and Conditional Formatting extensions on save. Values remain correct. Dropdowns and color-coding may degrade.
→ Mitigation: document in README that exported XLSX may have reduced formatting. Users can paste values into a fresh template if needed.

### TD-03: Cell Mapping Strategy (Named Range Access)
→ Access cells via openpyxl named ranges (wb.defined_names[name].destinations)
→ This is forward-compatible: if EFRAG moves cells in future versions, named ranges still point correctly
→ Fallback: direct cell reference (e.g., ws['G5']) only for cells without named ranges (booleans G10, G29)
→ All named range names match XBRL taxonomy element names (stable, standardized)

### TD-04: Data Aggregation (Monthly → Annual)
→ VSME is annual reporting. ChemTrace stores monthly records.
→ Aggregation: group by energy_type, sum consumption_kwh and emissions_tco2
→ Reporting period: derive from min(period) to max(period) in dataset
→ If data spans multiple years: use ALL data (user is responsible for filtering input). Log a warning if span > 12 months.

### TD-05: Energy Unit Conversions
→ Electricity: stored in kWh → VSME needs MWh → divide by 1000
→ Natural gas: stored in kWh → VSME needs MWh → divide by 1000
→ Diesel: stored in litres → VSME needs MWh → multiply by 0.010033 MWh/litre
  Source: EFRAG Fuel Conversion Parameters sheet, Row 16 (Gas/Diesel oil)
  Calculation: NCV 43 TJ/Gg × density 0.84 kg/L = 36.12 MJ/L ÷ 3600 = 0.010033 MWh/L
→ Unknown unit types: log warning, exclude from MWh total, include in tCO2eq if emissions exist

### TD-06: Scope 1 vs Scope 2 Classification
→ Scope 1 (direct emissions): natural_gas + diesel → sum their emissions_tco2
→ Scope 2 (indirect, location-based): electricity → sum its emissions_tco2
→ Scope 2 (market-based): NOT available in ChemTrace (requires energy attribute certificates) → leave D24 empty
→ Scope 3: NOT available → set G29=FALSE (checkbox)
→ These classifications follow GHG Protocol Corporate Standard (2004), consistent with VSME §30

### TD-07: GHG Intensity
→ Formula: total Scope 1+2 tCO2eq / turnover EUR
→ The template auto-calculates this (G66 formula: D25/Turnover)
→ ChemTrace provides D22 (Scope 1), D23 (Scope 2), and Turnover (E281 in General Information)
→ If --turnover not provided by user: leave E281 empty → G66 shows "-" (valid, IFERROR handles it)

### TD-08: Fuel Converter Bypass
→ EnvDisc G14/J14 (fuel energy breakdown) are FORMULA cells linked to Fuel Converter sheet
→ If Fuel Converter!D23=TRUE → values pulled from Fuel Converter calculations
→ If Fuel Converter!D23=FALSE → values show "-"
→ Decision: set Fuel Converter!D23=FALSE for MVP
→ Rationale: ChemTrace calculates total MWh in Python (more accurate than re-entering raw fuel data into EFRAG's converter). The fuel breakdown in G14/J14 shows "-" which is valid per VSME §29 ("if it can obtain the necessary information to provide such a breakdown")
→ The total energy (G5) still includes fuel MWh. Only the per-fuel-type breakdown row is empty.

### TD-09: Backward Compatibility
→ Current CLI: `chemtrace export --output path.csv`
→ New CLI: `chemtrace export [--format csv|vsme] [--output path] [--turnover EUR]`
→ `--format` defaults to `csv` → zero breaking changes
→ `--output` behavior: if format=csv → default extension .csv; if format=vsme → default extension .xlsx
→ If --output not specified and format=vsme → output to `output/vsme_report.xlsx`

### TD-10: Unit Convention in CSV (Implicit from energy_type)
→ The output CSV (`invoices.csv`) has NO explicit 'unit' column
→ Unit is implicit from energy_type (established convention in etl.py + factors.json):
  • electricity → consumption_kwh is in kWh (emission factor: tCO2/kWh)
  • natural_gas → consumption_kwh is in kWh (emission factor: tCO2/kWh)
  • diesel → consumption_kwh is in litres (emission factor: tCO2/litre)
→ SAP parser normalizes units before storing: MWh→kWh (*1000), m³→kWh (*GAS_CALORIFIC_VALUE)
→ vsme_export.py MUST respect this convention when converting to MWh

---

## 4. EXACT CELL MAP (from Gate Audit 2026-04-02)

### INPUT cells ChemTrace writes:

| # | Named Range | Sheet | Cell | Unit | Source | Transform |
|---|---|---|---|---|---|---|
| 1 | TotalEnergyConsumption | Environmental Disclosures | G5 | MWh | all records | kWh÷1000 + litres×0.010033 |
| 2 | EnergyConsumptionFromElectricity_NonRenewableEnergyMember | Environmental Disclosures | J12 | MWh | type=electricity | kWh÷1000 |
| 3 | EnergyConsumptionFromElectricity_RenewableEnergyMember | Environmental Disclosures | G12 | MWh | N/A | hardcode 0 |
| 4 | EnergyConsumptionFromSelfGeneratedElectricity_RenewableEnergyMember | Environmental Disclosures | G13 | MWh | N/A | hardcode 0 |
| 5 | EnergyConsumptionFromSelfGeneratedElectricity_NonRenewableEnergyMember | Environmental Disclosures | J13 | MWh | N/A | hardcode 0 |
| 6 | GrossScope1GreenhouseGasEmissions | Environmental Disclosures | D22 | tCO2eq | type=gas+diesel | sum emissions |
| 7 | GrossLocationBasedScope2GreenhouseGasEmissions | Environmental Disclosures | D23 | tCO2eq | type=electricity | sum emissions |
| 8 | Turnover | General Information | E281 | EUR | --turnover flag | direct (optional) |

### BOOLEAN gates ChemTrace sets:

| Cell | Value | Meaning |
|---|---|---|
| Environmental Disclosures!G10 | TRUE | "Has breakdown info" (we provide electricity) |
| Environmental Disclosures!G29 | FALSE | "No Scope 3 disclosure" |
| Fuel Converter!D23 | FALSE | "Don't auto-transfer fuel converter results" |

### FORMULA cells (DO NOT WRITE):

| Cell | Auto-calculates | From |
|---|---|---|
| K12 | Total electricity MWh | =SUM(G12:J12) |
| K13 | Total self-generated MWh | =SUM(G13:J13) |
| K14 | Total fuels MWh | Fuel Converter (shows "-" when D23=FALSE) |
| D25 | Total S1+S2 location-based | =SUM(D22,D23) |
| D26 | Total S1+S2 market-based | =SUM(D22,D24) → shows "-" (D24 empty) |
| G66 | S1+S2 intensity location | =D25/Turnover (if G29=FALSE) |
| G67 | S1+S2 intensity market | =D26/Turnover → shows "-" |

---

## 5. EXPECTED BEHAVIOR

### Happy path:
```
$ chemtrace export --format vsme --output report.xlsx --turnover 5000000

VSME B3 Export Summary:
  Template: EFRAG VSME Digital Template v1.2.0
  Records aggregated: 12 (5 PDF + 7 CSV)
  Reporting period: 2024-01 to 2024-03
  Total energy: 1,209.60 MWh
  Scope 1 (gas + diesel): 85.58 tCO2eq
  Scope 2 (electricity): 341.64 tCO2eq
  Turnover: 5,000,000.00 EUR
  Output: report.xlsx
```

### Edge cases:
→ No data (empty CSV): error message "No data found. Run `chemtrace parse` first." exit 1
→ Only electricity (no gas/diesel): Scope 1 = 0.0, G5 = electricity MWh only
→ Only diesel (no electricity): Scope 2 = 0.0, J12 = 0
→ No --turnover: Turnover cell empty → GHG intensity shows "-" (formula handles gracefully)
→ --turnover 0: Write 0 → GHG intensity formula shows "-" (IFERROR catches division by zero)
→ Data spans >12 months: log warning "Data spans N months. VSME is annual reporting. Consider filtering input."
→ Unknown energy_type (e.g., "district_heating"): log warning, exclude from MWh breakdown, include in emissions if present

### Error handling:
→ Template file missing: FileNotFoundError → "VSME template not found at {path}. Reinstall ChemTrace."
→ Template corrupt/unreadable: openpyxl exception → "Could not read VSME template: {error}"
→ CSV file missing: same as current export behavior → "No data found. Run `chemtrace parse` first."
→ openpyxl write failure: catch, log, exit 1 → "Failed to write VSME report: {error}"

---

## 6. KNOWN LIMITATIONS (document in README)

| # | Limitation | Impact | Workaround |
|---|---|---|---|
| L-01 | Renewable/non-renewable electricity split not tracked | All electricity reported as non-renewable (conservative) | Manual adjustment in Excel post-export |
| L-02 | Market-based Scope 2 not available | D24 empty, D26 shows "-" | Requires energy attribute certificates |
| L-03 | Fuel breakdown row (G14/J14) shows "-" | Total energy (G5) still correct | Use EFRAG Fuel Converter manually |
| L-04 | Data Validation dropdowns may be lost on save | Values correct, some UX degradation | Open fresh template, paste values |
| L-05 | Conditional Formatting may be lost on save | Color-coding for validation status may disappear | Cosmetic only, values unaffected |
| L-06 | No Scope 3 | G29=FALSE, Scope 3 section inactive | Manual entry in Excel for Scope 3 |
| L-07 | Self-generated electricity hardcoded to 0 | G13/J13 = 0 | Manual adjustment if applicable |

---

## 7. DECISION LOG

| ID | Decision | Rationale | Date |
|---|---|---|---|
| D-043 | EFRAG VSME B3 export moved to current phase | Template is published standard, no feedback needed. Differentiator for outreach. | 2026-04-02 |
| D-044 | Gate PASS. openpyxl compatible. | Write/read cycle preserves 13 sheets + 815 named ranges. | 2026-04-02 |
| D-045 | Use named range access (not cell coordinates) | Forward-compatible with future EFRAG template versions. | 2026-04-02 |
| D-046 | Bypass Fuel Converter (D23=FALSE) | ChemTrace calculates MWh in Python. Converter re-entry adds complexity without value. Valid per VSME §29. | 2026-04-02 |
| D-047 | Diesel NCV = 0.010033 MWh/litre | Sourced from EFRAG's own Fuel Conversion Parameters (NCV 43 TJ/Gg, density 0.84 kg/L). | 2026-04-02 |
| D-048 | English template only for MVP | Same structure as German. Labels differ but cells/named ranges identical. | 2026-04-02 |
| D-049 | Scope 2 location-based only (no market-based) | Market-based requires energy attribute certificates not available in ChemTrace data. | 2026-04-02 |

---

*CONTEXT generated: 2026-04-02 | SDD Gate 3 | Depends on: Gate PASS (0.92) + PLAN-06*
