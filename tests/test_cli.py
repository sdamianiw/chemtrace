"""Tests for CLI argparse interface."""

from __future__ import annotations

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


def test_ask_stub(capsys):
    """ask command prints Phase 02 stub message."""
    main(["ask", "What was electricity consumption?"])
    captured = capsys.readouterr()
    assert "Phase 02" in captured.out
    assert "not implemented" in captured.out.lower()


def test_parse_missing_dir(capsys):
    """parse with nonexistent dir exits with error."""
    with pytest.raises(SystemExit):
        main(["parse", "--input-dir", "/nonexistent/path/xyz"])


def test_help_flag(capsys):
    """--help prints usage and exits."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
