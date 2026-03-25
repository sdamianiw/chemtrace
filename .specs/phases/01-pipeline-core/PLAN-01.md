# PLAN-01.md — Phase 01: Pipeline Core
**Phase:** 01-pipeline-core
**Tasks:** 3 (max per SDD rules)
**Total budget:** 16h (2 weeks × 8h)
**Execution tool:** Claude Code via Cursor (Sonnet 4.6)
**Planning tool:** claude.ai Opus 4.6 (this chat)

---

## PRE-FLIGHT CHECKLIST (before opening Claude Code)

```bash
# 1. Create project folder
mkdir C:\Chemtrace
cd C:\Chemtrace
git init

# 2. Create folder structure
mkdir -p .specs/phases/01-pipeline-core
mkdir -p .specs/phases/02-rag-client
mkdir -p .specs/phases/03-docker-deploy
mkdir -p .skills
mkdir -p src/chemtrace
mkdir -p data/sample_invoices
mkdir -p data/emission_factors
mkdir -p tests
mkdir -p output

# 3. Copy spec files from downloads into .specs/
# → REQUIREMENTS.md → .specs/REQUIREMENTS.md
# → ARCHITECTURE.md → .specs/ARCHITECTURE.md
# → CONTEXT.md → .specs/phases/01-pipeline-core/CONTEXT.md
# → This file → .specs/phases/01-pipeline-core/PLAN-01.md

# 4. Copy skill files into .skills/
# → PROMPT_CONTRACT.md → .skills/PROMPT_CONTRACT.md
# → CODE_VERIFIER.md → .skills/CODE_VERIFIER.md

# 5. Copy CLAUDE.md to root
# → CLAUDE.md → C:\Chemtrace\CLAUDE.md

# 6. Copy existing PDFs into data/sample_invoices/
# → Invoice_Electricity_Jan2024_RuhrChem.pdf
# → Invoice_Electricity_Mar2024_RuhrChem.pdf
# → Invoice_NaturalGas_Jan2024_RuhrChem.pdf
# → ESG_Report_Energy_Emissions_RuhrChem_2024.pdf

# 7. Copy reference files (for Claude Code context)
# → invoice_etl_day2.ipynb → .specs/reference/invoice_etl_day2.ipynb
# → client_decarb_day6.ipynb → .specs/reference/client_decarb_day6.ipynb
# → invoices-index.json → .specs/reference/invoices-index.json

# 8. Initial commit
git add .
git commit -m "feat: project scaffold with SDD specs and sample data"

# 9. Open Cursor in C:\Chemtrace → Claude Code reads CLAUDE.md automatically
```

---

## TASK 1: Project Foundation + PDF Parser (6h)

### Goal
Create the project skeleton (config, types, utils) and a working PDF parser that correctly extracts all fields from the 3 existing synthetic invoices.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/REQUIREMENTS.md (sections 4.1, 4.2)
- .specs/ARCHITECTURE.md (sections 2.1, 2.2, 2.3)
- .specs/phases/01-pipeline-core/CONTEXT.md (sections 2, 3, 5)
- .specs/reference/invoice_etl_day2.ipynb (cells 11, 12 for logic reference)
- .skills/PROMPT_CONTRACT.md (follow its rules)

GOAL: Create the project foundation + working PDF parser.

CONSTRAINTS:
→ Files to CREATE: src/chemtrace/__init__.py, __main__.py, config.py, 
  pdf_parser.py, parser_patterns.py, utils.py, data/emission_factors/factors.json,
  .env.example, requirements.txt, pyproject.toml, .gitignore
