# CONTEXT.md — Phase 01: Pipeline Core
**Phase:** 01-pipeline-core
**Duration:** Week 1-2 (16h max)
**Gate:** `python -m chemtrace parse data/sample_invoices/` produces correct CSV
**Depends on:** REQUIREMENTS.md v1.0 ✅, ARCHITECTURE.md v1.0 ✅
**SDD Gate:** 3 of 5 (Specify ✅ → Design ✅ → Plan → Execute → Verify)

---

## 1. PHASE OBJECTIVE

Build the core parsing and ETL pipeline: PDF invoices in → structured CSV + ChromaDB index out. No RAG, no LLM, no Docker yet. Pure data pipeline.

---

## 2. WHAT EXISTS (from Azure prototype)

### Code to refactor:
→ `invoice_etl_day2.ipynb` (23 cells): Blob download → DocInt parsing → DataFrame → CSV → AI Search upload
→ `client_decarb_day6.ipynb` (4 cells): RAG client (Phase 02, not this phase)
→ `invoices-index.json`: Azure AI Search schema (reference for ChromaDB schema)
→ `invoices_summary_v2.csv`: Output from broken pipeline (contains Bug #4 incorrect values)

### What we keep (logic to port):
→ `analyze_invoice_blob()` (Cell 11): field extraction logic (InvoiceTotal, AmountDue, Items line-item sum). Rewrite for pdfplumber instead of Azure DocInt.
→ `INVOICE_METADATA` dict + `infer_metadata_from_name()` (Cell 12): metadata inference heuristics. Keep as-is, extend for diesel.
→ `build_content()` (Cell 20): content text generation for search index. Keep pattern.
→ `clean_number()` (Cell 20): number sanitization. Keep as-is.

### What we discard:
→ All Azure SDK imports and clients (DocInt, Blob, AI Search)
→ Hardcoded API keys (Cells 4, 8, 18, 20, 21)
→ Manual value patches (Cell 15) → parser must extract correctly
→ Blob download logic → replaced by local filesystem reads
→ AI Search upload → replaced by ChromaDB upsert

### Known bugs to fix in this phase:
→ Bug #2: Execution order (parse → validate → THEN save/index)
→ Bug #5: Double network call → N/A (no network), but apply principle: no redundant I/O
→ Bug #6: Silent errors → add errors.csv logging
→ Bug #7: EF = 0.0002 without source → use 0.000380 with UBA reference

---

## 3. TECHNICAL DECISIONS (this phase only)

### TD-01: pdfplumber extraction strategy

Our synthetic PDFs have a consistent structure:
```
Header block (vendor, customer, site, address, invoice #, date, billing period)
Table (Line | Meter ID | Energy type | From | To | Consumption | Unit price | Amount)
Footer block (Subtotal, Network & levies, VAT, Total)
Notes paragraph
```

Strategy:
1. `page.extract_text()` → get full text as string
2. `page.extract_tables()` → get structured table rows
3. Regex on full text → extract header fields (invoice number, dates, vendor, customer, site)
4. Table rows → extract line items (meter ID, energy type, consumption, price, amount)
5. Regex on full text → extract footer totals (subtotal, levies, VAT, total)

Why not just regex everything? Tables are more reliable for structured rows. Why not just tables? Header/footer fields aren't always in table format.

### TD-02: What if pdfplumber fails on a table?

Fallback chain:
1. Try `page.extract_tables()` with default settings
2. If empty → try with explicit `table_settings` (line margins, snap tolerance)
3. If still empty → fall back to pure regex on `extract_text()` for line items
4. If regex fails → ParseResult(success=False, error="Could not extract line items")

### TD-03: Synthetic PDF improvements needed

Current PDFs are good but need:
→ 1 new diesel invoice (Invoice_Diesel_Feb2024_RuhrChem.pdf): 8,500 litres, Scope 1
→ 1 new invoice with slightly different format (different vendor name/layout) to test parser robustness
→ These get created as part of Task 1 in PLAN-01

### TD-04: Emission factor verification

| Type | Value | Unit | Source | Status |
|---|---|---|---|---|
| Electricity (DE grid) | 0.000380 | tCO2e/kWh | UBA Emissionsfaktoren | [Pendiente verificación 2024] |
| Natural gas | 0.000202 | tCO2e/kWh | ESG Report synthetic | Consistent with EU average |
| Diesel | 0.002680 | tCO2e/litre | ESG Report synthetic | Consistent with DEFRA 2024 |

For MVP: use these values with source citation. Exact UBA 2024 value does not block execution.

---

## 4. FILES TO CREATE IN THIS PHASE

```
src/chemtrace/__init__.py         ← package init (version string)
src/chemtrace/__main__.py         ← entry point stub
src/chemtrace/config.py           ← .env loader + emission factors
src/chemtrace/pdf_parser.py       ← pdfplumber extraction
src/chemtrace/parser_patterns.py  ← configurable regex patterns
src/chemtrace/etl.py              ← batch pipeline orchestrator
src/chemtrace/vector_store.py     ← ChromaDB wrapper
src/chemtrace/utils.py            ← shared helpers (hash, logging)
data/sample_invoices/             ← 5 PDFs (3 existing + 2 new)
data/emission_factors/factors.json
tests/test_parser.py
tests/test_etl.py
tests/test_vector_store.py
.env.example
requirements.txt
pyproject.toml
.gitignore
```

---

## 5. EXPECTED VALUES (test oracle)

These are the correct values the parser MUST extract. Any deviation = bug.

| PDF | energy_type | consumption | unit | total_eur | line_items |
|---|---|---|---|---|---|
| Invoice_Electricity_Jan2024 | electricity | 478,800 | kWh | 116,461.40 | 2 (Plant: 420,500 + Office: 58,300) |
| Invoice_Electricity_Mar2024 | electricity | 453,100 | kWh | 108,096.61 | 2 (Plant: 398,200 + Office: 54,900) |
| Invoice_NaturalGas_Jan2024 | natural_gas | 310,800 | kWh | 26,925.23 | 1 (Boiler: 310,800) |
| Invoice_Diesel_Feb2024 (NEW) | diesel | 8,500 | litres | ~TBD | 1 |
| Invoice_Electricity_Feb2024_Stadtwerke (NEW) | electricity | ~TBD | kWh | ~TBD | 1 (different vendor format) |

→ Note: Jan2024 electricity TOTAL consumption = 420,500 + 58,300 = 478,800 kWh (both meters summed).
→ The old CSV had 3,500 kWh (Bug #4) because Azure DocInt returned quantity field instead of consumption.

---

## 6. RISK MITIGATION FOR THIS PHASE

| Risk | Mitigation | Owner |
|---|---|---|
| pdfplumber can't parse synthetic table | Validate in Task 1 before writing full parser. If fails → adjust PDF or try table_settings. | Sebas (manual test) |
| Emission factor wrong | Mark [Pendiente verificación] in factors.json. Use reasonable estimate. Not a blocker. | Accept for MVP |
| ChromaDB import issues on Windows | Test in Task 3. If fails → defer to Phase 03 (Docker only). | Sebas |
| Time overrun | 80/20 STOP at 16h. Cut: skip 5th invoice variant, simplify tests. | Sebas |

---

*Phase 01 context complete. See PLAN-01.md for execution tasks.*
