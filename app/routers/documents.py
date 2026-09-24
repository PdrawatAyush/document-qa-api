"""Document upload, listing, and deletion endpoints.

Upload flow: accept a PDF or .txt file -> extract text -> chunk it ->
embed each chunk locally (sentence-transformers) -> store chunk rows in
SQLite and chunk vectors in ChromaDB, tagged with owner_id/document_id so
retrieval can be scoped per user.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Chunk, Document, User
from app.schemas.schemas import DocumentOut
from app.services.auth_service import get_current_user
from app.services.chunking import chunk_text, extract_text
from app.services.embedding_service import embed_texts
from app.services import vector_store
from app.core.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = (".pdf", ".txt")
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = file.filename or "upload"
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    text = extract_text(filename, file.content_type, raw_bytes)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in file")

    pieces = chunk_text(text, chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    if not pieces:
        raise HTTPException(status_code=400, detail="No extractable text found in file")

    document = Document(
        owner_id=current_user.id,
        filename=filename,
        content_type=file.content_type,
        num_chunks=len(pieces),
    )
    db.add(document)
    db.flush()  # get document.id without committing yet

    chunk_rows: List[Chunk] = []
    for idx, piece in enumerate(pieces):
        chunk_rows.append(
            Chunk(
                document_id=document.id,
                owner_id=current_user.id,
                chunk_index=idx,
                text=piece,
            )
        )
    db.add_all(chunk_rows)
    db.commit()
    db.refresh(document)

    # Embed and store vectors. If this fails, roll back the DB rows so we
    # don't end up with metadata for chunks that were never embedded.
    try:
        embeddings = embed_texts([c.text for c in chunk_rows])
        vector_store.add_chunks(
            chunk_ids=[c.id for c in chunk_rows],
            embeddings=embeddings,
            documents=[c.text for c in chunk_rows],
            metadatas=[
                {
                    "owner_id": current_user.id,
                    "document_id": document.id,
                    "document_filename": document.filename,
                    "chunk_index": c.chunk_index,
                }
                for c in chunk_rows
            ],
        )
    except Exception as exc:
        db.delete(document)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Embedding failed: {exc}") from exc

    return document


@router.get("", response_model=List[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.owner_id == current_user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_document_chunks(document_id)
    db.delete(document)
    db.commit()
    return None
