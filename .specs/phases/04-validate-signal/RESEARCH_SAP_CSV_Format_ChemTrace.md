# RESEARCH → SAP CSV Energy Export Format for ChemTrace OSS
# Task 3.6 (PLAN-04 Week 3) | Date: 2026-04-01 | Audited: Level 2
# Confidence: 0.91 | Sources: SAP Community, EFRAG, dena/KEDi, BfEE, VCI, vendor docs

---

## 1. EXECUTIVE SUMMARY

No standardized CSV export format exists in SAP for energy consumption data.
German industrial SMEs export ad-hoc from SE16N, ALV grids, or custom Z-reports.
ChemTrace's SAP CSV parser must handle messy, variable, German-locale files.
The gap between "manual Excel" and "€50K+ SAP SFM" is confirmed and real.

---

## 2. VALIDATED PARSER SPECIFICATIONS

### 2.1 Delimiter
→ **Default: semicolon (;)**
→ SAP_CONVERT_TO_CSV_FORMAT hardcodes semicolon (ignores separator parameter)
→ Fallback: comma, then tab (custom ABAP or GUI_DOWNLOAD may use these)
→ Auto-detect strategy: count occurrences of ;  ,  \t in first 3 lines

### 2.2 Encoding (CORRECTED from original analysis)
→ **Primary: Windows-1252 (cp1252)** ← NOT ISO-8859-1
→ cp1252 is superset of ISO-8859-1, adds € (0x80) and other chars in 0x80-0x9F range
→ SAP codepage 1160 = cp1252 (default for Unicode SAP + Windows GUI)
→ Legacy non-Unicode ECC: codepage 1100 = true ISO-8859-1
→ S/4HANA may export UTF-8 (codepage 4110) depending on config
→ **Detection order: UTF-8 BOM (EF BB BF) → cp1252 → ISO-8859-1**
→ Validation chars: ä (0xE4), ö (0xF6), ü (0xFC), ß (0xDF), € (0x80 in cp1252)

### 2.3 Number Format
→ **German default: 1.234,56** (dot=thousands, comma=decimal)
→ Controlled by USR01-DCPFM field (per-user setting, not per-system)
→ Regex: `^-?\d{1,3}(\.\d{3})*(,\d+)?$` for German format
→ Edge case: numbers <1,000 have no thousands separator (just `234,56`)
→ **Must support BOTH German and English formats** (auto-detect by scanning first data row)

### 2.4 Headers
→ Many SAP exports have NO headers (SAP_CONVERT_TO_CSV_FORMAT omits them)
→ When present: bilingual DE/EN realistic
→ Parser needs column-inference logic for headerless files
→ Keyword matching for header detection (not position-based)

### 2.5 Period Format
→ No standard. Depends on admin's SE16N config and ABAP report formatting.
→ Accept: "2024-01", "01.2024", "202401", "Jan 2024", "Januar 2024", "January 2024", "P01/2024"
→ SAP fiscal periods: POPER field uses P01-P12 format internally

---

## 3. REALISTIC CSV STRUCTURE

### 3.1 Expected Headers (bilingual mapping)

| DE Header | EN Header | SAP Field Origin | Required |
|---|---|---|---|
| Werk | Plant | WERKS (4-char) | YES |
| Zeitraum | Period | POPER/MONAT | YES |
| Energieart | Energy_Type | Custom/Z-table | YES |
| Verbrauch | Consumption | IMRG delta calc | YES |
| Einheit | Unit | MEINS/MSEHI | YES |
| Kosten | Cost | COEP/ACDOCA | YES |
| Waehrung | Currency | WAERS | YES |
| Zaehler_ID | Meter_ID | IMPTT-POINT | NO |
| Kostenstelle | Cost_Center | KOSTL | NO |
| Standort | Location | Custom | NO |
| CO2_Faktor | Emission_Factor | Custom | NO |
| Bemerkung | Remarks | Custom | NO |

### 3.2 Synthetic Sample (for data/sample_sap/)

