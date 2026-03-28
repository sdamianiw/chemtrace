# CONTEXT.md — Phase 03: Docker Deploy
**Phase:** 03-docker-deploy
**Duration:** Week 4 (8h max)
**Gate:** `docker compose up -d` starts full stack → `docker compose run --rm chemtrace parse` + `ask` work correctly
**Depends on:** Phase 02 COMPLETE ✅ (75 tests, v0.2.0-rag-client, CODE_VERIFIER 0.97)
**SDD Gate:** 3 of 5 (Specify ✅ → Design ✅ → Plan → Execute → Verify)

---

## 1. PHASE OBJECTIVE

Containerize the full ChemTrace pipeline: Dockerfile + docker-compose.yml (app + Ollama) + entrypoint script + bilingual README + LICENSE. A new user goes from `git clone` to working demo in under 30 minutes (AC-10).

---

## 2. WHAT EXISTS (from Phase 01 + 02)

### Code complete:
→ `src/chemtrace/` → 9 modules: config, pdf_parser, parser_patterns, etl, vector_store, rag_client, prompts, cli, utils
→ `tests/` → 73 unit + 2 integration tests, all pass
→ `data/sample_invoices/` → 6 PDFs (5 invoices + 1 ESG report)
→ `data/emission_factors/factors.json` → emission factors with sources
→ `.env.example` → exists but OLLAMA_MODEL still references llama3.1:8b in ARCHITECTURE.md spec (actual config.py default is llama3.2:3b)
→ `pyproject.toml` → exists (pytest config + optional dev deps)
→ `requirements.txt` → exists (created in Phase 01 Task 1)

### Files to CREATE in this phase:
→ `Dockerfile`
→ `docker-compose.yml`
→ `scripts/entrypoint.sh`
→ `README.md` (bilingual EN/DE)
→ `LICENSE` (MIT)
→ `.specs/phases/03-docker-deploy/CONTEXT.md` (this file)
→ `.specs/phases/03-docker-deploy/PLAN-03.md`
→ `.specs/phases/03-docker-deploy/VERIFY.md`
→ `.dockerignore`

### Files to MODIFY:
→ `.env.example` → update OLLAMA_MODEL default to llama3.2:3b, add OLLAMA_TIMEOUT=60
→ `src/chemtrace/vector_store.py` → NB-06 fix (TRANSFORMERS_VERBOSITY + HF_HUB_VERBOSITY)
→ `requirements.txt` → pin to actual tested versions

---

## 3. TECHNICAL DECISIONS (this phase only)

