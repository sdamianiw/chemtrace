"""Shared utilities: number cleaning, hashing, content generation."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any


def clean_number(value: Any) -> float | None:
    """Convert a string or number to float, handling comma thousands-separators.

    Returns None for None, empty, NaN, Inf, or non-numeric input. Never throws.
    All 3 invoice PDFs use English number format (comma = thousands, period = decimal).
    """
    if value is None:
        return None
    try:
        cleaned = str(value).strip().replace(",", "")
        if not cleaned:
            return None
        result = float(cleaned)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except (ValueError, TypeError):
        return None


def compute_pdf_hash(pdf_path: Path) -> str:
    """Return SHA-256 hex digest of a PDF file for audit trail / deduplication."""
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


def build_content(record: dict) -> str:
    """Generate a plain-text summary of an invoice record for ChromaDB content field.

    Ported from notebook cell 21 (build_content).
    """
    blob_name = record.get("blob_name", "unknown")
    site = record.get("site", "unknown")
    period = record.get("period", "unknown")
    energy_type = record.get("energy_type", "unknown")
    energy_amount = record.get("energy_amount", "unknown")
    total_eur = record.get("total_eur", "unknown")
    currency = record.get("currency", "EUR")
    return (
        f"Invoice {blob_name} for site {site} covers period {period} "
        f"for {energy_type} energy. Energy amount is {energy_amount} kWh. "
        f"Total cost is {total_eur} {currency}."
    )
