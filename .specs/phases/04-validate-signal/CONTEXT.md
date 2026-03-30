# CONTEXT.md — Phase 04: Validate and Signal
**Phase:** 04-validate-signal
**Duration:** 5 weeks (31 mar → 30 abr 2026)
**Gate:** Docker image < 4 GB + LLM decision documented + SAP CSV connector tested + 5 outreach messages sent
**Depends on:** Phase 03 COMPLETE ✅ (v0.3.0-docker-deploy, e2e 7/7 PASS, 75 tests, CODE_VERIFIER 0.96)
**SDD Gate:** 3 of 5 (Specify ✅ → Design ✅ → Plan → Execute → Verify)

---

## 1. PHASE OBJECTIVE

Optimize Docker image from 9 GB to ~3→4 GB (torch CPU-only + multi-stage build), evaluate LLM alternatives (phi3:mini vs llama3.2:3b), add SAP CSV connector as second data input path, and begin NRW SME outreach + public visibility.

Unlike Phases 01→03 (single-week code sprints), Phase 04 is a 5-week mixed phase with 3 technical tracks and 2 non-technical tracks. Only the technical tracks have formal Technical Decisions below.

---

## 2. WHAT EXISTS (from Phase 01 + 02 + 03)

### Code complete (MVP shipped):
→ `src/chemtrace/` → 9 modules: config, pdf_parser, parser_patterns, etl, vector_store, rag_client, prompts, cli, utils
→ `tests/` → 73 unit + 2 integration tests, all pass
→ `data/sample_invoices/` → 6 PDFs (5 invoices + 1 ESG report)
→ `data/emission_factors/factors.json` → emission factors with sources
→ `Dockerfile` → single-stage python:3.11-slim (current: 9.14 GB image)
→ `docker-compose.yml` → app + ollama services
→ `scripts/entrypoint.sh` → Python-based Ollama health check + command routing
→ `README.md` → bilingual EN/DE
→ `.env.example` → all config documented

### Files to MODIFY in this phase:
→ `requirements.txt` → torch CPU-only index/pin (Track 1, S2)
→ `Dockerfile` → multi-stage build (Track 1, S2)
→ `src/chemtrace/config.py` → OLLAMA_MODEL default if phi3:mini wins (Track 2, S3)
→ `src/chemtrace/prompts.py` → system prompt improvements (Track 2, S3)
→ `README.md` → add demo GIF (S1), update image size post-optimization (S2)
→ `src/chemtrace/etl.py` → add CSV auto-detection in file iteration loop (TD-06, Track 3, S4)

### Files to CREATE in this phase:
→ `src/chemtrace/sap_parser.py` → SAP CSV parsing module (Track 3, S4)
→ `tests/test_sap_parser.py` → unit tests for SAP parser (Track 3, S4)
→ `data/sample_sap/` → synthetic SAP CSV sample (Track 3, S4)
→ `.specs/phases/04-validate-signal/CONTEXT.md` (this file)
→ `.specs/phases/04-validate-signal/PLAN-04.md`
→ `.specs/phases/04-validate-signal/VERIFY.md` (post-execution)

### Known issues entering this phase:
→ Docker image 9.14 GB (torch pulls CUDA deps)
→ WSL2 requires memory=4GB in .wslconfig
→ Embedding model re-downloads per container run (no HF cache volume mount)
→ llama3.2:3b limited for complex multi-document queries
→ Disk ~46 GB free (tight for rebuilds)

---

## 3. TECHNICAL DECISIONS

### Track 1: Docker Image Optimization (Week 2)

#### TD-01: torch CPU-only installation strategy

**Problem:** `sentence-transformers` pulls `torch` with full CUDA runtime (~4.5 GB). ChemTrace runs on CPU only (no GPU). This is the single largest contributor to the 9.14 GB image.

**Decision:** Use `--extra-index-url https://download.pytorch.org/whl/cpu` in pip install to pull CPU-only torch wheels.

