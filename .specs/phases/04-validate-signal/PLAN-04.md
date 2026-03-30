# PLAN-04.md — Day 31-60: Validate and Signal
**Phase:** 04-validate-signal
**Duration:** 5 weeks (31 mar → 30 abr 2026)
**Budget:** 8-10h/week, ~23h total planned (~4.6h/week average, S3 heaviest at 7h)
**Gate:** Docker image < 4 GB + SAP CSV connector + 5 outreach messages sent + 1 NRW event identified
**Depends on:** Phase 03 COMPLETE (v0.3.0-docker-deploy, e2e 7/7 PASS, CODE_VERIFIER 0.96)
**SDD Gate:** Specify → Design → Plan (this file) → Execute → Verify

---

## 1. PHASE OBJECTIVE

Optimize the Docker image from 9 GB to ~3-4 GB, improve LLM quality, add SAP CSV connector, begin NRW SME outreach, and establish public visibility (demo GIF, second LinkedIn post, ACHEMA research).

---

## 2. DEPENDENCY CHAIN

```
Docker cleanup nuclear (recover ~30 GB)
    ↓
torch CPU-only swap (modify requirements.txt + Dockerfile)
    ↓
Multi-stage Docker build (modify Dockerfile)
    ↓
phi3:mini test (needs Docker running with new image)
    ↓
Prompting improvements (needs Docker + Ollama, uses winning model)
    ↓
Demo GIF (uses optimized image + winning model + improved prompts)
    ↓
SAP CSV connector (independent of Docker, pure code)
```

---

## 3. WEEKLY EXECUTION PLAN

### WEEK 1 (31 mar → 4 abr): Publication + Cleanup + ACHEMA

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 1.1 | LinkedIn post publishes 1 PM CEST (Tue 31). Respond to comments 30-60 min. | 1h | Non-tech | Comments responded within 60 min |
| 1.2 | Docker cleanup: `docker system prune -a --volumes -f` + `docker builder prune -a -f` + `wsl --shutdown` + compact WSL2 vhdx | 30 min | PowerShell | Disk > 70 GB free |
| 1.3 | ACHEMA Founder Award: research deadline + requirements | 30 min | Browser | Deadline known, requirements documented |
| **Total** | | **2h** | | |

**Post-week 1 state:** Post live, disk clean (~76 GB free), ACHEMA info documented. GIF deferred to post-S3 (uses optimized image + winning LLM + improved prompts).

### WEEK 2 (7-11 abr): Docker Image Optimization

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 2.1 | CONTEXT/PLAN spec for torch CPU-only + multi-stage (claude.ai Opus) | 1h | Planning | Spec reviewed |
| 2.2 | Execute: torch CPU-only swap in requirements.txt (replace `torch` with `torch-cpu` or `--index-url` CPU wheel) | 1.5h | Claude Code | `pip install` succeeds, no CUDA deps |
| 2.3 | Execute: multi-stage Dockerfile (build stage + slim runtime stage) | 30 min | Claude Code | Dockerfile builds without error |
| 2.4 | Docker rebuild + e2e test (parse + ask + status with new image) | 1h | Docker | 7/7 PASS, 5/5 emissions exact |
| 2.5 | VERIFY: image size + commit + tag v0.4.0-optimized + push | 15 min | Git Bash | `docker images` < 4 GB |
| **Total** | | **4.75h** | | |

**Post-week 2 state:** Docker image 3-4 GB (was 9.14 GB). Tag v0.4.0-optimized pushed. E2e verified.

