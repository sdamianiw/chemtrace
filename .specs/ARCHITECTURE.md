# ARCHITECTURE.md — ChemTrace OSS
**Version:** 1.0
**Date:** 2026-03-23
**Author:** Sebas Damiani + Claude (Opus 4.6)
**Status:** DRAFT → Pending approval before PLAN-01.md
**SDD Gate:** 2 of 5 (Specify ✅ → Design → Plan → Execute → Verify)
**Depends on:** REQUIREMENTS.md v1.0 (approved 2026-03-23)

---

## 1. HIGH-LEVEL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│                                                         │
│   CLI: chemtrace parse | ask | status | export          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌──────────┐   ┌──────────┐   ┌───────────────────┐  │
│   │          │   │          │   │                   │  │
│   │ PDF      │──→│ ETL      │──→│ Vector Store      │  │
│   │ Parser   │   │ Pipeline │   │ (ChromaDB)        │  │
│   │          │   │          │   │                   │  │
│   └──────────┘   └──────────┘   └────────┬──────────┘  │
│                                          │              │
│                                          ▼              │
│                                 ┌───────────────────┐   │
│                                 │                   │   │
│                                 │ RAG Client        │   │
│                                 │ (Ollama LLM)      │   │
│                                 │                   │   │
│                                 └───────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Config (.env) │ Emission Factors │ Error Logger        │
└─────────────────────────────────────────────────────────┘
```

**Data flow:**
```
PDF files (input/)
    │
    ▼
pdf_parser.py ──→ raw dict per invoice (normalized fields)
    │
    ▼
etl.py ──→ validate → enrich (EF calc) → DataFrame
    │
    ├──→ CSV export (output/)
    │
    ├──→ ChromaDB index (vector_store.py)
    │
    └──→ errors.csv (if parse failures)

User question (CLI)
    │
    ▼
rag_client.py ──→ ChromaDB retrieval → Ollama completion → formatted answer
```

---

## 2. MODULE CONTRACTS

Each module has a clear interface. Modules communicate via Python dicts and DataFrames. No global state. No shared mutable objects.

### 2.1 config.py

**Responsibility:** Load all configuration from `.env` + provide constants with source documentation.

```python
# Interface
class Config:
    # Paths
    input_dir: Path          # default: ./data/sample_invoices/
    output_dir: Path         # default: ./output/
    chroma_dir: Path         # default: ./chroma_db/
    
    # Ollama
    ollama_base_url: str     # default: http://localhost:11434
    ollama_model: str        # default: llama3.1:8b
    
    # RAG
    rag_top_k: int           # default: 4
    rag_temperature: float   # default: 0.2
    rag_max_tokens: int      # default: 555
    
    # Embedding
    embedding_model: str     # default: all-MiniLM-L6-v2

# Emission factors (with source)
EMISSION_FACTORS: dict[str, EmissionFactor]
# Each EmissionFactor: value (tCO2/unit), unit (kWh or litre), source, year
```

**Design decisions:**
→ Single source of truth for all config.
→ python-dotenv for `.env` loading.
→ Emission factors as typed dataclass with mandatory `source` field.
→ Validation on load: fail fast if required config missing.

### 2.2 pdf_parser.py

**Responsibility:** Extract structured data from a single PDF invoice file. Pure function: PDF bytes in → dict out.

```python
# Interface
def parse_invoice(pdf_path: Path) -> ParseResult:
    """Parse a single PDF invoice, return structured data."""
    ...

@dataclass
class ParseResult:
    success: bool
    data: dict | None        # normalized invoice fields
    warnings: list[str]      # non-fatal extraction issues
    error: str | None        # fatal error message

# data dict schema:
{
    "vendor_name": str | None,
    "customer_name": str | None,
    "site_address": str | None,
    "invoice_number": str | None,
    "invoice_date": str | None,       # ISO format YYYY-MM-DD
    "billing_period_from": str | None, # ISO format YYYY-MM-DD
    "billing_period_to": str | None,
    "currency": str | None,            # e.g., "EUR"
    "line_items": list[LineItem],
    "subtotal": float | None,
    "network_levies": float | None,
    "vat_amount": float | None,
    "total_amount": float | None,
    "raw_text": str,                   # full extracted text for content field
}

