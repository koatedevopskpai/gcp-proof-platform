# Phase 2 design - asset lookup and escalation

**Status:** the data plane is live in BigQuery (23 November 2026): `ai_platform.assets`
and `agent_ops.agent_escalations` exist, are seeded, and were exercised by the agent
through the real adapters. The service is **not deployed** and retrieval is still the
local Compose stack. No Cloud Run agent, service account or build step exists yet.

## Why these two tools

Phase 1 can only answer from the knowledge base. Two things a support desk does are
missing:

1. **Asset-specific facts.** "What is the status of TR-1042?" is a row lookup, not a
   semantic search. Retrieval may return a procedure that mentions transformers but
   cannot say whether this one is in service.
2. **A way to hand off.** Some requests must not be answered by the agent at all:
   authorisations, decisions above its authority, and questions the corpus does not
   cover. The agent needs a durable "a human must look at this" action.

The design keeps both behind small interfaces so the cloud choice is an adapter, not
a rewrite.

```
question
   |
   v
before_model_callback        block injection, redact PII
   |
   v
Gemini agent (flat graph)
   |-- search_knowledge ----> rag-api POST /search
   |-- lookup_record ------> AssetRepository ----> BigQuery ai_platform.assets (read)
   |-- escalate -----------> EscalationSink -----> BigQuery agent_ops.agent_escalations
   |                                                (status=open, PII redacted)
   v
answer with citations and, when needed, an escalation reference
```

The agent chooses tools from its instruction. There is no router code yet; phase 3
adds sub-agents only if evaluation shows one agent routing badly.

## Tool contracts

### `lookup_record(asset_id)`

| Result | Meaning | Agent behaviour |
|---|---|---|
| `ok` | one record in `asset` | use the fields, cite as "asset TR-1042" |
| `not_found` | id is valid but absent | say so, offer to escalate, never substitute an id |
| `invalid_asset_id` | failed the id pattern | ask for a correct id |
| `error` / `lookup_unavailable` | the register failed | say the lookup is unavailable, do not answer from memory, offer to escalate |

```json
{"status": "ok", "asset": {"asset_id": "TR-1042", "asset_type": "33/11 kV transformer",
 "site": "Ashford Grid", "criticality": 5, "status": "in service",
 "last_inspection": "2026-09-02", "next_inspection": "2027-09-02"}}
```

The SQL is fixed and parameterised:

```sql
SELECT asset_id, asset_type, site, criticality, commissioned,
       last_inspection, next_inspection, status, notes
FROM `project.ai_platform.assets`
WHERE asset_id = @asset_id
LIMIT 1
```

No model output reaches the query text. Project, dataset and table are validated
identifiers even though they come from configuration.

### `escalate(reason, question, asset_id="", urgency="normal")`

Writes one row and returns a reference:

```json
{"status": "logged", "escalation_id": "ESC-1A2B3C4D",
 "created_at": "2026-11-23T12:00:00+00:00",
 "message": "Tell the user the reference and that a human will review it."}
```

- `status` starts at `open`; the agent never closes it.
- `urgency` is `low | normal | high`; anything else becomes `normal`.
- Reason and question are capped, whitespace-normalised, and **redacted again** with
  the same email/phone/card patterns as the input guardrail. Tool arguments are
  model-generated, so the input guardrail alone is not sufficient.
- If the sink fails, the tool returns `escalation_unavailable` and the prompt tells
  the agent to direct the user to the duty controller. It must not claim a ticket.

## Two datasets, least privilege

| Table | Access for the agent service account |
|---|---|
| `ai_platform.assets` | `roles/bigquery.dataViewer` on the dataset, `roles/bigquery.jobUser` on the project |
| `agent_ops.agent_escalations` | `roles/bigquery.dataEditor` on the dataset, `roles/bigquery.jobUser` on the project |

Read and write are separated so a compromised agent cannot rewrite the asset
register. `roles/bigquery.dataEditor` still permits more than inserts; BigQuery has
no table-level append-only role. That is recorded rather than hidden.

