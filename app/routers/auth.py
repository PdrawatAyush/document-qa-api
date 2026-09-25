"""Registration, login, and refresh-token endpoints.

Login issues a short-lived JWT access token plus a long-lived opaque refresh
token. The refresh token's hash (never the raw value) is stored in the
`refresh_tokens` table so it can be looked up, expired, and revoked
server-side (e.g. on logout) without needing a JWT blacklist.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token_value,
    refresh_token_expiry,
    utcnow_naive,
    verify_password,
)
from app.database import get_db
from app.models.models import RefreshToken, User
from app.schemas.schemas import RefreshRequest, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: str, db: Session) -> Token:
    access_token = create_access_token(subject=user_id)
    refresh_value = new_refresh_token_value()

    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_value),
            expires_at=refresh_token_expiry(),
        )
    )
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_value)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses "username" as the field name; we treat it as email.
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_tokens(user.id, db)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid, unexpired, unrevoked refresh token for a new access
    token. The refresh token is rotated (the old one is revoked and a new one
    issued alongside the new access token) so a stolen-and-reused old token
    is detectable/limited."""
    invalid_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    token_hash = hash_refresh_token(payload.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if row is None or row.revoked or row.expires_at < utcnow_naive():
        raise invalid_exception

    user = db.query(User).filter(User.id == row.user_id).first()
    if user is None:
        raise invalid_exception

    row.revoked = True
    db.commit()

    return _issue_tokens(user.id, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke a refresh token server-side (e.g. on user logout). Idempotent:
    revoking an already-revoked or unknown token still returns 204."""
    token_hash = hash_refresh_token(payload.refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if row is not None:
        row.revoked = True
        db.commit()
    return None
