"""Unit and integration tests for RAG client and prompt templates.

Unit tests mock HTTP calls -- no Ollama needed.
Integration tests require a running Ollama instance at localhost:11434.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from chemtrace.config import Config
from chemtrace.prompts import SYSTEM_PROMPT, build_user_message, format_context
from chemtrace.rag_client import RAGResponse, ask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ollama_available() -> bool:
    """Return True if Ollama is reachable at localhost:11434."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _make_doc(filename: str, content: str, site: str = "TestSite") -> dict:
    """Helper to build a document dict matching VectorStore.query() output."""
    return {
        "id": f"hash_{filename}",
        "document": content,
        "metadata": {
            "filename": filename,
            "site": site,
            "billing_period_from": "2024-01-01",
            "billing_period_to": "2024-01-31",
            "energy_type": "electricity",
        },
        "distance": 0.3,
    }


_SAMPLE_DOCS = [_make_doc("Invoice_Elec_Jan.pdf", "Electricity consumption 478800 kWh for Jan 2024.")]

# Synthetic records for integration tests (matching VectorStore.upsert() input)
_INTEGRATION_RECORDS = [
    {
        "pdf_hash": "abc123",
        "filename": "Invoice_Electricity_Jan2024.pdf",
        "site": "Essen",
        "vendor_name": "RuhrChem GmbH",
        "customer_name": "Chemtrace GmbH",
        "invoice_number": "INV-2024-001",
        "invoice_date": "2024-02-01",
        "billing_period_from": "2024-01-01",
        "billing_period_to": "2024-01-31",
        "energy_type": "electricity",
        "consumption_kwh": 478800.0,
        "consumption_unit": "kWh",
        "total_eur": 95760.0,
        "currency": "EUR",
        "content": "Electricity consumption 478800 kWh for January 2024.",
    },
]


# ---------------------------------------------------------------------------
# Unit tests -- no Ollama needed
# ---------------------------------------------------------------------------

def test_ask_with_mocked_ollama():
    """Full ask() with mocked HTTP returns valid RAGResponse with answer + sources."""
    config = Config()
    store = MagicMock()
    store.count.return_value = 2
    store.query.return_value = _SAMPLE_DOCS

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": "The electricity consumption was 478800 kWh."},
        "eval_count": 50,
        "prompt_eval_count": 100,
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("chemtrace.rag_client.requests.post", return_value=mock_resp):
        result = ask("What was electricity consumption?", config, store)

    assert isinstance(result, RAGResponse)
    assert "478800" in result.answer
    assert result.tokens_used == 150
    assert len(result.sources) == 1
    assert result.sources[0]["filename"] == "Invoice_Elec_Jan.pdf"
    assert result.model == config.ollama_model


def test_ask_connection_error():
    """ConnectionError from Ollama returns Error: message in RAGResponse."""
    config = Config()
    store = MagicMock()
    store.count.return_value = 1
    store.query.return_value = _SAMPLE_DOCS

    with patch(
        "chemtrace.rag_client.requests.post",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = ask("test?", config, store)

    assert result.answer.startswith("Error:")
    assert "Ollama" in result.answer or "connect" in result.answer.lower()
    assert result.tokens_used is None


def test_ask_timeout():
    """Timeout from Ollama returns timeout Error: message in RAGResponse."""
    config = Config()
    store = MagicMock()
    store.count.return_value = 1
    store.query.return_value = _SAMPLE_DOCS

    with patch(
        "chemtrace.rag_client.requests.post",
        side_effect=requests.exceptions.Timeout,
    ):
        result = ask("test?", config, store)

    assert result.answer.startswith("Error:")
    assert "timed out" in result.answer.lower() or "timeout" in result.answer.lower()
    assert result.tokens_used is None


def test_ask_empty_store():
    """Empty vector store (count=0) returns 'no documents' message without Ollama call."""
    config = Config()
    store = MagicMock()
    store.count.return_value = 0

    result = ask("What was consumption?", config, store)

    assert "no documents" in result.answer.lower() or "No documents" in result.answer
    store.query.assert_not_called()  # Ollama must not be called


def test_format_context_single_doc():
    """Single document is formatted with correct header and metadata."""
    docs = [_make_doc("inv.pdf", "Some invoice content.")]
    result = format_context(docs)

    assert "DOCUMENT 1" in result
    assert "inv.pdf" in result
    assert "TestSite" in result
    assert "Some invoice content." in result
    assert "DOCUMENT 2" not in result


def test_format_context_multiple_docs():
    """Multiple documents get sequential numbering."""
    docs = [_make_doc(f"doc{i}.pdf", f"Content {i}") for i in range(1, 4)]
    result = format_context(docs)

    assert "DOCUMENT 1" in result
    assert "DOCUMENT 2" in result
    assert "DOCUMENT 3" in result
    assert "doc1.pdf" in result
    assert "doc2.pdf" in result
    assert "doc3.pdf" in result


def test_system_prompt_contains_rules():
    """SYSTEM_PROMPT contains required instruction phrases."""
    assert "ONLY answer using the CONTEXT" in SYSTEM_PROMPT
    assert "cite your source" in SYSTEM_PROMPT
    assert "SAFETY" in SYSTEM_PROMPT
    assert "No outside knowledge" in SYSTEM_PROMPT


def test_build_user_message():
    """build_user_message combines context and question with correct structure."""
    msg = build_user_message("How much kWh?", "=== DOCUMENT 1 ===\ncontent")

    assert "CONTEXT:" in msg
    assert "QUESTION: How much kWh?" in msg
    assert "=== DOCUMENT 1 ===" in msg


# ---------------------------------------------------------------------------
# Integration tests -- require Ollama running at localhost:11434
# ---------------------------------------------------------------------------

skip_no_ollama = pytest.mark.skipif(
    not _ollama_available(),
    reason="Ollama not running at localhost:11434",
)


@skip_no_ollama
def test_integration_factual_question(tmp_path):
    """Real Ollama query about indexed data returns grounded answer."""
    from chemtrace.vector_store import VectorStore

    cfg = Config()
    cfg.chroma_dir = tmp_path / "chroma"
    store = VectorStore(cfg)
    store.upsert(_INTEGRATION_RECORDS)

    result = ask("What was the electricity consumption in January 2024?", cfg, store)

    assert result.answer
    assert not result.answer.startswith("Error:")
    assert result.sources


@skip_no_ollama
def test_integration_offtopic_refusal(tmp_path):
    """Off-topic question triggers refusal per system prompt rules."""
    from chemtrace.vector_store import VectorStore

    cfg = Config()
    cfg.chroma_dir = tmp_path / "chroma"
    store = VectorStore(cfg)
    store.upsert(_INTEGRATION_RECORDS)

    result = ask("What is the capital of France?", cfg, store)

    assert result.answer
    assert "cannot answer" in result.answer.lower()
