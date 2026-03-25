"""ChemTrace CLI entry point: python -m chemtrace <command>

Task 1: only 'parse' is implemented. Full CLI (argparse) comes in Task 3.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m chemtrace <command>")
        print("Commands: parse")
        sys.exit(1)

    command = sys.argv[1]

    if command == "parse":
        input_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/sample_invoices")
        if not input_dir.exists():
            print(f"ERROR: directory not found: {input_dir}")
            sys.exit(1)

        from chemtrace.pdf_parser import parse_invoice

        pdf_files = sorted(input_dir.glob("*.pdf"))
        if not pdf_files:
            print(f"No PDFs found in {input_dir}")
            sys.exit(0)

        for pdf_path in pdf_files:
            result = parse_invoice(pdf_path)
            status = "OK  " if result.success else "FAIL"
            print(f"[{status}] {pdf_path.name}")
            if result.warnings:
                for w in result.warnings:
                    print(f"       WARN: {w}")
            if result.error:
                print(f"       ERROR: {result.error}")
            if result.success and result.data:
                items = result.data.get("line_items", [])
                consumption = sum(li.consumption_kwh or 0.0 for li in items)
                print(
                    f"       invoice={result.data.get('invoice_number')} "
                    f"| total={result.data.get('total_amount')} EUR "
                    f"| consumption={consumption} kWh "
                    f"| items={len(items)}"
                )
    else:
        print(f"Unknown command: '{command}'. Available: parse")
        sys.exit(1)


if __name__ == "__main__":
    main()
