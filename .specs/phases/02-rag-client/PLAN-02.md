# PLAN-02.md — Phase 02: RAG Client
**Phase:** 02-rag-client
**Tasks:** 3 (max per SDD rules)
**Total budget:** 8h
**Execution tool:** Claude Code via Cursor (Sonnet 4.6)
**Planning tool:** claude.ai Opus 4.6 (this chat)

---

## PRE-FLIGHT CHECKLIST (before opening Claude Code)

```bash
# === STEP 1: Install Ollama (Windows native installer) ===
# Download from: https://ollama.com/download/windows
# Run installer → Ollama runs as system service
# Verify installation:
ollama --version
# Expected: ollama version 0.x.x

# === STEP 2: Pull the default model (~2 GB download) ===
ollama pull llama3.2:3b
# Wait for download to complete

# === STEP 3: Verify Ollama is running and model works ===
# Option A (PowerShell or cmd):
curl http://localhost:11434/api/tags

# Option B (if curl JSON escaping fails in Git Bash):
ollama run llama3.2:3b "Say hello in one sentence"
# Should return a greeting. Type /bye to exit.

# Option C (Git Bash friendly):
curl -s http://localhost:11434/api/tags | python -c "import sys,json; print([m['name'] for m in json.load(sys.stdin)['models']])"
# Should show ['llama3.2:3b']

# === STEP 4: RAM preparation ===
# Close before running Claude Code + Ollama:
#   → Edge/Chrome (all tabs)
#   → WhatsApp Desktop
#   → Spotify
#   → ChatGPT Desktop
#   → Any non-essential apps
# Keep: OneDrive, Windows Security, Cursor
# Target: <80% RAM usage before starting

# === STEP 5: Verify ChemTrace Phase 01 state ===
cd /c/Chemtrace
git status                    # clean working tree
git log --oneline -3          # last commit: 493d95c memory: session update
python -m pytest tests/ -q    # 62 passed

# === STEP 6: Verify ChromaDB has data ===
python -c "from chemtrace.vector_store import VectorStore; from chemtrace.config import Config; vs = VectorStore(Config()); print(f'Docs: {vs.count()}')"
# Expected: Docs: 5

# === STEP 7: Copy Phase 02 specs to repo ===
mkdir -p .specs/phases/02-rag-client
# Copy CONTEXT_Phase02_final.md → .specs/phases/02-rag-client/CONTEXT.md
# Copy PLAN-02_final.md → .specs/phases/02-rag-client/PLAN-02.md

# VERIFY files copied correctly:
ls .specs/phases/02-rag-client/CONTEXT.md .specs/phases/02-rag-client/PLAN-02.md
# Both files must exist. If not → copy them before proceeding.

# === STEP 8: Prepare Claude Code session ===
# Power Options → Sleep: Never
# Open Cursor → cd C:\Chemtrace
# Terminal: claude --dangerously-skip-permissions
# Paste via RIGHT-CLICK (not Ctrl+V)
# Use /status every ~5 exchanges
```

**BLOCKER CHECK:**
→ If Ollama install fails → STOP. Debug installation first.
→ If `ollama pull llama3.2:3b` fails → check internet, retry.
→ If smoke test fails → check `ollama serve` is running (auto-starts on Windows).
→ If RAM >85% after closing apps → proceed anyway, llama3.2:3b handles memory pressure well.
→ If .specs/phases/02-rag-client/ files missing → STOP. Copy files first.

---

## TASK 1: RAG Client Core + Prompts (3h)

### Goal
Create `rag_client.py` and `prompts.py` with full RAG pipeline: ChromaDB retrieval → context formatting → Ollama completion → structured RAGResponse. Fix NB-05 (HF warning). Change default model to llama3.2:3b.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/REQUIREMENTS.md (section REQ-F04: RAG Client)
- .specs/ARCHITECTURE.md (section 2.5: rag_client.py)
- .specs/phases/02-rag-client/CONTEXT.md (all sections, especially TD-01 through TD-08)
- src/chemtrace/config.py (understand existing Config fields and CURRENT defaults)
- src/chemtrace/vector_store.py (understand query() interface and return format)
- src/chemtrace/utils.py (understand build_content() output format)
- .skills/PROMPT_CONTRACT.md

