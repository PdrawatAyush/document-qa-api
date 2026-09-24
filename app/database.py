"""SQLAlchemy engine/session setup for the SQLite metadata database."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# check_same_thread=False is needed because FastAPI can use the connection
# across different threads within the same request lifecycle.
engine = create_engine(
    f"sqlite:///{settings.SQLITE_PATH}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