@dataclass
class LineItem:
    meter_id: str | None
    energy_type: str | None     # electricity, natural_gas, diesel
    period_from: str | None
    period_to: str | None
    consumption_kwh: float | None
    unit_price: float | None
    amount_eur: float | None
```

**Design decisions:**
→ pdfplumber as extraction engine (REQ-F01, D-02).
→ Two-pass extraction strategy:
  1. **Table extraction** (`page.extract_tables()`) → parse structured rows.
  2. **Text extraction** (`page.extract_text()`) → regex fallback for header fields (vendor, invoice number, dates).
→ No hardcoded field positions. Patterns are configurable.
→ `ParseResult` wrapper → caller always gets a clean response, never an exception.
→ `raw_text` preserved for ChromaDB content field (full-text search).

**Parser pattern config (new file: `parser_patterns.py`):**
```python
# Configurable regex patterns for different invoice formats
PATTERNS = {
    "invoice_number": [
        r"Invoice\s*(?:number|no\.?|#)\s*[:.]?\s*(\S+)",
        r"Rechnungsnummer\s*[:.]?\s*(\S+)",
    ],
    "billing_period": [
        r"Billing\s*period\s*[:.]?\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})",
        r"Abrechnungszeitraum\s*[:.]?\s*(\d{2}\.\d{2}\.\d{4})\s*[-–bis]\s*(\d{2}\.\d{2}\.\d{4})",
    ],
    "energy_type_keywords": {
        "electricity": ["electricity", "strom", "kwh", "electric"],
        "natural_gas": ["natural gas", "erdgas", "gas"],
        "diesel": ["diesel", "kraftstoff", "fuel"],
    },
    # ... extensible per REQ-NF04
}
```

→ Adding a new invoice format = adding patterns to this config. No code changes needed.

### 2.3 etl.py

**Responsibility:** Orchestrate batch processing. PDF directory → parsed + enriched DataFrame → CSV + ChromaDB.

```python
# Interface
def run_pipeline(config: Config) -> PipelineResult:
    """Process all PDFs in input_dir, return summary."""
    ...

@dataclass
class PipelineResult:
    total_files: int
    successful: int
    failed: int
    records: list[dict]      # all processed records
    errors: list[dict]       # error log entries
    csv_path: Path | None    # exported CSV path
```

**Processing order (REQ-F02, Fix Bug #2):**
```
1. List PDFs in input_dir
2. For each PDF:
   a. parse_invoice(pdf_path) → ParseResult
   b. If failed → log to errors, continue
   c. infer_metadata(filename) → fallback site/period/type
   d. merge parsed data + inferred metadata
   e. calculate_emissions(record, EMISSION_FACTORS)
   f. generate_content_text(record)
   g. compute_pdf_hash(pdf_path) → SHA-256 for audit trail
   h. Append to records list
3. Build DataFrame from all records
4. Export CSV to output_dir
5. Upsert all records to ChromaDB
6. Export errors.csv if any failures
7. Return PipelineResult summary
```

**Design decisions:**
→ Step-by-step, no parallel processing for MVP (simplicity).
→ `calculate_emissions()` is a pure function: kWh × EF = tCO2e. Traceable.
→ PDF SHA-256 hash stored per record (REQ-NF03 auditability).
→ Metadata inference from filename only as fallback; parsed data takes priority.

### 2.4 vector_store.py

**Responsibility:** ChromaDB wrapper. Index records, query by semantic similarity + metadata filters.

```python
# Interface
class VectorStore:
    def __init__(self, config: Config): ...
    
    def upsert(self, records: list[dict]) -> int:
        """Index/update records. Returns count upserted."""
    
    def query(self, question: str, top_k: int = 4,
              filters: dict | None = None) -> list[dict]:
        """Semantic search + optional metadata filter."""
    
    def count(self) -> int:
        """Total indexed documents."""
    
    def health(self) -> dict:
        """ChromaDB status check."""
    
    def delete_all(self) -> None:
        """Reset index (for re-indexing)."""
