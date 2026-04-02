# ChemTrace OSS

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)

Open-source Scope 1-3 carbon accounting pipeline for German industrial SMEs.

Open-Source Scope 1-3 Carbon-Accounting-Pipeline fuer deutsche Industrie-KMU.

## Demo

![ChemTrace Demo](docs/demo.gif)

---

## What is ChemTrace?

German industrial SMEs face mandatory CSRD Scope 1-3 reporting from 2026-2027, but existing
solutions require expensive SaaS subscriptions or cloud vendor lock-in. ChemTrace parses
energy invoices (electricity, natural gas, diesel) from PDF files, calculates CO2e emissions
using configurable factors, indexes the data in a local vector store, and answers natural
language questions about consumption and emissions — all running entirely on your own machine.
It also parses SAP CSV energy exports with automatic encoding, delimiter, and number format detection.

Key features: zero cloud dependencies, zero API keys, audit-ready emission traceability,
bilingual CLI, Docker deployment in under 30 minutes.

---

## Supported Input Formats

| Format | Description | Auto-detected |
|--------|-------------|---------------|
| PDF | German energy invoices (electricity, natural gas, diesel) | By .pdf extension |
| SAP CSV | SAP ECC/S4HANA energy exports (SE16N, ALV, Z-reports) | By .csv extension |

SAP CSV specifics:
→ Encoding: cp1252 (default), UTF-8, UTF-8 with BOM
→ Delimiter: semicolon (default), comma, tab
→ Number format: German (1.234,56) and English (1,234.56)
→ Headers: optional (column inference for headerless files)
→ Period formats: 2024-01, 01.2024, 202401, Jan 2024, P01/2024

---

## Quick Start (Docker)

> First build downloads torch + sentence-transformers (~2.5 GB image, 5-10 min).
> First model pull downloads llama3.2:3b (~2 GB, 3-5 min). Subsequent runs use cache.

**Step 1: Clone the repository**

```bash
git clone https://github.com/sdamianiw/chemtrace.git
cd chemtrace
```

**Step 2: Start Ollama and wait for it to be healthy**

```bash
docker compose up -d ollama
docker compose ps    # wait until ollama shows "healthy"
```

**Step 3: Parse the sample invoices**

```bash
docker compose run --rm chemtrace parse
```

Expected output: 5 invoices parsed, CSV written to `./output/`.

```bash
# Parse SAP CSV energy exports
docker compose run --rm -e CHEMTRACE_INPUT_DIR=./data/sample_sap chemtrace parse
```

**Step 4: Ask a question**

```bash
docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"
```

**Step 5: Shut down**

```bash
docker compose down
```

ChromaDB data and Ollama models are preserved in Docker named volumes between runs.

---

## Quick Start (Local Development)

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com) installed and running.

**Install dependencies**

```bash
pip install -r requirements.txt
```

**Pull the default model**

```bash
ollama pull llama3.2:3b
```

**Parse invoices**

```bash
PYTHONPATH=src python -m chemtrace parse --input-dir data/sample_invoices/
```

```bash
# For SAP CSV files, set the input directory:
CHEMTRACE_INPUT_DIR=data/sample_sap PYTHONPATH=src python -m chemtrace parse
```

**Ask a question**

```bash
PYTHONPATH=src python -m chemtrace ask "What was electricity consumption in Jan 2024?"
```

**Other commands**

```bash
PYTHONPATH=src python -m chemtrace status          # show indexed document count
PYTHONPATH=src python -m chemtrace export output/  # export data as CSV
```

---

## Schnellstart (Docker)

> Erster Build laedt torch + sentence-transformers (~2,5 GB Image, 5-10 Min.).
> Erster Modell-Download: llama3.2:3b (~2 GB, 3-5 Min.). Folgelaeufe nutzen den Cache.

**Schritt 1: Repository klonen**

```bash
git clone https://github.com/sdamianiw/chemtrace.git
cd chemtrace
```

**Schritt 2: Ollama starten und auf Betriebsbereitschaft warten**

```bash
docker compose up -d ollama
docker compose ps    # warten bis ollama "healthy" anzeigt
```

**Schritt 3: Musterrechnungen verarbeiten**

```bash
docker compose run --rm chemtrace parse
```

Ergebnis: 5 Rechnungen verarbeitet, CSV-Ausgabe in `./output/`.

```bash
# SAP CSV Energiedaten parsen
docker compose run --rm -e CHEMTRACE_INPUT_DIR=./data/sample_sap chemtrace parse
```

**Schritt 4: Frage stellen**

```bash
docker compose run --rm chemtrace ask "What was electricity consumption in Jan 2024?"
```

