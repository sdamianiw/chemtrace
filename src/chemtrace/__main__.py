"""ChemTrace CLI entry point: python -m chemtrace <command>"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m chemtrace <command>")
        print("Commands: parse, status")
        sys.exit(1)

    command = sys.argv[1]

    if command == "parse":
        _cmd_parse()
    elif command == "status":
        _cmd_status()
    else:
        print(f"Unknown command: '{command}'. Available: parse, status")
        sys.exit(1)


def _cmd_parse() -> None:
    from chemtrace.config import Config
    from chemtrace.etl import run_pipeline

    config = Config()
    if len(sys.argv) > 2:
        config.input_dir = Path(sys.argv[2])

    if not config.input_dir.exists():
        print(f"ERROR: directory not found: {config.input_dir}")
        sys.exit(1)

    result = run_pipeline(config)

    print(f"\nPipeline complete:")
    print(f"  Total files : {result.total_files}")
    print(f"  Successful  : {result.successful}")
    print(f"  Failed      : {result.failed}")
    if result.csv_path:
        print(f"  CSV output  : {result.csv_path}")
    if result.errors:
        print(f"  Errors      : {result.failed} (see {config.output_dir / 'errors.csv'})")
    if result.successful:
        # Print per-record summary
        print()
        for rec in result.records:
            em = rec.get("emissions_tco2")
            em_str = f"{em:.3f} tCO2e" if em is not None else "n/a"
            print(
                f"  [{rec['filename']}]"
                f"  {rec['energy_type'] or '?'}"
                f"  {rec['consumption_kwh']:,.0f} kWh"
                f"  {rec['total_eur'] or '?'} EUR"
                f"  -> {em_str}"
            )


def _cmd_status() -> None:
    from chemtrace.config import Config
    from chemtrace.vector_store import VectorStore

    config = Config()
    if not config.chroma_dir.exists():
        print("ChromaDB: not initialized (run 'parse' first)")
        return

    store = VectorStore(config)
    info = store.health()
    print(f"ChromaDB status : {info['status']}")
    print(f"  Collection    : {info['collection']}")
    print(f"  Documents     : {info['count']}")


if __name__ == "__main__":
    main()
