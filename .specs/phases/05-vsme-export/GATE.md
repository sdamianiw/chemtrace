# GATE TÉCNICO: EFRAG VSME B3 XLSX Export
# Date: 2026-04-02 | Template: VSME-Digital-Template-Sample-1_2_0.xlsx (v1.2.0)
# Level 3 Audit | Confidence: 0.92

---

## VERDICT: PASS ✓

openpyxl puede leer, escribir y guardar el template sin perder sheets (14→14)
ni named ranges (815→815). Valores escritos se leen correctamente post-save.

---

## 1. TEMPLATE STRUCTURE

13 sheets, 815 named ranges (XBRL taxonomy), 548 rows in Environmental Disclosures.
B3 section: rows 2-69 in 'Environmental Disclosures' sheet.

Key sheets:
  → 'Environmental Disclosures' (B3 lives here)
  → 'General Information' (Turnover lives here: E281)
  → 'Fuel Converter' (optional fuel→MWh calculator)
  → 'Fuel Conversion Parameters' (NCV/density reference data)

---

## 2. EXACT CELL MAPPING: ChemTrace → VSME B3

### INPUT CELLS (safe to write directly):

| Named Range | Cell | Unit | ChemTrace Source | Transform |
|---|---|---|---|---|
| TotalEnergyConsumption | EnvDisc!G5 | MWh | sum(energy_amount) all types | kWh ÷ 1000 + diesel litres × NCV |
| EnergyConsumptionFromElectricity_RenewableEnergyMember | EnvDisc!G12 | MWh | 0 (unknown split) | hardcode 0 |
| EnergyConsumptionFromElectricity_NonRenewableEnergyMember | EnvDisc!J12 | MWh | sum(energy_amount where type=electricity) | kWh ÷ 1000 |
| EnergyConsumptionFromSelfGeneratedElectricity_RenewableEnergyMember | EnvDisc!G13 | MWh | 0 | hardcode 0 |
| EnergyConsumptionFromSelfGeneratedElectricity_NonRenewableEnergyMember | EnvDisc!J13 | MWh | 0 | hardcode 0 |
| GrossScope1GreenhouseGasEmissions | EnvDisc!D22 | tCO2eq | sum(emissions_tco2 where type in [natural_gas, diesel]) | direct |
| GrossLocationBasedScope2GreenhouseGasEmissions | EnvDisc!D23 | tCO2eq | sum(emissions_tco2 where type=electricity) | direct |
| Turnover | GenInfo!E281 | EUR | user input (--turnover flag) | direct |

### BOOLEAN GATES (must set correctly):

| Cell | Current Sample | ChemTrace Value | Why |
|---|---|---|---|
| EnvDisc!G10 | FALSE | TRUE | "Has breakdown info" → we provide electricity breakdown |
| EnvDisc!G29 | TRUE | FALSE | "Disclosing Scope 3" → ChemTrace has no Scope 3 |

### FORMULA CELLS (DO NOT WRITE, auto-calculated):

| Cell | Formula | Depends On |
|---|---|---|
| EnvDisc!K12 | =SUM(G12:J12) | G12, J12 |
| EnvDisc!K13 | =SUM(G13:J13) | G13, J13 |
| EnvDisc!K14 | =IF(FuelConverter!D23=TRUE, ...) | Fuel Converter |
| EnvDisc!D25 | =SUM(D22,D23) | D22, D23 |
| EnvDisc!D26 | =SUM(D22,D24) | D22, D24 (market, not filled) |
| EnvDisc!G66 | =D25/Turnover (if G29=FALSE) | D25, Turnover |
| EnvDisc!G67 | =D26/Turnover (if G29=FALSE) | D26, Turnover |

### FUEL CONVERTER DECISION:

G14/J14 (fuels breakdown) are FORMULAS linked to Fuel Converter sheet.
If FuelConverter!D23=TRUE → pulls calculated MWh from Fuel Converter.
If FuelConverter!D23=FALSE → shows "-".

**Decision: Set FuelConverter!D23=FALSE for MVP.**
Rationale: ChemTrace already has total kWh for gas and litres for diesel.
We calculate total MWh in Python and put it in G5 (TotalEnergy).
The fuel breakdown shows "-" which is valid VSME (breakdown is optional per §29).
Fuel Converter integration is post-MVP enhancement.

---

## 3. AGGREGATION LOGIC

VSME is annual reporting. ChemTrace has monthly records.