```

**Design decisions:**
→ ChromaDB with `all-MiniLM-L6-v2` embedding function (REQ-F03, D-03, D-06).
→ Collection name: `chemtrace_invoices`.
→ Document ID = SHA-256 hash of source PDF → upsert handles deduplication (REQ AC-09).
→ Metadata fields stored as ChromaDB metadata (filterable): site, period, energy_type.
→ `content` field = generated text summary (used for embedding + retrieval).
→ Persist directory configurable via `.env` (Docker volume mount).

### 2.5 rag_client.py

**Responsibility:** Answer questions using retrieved context + Ollama LLM.

```python
# Interface
def ask(question: str, config: Config, store: VectorStore) -> RAGResponse:
    """Full RAG pipeline: retrieve → augment → generate."""
    ...

@dataclass
class RAGResponse:
    answer: str
    sources: list[dict]      # retrieved documents used
    model: str               # Ollama model used
    tokens_used: int | None  # if available from Ollama response
```

**Design decisions:**
→ Ollama HTTP API (`http://localhost:11434/api/chat`). Standard REST, no SDK dependency.
→ System prompt + safety message from original RAG client (proven, tested with guardrails).
→ Context injection: retrieved docs formatted as structured text in user message.
→ Off-topic detection: system prompt instructs refusal. No code-level filter needed for MVP.
→ Response includes `sources` list → user can verify which invoices were cited.

**Ollama integration pattern:**
```python
import requests

def _call_ollama(messages: list[dict], config: Config) -> str:
    response = requests.post(
        f"{config.ollama_base_url}/api/chat",
        json={
            "model": config.ollama_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": config.rag_temperature,
                "num_predict": config.rag_max_tokens,
            }
        }
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
```

→ No SDK. Pure HTTP. Minimal dependency. Works with any Ollama-compatible server.

### 2.6 cli.py

**Responsibility:** CLI entry point using `argparse` (no extra dependency like click/typer for MVP).

```python
# Commands
chemtrace parse [--input-dir PATH] [--output-dir PATH]
chemtrace ask "question"
chemtrace status
chemtrace export [--output PATH]
```

→ Each command maps to one function call. No complex state management.

---

## 3. FILE STRUCTURE (FINAL)

```
C:\Chemtrace\
├── .specs/
│   ├── PROJECT.md
│   ├── REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── STATE.md
│   └── phases/
│       ├── 01-pipeline-core/
│       │   ├── CONTEXT.md
│       │   ├── PLAN-01.md
│       │   └── VERIFY.md
│       ├── 02-rag-client/
│       └── 03-docker-deploy/
├── .skills/
│   ├── PROMPT_CONTRACT.md
│   └── CODE_VERIFIER.md
├── CLAUDE.md
├── src/
│   └── chemtrace/
│       ├── __init__.py
│       ├── __main__.py       ← entry point (python -m chemtrace)
│       ├── cli.py
│       ├── config.py
│       ├── pdf_parser.py
│       ├── parser_patterns.py
│       ├── etl.py
│       ├── vector_store.py
│       ├── rag_client.py
│       └── utils.py
├── data/
│   ├── sample_invoices/      ← synthetic PDFs
│   └── emission_factors/
│       └── factors.json      ← EF table with sources
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_etl.py
│   ├── test_vector_store.py
│   └── test_rag.py
├── output/                   ← generated CSV + errors
├── chroma_db/                ← ChromaDB persistence (gitignored)
├── .env.example
├── .env                      ← gitignored
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 4. DOCKER ARCHITECTURE

```yaml
# docker-compose.yml
services:
  chemtrace:
    build: .
    volumes:
      - ./data/sample_invoices:/app/data/sample_invoices:ro
      - ./output:/app/output
      - chroma_data:/app/chroma_db
      - ./.env:/app/.env:ro
    depends_on:
      - ollama
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_models:/root/.ollama
    # GPU passthrough (optional):
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

volumes:
  chroma_data:
  ollama_models:
```

**Design decisions:**
→ Two containers: app + Ollama. ChromaDB embedded in app container (not separate service → simpler).
→ Ollama model pulled on first run via entrypoint script.
→ Volumes: input PDFs read-only, output writable, ChromaDB persistent, Ollama models persistent.
→ GPU optional via docker-compose override (not default → most PYMEs don't have GPU servers).

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/emission_factors/ data/emission_factors/
COPY .env.example .env.example

# Entrypoint script handles Ollama model pull on first run
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "chemtrace", "status"]
```

---

## 5. CONFIGURATION MANAGEMENT

