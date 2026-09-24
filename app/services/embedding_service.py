"""Local embedding generation with sentence-transformers.

The model is loaded lazily (on first use) and cached, so importing this
module — and running the app/tests without ever calling embed_texts — does
not require downloading the model.
"""
from typing import List

from app.core.config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of strings, returning a list of float vectors."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(list(texts), convert_to_numpy=True, show_progress_bar=False)
    return vectors.tolist()


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