**Schritt 5: Herunterfahren**

```bash
docker compose down
```

ChromaDB-Daten und Ollama-Modelle bleiben in Docker-Volumes zwischen den Laeufen erhalten.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│                                                         │
│   CLI: chemtrace parse | ask | status | export          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌──────────┐   ┌──────────┐   ┌───────────────────┐  │
│   │          │   │          │   │                   │  │
│   │ PDF/CSV  │──→│ ETL      │──→│ Vector Store      │  │
│   │ Parsers  │   │ Pipeline │   │ (ChromaDB)        │  │
│   │          │   │          │   │                   │  │
│   └──────────┘   └──────────┘   └────────┬──────────┘  │
│                                          │              │
│                                          ▼              │
│                                 ┌───────────────────┐   │
│                                 │                   │   │
│                                 │ RAG Client        │   │
│                                 │ (Ollama LLM)      │   │
│                                 │                   │   │
│                                 └───────────────────┘   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  Config (.env) │ Emission Factors │ Error Logger        │
└─────────────────────────────────────────────────────────┘
```

**Data flow:**

```
PDF files (data/sample_invoices/)
    │
    ▼
pdf_parser.py ──→ ParseResult
                      │
CSV files (data/sample_sap/)      │
    │                              ▼
    ▼                          etl.py
sap_parser.py ──→ ParseResult ──→ (validate → enrich → store)
                                   │
                                   ├──→ CSV export (output/)
                                   ├──→ ChromaDB index
                                   └──→ errors.csv

User question (CLI)
    │
    ▼
rag_client.py ──→ ChromaDB retrieval → Ollama completion → formatted answer
```

---

## Configuration

Copy `.env.example` to `.env` and edit as needed. Docker Compose reads `.env` automatically.

| Variable | Default | Description |
|---|---|---|
| `CHEMTRACE_INPUT_DIR` | `./data/sample_invoices` | Input PDF directory |
| `CHEMTRACE_OUTPUT_DIR` | `./output` | CSV output directory |
| `CHEMTRACE_CHROMA_DIR` | `./chroma_db` | ChromaDB persistence path |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2:3b` | LLM model name |
| `OLLAMA_TIMEOUT` | `60` | Ollama request timeout (seconds) |
| `RAG_TOP_K` | `4` | Number of retrieved documents |
| `RAG_TEMPERATURE` | `0.2` | LLM sampling temperature |
| `RAG_MAX_TOKENS` | `555` | Maximum response tokens |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local sentence embedding model |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Emission Factors

Emission factors are stored in `data/emission_factors/factors.json` with source citations.
Every CO2e calculation is fully traceable: `energy_amount × factor = emissions_tco2`.

| Energy Type | Factor | Unit | Source | Year |
|---|---|---|---|---|
| Electricity (DE grid mix) | 0.000380 | tCO2e/kWh | UBA Emissionsfaktoren | 2024 |
| Natural Gas | 0.000202 | tCO2e/kWh | Synthetic ESG Report | 2024 |
| Diesel | 0.002680 | tCO2e/litre | Synthetic ESG Report (DEFRA 2024) | 2024 |

To add a new energy type: add one entry to `factors.json` — no code changes required.

---

## RAM Requirements

| RAM | Recommended Setup | Default Model |
|---|---|---|
| 8 GB | Local development only (no Docker) | `llama3.2:3b` |
| 16 GB | Docker (recommended minimum) | `llama3.2:3b` |
| 32 GB+ | Docker + larger models | `llama3.1:8b` or any |

To switch models: set `OLLAMA_MODEL=llama3.1:8b` in your `.env` file.

**Windows (WSL2) users:** Docker runs inside WSL2. Create or edit `~/.wslconfig` to ensure sufficient memory:
```ini
[wsl2]
memory=4GB
```

After editing, run `wsl --shutdown` and restart Docker Desktop. With `memory=2GB` or less, Ollama cannot load the model and will fail with HTTP 500.

---

## Contributing

ChemTrace is an early-stage OSS project. Contributions are welcome.

→ Open an issue to discuss a bug or feature before submitting a PR.
→ Follow the existing code style (type hints, docstrings, no hardcoded values).
→ All PRs must pass `pytest tests/` (73 unit tests + 2 integration tests).
→ New parsers: add regex patterns to `src/chemtrace/parser_patterns.py`.
→ New emission factors: add entries to `data/emission_factors/factors.json` with source citation.

---

## License

MIT License. See [LICENSE](LICENSE) for full text.
Copyright (c) 2026 Sebastian Damiani Wolf.
