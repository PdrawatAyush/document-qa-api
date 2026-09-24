"""Answer generation via the Anthropic API, grounded in retrieved chunks."""
from typing import List

from app.core.config import settings
from app.schemas.schemas import RetrievedChunk


class LLMNotConfiguredError(Exception):
    """Raised when ANTHROPIC_API_KEY is not set."""


def _build_prompt(question: str, chunks: List[RetrievedChunk]) -> str:
    context_blocks = []
    for i, c in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] (document: {c.document_filename}, chunk: {c.chunk_index})\n{c.text}"
        )
    context = "\n\n".join(context_blocks)

    return (
        "You are a helpful assistant answering questions using ONLY the "
        "provided context excerpts. Each excerpt is numbered like [1], [2], etc.\n\n"
        "Rules:\n"
        "- Answer using only information in the context below.\n"
        "- If the context does not contain the answer, say you don't know.\n"
        "- Cite the excerpt number(s) you used, e.g. \"(see [1])\", inline in your answer.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def generate_answer(question: str, chunks: List[RetrievedChunk]) -> str:
    """Calls the Anthropic API to synthesize an answer from retrieved chunks.

    Raises LLMNotConfiguredError if no API key is set, so the caller (the
    router) can return a clear 503 instead of crashing.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise LLMNotConfiguredError(
            "ANTHROPIC_API_KEY is not set. Generation is unavailable; "
            "retrieval-only endpoints still work."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    prompt = _build_prompt(question, chunks)

    message = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
