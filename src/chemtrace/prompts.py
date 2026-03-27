"""Prompt templates for ChemTrace RAG pipeline.

System prompt, context formatting, and user message construction
for Ollama LLM inference with llama3.2:3b (or any Ollama-compatible model).
"""

from __future__ import annotations


SYSTEM_PROMPT: str = (
    "You are ChemTrace, an energy data assistant for industrial carbon accounting.\n"
    "\n"
    "RULES (follow ALL strictly):\n"
    "1. ONLY answer using the CONTEXT documents provided below. Never use outside knowledge.\n"
    "2. ALWAYS cite your source by document name "
    "(e.g., \"Source: Invoice_Electricity_Jan2024_RuhrChem.pdf\").\n"
    "3. Include specific numbers (kWh, EUR, tCO2e) when available in the context.\n"
    "4. If the question CANNOT be answered from the provided context, respond EXACTLY:\n"
    "   \"I cannot answer this question based on the available energy data.\"\n"
    "5. Do NOT invent or estimate numbers. Only state what appears in the documents.\n"
    "6. Keep answers concise. For simple questions: 2-3 sentences. "
    "For comparisons: up to 5 sentences.\n"
    "\n"
    "SAFETY: Do not provide advice on illegal activities or generate harmful content.\n"
    "\n"
    "REMEMBER: Only use the CONTEXT below. No outside knowledge. No invented numbers."
)


def format_context(documents: list[dict]) -> str:
    """Format retrieved documents into structured context for LLM injection.

    Each document is wrapped with numbered delimiters and includes metadata
    headers (Source, Site, Period, Energy type) followed by the document content.

    Args:
        documents: List of dicts from VectorStore.query(), each with keys:
            'document' (str content), 'metadata' (dict with filename, site,
            billing_period_from, billing_period_to, energy_type).

    Returns:
        Formatted context string with clearly delimited document blocks.
        Returns empty string if documents list is empty.
    """
    if not documents:
        return ""

    blocks: list[str] = []
    for i, doc in enumerate(documents, start=1):
        meta = doc.get("metadata", {})
        filename = meta.get("filename", "unknown")
        site = meta.get("site", "unknown")
        period_from = meta.get("billing_period_from", "?")
        period_to = meta.get("billing_period_to", "?")
        energy_type = meta.get("energy_type", "unknown")
        content = doc.get("document", "")

        block = (
            f"=== DOCUMENT {i} ===\n"
            f"Source: {filename}\n"
            f"Site: {site}\n"
            f"Period: {period_from} to {period_to}\n"
            f"Energy type: {energy_type}\n"
            f"---\n"
            f"{content}\n"
            f"=================="
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def build_user_message(question: str, context: str) -> str:
    """Build the user message combining formatted context and the question.

    Args:
        question: The user's natural language question.
        context: Formatted context string from format_context().

    Returns:
        Combined message string for the LLM user role.
    """
    return f"CONTEXT:\n{context}\n\nQUESTION: {question}"
