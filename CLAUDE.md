# CLAUDE.md — ChemTrace OSS

## Project
Open-source Scope 1-3 carbon accounting pipeline. Python + pdfplumber + ChromaDB + Ollama.
Repo: C:\Chemtrace (/c/Chemtrace). Python 3.11+, Cursor + Claude Code (Max), Windows 11.

## Session Start Protocol
1. Read .memory/session_log.md → know where we left off
2. Read .memory/lessons.md → never repeat past mistakes
3. Read relevant .specs/ files for current phase
4. Begin work

## Autonomy Level
Execute autonomously. Do NOT ask permission for:
→ Reading any file, running tests, running python, git status/diff/log
→ Creating/editing files within scope of current task constraints
→ Fixing bugs found during verification (apply CODE_VERIFIER.md, fix, log lesson)
→ Running verification commands, grep, lint, type checks

STOP and ask ONLY for these 5 cases:
1. Architectural change (new module, new dependency, interface change)
2. Rewriting >50 lines of existing code
3. Touching 3+ files not listed in task constraints
4. Installing new dependencies (pip install, npm install)
5. Modifying .specs/ or .skills/ files

Everything else: execute → log → continue.
## Workflow Orchestration
→ Plan mode for 3+ step tasks. If sideways → STOP, re-plan.
→ One task = one commit. git status clean after every block.
→ After ANY code execution: apply .skills/CODE_VERIFIER.md autonomously before commit.
→ If CODE_VERIFIER finds issues: fix them immediately, do not ask. Log fix in .memory/lessons.md.
→ Use subagent thinking: break complex problems into independent verification steps.
## Self-Improvement Loop
→ After ANY error or correction: append to .memory/lessons.md immediately.
→ After ANY significant decision: append to .memory/decisions.md.
→ Pattern: Error → Root cause analysis → Create prevention rule → Apply rule going forward.
→ Review lessons at session start. If a rule prevented an error, note it.
→ Goal: recursive improvement. Error rate must decrease over sessions.
## Session End Protocol
1. Update .memory/session_log.md (overwrite with current session summary)
2. Append any new lessons to .memory/lessons.md
3. Append any new decisions to .memory/decisions.md
4. Commit memory files: git add .memory/ && git commit -m "memory: session update"

## Rules (HARD)
→ Before ANY task: read relevant .specs/ files. Never code blind.
→ Before touching any file: reason about root cause → minimal fix → downstream impact.
→ No hardcoded values. All config via .env or constants with source citation.
→ No temp fixes. Find root causes. Senior developer standards.
→ ParseResult wrapper: never throw from parser. Always return structured response.
→ /clear (not /exit) for fresh context. If context >40%: stop, commit, fresh session.

## Structure
→ .specs/ → REQUIREMENTS.md, ARCHITECTURE.md, phase plans (READ-ONLY)
→ .skills/ → PROMPT_CONTRACT.md, CODE_VERIFIER.md (apply autonomously)
→ .memory/ → lessons.md, decisions.md, session_log.md (READ + WRITE every session)
→ src/chemtrace/ → all source code
→ data/ → sample_invoices/, emission_factors/
→ tests/ → pytest suite
