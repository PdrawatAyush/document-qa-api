"""Password hashing, JWT, and refresh-token helpers."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """Return the subject (user id) encoded in the token, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def utcnow_naive() -> datetime:
    """UTC 'now' as a naive datetime, matching how SQLite/SQLAlchemy round-trips
    DateTime columns here (no tzinfo preserved) so stored and freshly-computed
    values can be compared directly without naive/aware mismatches."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_refresh_token_value() -> str:
    """A random opaque refresh token (not a JWT). Only its hash is stored, so a
    leaked database dump doesn't hand out usable refresh tokens."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return utcnow_naive() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