**Prompt for Claude Code (Task 2.2-2.3):**
```
Before touching any file, reason step by step about:
1. What the root cause is (torch pulling CUDA deps)
2. What the minimal change solves it (CPU-only wheel index)
3. What could break downstream (sentence-transformers compatibility)
Then apply the fix.

Read these files first:
→ requirements.txt (current pinned versions)
→ Dockerfile (current single-stage)
→ .specs/ARCHITECTURE.md (OQ-03 optimization note)

GOAL: Reduce Docker image from 9 GB to ~3-4 GB.

PRE-CHECK (before any file changes):
→ Run: pip install sentence-transformers --dry-run 2>&1 | grep torch
→ Note the exact torch version required (e.g., torch>=2.x.y)
→ Verify CPU wheel exists: check https://download.pytorch.org/whl/cpu/ for that version
→ If CPU wheel does NOT exist for required version → STOP and report. Do not proceed.

TASK A: torch CPU-only swap
→ In requirements.txt, replace torch dependency with CPU-only variant
→ Option 1: Add --extra-index-url https://download.pytorch.org/whl/cpu to pip install
→ Option 2: Pin torch+cpu explicitly
→ Verify sentence-transformers still imports correctly
→ Run: PYTHONPATH=src python -c "from chemtrace.vector_store import VectorStore; print('OK')"

TASK B: Multi-stage Dockerfile
→ Stage 1 (build): python:3.11-slim, install gcc + deps, pip install
→ Stage 2 (runtime): python:3.11-slim, copy installed packages + app code
→ Do NOT copy gcc, build-essential, or pip cache to runtime stage
→ Keep PYTHONPATH=/app/src and ENTRYPOINT as-is

VERIFICATION:
→ docker build --no-cache -t chemtrace:v0.4.0 . (MUST use --no-cache on first build after torch swap to avoid stale layers)
→ docker images chemtrace:v0.4.0 → size should be < 4 GB
→ docker run --rm chemtrace:v0.4.0 python -c "from chemtrace.config import Config; print(Config())"
→ docker run --rm chemtrace:v0.4.0 python -c "from chemtrace.vector_store import VectorStore; print('OK')"

FAILURE MODES:
→ sentence-transformers incompatible with torch CPU-only → test import explicitly
→ Multi-stage COPY misses site-packages → verify with import test
→ chromadb needs specific torch version → check chromadb[torch] compat

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### WEEK 3 (14-18 abr): LLM Improvements + Outreach Prep

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 3.1 | Test phi3:mini: `ollama pull phi3:mini`, run same 5 queries from VERIFY.md, compare quality vs llama3.2:3b | 1h | Docker | Side-by-side comparison documented |
| 3.2 | Prompting improvements: adjust system prompt for better retrieval grounding, test with both models | 1h | Claude Code + Docker | At least 1 measurable improvement |
| 3.3 | LLM decision: phi3:mini or llama3.2:3b as default. Document rationale. Commit if config changes. | 30 min | Decision | Decision in .memory/decisions.md |
| 3.4 | NRW company research: identify 10 targets (IHK Essen, LinkedIn, Wer liefert was, chemical industry directories) | 1.5h | Browser | 10 companies with contact info in spreadsheet |
| 3.5 | Draft outreach template: email + LinkedIn message variants (must include concrete CTA, see below) | 1h | claude.ai | 2-3 message variants ready to send |
| 3.6 | SAP CSV format research: google "SAP ECC energy consumption CSV export" + "S/4HANA Energiedatenmanagement export format." Document: typical headers, delimiters, encoding, gotchas. Ask for real sample during outreach (natural conversation starter). | 15 min | Browser | SAP CSV format documented (headers + sample structure) |
| 3.7 | Create outreach tracker (simple CSV/spreadsheet): columns = company, contact_name, contact_email, channel (email/LinkedIn), date_sent, status (pending/sent/replied/meeting), next_action, notes. Pre-fill with 10 companies from Task 3.4. | 15 min | Spreadsheet | Tracker file exists with 10 rows |
| 3.8 | Demo GIF: install ScreenToGif, record parse → ask → status with optimized image + winning model, edit (remove wait frames), export < 5 MB. See GIF_RECORDING_GUIDE.md. | 1h | Docker | GIF file < 5 MB, shows full optimized pipeline |
| 3.9 | Add GIF to README.md + commit + push | 30 min | Git Bash | GIF renders in GitHub README |
| **Total** | | **7h** | | |

**Post-week 3 state:** LLM decision made. 10 target companies identified. Outreach templates ready (with CTA). SAP CSV format documented. Outreach tracker populated. Demo GIF in README (recorded with optimized image + winning LLM).

**Outreach CTA (decide before drafting templates):**
Choose ONE primary CTA per message variant. Candidates ranked by conversion likelihood:
→ (a) "Free 30 min walkthrough: I'll show you your CSRD Scope 1-2 gap using your own energy invoices (anonymized)."
→ (b) "Free 2-week pilot: clone the repo, I help you set it up with your data."
→ (c) "Quick 15 min demo call: I'll walk you through how ChemTrace handles German energy invoices."
Decision: pick (a) or (c) as primary. (b) = escalation offer if (a)/(c) generates interest.

**Queries for phi3:mini comparison (from VERIFY.md e2e):**
```
1. "What was electricity consumption in Jan 2024?"
   Expected: 478,800 kWh, source: Invoice_Electricity_Jan2024_RuhrChem.pdf
2. "How much diesel was used in Feb 2024?"
   Expected: 8,500 litres, source: Invoice_Diesel_Feb2024_RuhrChem.pdf
3. "What were total emissions from natural gas?"
   Expected: 62.782 tCO2e, source: Invoice_NaturalGas_Jan2024_RuhrChem.pdf
4. "Compare electricity consumption across all months"
   Expected: Jan 478,800 / Feb 415,300 / Mar 453,100 kWh with sources
5. "What is the weather in Berlin?" (off-topic guardrail test)
   Expected: Polite refusal
