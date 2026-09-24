# Document Q&A API

A FastAPI service that lets you upload documents, then ask natural-language questions and get answers with citations back to the source text (retrieval-augmented generation).

Status: in progress — this is a Tier 3 stretch project, built mostly autonomously as a portfolio piece for later (see the primary job-search project at `../personal project` for the near-term ₹50k/2-3 month plan).

## Planned stack
- FastAPI — REST API
- SQLite/PostgreSQL — document + chat metadata
- ChromaDB — local vector store (no external infra required)
- sentence-transformers — local embeddings (free, no API key needed for retrieval)
- Anthropic API (optional, via `ANTHROPIC_API_KEY` env var) — generation step, for turning retrieved chunks into an actual answer with citations
- pytest — tests
- Docker — containerization for deployment later

## Planned features
- [ ] Upload a document (PDF/txt), chunk it, embed it, store in the vector store
- [ ] Ask a question, retrieve relevant chunks, generate an answer with citations to source chunks
- [ ] Multiple documents / basic collections
- [ ] Auth (JWT) so documents are scoped per user
- [ ] Dockerized, deployable

Build log and progress in commit history.