→ Files NOT to touch: .specs/*, .skills/*, CLAUDE.md, data/sample_invoices/*
→ Max ~400 lines total across all files

FAILURE MODES:
→ Parser hardcodes field positions → breaks on different invoice formats
→ Parser crashes on unexpected input → must return ParseResult with error
→ Config missing validation → silent failures downstream

OUTPUT FORMAT:
→ All files listed above created and importable
→ `python -c "from chemtrace.pdf_parser import parse_invoice; print('OK')"` works
→ Running parse_invoice on each of the 3 existing PDFs returns correct values
  per CONTEXT.md Section 5 (Expected Values table)

VERIFICATION:
→ python -c "from chemtrace.config import Config; c = Config(); print(c)"
→ python -c "from chemtrace.pdf_parser import parse_invoice; from pathlib import Path; r = parse_invoice(Path('data/sample_invoices/Invoice_Electricity_Jan2024_RuhrChem.pdf')); print(r.success, r.data['total_amount'], sum(li.consumption_kwh for li in r.data['line_items']))"
→ Expected: True, 116461.40, 478800.0
→ Repeat for all 3 PDFs with expected values from CONTEXT.md

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 1)
→ [ ] Config loads from .env with defaults
→ [ ] Emission factors loaded from factors.json with source field
→ [ ] parse_invoice() extracts all header fields from 3 test PDFs
→ [ ] parse_invoice() extracts correct line items (meter ID, consumption, price, amount)
→ [ ] parse_invoice() extracts correct totals (subtotal, levies, VAT, total)
→ [ ] parse_invoice() returns ParseResult(success=False) for empty/invalid PDF
→ [ ] No hardcoded field positions → regex patterns in parser_patterns.py
→ [ ] SHA-256 hash utility in utils.py
→ [ ] requirements.txt with pinned versions
→ [ ] .gitignore includes: .env, chroma_db/, output/, __pycache__/, *.pyc

### Post-Task
```bash
git add .
git commit -m "feat: project foundation + PDF parser with configurable patterns"
# /clear in Claude Code for fresh context
```

---

## TASK 2: ETL Pipeline + Vector Store + Tests (6h)

### Goal
Build the batch ETL pipeline (parse → validate → enrich → store) and ChromaDB vector store. All 3 existing invoices processed correctly end-to-end.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/ARCHITECTURE.md (sections 2.3, 2.4)
- .specs/phases/01-pipeline-core/CONTEXT.md (sections 2, 5)
- src/chemtrace/config.py (understand current Config)
- src/chemtrace/pdf_parser.py (understand ParseResult interface)
- .specs/reference/invoice_etl_day2.ipynb (cells 12-16, 20 for ETL logic)
- .skills/PROMPT_CONTRACT.md

GOAL: Create ETL pipeline + ChromaDB vector store. Batch process 3 PDFs → CSV + indexed.

CONSTRAINTS:
→ Files to CREATE: src/chemtrace/etl.py, src/chemtrace/vector_store.py,
  tests/test_parser.py, tests/test_etl.py, tests/test_vector_store.py, tests/__init__.py
→ Files to MODIFY (if needed): src/chemtrace/config.py (add chroma config)
→ Files NOT to touch: pdf_parser.py (unless bug found), .specs/*, data/*
→ Max ~500 lines total new code

FAILURE MODES:
→ ETL saves CSV BEFORE validation (Bug #2 from original) → enforce order
→ ChromaDB duplicates on re-run → must upsert by PDF hash
→ Silent errors on parse failure → must log to errors.csv
→ Emission calculation wrong → must be traceable: kWh × EF = tCO2e

OUTPUT FORMAT:
→ `python -m chemtrace parse data/sample_invoices/` prints summary + creates output/invoices.csv
→ CSV contains 3 rows with correct values (per CONTEXT.md Section 5)
→ CSV includes emissions_tco2 column (calculated from consumption × EF)
→ ChromaDB at chroma_db/ contains 3 documents
→ `pytest tests/` passes all tests

VERIFICATION:
→ python -m chemtrace parse data/sample_invoices/
→ cat output/invoices.csv (check values match expected)
→ python -c "from chemtrace.vector_store import VectorStore; from chemtrace.config import Config; vs = VectorStore(Config()); print(vs.count())"
→ Expected: 3
→ pytest tests/ -v
→ Run parse twice → count still 3 (dedup test)

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 2)
→ [ ] ETL processes 3 PDFs without errors
→ [ ] CSV output has correct columns: blob_name, site, period, energy_type, energy_amount, currency, total_eur, emissions_tco2, pdf_hash
→ [ ] Emission values: Elec Jan = 478800 × 0.000380 = ~181.94 tCO2e
→ [ ] ChromaDB stores 3 documents with searchable content
→ [ ] Re-run produces same count (upsert, no duplicates)
→ [ ] errors.csv created if any PDF fails (test with a dummy empty PDF)
→ [ ] pytest: minimum 3 test files, all green
→ [ ] Execution order enforced: parse → validate → calculate → save → index

### Post-Task
```bash
git add .
git commit -m "feat: ETL pipeline + ChromaDB vector store + test suite"
# /clear in Claude Code for fresh context
```

---

## TASK 3: Synthetic Data Enhancement + CLI Polish + Phase Verification (4h)

### Goal
Create 2 new synthetic invoice PDFs (diesel + different vendor format), wire up CLI commands, run full phase verification.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/REQUIREMENTS.md (sections 4.5, 4.7)
- .specs/ARCHITECTURE.md (section 2.6)
- .specs/phases/01-pipeline-core/CONTEXT.md (section 3.3)
- src/chemtrace/ (all modules, understand current state)
- data/sample_invoices/ (existing PDFs for format reference)
- .skills/PROMPT_CONTRACT.md

GOAL: Create 2 new synthetic PDFs + CLI interface + full phase verification.

CONSTRAINTS:
→ Files to CREATE: 
  src/chemtrace/cli.py,
  data/sample_invoices/Invoice_Diesel_Feb2024_RuhrChem.pdf (synthetic, generated via reportlab),
  data/sample_invoices/Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf (synthetic, different vendor)
→ Files to MODIFY: src/chemtrace/__main__.py (wire CLI), parser_patterns.py (if needed for new format)
→ Files NOT to touch: etl.py, vector_store.py (unless bug found)

FAILURE MODES:
→ New PDFs not parseable by existing parser → patterns must handle variations
→ CLI crashes on missing ChromaDB → graceful error message
→ Diesel invoice uses litres not kWh → parser/ETL must handle unit differences

OUTPUT FORMAT:
→ 2 new PDFs in data/sample_invoices/ that look realistic
→ `python -m chemtrace parse data/sample_invoices/` processes all 5 PDFs → 5 rows in CSV
→ `python -m chemtrace status` shows count of indexed docs
→ `python -m chemtrace export output/full_export.csv` works
→ pytest still green with new PDFs included

NEW PDF SPECIFICATIONS:

Invoice_Diesel_Feb2024_RuhrChem.pdf:
  Vendor: NRW Energie Versorgung GmbH (same vendor)
  Customer: RuhrChem Lubricants GmbH
  Site: Essen Blending Plant
  Invoice: DI-2024-001, Date: 2024-03-08
  Period: 2024-02-01 to 2024-02-29
  Line: D-ESSEN-FLEET-01, Diesel - Internal logistics, 8,500 litres, €1.42/litre, €12,070.00
  Subtotal: 12,070.00, Network/levies 5%: 603.50, VAT 19%: 2,407.97, Total: 15,081.47
  Currency: EUR

Invoice_Electricity_Feb2024_Stadtwerke_Essen.pdf:
  Vendor: Stadtwerke Essen AG (DIFFERENT vendor → tests parser flexibility)
  Customer: RuhrChem Lubricants GmbH
  Site: Essen Blending Plant
  Invoice: SWE-2024-0847, Date: 2024-03-15
  Period: 2024-02-01 to 2024-02-28
  Line: E-ESSEN-PLANT-01, Strom - Produktion, 415,300 kWh, €0.1810/kWh, €75,169.30
  Note: Uses German terms (Strom, Produktion, Rechnungsnummer, Abrechnungszeitraum)
  Subtotal: 75,169.30, Netzentgelte & Umlagen 12%: 9,020.32, MwSt 19%: 15,996.03, Gesamt: 100,185.65
  Currency: EUR

VERIFICATION:
→ python -m chemtrace parse data/sample_invoices/
→ Verify CSV: 5 rows, all values correct
→ python -m chemtrace status → "5 documents indexed"
→ python -m chemtrace export output/test.csv → valid CSV
→ pytest tests/ -v → all green
→ Apply .skills/CODE_VERIFIER.md FULL protocol (this is end-of-phase)

After CODE_VERIFIER, generate .specs/phases/01-pipeline-core/VERIFY.md with results.
```

### Acceptance Criteria (Task 3)
→ [ ] 5 PDFs in data/sample_invoices/, all parseable
→ [ ] Diesel invoice parsed with litres (not kWh)
→ [ ] Stadtwerke invoice with German terms parsed correctly
→ [ ] CLI: parse, status, export commands work
→ [ ] Full test suite green
→ [ ] VERIFY.md generated with all checks

### Post-Task
```bash
git add .
git commit -m "feat: synthetic data + CLI interface + phase 01 verification"
git tag v0.1.0-pipeline-core
# /clear in Claude Code
```

---

## PHASE 01 GATE (Definition of Done)

| # | Check | Command | Expected |
|---|---|---|---|
| G-01 | Parse 5 PDFs | `python -m chemtrace parse data/sample_invoices/` | "5 processed, 0 errors" |
| G-02 | CSV correct | `cat output/invoices.csv` | 5 rows, correct values |
| G-03 | Emissions calculated | Check CSV emissions_tco2 column | Non-zero, traceable |
| G-04 | ChromaDB populated | `python -m chemtrace status` | "5 documents indexed" |
| G-05 | No duplicates | Run parse twice, check status | Still 5 |
| G-06 | Export works | `python -m chemtrace export output/test.csv` | Valid CSV |
| G-07 | Tests green | `pytest tests/ -v` | All pass |
| G-08 | No hardcoded values | `grep -r "API_KEY\|hardcode\|0\.0002" src/` | No matches |
| G-09 | Error handling | Parse with empty PDF in dir | errors.csv created, others still processed |
| G-10 | Code Verifier | `.skills/CODE_VERIFIER.md` full run | No critical findings |

**If all G-01 to G-10 pass → Phase 01 complete. Proceed to Phase 02 (RAG Client).**

---

*PLAN-01 ready for execution. 3 tasks, 16h budget, copy-paste prompts for Claude Code.*
