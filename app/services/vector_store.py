"""ChromaDB-backed vector store for document chunks.

Each user's chunks are stored with owner_id / document_id metadata so that
queries can be filtered to a single user's documents, keeping data scoped
per-user at the retrieval layer as well as in SQL.
"""
from typing import List, Optional

import chromadb

from app.core.config import settings

_client = None
_collection = None

COLLECTION_NAME = "document_chunks"


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def add_chunks(
    chunk_ids: List[str],
    embeddings: List[List[float]],
    documents: List[str],
    metadatas: List[dict],
) -> None:
    collection = _get_collection()
    collection.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query(
    query_embedding: List[float],
    top_k: int,
    owner_id: str,
    document_id: Optional[str] = None,
) -> dict:
    collection = _get_collection()

    where: dict = {"owner_id": owner_id}
    if document_id:
        where = {"$and": [{"owner_id": owner_id}, {"document_id": document_id}]}

    # Chroma errors if asked for more results than exist in the collection.
    count = collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
        where=where,
    )


def delete_document_chunks(document_id: str) -> None:
    collection = _get_collection()
    collection.delete(where={"document_id": document_id})


def reset_collection() -> None:
    """Used by tests to get a clean collection between test runs."""
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = _client.get_or_create_collection(name=COLLECTION_NAME)
