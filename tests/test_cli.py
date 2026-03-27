"""Tests for CLI argparse interface."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from chemtrace.cli import main


def test_no_command_exits(capsys):
    """No command prints help and exits with code 1."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 1


def test_unknown_command_exits(capsys):
    """Unknown command exits with error."""
    with pytest.raises(SystemExit):
        main(["nonexistent_cmd"])


def test_ask_no_question(capsys):
    """ask with no question argument prints usage to stderr and exits 1."""
    with pytest.raises(SystemExit) as exc_info:
        main(["ask"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower() or "question" in captured.err.lower()


def test_ask_calls_rag(capsys):
    """ask command calls rag_client.ask and formats answer + sources + footer."""
    from chemtrace.rag_client import RAGResponse

    mock_response = RAGResponse(
        answer="Total electricity was 478800 kWh.",
        sources=[
            {"filename": "Invoice_Electricity_Jan2024.pdf"},
            {"filename": "Invoice_NaturalGas_Jan2024.pdf"},
            {"filename": "Invoice_Electricity_Jan2024.pdf"},  # duplicate -- should dedupe
        ],
        model="llama3.2:3b",
        tokens_used=150,
    )

    with patch("chemtrace.config.Config"), \
         patch("chemtrace.vector_store.VectorStore"), \
         patch("chemtrace.rag_client.ask", return_value=mock_response):
        main(["ask", "What was total electricity?"])

    captured = capsys.readouterr()
    assert "478800 kWh" in captured.out
    assert "Sources:" in captured.out
    assert "Invoice_Electricity_Jan2024.pdf" in captured.out
    assert "Invoice_NaturalGas_Jan2024.pdf" in captured.out
    assert captured.out.count("Invoice_Electricity_Jan2024.pdf") == 1  # deduplicated
    assert "Tokens: 150" in captured.out
    assert "llama3.2:3b" in captured.out
    assert "Thinking" in captured.err


def test_ask_error_response(capsys):
    """ask command with Error: response prints to stderr and exits 1."""
    from chemtrace.rag_client import RAGResponse

    mock_response = RAGResponse(
        answer="Error: Cannot connect to Ollama at http://localhost:11434.",
        sources=[],
        model="llama3.2:3b",
    )

    with patch("chemtrace.config.Config"), \
         patch("chemtrace.vector_store.VectorStore"), \
         patch("chemtrace.rag_client.ask", return_value=mock_response):
        with pytest.raises(SystemExit) as exc_info:
            main(["ask", "What was total electricity?"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert captured.out == ""  # nothing on stdout


def test_export_no_csv(capsys, tmp_path):
    """export with no CSV file prints error to stderr and exits 1."""
    with patch("chemtrace.config.Config") as MockConfig:
        mock_cfg = MagicMock()
        mock_cfg.output_dir = tmp_path  # tmp_path has no invoices.csv
        MockConfig.return_value = mock_cfg
        with pytest.raises(SystemExit) as exc_info:
            main(["export"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "chemtrace parse" in captured.err


def test_parse_missing_dir(capsys):
    """parse with nonexistent dir exits with error."""
    with pytest.raises(SystemExit):
        main(["parse", "--input-dir", "/nonexistent/path/xyz"])


def test_help_flag(capsys):
    """--help prints usage and exits."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
