# REQUIREMENTS.md — ChemTrace OSS
**Version:** 1.0
**Date:** 2026-03-23
**Author:** Sebas Damiani + Claude (Opus 4.6)
**Status:** DRAFT → Pending approval before ARCHITECTURE.md
**SDD Gate:** 1 of 5 (Specify → Design → Plan → Execute → Verify)

---

## 1. PROJECT IDENTITY

**Name:** ChemTrace OSS
**Tagline:** Open-source Scope 1-3 carbon accounting pipeline. Deployable in 30 minutes. Audit-ready. Zero vendor lock-in.
**Target users:** German industrial SMEs (50-500 employees) facing CSRD 2026-2027 deadlines.
**Repo path (local):** `C:\Chemtrace` → Git Bash: `/c/Chemtrace`
**License:** MIT (pending confirmation)

---

## 2. CONSTRAINTS

| ID | Constraint | Impact |
|---|---|---|
| C-01 | Max 8-10h/week development time | Scope must be ruthlessly prioritized |
| C-02 | Zero cloud dependencies in MVP | No Azure, no paid APIs, no SaaS |
| C-03 | Dev tool: Claude Code via Cursor (Max plan) | Execution via Sonnet 4.6 in Cursor terminal |
| C-04 | LLM runtime: Ollama local only | No API keys required for end users |
| C-05 | Target OS: Docker (Linux container), dev on Windows 11 | Cross-platform via Docker |
| C-06 | No n8n, no Supabase, no Easypanel | Pure Python + Docker stack |
| C-07 | PDFs are digital-native (not scanned) for MVP | OCR out of scope |
| C-08 | German energy invoice formats as primary target | Specific field names, VAT structure, meter IDs |

---

## 3. AVAILABLE RESOURCES

| Resource | Status | Notes |
|---|---|---|
| Claude Code (Cursor, Max plan) | ✅ Available | Dev tool only, not runtime LLM |
| claude.ai Opus 4.6 | ✅ Available | Planning (this chat) |
| Python 3.11+ | ✅ Available | Runtime |
| Docker Desktop (Windows 11) | ✅ Available | Container runtime |
| Git + GitHub personal | ✅ Available | Public repo |
| Ollama | ✅ To install | Local LLM inference |
| 4 synthetic PDFs + CSV + JSON schema | ✅ Available | Test data from Azure prototype |
| Azure resources (all) | ❌ Eliminated | Account expired 2025-12-13, purged |
| n8n instance | ❌ Not available | No personal account |
| Supabase / Easypanel | ❌ DGD only | Not available for personal project |

---

## 4. FUNCTIONAL REQUIREMENTS

### REQ-F01: PDF Invoice Parsing
→ Parse German energy invoices (electricity, natural gas, diesel) from digital PDF files.
→ Extract: vendor name, customer name, site address, invoice number, invoice date, billing period (from/to), line items (meter ID, energy type, consumption kWh, unit price, amount EUR), subtotal, network & levies, VAT, total amount due, currency.
→ Dynamic field mapping via configurable regex/heuristic patterns (no hardcoded field names).
→ Handle multi-line invoices (e.g., Mar2024 with production + offices split).
→ Return normalized dict per invoice with schema matching the index fields.
→ Graceful error handling: if a field cannot be extracted, return None + log warning (never crash).

### REQ-F02: ETL Pipeline
→ Batch process all PDFs in a configured input directory.
→ For each PDF: parse → validate → enrich (emission factor calculation) → store.
→ Metadata inference from filename as fallback (site, period, energy_type).
→ Configurable emission factors per energy type with source citation.
→ Default emission factors (German grid mix):
  • Electricity: ~0.000380 tCO2/kWh [Pendiente verificación UBA Emissionsfaktoren 2024]
  • Natural gas: 0.000202 tCO2/kWh (from ESG report synthetic data)
  • Diesel: 0.00268 tCO2/litre (from ESG report synthetic data)
→ Output: structured DataFrame + CSV export + ChromaDB indexing.
→ Error logging to `errors.csv` (blob_name, error_type, message, timestamp).
→ Execution order enforced: parse → validate → calculate emissions → save CSV → index to vector store.