```

**Evaluation rubric (4 binary criteria, model wins 3/4 → chosen):**
| Criterion | How to judge | PASS/FAIL |
|---|---|---|
| Source citation | Response mentions correct blob_name for each fact | Binary |
| Numeric accuracy | Numbers match expected values exactly | Binary |
| Guardrail refusal | Off-topic query 5 gets polite refusal, not hallucinated answer | Binary |
| Latency | Response completes in < 15 seconds on CPU | Binary |

→ Record results in table for both models. Model with ≥3/4 PASS wins.
→ If tied: prefer llama3.2:3b (already proven, zero migration cost).

### WEEK 4 (21-25 abr): SAP Connector + Outreach Execution

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 4.1 | PLAN-05.md: spec SAP CSV connector using format research from Task 3.6 (claude.ai Opus) | 1h | Planning | Spec approved, format validated |
| 4.2 | Execute: SAP CSV parser module + integration with existing ETL | 3h | Claude Code | Tests pass, sample CSV parsed correctly |
| 4.3 | VERIFY + commit + tag v0.5.0-sap-connector + push | 30 min | Claude Code | CODE_VERIFIER > 0.90 |
| 4.4 | Send 5 outreach messages (email/LinkedIn to identified targets). Update tracker from Task 3.7 with date_sent + status. | 1h | Browser | 5 messages sent, tracker updated |
| 4.5 | NRW tech event: find relevant meetup/conference, register | 30 min | Browser | Event identified, registered |
| **Total** | | **6h** | | |

**Post-week 4 state:** SAP CSV connector working. Tag v0.5.0 pushed. 5 outreach messages sent. Event registered.

**SAP CSV connector scope (minimal):**
→ Parse standard SAP energy consumption export (CSV format)
→ Map SAP fields to ChemTrace schema (site, period, energy_type, amount, unit)
→ Integrate with existing ETL pipeline (same emission factor calculation)
→ If no real SAP sample available: generate synthetic CSV based on SAP ECC/S4HANA standard export format

### WEEK 5 (28-30 abr): Second Post + Buffer

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 5.1 | Second LinkedIn post: "From 9 GB to 3 GB" optimization story + GIF | 1h | Non-tech | Post published |
| 5.2 | Send remaining 5 outreach messages. Update tracker. | 1h | Browser | 10 total messages sent, tracker complete |
| 5.3 | ACHEMA Founder Award application draft (if deadline applies) | 1h | claude.ai | Draft ready for review |
| **Total** | | **3h** | | |

---

## 4. TAGS PLANNED

| Tag | Content | Week |
|---|---|---|
| v0.4.0-optimized | Docker image < 4 GB (torch CPU-only + multi-stage) | Week 2 |
| v0.5.0-sap-connector | SAP CSV parser integrated | Week 4 |

---

## 5. RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| torch CPU-only breaks sentence-transformers | Low | High | Test import before rebuilding. Fallback: keep current image, defer optimization. |
| phi3:mini doesn't fit in 8 GB RAM | Medium | Low | If OOM, decision is made: stay with llama3.2:3b. Zero time wasted. |
| No real SAP CSV sample available | Medium | Medium | Generate synthetic based on SAP standard export schema. Validate format with outreach contacts. |
| 0 outreach responses in April | High | Medium | Expected. Outreach is pipeline, not conversion. NRW tech event is backup channel. |
| DGD heavy week conflicts | Medium | Medium | Drop non-tech track first. Code has priority (builds on itself). Outreach can shift. |
| ACHEMA deadline already passed | Low | Low | Research in week 1 resolves this. If passed, pivot to other awards/events. |

---

## 6. METRICS (Day 60 targets from blueprint)

| Metric | Target | Realistic assessment |
|---|---|---|
| GitHub stars | 150+ | Aggressive. 20-50 more realistic without viral post. |
| Pilot user | 1 real | Possible if outreach generates 1-2 conversations. |
| NRW tech event | 1 presented or attended | Achievable. IHK/Meetup events are frequent. |
| Docker image size | < 4 GB | High confidence (torch CPU-only is proven approach). |
| SAP connector | Working + tested | High confidence (CSV parsing is straightforward). |

---

## 7. DECISION RULES

→ If DGD is heavy any week → drop non-tech tasks first, reschedule to following week
→ If torch CPU-only breaks compatibility → abort optimization, document, defer to ONNX (Day 61-90)
→ If phi3:mini OOMs on 8 GB → stay with llama3.2:3b, decision done in 5 minutes
→ If no SAP sample by week 4 → generate synthetic, validate format post-outreach
→ If ACHEMA deadline has passed → pivot to Chemspec Europe, DECHEMA events, or IHK NRW awards
→ 80/20 STOP applies to all tasks: if overthinking, ship the 80% version

---

*Plan generated: 2026-03-30 | Audited: 2026-03-30 (Level 3, fixes H1-H6 applied) | Budget: ~23h over 5 weeks | Confidence: 0.93*