**Alternatives considered:**
→ Option A (chosen): `--extra-index-url` flag in Dockerfile pip install. Keeps requirements.txt clean, targets Docker only.
→ Option B: Pin `torch==X.Y.Z+cpu` explicitly in requirements.txt. More explicit, but breaks local dev on machines with GPU (force-installs CPU variant).
→ Option C: Separate `requirements-docker.txt` with CPU pins. Adds file maintenance overhead for 1 line difference.

**Rationale for Option A:**
→ requirements.txt stays universal (works on any machine).
→ CPU-only constraint is a Docker concern, belongs in Dockerfile.
→ `--extra-index-url` is pip's official mechanism for alternative package indices.
→ Precedent: PyTorch's own documentation recommends this approach.

**Pre-execution gate (MANDATORY):**
→ Run `pip install sentence-transformers --dry-run 2>&1 | grep torch` to identify exact torch version required.
→ Verify CPU wheel exists at `https://download.pytorch.org/whl/cpu/` for that version.
→ If wheel does NOT exist → ABORT and document. Fallback to Option B or defer to ONNX (Day 61-90).

**Expected result:** torch drops from ~4.5 GB to ~200-300 MB (CPU-only). Total image: ~3-4 GB.

#### TD-02: Multi-stage Dockerfile

**Problem:** Current single-stage image includes gcc, build-essential, pip cache, and build artifacts alongside runtime code.

**Decision:** Two-stage Dockerfile: build stage installs everything, runtime stage copies only installed packages + app code.

**Structure:**
```dockerfile
# Stage 1: Build
FROM python:3.11-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ src/
COPY data/ data/
COPY .env.example .env.example
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PYTHONPATH=/app/src
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "chemtrace", "status"]
```

**Key decisions within:**
→ `--prefix=/install` in build stage → allows clean COPY to /usr/local in runtime (no pip cache, no build tools).
→ gcc NOT in runtime stage → saves ~100 MB.
→ python:3.11-slim for both stages (not alpine) → consistent with Phase 03 TD-01 rationale (torch/sentence-transformers fail on musl).
→ `--no-cache` flag required on FIRST build after torch swap to avoid stale layers.

**Risk:** `--prefix=/install` + COPY to `/usr/local` might miss some packages that install to non-standard locations. Mitigation: import tests post-build (verify chemtrace.config, chemtrace.vector_store imports work).

**CONSTRAINT:** Both stages MUST use the identical base image tag (`python:3.11-slim`, never `python:3-slim` or `python:slim`) to ensure site-packages paths match between build and runtime. If base image diverges, `--prefix` install structure won't align with runtime Python's `sys.path`.

#### TD-03: Embedding model compatibility

**Question:** Does `all-MiniLM-L6-v2` (via sentence-transformers) work correctly with torch CPU-only?

**Answer:** Yes. sentence-transformers uses torch for tensor operations only. MiniLM-L6-v2 does not require CUDA kernels. CPU inference works identically (slower, but embeddings are computed once per parse, not per query).

**No change required** to embedding model or vector_store.py. Verify with:
```
docker run --rm chemtrace:v0.4.0 python -c "from chemtrace.vector_store import VectorStore; print('OK')"
```

### Track 2: LLM Evaluation (Week 3)

#### TD-04: phi3:mini as evaluation candidate

**Problem:** llama3.2:3b shows limitations on complex multi-document queries (e.g., "compare electricity across all months"). Need to evaluate if a different model improves quality within the same hardware constraints.

**Decision:** Test phi3:mini (~2.3 GB) as the primary alternative.

**Why phi3:mini over other candidates:**
→ mistral:7b (~4.1 GB): Too large for 8 GB RAM with Docker + ChromaDB + embedding model running simultaneously. OOM risk = high.
→ gemma:2b (~1.5 GB): Smaller than needed. Instruction-following quality likely lower for grounded RAG tasks, but no direct benchmark comparison available. [Pendiente verificación: gemma2:2b vs phi3:mini on instruction-following RAG tasks]
→ qwen2:1.5b (~1.0 GB): Same concern as gemma. Too small for grounded RAG with source citation.
→ phi3:mini (~2.3 GB): Microsoft model optimized for instruction-following on constrained hardware. Good balance of size vs quality for RAG tasks. Well-documented Ollama support.

