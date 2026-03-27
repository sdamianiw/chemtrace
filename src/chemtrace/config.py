"""Configuration: Config dataclass, EmissionFactor, and factors.json loader."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root: src/chemtrace/config.py → up 3 levels
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class EmissionFactor:
    value: float       # tCO2e per unit
    unit: str          # "tCO2e/kWh" or "tCO2e/litre"
    source: str
    year: int
    note: str = ""


@dataclass
class Config:
    # Paths
    input_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data" / "sample_invoices")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    chroma_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "chroma_db")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: int = 60

    # RAG
    rag_top_k: int = 4
    rag_temperature: float = 0.2
    rag_max_tokens: int = 555

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    def __post_init__(self) -> None:
        # Override defaults with environment variables if set
        if v := os.getenv("CHEMTRACE_INPUT_DIR"):
            self.input_dir = Path(v)
        if v := os.getenv("CHEMTRACE_OUTPUT_DIR"):
            self.output_dir = Path(v)
        if v := os.getenv("CHEMTRACE_CHROMA_DIR"):
            self.chroma_dir = Path(v)
        if v := os.getenv("OLLAMA_BASE_URL"):
            self.ollama_base_url = v
        if v := os.getenv("OLLAMA_MODEL"):
            self.ollama_model = v
        if v := os.getenv("OLLAMA_TIMEOUT"):
            self.ollama_timeout = int(v)
        if v := os.getenv("RAG_TOP_K"):
            self.rag_top_k = int(v)
        if v := os.getenv("RAG_TEMPERATURE"):
            self.rag_temperature = float(v)
        if v := os.getenv("RAG_MAX_TOKENS"):
            self.rag_max_tokens = int(v)
        if v := os.getenv("EMBEDDING_MODEL"):
            self.embedding_model = v


def load_emission_factors(
    path: Path | None = None,
) -> dict[str, EmissionFactor]:
    """Load emission factors from factors.json. Returns empty dict + warning if file missing."""
    factors_path = path or (PROJECT_ROOT / "data" / "emission_factors" / "factors.json")
    if not factors_path.exists():
        logger.warning("Emission factors file not found: %s", factors_path)
        return {}
    try:
        raw: dict = json.loads(factors_path.read_text(encoding="utf-8"))
        return {
            name: EmissionFactor(
                value=float(entry["value"]),
                unit=str(entry["unit"]),
                source=str(entry["source"]),
                year=int(entry["year"]),
                note=str(entry.get("note", "")),
            )
            for name, entry in raw.items()
        }
    except Exception as exc:
        logger.warning("Failed to load emission factors: %s", exc)
        return {}