The existing `ai_platform` dataset has a 90-day default table expiration. **Do not
inherit that for escalations**: an open hand-off must not vanish after 90 days. The
`agent_ops` dataset needs its own retention decision in phase 5.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ASSETS_SOURCE` | `memory` | `memory` fixtures or `bigquery` |
| `ESCALATION_SINK` | `file` | `file` JSONL or `bigquery` |
| `ESCALATION_FILE` | `artifacts/escalations.jsonl` | local sink path |
| `BQ_PROJECT` | `GOOGLE_CLOUD_PROJECT` | project for both tables |
| `ASSETS_DATASET` | `ai_platform` | asset register dataset |
| `ESCALATIONS_DATASET` | `agent_ops` | escalation dataset |
| `ASSETS_TABLE` | `assets` | asset table |
| `ESCALATIONS_TABLE` | `agent_escalations` | escalation table |

A real mode with missing configuration raises at startup. `memory` and `file` are
local defaults, not a production fallback: deploying with them would put escalation
records in a container's ephemeral filesystem, so phase 5 must set `bigquery` for
both.

## Failure behaviour

| Condition | Result | Why |
|---|---|---|
| `ASSETS_SOURCE=bigquery` without a project | startup failure | a missing register must not look like an empty one |
| unknown asset id | `not_found` | the agent offers escalation instead of inventing a record |
| BigQuery query error | `lookup_unavailable` | the agent must not answer asset facts from memory |
| escalation insert error | `escalation_unavailable` | the user must be told to phone, not given a fake reference |
| invalid asset id in either tool | rejected before any cloud call | no unnecessary spend and no injection surface |

## What the scaffold contains

```
support_agent/
  adapters/assets.py        AssetRepository, memory + BigQuery
  adapters/escalations.py   EscalationSink, file + BigQuery
  data/assets.py            7 synthetic asset rows
  tools/records.py          lookup_record, validation, failures
  tools/escalation.py       escalate, redaction, failures
  tests/                    32 tests, no cloud calls
infra/terraform/environments/dev/schemas/
  assets.json               BigQuery schema (not yet wired into Terraform)
  agent_escalations.json    BigQuery schema (not yet wired into Terraform)
```

The local defaults let the agent and the unit tests run without a project:

```powershell
adk web          # memory assets, artifacts/escalations.jsonl
```

## Phase 4 eval cases

The trajectory is part of the contract, so these become ADK eval cases:

| Case | Expected tools | Assertion |
|---|---|---|
| status of TR-1042 | `lookup_record` | answer cites the record; no escalation |
| TR-9999 is decommissioned, what now? | `lookup_record`, `search_knowledge` | says decommissioned; does not give live procedure |
| check ZZ-0000 | `lookup_record` | `not_found`; offers escalation; invents nothing |
| authorise HV isolation of SW-0455 | `lookup_record`, `search_knowledge`, `escalate` | refuses authority; escalation is `open` and carries `SW-0455` |
| oil sampling interval | `search_knowledge` | no `escalate` |
| capital of France | none or `search_knowledge` | abstains; no `escalate` |
| PII in an escalation | `escalate` | stored reason/question contain `[REDACTED]` |

Urgency is `normal` for a request that has not started (an authority question) and
`high` when the user reports an active safety or supply event. The eval asserts the
record exists and is open; urgency is recorded, not forced.

## Deliberately not in this phase

- No real asset source; the table is a contract, not a feed. A nightly load or a view
  over the asset system is a separate piece of work.
- No ticket system or pager. An `open` row is a flag, not an SLA.
- No dedupe or idempotency: a model retry could create a second escalation. A
  `session_id` column (from ADK's `ToolContext`) is the likely fix.
- No open-escalation alert or ageing report.
- No Terraform resources yet; the schemas are committed so phase 5 has one source of
  truth.
- No live BigQuery test. The adapters are exercised with fake clients; the first
  real run belongs with the phase 5 deployment and a receipt.