```csv
Werk;Zeitraum;Energieart;Verbrauch;Einheit;Kosten;Waehrung;Zaehler_ID;Bemerkung
Essen Blending;2024-01;Strom;478800,0;kWh;116461,40;EUR;DE-ESS-001;Hauptzaehler Produktion
Essen Blending;2024-01;Erdgas;310800,0;kWh;24864,00;EUR;DE-ESS-G01;Kessel + Trockner
Essen Blending;2024-02;Diesel;8500,0;Liter;13600,00;EUR;;Interne Logistik
Essen Blending;2024-03;Strom;420000,0;kWh;108096,61;EUR;DE-ESS-001;Hauptzaehler Produktion
```

### 3.3 Energy Type Keyword Mapping

| DE keyword | EN keyword | ChemTrace energy_type |
|---|---|---|
| Strom, Elektrizität | Electricity, Electric | electricity |
| Erdgas, Gas, Naturgas | Natural Gas, Gas | natural_gas |
| Diesel, Kraftstoff, Heizöl | Diesel, Fuel Oil | diesel |
| Fernwärme | District Heating | district_heating (future) |

---

## 4. SAP TABLE LANDSCAPE (CORRECTED)

### 4.1 Correction: EABL is NOT relevant
→ EABL belongs to SAP IS-U (Industry Solution for Utilities)
→ Used by energy PROVIDERS, not by factories tracking own consumption
→ Remove from ChemTrace documentation

### 4.2 Relevant Tables for Industrial Energy Tracking

**SAP PM (meter readings):**
→ IMPTT → Measuring point master (links to equipment via MPOBJ)
→ IMRG → Measurement documents (RECDV=recorded value, IDATE=date, POINT=measuring point)
→ EQUI → Equipment master for physical meters
→ Note: SAP stores READINGS, not consumption. Delta calculation = manual or custom ABAP.

**SAP CO/FI (cost tracking):**
→ COEP → CO actual line items (energy costs as specific GL postings)
→ COSP/COSS → CO totals for primary/secondary costs
→ ACDOCA → Universal journal in S/4HANA (replaces BSEG)

### 4.3 Relevant Transaction Codes
→ IK11 → Create measurement document
→ IK16 → Bulk entry measurement documents
→ IK17 → Display measurement document list (primary PM energy report)
→ S_ALR_87013611 → Cost center actual/plan/variance (most used for energy cost analysis)
→ KSB1 → Cost center line items (drill into individual energy invoices)
→ **EM_CONSUMPTION does NOT exist** (was incorrectly assumed in original analysis)

---

## 5. COMPETITIVE LANDSCAPE (German SME Energy Management)

### 5.1 Enterprise (NOT ChemTrace competitors)
→ SAP SFM → ~€50K+/year, quote-based, enterprise-only references
→ SAP Green Ledger → Requires RISE with SAP contract

### 5.2 Mid-Market SaaS (indirect competitors, validates demand)
→ **ENIT Agent** → Fraunhofer ISE spin-off (now proALPHA), 200+ industrial customers, hardware+software, targets ≥0.5 GWh
→ **IngSoft InterWatt** → DACH market leader, 20,000+ users, AI anomaly detection, ISO 50001 certified
→ **ecoplanet** → Cloud-native, targets ≥200 employees / ≥7.5 GWh, AI analysis, CSRD positioning
→ **OPTENDA Energy Monitor** → Freiburg, BAFA-listed, digital meter acquisition, ISO 50001

### 5.3 ChemTrace Differentiator (confirmed)
→ All competitors above are SaaS + paid + require hardware/sensors
→ ChemTrace = open-source, zero-cost, offline, no hardware, audit-ready
→ BAFA Module 3 subsidy: 50% (small) / 40% (medium) reimbursement on implementation
→ ChemTrace managed implementation (€5-8K) could be partially BAFA-funded

### 5.4 Dominant Reality
→ **Excel manual** remains primary tool for firms 50-100 employees
→ Energy managers report 2-4 days/month on manual Excel compilation
→ This is ChemTrace's true competitor: customer apathy + Excel inertia

---

## 6. EFRAG VSME IMPLICATIONS