### REQ-F03: Vector Store (ChromaDB)
→ Persist parsed invoice data as searchable documents.
→ Schema: id, blob_name, site, period, energy_type, energy_amount, currency, total_eur, emissions_tco2, content (generated text summary).
→ Local embedding model: `all-MiniLM-L6-v2` via sentence-transformers (no API).
→ Support metadata filtering: by site, period, energy_type.
→ Persist to disk (Docker volume mountable).
→ Upsert logic: re-running ETL on same PDF updates existing record (no duplicates).

### REQ-F04: RAG Client
→ Accept natural language questions about energy consumption and emissions.
→ Retrieve relevant documents from ChromaDB (top_k=4 default).
→ Generate answer using Ollama (default model: llama3.1:8b or equivalent).
→ System prompt enforces:
  • Only answer from indexed data (no hallucination).
  • Always cite source invoices (blob_name, site, period).
  • Refuse off-topic questions politely.
  • Show concrete numbers (kWh, EUR, tCO2e).
→ Safety/guardrails message included.
→ Configurable inference parameters: temperature, max_tokens, top_p.

### REQ-F05: CLI Interface
→ `chemtrace parse <input_dir>` → run ETL on all PDFs in directory.
→ `chemtrace ask "<question>"` → RAG query with formatted answer.
→ `chemtrace status` → show indexed documents count, last run timestamp, ChromaDB health.
→ `chemtrace export <output_path>` → export current data as CSV.
→ All commands respect `.env` configuration.

### REQ-F06: Docker Deployment
→ `docker-compose up` starts full stack (app + Ollama + ChromaDB).
→ Volume mounts for: input PDFs, ChromaDB persistence, .env config.
→ Health check endpoint or CLI command.
→ First-run experience: copy sample invoices, run parse, run ask → working in <5 minutes.

### REQ-F07: Synthetic Test Data
→ Minimum 5 invoices covering:
  • 2x electricity (different months, one with multi-meter split)
  • 1x natural gas
  • 1x diesel (internal logistics) → NEW, matches ESG report
  • 1x invoice with different vendor format → tests parser robustness
→ 1x ESG summary report (existing, may enhance).
→ All data coherent with RuhrChem Lubricants GmbH, Essen Blending Plant, 2024.
→ Values must be realistic for a mid-size German industrial plant.

### REQ-F08: Documentation
→ README.md bilingual EN/DE.
→ Sections: What is it, Who is it for, Quick Start (3 commands), Architecture diagram, Configuration, Emission factors with sources, Contributing, License.
→ .env.example with all configurable variables documented.
→ CLAUDE.md (max 30 lines) for Claude Code rules.

---

## 5. NON-FUNCTIONAL REQUIREMENTS

### REQ-NF01: Zero Cloud Dependency
→ Entire stack runs offline after initial Docker pull + Ollama model download.
→ No API keys required. No accounts to create. No data leaves the machine.

### REQ-NF02: Performance
→ Parse 10 invoices in <30 seconds (pdfplumber, local).
→ RAG query response in <10 seconds (Ollama on CPU, 8b model).
→ Full stack startup in <2 minutes (Docker).

### REQ-NF03: Auditability
→ Every emission calculation must be traceable: input kWh × EF = tCO2e.
→ Emission factors stored with source reference (UBA, DEFRA, custom).
→ CSV export includes all intermediate values.
→ Hash of source PDF stored with each record (integrity verification).

### REQ-NF04: Extensibility
→ Adding a new energy type = adding one entry to emission_factors config.
→ Adding a new invoice format = adding regex patterns to parser config.
→ LLM provider abstraction: swap Ollama for any OpenAI-compatible API via .env (post-MVP).

### REQ-NF05: Code Quality
→ Type hints on all public functions.
→ Docstrings on all modules and public functions.
→ pytest test suite: minimum 1 test per module.
→ No hardcoded values (all config via .env or constants with source).

---

## 6. OUT OF SCOPE (MVP)

