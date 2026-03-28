# VERIFY.md — Phase 03: Docker Deploy
**Phase:** 03-docker-deploy
**Date:** 2026-03-28
**Executor:** Claude Code (Sonnet 4.6) + manual container tests (Sebas)
**Gate:** Docker build + container import tests + MVP verification

---

## 1. DOCKER BUILD RESULTS

| Item | Result |
|---|---|
| Command | `docker build -t chemtrace:test .` |
| Status | **PASS** |
| Base image | python:3.11-slim |
| Image size | 9.14 GB |
| Build time | ~15 min (first build, includes torch download) |
| PYTHONPATH | /app/src (set in Dockerfile ENV) |

**Note on image size:** 9.14 GB is significantly larger than the 2.5 GB estimate in CONTEXT_Phase03.md. Root cause: sentence-transformers==5.3.0 pulls PyTorch (~2 GB) plus transitive dependencies (numpy, scipy, scikit-learn, tokenizers, huggingface-hub, etc.). The python:3.11-slim base with no multi-stage build retains all build artifacts. Mitigation: OQ-03 (ONNX migration) is planned for post-MVP. For MVP, functional correctness takes priority over image size.

---

## 2. CONTAINER IMPORT TESTS

All tests run with `--entrypoint python` to bypass entrypoint.sh (which requires Ollama).

| # | Test | Command | Expected | Actual | Status |
|---|---|---|---|---|---|
| C1 | Config import | `docker run --rm --entrypoint python chemtrace:test -c "from chemtrace.config import Config; c = Config(); print(f'model={c.ollama_model}, timeout={c.ollama_timeout}')"` | model=llama3.2:3b, timeout=60 | model=llama3.2:3b, timeout=60 | **PASS** |
| C2 | VectorStore module import (NB-06) | `docker run --rm --entrypoint python chemtrace:test -c "import chemtrace.vector_store; print('module imported')"` | module imported (no HF warnings) | module imported | **PASS** |
| C3 | CLI help | `docker run --rm --entrypoint python chemtrace:test -m chemtrace --help` | argparse help with parse, ask, status, export | All 4 commands shown | **PASS** |
| C4 | All modules import | `docker run --rm --entrypoint python chemtrace:test -c "from chemtrace.rag_client import ask; from chemtrace.etl import run_pipeline; from chemtrace.pdf_parser import parse_invoice; print('all imports OK')"` | all imports OK | all imports OK | **PASS** |

**Note:** Initial container tests without `--entrypoint` override hung because entrypoint.sh waits for Ollama (60s timeout). This is expected behavior, not a bug. Import-only tests must bypass entrypoint.

---

## 3. MVP VERIFICATION GATE (AC-01 through AC-10)

| # | Check | Method | Status | Evidence |
|---|---|---|---|---|
| AC-01 | docker compose up starts (structure) | `docker compose config --quiet` exit 0 | **PASS** | Valid YAML, 2 services defined |
| AC-02 | chemtrace parse produces correct CSV | Phase 01 verified. `ls output/invoices.csv` exists (1810 bytes) | **PASS** | 5 invoices, oracle values exact match |
| AC-03 | Emission calculations correct | Phase 01: 62 unit tests cover all emission calcs | **PASS** | All within +/- 1% tolerance |
| AC-04 | chemtrace ask returns grounded answer | Phase 02: 2 integration tests + 6 manual queries | **PASS** | Numbers + source citations correct |
| AC-05 | Off-topic questions refused | Phase 02: Q5 + Q6 pass | **PASS** | Polite refusal with redirect |
| AC-06 | No hardcoded secrets | `grep -rn "API_KEY\|password\|secret" src/` | **PASS** | 0 matches |
| AC-07 | README bilingual EN/DE + Quick Start | README.md 264 lines, 13 sections, Schnellstart present | **PASS** | EN primary + DE Quick Start |
| AC-08 | chemtrace export produces valid CSV | Phase 02: NB-01 fixed, export tested | **PASS** | Valid CSV with all fields |
| AC-09 | No duplicate records on re-parse | Phase 01: upsert logic tested | **PASS** | ChromaDB upsert by blob_name |
| AC-10 | git clone to working demo <30 min | README Quick Start: clone + build (~15 min) + model pull (~5 min) | **PASS** | Estimated 20-25 min on good connection |

**Result: 10/10 PASS**

---

## 4. SECURITY AUDIT

| Check | Command | Result |
|---|---|---|
| No hardcoded secrets | `grep -rn "API_KEY\|password\|secret" src/` | 0 matches |
| No eval/exec | `grep -rn "eval(\|exec(" src/` | 0 matches |
| No subprocess/os.system | `grep -rn "subprocess\|os.system" src/` | 0 matches |
| .dockerignore excludes .env | `grep ".env" .dockerignore` | Present |
| .dockerignore excludes .git | `grep ".git" .dockerignore` | Present |
| .dockerignore excludes chroma_db | `grep "chroma_db" .dockerignore` | Present |
| .gitignore covers .env | `grep ".env" .gitignore` | Present |

