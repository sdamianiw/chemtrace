# PLAN-03.md — Phase 03: Docker Deploy
**Phase:** 03-docker-deploy
**Tasks:** 3 (max per SDD rules)
**Total budget:** 8h
**Execution tool:** Claude Code via Cursor (Sonnet 4.6)
**Planning tool:** claude.ai Opus 4.6 (this chat)

---

## PRE-FLIGHT CHECKLIST (before opening Claude Code)

```bash
# === STEP 1: Verify Docker Desktop is running ===
docker --version
# Expected: Docker version 2x.x.x or similar
docker compose version
# Expected: Docker Compose version v2.x.x

# === STEP 2: Verify Phase 02 state ===
cd /c/Chemtrace
git status                    # clean working tree
git log --oneline -3          # last commit: 5b6218f or later
git tag -l "v0.2*"            # v0.2.0-rag-client present

# === STEP 3: Verify tests still pass ===
PYTHONPATH="C:\\Chemtrace\\src" python -m pytest tests/ -q -k "not integration"
# Expected: 73 passed

# === STEP 4: RAM preparation ===
# Close before running Claude Code:
#   → Edge/Chrome (all tabs)
#   → Any non-essential apps
# Keep: Cursor, Docker Desktop
# Note: Ollama does NOT need to be running for Task 1 and Task 2

# === STEP 5: Claude Code fresh context ===
# /clear in Claude Code
# Use: claude --dangerously-skip-permissions
```

---

## TASK 1: Docker Infrastructure + NB-06 Fix (3h)

### Goal
Create Dockerfile, docker-compose.yml, entrypoint.sh, .dockerignore. Fix NB-06 HF warnings. Update requirements.txt with pinned versions.

### Claude Code Prompt (copy-paste ready)

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\\Chemtrace\\src" python ...
PYTHONPATH="C:\\Chemtrace\\src" pytest ...
This is a known workaround (pip install -e . fails on this machine).

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/phases/03-docker-deploy/CONTEXT.md (all sections, especially TD-01 through TD-04)
- .specs/ARCHITECTURE.md (section 4: Docker Architecture)
- src/chemtrace/vector_store.py (current env vars block, lines 1-10)
- requirements.txt (current state)
- .skills/PROMPT_CONTRACT.md
- .skills/CODE_VERIFIER.md

GOAL: Create Docker infrastructure files + fix NB-06 (HF Hub warning suppression).

CONSTRAINTS:
→ Files to CREATE: Dockerfile, docker-compose.yml, scripts/entrypoint.sh, .dockerignore
→ Files to MODIFY: requirements.txt (pin to tested versions), src/chemtrace/vector_store.py (NB-06: add 2 env vars)
→ Files NOT to touch: any other src/ files, tests/, .specs/ (except reading)
→ Dockerfile must use python:3.11-slim base
→ docker-compose.yml must have 2 services: chemtrace + ollama
→ entrypoint.sh must use Python (not curl) for Ollama checks
→ NB-06 fix: add TRANSFORMERS_VERBOSITY=error and HF_HUB_VERBOSITY=error to vector_store.py env block

IMPORTANT DECISIONS (from CONTEXT.md, follow exactly):
→ TD-01: python:3.11-slim, PYTHONPATH=/app/src, no multi-stage
→ TD-02: ollama healthcheck uses "ollama list", start_period 30s, depends_on condition service_healthy
→ TD-03: entrypoint.sh uses Python+requests for Ollama checks, exec at end
→ TD-04: .dockerignore excludes .git, .specs, .skills, tests, chroma_db, output, __pycache__

FAILURE MODES:
→ Missing gcc → pip install fails for C extensions in slim image
→ Wrong PYTHONPATH → ModuleNotFoundError inside container
→ entrypoint.sh not executable → permission denied on Docker run
→ Ollama healthcheck too aggressive → container marked unhealthy before ready
→ NB-06 fix breaks existing tests → run full suite after

VERIFICATION:
→ docker build -t chemtrace:test .  (must succeed)
→ docker run --rm chemtrace:test python -c "from chemtrace.config import Config; print(Config().ollama_model)"
   Expected: llama3.2:3b
→ docker run --rm chemtrace:test python -c "from chemtrace.vector_store import VectorStore; print('OK')"
   Expected: OK (no HF warnings on stderr)
