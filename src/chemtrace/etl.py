"""ETL pipeline: batch-process PDF invoices → validated CSV + ChromaDB index.

Processing order enforces Bug #2 fix: parse ALL → validate → THEN save/index.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from chemtrace.config import Config, EmissionFactor, load_emission_factors
from chemtrace.pdf_parser import LineItem, parse_invoice
from chemtrace.utils import build_content, compute_pdf_hash
from chemtrace.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Maps parser energy_type → factors.json key.
# Add here when supporting new energy types.
ENERGY_TYPE_TO_EF_KEY: dict[str, str] = {
    "electricity": "electricity_de_grid_mix",
    "natural_gas": "natural_gas",
    "diesel": "diesel",
}


@dataclass
class PipelineResult:
    total_files: int
    successful: int
    failed: int
    records: list[dict]
    errors: list[dict]
    csv_path: Path | None


def run_pipeline(config: Config) -> PipelineResult:
    """Process all PDFs in input_dir. Validate → enrich → CSV → ChromaDB."""
    pdf_files = sorted(config.input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.info("No PDFs found in %s", config.input_dir)
        return PipelineResult(
            total_files=0, successful=0, failed=0,
            records=[], errors=[], csv_path=None,
        )

    factors = load_emission_factors()
    config.output_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    errors: list[dict] = []

    # Phase 1: parse + validate all files (no I/O writes yet)
    for pdf_path in pdf_files:
        result = parse_invoice(pdf_path)
        if not result.success:
            errors.append({
                "filename": pdf_path.name,
                "error_type": "parse_error",
                "message": result.error or "Unknown parse error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.warning("Parse failed [%s]: %s", pdf_path.name, result.error)
            continue

        record = _build_record(pdf_path, result.data, factors)
        records.append(record)
        logger.info("Parsed OK: %s", pdf_path.name)

    # Phase 2: export CSV (only after all parsing complete)
    csv_path: Path | None = None
    if records:
        df = pd.DataFrame(records)
        # Drop content from CSV: it's long and belongs in ChromaDB only
        csv_cols = [c for c in df.columns if c != "content"]
        csv_path = config.output_dir / "invoices.csv"
        df[csv_cols].to_csv(csv_path, index=False, float_format="%.4f")
        logger.info("Exported %d records → %s", len(records), csv_path)

        # Phase 3: upsert to ChromaDB (after CSV is safely written)
        store = VectorStore(config)
        store.upsert(records)
        logger.info("Upserted %d documents to ChromaDB", len(records))

    # Phase 4: log errors
    if errors:
        errors_path = config.output_dir / "errors.csv"
        pd.DataFrame(errors).to_csv(errors_path, index=False)
        logger.info("Logged %d errors → %s", len(errors), errors_path)

    return PipelineResult(
        total_files=len(pdf_files),
        successful=len(records),
        failed=len(errors),
        records=records,
        errors=errors,
        csv_path=csv_path,
    )


def _build_record(
    pdf_path: Path,
    data: dict,
    factors: dict[str, EmissionFactor],
) -> dict:
    """Enrich a parsed invoice data dict into a flat record for CSV + ChromaDB."""
    line_items: list[LineItem] = data.get("line_items") or []

    # Total consumption = sum of all line items
    consumption = sum(li.consumption_kwh or 0.0 for li in line_items)
    if consumption == 0.0 and line_items:
        logger.warning("All line items have null consumption in %s", pdf_path.name)

    # Consumption unit from first line item (H10 fix)
    consumption_unit: str = next(
        (li.consumption_unit for li in line_items if li.consumption_unit),
        "kWh",
    )

    # Primary energy type from first line item with a non-None type
    energy_type: str | None = next(
        (li.energy_type for li in line_items if li.energy_type),
        None,
    )
    if energy_type is None:
        logger.warning("No energy type in line items for %s", pdf_path.name)

    # Emission factor lookup
    ef_key = ENERGY_TYPE_TO_EF_KEY.get(energy_type or "")
    ef: EmissionFactor | None = factors.get(ef_key) if ef_key else None
    if ef is None and energy_type:
        logger.warning(
            "No emission factor for energy_type=%s (key=%s) in %s",
            energy_type, ef_key, pdf_path.name,
        )

    # Emission calculation: kWh (or litres) × EF = tCO2e
    emissions_tco2: float | None = (consumption * ef.value) if (ef and consumption) else None

    # Adapter dict matching build_content() expected keys (utils.py:36)
    period_str = (
        f"{data.get('billing_period_from', '?')} to {data.get('billing_period_to', '?')}"
    )
    content_input = {
        "blob_name": pdf_path.name,
        "site": data.get("site_address") or "unknown",
        "period": period_str,
        "energy_type": energy_type or "unknown",
        "energy_amount": consumption,
        "total_eur": data.get("total_amount") or "unknown",
        "currency": data.get("currency") or "EUR",
        "consumption_unit": consumption_unit,
    }

    return {
        "filename": pdf_path.name,
        "pdf_hash": compute_pdf_hash(pdf_path),
        "vendor_name": data.get("vendor_name"),
        "customer_name": data.get("customer_name"),
        "site": data.get("site_address"),
        "invoice_number": data.get("invoice_number"),
        "invoice_date": data.get("invoice_date"),
        "billing_period_from": data.get("billing_period_from"),
        "billing_period_to": data.get("billing_period_to"),
        "energy_type": energy_type,
        "consumption_kwh": consumption,
        "consumption_unit": consumption_unit,
        "total_eur": data.get("total_amount"),
        "currency": data.get("currency") or "EUR",
        "emissions_tco2": emissions_tco2,
        "emission_factor_value": ef.value if ef else None,
        "emission_factor_source": ef.source if ef else None,
        "content": build_content(content_input),
    }
