# Decisions — ChemTrace OSS
## Decision log: only decisions impacting >1 module or architecture.
## Review date = 30 days from decision. Flag "REVIEW DUE" when reached.

| # | Date | Decision | Reasoning | Expected Outcome | Review Date | Status |
|---|------|----------|-----------|-----------------|------------|--------|
| D-001 | 2026-03-23 | Ollama local, zero cloud | Privacy + zero cost + offline | Users deploy without API keys | 2026-04-22 | Active |
| D-002 | 2026-03-23 | pdfplumber over Azure DocInt | OSS, local, sufficient for digital PDFs | Parse all German invoice formats | 2026-04-22 | Active |
| D-003 | 2026-03-23 | ChromaDB over Azure AI Search | OSS, embeddable, semantic + metadata | Local vector search <1s | 2026-04-22 | Active |
| D-004 | 2026-03-24 | Persistent memory system | Self-improvement + accountability + autonomy | Decreasing error rate over sessions | 2026-04-23 | Active |
| D-005 | 2026-03-27 | consumption_unit field on LineItem (not rename consumption_kwh) | Backward compat: renaming breaks all tests + downstream; adding a unit field clarifies without breakage | diesel uses "litres", everything else "kWh"; CSV documents both | 2026-04-26 | Active |
| D-006 | 2026-03-27 | argparse for CLI (not click/typer) | Stdlib only; 4 commands don't justify extra dep; testable via main(argv) | All CLI commands accessible via subparsers | 2026-04-26 | Active |
| D-028 | 2026-03-31 | Keep llama3.2:3b as default LLM. phi3:mini rejected. | phi3:mini timed out on 2/5 queries (Q1 electricity, Q4 comparison) at OLLAMA_TIMEOUT=60 on 8 GB RAM. llama3.2:3b passed 5/5 with correct numbers, source citations, and guardrail refusal. phi3:mini quality was comparable when it responded, but latency is unacceptable. Zero code changes needed. | Reliable 5/5 query response with llama3.2:3b | 2026-04-30 | Active |
