# Lessons — ChemTrace OSS
## Self-Improvement Log: errors → root cause → rule → prevention
## Protocol: After ANY correction or error, append a new entry. Consolidate when >30 entries.

| # | Date | Error | Root Cause | Rule Created | Applied In |
|---|------|-------|-----------|-------------|-----------|
| L-001 | 2026-03-24 | System initialized | N/A | Read .memory/lessons.md at session start | All sessions |
| L-002 | 2026-03-26 | UnicodeEncodeError on Windows cp1252 for → (U+2192) in print() output | Windows console uses cp1252 by default; non-ASCII chars in f-strings cause encode error at print time | Never use Unicode arrows/symbols in CLI print() output; use ASCII alternatives (-> instead of →, => instead of ⇒) | __main__.py, all CLI output |
