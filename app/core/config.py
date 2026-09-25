"""Application configuration, loaded from environment variables (.env supported)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # General
    APP_NAME: str = "Document Q&A API"

    # Storage paths
    DATA_DIR: str = os.environ.get("DATA_DIR", "./data")
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    CHROMA_DIR: str = os.path.join(DATA_DIR, "chroma")
    SQLITE_PATH: str = os.path.join(DATA_DIR, "app.db")

    # Auth / JWT
    JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Embeddings
    EMBEDDING_MODEL_NAME: str = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # Chunking
    CHUNK_SIZE: int = int(os.environ.get("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.environ.get("CHUNK_OVERLAP", "150"))

    # Retrieval
    DEFAULT_TOP_K: int = int(os.environ.get("DEFAULT_TOP_K", "4"))

    # Anthropic / generation
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")


settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DIR, exist_ok=True)
