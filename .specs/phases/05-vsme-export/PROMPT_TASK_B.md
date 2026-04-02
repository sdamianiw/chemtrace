# PROMPT — PLAN-06 Task B: CLI + Docker + README + Tag
# Re-audited: 2026-04-02 s16 | Fixes: column names, test count, .dockerignore, .gitignore

```
ENVIRONMENT NOTE: Python imports require PYTHONPATH. Before running any python or pytest command, prefix with:
PYTHONPATH="C:\Chemtrace\src" python ...
PYTHONPATH="C:\Chemtrace\src" pytest ...

Before touching any file, reason step by step about:
1. What the root cause is
2. What the minimal change solves it
3. What could break downstream
Then apply the fix.

Read these files first:
→ src/chemtrace/cli.py (current _cmd_export, argparse setup)
→ src/chemtrace/vsme_export.py (export_vsme_b3 interface, VSMEExportResult dataclass)
→ src/chemtrace/config.py (Config, output_dir)
→ README.md (current structure)
→ .skills/PROMPT_CONTRACT.md

AUDIT CORRECTIONS (from fresh context, post Task A /clear):
→ vsme_export.py uses consumption_kwh (not energy_amount) and billing_period_from/billing_period_to (not period). These are the REAL CSV column names. Do NOT change vsme_export.py.
→ Current test count is 153 passed (18 VSME + 135 existing), not 147. Expect 153+ after Task B.
→ Check .dockerignore: verify data/vsme_templates/ is NOT excluded. If excluded, add exception.
→ Add output/*.xlsx to .gitignore if not already present.

GOAL: Wire VSME export into CLI. Docker e2e test. README update. Tag.

================================================================
TASK B1: Modify src/chemtrace/cli.py + config.py + .env.example
================================================================

Changes to argparse setup:
→ Add --format flag to export subcommand: choices=['csv', 'vsme'], default='csv'
→ Add --turnover flag to export subcommand: type=float, default=None, help='Annual turnover in EUR for GHG intensity calculation'

Changes to _cmd_export():
→ If args.format == 'csv': existing behavior (unchanged)
→ If args.format == 'vsme':
  1. Determine csv_path: config.output_dir / "invoices.csv"
  2. If not csv_path.exists(): print error, exit 1
  3. Determine template_path from config:
     Add to Config dataclass: vsme_template_path (with env var CHEMTRACE_VSME_TEMPLATE)
     Default: Path("data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx")
     This works in both local dev (CWD=C:\Chemtrace) and Docker (WORKDIR=/app)
     If path doesn't exist: print error, exit 1
  4. Determine output_path: args.output if provided, else config.output_dir / "vsme_report.xlsx"
  5. Call export_vsme_b3(csv_path, template_path, output_path, args.turnover)
  6. Print summary from VSMEExportResult
  7. If result.warnings: print each warning to stderr

Changes to config.py:
→ Add vsme_template_path field to Config dataclass
→ Default: Path(os.getenv("CHEMTRACE_VSME_TEMPLATE", "data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx"))

Changes to .env.example:
→ Add at end:
  # VSME Export
  # CHEMTRACE_VSME_TEMPLATE=data/vsme_templates/VSME-Digital-Template-1_2_0.xlsx

CONSTRAINTS:
→ Files to MODIFY: src/chemtrace/cli.py, src/chemtrace/config.py, .env.example
→ Files NOT to touch: vsme_export.py (already done in Task A), etl.py
→ Backward compatibility: `chemtrace export --output x.csv` must still work identically

================================================================
TASK B2: Update README.md
================================================================

Add VSME export section. Surgical edits (same approach as SAP CSV README update):

Edit 1: In "What is ChemTrace?" paragraph → add "exports to EFRAG VSME format"
Edit 2: New section "VSME Export" after existing export docs:
  ### VSME Export (EFRAG Digital Template)
  ChemTrace can export energy and emissions data to the official EFRAG VSME
  Digital Template (v1.2.0). This fills Disclosure B3 (Energy and GHG Emissions)
  for CSRD/VSME compliance reporting.

  Docker:
  docker compose run --rm chemtrace export --format vsme --output output/vsme_report.xlsx
  docker compose run --rm chemtrace export --format vsme --output output/vsme_report.xlsx --turnover 5000000

  Local:
  chemtrace export --format vsme --output vsme_report.xlsx --turnover 5000000

  The exported XLSX can be uploaded to EFRAG's online XBRL converter
  (https://xbrl.efrag.org/convert/) for machine-readable reporting.

Edit 3: DE Schnellstart section → add equivalent German text

================================================================
TASK B3: Check .dockerignore + .gitignore (AUDIT ITEMS)
================================================================

CHECK 1 (.dockerignore):
→ Run: grep "data" .dockerignore
→ If data/ is excluded but data/vsme_templates/ is NOT excepted:
  Add: !data/vsme_templates/
→ Template MUST be inside Docker image for export to work.

CHECK 2 (.gitignore):
→ Run: grep "xlsx" .gitignore
→ If output/*.xlsx is NOT present:
  Add: output/*.xlsx
→ Prevents accidentally committing generated VSME reports.

================================================================
TASK B4: Run tests
================================================================

  PYTHONPATH="C:\Chemtrace\src" pytest tests/ -v
  Expected: 153+ tests, 0 failures (18 VSME + 135 existing)

After completion, apply .skills/CODE_VERIFIER.md protocol.
```