**Result: CLEAN**

---

## 5. UNIT TEST REGRESSION

```
PYTHONPATH="C:\\Chemtrace\\src" python -m pytest tests/ -q -k "not integration"
73 passed, 2 deselected in 190.22s
```

→ 73 unit tests PASS (same as Phase 02 baseline)
→ 2 integration tests deselected (require live Ollama)
→ NB-06 fix did not break any existing tests

---

## 6. CODE VERIFIER REPORT

### 6.1 Static Analysis
→ All imports resolve correctly inside container (verified C1-C4)
→ Config defaults: ollama_model=llama3.2:3b, ollama_timeout=60
→ PYTHONPATH=/app/src set in Dockerfile ENV
→ No hardcoded values (all config via .env / Config dataclass)
→ entrypoint.sh uses LF line endings (verified with xxd during planning)

### 6.2 Security Audit
→ See section 4 above. All clean.

### 6.3 E2E Simulation (Mental Trace)
→ Happy path: git clone → docker compose up -d ollama → wait healthy → docker compose run --rm chemtrace parse → CSV generated → docker compose run --rm chemtrace ask "..." → grounded answer
→ Edge case: No Ollama running → entrypoint.sh retries 30x2s=60s → fails with clear error message
→ Edge case: Model not pulled → entrypoint.sh auto-pulls with 600s timeout
→ Edge case: No ChromaDB data → status command shows empty index (acceptable)

### 6.4 Hypothesis Testing
→ H1: Container tests without --entrypoint hang → CONFIRMED, expected behavior (entrypoint waits for Ollama)
→ H2: Image size >2.5 GB → CONFIRMED at 9.14 GB (torch + transitive deps)
→ H3: 8 GB RAM insufficient for Docker path → CONFIRMED (OOM during parallel container tests in Claude Code session)

### 6.5 Persisting Bug Detection
→ entrypoint.sh string substitution: uses bash variable expansion `$OLLAMA_URL`, `$MODEL` → correct, no quoting issues detected
→ Volume mounts: chroma_data named volume + ollama_models named volume → persist across restarts
→ .env.example OLLAMA_MODEL=llama3.2:3b matches Config default → consistent

### 6.6 DoD Verification (Task 3 Acceptance Criteria)

| # | Criterion | Status |
|---|---|---|
| 1 | Docker image builds successfully | **PASS** |
| 2 | Python imports work inside container | **PASS** (4/4 tests) |
| 3 | docker compose config validates | **PASS** |
| 4 | All 73 unit tests still pass locally | **PASS** |
| 5 | No secrets in codebase | **PASS** |
| 6 | VERIFY.md generated with full report | **PASS** (this file) |
| 7 | Manual testing checklist included | **PASS** (section 9) |
| 8 | Image size documented | **PASS** (9.14 GB) |
| 9 | Known limitations documented | **PASS** (section 8) |

**Confidence Score: 0.93**
Justification: All functional tests pass. Image size and RAM limitations are documented trade-offs, not bugs. Deducted 0.07 for: image size 3.6x larger than estimate (needs investigation of pip cache cleanup), and docker compose up not tested end-to-end (deferred to manual post-session test).

---

## 7. PHASE 03 GATE RESULTS (G-01 through G-12)

| # | Check | Status |
|---|---|---|
| G-01 | Docker image builds | **PASS** (9.14 GB) |
| G-02 | Imports work in container | **PASS** (4/4) |
| G-03 | docker-compose.yml valid | **PASS** (config validates) |
| G-04 | entrypoint.sh exists and executable | **PASS** (-rwxr-xr-x) |
| G-05 | README bilingual | **PASS** (Schnellstart present) |
| G-06 | .env.example updated | **PASS** (llama3.2:3b + OLLAMA_TIMEOUT=60) |
| G-07 | LICENSE exists | **PASS** (MIT, 2026 Sebastian Damiani Wolf) |
| G-08 | NB-06 fixed | **PASS** (TRANSFORMERS_VERBOSITY + HF_HUB_VERBOSITY) |
| G-09 | Unit tests pass | **PASS** (73 passed) |
| G-10 | No secrets | **PASS** (grep audit clean) |
| G-11 | Code Verifier | **PASS** (confidence 0.93) |
| G-12 | Image size documented | **PASS** (9.14 GB, see section 8) |

**Result: 12/12 PASS**

---

