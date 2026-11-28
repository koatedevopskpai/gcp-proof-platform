# Agent demo teardown - 28 November 2026

**Status:** complete
**Scope:** `infra/terraform/environments/agent-demo`
**Trigger:** the desktop reminder fired at 06:04 UTC with result 0; teardown was run
manually after confirming the destroy plan.

## Removed

| Area | Resources |
|---|---|
| Cloud Run services | `agent-demo-adk`, `agent-demo-rag-api` |
| Cloud Run jobs | `agent-demo-seed`, `phase4-ragas` |
| Cloud SQL | `agent-demo-pg` (Postgres 16, private IP) |
| BigQuery | `agent_demo_data` (`assets`), `agent_demo_ops` (`agent_escalations`) |
| Secret Manager | `agent-demo-rag-db`, `agent-demo-seed-db` and versions |
| Service accounts | `agent-demo-agent`, `agent-demo-rag`, `agent-demo-seed`, `agent-demo-invoker` |
| IAM | project and dataset bindings for the demo service accounts |
| Network | `agent-demo-vpc`, `agent-demo-subnet`, `agent-demo-sql-range`, service-networking peering |
| Artifact Registry | `adk-agent:agent-demo`, `rag-api:agent-demo`, `phase4-ragas:{baseline,percase,percase2,promptfix}` |

## Preserved

| Resource | Why |
|---|---|
| `agent_eval_data.assets` (7 rows) | permanent evaluation assets, no dependency on the demo |
| `eval-to-bq` Cloud Run job | permanent evaluation gate, documented in `docs/architecture.md` |
| `rag-api` tags `9fa0b04`, `cae2abd`, `f49ede8` | CI/dev images, not demo-only |
| `agent_ops`, `ai_platform`, market datasets | outside the demo |

## Verification

| Check | Command | Result |
|---|---|---|
| Terraform state | `terraform -chdir=... state list` | 0 resources |
| Cloud Run services | `gcloud run services list --region us-central1` | none |
| Cloud Run jobs | `gcloud run jobs list --region us-central1` | `eval-to-bq` only |
| Cloud SQL | `gcloud sql instances list` | none |
| Demo secrets | `gcloud secrets list --filter='name:agent-demo'` | none |
| Demo service accounts | `gcloud iam service-accounts list --filter='email:agent-demo'` | none |
| Demo network | `gcloud compute networks list --filter='name:agent-demo'` | none |
| Demo global address | `gcloud compute addresses list --global --filter='name:agent-demo'` | none |
| Datasets | `bq ls` | no `agent_demo_*`; `agent_eval_data` present |
| Eval assets | `select count(*) from agent_eval_data.assets` | 7 |
| Demo image tags | `gcloud artifacts docker tags list` | no `agent-demo`, no `phase4-ragas` |

## Issues and fixes

1. **PowerShell did not expand `-chdir=$tfDir`.** Terraform received the literal
   variable. Fixed by quoting the whole argument: `terraform "-chdir=$tfDir" ...`.
2. **The first destroy stopped mid-run.** `$ErrorActionPreference = "Stop"` plus
   Terraform's progress on stderr aborted the pipeline after 20 resources. The script
   now uses `Continue` around Terraform and checks `$LASTEXITCODE`.
3. **Cloud Run deletion protection.** The provider refused to delete the two services
   and the seed job because `deletion_protection` defaulted to true. They were deleted
   with `gcloud`, removed from state, and the Terraform config now sets
   `deletion_protection = false`.
4. **Cloud SQL `postgres` role had dependent objects.** `terraform destroy` could not
   drop the role because 211 objects still depended on it. The instance was deleted
   with `gcloud sql instances delete`, then the instance/user resources were removed
   from state.
5. **Service Networking connection blocked by a producer.** After the SQL instance was
   gone, the connection still reported a producer. The VPC peering was deleted
   directly with `gcloud compute networks peerings delete`, then the connection was
   removed from state.

## Cost

- Cloud SQL and both Cloud Run services are gone; no compute is running.
- `eval-to-bq` is idle and has no idle compute charge.
- BigQuery storage for seven rows is negligible.
- Remaining Artifact Registry images are shared CI/permanent images, not demo-only.

The demo no longer contributes to the daily run rate.