### 6.1 Disclosure B3 Requirements (Energy + GHG Emissions)
→ Total energy consumption in MWh (breakdown: electricity, fossil fuels)
→ Scope 1 + Scope 2 GHG emissions in tCO2eq (location-based)
→ GHG intensity (gross emissions / turnover in EUR)
→ Scope 3: "may be appropriate" for high-impact sectors (includes chemicals)

### 6.2 Format: XLSX + XBRL, NOT CSV
→ EFRAG Digital Template: XLSX (v1.1.1, Nov 2025)
→ XBRL taxonomy for machine-readable reporting
→ Open-source XLSX-to-iXBRL converter (MIT license, GitHub)
→ **ChemTrace implication: consider XLSX export targeting EFRAG template (post-MVP)**

### 6.3 Omnibus I Expansion (Feb 2025)
→ VSME now applies to companies up to 1,000 employees
→ Directly covers ChemTrace target market
→ Strengthens urgency for compliance tools

---

## 7. PARSER DESIGN DECISIONS (updated)

| Aspect | Decision | Rationale |
|---|---|---|
| Delimiter | Semicolon default, auto-detect comma/tab | SAP hardcodes semicolon |
| Encoding | Detect: UTF-8 BOM → cp1252 → ISO-8859-1 | cp1252 is true SAP default, not ISO-8859-1 |
| Numbers | Auto-detect German (1.234,56) vs English (1,234.56) | Per-user SAP setting, both possible |
| Headers | Optional. Keyword matching, not position-based | Many SAP exports lack headers |
| Period | Accept 6+ formats, normalize to YYYY-MM | SAP has no standard period format |
| Energy keywords | Bilingual DE/EN keyword sets | German SAP + international teams |
| Missing fields | Skip gracefully, log warning | Real exports have gaps |
| Headerless files | Column inference by data pattern analysis | SAP_CONVERT_TO_CSV_FORMAT omits headers |

---

## 8. IMPACT ON CHEMTRACE ARCHITECTURE

### 8.1 Changes to CONTEXT_Phase04 TD-07
→ Replace "SAP ECC standard energy data management export" with "pragmatic ad-hoc export"
→ Replace EABL reference with IMRG
→ Add cp1252 as primary encoding (not ISO-8859-1)
→ Add headerless file support requirement

### 8.2 Changes to Task 4.2 (SAP CSV Parser Implementation)
→ Add delimiter auto-detection (;  ,  \t)
→ Add encoding detection chain (UTF-8 → cp1252 → ISO-8859-1)
→ Add headerless file column inference
→ Add period format normalization (6+ input formats → YYYY-MM)
→ Bilingual keyword mapping for energy types

### 8.3 Future Consideration (post-MVP, not now)
→ XLSX export targeting EFRAG VSME Digital Template
→ BAFA subsidy documentation for managed implementation pricing
→ ENIT/InterWatt feature comparison for positioning

---

## 9. AUDIT TRAIL

| Check | Status |
|---|---|
| Claims 1-3, 7 (parser specs) | ✅ Validated (encoding corrected to cp1252) |
| Claim 4 (SME tracking reality) | ✅ Validated (VCI: 91% SMEs, Excel dominant) |
| Claim 5 (SFM pricing) | ✅ Validated (enterprise-only, ~€50K+) |
| Claim 6 (field names) | ✅ Validated + expanded (added Kostenstelle, Standort) |
| SAP tables | ⚠️ Corrected (EABL → IMRG, EM_CONSUMPTION removed) |
| Competitive landscape | ✅ New finding (ENIT, InterWatt, ecoplanet identified) |
| EFRAG VSME | ✅ New finding (XLSX/XBRL, not CSV; Omnibus I expansion) |
| BAFA subsidy | ✅ New finding (40-50% reimbursement, applicable to ChemTrace) |

**Level 2 Audit: PASS**
→ Zero CRITICAL/HIGH findings
→ 3 MEDIUM corrections applied (encoding, EABL, EM_CONSUMPTION)
→ 2 strategic additions (EFRAG XLSX, BAFA subsidy)
→ Confidence: 0.91

---

*Research: 2026-04-01 | Deep research validated | Ready for Task 4.2 implementation*