### .env.example
```bash
# === ChemTrace Configuration ===

# Paths (defaults work for Docker; override for local dev)
CHEMTRACE_INPUT_DIR=./data/sample_invoices
CHEMTRACE_OUTPUT_DIR=./output
CHEMTRACE_CHROMA_DIR=./chroma_db

# Ollama (LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# RAG parameters
RAG_TOP_K=4
RAG_TEMPERATURE=0.2
RAG_MAX_TOKENS=555

# Embedding model (sentence-transformers, runs locally)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Logging
LOG_LEVEL=INFO
```

→ Zero secrets. No API keys. Nothing to leak.

### emission_factors/factors.json
```json
{
  "electricity_de_grid_mix": {
    "value": 0.000380,
    "unit": "tCO2e/kWh",
    "source": "UBA Emissionsfaktoren",
    "year": 2024,
    "note": "[Pendiente verificación UBA 2024]"
  },
  "natural_gas": {
    "value": 0.000202,
    "unit": "tCO2e/kWh",
    "source": "Synthetic ESG Report (ChemTrace demo data)",
    "year": 2024,
    "note": "Based on typical European natural gas factor"
  },
  "diesel": {
    "value": 0.002680,
    "unit": "tCO2e/litre",
    "source": "Synthetic ESG Report (ChemTrace demo data)",
    "year": 2024,
    "note": "Based on typical European diesel factor"
  }
}
```

→ Every factor has `source` + `year` + `note` → audit-ready (REQ-NF03).

---

## 6. SECURITY CONSIDERATIONS

| Area | Risk | Mitigation |
|---|---|---|
| API keys | None in codebase (zero cloud) | No keys needed. .env has only paths and model names. |
| PDF injection | Malicious PDFs could exploit parser | pdfplumber is read-only, no code execution. Validate file size <10MB before parsing. |
| Ollama prompt injection | User question could trick LLM | System prompt constrains to indexed data only. Safety message blocks harmful content. |
| Docker network | Ollama port exposed | docker-compose internal network only. No external port binding by default. |
| Data at rest | ChromaDB stores invoice data | Local disk only. No cloud sync. Docker volume with standard file permissions. |
| Dependency supply chain | pip packages | Pin versions in requirements.txt. Use `pip audit` in CI (post-MVP). |

---

## 7. CLAUDE CODE SKILLS

Two skills to create in `.skills/` folder for Claude Code sessions:

### 7.1 PROMPT_CONTRACT.md

Purpose: Enforce structured prompts for every Claude Code task. Prevents lazy/ambiguous execution.

```
# PROMPT CONTRACT — ChemTrace

## Before ANY task, Claude Code must receive:

### GOAL (1 line)
What exactly should change after this task is done?

### CONSTRAINTS
→ Which files can be touched (whitelist)
→ Which files must NOT be touched
→ Max lines of code changed (estimate)

### FAILURE MODES
→ What breaks if this is done wrong?
→ What downstream depends on this?

### OUTPUT FORMAT
→ Expected file changes (list)
→ Expected test results
→ Expected CLI behavior after change

### VERIFICATION
→ How to confirm success (commands to run)
→ What to grep/check after completion

## If any section is missing → Claude Code must ASK before executing.
```

### 7.2 CODE_VERIFIER.md

Purpose: Exhaustive verification sub-agent. Runs after every execution phase.

```
# CODE VERIFIER — ChemTrace

## Trigger: After ANY code execution, before commit.

## Verification Protocol:

### 1. STATIC ANALYSIS
→ Type errors (mypy or manual check)
→ Import chain: every import resolves
→ No hardcoded values (grep for strings that should be config)
→ No TODO/FIXME left unmarked

### 2. SECURITY AUDIT
→ No secrets in code (grep for key, password, token, secret)
→ No eval/exec calls
→ No shell injection vectors (subprocess with user input)
→ File operations use Path (not string concatenation)
→ External input (PDF content) never executed as code

### 3. E2E SIMULATION
→ Trace happy path: input → every function call → output
→ Identify: what if input is None? Empty? Wrong type?
→ Identify: what if external service (Ollama) is down?
→ Identify: what if PDF is empty? Corrupted? Too large?

### 4. HYPOTHESIS TESTING
→ For each bug fix: create hypothesis of root cause
→ Verify hypothesis with specific test case
→ Confirm fix addresses root cause (not symptom)
→ Check: does fix introduce new failure modes?

### 5. FALSE POSITIVE DETECTION
→ Review test results: are "passing" tests actually testing the right thing?
→ Check: are assertions specific enough? (not just "assert True")
→ Check: do mocks hide real failures?

### 6. DoD VERIFICATION
→ Run through all acceptance criteria from REQUIREMENTS.md
→ Each criterion: PASS / FAIL / NOT YET TESTABLE
→ Confidence score: 0.0-1.0

## Output format:
| Check | Status | Finding | Action |
|-------|--------|---------|--------|
| ...   | ✅/⚠️/❌ | ...    | ...    |
```

