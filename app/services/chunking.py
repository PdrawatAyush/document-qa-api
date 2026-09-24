"""Text extraction and chunking utilities."""
import io
from typing import List

from pypdf import PdfReader


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
    """Split text into overlapping chunks, breaking on whitespace where possible.

    chunk_size / chunk_overlap are measured in characters. This keeps the
    dependency footprint small (no tokenizer needed) while still giving
    reasonably sized, context-preserving chunks for embedding.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks = []
    start = 0
    text_len = len(normalized)
    step = chunk_size - chunk_overlap

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break on a word boundary instead of mid-word, unless we're
        # already at the end of the text.
        if end < text_len:
            last_space = normalized.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start += step

    return chunks