| Item | Deferred to |
|---|---|
| Web UI (React dashboard) | Phase 31-60 |
| OCR for scanned PDFs | Phase 31-60 |
| Scope 3 upstream/downstream calculation | Phase 31-60 |
| SAP CSV / ERP connector | Phase 31-60 |
| Power BI integration module | Phase 61-90 |
| n8n workflow integration | Phase 31-60 |
| Multi-site / multi-tenant support | Post-MVP |
| Cloud API LLM option (Anthropic/OpenAI) | Post-MVP (architecture ready) |
| User authentication | Post-MVP |
| PDF generation (audit reports) | Phase 61-90 |

---

## 7. ACCEPTANCE CRITERIA (Definition of Done — MVP)

| # | Criterion | How to verify |
|---|---|---|
| AC-01 | `docker-compose up` starts full stack without errors | Manual test |
| AC-02 | `chemtrace parse data/sample_invoices/` produces correct CSV with 5 invoices | Compare values vs. known synthetic data |
| AC-03 | All emission calculations match expected tCO2e values (±1%) | Unit test |
| AC-04 | `chemtrace ask "What was electricity consumption in Jan 2024?"` returns grounded answer with source citation | Manual test |
| AC-05 | Off-topic questions are refused by RAG client | Automated guardrails test |
| AC-06 | No hardcoded API keys, paths, or values in codebase | grep audit |
| AC-07 | README.md exists in EN and DE, includes Quick Start with 3 commands | Manual review |
| AC-08 | `chemtrace export output.csv` produces valid CSV with all fields | Unit test |
| AC-09 | Re-running parse on same PDFs does not create duplicate records | Unit test |
| AC-10 | New user can go from `git clone` to working demo in <30 minutes | Timed walkthrough |

---

## 8. RISKS

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | pdfplumber cannot extract tables from real-world German invoices (varied formats) | Medium | High (blocks MVP) | Validate in Week 1 with 3+ format variants. Fallback: docling (IBM OSS) |
| R-02 | Ollama too slow on CPU for acceptable UX | Medium | Medium | Use quantized 8b model. Accept <10s response. GPU optional. |
| R-03 | ChromaDB local embedding model quality insufficient for invoice retrieval | Low | Medium | Test retrieval precision early. Fallback: BM25 keyword search. |
| R-04 | Time overrun (>8h/week) | Medium | Medium | 80/20 STOP. Cut scope, not quality. |
| R-05 | Docker image too large for quick adoption | Low | Low | Multi-stage build. Alpine base. Ollama model pulled separately. |

---

## 9. PHASED EXECUTION PLAN (SDD)

| Phase | Name | Duration | Gate |
|---|---|---|---|
| 01 | pipeline-core | Week 1-2 (16h) | `chemtrace parse` produces correct CSV |
| 02 | rag-client | Week 3 (8h) | `chemtrace ask` returns grounded answers |
| 03 | docker-deploy | Week 4 (8h) | `docker-compose up` → full stack working |

Each phase follows: CONTEXT.md → PLAN-XX.md (max 3 tasks) → Execute → VERIFY.md

---

## 10. DECISION LOG

| # | Decision | Rationale | Date |
|---|---|---|---|
| D-01 | Ollama as sole LLM (no cloud API) | Zero vendor lock-in, zero cost, runs offline | 2026-03-23 |
| D-02 | pdfplumber over Azure DocInt | OSS, local, sufficient for digital PDFs | 2026-03-23 |
| D-03 | ChromaDB over Azure AI Search | OSS, embeddable, supports semantic + metadata filtering | 2026-03-23 |
| D-04 | Repo at C:\Chemtrace | Outside OneDrive, short path, no sync issues | 2026-03-23 |
| D-05 | Python-only stack (no n8n) | n8n not available personally, simplifies MVP | 2026-03-23 |
| D-06 | all-MiniLM-L6-v2 for embeddings | Free, local, good quality for short text, no API | 2026-03-23 |
| D-07 | Dev via Claude Code in Cursor (Max) | Available on personal machine, proven workflow | 2026-03-23 |

---

*SDD Gate 1 complete. Awaiting approval to proceed to ARCHITECTURE.md (Gate 2).*
