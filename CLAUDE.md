# CLAUDE.md — ChemTrace OSS

## Project
Open-source Scope 1-3 carbon accounting pipeline. Python + pdfplumber + ChromaDB + Ollama.

## Rules (HARD)
- Before ANY task: read relevant .specs/ files first. Never code blind.
- Before touching any file: reason about root cause → minimal fix → downstream impact.
- Plan mode for 3+ step tasks. If sideways → STOP, re-plan.
- One task = one commit. `git status` clean after every block.
- No hardcoded values. All config via .env or constants with source citation.
- No temp fixes. Find root causes. Senior developer standards.
- ParseResult wrapper: never throw from parser. Always return structured response.
- After execution: apply .skills/CODE_VERIFIER.md before commit.

## Structure
- `.specs/` → REQUIREMENTS.md, ARCHITECTURE.md, phase plans (read-only reference)
- `.skills/` → PROMPT_CONTRACT.md, CODE_VERIFIER.md (apply when instructed)
- `src/chemtrace/` → all source code (config, pdf_parser, etl, vector_store, rag_client, cli)
- `data/` → sample_invoices/ (PDFs), emission_factors/ (factors.json)
- `tests/` → pytest suite

## Dev Environment
- Path: C:\Chemtrace (/c/Chemtrace in Git Bash)
- Python 3.11+, Cursor + Claude Code (Max), Windows 11
- Docker Desktop for containerized deployment
- Ollama for local LLM inference (Phase 02+)

## Context Management
- /clear (not /exit) for fresh context
- If context >40%: stop, commit, fresh session
