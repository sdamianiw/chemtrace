# PROMPT — S3 Compute Analytics (Pre-computed Math for RAG)
# AUDITED: Level 3 (2026-04-01). Fixes H1 + H2 applied. Confidence: 0.91

## Context
ChemTrace OSS Phase 04, Task 3.2 extended.
Repo: /c/Chemtrace | Branch: main | Latest commit: 5ae97cf
Tag: v0.4.0-optimized

## Problem
llama3.2:3b (and all small LLMs) fail at arithmetic. Q4 comparison query returned wrong subtraction (8,464.79 instead of 8,364.79). Numbers extracted from docs were correct, but LLM cannot reliably compute differences/sums/percentages. This is a fundamental limitation of small models, not solvable with prompting.

## Solution: Python pre-computes, LLM narrates
After ChromaDB retrieval, Python analyzes retrieved documents and computes analytics (differences, sums, percentages) from metadata. Results are injected into the context BEFORE sending to the LLM. The LLM only reads and reports pre-computed numbers.

Flow:
```
User query → ChromaDB retrieval (top_k docs) → compute_analytics(docs) → 
Context = [original docs] + [COMPUTED ANALYTICS section] → LLM narrates → Response
```

## Pre-flight
Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream

Read these files BEFORE modifying anything:
→ src/chemtrace/rag_client.py (understand current flow)
→ src/chemtrace/prompts.py (understand current system prompt + rule 7)
→ src/chemtrace/vector_store.py (understand what metadata is available on retrieved docs)
→ tests/test_rag.py (understand existing test assertions)
→ Check period format in vector_store.py metadata (print a sample query result or inspect upsert code).
   If period is ISO-sortable (e.g., "2024-01"): standard string sort works.
   If period uses month names (e.g., "Jan-2024"): implement month-name-to-number
   mapping before sort. Do NOT assume lexicographic sort on month names is correct.

## Implementation — rag_client.py

### New function: compute_analytics(documents: list[dict]) -> str

Location: Add to rag_client.py as a standalone function (not a method on a class).

Logic:
1. Group retrieved documents by `energy_type` metadata field
2. For each group with >=2 documents:
   a. Extract numeric fields: `total_eur`, `energy_amount`, `emissions_tco2`
   b. Sort by `period` (chronological). Verify period format from pre-flight:
      → If ISO-sortable (e.g., "2024-01"): use standard string sort
      → If month names (e.g., "Jan-2024"): parse to sortable key first
   c. For each numeric field where values differ:
      → Compute difference (later - earlier)
      → Compute percentage change: ((later - earlier) / earlier) * 100
   d. Format as structured text block
3. For groups with 3+ documents: list ALL values chronologically.
   Compute difference between FIRST and LAST document only.
   Pairwise consecutive diffs are deferred (over-engineering for MVP).
4. If no groups have >=2 docs → return empty string (zero injection)

Output format (example for 2 docs):
```
COMPUTED ANALYTICS (verified calculations):
Electricity comparison:
  → Jan 2024: 116,461.40 EUR | 478,800.0 kWh | 181.94 tCO2e
  → Mar 2024: 108,096.61 EUR | 420,000.0 kWh | 159.60 tCO2e
  → Difference: -8,364.79 EUR (-7.18%) | -58,800.0 kWh (-12.28%) | -22.34 tCO2e (-12.28%)
```

Output format (example for 3+ docs):
```
COMPUTED ANALYTICS (verified calculations):
Electricity comparison (3 periods):
  → Jan 2024: 116,461.40 EUR | 478,800.0 kWh | 181.94 tCO2e
  → Feb 2024: 99,200.30 EUR | 415,300.0 kWh | 157.81 tCO2e
  → Mar 2024: 108,096.61 EUR | 420,000.0 kWh | 159.60 tCO2e
  → Change (Jan → Mar): -8,364.79 EUR (-7.18%) | -58,800.0 kWh (-12.28%) | -22.34 tCO2e (-12.28%)
```

### Integration point in ask() method

After retrieval, before building the user message:
```python
# existing: docs = self.vector_store.query(question, top_k)
# existing: context = format_context(docs)

analytics = compute_analytics(docs)
if analytics:
    context = context + "\n" + analytics
    
# existing: user_message = build_user_message(question, context)
```

### Edge case handling
→ Missing numeric field (None or not present) → skip that field, don't crash
→ Division by zero (earlier value = 0) → skip percentage, show absolute diff only
→ 1 doc only → no analytics → empty string → zero injection
→ Mixed energy types in retrieval → group separately, compute per group
→ String values in metadata (ChromaDB may return strings) → float() conversion with try/except
→ 3+ docs same energy_type → list all chronologically, diff FIRST vs LAST only

## Implementation — prompts.py

Update rule 7 (replace current version):
```
"7. When comparing values, use the COMPUTED ANALYTICS section if present. "
"Report those pre-computed numbers exactly as shown. Do NOT perform your own calculations.\n"
```

## Tests — test_rag.py

Add these unit tests (NO Ollama needed, use unittest.mock):

1. `test_compute_analytics_two_electricity_docs`:
   → Input: 2 docs with energy_type=electricity, different periods and values
   → Assert: output contains "COMPUTED ANALYTICS"
   → Assert: output contains correct difference (computed in test)

2. `test_compute_analytics_single_doc`:
   → Input: 1 doc only
   → Assert: output is empty string

3. `test_compute_analytics_mixed_types`:
   → Input: 3 docs (2 electricity, 1 gas)
   → Assert: analytics only for electricity group

4. `test_compute_analytics_missing_field`:
   → Input: 2 docs, one missing total_eur
   → Assert: no crash, skips that field

5. `test_compute_analytics_zero_value`:
   → Input: 2 docs, earlier total_eur = 0
   → Assert: no crash, no percentage shown, absolute diff shown

## Verification

After implementation:
→ PYTHONPATH="C:\Chemtrace\src" python -m pytest tests/ -q -k "not integration"
→ All existing tests must still pass + 5 new tests pass
→ Do NOT run integration tests (Sebas tests manually after)

## Commit

```bash
git add src/chemtrace/rag_client.py src/chemtrace/prompts.py tests/test_rag.py
git commit -m "feat: pre-computed analytics for comparison queries (Python math, LLM narrates)"
```

Do NOT push. Sebas pushes manually.

## Constraints
→ Read ALL 4 files before modifying anything (pre-flight)
→ compute_analytics is a pure function (no side effects, no I/O)
→ Do NOT change vector_store.py, config.py, cli.py, or any other files
→ Do NOT add new dependencies
→ If unit tests fail → fix the implementation, not the tests
→ Metadata field names: verify exact names from vector_store.py (may be energy_amount, total_eur, emissions_tco2 → confirm before coding)
→ Use arrows (→) not dashes (-) in any output strings shown to users
