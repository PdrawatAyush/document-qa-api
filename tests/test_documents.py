"""Tests for document upload, listing, retrieval-scoping, and user isolation."""

SAMPLE_TEXT = (
    b"The capital of France is Paris. Paris is famous for the Eiffel Tower "
    b"and the Louvre museum. " * 15
)


def test_upload_txt_document(client, make_user):
    _, headers = make_user()
    resp = client.post(
        "/documents",
        files={"file": ("facts.txt", SAMPLE_TEXT, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "facts.txt"
    assert body["num_chunks"] >= 1


def test_upload_rejects_unsupported_extension(client, make_user):
    _, headers = make_user()
    resp = client.post(
        "/documents",
        files={"file": ("image.png", b"not really a png", "image/png")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_upload_rejects_empty_file(client, make_user):
    _, headers = make_user()
    resp = client.post(
        "/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_upload_requires_auth(client):
    resp = client.post(
        "/documents",
        files={"file": ("facts.txt", SAMPLE_TEXT, "text/plain")},
    )
    assert resp.status_code == 401


def test_list_documents_returns_only_own_uploads(client, make_user):
    _, headers_a = make_user("alice@example.com")
    _, headers_b = make_user("bob@example.com")

    client.post(
        "/documents",
        files={"file": ("alice.txt", SAMPLE_TEXT, "text/plain")},
        headers=headers_a,
    )

    resp_a = client.get("/documents", headers=headers_a)
    resp_b = client.get("/documents", headers=headers_b)

    assert len(resp_a.json()) == 1
    assert resp_a.json()[0]["filename"] == "alice.txt"
    assert len(resp_b.json()) == 0


def test_get_other_users_document_is_404(client, make_user):
    _, headers_a = make_user("alice2@example.com")
    _, headers_b = make_user("bob2@example.com")

    upload = client.post(
        "/documents",
        files={"file": ("alice.txt", SAMPLE_TEXT, "text/plain")},
        headers=headers_a,
    )
    doc_id = upload.json()["id"]

    resp = client.get(f"/documents/{doc_id}", headers=headers_b)
    assert resp.status_code == 404

    resp_owner = client.get(f"/documents/{doc_id}", headers=headers_a)
    assert resp_owner.status_code == 200


def test_delete_document_removes_it(client, make_user):
    _, headers = make_user()
    upload = client.post(
        "/documents",
        files={"file": ("temp.txt", SAMPLE_TEXT, "text/plain")},
        headers=headers,
    )
    doc_id = upload.json()["id"]

    resp = client.delete(f"/documents/{doc_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/documents/{doc_id}", headers=headers)
    assert resp.status_code == 404