→ PYTHONPATH="C:\\Chemtrace\\src" python -m pytest tests/ -q -k "not integration"
   Expected: 73 passed (NB-06 fix didn't break anything)
→ cat .dockerignore | grep -c "tests"  → 1 (tests excluded from image)
→ grep "TRANSFORMERS_VERBOSITY" src/chemtrace/vector_store.py  → should match

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 1)
→ [ ] Dockerfile builds successfully with `docker build -t chemtrace:test .`
→ [ ] Docker image has working Python imports (config, vector_store, rag_client)
→ [ ] docker-compose.yml defines 2 services (chemtrace + ollama) with health check
→ [ ] entrypoint.sh waits for Ollama, pulls model, execs command
→ [ ] .dockerignore excludes tests, .git, .specs, chroma_db, output
→ [ ] requirements.txt pinned to tested versions (pdfplumber==0.11.9, pandas==3.0.1, etc.)
→ [ ] NB-06 fixed: TRANSFORMERS_VERBOSITY=error + HF_HUB_VERBOSITY=error in vector_store.py
→ [ ] All 73 unit tests still pass after NB-06 fix
→ [ ] scripts/ directory created with entrypoint.sh (chmod +x)

### Post-Task
```bash
git add .
git commit -m "feat: Docker infrastructure + NB-06 HF warning fix (Phase 03, Task 1)"
# /clear in Claude Code for fresh context
```

---

## TASK 2: README + .env.example + LICENSE (2h)

### Goal
Create bilingual README.md (EN primary + DE Quick Start), update .env.example defaults, add MIT LICENSE file.

### Claude Code Prompt (copy-paste ready)

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\\Chemtrace\\src" python ...
PYTHONPATH="C:\\Chemtrace\\src" pytest ...

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/phases/03-docker-deploy/CONTEXT.md (section 3: TD-05, TD-09)
- .specs/REQUIREMENTS.md (section 4.8: REQ-F08 Documentation)
- .specs/ARCHITECTURE.md (section 1: High-Level Architecture diagram, section 5: Configuration)
- .specs/phases/02-rag-client/CONTEXT.md (section 3: TD-02 RAM requirements table)
- .env.example (current state)
- data/emission_factors/factors.json (for emission factors table in README)
- docker-compose.yml (just created in Task 1, for Quick Start commands)
- .skills/PROMPT_CONTRACT.md

GOAL: Create README.md (bilingual EN/DE), update .env.example, add LICENSE.

CONSTRAINTS:
→ Files to CREATE: README.md, LICENSE
→ Files to MODIFY: .env.example (update OLLAMA_MODEL default to llama3.2:3b, add OLLAMA_TIMEOUT=60)
→ Files NOT to touch: src/, tests/, Dockerfile, docker-compose.yml
→ README target: 200-250 lines, NOT longer
→ LICENSE: MIT, copyright "2026 Sebastian Damiani Wolf"

README STRUCTURE (follow this order):
1. Title "ChemTrace OSS" + badges (MIT, Python 3.11, Docker)
2. Tagline EN: "Open-source Scope 1-3 carbon accounting pipeline for German industrial SMEs."
3. Tagline DE: "Open-Source Scope 1-3 Carbon-Accounting-Pipeline fuer deutsche Industrie-KMU."
4. "What is ChemTrace?" section (EN, 2-3 sentences: CSRD problem, what it does, key features)
5. "Quick Start (Docker)" section (EN, step-by-step with commands):
   → git clone, cd, docker compose up -d ollama, wait for healthy,
   → docker compose run --rm chemtrace parse,
   → docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"
6. "Quick Start (Local Development)" section (EN):
   → Prerequisites: Python 3.11+, Ollama installed
   → pip install -r requirements.txt
   → ollama pull llama3.2:3b
   → PYTHONPATH=src python -m chemtrace parse --input-dir data/sample_invoices/
   → PYTHONPATH=src python -m chemtrace ask "..."
7. "Schnellstart (Docker)" section (DE, same commands, German descriptions)
8. "Architecture" section (EN, ASCII diagram from ARCHITECTURE.md section 1)
9. "Configuration" section (EN, table of .env variables with defaults)
10. "Emission Factors" section (EN, table from factors.json with sources)
11. "RAM Requirements" section (EN, table: 8GB/16GB/32GB recommendations)
12. "CLI Commands" section (EN, 4 commands with descriptions)
13. "Contributing" section (EN, 3-4 lines: issues welcome, PRs welcome, code style)
14. "License" section (EN, MIT + link)

IMPORTANT:
→ Do NOT use dashes (-) as bullet points. Use arrows (→) or plain text.
→ ASCII art diagram must render correctly in GitHub markdown (use code block)
→ Quick Start commands must be exact (test them mentally against docker-compose.yml)
→ German section uses "ue" not "ü" in code/filenames (ASCII safe)
→ .env.example: keep all existing variables, update OLLAMA_MODEL default, add OLLAMA_TIMEOUT

