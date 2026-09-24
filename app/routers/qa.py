"""Retrieval and generation (RAG) endpoints.

/qa/retrieve - embed the question, fetch the top-k most relevant chunks
    for the current user (optionally scoped to one document). No LLM call,
    no API key required.

/qa/ask - does the same retrieval, then sends the retrieved chunks to the
    Anthropic API to synthesize a cited answer. Returns 503 with a clear
    message if ANTHROPIC_API_KEY isn't configured, rather than crashing.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.models import Document, User
from app.schemas.schemas import (
    AnswerResponse,
    Citation,
    QuestionRequest,
    RetrievalResponse,
    RetrievedChunk,
)
from app.services import vector_store
from app.services.auth_service import get_current_user
from app.services.embedding_service import embed_query
from app.services.llm_service import LLMNotConfiguredError, generate_answer

router = APIRouter(prefix="/qa", tags=["qa"])


def _retrieve(payload: QuestionRequest, db: Session, current_user: User) -> list[RetrievedChunk]:
    if payload.document_id:
        owned = (
            db.query(Document)
            .filter(Document.id == payload.document_id, Document.owner_id == current_user.id)
            .first()
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Document not found")

    top_k = payload.top_k or settings.DEFAULT_TOP_K
    query_embedding = embed_query(payload.question)

    raw = vector_store.query(
        query_embedding=query_embedding,
        top_k=top_k,
        owner_id=current_user.id,
        document_id=payload.document_id,
    )

    results: list[RetrievedChunk] = []
    ids = raw.get("ids", [[]])[0]
    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    for chunk_id, text, meta, distance in zip(ids, documents, metadatas, distances):
        # Chroma's default space is L2 distance; convert to a similarity-ish
        # score in (0, 1] so it's easier for API consumers to interpret.
        score = 1.0 / (1.0 + distance)
        results.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=meta["document_id"],
                document_filename=meta["document_filename"],
                chunk_index=meta["chunk_index"],
                text=text,
                score=score,
            )
        )

    return results


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve(
    payload: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = _retrieve(payload, db, current_user)
    return RetrievalResponse(question=payload.question, results=results)


@router.post("/ask", response_model=AnswerResponse)
def ask(
    payload: QuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = _retrieve(payload, db, current_user)

    if not results:
        return AnswerResponse(
            question=payload.question,
            answer="I couldn't find any relevant content in your documents to answer this question.",
            citations=[],
        )

    try:
        answer_text = generate_answer(payload.question, results)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    citations = [
        Citation(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            document_filename=r.document_filename,
            chunk_index=r.chunk_index,
        )
        for r in results
    ]

    return AnswerResponse(question=payload.question, answer=answer_text, citations=citations)
