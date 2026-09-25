"""Text extraction and chunking utilities."""
import io
from typing import List

import tiktoken
from pypdf import PdfReader

# cl100k_base is the encoding used by GPT-3.5/4-era OpenAI models. Anthropic
# doesn't publish a public tokenizer, so this is used as a stand-in purely to
# measure chunk size/overlap in "tokens" rather than raw characters -- it's
# not meant to exactly match Claude's tokenizer, just to give a much more
# accurate proxy for LLM context budgeting than character counts do.
_ENCODING_NAME = "cl100k_base"
_encoding = None


def _get_encoding():
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding(_ENCODING_NAME)
    return _encoding


def extract_text(filename: str, content_type: str, raw_bytes: bytes) -> str:
    """Extract plain text from an uploaded file's raw bytes.

    Supports .txt (decoded as UTF-8, falling back to latin-1) and .pdf
    (page text extracted with pypdf).
    """
    lower_name = (filename or "").lower()
    is_pdf = lower_name.endswith(".pdf") or content_type == "application/pdf"

    if is_pdf:
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages_text = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        return "\n".join(pages_text)

    # Treat everything else as plain text.
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin-1")


def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks, measured in tokens (via tiktoken's
    cl100k_base encoding) rather than characters, so chunk_size lines up with
    actual LLM context budgeting instead of being a rough character proxy.

    chunk_size / chunk_overlap are token counts. Each chunk is produced by
    slicing the token stream and decoding back to text, so chunk boundaries
    can fall mid-word (tokens don't align to whitespace) -- that's fine for
    embedding/retrieval purposes and is how most token-based chunkers work.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    encoding = _get_encoding()
    tokens = encoding.encode(normalized)
    total_tokens = len(tokens)
    if total_tokens == 0:
        return []

    chunks = []
    start = 0
    step = chunk_size - chunk_overlap

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)

        piece = encoding.decode(tokens[start:end]).strip()
        if piece:
            chunks.append(piece)

        # Once a chunk has reached the end of the token stream there is
        # nothing left to cover -- stop instead of sliding the window
        # forward again, which would otherwise emit a spurious tiny final
        # chunk that just duplicates the tail of the previous one (only
        # visible once the input is short enough that the *first* chunk
        # already reaches the end).
        if end >= total_tokens:
            break
        start += step

    return chunks
