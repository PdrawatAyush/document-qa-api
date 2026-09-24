# Document Q&A API

A FastAPI service that lets you upload documents, then ask natural-language questions and get answers with citations back to the source text (retrieval-augmented generation).

Status: working end-to-end — upload, chunking, embedding, retrieval, cited generation, JWT auth with per-user document scoping, tests, and Docker are all implemented. See the primary job-search project at `../personal project` for the near-term ₹50k/2-3 month plan; this is a portfolio/stretch piece built alongside it.

## Stack
- **FastAPI** — REST API
- **SQLite** (via SQLAlchemy) — document/chunk/user metadata
- **ChromaDB** — local persistent vector store (no external infra required)
- **sentence-transformers** (`all-MiniLM-L6-v2`) — local embeddings, no API key needed, so upload + retrieval work fully offline
- **Anthropic API** (`ANTHROPIC_API_KEY` env var) — generation step, turns retrieved chunks into a cited answer. If the key isn't set, `/qa/ask` returns a clear `503` instead of crashing; everything else (upload, retrieval) still works and is testable without any key.
- **python-jose + passlib[bcrypt]** — JWT auth
- **pytest** — tests (the Anthropic call is mocked, so the suite needs no API key or network access)
- **Docker / docker-compose** — containerization, with a named volume for the SQLite DB + Chroma data

## Features
- [x] Upload a document (PDF/txt), chunk it, embed it, store in the vector store
- [x] Ask a question, retrieve relevant chunks, generate an answer with citations to source chunks
- [x] Multiple documents per user, optionally scope a question to one document
- [x] Auth (JWT) so documents (and retrieval) are scoped per user
- [x] Dockerized, deployable
- [x] pytest suite covering auth, upload, retrieval, generation, and user isolation

## Project structure
```
app/
  core/         config (env vars) and security (password hashing, JWT)
  models/       SQLAlchemy ORM models (User, Document, Chunk)
  schemas/      Pydantic request/response schemas
  routers/      FastAPI routers: auth, documents, qa
  services/     chunking, embeddings, vector store (Chroma), LLM (Anthropic), auth dependency
  database.py   SQLAlchemy engine/session setup
  main.py       FastAPI app assembly
tests/          pytest suite (auth, documents, qa) with fixtures in conftest.py
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
   - `POST /auth/login` — form data `username`/`password`, returns a JWT `access_token`
   - `POST /documents` — multipart upload with a `.pdf` or `.txt` file, `Authorization: Bearer <token>`
   - `POST /qa/retrieve` — `{"question": "..."}`, returns top-k chunks with scores, no LLM call
   - `POST /qa/ask` — `{"question": "..."}`, retrieves chunks and calls Anthropic for a cited answer (needs `ANTHROPIC_API_KEY`)

   Both `qa` endpoints accept an optional `"document_id"` to scope the question to a single document, and an optional `"top_k"`.

The first request that triggers embedding will download the `all-MiniLM-L6-v2` model from Hugging Face (a few hundred MB, cached locally afterwards) — this needs internet access once.

## Running with Docker

```bash
# from the project root, with ANTHROPIC_API_KEY set in your shell (optional)
docker compose up --build
```

The API is then available at http://localhost:8000. SQLite and Chroma data persist in a named Docker volume (`docqa_data`) across restarts. Pass `ANTHROPIC_API_KEY` (and other overrides) via a `.env` file in the project root — docker-compose reads it automatically — or via your shell environment.

Note: the Docker build/run was written against the standard `python:3.11-slim` + pip pattern but could not be executed in the sandboxed environment this project was built in (no Docker daemon available there). If `docker compose up` surfaces a missing system dependency for `tokenizers`/`sentence-transformers` on your machine, `apt-get install build-essential` (already included in the Dockerfile) should cover it.

## Running tests

```bash
pytest
```

Tests spin up an isolated temp SQLite DB and Chroma collection per run (via `tests/conftest.py`), so they don't touch your real `data/` directory. They cover:
- **Auth** (`tests/test_auth.py`) — registration, duplicate-email rejection, login success/failure, protected-endpoint enforcement.
- **Documents** (`tests/test_documents.py`) — upload (txt), rejection of unsupported file types and empty files, auth requirement, and that one user cannot see or fetch another user's documents.
- **Q&A** (`tests/test_qa.py`) — retrieval returns relevant chunks, retrieval is scoped per user, `/qa/ask` returns `503` with no API key, and `/qa/ask` returns a cited answer when the Anthropic call is mocked (`unittest.mock.patch` on `app.routers.qa.generate_answer` — no real API key or network call needed).

The embedding model runs for real in tests (it's local and free); only the Anthropic call is mocked.

## Known limitations / notes
- Chunking is character-based (not token-based) for simplicity — no extra tokenizer dependency needed.
- PDF text extraction (`pypdf`) works well for text-based PDFs; scanned/image-only PDFs would need OCR, which is out of scope here.
- No refresh tokens — JWTs simply expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60) and the user logs in again.
- SQLite is used for simplicity per the project brief; swapping to Postgres later would mean changing the connection string in `app/database.py` and adding a driver.
- Docker setup is written to standard patterns but unverified in this build environment (no Docker daemon available) — see the Docker section above.
