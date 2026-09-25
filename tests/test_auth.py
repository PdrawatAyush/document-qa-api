"""Tests for registration, login, token-protected access, and refresh tokens."""
from datetime import timedelta

from app.core.security import utcnow_naive
from app.database import SessionLocal
from app.models.models import RefreshToken


def test_register_creates_user(client):
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "password123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert "id" in body
    assert "hashed_password" not in body


def test_register_duplicate_email_rejected(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    resp = client.post("/auth/register", json={"email": "dup@example.com", "password": "password123"})
    assert resp.status_code == 400


def test_login_success_returns_token(client):
    client.post("/auth/register", json={"email": "b@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "b@example.com", "password": "password123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password_rejected(client):
    client.post("/auth/register", json={"email": "c@example.com", "password": "password123"})
    resp = client.post("/auth/login", data={"username": "c@example.com", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_unknown_user_rejected(client):
    resp = client.post("/auth/login", data={"username": "nobody@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_protected_endpoint_requires_token(client):
    resp = client.get("/documents")
    assert resp.status_code == 401


def test_protected_endpoint_rejects_bad_token(client):
    resp = client.get("/documents", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# ---- Refresh tokens ----


def _login(client, email="refresh@example.com", password="password123"):
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post("/auth/login", data={"username": email, "password": password})
    return resp.json()


def test_refresh_issues_new_access_token(client):
    tokens = _login(client, "refresh1@example.com")

    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    # New access token actually works against a protected endpoint.
    me = client.get("/documents", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_refresh_rotates_old_token_so_reuse_is_rejected(client):
    tokens = _login(client, "refresh2@example.com")

    first = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200

    # Reusing the original (now-rotated/revoked) refresh token must fail.
    second = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert second.status_code == 401


def test_refresh_rejects_invalid_token(client):
    resp = client.post("/auth/refresh", json={"refresh_token": "not-a-real-refresh-token"})
    assert resp.status_code == 401


def test_refresh_rejects_expired_token(client):
    tokens = _login(client, "refresh3@example.com")

    # Force the stored refresh token to look expired.
    db = SessionLocal()
    try:
        from app.core.security import hash_refresh_token

        row = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"]))
            .first()
        )
        assert row is not None
        row.expires_at = utcnow_naive() - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = _login(client, "refresh4@example.com")

    logout_resp = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout_resp.status_code == 204

    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_logout_is_idempotent_for_unknown_token(client):
    resp = client.post("/auth/logout", json={"refresh_token": "never-issued-token"})
    assert resp.status_code == 204
