"""FastAPI application entrypoint."""
from fastapi import FastAPI

from app.database import Base, engine
from app.models import models  # noqa: F401  (ensures models are registered on Base)
from app.routers import auth, documents

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Document Q&A API",
    description=(
        "Upload documents and ask natural-language questions about them. "
        "Retrieval-augmented generation with citations back to source chunks."
    ),
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(documents.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