**Evaluation protocol:** 5 queries from VERIFY.md e2e, 4 binary criteria (source citation, numeric accuracy, guardrail refusal, latency < 15s). Model with ≥3/4 PASS wins. Tie → llama3.2:3b stays (zero migration cost).

**If phi3:mini wins:** Update `config.py` default, update `.env.example`, update README. If llama3.2:3b wins: document decision, zero code changes.

#### TD-05: Prompting improvements scope

**Current state:** System prompt (prompts.py) uses numbered rules, works well with llama3.2:3b (0 prompt tuning iterations needed in Phase 02).

**Improvement candidates (test both models):**
→ (a) Add explicit "ALWAYS include the source file name" reinforcement (current: mentioned once)
→ (b) Add "If multiple documents match, list ALL with their values" for comparison queries
→ (c) Add output format template: "Source: [filename] | Value: [number] [unit]"

**Constraint:** Max 3 iterations of prompt tuning (80/20 rule). If no measurable improvement after 3 tries → ship current prompt.

**Measurable improvement = at least 1 of:**
→ Previously failing query now passes
→ Source citation now appears where it was missing
→ Numeric accuracy improves on comparison query (#4)

### Track 3: SAP CSV Connector (Week 4)

#### TD-06: SAP CSV connector architecture

**Problem:** Current pipeline only accepts PDF invoices. German SMEs using SAP ECC or S/4HANA export energy consumption data as CSV. Adding CSV as a second input path broadens addressable market.

**Decision:** New module `sap_parser.py` that follows the same interface pattern as `pdf_parser.py`.

**Integration pattern:**
```
data/sample_invoices/*.pdf  →  pdf_parser.py  →  ParseResult
data/sample_sap/*.csv       →  sap_parser.py  →  ParseResult  (same dataclass)
                                                      ↓
                                                   etl.py  (unchanged)
                                                      ↓
                                              ChromaDB + CSV export
```

**Key architectural decision:** `sap_parser.py` returns the SAME `ParseResult` dataclass used by `pdf_parser.py`. This means:
→ etl.py requires ZERO changes (polymorphic input)
→ vector_store.py requires ZERO changes
→ rag_client.py requires ZERO changes
→ CLI gets a new flag or auto-detection: `chemtrace parse data/` processes both PDFs and CSVs in the directory

**Auto-detection logic (in etl.py):**
```python
for file in input_dir.iterdir():
    if file.suffix == '.pdf':
        result = parse_invoice(file)        # existing
    elif file.suffix == '.csv':
        result = parse_sap_csv(file)        # new
    else:
        log_warning(f"Unsupported file: {file}")
```

**Why not a generic "connector" abstraction?**
→ Over-engineering for 2 input types. A simple if/elif in etl.py is sufficient.
→ YAGNI: if a third connector is needed (OCR, API), refactor then.
→ Keeping it simple means SAP connector can ship in 3h.

**Caveat:** Auto-detection assumes ALL `.csv` files in input_dir are SAP energy export format. A non-SAP CSV will produce parse warnings or incorrect results. Post-MVP: add `--input-type pdf|sap-csv` CLI flag for explicit override. MVP: document this assumption in README.

#### TD-07: SAP CSV expected format

**Status:** [Pendiente verificación → Task 3.6 in PLAN-04 researches actual format]

**Working assumptions (based on SAP ECC standard energy data management export):**
→ Delimiter: semicolon (`;`) → standard in German/European CSV exports
→ Encoding: UTF-8 or ISO-8859-1 (must handle both)
→ Headers likely include: Werk/Plant, Zeitraum/Period, Energieart/Energy Type, Verbrauch/Consumption, Einheit/Unit, Kosten/Cost, Währung/Currency
→ German number format: `1.234,56` (dot as thousands separator, comma as decimal)

**Mitigation for format unknowns:**
→ Task 3.6 (S3) researches actual format before coding
→ If no real sample by S4: generate synthetic CSV based on research
→ Outreach messages (S4-S5) explicitly request "anonymized energy export CSV" as conversation starter
→ Parser must handle both German (`1.234,56`) and English (`1,234.56`) number formats

#### TD-08: SAP parser testing strategy

**Unit tests (no external dependencies):**
→ Parse synthetic SAP CSV → correct ParseResult fields
→ Handle German number format (`1.234,56` → 1234.56)
→ Handle missing columns gracefully (return None + warning)
→ Handle empty CSV → graceful error
→ Handle wrong delimiter (comma vs semicolon) → auto-detect or error

**Integration (requires existing pipeline):**
→ Mix PDFs + CSVs in same input_dir → etl.py processes both
→ ChromaDB contains records from both sources
→ RAG query retrieves data from both PDF and CSV sources

---

## 4. NON-TECHNICAL TRACKS (no TDs needed, decisions made inline during execution)

| Track | Scope | Decision venue |
|---|---|---|
| Demo GIF (S1) | Tool selection, recording, README embed | Inline during S1 |
| ACHEMA Founder Award (S1) | Research deadline, eligibility | Browser research, document result |
| NRW outreach (S3-S5) | Target selection, CTA, templates, tracker | PLAN-04.md (CTA block, tracker task) |
| LinkedIn second post (S5) | Content, timing | Same pattern as first post (S5 handoff) |

These tracks are operationally simple and don't warrant formal TDs. Decisions captured in PLAN-04.md task descriptions and session handoffs.

---

## 5. RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| torch CPU wheel doesn't exist for required version | Low | High | Pre-check gate (TD-01). Fallback: explicit pin or defer to ONNX. |
| `--prefix=/install` COPY misses packages | Low | High | Import tests post-build. Fallback: pip install in single stage with cache cleanup. |
| phi3:mini OOM on 8 GB | Medium | Low | If OOM, stay with llama3.2:3b. Decision in 5 minutes. |
| SAP CSV format assumptions wrong | Medium | Medium | Research in S3 (TD-07). Synthetic fallback. Validate with outreach contacts. |
| sentence-transformers incompatible with CPU torch | Low | High | Import test before full rebuild. Same torch version, different build. Should work. |
| Multi-doc query quality doesn't improve | Medium | Low | Accept current quality. Prompting has diminishing returns → 80/20 STOP after 3 iterations. |

---

## 6. ARCHITECTURE DECISION RECORD

| # | Decision | Rationale | Date |
|---|---|---|---|
| D-018 | torch CPU-only via `--extra-index-url` in Dockerfile (not requirements.txt) | Keeps requirements.txt universal. CPU constraint is Docker-specific. | 2026-03-30 |
| D-019 | Multi-stage Dockerfile with `--prefix=/install` | Removes gcc, build cache, pip artifacts from runtime. Expected ~50% image reduction. | 2026-03-30 |
| D-020 | phi3:mini as primary LLM evaluation candidate | Best size/quality ratio for 8 GB RAM. mistral too large, gemma/qwen too small. | 2026-03-30 |
| D-021 | SAP CSV parser returns same ParseResult as PDF parser | Polymorphic input → zero changes to etl.py, vector_store.py, rag_client.py. | 2026-03-30 |
| D-022 | Auto-detection by file extension in etl.py (not abstract connector) | YAGNI. 2 input types don't justify abstraction layer. Refactor if third connector needed. | 2026-03-30 |
| D-023 | No change to embedding model post-optimization | all-MiniLM-L6-v2 works on CPU torch. Verified by import test. | 2026-03-30 |

---

*Phase 04 context complete. See PLAN-04.md for execution tasks.*
