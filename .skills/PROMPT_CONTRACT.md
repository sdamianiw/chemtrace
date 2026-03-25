# PROMPT CONTRACT — ChemTrace

## Purpose
Enforce structured prompts for every Claude Code task. Prevents lazy/ambiguous execution.
This skill is referenced in CLAUDE.md. Apply it before executing any non-trivial task.

---

## Before ANY task, Claude Code must receive:

### GOAL (1 line)
What exactly should change after this task is done?

### CONSTRAINTS
→ Which files can be touched (whitelist)
→ Which files must NOT be touched
→ Max lines of code changed (estimate)

### FAILURE MODES
→ What breaks if this is done wrong?
→ What downstream modules depend on this?
→ What edge cases could cause silent failures?

### OUTPUT FORMAT
→ Expected file changes (list with paths)
→ Expected test results (which tests pass/fail)
→ Expected CLI behavior after change

### VERIFICATION
→ Exact commands to run to confirm success
→ What to grep/check after completion
→ Expected output values (test oracle)

---

## Rules

1. If ANY section above is missing from the prompt → ASK before executing. Never guess.
2. If the goal is ambiguous → request clarification. "Make it work" is not a goal.
3. If constraints are missing → assume MINIMAL IMPACT (touch only what's necessary).
4. Always read referenced .specs/ files BEFORE writing code.
5. Always run verification commands AFTER writing code.
6. If verification fails → STOP. Do not add patches on top of patches. Re-analyze root cause.

---

## Anti-patterns (NEVER do these)

→ "I'll just quickly fix this" without reading existing code first
→ Modifying files not in the whitelist without asking
→ Skipping verification because "it should work"
→ Adding TODO/FIXME without logging it in the commit message
→ Catching exceptions with bare `except:` and swallowing errors
→ Using hardcoded values "just for now"