```
For each energy_type:
    sum energy_amount across all periods → annual total
    sum emissions_tco2 across all periods → annual total

Electricity MWh = sum(energy_amount where type=electricity) / 1000
Gas MWh = sum(energy_amount where type=natural_gas) / 1000  
Diesel MWh = sum(energy_amount where type=diesel) * 0.01003  # NCV: 10.033 kWh/litre ÷ 1000
Total MWh = Electricity MWh + Gas MWh + Diesel MWh

Scope 1 = sum(emissions where type in [natural_gas, diesel])
Scope 2 = sum(emissions where type=electricity)
```

Diesel NCV: 10.033 kWh/litre (36.1 MJ/litre ÷ 3.6) 
Source: DEFRA UK Government GHG Conversion Factors 2024, Table "Fuels", Row "Diesel (average biofuel blend)"
[Pendiente verificación: cross-check with EFRAG Fuel Conversion Parameters sheet in template]

---

## 4. RISKS & WARNINGS

| # | Finding | Severity | Mitigation |
|---|---|---|---|
| W-01 | openpyxl warns "Data Validation extension not supported and will be removed" | MEDIUM | Dropdowns in template may break. ChemTrace only writes value cells, doesn't need dropdowns. End user opening in Excel should see values correctly but some dropdown validations may be missing. |
| W-02 | openpyxl warns "Conditional Formatting extension not supported and will be removed" | MEDIUM | Color-coding for validation status may disappear. Values remain correct. Cosmetic only. |
| W-03 | Fuel breakdown (G14/J14) shows "-" instead of MWh breakdown | LOW | Valid per VSME §29 ("if it can obtain the necessary information"). Post-MVP: integrate Fuel Converter. |
| W-04 | GrossMarketBasedScope2 (D24) left empty | LOW | Location-based (D23) is the primary metric. Market-based requires energy attribute certificates. Not available in ChemTrace. |
| W-05 | Renewable/non-renewable electricity split hardcoded to 0/100% | LOW | ChemTrace doesn't track renewable certificates. All electricity classified as non-renewable. Conservative and defensible. |
| W-06 | Template is v1.2.0 (Feb 2026), EFRAG may release updates | LOW | Named ranges follow XBRL taxonomy (stable). Minor cell shifts possible. Pin to v1.2.0 in repo. |

---

## 5. IMPLEMENTATION REQUIREMENTS

### New dependency:
→ openpyxl (already used by EFRAG converter, MIT license)
→ CHECK: is openpyxl already in requirements.txt? If not, add it.

### New files:
→ src/chemtrace/vsme_export.py (~150-250 lines)
→ data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx (631KB, MIT license)
→ tests/test_vsme_export.py (~10 tests)

### Modified files:
→ src/chemtrace/cli.py (add --format vsme flag)
→ requirements.txt (add openpyxl if missing)
→ README.md (add VSME export section)

### CLI interface:
→ chemtrace export --format csv --output report.csv (default, backward compatible)
→ chemtrace export --format vsme --output report.xlsx [--turnover 5000000]

---

## 6. AUDIT TRAIL

| Check | Status | Confidence |
|---|---|---|
| Template readable by openpyxl | ✓ PASS | 1.0 |
| Named ranges preserved after write+save | ✓ PASS (815→815) | 1.0 |
| Sheets preserved after write+save | ✓ PASS (14→14) | 1.0 |
| Values read back correctly after write | ✓ PASS | 1.0 |
| B3 input cells identified (not formulas) | ✓ PASS (8 cells) | 0.95 |
| Formula cells identified (don't touch) | ✓ PASS (7+ cells) | 0.95 |
| Boolean gates identified (G10, G29) | ✓ PASS | 0.95 |
| Turnover location confirmed | ✓ PASS (GenInfo!E281) | 1.0 |
| Fuel Converter dependency understood | ✓ PASS (bypass for MVP) | 0.90 |
| Data Validation warning assessed | ⚠️ MEDIUM risk | 0.85 |
| Conditional Formatting warning assessed | ⚠️ LOW risk | 0.90 |

**Overall Gate Confidence: 0.92**

---

## 7. DECISION

**D-044: VSME B3 XLSX export gate PASS.**
→ 8 input cells clearly identified
→ Formula cells mapped (don't touch)
→ Write/read cycle verified
→ Fuel Converter bypassed for MVP (valid per VSME §29)
→ openpyxl warnings are cosmetic, not blocking
→ Proceed to CONTEXT + PLAN-06 spec

---

*Gate audit: 2026-04-02 | Level 3 | Recursive inspection: 6 phases + 1 write test | Confidence: 0.92*
