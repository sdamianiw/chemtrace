# CONTEXT.md — Phase 02: RAG Client
**Phase:** 02-rag-client
**Duration:** Week 3 (8h max)
**Gate:** `python -m chemtrace ask "What was electricity consumption in Jan 2024?"` returns grounded answer with source citation
**Depends on:** Phase 01 COMPLETE ✅ (62 tests, 5 invoices, 9 commits, CODE_VERIFIER 0.97)
**SDD Gate:** 3 of 5 (Specify ✅ → Design ✅ → Plan → Execute → Verify)

---

## 1. PHASE OBJECTIVE

Build the RAG pipeline: user question → ChromaDB retrieval → Ollama LLM completion → formatted answer with source citations. Wire the CLI `ask` command. Fix NB-01 and NB-05 from Phase 01 backlog.

---

## 2. WHAT EXISTS (from Phase 01)

### Code available:
→ `src/chemtrace/vector_store.py` — VectorStore class with `query()` method (semantic search + metadata filters). TESTED (13 tests).
→ `src/chemtrace/config.py` — Config dataclass with `ollama_base_url`, `ollama_model`, `rag_top_k`, `rag_temperature`, `rag_max_tokens` already defined. **Current default for ollama_model is "llama3.1:8b" → must be changed to "llama3.2:3b" in this phase.**
→ `src/chemtrace/cli.py` — `ask` command exists as stub: prints "RAG client not yet implemented".
→ `src/chemtrace/utils.py` — `build_content()` generates text summaries already indexed in ChromaDB.
→ ChromaDB index populated with 5 invoices (from `chemtrace parse`).

### Original RAG logic to port (from `client_decarb_day6.ipynb`, now in _archive/):
→ System prompt enforcing grounded answers, source citation, off-topic refusal
→ Safety message (guardrails against harmful content)
→ Inference params: temperature=0.2, max_tokens=555
→ Context injection pattern: retrieved docs formatted as structured blocks in user message
→ Validated against Azure OpenAI GPT-4o-mini. Needs adaptation for Ollama/llama3.2:3b.

### What's different from original:
→ LLM: Azure OpenAI GPT-4o-mini → Ollama llama3.2:3b (local, HTTP API)
→ Vector store: Azure AI Search (BM25 + semantic) → ChromaDB (semantic only, with metadata filters)
→ Data format: Azure index schema → ChromaDB documents with content + metadata
→ API: Azure OpenAI SDK → raw HTTP requests to Ollama (ARCHITECTURE.md D-11)

---

## 3. TECHNICAL DECISIONS (this phase only)

### TD-01: Ollama HTTP API pattern

Per ARCHITECTURE.md section 2.5:
```python
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
```

→ `stream: False` for MVP. Simpler parsing, acceptable UX for CLI.
→ `num_predict` = Ollama's equivalent of `max_tokens`.
→ Response: `response.json()["message"]["content"]`
→ Error handling: `response.raise_for_status()` + catch `requests.ConnectionError` for "Ollama not running".

### TD-02: Model selection — llama3.2:3b as default

**Decision:** Default model changed from llama3.1:8b to llama3.2:3b.

**IMPORTANT: The current value in config.py is "llama3.1:8b". This MUST be changed to "llama3.2:3b". Also update .env.example.**

**NOTE: ARCHITECTURE.md section 2.5 still references "llama3.1:8b" in examples. Ignore those references. The authoritative model name for Phase 02 is "llama3.2:3b".**

**Rationale:**
→ Dev machine has 8 GB RAM total, ~585 MB free after Windows 11 + essential services.
→ llama3.1:8b requires ~4.7 GB → would force heavy swap, 30-120s response times, OOM risk.
→ llama3.2:3b requires ~2.0 GB → fits within available memory with Ollama's memory management.
→ Target PYME users likely have similar machines (8-16 GB).
→ RAG use case is "read context + cite numbers" → does not require deep reasoning of 8b model.
→ Expected response time: 3-8s typical on CPU, up to 15s acceptable under memory pressure. REQ-NF02 target: <10s.
→ Users with 16 GB+ RAM can switch to llama3.1:8b via OLLAMA_MODEL in .env.

**RAM requirements to document in README:**

