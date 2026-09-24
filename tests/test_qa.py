"""Tests for retrieval and generation endpoints.

The Anthropic call is mocked throughout so the suite never needs a real
ANTHROPIC_API_KEY or network access.
"""
from unittest.mock import patch

SAMPLE_TEXT = (
    b"The capital of France is Paris. Paris is famous for the Eiffel Tower "
    b"and the Louvre museum. " * 15
)


def _upload_sample(client, headers, filename="facts.txt"):
    return client.post(
        "/documents",
        files={"file": (filename, SAMPLE_TEXT, "text/plain")},
        headers=headers,
    )


def test_retrieve_returns_relevant_chunks(client, make_user):
    _, headers = make_user()
    _upload_sample(client, headers)

    resp = client.post(
        "/qa/retrieve",
        json={"question": "What is the capital of France?"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"], "expected at least one retrieved chunk"
    assert "Paris" in body["results"][0]["text"]
    assert body["results"][0]["document_filename"] == "facts.txt"


def test_retrieve_scoped_to_current_user(client, make_user):
    _, headers_a = make_user("alice3@example.com")
    _, headers_b = make_user("bob3@example.com")
    _upload_sample(client, headers_a)

    resp = client.post(
        "/qa/retrieve",
        json={"question": "capital of France"},
        headers=headers_b,
    )
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_retrieve_requires_auth(client):
    resp = client.post("/qa/retrieve", json={"question": "anything"})
    assert resp.status_code == 401


def test_ask_without_api_key_returns_503(client, make_user):
    _, headers = make_user()
    _upload_sample(client, headers)

    resp = client.post(
        "/qa/ask",
        json={"question": "What is the capital of France?"},
        headers=headers,
    )
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_ask_with_mocked_llm_returns_answer_and_citations(client, make_user):
    _, headers = make_user()
    _upload_sample(client, headers)

    with patch("app.routers.qa.generate_answer") as mock_generate:
        mock_generate.return_value = "Paris is the capital of France (see [1])."

        resp = client.post(
            "/qa/ask",
            json={"question": "What is the capital of France?"},
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Paris is the capital of France (see [1])."
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["document_filename"] == "facts.txt"
    mock_generate.assert_called_once()


def test_ask_with_no_matching_documents_skips_llm_call(client, make_user):
    _, headers = make_user()
    # No documents uploaded at all -> nothing to retrieve.

    with patch("app.routers.qa.generate_answer") as mock_generate:
        resp = client.post(
            "/qa/ask",
            json={"question": "anything at all"},
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.json()["citations"] == []
    mock_generate.assert_not_called()
