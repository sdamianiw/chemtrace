# Decisions — ChemTrace OSS
## Decision log: only decisions impacting >1 module or architecture.
## Review date = 30 days from decision. Flag "REVIEW DUE" when reached.

| # | Date | Decision | Reasoning | Expected Outcome | Review Date | Status |
|---|------|----------|-----------|-----------------|------------|--------|
| D-001 | 2026-03-23 | Ollama local, zero cloud | Privacy + zero cost + offline | Users deploy without API keys | 2026-04-22 | Active |
| D-002 | 2026-03-23 | pdfplumber over Azure DocInt | OSS, local, sufficient for digital PDFs | Parse all German invoice formats | 2026-04-22 | Active |
| D-003 | 2026-03-23 | ChromaDB over Azure AI Search | OSS, embeddable, semantic + metadata | Local vector search <1s | 2026-04-22 | Active |
| D-004 | 2026-03-24 | Persistent memory system | Self-improvement + accountability + autonomy | Decreasing error rate over sessions | 2026-04-23 | Active |