| RAM | Recommended model | Config |
|---|---|---|
| 8 GB | llama3.2:3b (default) | No change needed |
| 16 GB+ | llama3.1:8b | `OLLAMA_MODEL=llama3.1:8b` in .env |
| 32 GB+ / GPU | llama3.1:70b or any | `OLLAMA_MODEL=<model>` in .env |

**Fallback model:** If llama3.2:3b quality is insufficient → try `ollama pull phi3:mini` (~2.3 GB, Microsoft-optimized for RAG).

### TD-03: System prompt design for llama3.2:3b

llama3.2:3b is less capable than GPT-4o-mini but sufficient for structured retrieval tasks.
Key adaptations:
→ System prompt must be VERY explicit and structured (3b models are more literal → advantage for RAG).
→ Use numbered rules, not prose paragraphs.
→ Use structured markers in context injection (numbered docs with clear delimiters).
→ Reinforce "only answer from provided data" at start AND end of system prompt.
→ Keep safety message minimal (3b has limited context window vs 8b).
→ Test with actual queries in Task 3 (integration tests).

Proposed system prompt structure:
```
You are ChemTrace, an energy data assistant for industrial carbon accounting.

RULES (follow ALL strictly):
1. ONLY answer using the CONTEXT documents provided below. Never use outside knowledge.
2. ALWAYS cite your source by document name (e.g., "Source: Invoice_Electricity_Jan2024_RuhrChem.pdf").
3. Include specific numbers (kWh, EUR, tCO2e) when available in the context.
4. If the question CANNOT be answered from the provided context, respond EXACTLY:
   "I cannot answer this question based on the available energy data."
5. Do NOT invent or estimate numbers. Only state what appears in the documents.
6. Keep answers concise. For simple questions: 2-3 sentences. For comparisons: up to 5 sentences.

SAFETY: Do not provide advice on illegal activities or generate harmful content.

REMEMBER: Only use the CONTEXT below. No outside knowledge. No invented numbers.
```

### TD-04: Context injection format

ChromaDB query returns documents with metadata. Format for LLM context:
```
=== DOCUMENT 1 ===
Source: Invoice_Electricity_Jan2024_RuhrChem.pdf
Site: Essen Blending Plant
Period: 2024-01-01 to 2024-01-31
Energy type: electricity
---
[content text from build_content()]
==================
```

→ Clear delimiters help smaller models distinguish between documents.
→ Include metadata headers so LLM can cite specific sources.
→ top_k=4 default (from Config). [Pendiente de verificación: llama3.2:3b context window size. If significantly smaller than 128k → reduce to top_k=3. For our use case with short invoice summaries, 4 docs should fit in any reasonable context window.]

### TD-05: RAGResponse structure

Per ARCHITECTURE.md:
```python
@dataclass
class RAGResponse:
    answer: str
    sources: list[dict]      # retrieved documents metadata
    model: str               # "llama3.2:3b"
    tokens_used: int | None  # from Ollama response if available
```

→ Ollama /api/chat response includes `eval_count` + `prompt_eval_count`.
→ Store sum in `tokens_used`. Useful for debugging, not critical for MVP.

### TD-06: Error handling strategy

**Check order: ChromaDB count FIRST → if empty, return error WITHOUT calling Ollama. This prevents confusing double-error scenarios.**

| Scenario | Behavior |
|---|---|
| ChromaDB empty (checked first) | RAGResponse with answer="No documents indexed. Run: chemtrace parse first." |
| Ollama not running | RAGResponse with answer="Error: Cannot connect to Ollama at {url}. Is it running? Start with: ollama serve" |
| Model not pulled | RAGResponse with answer="Error: Model {model} not available. Run: ollama pull {model}" |
| Query returns 0 results | RAGResponse with answer="No relevant documents found for your question." |
| Ollama timeout (>60s) | requests.Timeout caught → helpful error message |
| Empty/malformed response | Fallback message + log warning |

→ NEVER crash. Always return RAGResponse with informative error in `answer` field.
→ Print "Thinking..." to CLI before Ollama call so user knows it's working (3-8s wait).

### TD-07: NB-01 fix (export re-runs pipeline)

Current: `_cmd_export()` calls `run_pipeline()` → slow, unexpected.
Fix: Check if `output/invoices.csv` exists → if yes, copy to target path. If no, print "No data found. Run `chemtrace parse` first."
→ ~15 lines change in cli.py.

### TD-08: NB-05 fix (HF Hub warning)