FAILURE MODES:
→ README commands don't match actual docker-compose.yml → user can't follow Quick Start
→ .env.example variables don't match Config class → silent config mismatch
→ German text has encoding issues → use ASCII-safe German

VERIFICATION:
→ wc -l README.md → should be 200-280 lines
→ grep "llama3.2:3b" README.md → should appear (RAM table + config)
→ grep "llama3.2:3b" .env.example → should appear as default
→ grep "OLLAMA_TIMEOUT" .env.example → should appear
→ head -1 LICENSE → should contain "MIT License"
→ grep "2026 Sebastian Damiani" LICENSE → should match

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 2)
→ [ ] README.md exists with bilingual content (EN + DE Quick Start)
→ [ ] README.md has Docker Quick Start with exact commands matching docker-compose.yml
→ [ ] README.md has Local Dev Quick Start for non-Docker users
→ [ ] README.md has Architecture diagram, Configuration table, Emission Factors table
→ [ ] README.md has RAM Requirements table (8GB/16GB/32GB)
→ [ ] README.md is 200-280 lines (not a novel)
→ [ ] .env.example has OLLAMA_MODEL=llama3.2:3b as default
→ [ ] .env.example has OLLAMA_TIMEOUT=60
→ [ ] LICENSE file exists (MIT, correct copyright)
→ [ ] No dashes used as bullets in README

### Post-Task
```bash
git add .
git commit -m "docs: bilingual README + .env.example update + MIT LICENSE (Phase 03, Task 2)"
# /clear in Claude Code for fresh context
```

---

## TASK 3: Docker Build Test + Phase Verification + VERIFY.md (2h)

### Goal
Test Docker build, run full phase verification gate, execute CODE_VERIFIER protocol, generate VERIFY.md.

### Claude Code Prompt (copy-paste ready)

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\\Chemtrace\\src" python ...
PYTHONPATH="C:\\Chemtrace\\src" pytest ...

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/phases/03-docker-deploy/CONTEXT.md (all sections)
- .specs/phases/03-docker-deploy/PLAN-03.md (this plan, Task 3 acceptance criteria)
- .specs/REQUIREMENTS.md (section 7: Acceptance Criteria AC-01 through AC-10)
- Dockerfile
- docker-compose.yml
- scripts/entrypoint.sh
- README.md
- .env.example
- .skills/CODE_VERIFIER.md

GOAL: Validate Docker build works. Run full MVP verification. Generate VERIFY.md.

CONSTRAINTS:
→ Files to CREATE: .specs/phases/03-docker-deploy/VERIFY.md
→ Files to MODIFY: Dockerfile, docker-compose.yml, entrypoint.sh (ONLY if bugs found during testing)
→ Files NOT to touch: src/ (unless critical bug), tests/, README.md, LICENSE
→ If Docker build fails: fix the Dockerfile, don't work around it

DOCKER BUILD TEST:
1. Build the image:
   → docker build -t chemtrace:test .
   → If fails: analyze error, fix Dockerfile, rebuild
2. Test imports inside container:
   → docker run --rm chemtrace:test python -c "from chemtrace.config import Config; c = Config(); print(f'model={c.ollama_model}, timeout={c.ollama_timeout}')"
   → Expected: model=llama3.2:3b, timeout=60
3. Test vector_store import (NB-06 verification):
   → docker run --rm chemtrace:test python -c "import os; os.environ.get('TRANSFORMERS_VERBOSITY'); from chemtrace.vector_store import VectorStore; print('OK')" 2>&1
   → Expected: OK with no/minimal stderr warnings
4. Test entrypoint without Ollama (should fail gracefully):
   → docker run --rm --entrypoint python chemtrace:test -m chemtrace status 2>&1
   → Expected: shows usage or ChromaDB status (not an import error)
5. Image size check:
   → docker images chemtrace:test --format "{{.Size}}"
   → Document the size in VERIFY.md

NOTE: Do NOT run docker compose up (Ollama + ChromaDB + app simultaneously requires too much RAM on this machine). Docker compose testing is manual post-session.

FULL MVP VERIFICATION GATE:
Run all checks from REQUIREMENTS.md AC-01 through AC-10:

| # | Check | How to verify | Status |
|---|---|---|---|
| AC-01 | docker compose up starts (structure check) | Verify docker-compose.yml is valid: docker compose config | |
| AC-02 | chemtrace parse produces correct CSV | Already verified (Phase 01). Verify CSV exists: ls output/invoices.csv | |
| AC-03 | Emission calculations correct | Already verified (Phase 01). 62 unit tests cover this. | |
| AC-04 | chemtrace ask returns grounded answer | Already verified (Phase 02). 2 integration tests + 6 manual queries. | |
| AC-05 | Off-topic questions refused | Already verified (Phase 02). Q5+Q6 pass. | |
| AC-06 | No hardcoded secrets | grep -rn "API_KEY\|password\|secret" src/ | |
| AC-07 | README bilingual EN/DE + Quick Start | head -50 README.md | |
| AC-08 | chemtrace export produces valid CSV | Already verified (Phase 02). NB-01 fixed. | |
| AC-09 | No duplicate records on re-parse | Already verified (Phase 01). Upsert logic tested. | |
| AC-10 | git clone to working demo <30 min | Estimate from README Quick Start steps | |