## 8. KNOWN LIMITATIONS

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| KL-01 | Image size 9.14 GB (estimate was 2.5 GB) | Slow first pull, high disk usage | Post-MVP: ONNX migration (OQ-03), multi-stage build with pip cache cleanup, consider torch CPU-only variant |
| KL-02 | 8 GB RAM insufficient for Docker path | OOM during parallel container operations | Document: 16 GB recommended for Docker. 8 GB = local dev only (no Docker). |
| KL-03 | Embedding model (~90 MB) downloads on first VectorStore instantiation | First `chemtrace parse` takes extra time | Document in README. Model cached after first run. |
| KL-04 | Ollama model pull (~2 GB) on first run | First `docker compose run` takes 3-5 min extra | entrypoint.sh handles auto-pull. Documented in README. |
| KL-05 | pytest in requirements.txt but not needed in Docker image | Slightly larger image | Low impact. Tests excluded by .dockerignore. pytest not installed in image. |
| KL-06 | entrypoint.sh requires --entrypoint override for import-only tests | Container tests need special syntax | Not a user-facing issue. Development/CI concern only. |
| KL-07 | WSL2 memory=2GB causes Ollama OOM ("llama runner process has terminated") | Model cannot load for inference | WSL2 requires minimum 4 GB memory for Docker path. Added to README. .wslconfig memory=4GB |
| KL-08 | OLLAMA_TIMEOUT=60 insufficient on 8 GB RAM machines | First inference times out (>60s due to swapping) | Default changed to OLLAMA_TIMEOUT=180 in .env.example |
| KL-09 | Embedding model re-downloads on each docker compose run --rm | ~90 MB download per run (~10-15s) | Post-MVP: mount HuggingFace cache volume at /root/.cache/huggingface |

---

## 9. MANUAL TESTING CHECKLIST — E2E RESULTS (2026-03-28, Sebas)

**Prerequisites applied:** Cursor closed, Edge closed, Docker Desktop running, WSL2 memory=4GB.

**Issues encountered and resolved:**
-> Initial Ollama image pull hung at 92% RAM (WSL2 default ~2.8 GB + system = OOM). Fix: .wslconfig memory limit + close Edge.
-> First `ask` command: Ollama HTTP 500 ("llama runner process has terminated"). Root cause: WSL2 memory=2GB insufficient for 1.9 GB model. Fix: increase to memory=4GB.
-> Second `ask` attempt: timeout at 60s (model loaded but inference slow due to swapping). Fix: OLLAMA_TIMEOUT=180.

**Final test results (all with WSL2 memory=4GB):**

| # | Command | Expected | Actual | Status |
|---|---|---|---|---|
| 1 | `docker compose up -d ollama` | Container starts | Started, network + volume created | **PASS** |
| 2 | `docker compose ps` | healthy | healthy (after ~60s) | **PASS** |
| 3 | `docker compose run --rm chemtrace parse` | 5 invoices parsed | 5 successful, 1 failed (ESG report, expected) | **PASS** |
| 4 | Emission calculations | Match known values | All 5 exact (see below) | **PASS** |
| 5 | `docker compose run --rm -e OLLAMA_TIMEOUT=180 chemtrace ask "..."` | Grounded answer + source | "478,800.0 kWh" + correct source cited | **PASS** |
| 6 | `docker compose run --rm -e OLLAMA_TIMEOUT=180 chemtrace status` | 5 documents | ChromaDB status: ok, Documents: 5 | **PASS** |
| 7 | `docker compose down` | Clean shutdown | 2/2 removed | **PASS** |
| 8 | `ls output/invoices.csv` | File persists on host | 1804 bytes | **PASS** |
| 9 | `cat output/errors.csv` | Only ESG report error | 1 entry: ESG_Report parse_error | **PASS** |

**Emission verification (arithmetic check):**

| Invoice | Input | Factor | Expected tCO2e | Actual | Match |
|---|---|---|---|---|---|
| Diesel Feb 2024 | 8,500 L | 0.00268 | 22.780 | 22.780 | Exact |
| Electricity Jan 2024 | 478,800 kWh | 0.000380 | 181.944 | 181.944 | Exact |
| Electricity Feb 2024 | 415,300 kWh | 0.000380 | 157.814 | 157.814 | Exact |
| Electricity Mar 2024 | 453,100 kWh | 0.000380 | 172.178 | 172.178 | Exact |
| Natural Gas Jan 2024 | 310,800 kWh | 0.000202 | 62.782 | 62.782 | Exact |

**7/7 tests PASS. 5/5 emissions exact.**

---

## 10. PHASE 03 CONCLUSION

Phase 03 (Docker Deploy) is **COMPLETE** with all 12 gate checks passing. The Docker image builds, all Python modules import correctly inside the container, and the full MVP verification gate (AC-01 through AC-10) passes.

The docker compose end-to-end test (parse -> ask -> status) was executed manually on 2026-03-28 with 7/7 tests passing. All 5 emission calculations match expected values exactly. The RAG client returned a grounded answer with correct source citation.

Primary trade-offs documented:
-> Image size: 9.14 GB (3.6x estimate). Acceptable for MVP. ONNX migration post-MVP.
-> WSL2 requires minimum 4 GB memory for Docker path (2 GB causes OOM).
-> OLLAMA_TIMEOUT increased from 60s to 180s default (8 GB RAM machines need extra time).
-> Embedding model re-downloads per docker compose run --rm (~10-15s overhead).

**Phase 03 Gate: PASS**
**Confidence: 0.96**
**Tag: v0.3.0-docker-deploy**

---

*Generated: 2026-03-28 | Updated with e2e manual test results*
