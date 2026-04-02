"""ChemTrace CLI -- argparse-based command interface.

Commands:
    chemtrace parse  [--input-dir PATH] [--output-dir PATH]
    chemtrace status
    chemtrace export [--output PATH] [--format csv|vsme] [--turnover EUR]
    chemtrace ask    "question"
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Entry point for the chemtrace CLI."""
    parser = argparse.ArgumentParser(
        prog="chemtrace",
        description="ChemTrace: Open-source Scope 1-3 carbon accounting pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # parse
    p_parse = subparsers.add_parser("parse", help="Parse invoices and run ETL pipeline")
    p_parse.add_argument(
        "--input-dir", type=Path, default=None,
        help="Input directory containing PDF invoices",
    )
    p_parse.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory for CSV files",
    )

    # status
    subparsers.add_parser("status", help="Show ChromaDB index status")

    # export
    p_export = subparsers.add_parser("export", help="Export invoice data to CSV")
    p_export.add_argument(
        "--output", type=Path, default=None,
        help="Output file path",
    )
    p_export.add_argument(
        "--format", choices=["csv", "vsme"], default="csv",
        help="Export format (default: csv)",
    )
    p_export.add_argument(
        "--turnover", type=float, default=None,
        help="Annual turnover in EUR for GHG intensity calculation",
    )

    # ask
    p_ask = subparsers.add_parser("ask", help="Ask a question about energy data")
    p_ask.add_argument("question", nargs="?", default=None, help="Natural language question")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "parse":
        _cmd_parse(args)
    elif args.command == "status":
        _cmd_status()
    elif args.command == "export":
        _cmd_export(args)
    elif args.command == "ask":
        _cmd_ask(args)


def _cmd_parse(args: argparse.Namespace) -> None:
    from chemtrace.config import Config
    from chemtrace.etl import run_pipeline

    config = Config()
    if args.input_dir is not None:
        config.input_dir = args.input_dir
    if args.output_dir is not None:
        config.output_dir = args.output_dir

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
        print()
        for rec in result.records:
            em = rec.get("emissions_tco2")
            em_str = f"{em:.3f} tCO2e" if em is not None else "n/a"
            unit = rec.get("consumption_unit", "kWh")
            print(
                f"  [{rec['filename']}]"
                f"  {rec['energy_type'] or '?'}"
                f"  {rec['consumption_kwh']:,.0f} {unit}"
                f"  {rec['total_eur'] or '?'} EUR"
                f"  -> {em_str}"
            )


def _cmd_status() -> None:
    from chemtrace.config import Config
    from chemtrace.vector_store import VectorStore

    config = Config()
    if not config.chroma_dir.exists():
        print("ChromaDB: not initialized (run 'chemtrace parse' first)")
        return

    try:
        store = VectorStore(config)
        info = store.health()
        print(f"ChromaDB status : {info['status']}")
        print(f"  Collection    : {info['collection']}")
        print(f"  Documents     : {info['count']}")
    except Exception as exc:
        print(f"ChromaDB error: {exc}")
        print("Try running 'chemtrace parse' first.")


def _cmd_export(args: argparse.Namespace) -> None:
    from chemtrace.config import Config

    config = Config()
    csv_path = config.output_dir / "invoices.csv"

    if not csv_path.exists():
        print("No data found. Run `chemtrace parse` first.", file=sys.stderr)
        sys.exit(1)

    if args.format == "vsme":
        _cmd_export_vsme(args, config, csv_path)
    else:
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(csv_path, args.output)
            print(f"Exported -> {args.output}")
        else:
            print(str(csv_path))


def _cmd_export_vsme(
    args: argparse.Namespace,
    config: "Config",
    csv_path: Path,
) -> None:
    from chemtrace.vsme_export import export_vsme_b3

    template_path = config.vsme_template_path
    if not template_path.exists():
        print(f"VSME template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output if args.output is not None else config.output_dir / "vsme_report.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = export_vsme_b3(csv_path, template_path, output_path, args.turnover)

    print(f"VSME B3 exported -> {result.output_path}")
    print(f"  Records   : {result.records_count}")
    print(f"  Period    : {result.period_start} to {result.period_end}")
    print(f"  Energy    : {result.total_energy_mwh:.2f} MWh")
    print(f"  Scope 1   : {result.scope1_tco2eq:.4f} tCO2eq")
    print(f"  Scope 2   : {result.scope2_tco2eq:.4f} tCO2eq")
    if result.turnover_eur is not None:
        print(f"  Turnover  : {result.turnover_eur:,.0f} EUR")

    for warning in result.warnings:
        print(f"  WARNING: {warning}", file=sys.stderr)


def _cmd_ask(args: argparse.Namespace) -> None:
    if args.question is None:
        print('Usage: chemtrace ask "your question here"', file=sys.stderr)
        sys.exit(1)

    from chemtrace.config import Config
    from chemtrace.rag_client import ask
    from chemtrace.vector_store import VectorStore

    config = Config()
    store = VectorStore(config)

    print("Thinking...", file=sys.stderr)
    response = ask(args.question, config, store)

    if response.answer.startswith("Error:"):
        print(response.answer, file=sys.stderr)
        sys.exit(1)

    print(response.answer)
    print()
    print("Sources:")
    seen: set[str] = set()
    for src in response.sources:
        fname = src.get("filename", "")
        if fname and fname not in seen:
            seen.add(fname)
            print(f"  - {fname}")

    if response.tokens_used:
        print(f"(Model: {response.model}, Tokens: {response.tokens_used})")
