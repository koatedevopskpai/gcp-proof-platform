# Receipt - five-day keyless ADK agent on Cloud Run

**Date:** 23 November 2026
**Window:** keep until **28 November 2026**, then destroy
**Branch:** `feature/adk-support-agent` (code committed with this receipt)
**Project / region:** `gcp-proof-platform` / `us-central1`
**Terraform root:** `infra/terraform/environments/agent-demo` (state prefix `agent-demo`)

This is the deployed version of phase 2. It is isolated from `environments/dev`: its
own VPC, Cloud SQL, Cloud Run services, BigQuery datasets, secrets and service
accounts. Destroying it does not touch the evaluation path.

## Architecture

```
invoker SA (token only)
      |
      v
Cloud Run: agent-demo-adk          IAM required, no allUsers
  service account: agent-demo-agent
      |  ID token, audience = rag URL
      v
Cloud Run: agent-demo-rag-api      IAM required, only agent-demo-agent has invoker
  service account: agent-demo-rag
      |  private IP 10.140.0.3
      v
Cloud SQL Postgres 16              no public IP, pgvector, zonal, no backups
```

The agent calls Vertex AI and BigQuery as its own service account. No key file and
no `GOOGLE_API_KEY` exist in either service.

## Deployed

| Resource | Detail |
|---|---|
| `agent-demo-adk` | Cloud Run service, `adk api_server`, max 1 instance (in-memory sessions) |
| `agent-demo-rag-api` | Cloud Run service, 1 vCPU / 1 GiB, max 2 instances |
| `agent-demo-seed` | one-off Cloud Run job: pgvector, `documents` table, grants, 19 embeddings |
| `agent-demo-pg` | Cloud SQL Postgres 16, `db-g1-small`, private IP only |
| `agent_demo_data.assets` | 7 synthetic asset rows |
| `agent_demo_ops.agent_escalations` | open HITL rows, no default expiration |
| `agent-demo-rag-db` / `agent-demo-seed-db` | Secret Manager, app and one-off admin passwords |
| `agent-demo-agent` / `-rag` / `-seed` / `-invoker` | one service account per workload |

`agent-demo-rag-api` and `agent-demo-adk` are public endpoints at the network layer
but both returned **403 without an ID token**. The ADK API server has no
authentication of its own; Cloud Run IAM is the boundary.

## Keyless and least privilege

| Check | Result |
|---|---|
| User-managed keys on all four service accounts | **0** |
| Unauthenticated `GET /health` on the agent | **403** |
| Unauthenticated `GET /health` on rag-api | **403** |
| Authenticated agent `/health` (invoker SA token) | **200** |
| Invoker SA token against rag-api (no role there) | **401** |
| Agent service account env | no secret refs, no API key |
| rag-api service account env | one secret ref: `DB_PASSWORD` |
| Cloud SQL addresses | `10.140.0.3` **PRIVATE**; `ipv4Enabled: false` |
| `allUsers` / `allAuthenticatedUsers` | absent from both services |
| Project roles | `aiplatform.user`, dataset-scoped BigQuery, `run.invoker`, AR reader, logs — no Editor/Owner |

The human does not have `run.invoker` on the agent. They have
`roles/iam.serviceAccountTokenCreator` on **`agent-demo-invoker` only**, and that
service account has exactly one role: `roles/run.invoker` on the agent. This is the
token-minting boundary the receipt is meant to demonstrate.

The rag-api's only invoker is `agent-demo-agent`; its ID token is fetched from the
metadata server inside `search_knowledge`, with no key and no shared secret.

## Live run

Five questions through the deployed agent, each with a fresh session:

| # | Question | Tools | Outcome |
|---|---|---|---|
| 1 | Status of asset TR-1042? | `lookup_record` | BigQuery row: in service, Ashford Grid, next inspection 2027-09-02 |
| 2 | How often is transformer oil sampled? | `search_knowledge` | rag-api 200, cited rail-001 |
| 3 | Authorise HV isolation of SW-0455? | `lookup_record`, `search_knowledge`, `escalate` | Refused, cited util-005, wrote **ESC-46E785F1** |
| 4 | ZZ-0000 is showing an alarm, what now? | `lookup_record`, `search_knowledge` | Said not found; offered escalation; did not invent a record |
| 5 | Capital of France? | none | Declined as outside the knowledge base |

Verified data:

- `SELECT COUNT(*) FROM agent_demo_data.assets` → **7**
- `agent_demo_ops.agent_escalations` contains `ESC-46E785F1`, `asset_id=SW-0455`,
  `status=open`, `urgency=normal`. An earlier row `ESC-1CD3C97E` (urgency high) was
  written while rag-api was still on the old image; it is also open.
- `rag-api` logs show `POST /search 200` for the retrieval calls.

## Findings from the deployment

Three real issues, fixed and recorded:

1. **`google.auth.default()` failed on Cloud Run** even though the metadata token
   endpoint worked. Cause: the rag-api image lacked `requests`, and google-auth's GCE
   detection imports it and silently treats the ImportError as "no credentials".
   Fixed by adding `requests==2.*`; `test_refresh_transport...` still covers the
   separate refresh transport.
2. **`gcloud auth print-identity-token --impersonate` failed with
   `iam.serviceAccounts.getAccessToken` denied** until
   `iamcredentials.googleapis.com` was enabled. Terraform now enables it.
3. **Cloud Run pins the image digest when a service is created from a tag.** After
   rebuilding `rag-api:agent-demo` with the `requests` fix, the service kept running
   the old digest until `gcloud run services update --image` forced a new revision.
   The Terraform README records this.

The Cloud SQL schema had already been created by the first seed attempt; the retry
found 0 existing rows and inserted all 19, then granted CRUD to `rag`.

## Cost

Five days, us-central1, estimates:

| Item | Five days |
|---|---|
| Cloud SQL `db-g1-small`, zonal, no HA | ~$6 |
| 10 GB SSD | ~$0.30 |
| Cloud Run agent + rag-api | cents (scale to zero) |
| BigQuery demo datasets | cents |
| Artifact Registry | cents |
| **Total** | **~$6–9** |

The existing £15/month budget alert is not threatened. Cloud SQL is the only
component that bills while idle, which is why the teardown is a hard step.

## Teardown

A topmost reminder is registered for **06:00 on 28 November 2026**; its button runs
the destroy below after a confirmation. Preview it with the desktop shortcut or
`scripts/agent-demo-reminder-setup.ps1`.

```powershell
.\scripts\agent-demo-down.ps1
```

Removes Cloud Run, Cloud SQL, the VPC, both demo datasets, the secrets and the
service accounts. Images remain in Artifact Registry. **Do this on 28 November
2026.** A stopped Cloud SQL instance still bills storage, so destroy rather than
stop.

## Not claimed

- The database uses a password in Secret Manager, not IAM database auth. The Cloud
  SQL Python connector supports `pg8000`/`pymysql`/`pytds`, not `psycopg`; switching
  the driver would have changed the retrieval stack for a five-day demo. The agent
  and all GCP API calls are keyless.
- rag-api has public ingress, protected by IAM. Internal-only ingress behind a load
  balancer was not used (cost and reachability).
- No VPC Service Controls: the project is a standalone account, not an organization.
- No HA, no backups, no retention policy; this is a demo window, not a service.
- ADK sessions are in-memory, so the agent is capped at one instance.
- One run, five questions, synthetic assets and corpus.

Raw traces and the summary are in `raw/agent-demo-live/`.
