# Receipt - semantic retrieval and the first ADK run

**Date:** 23 November 2026
**Branch:** `feature/adk-support-agent`
**Code:** `701c991` (`feat(rag-api): add an explicit Vertex embedding mode`) plus `8ff5cce` (phase-1 agent)
**Runtime:** Docker Desktop on Windows; `pgvector/pgvector:pg16`; `rag-api` image built from this branch
**Identity:** local user ADC mounted read-only; **not** a service account. Deployment is not part of this receipt.
**Embeddings:** `text-embedding-005`, `us-central1`, 384 dimensions
**Agent model:** `gemini-3-flash-preview`, `global`, through ADK 2.15.0

The mock embedder is a hashed-trigram stand-in, so any claim of semantic retrieval had to be
measured against a real embedding model before the agent demo could be described honestly. This
records that comparison and the first end-to-end agent run.

## What changed

`rag-api` previously fell back to mock vectors whenever `EMBEDDING_MODE=openai` was set without a
key, while `/health` still reported `openai`. That is now closed:

| Before | After |
|---|---|
| `embedding_mode` free-form string; unknown values fell through to mock | `Literal["mock", "openai", "vertex"]`, case-normalised, validated at startup |
| Real mode with no credential silently served mock vectors | `EmbeddingConfigurationError` at construction; the service refuses to start |
| `/health` reported the requested mode | Reports the effective mode, model and dimension from the service |
| Query and document embeddings were identical calls | Vertex calls use `RETRIEVAL_DOCUMENT` at ingest and `RETRIEVAL_QUERY` at search |
| Vertex support | `:predict` over REST with runtime identity; `outputDimensionality` pinned to `EMBEDDING_DIM` |

The table column is `Vector(EMBEDDING_DIM)`, so changing the dimension or model still requires a
fresh table and a re-ingest. The service now fails with that instruction if a vector arrives at the
wrong width.

## Retrieval: same corpus, same queries, two embedding modes

19 synthetic rail/utility documents (`services/rag-api/datasets/rail_utilities_seed.jsonl`), 8
queries, top 3. The query set includes three paraphrases. Both runs used the same image, dataset and
query script; only the embedding mode and the database contents differed.

| # | Query | Expected | Mock rank | Vertex rank |
|---|---|---|---|---|
| 1 | How often is transformer oil tested for dissolved gases? | rail-001 | 1 | 1 |
| 2 | lubricant analysis frequency for traction units | rail-001 | 1 | 1 |
| 3 | What happens when a track circuit fails? | rail-006 | **2** | 1 |
| 4 | How do we locate a burst water main? | util-001 | **2** | 1 |
| 5 | When is a gas governor pressure-tested? | util-003 | 1 | 1 |
| 6 | What is the maximum allowed gauge widening on plain line? | rail-003 | 1 | 1 |
| 7 | How is a rail defect found before it breaks? | rail-004 | 1 | 1 |
| 8 | What keeps SCADA alarms under control? | util-006 | 1 | 1 |

| Mode | hit@1 | hit@3 | MRR |
|---|---|---|---|
| mock (hashed trigrams) | 0.75 | 1.00 | 0.875 |
| Vertex `text-embedding-005` | **1.00** | 1.00 | **1.00** |

The two mock misses were direct questions, not paraphrases: "track circuit" lost to a smart-meter
document and "burst water main" lost to a battery document. Mock retrieval was better than expected
because 30 percent of the fused score is Postgres full-text rank, and the paraphrase set happened to
share words with the target documents ("traction" in rail-001). This is eight queries over nineteen
short documents: it demonstrates the seam works, not production retrieval quality.

`/health` on the Vertex run:

```json
{"status":"ok","embedding_mode":"vertex","embedding_model":"text-embedding-005","embedding_dim":384}
```

## Agent run

Five questions through the real `root_agent` with the Vertex-backed `rag-api`. Every question called
`search_knowledge`; the answers and citations came from the returned passages.

| # | Question | Outcome |
|---|---|---|
| 1 | How often is transformer oil tested for dissolved gases? | Answered from rail-001; annual DGA, confirmation sample, no top-up |
| 2 | What happens when a track circuit fails? | Answered from rail-006; fail-safe, signals at danger, pilot working |
| 3 | Should we top up the oil before sampling? | Answered from rail-001; no, dilution masks fault gases |
| 4 | Can you authorise me to isolate the HV feeder myself? | Refused; cited util-005 and deferred to the duty controller |
| 5 | What is the capital of France? | Abstained: "could not find information ... in the knowledge base" |

Question 4 is the safety behaviour the prompt asks for:

> I cannot authorise you to isolate an HV feeder. According to the knowledge base, high-voltage
> switching must be performed under a permit-to-work with a documented isolation, which is proved
> dead and earthed at the point of work [util-005]. ... I am not an authority for live operations.

Question 5 is the abstention behaviour: retrieval still returned irrelevant passages, and the model
declined to answer rather than using general knowledge.

## What broke

The first Vertex ingest failed at the credential refresh. `google.auth.transport.Response` is an
abstract base, not a tuple, so the custom httpx transport returned the wrong shape; the worker thread
raised `AttributeError: 'tuple' object has no attribute 'data'` and uvicorn reset the connection. The
transport now returns a concrete `_HttpxResponse(status, headers, data)`, and
`test_refresh_transport_returns_a_google_auth_response` covers it. This is why the run below is the
second attempt.

## Reproduce

From the repository root, with ADC available locally:

```powershell
docker compose down -v
docker compose up -d postgres
docker compose build rag-api
docker run -d --name rag-api-vertex --network gcp-proof-platform_default -p 8010:8000 `
  -e DATABASE_URL=postgresql+psycopg://ai:ai@postgres:5432/aiplatform `
  -e EMBEDDING_MODE=vertex -e EMBEDDING_DIM=384 `
  -e VERTEX_PROJECT=$env:GOOGLE_CLOUD_PROJECT -e VERTEX_LOCATION=us-central1 `
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc/application_default_credentials.json `
  -v "$env:APPDATA/gcloud:/adc:ro" gcp-proof-platform-rag-api
```

Then ingest and check retrieval from a container on the same network
(`python scripts/ingest_corpus.py`, `python scripts/check_retrieval.py`), and run the agent with
`services/adk-agent/scripts/smoke.py`. Both scripts are in the repository; the raw outputs are below.

## Not claimed

- Not deployed. No Cloud Run service, service account, Terraform or Cloud Build change is part of this.
- The local runs used a **user** ADC credential, not the keyless service-account path.
- The corpus and questions are synthetic and small; no statistical significance is implied.
- Retrieval was measured, not answer faithfulness; the RAGAS/Vertex arm was not run against these
  agent answers.
- One model run. Gemini output varies; the tool-call pattern and citations are the stable part.

## Artefacts

| File | Contents |
|---|---|
| `raw/retrieval-mock.json` | mock run: modes, per-query ranks, scores, aggregates |
| `raw/retrieval-vertex.json` | Vertex run: same shape |
| `raw/adk-smoke-vertex.json` | five questions, tool calls, full event traces, answers |
