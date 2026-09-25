# Document Q&A API

A FastAPI service that lets you upload documents, then ask natural-language questions and get answers with citations back to the source text (retrieval-augmented generation).

Status: working end-to-end — upload, token-based chunking, embedding, retrieval, cited generation, JWT auth with refresh tokens and per-user document scoping, tests, and Docker are all implemented. See the primary job-search project at `../personal project` for the near-term ₹50k/2-3 month plan; this is a portfolio/stretch piece built alongside it.

**Verified**: beyond the pytest suite (mocked LLM calls), this was actually run live — a real `uvicorn` process hit with real HTTP requests (not `TestClient`) — exercising: register → login (access + refresh token) → refresh the access token → reuse-of-rotated-refresh-token rejected → logout revokes the refresh token → upload a real `.txt` file → `/qa/retrieve` returns sensible, correctly-scored chunks → `/qa/ask` returns a clean `503` with no `ANTHROPIC_API_KEY` set (no key was available in this environment, so the real-generation path itself is still unexercised live). That live run caught and fixed two real bugs that the mocked test suite couldn't see (see "Known limitations / notes" and the git history for details): a character-chunking edge case that emitted a spurious duplicate tail chunk for short documents, and a `chromadb`/`posthog` dependency-version mismatch that spammed telemetry errors on every vector-store call.

## Stack
- **FastAPI** — REST API
- **SQLite** (via SQLAlchemy) — document/chunk/user/refresh-token metadata
- **ChromaDB** — local persistent vector store (no external infra required)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local embeddings, no API key needed, so upload + retrieval work fully offline
- **tiktoken** (`cl100k_base`) — token-based chunking, so `CHUNK_SIZE`/`CHUNK_OVERLAP` measure actual tokens rather than characters
- **Anthropic API** (`ANTHROPIC_API_KEY` env var) — generation step, turns retrieved chunks into a cited answer. If the key isn't set, `/qa/ask` returns a clear `503` instead of crashing; everything else (upload, retrieval) still works and is testable without any key.
- **python-jose + passlib[bcrypt]** — JWT access tokens, plus an opaque, hashed, revocable refresh token stored in SQLite
- **pytest** — tests (the Anthropic call is mocked, so the suite needs no API key or network access)
- **Docker / docker-compose** — containerization, with a named volume for the SQLite DB + Chroma data

## Features
- [x] Upload a document (PDF/txt), chunk it (token-based, via tiktoken), embed it, store in the vector store
- [x] Ask a question, retrieve relevant chunks, generate an answer with citations to source chunks
- [x] Multiple documents per user, optionally scope a question to one document
- [x] Auth (JWT access tokens + rotating, revocable refresh tokens) so documents (and retrieval) are scoped per user
- [x] Dockerized, deployable (Dockerfile/compose read-reviewed for correctness; not run — no Docker daemon in this environment)
- [x] pytest suite covering auth, refresh tokens, chunking, upload, retrieval, generation, and user isolation
- [x] Live end-to-end smoke test against a real running server (see "Verified" above)

## Project structure
```
app/
  core/         config (env vars) and security (password hashing, JWT, refresh-token hashing)
  models/       SQLAlchemy ORM models (User, Document, Chunk, RefreshToken)
  schemas/      Pydantic request/response schemas
  routers/      FastAPI routers: auth, documents, qa
  services/     chunking (tiktoken), embeddings, vector store (Chroma), LLM (Anthropic), auth dependency
  database.py   SQLAlchemy engine/session setup
  main.py       FastAPI app assembly
tests/          pytest suite (auth, refresh tokens, chunking, documents, qa) with fixtures in conftest.py
Dockerfile
docker-compose.yml
```

## Running locally

1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. (Optional) Set your Anthropic API key so the `/qa/ask` generation endpoint works. Copy `.env.example` to `.env` and fill it in:
   ```bash
   cp .env.example .env
   # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
   ```
   Without a key, everything except `/qa/ask` still works (`/documents`, `/qa/retrieve`, auth).

3. Run the API:
   ```bash
   uvicorn app.main:app --reload
   ```
   Interactive API docs: http://127.0.0.1:8000/docs

