"""Shared pytest fixtures.

Sets DATA_DIR to a temp directory (isolated SQLite DB + Chroma store) and
clears ANTHROPIC_API_KEY *before* the app is imported, since app.core.config
reads the environment once at import time. This means the test suite never
needs a real API key for retrieval, and generation tests explicitly mock
the LLM call rather than hitting the network.
"""
import os
import shutil
import tempfile

import pytest

_TEST_DATA_DIR = tempfile.mkdtemp(prefix="docqa_test_")
os.environ["DATA_DIR"] = _TEST_DATA_DIR
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["JWT_SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import vector_store  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    """Reset SQL tables and the Chroma collection before every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    vector_store.reset_collection()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def make_user(client):
    """Registers + logs in a user, returning (user_json, auth_headers)."""

    def _make_user(email="user@example.com", password="password123"):
        client.post("/auth/register", json={"email": email, "password": password})
        resp = client.post("/auth/login", data={"username": email, "password": password})
        token = resp.json()["access_token"]
        return {"email": email}, {"Authorization": f"Bearer {token}"}

    return _make_user


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