GOAL: Create RAG client module + prompts module. Full pipeline: question → retrieve → augment → generate → RAGResponse.

CONSTRAINTS:
→ Files to CREATE: src/chemtrace/rag_client.py, src/chemtrace/prompts.py
→ Files to MODIFY:
  - src/chemtrace/config.py (change default OLLAMA_MODEL from "llama3.1:8b" to "llama3.2:3b", add OLLAMA_TIMEOUT default 60)
  - src/chemtrace/vector_store.py (NB-05 fix: add HF telemetry suppression, 3 lines at top before imports)
  - .env.example (update OLLAMA_MODEL default to llama3.2:3b, add OLLAMA_TIMEOUT=60)
→ Files NOT to touch: pdf_parser.py, etl.py, parser_patterns.py, cli.py, tests/*, .specs/*
→ Max ~300 lines total new code

IMPORTANT: Default model is llama3.2:3b (NOT llama3.1:8b). The current config.py has "llama3.1:8b" as default — this MUST be changed to "llama3.2:3b". Ignore any references to llama3.1:8b in ARCHITECTURE.md — those are outdated.

FAILURE MODES:
→ Ollama not running → must return helpful error in RAGResponse, never crash
→ Model not pulled → detect via Ollama API error and return specific message
→ ChromaDB empty → check count FIRST before calling Ollama, return informative message
→ Ollama returns empty response → handle gracefully with fallback message
→ System prompt too weak → llama3.2:3b hallucinates (test in Task 3)
→ Context injection format unclear → model can't distinguish documents

IMPLEMENTATION DETAILS:

rag_client.py must implement:
1. ask(question, config, store) → RAGResponse
2. Internal flow:
   a. Check store.count() > 0, else return error RAGResponse (do NOT call Ollama)
   b. Retrieve top_k docs via store.query(question)
   c. Format context via prompts.format_context(docs)
   d. Build messages: [system_prompt, user_message_with_context_and_question]
   e. Call _call_ollama(messages, config) → raw answer string
   f. Return RAGResponse(answer, sources, model, tokens_used)
3. _call_ollama(messages, config) → str
   - POST to {ollama_base_url}/api/chat with stream=False
   - Timeout: config.ollama_timeout seconds
   - Handle: ConnectionError → "Ollama not running" message
   - Handle: Timeout → "Request timed out" message
   - Handle: HTTP 404 → "Model not found, run ollama pull" message
   - Handle: Empty response → fallback error message
   - Extract tokens: eval_count + prompt_eval_count from response JSON

prompts.py must implement:
1. SYSTEM_PROMPT: constant string with numbered rules (see CONTEXT.md TD-03)
   Must include:
   - Role definition (ChemTrace energy data assistant)
   - Rule 1: ONLY answer from provided CONTEXT
   - Rule 2: ALWAYS cite source document name
   - Rule 3: Include specific numbers
   - Rule 4: Exact refusal phrase for unanswerable questions
   - Rule 5: Do NOT invent numbers
   - Rule 6: Concise answers (simple: 2-3 sentences, comparisons: up to 5)
   - Safety clause
   - Final reminder: only use CONTEXT, no invented numbers
2. format_context(documents: list[dict]) → str
   - Format each doc with === DOCUMENT N === delimiters
   - Include metadata: Source, Site, Period, Energy type
   - Include content text between delimiters
3. build_user_message(question: str, context: str) → str
   - Structure: "CONTEXT:\n{context}\n\nQUESTION: {question}"

config.py changes:
→ OLLAMA_MODEL default: change from "llama3.1:8b" to "llama3.2:3b"
→ Add: ollama_timeout: int field, default 60, from env OLLAMA_TIMEOUT

vector_store.py NB-05 fix:
→ Add at very top of file (before any other imports):
  import os
  os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
  os.environ["TOKENIZERS_PARALLELISM"] = "false"

VERIFICATION:
→ python -c "from chemtrace.rag_client import ask, RAGResponse; print('OK')"
→ python -c "from chemtrace.prompts import SYSTEM_PROMPT, format_context; print(len(SYSTEM_PROMPT))"
→ python -c "from chemtrace.config import Config; c = Config(); print(c.ollama_model, c.ollama_timeout)"
→ Expected: llama3.2:3b 60
→ grep -n "ollama_model\|llama3" src/chemtrace/config.py
→ Expected: default shows "llama3.2:3b", no remaining "llama3.1:8b" as default
→ python -c "from chemtrace.vector_store import VectorStore; from chemtrace.config import Config; vs = VectorStore(Config()); print(vs.count())"
→ Expected: 5 (confirms NB-05 fix doesn't break anything, no HF warnings printed)
→ pytest tests/ -q
→ Expected: 62 passed (verify no test hardcodes model name — if any test fails, check if it asserts on "llama3.1:8b")

Quick integration smoke test (requires Ollama running with llama3.2:3b):
→ python -c "
from chemtrace.rag_client import ask
from chemtrace.config import Config
from chemtrace.vector_store import VectorStore
config = Config()
store = VectorStore(config)
result = ask('What was electricity consumption in Jan 2024?', config, store)
print(f'Answer: {result.answer[:200]}')
print(f'Sources: {len(result.sources)}')
print(f'Model: {result.model}')
"
→ Should print answer mentioning 478,800 kWh or 420,500 kWh with source citation

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 1)
→ [ ] rag_client.py: ask() returns RAGResponse for valid question
→ [ ] rag_client.py: returns error RAGResponse when Ollama is not running (no crash)
→ [ ] rag_client.py: returns error RAGResponse when ChromaDB is empty (checked BEFORE Ollama call)
→ [ ] rag_client.py: timeout handling (60s default, configurable)
→ [ ] rag_client.py: handles model-not-found error with "ollama pull" instruction
→ [ ] prompts.py: SYSTEM_PROMPT with numbered rules enforcing grounding + citation + refusal
→ [ ] prompts.py: format_context() produces clearly delimited document blocks
→ [ ] prompts.py: build_user_message() combines context + question
→ [ ] config.py: OLLAMA_MODEL default changed from "llama3.1:8b" to "llama3.2:3b"
→ [ ] config.py: OLLAMA_TIMEOUT field added (default 60)
→ [ ] .env.example: updated with new defaults
→ [ ] vector_store.py: HF telemetry warnings suppressed (NB-05)
→ [ ] Smoke test: factual question returns grounded answer (manual verify)
→ [ ] All 62 existing tests still pass (no regressions from model default change)

### Post-Task
```bash
git add .
git commit -m "feat: RAG client + prompts + Ollama integration (Phase 02, Task 1)"
# /clear in Claude Code for fresh context
```

---

## TASK 2: CLI Wiring + NB-01 Fix + Unit Tests (3h)

### Goal
Wire the CLI `ask` command to rag_client, fix NB-01 (export re-runs pipeline), write unit tests with mocked Ollama.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/phases/02-rag-client/CONTEXT.md (TD-06 error handling order, TD-07 NB-01 fix, TD-09 "Thinking..." feedback)
- src/chemtrace/cli.py (current state: understand ask stub + export implementation)
- src/chemtrace/rag_client.py (understand ask() interface and RAGResponse)
- src/chemtrace/prompts.py (understand exports)
- tests/test_cli.py (existing CLI tests)
- .skills/PROMPT_CONTRACT.md

GOAL: Wire CLI ask command + fix export command + write unit tests for RAG.

CONSTRAINTS:
→ Files to CREATE: tests/test_rag.py
→ Files to MODIFY: src/chemtrace/cli.py (wire ask + fix export), tests/test_cli.py (update/add ask test)
→ Files NOT to touch: rag_client.py, prompts.py, config.py, vector_store.py, pdf_parser.py, etl.py
→ If NB-05 fix from Task 1 caused issues in vector_store.py → flag the issue in output, do not modify vector_store.py yourself
→ Max ~350 lines total new/modified code

FAILURE MODES:
→ CLI ask crashes when Ollama is down → must show user-friendly error from RAGResponse
→ Export fix breaks existing export behavior → test both paths (CSV exists / doesn't exist)
→ Mocked tests pass but real integration fails → keep mocks realistic
→ Test imports break existing test suite → verify pytest runs ALL tests after changes

CLI ASK IMPLEMENTATION:
→ Replace stub in _cmd_ask() with:
  1. Initialize Config + VectorStore
  2. Print "Thinking..." to stderr (user feedback during Ollama call)
  3. Call ask(question, config, store) from rag_client
  4. Print formatted output:
     - Answer text
     - Blank line
     - "Sources:" header + list of source document names
     - If tokens_used: print "(Model: {model}, Tokens: {tokens})" as footer
  5. If RAGResponse.answer starts with "Error:" → print to stderr, exit code 1

CLI EXPORT FIX (NB-01):
→ Current: _cmd_export() runs full pipeline → slow, unexpected
→ New logic:
  1. Determine default CSV path: config.output_dir / "invoices.csv"
  2. If CSV exists → copy to --output target (or print path if no --output given)
  3. If CSV does NOT exist → print "No data found. Run `chemtrace parse` first." to stderr, exit 1
  4. Do NOT call run_pipeline() from export

TEST STRATEGY for test_rag.py:
→ Unit tests (NO Ollama needed, use unittest.mock):
  1. test_ask_with_mocked_ollama: mock requests.post → verify RAGResponse has answer + sources + model
  2. test_ask_connection_error: mock ConnectionError → verify error message in RAGResponse.answer
  3. test_ask_timeout: mock Timeout → verify timeout error in RAGResponse.answer
  4. test_ask_empty_store: mock VectorStore.count() returning 0 → verify "no documents" message
  5. test_format_context_single_doc: verify formatting with 1 document
  6. test_format_context_multiple_docs: verify formatting with 3 documents, correct numbering
  7. test_system_prompt_contains_rules: verify SYSTEM_PROMPT has key phrases ("ONLY answer", "cite", "cannot answer")
  8. test_build_user_message: verify question + context combined with correct structure
→ Integration tests (REQUIRE Ollama running, skip if not available):
  9. test_integration_factual_question: real query → answer contains expected number (e.g., "478" or "420")
  10. test_integration_offtopic_refusal: off-topic query → answer contains refusal phrase

→ Integration test decorator: @pytest.mark.skipif(not _ollama_available(), reason="Ollama not running")
→ Helper: _ollama_available() tries GET to http://localhost:11434/api/tags, returns True/False

VERIFICATION:
→ pytest tests/ -v -k "not integration" → all pass without Ollama
→ Count: 62 existing + 8 new unit = 70 pass
→ python -m chemtrace ask "What was electricity consumption in Jan 2024?" → formatted answer with sources
→ python -m chemtrace ask "Write me a poem" → refusal message
→ python -m chemtrace export --output output/test_export.csv → copies existing CSV (if available)
→ python -m chemtrace export → works (shows path or copies)
→ Stop Ollama → python -m chemtrace ask "test" → error message, no crash, no traceback
→ Verify: pytest tests/ -v -k "not integration" → 70 pass, 0 fail

After completion, apply .skills/CODE_VERIFIER.md protocol.
```

### Acceptance Criteria (Task 2)
→ [ ] CLI `ask` command works end-to-end (with Ollama running)
→ [ ] CLI `ask` prints "Thinking..." before Ollama call
→ [ ] CLI `ask` shows formatted answer with sources section
→ [ ] CLI `ask` shows user-friendly error when Ollama is down (no crash, no traceback)
→ [ ] CLI `export` no longer re-runs pipeline (NB-01 fixed)
→ [ ] CLI `export` copies existing CSV or shows "run parse first"
→ [ ] test_rag.py: 8 unit tests, all pass without Ollama
→ [ ] test_rag.py: 2 integration tests with skip-if-no-ollama decorator
→ [ ] All 62 existing tests still pass (zero regressions)
→ [ ] Total unit test count: 62 + 8 = 70+

### Post-Task
```bash
git add .
git commit -m "feat: CLI ask wiring + export fix + RAG unit tests (Phase 02, Task 2)"
# /clear in Claude Code for fresh context
```

---

## TASK 3: Integration Testing + Prompt Tuning + Phase Verification (2h)

### Goal
Run integration tests with live Ollama, tune system prompt if needed, run full phase verification.

### Claude Code Prompt (copy-paste ready)

```
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
- .specs/phases/02-rag-client/CONTEXT.md (section 5: Expected Behavior, section 3: TD-03 system prompt)
- src/chemtrace/rag_client.py (current implementation)
- src/chemtrace/prompts.py (current system prompt)
- tests/test_rag.py (current tests, especially integration tests)
- .skills/PROMPT_CONTRACT.md
- .skills/CODE_VERIFIER.md

GOAL: Run integration tests with live Ollama. Tune prompt if answer quality is poor. Generate VERIFY.md.

CONSTRAINTS:
→ Files to MODIFY (only if prompt tuning needed): src/chemtrace/prompts.py
→ Files to MODIFY: tests/test_rag.py (adjust integration test assertions if needed)
→ Files to CREATE: .specs/phases/02-rag-client/VERIFY.md
→ Files NOT to touch: rag_client.py (unless bug found), cli.py, config.py, vector_store.py
→ Prompt tuning: max 3 iterations. If still problematic after 3 → document limitation and move on.

IMPORTANT: Model is llama3.2:3b. It is less capable than 8b models. Acceptable trade-offs:
→ Answers may be shorter/more literal → OK for data retrieval
→ May not synthesize across documents as well → individual document citation is sufficient
→ May occasionally miss off-topic refusal → document as known limitation if persistent

SUCCESS CRITERIA FOR PROMPT TUNING:
→ Factual question returns correct number from source data → MUST PASS
→ Factual question cites source document → MUST PASS
→ Off-topic question triggers refusal → SHOULD PASS (if fails after 3 iterations → document as limitation)
→ If 2 of 3 criteria pass → accept and document the gap

FAILURE MODES:
→ llama3.2:3b hallucinates numbers → tighten with "NEVER invent", "FORBIDDEN to estimate"
→ llama3.2:3b ignores off-topic refusal → add stronger instruction or keyword-based post-filter
→ Integration tests flaky → use contains/regex assertions, not exact match
→ Prompt changes break unit tests → run full suite after each iteration

INTEGRATION TEST EXECUTION:
1. First, ensure ChromaDB has 5 documents indexed:
   → python -m chemtrace parse --input-dir data/sample_invoices/

2. Run integration tests:
   → pytest tests/test_rag.py -v -k "integration" --tb=long

3. If tests fail, analyze WHY:
   a. Retrieval issue → log what docs ChromaDB returns for the query
   b. Prompt issue → LLM ignores constraints → tighten prompt
   c. Format issue → LLM can't parse context → adjust delimiters
   d. Model capability issue → 3b genuinely can't do this → document, accept

4. Manual test battery (run each, evaluate quality):
   → python -m chemtrace ask "What was electricity consumption in Jan 2024?"
   → python -m chemtrace ask "How much did natural gas cost in January 2024?"
   → python -m chemtrace ask "What is the total diesel consumption?"
   → python -m chemtrace ask "Compare electricity costs between January and March 2024"
   → python -m chemtrace ask "What is the capital of Germany?"
   → python -m chemtrace ask "Write me a poem about energy"

5. Evaluate each answer:
   - Correct numbers from source docs? (critical → MUST PASS)
   - Source document cited? (important → MUST PASS)
   - Refuses off-topic? (important → SHOULD PASS)
   - Concise and readable? (nice-to-have)

PROMPT TUNING (if needed, max 3 iterations):
→ Iteration 1: Strengthen constraint language ("NEVER", "FORBIDDEN", "STRICTLY")
→ Iteration 2: Add 1-2 few-shot examples to system prompt (example Q + ideal A)
→ Iteration 3: Try XML-like tags instead of === delimiters for context
→ After EACH iteration: run unit tests + 2 manual queries to verify improvement
→ If 3 iterations done and still problematic: document in VERIFY.md as known limitation

VERIFICATION (Phase 02 Gate):
→ pytest tests/ -v -k "not integration" → all unit tests pass (70+)
→ pytest tests/test_rag.py -v -k "integration" → pass (with Ollama running)
→ python -m chemtrace ask "What was electricity consumption in Jan 2024?" → correct numbers + source
→ python -m chemtrace ask "What is the capital of Germany?" → polite refusal
→ python -m chemtrace status → shows document count
→ python -m chemtrace export → works without re-running pipeline (NB-01)
→ grep -rn "API_KEY\|password\|secret" src/ → no secrets
→ grep -rn "llama3.1:8b" src/ .env.example → should NOT appear as default (only in comments if any)
→ Apply .skills/CODE_VERIFIER.md FULL protocol (end-of-phase)

After CODE_VERIFIER, generate .specs/phases/02-rag-client/VERIFY.md with results.
```

### Acceptance Criteria (Task 3)
→ [ ] Integration tests pass with live Ollama + llama3.2:3b
→ [ ] Factual questions return grounded answers with correct numbers
→ [ ] Source citations present in answers
→ [ ] Off-topic questions refused (or documented as known limitation)
→ [ ] System prompt tuning documented (iterations, changes, rationale)
→ [ ] All unit tests still pass after any prompt changes
→ [ ] VERIFY.md generated with full CODE_VERIFIER report
→ [ ] Known limitations documented (if any)

### Post-Task
```bash
git add .
git commit -m "feat: integration tests + prompt tuning + phase 02 verification"
git tag v0.2.0-rag-client
# Push to GitHub
git push origin main --tags
# /clear in Claude Code
```

---

## PHASE 02 GATE (Definition of Done)

| # | Check | Command | Expected |
|---|---|---|---|
| G-01 | RAG answers factual question | `chemtrace ask "What was electricity consumption in Jan 2024?"` | Answer with 478,800 kWh or breakdown + source |
| G-02 | RAG refuses off-topic | `chemtrace ask "What is the capital of Germany?"` | Polite refusal |
| G-03 | RAG cites sources | Any factual answer | Document name mentioned |
| G-04 | RAG handles Ollama down | Stop Ollama → run ask | Error message, no crash |
| G-05 | Export fixed (NB-01) | `chemtrace export` | Copies CSV, no pipeline re-run |
| G-06 | HF warning gone (NB-05) | Run any VectorStore command | No HF Hub warnings |
| G-07 | Default model correct | `python -c "from chemtrace.config import Config; print(Config().ollama_model)"` (without .env override) | llama3.2:3b |
| G-08 | Unit tests pass | `pytest tests/ -k "not integration"` | 70+ pass |
| G-09 | Integration tests pass | `pytest tests/ -k "integration"` | 2+ pass (Ollama required) |
| G-10 | No regressions | `pytest tests/` (all) | 62 original + new = all pass |
| G-11 | Code Verifier | `.skills/CODE_VERIFIER.md` full run | No critical findings |

**If all G-01 to G-11 pass → Phase 02 complete. Proceed to Phase 03 (Docker Deploy).**

---

## NOTES

### LLM Non-Determinism
Integration tests involving Ollama are inherently non-deterministic. Strategies:
→ Use `temperature: 0.0` for test runs (override in test fixture) for most deterministic output
→ Assert on CONTAINS not EQUALS (e.g., "478" in answer, not exact string match)
→ Allow regex for source citation (e.g., `Invoice.*Electricity.*Jan`)
→ If test passes 4/5 times → accept, document flakiness
→ Mark integration tests clearly so CI can skip them

### RAM Management During Sessions
→ Before running `chemtrace ask`: close Edge, Spotify, WhatsApp, non-essential apps
→ Ollama + llama3.2:3b peak: ~2.5 GB. With ChromaDB + sentence-transformers: ~3.5 GB total.
→ After session: Ollama releases model from RAM after idle timeout (default 5 min)
→ If OOM occurs: `ollama stop` → free RAM → retry

### Model Upgrade Path
→ 8 GB RAM: llama3.2:3b (default, tested)
→ 16 GB RAM: `OLLAMA_MODEL=llama3.1:8b` in .env
→ GPU available: Ollama auto-detects GPU, any model size works
→ All models use same Ollama API → zero code changes needed
→ **Fallback model:** If llama3.2:3b quality insufficient → `ollama pull phi3:mini` (~2.3 GB, Microsoft-optimized for RAG)

---

*PLAN-02 ready for execution. 3 tasks, 8h budget, copy-paste prompts for Claude Code.*
