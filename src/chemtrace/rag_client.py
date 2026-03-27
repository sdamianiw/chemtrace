"""RAG client: retrieve context from ChromaDB, generate answers via Ollama.

Full pipeline: question -> retrieve -> augment -> generate -> RAGResponse.
Uses pure HTTP requests to Ollama (no SDK dependency, per ARCHITECTURE.md D-11).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from chemtrace.config import Config
from chemtrace.prompts import SYSTEM_PROMPT, build_user_message, format_context
from chemtrace.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    """Structured response from the RAG pipeline."""

    answer: str
    sources: list[dict] = field(default_factory=list)
    model: str = ""
    tokens_used: int | None = None


def ask(question: str, config: Config, store: VectorStore) -> RAGResponse:
    """Full RAG pipeline: retrieve relevant docs, augment prompt, generate answer.

    Never raises exceptions. All error conditions return a RAGResponse with an
    informative error message in the answer field.

    Args:
        question: Natural language question about energy data.
        config: Application configuration (Ollama URL, model, RAG params).
        store: ChromaDB vector store with indexed invoice documents.

    Returns:
        RAGResponse with answer, sources, model name, and token count.
    """
    # Step 1: Check ChromaDB has data BEFORE calling Ollama (TD-06)
    try:
        doc_count = store.count()
    except Exception as exc:
        logger.warning("ChromaDB count error: %s", exc)
        return RAGResponse(
            answer="Error: Cannot access ChromaDB. Run: chemtrace parse",
            model=config.ollama_model,
        )

    if doc_count == 0:
        return RAGResponse(
            answer="No documents indexed. Run: chemtrace parse first.",
            model=config.ollama_model,
        )

    # Step 2: Retrieve relevant documents
    try:
        docs = store.query(question, top_k=config.rag_top_k)
    except Exception as exc:
        logger.warning("ChromaDB query error: %s", exc)
        return RAGResponse(
            answer="Error: ChromaDB query failed. Try: chemtrace parse",
            model=config.ollama_model,
        )

    if not docs:
        return RAGResponse(
            answer="No relevant documents found for your question.",
            sources=[],
            model=config.ollama_model,
        )

    # Step 3: Format context and build messages
    context = format_context(docs)
    user_message = build_user_message(question, context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Step 4: Call Ollama LLM
    answer, tokens_used = _call_ollama(messages, config)

    # Step 5: Extract sources from retrieved docs metadata
    sources = [
        {
            "filename": d.get("metadata", {}).get("filename", ""),
            "site": d.get("metadata", {}).get("site", ""),
            "energy_type": d.get("metadata", {}).get("energy_type", ""),
            "distance": d.get("distance"),
        }
        for d in docs
    ]

    return RAGResponse(
        answer=answer,
        sources=sources,
        model=config.ollama_model,
        tokens_used=tokens_used,
    )


def _call_ollama(
    messages: list[dict], config: Config
) -> tuple[str, int | None]:
    """Send chat completion request to Ollama HTTP API.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        config: Configuration with ollama_base_url, ollama_model, RAG params.

    Returns:
        Tuple of (answer_text, tokens_used_or_None). On any error, answer_text
        contains a user-friendly ASCII error message.
    """
    url = f"{config.ollama_base_url}/api/chat"
    payload = {
        "model": config.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": config.rag_temperature,
            "num_predict": config.rag_max_tokens,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=config.ollama_timeout)
    except requests.exceptions.ConnectionError:
        msg = (
            f"Error: Cannot connect to Ollama at {config.ollama_base_url}. "
            f"Is it running? Start with: ollama serve"
        )
        logger.warning(msg)
        return msg, None
    except requests.exceptions.Timeout:
        msg = (
            f"Error: Ollama request timed out after {config.ollama_timeout}s. "
            f"Try increasing OLLAMA_TIMEOUT or using a smaller model."
        )
        logger.warning(msg)
        return msg, None

    if resp.status_code == 404:
        msg = (
            f"Error: Model '{config.ollama_model}' not found. "
            f"Run: ollama pull {config.ollama_model}"
        )
        logger.warning(msg)
        return msg, None

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = f"Error: Ollama returned HTTP {resp.status_code}: {exc}"
        logger.warning(msg)
        return msg, None

    try:
        data = resp.json()
    except ValueError:
        msg = "Error: Ollama returned invalid JSON response."
        logger.warning(msg)
        return msg, None

    answer = data.get("message", {}).get("content", "").strip()
    if not answer:
        msg = "Error: Ollama returned an empty response. Try rephrasing your question."
        logger.warning(msg)
        return msg, None

    # Extract token counts from Ollama response (top-level fields)
    tokens_used: int | None = None
    eval_count = data.get("eval_count")
    prompt_eval_count = data.get("prompt_eval_count")
    if eval_count is not None and prompt_eval_count is not None:
        tokens_used = int(eval_count) + int(prompt_eval_count)

    return answer, tokens_used
