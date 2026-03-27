"""ChromaDB vector store wrapper for ChemTrace invoice records."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from chemtrace.config import Config

logger = logging.getLogger(__name__)

COLLECTION_NAME = "chemtrace_invoices"


class VectorStore:
    """ChromaDB wrapper. Index records, query by semantic similarity + metadata filters."""

    def __init__(self, config: Config) -> None:
        self._client = chromadb.PersistentClient(path=str(config.chroma_dir))
        self._ef = SentenceTransformerEmbeddingFunction(
            model_name=config.embedding_model
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._ef,
        )

    def upsert(self, records: list[dict]) -> int:
        """Index/update records by pdf_hash. Returns count upserted."""
        if not records:
            return 0
        ids = [r["pdf_hash"] for r in records]
        documents = [r["content"] for r in records]
        metadatas = [_to_metadata(r) for r in records]
        self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(records)

    def query(
        self,
        question: str,
        top_k: int = 4,
        filters: dict | None = None,
    ) -> list[dict]:
        """Semantic search + optional metadata filter. Returns list of result dicts."""
        n_docs = self._collection.count()
        if n_docs == 0:
            return []
        kwargs: dict[str, Any] = {
            "query_texts": [question],
            "n_results": min(top_k, n_docs),
        }
        if filters:
            kwargs["where"] = filters
        result = self._collection.query(**kwargs)
        output = []
        for i, doc_id in enumerate(result["ids"][0]):
            output.append({
                "id": doc_id,
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i] if result.get("distances") else None,
            })
        return output

    def count(self) -> int:
        """Total indexed documents."""
        return self._collection.count()

    def health(self) -> dict:
        """ChromaDB status check."""
        return {
            "status": "ok",
            "collection": COLLECTION_NAME,
            "count": self._collection.count(),
        }

    def delete_all(self) -> None:
        """Reset index. Deletes and recreates the collection."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._ef,
        )


def _to_metadata(record: dict) -> dict:
    """Convert record dict to ChromaDB-safe metadata (no None values allowed)."""
    return {
        "filename": record.get("filename") or "",
        "site": record.get("site") or "",
        "energy_type": record.get("energy_type") or "",
        "billing_period_from": record.get("billing_period_from") or "",
        "billing_period_to": record.get("billing_period_to") or "",
        "consumption_kwh": float(record["consumption_kwh"]) if record.get("consumption_kwh") is not None else 0.0,
        "total_eur": float(record["total_eur"]) if record.get("total_eur") is not None else 0.0,
        "emissions_tco2": float(record["emissions_tco2"]) if record.get("emissions_tco2") is not None else 0.0,
        "currency": record.get("currency") or "EUR",
        "invoice_number": record.get("invoice_number") or "",
        "vendor_name": record.get("vendor_name") or "",
        "consumption_unit": record.get("consumption_unit") or "kWh",
    }