Add to vector_store.py before sentence-transformers import:
```python
import os
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
```
→ Suppresses warnings. 3 lines.

---

## 4. FILES TO CREATE/MODIFY IN THIS PHASE

### CREATE:
```
src/chemtrace/rag_client.py      → RAG pipeline: retrieve + augment + generate
src/chemtrace/prompts.py         → system prompt + safety message + context formatter
tests/test_rag.py                → unit tests (mocked Ollama) + integration tests (live Ollama)
```

### MODIFY:
```
src/chemtrace/cli.py             → wire ask command to rag_client + fix NB-01 export
src/chemtrace/vector_store.py    → fix NB-05 (HF warning suppression)
src/chemtrace/config.py          → change OLLAMA_MODEL default from "llama3.1:8b" to "llama3.2:3b" + add OLLAMA_TIMEOUT (60s)
.env.example                     → update OLLAMA_MODEL default to llama3.2:3b + add OLLAMA_TIMEOUT=60
```

---

## 5. EXPECTED BEHAVIOR (test oracle)

### Factual questions (grounded answers expected):

| Question | Expected answer contains | Source cited |
|---|---|---|
| "What was electricity consumption in Jan 2024?" | 478,800 kWh (or 420,500 + 58,300 breakdown) | Invoice_Electricity_Jan2024_RuhrChem.pdf |
| "How much did natural gas cost in January?" | 26,925.23 EUR | Invoice_NaturalGas_Jan2024_RuhrChem.pdf |
| "What is the total diesel consumption?" | 8,500 litres | Invoice_Diesel_Feb2024_RuhrChem.pdf |
| "Compare electricity costs between Jan and Mar 2024" | Jan: 116,461.40, Mar: 108,096.61 EUR | Both electricity invoices |
| "What are the emissions from natural gas?" | ~62.78 tCO2e (310,800 x 0.000202) | NaturalGas invoice + EF |

### Off-topic questions (refusal expected):

| Question | Expected behavior |
|---|---|
| "What is the capital of Germany?" | Polite refusal: only answers about indexed energy data |
| "Write me a poem" | Refusal |
| "Tell me about climate change" | Refusal (general topic, not indexed data) |

### Error scenarios:

| Scenario | Expected behavior |
|---|---|
| Ollama not running | Clear error message with start instructions |
| No documents indexed | "Run chemtrace parse first" (checked before Ollama call) |
| Ambiguous question | Best-effort answer from retrieved context |

---

## 6. RISK MITIGATION FOR THIS PHASE

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| llama3.2:3b answer quality too low for RAG | Medium | High | Test in Task 3. 3b sufficient for "read + cite". Fallback: `ollama pull phi3:mini` (~2.3 GB). |
| llama3.2:3b ignores system prompt constraints | Medium | Medium | Explicit numbered rules + reinforce at end. Fallback: post-processing keyword filter. |
| llama3.2:3b hallucinates numbers | Medium | High | System prompt reinforces constraint x2. Integration tests verify exact numbers. |
| RAM pressure with Ollama + ChromaDB + Cursor | Medium | Medium | Close browser before running ask. 3b model fits in ~2 GB. Document in README. |
| Ollama install issues on Windows | Low | Low | Native installer since v0.1.24. Fallback: WSL2. |
| ChromaDB retrieval quality | Low | Low | Already tested (13 tests). Content quality good. |
| Time overrun (>8h) | Medium | Medium | 80/20 STOP. Cut: integration tests → manual verification only. |

---

## 7. ARCHITECTURE DECISION RECORD

| # | Decision | Rationale | Date |
|---|---|---|---|
| D-007 | llama3.2:3b as default (was llama3.1:8b) | 8 GB RAM constraint. 3b fits, 8b causes swap/OOM. RAG task doesn't need 8b reasoning. | 2026-03-27 |
| D-008 | prompts.py as separate module | System prompt needs iteration. Separating from rag_client.py isolates prompt changes. | 2026-03-27 |
| D-009 | "Thinking..." CLI feedback before Ollama call | 3-8s wait on CPU. User needs to know system is working, not frozen. | 2026-03-27 |
| D-010 | stream: False for MVP | Simpler response parsing. Streaming UX is nice-to-have for Phase 03+. | 2026-03-27 |

---

*Phase 02 context complete. See PLAN-02.md for execution tasks.*