4. Typical flow (via `/docs` or curl):
   - `POST /auth/register` — `{"email": "...", "password": "..."}`
   - `POST /auth/login` — form data `username`/`password`, returns `{"access_token", "refresh_token", "token_type"}`
   - `POST /auth/refresh` — `{"refresh_token": "..."}`, returns a new access token **and** a new refresh token (the old refresh token is rotated/revoked, so reusing it fails)
   - `POST /auth/logout` — `{"refresh_token": "..."}`, revokes that refresh token server-side (204, idempotent)
   - `POST /documents` — multipart upload with a `.pdf` or `.txt` file, `Authorization: Bearer <access_token>`
   - `POST /qa/retrieve` — `{"question": "..."}`, returns top-k chunks with scores, no LLM call
   - `POST /qa/ask` — `{"question": "..."}`, retrieves chunks and calls Anthropic for a cited answer (needs `ANTHROPIC_API_KEY`)

   Both `qa` endpoints accept an optional `"document_id"` to scope the question to a single document, and an optional `"top_k"`.

   Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60); refresh tokens after `REFRESH_TOKEN_EXPIRE_DAYS` (default 7). Only a SHA-256 hash of each refresh token is stored, so a database dump doesn't hand out usable tokens.

The first request that triggers embedding will download the `all-MiniLM-L6-v2` model from Hugging Face (a few hundred MB, cached locally afterwards) — this needs internet access once. The first request that triggers chunking will similarly download tiktoken's `cl100k_base` BPE file once, and cache it.

## Running with Docker

```bash
# from the project root, with ANTHROPIC_API_KEY set in your shell (optional)
docker compose up --build
```

The API is then available at http://localhost:8000. SQLite and Chroma data persist in a named Docker volume (`docqa_data`) across restarts. Pass `ANTHROPIC_API_KEY` (and other overrides) via a `.env` file in the project root — docker-compose reads it automatically — or via your shell environment.

Note: the Dockerfile and docker-compose.yml have been carefully read-reviewed (base image, `COPY` paths against the actual project layout, `EXPOSE`/port mapping, the `docqa_data` volume against `DATA_DIR`, and `requirements.txt` against every import in `app/`) and one real gap was fixed as part of that review — `libgomp1` (the GNU OpenMP runtime `torch`/sentence-transformers needs at import time) is now installed explicitly, since it isn't reliably pulled in as a transitive dependency of `build-essential` alone on `python:3.11-slim`. That said, the build/run itself remains **unverified by actual execution** — no Docker daemon was available in this environment.

## Running tests

```bash
pytest
```

Tests spin up an isolated temp SQLite DB and Chroma collection per run (via `tests/conftest.py`), so they don't touch your real `data/` directory. They cover:
- **Auth** (`tests/test_auth.py`) — registration, duplicate-email rejection, login success/failure, protected-endpoint enforcement, and refresh tokens: issued on login, exchanged for a new access token, rotation rejects reuse of the old refresh token, invalid/expired tokens rejected, logout revokes a token (and is idempotent for unknown tokens).
- **Chunking** (`tests/test_chunking.py`) — token-budget adherence, overlap between consecutive chunks, a short document produces exactly one chunk (regression test for the tail-duplicate bug found during live testing), empty input, and the `chunk_overlap >= chunk_size` guard.
- **Documents** (`tests/test_documents.py`) — upload (txt), rejection of unsupported file types and empty files, auth requirement, and that one user cannot see or fetch another user's documents.
- **Q&A** (`tests/test_qa.py`) — retrieval returns relevant chunks, retrieval is scoped per user, `/qa/ask` returns `503` with no API key, and `/qa/ask` returns a cited answer when the Anthropic call is mocked (`unittest.mock.patch` on `app.routers.qa.generate_answer` — no real API key or network call needed).

The embedding model runs for real in tests (it's local and free); only the Anthropic call is mocked.

## Known limitations / notes
- PDF text extraction (`pypdf`) works well for text-based PDFs; scanned/image-only PDFs would need OCR, which is out of scope here.
- SQLite is used for simplicity per the project brief; swapping to Postgres later would mean changing the connection string in `app/database.py` and adding a driver. (Note: `RefreshToken.expires_at` comparisons use naive UTC datetimes specifically because SQLite/SQLAlchemy doesn't round-trip timezone info on this column type — a Postgres migration should double check that comparison still holds, or switch to timezone-aware columns.)
- Docker setup has been read-reviewed for correctness (and one real bug fixed — see the Docker section above) but remains unverified by actual execution — no Docker daemon available in this environment.
- Refresh-token rotation revokes the *old* token but there's no "revoke all sessions for this user" endpoint yet — only per-token revocation via `/auth/logout`.
- ~~Chunking is character-based~~ — now token-based via `tiktoken` (`cl100k_base`), see the Stack section. Note this encoding is a stand-in, not Claude's actual tokenizer (Anthropic doesn't publish one), so it's a much closer proxy for LLM context budgeting than character counts, but not an exact one.
- ~~No refresh tokens~~ — resolved, see the Stack/Features sections and `POST /auth/refresh` / `POST /auth/logout` above.