### TD-01: Dockerfile strategy — python:3.11-slim + requirements.txt

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps for pdfplumber (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY data/ data/
COPY .env.example .env.example
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/entrypoint.sh"]
```

**Rationale:**
→ python:3.11-slim over alpine: sentence-transformers + torch have complex C dependencies that fail on alpine.
→ PYTHONPATH instead of pip install: consistent with dev pattern, avoids pyproject.toml build config complexity.
→ gcc needed for some transitive C extension builds. Removed after install via multi-stage if image size becomes an issue (post-MVP).
→ No CMD default: entrypoint.sh handles command routing.
→ Expected image size: ~2.5 GB (sentence-transformers pulls torch). Documented as known trade-off (ARCHITECTURE.md OQ-03).

**IMPORTANT: Do NOT use multi-stage build for MVP.** The app is a CLI tool, not a web server. No nginx needed. One stage is simpler and debuggable.

### TD-02: docker-compose.yml — 2 services (app + Ollama)

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_models:/root/.ollama
    ports:
      - "11434:11434"   # Expose for local dev convenience
    healthcheck:
      test: ["CMD-SHELL", "ollama list || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 30s

  chemtrace:
    build: .
    volumes:
      - ./data/sample_invoices:/app/data/sample_invoices:ro
      - ./output:/app/output
      - chroma_data:/app/chroma_db
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2:3b}

volumes:
  chroma_data:
  ollama_models:
```

**Key design decisions:**
→ Ollama health check uses `ollama list` (builtin, no curl dependency needed).
→ `start_period: 30s` gives Ollama time to initialize on first run.
→ chemtrace depends_on with `condition: service_healthy` → waits for Ollama to be ready.
→ ChromaDB data persists in named volume (survives container restarts).
→ Ollama models persist in named volume (avoid re-downloading 2GB model).
→ Input PDFs mounted read-only. Output writable.
→ No .env file mounted → environment variables set in compose. User overrides via `.env` file that docker compose reads automatically.
→ Ollama port 11434 exposed for local dev convenience (can also use `ollama` CLI on host).

**Usage pattern (CLI tool, not long-running service):**
```bash
docker compose up -d ollama          # Start Ollama in background
docker compose run --rm chemtrace parse   # Run parse
docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"
docker compose down                  # Stop everything
```

→ `docker compose run --rm` creates a temporary container, runs the command, removes container.
→ The chemtrace service is NOT meant to run as a daemon. It's a CLI tool.

### TD-03: entrypoint.sh — Python-based (no curl dependency)

```bash
#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-llama3.2:3b}"

# Wait for Ollama to be ready (backup check, compose healthcheck should handle this)
echo "Checking Ollama at $OLLAMA_URL..."
python -c "
import requests, time, sys
url = '$OLLAMA_URL'
for i in range(30):
    try:
        r = requests.get(f'{url}/api/tags', timeout=3)
        if r.status_code == 200:
            print('Ollama is ready.')
            sys.exit(0)
    except Exception:
        pass
    time.sleep(2)
print('ERROR: Ollama not reachable after 60s.', file=sys.stderr)
sys.exit(1)
"

# Pull model if not already available
python -c "
import requests, json, sys
url = '$OLLAMA_URL'
model = '$MODEL'
tags = requests.get(f'{url}/api/tags').json()
names = [m['name'] for m in tags.get('models', [])]
if model in names:
    print(f'Model {model} already available.')
else:
    print(f'Pulling {model}... (this may take several minutes on first run)')
    r = requests.post(f'{url}/api/pull', json={'name': model, 'stream': False}, timeout=600)
    if r.status_code == 200:
        print(f'Model {model} ready.')
    else:
        print(f'ERROR: Failed to pull {model}: {r.text}', file=sys.stderr)
        sys.exit(1)
"

# Execute the chemtrace command
exec python -m chemtrace "$@"
```

**Rationale:**
→ Uses Python + requests instead of curl (requests is already installed, curl may not exist in python:3.11-slim).
→ 30 retries × 2s = 60s max wait for Ollama. Generous enough for cold start.
→ Model pull with 600s timeout (10 min). First pull of llama3.2:3b is ~2GB download.
→ `exec` replaces shell with Python process → clean signal handling (Ctrl+C works).
→ If no arguments passed: `python -m chemtrace` shows argparse help.

### TD-04: .dockerignore

```
.git
.specs
.skills
.memory
.claude
.env
.venv
venv
__pycache__
*.pyc
chroma_db
output
tests
scripts/generate_pdfs.py
_archive
*.md
!README.md
.pytest_cache
```

→ Reduces build context significantly.
→ Tests NOT included in image (run locally, not in container).
→ README.md included (for reference inside container if needed).

### TD-05: README.md structure — bilingual EN/DE

Structure:
```
# ChemTrace OSS
[badges: MIT license, Python 3.11, Docker]
[1-line tagline EN]
[1-line tagline DE]

## What is ChemTrace? / Was ist ChemTrace?
[2 paragraphs EN, 2 paragraphs DE]

## Quick Start (Docker) — 5 minutes
[Step-by-step EN with commands]

## Quick Start (Local Development)
[Step-by-step EN with commands]

## Schnellstart (Docker) — 5 Minuten
[Same Docker steps in German]

## Architecture
[ASCII diagram from ARCHITECTURE.md]

## Configuration
[.env variables table]

## Emission Factors
[Table with sources]

## RAM Requirements
[Table from CONTEXT_Phase02.md TD-02]

## Contributing
[Brief guidelines]

## License
MIT
```

→ English first (primary audience: GitHub/international OSS).
→ German Quick Start duplicated (primary user audience: German SMEs).
→ Technical sections in English only (developers read English).
→ Total: ~200-250 lines. Not a novel.

### TD-06: NB-06 fix (HF Hub warning suppression)

Add to `vector_store.py` env block (lines 3-7):
```python
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_VERBOSITY"] = "error"
```

→ Suppresses the "unauthenticated requests" nag and BertModel LOAD REPORT on stderr.
→ NB-05 already set HF_HUB_DISABLE_TELEMETRY and TOKENIZERS_PARALLELISM.
→ 2 lines added. Zero functional impact.

### TD-07: requirements.txt — pin to tested versions

```
# Core
pdfplumber==0.11.9
pandas==3.0.1
python-dotenv==1.2.2

# Vector store + embeddings
chromadb>=1.0.0
sentence-transformers==5.3.0

# LLM client (pure HTTP)
requests>=2.31.0

# Testing (not needed in Docker, but pin for dev)
pytest>=9.0.0
```

→ Pin major versions where tested. Use >= for chromadb (API stable from 1.0.0+).
→ pytest not installed in Docker image (not in COPY, tests excluded by .dockerignore). But kept in requirements.txt for local dev.

### TD-08: Docker testing strategy

**In Claude Code (automated):**
→ `docker build -t chemtrace:test .` → validates Dockerfile, pip install, COPY steps
→ `docker run --rm chemtrace:test python -c "from chemtrace.config import Config; print(Config())"` → validates imports work inside container
→ Cannot test compose up (needs Ollama container + 8GB RAM constraint)

**Manual by Sebas (post-session):**
→ Close Cursor + Claude Code (free RAM)
→ `docker compose up -d ollama` → wait for healthy
→ `docker compose run --rm chemtrace parse` → verify 5 invoices parsed
→ `docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"` → verify grounded answer
→ `docker compose run --rm chemtrace status` → verify 5 documents
→ `docker compose down` → clean shutdown

### TD-09: LICENSE — MIT

Standard MIT license with copyright: `Copyright (c) 2026 Sebastian Damiani Wolf`

---

## 4. RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| sentence-transformers + torch makes image >3GB | High | Medium | Accept for MVP. Document. OQ-03 (ONNX migration) is post-MVP. |
| gcc not sufficient for all pip dependencies in slim | Low | High | Add libffi-dev, libssl-dev if needed. Test in docker build. |
| Ollama healthcheck fails in compose | Low | Medium | Fallback to entrypoint.sh retry loop (belt + suspenders). |
| Docker build timeout on slow network (torch download) | Medium | Low | Document: first build takes 5-10 min. Subsequent builds cached. |
| RAM pressure running compose on 8GB machine | High | Medium | Document: minimum 8GB, recommended 16GB for Docker path. Local dev path (no Docker) for 8GB machines. |
| Docker Desktop not running | Low | Low | Clear error message in README Quick Start. |

---

## 5. ARCHITECTURE DECISION RECORD

| # | Decision | Rationale | Date |
|---|---|---|---|
| D-011 | python:3.11-slim over alpine | torch/sentence-transformers have complex C deps that fail on alpine musl. | 2026-03-28 |
| D-012 | PYTHONPATH in Docker (not pip install .) | Consistent with dev pattern. Avoids pyproject.toml build config. | 2026-03-28 |
| D-013 | docker compose run --rm pattern (not daemon) | ChemTrace is a CLI tool, not a web server. No need for permanent container. | 2026-03-28 |
| D-014 | Python-based entrypoint (not curl) | curl not available in python:3.11-slim. requests already installed. | 2026-03-28 |
| D-015 | Ollama port 11434 exposed to host | Convenience for local dev. User can also use host ollama CLI. | 2026-03-28 |
| D-016 | README bilingual EN primary + DE Quick Start | GitHub audience is international. German SMEs need Quick Start in DE. | 2026-03-28 |
| D-017 | Accept ~2.5GB image size for MVP | ONNX migration (OQ-03) deferred. Functional correctness over image size. | 2026-03-28 |

---

*Phase 03 context complete. See PLAN-03.md for execution tasks.*
