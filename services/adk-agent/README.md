# ADK support agent (prototype)

A grounded support agent for a rail and utilities asset knowledge base, built with
[Google Agent Development Kit](https://google.github.io/adk-docs/) and Gemini on
Vertex AI. This is the third arm of the proof platform: the retrieval API answers
"what does the corpus say", the evaluator scores answers, and this service decides
what to do with a user's question.

**Status: phase 1 (retrieval agent), local only.** Nothing is deployed yet and no
deployment is claimed. See [Phase plan](#phase-plan).

## What it does

```
user question
   |
   v
root LLM agent (Gemini)
   |-- before_model_callback: blocks prompt injection, redacts email/phone/card
   |-- search_knowledge(query, top_k) --> rag-api POST /search
   v
grounded answer with [doc-id] citations, or an explicit "not in the knowledge base"
```

The agent talks to `rag-api` over HTTP and never touches Postgres. Retrieval stays
behind that service boundary so the same agent can be pointed at another corpus
without changing its tools.

## Layout

```
services/adk-agent/
  support_agent/
    agent.py          # root_agent: the graph
    prompts.py        # grounding and safety rules
    guardrails.py     # before_model_callback
    config.py         # env-backed settings
    tools/knowledge.py# search_knowledge -> POST /search
  scripts/smoke.py    # one-shot real-model run that records tool calls and answers
  tests/              # no network, no model calls
  requirements.txt
  requirements-dev.txt
```

## Run it locally

Start the retrieval API first (from the repository root):

```powershell
docker compose up -d postgres rag-api
```

Then, in `services/adk-agent`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

gcloud auth application-default login
Copy-Item .env.example .env    # then set GOOGLE_CLOUD_PROJECT

adk web                        # http://localhost:8000/dev-ui
```

`adk web` reads `.env` from this directory. Ask it something the corpus covers; it
should call `search_knowledge` and cite passage ids.

Tests:

```powershell
pytest -q
```

### Environment

| Variable | Purpose |
|---|---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` calls Vertex AI instead of the Gemini API |
| `GOOGLE_CLOUD_PROJECT` | project for Vertex; Application Default Credentials are used |
| `GOOGLE_CLOUD_LOCATION` | `global`; `gemini-3-flash-preview` is global-only |
| `AGENT_MODEL` | model id, default `gemini-3-flash-preview` |
| `RAG_API_URL` | default `http://localhost:8010` (the Compose port) |

## The mock-embedding caveat

The Compose stack still defaults to `EMBEDDING_MODE=mock`: `rag-api` produces
deterministic stand-in vectors, not semantic embeddings. That is adequate for
exercising the agent offline, but "grounded" then means *grounded in the indexed
text*, not *embedded by a production model*.

`rag-api` now has an explicit `vertex` mode (`text-embedding-005`, runtime
identity). The same eight queries scored **0.75 hit@1 with mock** and **1.00 hit@1
with Vertex** over the 19-document seed corpus; the agent's first five questions
were answered with citations, or declined, as intended. The full record is in
[`evidence/adk-agent/2026-11-23-embedding-and-smoke.md`](../../evidence/adk-agent/2026-11-23-embedding-and-smoke.md).

To run the agent against semantic retrieval, start `rag-api` with
`EMBEDDING_MODE=vertex` and a reachable project, ingest the corpus (it embeds at
ingest time), then point `RAG_API_URL` at that service. See
`services/rag-api/README.md`. The corpus is synthetic and is not operational
guidance.

## Smoke run

`scripts/smoke.py` drives the real model through the real tools and writes a JSON
trace:

```powershell
python scripts/smoke.py --output ..\..\evidence\adk-agent\raw\adk-smoke-vertex.json
```

It calls Vertex AI and costs a few model tokens. The unit tests never do.

## Phase plan

| Phase | Scope | State |
|---|---|---|
| 1 | Root agent, `search_knowledge`, input guardrails, local `adk web`, unit tests | built, local |
| 1b | Seed rail/utility corpus and ingest it | 19 synthetic documents; mock and Vertex runs recorded |
| 2 | `lookup_record` (BigQuery, read-only) and an `escalate` tool that raises a HITL flag | not started |
| 3 | Router + retriever/responder sub-agents, only if phase 1 evaluation shows a need | not started |
| 4 | ADK trajectory evals, plus the existing RAGAS/Vertex arm, rows into `ai_platform.eval_reports` | not started |
| 5 | Terraform + Cloud Build deploy to Cloud Run, receipt, teardown | not started |

Deployment notes for phase 5: the service must run as a dedicated service account
with `roles/aiplatform.user` and no key file, reach `rag-api` over its private or
authenticated URL, and not be invocable by `allUsers` unless that posture is
deliberately accepted and written down.