UNIT TEST REGRESSION:
→ PYTHONPATH="C:\\Chemtrace\\src" python -m pytest tests/ -q -k "not integration" → 73 pass

SECURITY AUDIT:
→ grep -rn "API_KEY\|password\|secret" src/ → no matches
→ grep -rn "eval(\|exec(" src/ → no matches
→ grep -rn "subprocess\|os.system" src/ → no matches
→ Verify .dockerignore excludes .env, .git, chroma_db

CODE_VERIFIER FULL PROTOCOL:
Execute all 6 steps from .skills/CODE_VERIFIER.md (end-of-phase, covers all Phase 03 files).

After CODE_VERIFIER, generate .specs/phases/03-docker-deploy/VERIFY.md with:
→ Docker build results (success/fail, image size)
→ Container import tests (all pass/fail)
→ MVP gate results (AC-01 through AC-10)
→ CODE_VERIFIER report (findings table)
→ Known limitations
→ Confidence score
→ Manual testing checklist for Sebas (docker compose up test post-session)
```

### Acceptance Criteria (Task 3)
→ [ ] Docker image builds successfully
→ [ ] Python imports work inside container (config, vector_store, rag_client)
→ [ ] docker compose config validates without errors
→ [ ] All 73 unit tests still pass locally
→ [ ] No secrets in codebase (grep audit)
→ [ ] VERIFY.md generated with full CODE_VERIFIER report
→ [ ] Manual testing checklist for docker compose included in VERIFY.md
→ [ ] Image size documented
→ [ ] Known limitations documented

### Post-Task
```bash
git add .
git commit -m "feat: Docker build verified + Phase 03 VERIFY.md (Phase 03, Task 3)"
git tag v0.3.0-docker-deploy
# Push to GitHub
git push origin main --tags
# /clear in Claude Code
```

---

## PHASE 03 GATE (Definition of Done)

| # | Check | Command | Expected |
|---|---|---|---|
| G-01 | Docker image builds | `docker build -t chemtrace:test .` | Success, image created |
| G-02 | Imports work in container | `docker run --rm chemtrace:test python -c "from chemtrace.config import Config; print('OK')"` | OK |
| G-03 | docker-compose.yml valid | `docker compose config` | No errors |
| G-04 | entrypoint.sh exists and executable | `ls -la scripts/entrypoint.sh` | -rwxr-xr-x |
| G-05 | README bilingual | `grep -c "Schnellstart" README.md` | >= 1 |
| G-06 | .env.example updated | `grep "llama3.2:3b" .env.example` | Match |
| G-07 | LICENSE exists | `head -1 LICENSE` | MIT License |
| G-08 | NB-06 fixed | `grep "TRANSFORMERS_VERBOSITY" src/chemtrace/vector_store.py` | Match |
| G-09 | Unit tests pass | `pytest tests/ -k "not integration"` | 73 pass |
| G-10 | No secrets | `grep -rn "API_KEY\|password\|secret" src/` | No matches |
| G-11 | Code Verifier | Full 6-step protocol | Confidence >= 0.9 |
| G-12 | Image size documented | In VERIFY.md | Size noted |

**Post-gate manual test (Sebas, after closing Cursor):**
```bash
# Close Cursor + Claude Code first (free RAM)
docker compose up -d ollama
# Wait ~30s for healthy
docker compose run --rm chemtrace parse
docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"
docker compose run --rm chemtrace status
docker compose down
```

---

## TIME BUDGET

| Task | Estimated | Buffer |
|---|---|---|
| Task 1: Docker infra + NB-06 | 3h | +30min |
| Task 2: README + .env + LICENSE | 2h | +30min |
| Task 3: Build test + verification | 2h | +30min |
| **Total** | **7h** | **+1.5h** (within 8h budget) |

**80/20 cuts if over budget:**
→ Cut 1: German README section → defer to post-MVP LinkedIn push
→ Cut 2: Docker build test → manual only (skip Claude Code docker commands)
→ Cut 3: VERIFY.md → abbreviated version (gate table + confidence score only)

---

*Phase 03 planning complete. Execute Task 1 → Task 2 → Task 3 sequentially. One Claude Code session per task.*
