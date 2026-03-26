"""Unit tests for vector_store.VectorStore using synthetic records + tmp dirs.

No real PDFs. No writes to project chroma_db/ directory.
"""

from __future__ import annotations

import hashlib

import pytest

from chemtrace.config import Config
from chemtrace.vector_store import VectorStore


def _fake_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


SAMPLE_RECORDS = [
    {
        "pdf_hash": _fake_hash("invoice_elec_1"),
        "filename": "Invoice_Electricity_Jan2024.pdf",
        "content": "Invoice for site Essen plant covers Jan 2024 for electricity energy. "
                   "Energy amount is 478800 kWh. Total cost is 116461.40 EUR.",
        "site": "Essen",
        "energy_type": "electricity",
        "billing_period_from": "2024-01-01",
        "billing_period_to": "2024-01-31",
        "consumption_kwh": 478800.0,
        "total_eur": 116461.40,
        "emissions_tco2": 181.944,
        "currency": "EUR",
        "invoice_number": "INV-2024-001",
        "vendor_name": "TestGridCo",
    },
    {
        "pdf_hash": _fake_hash("invoice_gas_1"),
        "filename": "Invoice_NaturalGas_Jan2024.pdf",
        "content": "Invoice for site Essen plant covers Jan 2024 for natural_gas energy. "
                   "Energy amount is 310800 kWh. Total cost is 26925.23 EUR.",
        "site": "Essen",
        "energy_type": "natural_gas",
        "billing_period_from": "2024-01-01",
        "billing_period_to": "2024-01-31",
        "consumption_kwh": 310800.0,
        "total_eur": 26925.23,
        "emissions_tco2": 62.782,
        "currency": "EUR",
        "invoice_number": "INV-GAS-2024-001",
        "vendor_name": "TestGasCo",
    },
]


@pytest.fixture
def tmp_config(tmp_path):
    cfg = Config()
    cfg.chroma_dir = tmp_path / "chroma_test"
    return cfg


@pytest.fixture
def store(tmp_config):
    return VectorStore(tmp_config)


def test_upsert_and_count(store):
    store.upsert(SAMPLE_RECORDS)
    assert store.count() == 2


def test_upsert_dedup(store):
    """Upserting same records twice must not create duplicates."""
    store.upsert(SAMPLE_RECORDS)
    store.upsert(SAMPLE_RECORDS)
    assert store.count() == 2


def test_empty_upsert(store):
    n = store.upsert([])
    assert n == 0
    assert store.count() == 0


def test_query_returns_results(store):
    store.upsert(SAMPLE_RECORDS)
    results = store.query("electricity consumption kWh")
    assert len(results) > 0
    assert "id" in results[0]
    assert "document" in results[0]
    assert "metadata" in results[0]


def test_query_empty_store(store):
    results = store.query("electricity")
    assert results == []


def test_health_returns_ok(store):
    info = store.health()
    assert info["status"] == "ok"
    assert "count" in info
    assert "collection" in info


def test_delete_all(store):
    store.upsert(SAMPLE_RECORDS)
    assert store.count() == 2
    store.delete_all()
    assert store.count() == 0


def test_query_with_filter(store):
    """Filter by energy_type metadata returns only matching documents."""
    store.upsert(SAMPLE_RECORDS)
    results = store.query(
        "energy consumption",
        filters={"energy_type": {"$eq": "electricity"}},
    )
    assert len(results) >= 1
    for r in results:
        assert r["metadata"]["energy_type"] == "electricity"
