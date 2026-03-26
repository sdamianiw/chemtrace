"""Integration tests for etl.run_pipeline() using real PDFs + tmp dirs.

All tests use isolated tmp_path for output_dir and chroma_dir.
The project's chroma_db/ and output/ directories are NEVER written during tests.

Expected emission values (kWh × EF):
  Electricity Jan: 478,800 × 0.000380 = 181.944 tCO2e
  Electricity Mar: 453,100 × 0.000380 = 172.178 tCO2e
  NaturalGas  Jan: 310,800 × 0.000202 =  62.782 tCO2e
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from chemtrace.config import Config
from chemtrace.etl import run_pipeline
from chemtrace.vector_store import VectorStore

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_invoices"


@pytest.fixture
def tmp_config(tmp_path):
    cfg = Config()
    cfg.input_dir = DATA_DIR
    cfg.output_dir = tmp_path / "output"
    cfg.chroma_dir = tmp_path / "chroma"
    return cfg


@pytest.fixture
def pipeline_result(tmp_config):
    return run_pipeline(tmp_config)


def test_pipeline_processes_all_files(pipeline_result):
    """4 PDFs total: 3 invoices pass, 1 ESG report fails."""
    assert pipeline_result.total_files == 4
    assert pipeline_result.successful == 3
    assert pipeline_result.failed == 1
    assert len(pipeline_result.records) == 3
    assert len(pipeline_result.errors) == 1


def test_pipeline_csv_exists(pipeline_result, tmp_config):
    assert pipeline_result.csv_path is not None
    assert pipeline_result.csv_path.exists()


def test_pipeline_csv_has_correct_rows(pipeline_result):
    df = pd.read_csv(pipeline_result.csv_path)
    assert len(df) == 3


def test_pipeline_csv_has_emissions_column(pipeline_result):
    df = pd.read_csv(pipeline_result.csv_path)
    assert "emissions_tco2" in df.columns
    assert (df["emissions_tco2"] > 0).all()


def test_pipeline_csv_no_content_column(pipeline_result):
    """content column is for ChromaDB only, must not be in CSV."""
    df = pd.read_csv(pipeline_result.csv_path)
    assert "content" not in df.columns


def test_pipeline_emission_electricity_jan(pipeline_result):
    records = pipeline_result.records
    # Jan electricity: 478,800 kWh × 0.000380 = 181.944 tCO2e
    jan = next(
        r for r in records
        if "Jan2024" in r["filename"] and r.get("energy_type") == "electricity"
    )
    assert jan["emissions_tco2"] == pytest.approx(181.944, abs=0.01)


def test_pipeline_emission_natural_gas(pipeline_result):
    records = pipeline_result.records
    # Natural gas: 310,800 kWh × 0.000202 = 62.782 tCO2e
    gas = next(r for r in records if r.get("energy_type") == "natural_gas")
    assert gas["emissions_tco2"] == pytest.approx(62.782, abs=0.01)


def test_pipeline_errors_csv_exists(pipeline_result, tmp_config):
    errors_csv = tmp_config.output_dir / "errors.csv"
    assert errors_csv.exists()
    df = pd.read_csv(errors_csv)
    assert len(df) == 1
    assert "filename" in df.columns
    assert "message" in df.columns


def test_pipeline_chromadb_count(pipeline_result, tmp_config):
    store = VectorStore(tmp_config)
    assert store.count() == 3


def test_pipeline_idempotent(tmp_config):
    """Running pipeline twice must not create duplicate ChromaDB documents."""
    run_pipeline(tmp_config)
    run_pipeline(tmp_config)
    store = VectorStore(tmp_config)
    assert store.count() == 3