---

## 8. DEPENDENCY LIST (requirements.txt)

```
# Core
pdfplumber>=0.10.0
pandas>=2.0.0
python-dotenv>=1.0.0

# Vector store
chromadb>=0.4.0
sentence-transformers>=2.2.0

# LLM client (pure HTTP, no SDK)
requests>=2.31.0

# Testing
pytest>=7.0.0

# Utility
hashlib  # stdlib, no install needed
```

→ 6 external dependencies for production. Minimal surface area.
→ sentence-transformers pulls torch → Docker image will be ~2GB. Acceptable trade-off for local embeddings.

**Alternative to reduce image size (post-MVP):** Use `onnxruntime` + ONNX export of MiniLM instead of full torch. Cuts ~1.5GB.

---

## 9. TESTING STRATEGY

| Module | Test type | Key scenarios |
|---|---|---|
| pdf_parser | Unit | Parse each of 5 sample invoices → correct fields extracted. Empty PDF → graceful error. |
| etl | Integration | Batch 5 PDFs → correct DataFrame + CSV. Error in 1 PDF → others still processed. |
| vector_store | Unit | Upsert 5 records → count = 5. Upsert same → count still 5 (dedup). Query "electricity" → returns electricity records. |
| rag_client | Integration | Requires Ollama running. Ask factual question → answer contains correct numbers + sources. Off-topic → refusal. |
| cli | E2E | `parse` → CSV exists. `status` → shows count. `ask` → returns answer. |

→ Tests for parser + etl + vector_store can run without Ollama (no LLM dependency).
→ RAG tests require Ollama → marked as integration tests, run separately.

---

## 10. OPEN QUESTIONS (to resolve in Phase execution)

| # | Question | When to resolve | Impact |
|---|---|---|---|
| OQ-01 | Exact UBA 2024 emission factor for German electricity grid mix | Phase 01, before EF config | Low (use 0.000380 as reasonable estimate) |
| OQ-02 | llama3.1:8b vs phi-3 vs mistral:7b performance on RAG task | Phase 02, during RAG testing | Medium (affects response quality) |
| OQ-03 | sentence-transformers Docker image size optimization | Phase 03 | Low (functional without it) |

---

## 11. DECISION LOG (continued from REQUIREMENTS.md)

| # | Decision | Rationale | Date |
|---|---|---|---|
| D-08 | pdfplumber two-pass strategy (tables + regex text) | Tables for line items, regex for header fields. Covers all current invoice formats. | 2026-03-23 |
| D-09 | ParseResult wrapper (never throw from parser) | Caller always gets clean response. Errors logged, not propagated. | 2026-03-23 |
| D-10 | SHA-256 hash as ChromaDB document ID | Deduplication + audit trail in one field. | 2026-03-23 |
| D-11 | Ollama via raw HTTP (no SDK) | Zero extra dependency. Works with any OpenAI-compatible API post-MVP. | 2026-03-23 |
| D-12 | argparse for CLI (no click/typer) | Stdlib only. 4 commands don't justify extra dependency. | 2026-03-23 |
| D-13 | ChromaDB embedded (not separate Docker service) | Simpler compose. PYME installs don't need distributed DB for <1000 docs. | 2026-03-23 |
| D-14 | Two Claude Code skills (Prompt Contract + Code Verifier) | Enforce quality gates during execution. Prevent lazy/ambiguous prompts. | 2026-03-23 |

---

*SDD Gate 2 complete. Awaiting approval to proceed to Phase 01 CONTEXT.md + PLAN-01.md (Gate 3).*
