"""Pydantic request/response schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


# ---- Documents ----

class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: Optional[str] = None
    num_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkOut(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str

    class Config:
        from_attributes = True


# ---- Retrieval / Q&A ----

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: Optional[int] = None
    document_id: Optional[str] = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    chunk_index: int
    text: str
    score: float


class RetrievalResponse(BaseModel):
    question: str
    results: List[RetrievedChunk]


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    chunk_index: int


class AnswerResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
