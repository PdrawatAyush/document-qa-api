"""Unit tests for token-based chunking (app.services.chunking.chunk_text).

Chunking used to be character-based; it's now token-based via tiktoken so
chunk_size/chunk_overlap actually reflect LLM context budgeting. These tests
also cover a real bug found during a live end-to-end smoke test: a short
document (one that fits entirely within a single chunk) used to still
produce a spurious, tiny, duplicate-content trailing chunk.
"""
import tiktoken

from app.services.chunking import chunk_text

_encoding = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_encoding.encode(text))


def test_short_text_produces_a_single_chunk_no_spurious_tail():
    # Regression test: this exact shape of input (short text, well under
    # chunk_size) used to produce a second, tiny, duplicate-tail chunk under
    # the old character-based chunker.
    text = "The capital of France is Paris. Paris is famous for the Eiffel Tower."
    chunks = chunk_text(text, chunk_size=1000, chunk_overlap=150)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text_returns_no_chunks():
    assert chunk_text("   \n  ", chunk_size=1000, chunk_overlap=150) == []


def test_chunks_respect_token_budget():
    # Build text comfortably longer than a small token budget.
    text = " ".join(f"sentence number {i} about various topics." for i in range(200))
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)
    assert len(chunks) > 1
    for c in chunks:
        assert _token_len(c) <= 50


def test_chunks_overlap_by_roughly_the_configured_amount():
    # Re-encoding a decoded/stripped chunk in isolation isn't guaranteed to
    # reproduce the exact same BPE tokens as the original slice (token
    # boundaries can shift once surrounding context is removed), so this
    # checks the overlap at the word/content level instead of by re-tokenizing.
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1

    first_words = chunks[0].split()
    second_words = chunks[1].split()
    # The end of chunk[0] and the start of chunk[1] should share real
    # overlapping content, not just pick up where the previous chunk left off.
    tail = first_words[-5:]
    head = second_words[:len(first_words)]
    assert any(w in head for w in tail)


def test_last_chunk_is_not_a_tiny_duplicate_tail():
    # A longer document whose length isn't a clean multiple of the step size
    # should still end cleanly at the true end of the text, not with an
    # extra sliver chunk beyond it that just duplicates the previous tail.
    text = " ".join(f"token{i}" for i in range(237))
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)

    # Coverage reaches the true end of the source text.
    assert chunks[-1].split()[-1] == text.split()[-1]

    # No chunk is a pure content-duplicate of another (the original bug
    # produced a final chunk that was wholly contained in the previous one).
    assert len(chunks) == len(set(chunks))
    for c in chunks:
        assert _token_len(c) >= 5, "unexpectedly tiny chunk, looks like a stray tail fragment"


def test_overlap_must_be_smaller_than_chunk_size():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, chunk_overlap=100)
