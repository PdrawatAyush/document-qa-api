"""Tests for registration, login, and token-protected access."""


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
