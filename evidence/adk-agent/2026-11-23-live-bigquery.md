# Receipt - live BigQuery data plane for the ADK agent

**Date:** 23 November 2026
**Branch:** `feature/adk-support-agent` (phase-2 data plane, uncommitted at run time)
**Project:** `gcp-proof-platform`
**Agent model:** `gemini-3-flash-preview` (`global`) through ADK 2.15.0
**Identity:** local user ADC; not a service account
**Retrieval:** local `rag-api` in `EMBEDDING_MODE=mock` with the 19-document corpus

This is the step from fixtures to live records. The agent process still ran from a
laptop container and retrieval was still the local Compose stack; the asset register
and the escalation sink were real BigQuery tables.

## Provisioned

Added to `infra/terraform/environments/dev/bigquery.tf` and applied with `-target`
so the destroyed VM/VPC were not recreated:

| Resource | Detail |
|---|---|
| `google_bigquery_dataset.agent_ops` | no default table expiration; an open escalation must not vanish at 90 days |
| `google_bigquery_table.assets` | in `ai_platform`, schema `schemas/assets.json` |
| `google_bigquery_table.agent_escalations` | in `agent_ops`, schema `schemas/agent_escalations.json` |

`apply`: 3 added, 0 changed, 0 destroyed. No compute was created.

## Seeded

`services/adk-agent/scripts/seed_assets.py` loaded the 7 synthetic fixtures:

```
loaded 7 assets into gcp-proof-platform.ai_platform.assets
```

Verified: `SELECT COUNT(*) FROM ai_platform.assets` returned **7**.

## Live run

Environment: `ASSETS_SOURCE=bigquery`, `ESCALATION_SINK=bigquery`,
`BQ_PROJECT=gcp-proof-platform`, `RAG_API_URL=http://rag-api:8000` (local Compose).

| # | Question | Tools | Outcome |
|---|---|---|---|
| 1 | Status of asset TR-1042? | `lookup_record` | Answered from BigQuery: in service, Ashford Grid, next inspection 2027-09-02 |
| 2 | Asset ZZ-0000 is showing an alarm. What now? | `lookup_record` | `not_found`; offered escalation; invented nothing |
| 3 | Authorise HV isolation of SW-0455? | `lookup_record`, `search_knowledge`, `escalate` | Refused authority; wrote ESC-292A2839; cited the duty controller |
| 4 | Oil sampling interval? | `search_knowledge` | Answered from rail-001; no escalation |
| 5 | Capital of France? | none | Declined as outside the knowledge base |

## Verified escalation row

`SELECT ... FROM agent_ops.agent_escalations`:

```json
{"escalation_id": "ESC-292A2839", "asset_id": "SW-0455",
 "reason": "Request for HV isolation authorisation.",
 "urgency": "normal", "status": "open", "created_at": "2026-11-23 18:44:30"}
```

That is a real row in `agent_ops`, written by the tool through the BigQuery adapter,
with PII redaction still applied before insert.

## Serving path

The image builds from `services/adk-agent/Dockerfile` (379 MB) and serves the agent
with `adk api_server`:

```
GET /list-apps -> ["support_agent"]
GET /docs      -> 200
```

ADK warns that the server has no authentication of its own. A Cloud Run deployment
must keep `allUsers` off and rely on IAM (`roles/run.invoker`) or an authenticating
proxy. Session storage is in-memory and rooted at `/app`, so a deployed demo needs
`max_instance_count = 1` unless a shared session store is added.

## Still not live

| Piece | State | Why it matters |
|---|---|---|
| `rag-api` | local Compose, mock embeddings | no running retrieval service in GCP |
| Agent process | local container | not a Cloud Run service; no service account |
| Identity | user ADC | the keyless runtime path is not exercised |
| Cloud Run service + IAM + build step | absent | no deployed endpoint, no `run.invoker` boundary |
| VM / Cloud SQL | none | retrieval has no home; the VM and VPC were destroyed |

Raw trace: `raw/phase-2-live-bigquery.json`.
