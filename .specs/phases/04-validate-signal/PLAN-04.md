# PLAN-04.md — Day 31-60: Validate and Signal
**Phase:** 04-validate-signal
**Duration:** 5 weeks (31 mar → 30 abr 2026)
**Budget:** 8-10h/week, ~23h total planned (~4.6h/week average, S3 heaviest at 7h)
**Gate:** Docker image < 4 GB + SAP CSV connector + 5 outreach messages sent + Chemspec Europe registered
**Depends on:** Phase 03 COMPLETE (v0.3.0-docker-deploy, e2e 7/7 PASS, CODE_VERIFIER 0.96)
**SDD Gate:** Specify → Design → Plan (this file) → Execute → Verify

---

## 1. PHASE OBJECTIVE

Optimize the Docker image from 9 GB to ~3-4 GB, improve LLM quality, add SAP CSV connector, begin NRW SME outreach, and establish public visibility (demo GIF, second LinkedIn post, Chemspec Europe attendance).

---

## 2. DEPENDENCY CHAIN

```
Docker cleanup nuclear (recover ~30 GB) ← DONE (s6, 84.1 GB free)
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

### WEEK 1 (31 mar → 4 abr): Publication + ACHEMA Research ✅ COMPLETED

| # | Task | Hours | Type | Status |
|---|---|---|---|---|
| 1.1 | LinkedIn post publishes 1:30 PM CEST (Tue 31). Respond to comments 30→60 min. | 1h | Non-tech | ✅ Scheduled |
| 1.2 | Docker cleanup nuclear | 0h | PowerShell | ✅ DONE in s6 (84.1 GB free) |
| 1.3 | ACHEMA Start-up Award 2027: deep research + strategic dossier | 1h | claude.ai | ✅ DONE. Full dossier generated. |
| **Total** | | **2h** | | |

**Post-week 1 state:** Post live, disk clean (84.1 GB free), ACHEMA dossier complete. GIF deferred to S3. Cleanup ahead of schedule.

**ACHEMA Research Key Findings (from dossier):**
→ Concept deadline: 31 August 2026. Business Plan deadline: 30 November 2026.
→ No early-bird scoring bonus. BUT concept phase unlocks 3 months of mentoring + feedback.
→ Solo founder + pre-founding + no registered company = ALL eligible.
→ Carbon Minds (2022 finalista) = direct carbon accounting precedent → made top 10.
→ Zero solo founders among historical finalists → advisory board member needed (Day 61-90).
→ Mentor + investor access (HTGF + BA FrankfurtRheinMain) independent of competition result.
→ Chemspec Europe 2026 Cologne (6-7 May) identified as optimal NRW event replacement.
→ Science4Life (deadline 13 Apr) → SKIP this cycle, scope creep risk. Note for Oct 2026 cycle.
→ DNP Products 2027 (deadline 7 Jun) → evaluate at start of Day 61-90.
→ Decisions: D-024 through D-027 registered. Learnings: L-034 through L-037 registered.

### WEEK 2 (7-11 abr): Docker Image Optimization

| # | Task | Hours | Type | Gate |
|---|---|---|---|---|
| 2.0 | Email DECHEMA: Idea phase confidential assessment request (5 min, zero cost) | 0.1h | Email | Email sent |
| 2.1 | CONTEXT/PLAN spec for torch CPU-only + multi-stage (claude.ai Opus) | 1h | Planning | Spec reviewed |
| 2.2 | Execute: torch CPU-only swap in requirements.txt (replace `torch` with `torch-cpu` or `--index-url` CPU wheel) | 1.5h | Claude Code | `pip install` succeeds, no CUDA deps |
| 2.3 | Execute: multi-stage Dockerfile (build stage + slim runtime stage) | 30 min | Claude Code | Dockerfile builds without error |
| 2.4 | Docker rebuild + e2e test (parse + ask + status with new image) | 1h | Docker | 7/7 PASS, 5/5 emissions exact |
| 2.5 | VERIFY: image size + commit + tag v0.4.0-optimized + push | 15 min | Git Bash | `docker images` < 4 GB |
| **Total** | | **4.85h** | | |

**Post-week 2 state:** Docker image 3-4 GB (was 9.14 GB). Tag v0.4.0-optimized pushed. E2e verified. DECHEMA contacted.

**⚡ EASTER WEEK OPPORTUNITY:** DGD likely quiet (many colleagues on holiday). If bandwidth allows, pull Task 3.1 (phi3:mini test) into S2 to get ahead of schedule. Only if Docker optimization completes cleanly by Wednesday.

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

### WEEK 3 (14-18 abr): LLM Improvements + Outreach Prep + GIF

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
| 4.5 | Register for Chemspec Europe 2026 Cologne (6→7 May) as visitor. Confirm startup sessions in programme. | 15 min | Browser | Registration confirmed |
| **Total** | | **5.75h** | | |

**Post-week 4 state:** SAP CSV connector working. Tag v0.5.0 pushed. 5 outreach messages sent. Chemspec Europe registered.

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
| 5.3 | Chemspec Europe prep: prepare 30-second elevator pitch + business cards/QR code to GitHub repo | 30 min | Prep | Pitch rehearsed, QR code ready |
| **Total** | | **2.5h** | | |

**Post-week 5 state:** Second post live. 10 outreach messages sent. Chemspec Europe prep done. Ready for Day 61→90.

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
| 0 outreach responses in April | High | Medium | Expected. Outreach is pipeline, not conversion. Chemspec Europe is backup channel. |
| DGD heavy week conflicts | Medium | Medium | Drop non-tech track first. Code has priority (builds on itself). Outreach can shift. |
| Chemspec Europe 2026 programme lacks startup sessions | Low | Low | Attend anyway for networking. Cologne is 45 min from Ratingen → minimal time investment. |

---

## 6. METRICS (Day 60 targets from blueprint)

| Metric | Target | Realistic assessment |
|---|---|---|
| GitHub stars | 150+ | Aggressive. 20-50 more realistic without viral post. |
| Pilot user | 1 real | Possible if outreach generates 1-2 conversations. |
| NRW tech event | 1 attended (Chemspec Europe Cologne) | High confidence. Registration only. |
| Docker image size | < 4 GB | High confidence (torch CPU-only is proven approach). |
| SAP connector | Working + tested | High confidence (CSV parsing is straightforward). |

---

## 7. DECISION RULES

→ If DGD is heavy any week → drop non-tech tasks first, reschedule to following week
→ If torch CPU-only breaks compatibility → abort optimization, document, defer to ONNX (Day 61-90)
→ If phi3:mini OOMs on 8 GB → stay with llama3.2:3b, decision done in 5 minutes
→ If no SAP sample by week 4 → generate synthetic, validate format post-outreach
→ If Chemspec Europe programme not relevant → attend Day 1 only for ad-hoc networking
→ 80/20 STOP applies to all tasks: if overthinking, ship the 80% version
→ Easter week quiet at DGD → opportunity to pull S3 tasks forward if S2 completes early

---

## 8. DECISIONS LOG (from ACHEMA research)

| ID | Decision | Rationale | Date |
|---|---|---|---|
| D-024 | ACHEMA: Enter Concept phase (deadline 31 Aug 2026). Zero action before Day 61-90, except DECHEMA email. | Concept unlocks 3 months mentoring + feedback. Pre-revenue is normal among finalists. Carbon Minds precedent validates ESG/carbon tools. | 2026-03-31 |
| D-025 | Science4Life 2026: SKIP (deadline 13 Apr too tight). Note for Oct 2026 cycle. | Scope creep risk. 4-6h competes with Docker optimization. Budget is sacred. | 2026-03-31 |
| D-026 | Chemspec Europe Cologne (6-7 May): REPLACES generic "NRW tech event" in Task 4.5. | 45 min from Ratingen. Startup sessions + 4,500 visitors. Direct target audience. | 2026-03-31 |
| D-027 | DNP Products 2027 (deadline 7 Jun): Evaluate at start of Day 61-90. | CSRD alignment. Ceremony in Düsseldorf (local). €190 fee. | 2026-03-31 |

---

## 9. LEARNINGS LOG (from ACHEMA research)

| ID | Learning | Category |
|---|---|---|
| L-034 | ACHEMA solo founders = 0 finalists historically. Advisory board member or co-founder materially improves probability. Target for Day 61-90. | Awards/Positioning |
| L-035 | Carbon Minds (2022 ACHEMA finalist) = direct precedent for carbon accounting in chemical industry. Market validation. | Market/Competition |
| L-036 | ACHEMA value is NOT the prize (€15K, low probability), but: DECHEMA mentoring + structured feedback + investor matchmaking HTGF/BA FrankfurtRheinMain (independent of competition result). Expected value high even without winning. | Awards/Strategy |
| L-037 | DE/NRW awards landscape richer than expected. Pipeline: Chemspec (May) → DNP (Jun) → ACHEMA concept (Aug) → ACHEMA BP (Nov) → Innovationspreis NRW (2027). | Awards/Pipeline |

---

## 10. AWARDS PIPELINE (visibility track, Day 31→120)

| Award/Event | Deadline/Date | Esfuerzo | Priority | Phase |
|---|---|---|---|---|
| Chemspec Europe Cologne (visitor) | 6-7 May 2026 | 1 day + prep | HIGH | Day 31-60 (S4/S5) |
| DNP Products 2027 | 7 Jun 2026 | 3-4h + €190 | MEDIUM | Day 61-90 |
| ACHEMA Concept submission | 31 Aug 2026 | 4-6h | HIGH | Day 61-90 |
| CHEManager Innovation Pitch | Rolling | 2h | MEDIUM | After GIF + SAP + 1 pilot |
| ACHEMA Business Plan | 30 Nov 2026 | 10-15h | HIGH | Day 91-120 |
| SET Award 2027 | ~Sep 2026 | 4-6h | LOW | Day 91-120 |
| Innovationspreis NRW 2027 | Early 2027 | TBD | MEDIUM | Day 120+ |
| Science4Life 2027 cycle | ~Oct 2026 | 4-6h | MEDIUM | Day 91-120 |

---

*Plan generated: 2026-03-30 | Updated: 2026-03-31 (ACHEMA dossier findings integrated, Chemspec Europe added, awards pipeline created) | Audited: 2026-03-30 (Level 3, fixes H1-H6 applied) | Budget: ~22h over 5 weeks | Confidence: 0.93*
