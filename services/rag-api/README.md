# rag-api

FastAPI retrieval service over Postgres + pgvector. Hybrid search: dense cosine
similarity fused 70/30 with Postgres full-text rank.

| Endpoint | Body | Returns |
|---|---|---|
| `GET /health` | - | status, effective embedding mode, model and dimension |
| `POST /ingest` | `{"id": "...", "content": "..."}` | `{"id", "dimensions"}`; `409` if the id exists |
| `POST /search` | `{"query": "...", "top_k": 4}` | ranked `{id, content, score}`; `top_k` 1-20 |
| `POST /rag` | `{"query": "...", "top_k": 4}` | answer, sources, fallback/blocked flags |

## Embedding modes

`EMBEDDING_MODE` is explicit and validated at startup. A real mode that cannot be
served raises instead of silently degrading to mock.

| Mode | Needs | Notes |
|---|---|---|
| `mock` (default) | nothing | Deterministic hashed trigrams. **Not semantic retrieval.** Byte-compatible with the .NET mock embedder |
| `openai` | `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Sends `dimensions` so the vector matches `EMBEDDING_DIM` |
| `vertex` | ADC or a runtime service account, `VERTEX_PROJECT` | `text-embedding-005` over the REST `:predict` endpoint; no key file |

Vertex calls use `RETRIEVAL_DOCUMENT` at ingest and `RETRIEVAL_QUERY` at search.
`/health` reports the mode actually in use.

### Dimension

The `documents.embedding` column is `vector(EMBEDDING_DIM)`, fixed when the table is
created. `text-embedding-005` accepts 1-768 dimensions (1536 is rejected). If you
change `EMBEDDING_DIM`, the model, or the mode, recreate the table and re-ingest:
vectors from different models must not share an index. The service rejects a vector
whose width does not match the configured dimension.

In a real-embedding run, ingest through this API. `dotnet-ingest` writes mock
vectors and would poison a Vertex index.

## Local run

Mock (offline):

```powershell
docker compose up -d postgres rag-api
curl http://localhost:8010/health
```

Vertex, using your local ADC (read-only mount; adapt the path outside Windows):

```powershell
docker compose up -d postgres
docker compose build rag-api
docker run -d --name rag-api-vertex --network gcp-proof-platform_default -p 8010:8000 `
  -e DATABASE_URL=postgresql+psycopg://ai:ai@postgres:5432/aiplatform `
  -e EMBEDDING_MODE=vertex -e EMBEDDING_DIM=384 `
  -e VERTEX_PROJECT=$env:GOOGLE_CLOUD_PROJECT -e VERTEX_LOCATION=us-central1 `
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc/application_default_credentials.json `
  -v "$env:APPDATA/gcloud:/adc:ro" gcp-proof-platform-rag-api
```

On Cloud Run the same mode uses the service account, with no mounted credential.

## Corpus and checks

```powershell
python scripts/ingest_corpus.py --url http://localhost:8010
python scripts/check_retrieval.py --url http://localhost:8010 --output retrieval.json
```

The seed corpus is 19 synthetic rail/utility documents; it is not operational
guidance. `check_retrieval.py` replays eight fixed queries and reports hit@1, hit@k
and MRR. Measured comparison: mock 0.75 hit@1, Vertex `text-embedding-005` 1.00 —
see `evidence/adk-agent/2026-11-23-embedding-and-smoke.md`.

Tests (no database, no provider):

```powershell
docker run --rm -v "${PWD}:/app" -w /app python:3.12-slim `
  sh -c "pip install -q -r requirements-dev.txt && pytest -q"
```
