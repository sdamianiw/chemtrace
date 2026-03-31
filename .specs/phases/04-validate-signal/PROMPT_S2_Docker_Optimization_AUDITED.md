# CLAUDE CODE PROMPT — S2: Docker Image Optimization
# Phase 04, Tasks 2.2 + 2.3
# Copy-paste this ENTIRE prompt into Claude Code (Cursor terminal T2)
# Date: 2026-03-31 | AUDITED: Level 3, fixes H1+H6 applied
# Pre-checks PASSED: torch 2.11.0+cpu confirmed available

Before touching any file, reason step by step about:
1. What the root cause is (torch 2.11.0 pulling cuda-toolkit 13.0.2 + nvidia-cudnn + triton → 9.14 GB image)
2. What the minimal change solves it (CPU-only wheel index + explicit pin → torch 2.11.0+cpu, ~200-300 MB instead of ~4.5 GB)
3. What could break downstream (sentence-transformers 5.3.0 compatibility, chromadb imports, --prefix=/install path alignment)
Then apply the fix.

## FILES TO READ FIRST (mandatory pre-flight)

→ requirements.txt (current: sentence-transformers==5.3.0, chromadb>=1.0.0)
→ Dockerfile (current: single-stage python:3.11-slim, gcc, no --extra-index-url)
→ docker-compose.yml (verify volume mounts and service structure, do NOT modify)
→ scripts/entrypoint.sh (verify ENTRYPOINT uses exec "$@", do NOT modify)
→ src/chemtrace/config.py (verify PYTHONPATH expectations, do NOT modify)
→ .dockerignore (already exists with proper exclusions, do NOT recreate)

## CONFIRMED VERSIONS (from pre-check gate, do NOT change these)

→ Python: 3.11 (base image python:3.11-slim)
→ sentence-transformers: 5.3.0 (pinned in requirements.txt)
→ torch required: >=1.11.0 (pulled by sentence-transformers)
→ torch resolved: 2.11.0 (latest, confirmed via --dry-run)
→ torch CPU wheel: 2.11.0+cpu (confirmed available at https://download.pytorch.org/whl/cpu/)
→ torchvision: NOT required (not a dependency of sentence-transformers 5.3.0)
→ torchaudio: NOT required

## GOAL

Reduce Docker image from 9.14 GB to ~3-4 GB via two changes:
A) torch CPU-only wheel installation (eliminates CUDA runtime ~4.5 GB)
B) Multi-stage Dockerfile (eliminates gcc, build cache, pip artifacts)

## TASK A: Modify Dockerfile — torch CPU-only + multi-stage

Replace the ENTIRE Dockerfile with this structure. Do NOT modify requirements.txt (the CPU constraint belongs in Docker, not in requirements.txt — this is architectural decision D-018).

```dockerfile
# === Stage 1: Build ===
FROM python:3.11-slim AS builder
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies with CPU-only torch
# CRITICAL: torch==2.11.0+cpu pinned explicitly to prevent pip resolving CUDA variant from PyPI
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch==2.11.0+cpu \
    -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.11-slim
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code and data
COPY src/ src/
COPY data/ data/
COPY .env.example .env.example
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "chemtrace", "status"]
```

CRITICAL CONSTRAINTS for the Dockerfile:
→ Both stages MUST use python:3.11-slim (not python:3-slim, not python:slim, not alpine). Identical base image ensures site-packages paths match.
→ torch==2.11.0+cpu MUST be pinned explicitly in the pip install line (not just --extra-index-url). This prevents pip from resolving the CUDA variant from PyPI.
→ --prefix=/install in build stage → COPY --from=builder /install /usr/local in runtime stage. This is the cleanest pattern for multi-stage Python.
→ --extra-index-url goes in the pip install command, NOT in requirements.txt
→ --no-cache-dir is mandatory (no pip cache in build stage)
→ gcc is ONLY in build stage. NOT in runtime stage.
→ CMD line is NEW (was missing in Phase 03 Dockerfile). It provides a default command. Verified: entrypoint.sh uses `exec python -m chemtrace "$@"` which correctly passes CMD args.
→ Do NOT modify docker-compose.yml
→ Do NOT modify scripts/entrypoint.sh
→ Do NOT modify requirements.txt
→ Do NOT modify any source code in src/

## TASK B: Verify .dockerignore is adequate (DO NOT recreate)

.dockerignore ALREADY EXISTS with proper exclusions. Read it and verify it includes at minimum:
→ __pycache__/
→ *.pyc
→ .git
→ .env
→ chroma_db
→ output
→ .specs
→ .memory
→ tests
→ .pytest_cache

If ALL of the above are present → do NOT modify .dockerignore. It already has refined patterns (e.g., `*.md` with `!README.md` negation, `scripts/generate_pdfs.py` specific exclusion).

Only ADD missing entries if any critical exclusion is absent. Do NOT recreate from scratch. Do NOT remove existing entries.

## WHAT NOT TO DO

→ Do NOT add torch or torch+cpu to requirements.txt
→ Do NOT remove any existing dependency from requirements.txt
→ Do NOT change pinned versions in requirements.txt
→ Do NOT modify docker-compose.yml
→ Do NOT modify any Python source code
→ Do NOT modify scripts/entrypoint.sh
→ Do NOT use alpine base image (torch fails on musl libc)
→ Do NOT add --extra-index-url to requirements.txt (it goes in Dockerfile only)
→ Do NOT recreate .dockerignore from scratch (it already exists with correct patterns)

## VERIFICATION (run these after modifying Dockerfile)

Step 1: Show the diff
→ git diff Dockerfile
→ git diff .dockerignore (only if modified)

Step 2: Syntax verification
→ Read the new Dockerfile line by line and confirm no syntax errors
→ Confirm both FROM lines use python:3.11-slim
→ Confirm --prefix=/install and COPY --from=builder /install /usr/local are paired
→ Confirm --extra-index-url is in the pip install line
→ Confirm torch==2.11.0+cpu is explicitly pinned in the pip install line

DO NOT run docker build (we do that manually in PASO 3 with --no-cache after closing Cursor to free RAM).

## FAILURE MODES TO CHECK

→ If --prefix=/install puts packages in unexpected path → import tests will catch this in PASO 3
→ If .dockerignore accidentally excludes needed files (data/, src/, scripts/) → verify COPY commands still work
→ If CMD line conflicts with ENTRYPOINT → VERIFIED: entrypoint.sh uses exec "$@", CMD args pass through correctly
→ If pip resolves CUDA torch despite --extra-index-url → MITIGATED: torch==2.11.0+cpu explicit pin forces CPU variant

## DEFINITION OF DONE

→ [ ] Dockerfile replaced with multi-stage (2 FROM statements)
→ [ ] --extra-index-url https://download.pytorch.org/whl/cpu in pip install line
→ [ ] torch==2.11.0+cpu explicitly pinned in pip install line
→ [ ] gcc ONLY in builder stage
→ [ ] --prefix=/install + COPY --from=builder /install /usr/local
→ [ ] .dockerignore verified adequate (not recreated)
→ [ ] git diff shows ONLY Dockerfile changes (and .dockerignore ONLY if entries were added)
→ [ ] Zero changes to requirements.txt, docker-compose.yml, src/, scripts/
→ [ ] No new dependencies added
