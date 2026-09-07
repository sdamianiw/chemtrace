# ChemTrace OSS

Open-source Scope 1-2 carbon accounting pipeline for German industrial SMEs facing CSRD 2026-2027 compliance. Python 3.11 + pdfplumber + ChromaDB + Ollama (llama3.2:3b) + sentence-transformers. Repo `C:\Chemtrace`, Windows 11, Cursor + Claude Code.

Behavioral guidelines are global (`~/.claude/CLAUDE.md` + the `karpathy-guidelines` / `plan-preflight` skills) and not repeated here. Below is what only this project knows.

## Hard constraints
Zero cloud dependencies (no Azure, no paid APIs) · Ollama-only LLM · Docker deployment · no n8n/Supabase · digital-native PDFs only, no OCR. 8-10h/week budget, so scope prioritization is ruthless.

## Session protocol
1. Read `.memory/session_log.md` (where we left off) and `.memory/lessons.md` (past mistakes).
2. Read the `.specs/` files for the current phase. Never code blind.
3. At session end: overwrite `session_log.md`, append new lessons and decisions, then `git add .memory/ && git commit -m "memory: session update"`.

## Autonomy contract
Execute without asking: reading files, running tests/python/git status-diff-log, creating or editing files inside the current task's constraints, fixing bugs found during verification, running verification/grep/lint/type checks.

STOP and ask for exactly these five: (1) architectural change, meaning a new module, new dependency, or interface change · (2) rewriting more than 50 lines of existing code · (3) touching 3+ files outside the task constraints · (4) installing dependencies · (5) modifying `.specs/` or `.skills/`.

Everything else: execute, log, continue.

## Project rules (HARD)
- Apply `.skills/CODE_VERIFIER.md` after any code execution, before commit. If it finds something, fix it without asking and log the fix in `.memory/lessons.md`.
- **ParseResult wrapper:** a parser never throws. It always returns a structured result.
- No hardcoded values: config via `.env` or constants with a source citation.
- One task = one commit; `git status` clean after every block.
- `PYTHONPATH="C:\Chemtrace\src"` prefixes every python/pytest call (`pip install -e .` fails on this machine).
- Never print non-ASCII in CLI output: Windows cp1252 crashes on `→`, `✓` and friends.
- `/clear` (not `/exit`) for fresh context. Above ~40% context: stop, commit, new session.

## Structure
`.specs/` REQUIREMENTS + ARCHITECTURE + phase plans (READ-ONLY) · `.skills/` PROMPT_CONTRACT + CODE_VERIFIER (apply autonomously) · `.memory/` lessons, decisions, session_log (read + write every session) · `src/chemtrace/` source · `data/` sample_invoices + emission_factors + sample_sap · `tests/` pytest.

## State
Shipped through **v0.6.0-vsme-export**; last commit 2026-04-03, so the repo has been dormant. Check `git log` before trusting any status note. Phase 04's remaining work was non-code signal work (outreach, Chemspec Europe registration).
