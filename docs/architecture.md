# Architecture — GCP Proof Platform

## Goals

1. Demonstrate GCP DevOps/Platform engineering in public, NDA-proof code.
2. Close the skill gaps for a GCP DevOps / Platform Engineer role:
   Compute Engine, Cloud Run, BigQuery, GKE/Helm, Terraform, Cloud Build.
3. Stay under a **hard $20/month** always-on budget with full FinOps labelling.

## Design decision: what fits $20/month

| Service | Always-on cost | Verdict |
|---|---|---|
| Compute Engine e2-small VM | ~$12/mo | ✅ keep |
| Cloud Run (scaled-to-zero / jobs) | ~$1/mo | ✅ keep |
| BigQuery (small pipeline) | ~$1/mo | ✅ keep |
| Artifact Registry | ~$0.50/mo | ✅ keep |
| **GKE** (management fee) | **~$73/mo** | ❌ on-demand only (`enable_gke=false`) |

GKE is kept as an optional module so K8s/Helm skills are demonstrable without
paying $73/mo always-on — the same "ephemeral" pattern used on the AWS side.

## Data plane

The always-on VM runs the proven 4-service stack (TS gateway, Python rag-api, C#
dotnet-ingest, Postgres+pgvector) via Docker Compose, cloned from this repo by the
startup script (`startup.sh.tftpl`).

## Analytics plane (BigQuery)

- `ai_platform.eval_reports` table (schema in `schemas/eval_reports.json`).
- Cloud Run job `eval-to-bq` runs the evaluation gate (reusing `services/evaluator`)
  and loads one row per eval question into BigQuery.
- Cloud Scheduler fires it daily (`0 6 * * *`) via an OIDC-authenticated HTTP call.
- Env-injected config: `PROJECT_ID`, `BQ_DATASET`, `BQ_TABLE`.

## CI/CD (Cloud Build)

`infra/cloudbuild/cloudbuild.yaml`:
1. Build + push gateway, rag-api, dotnet-ingest, evaluator → Artifact Registry.
2. **Evaluation gate**: run the evaluator image; fail if aggregate < 0.80.
3. Unit tests for all three languages run in parallel.
Cloud Build SA is granted `artifactregistry.writer` + `run.admin` in
`cloudbuild_iam.tf`.

## FinOps

- Provider `default_labels` apply the full taxonomy to every labelled resource:
  `cost_center`, `business_unit`, `owner`, `budget_owner`, `workload`,
  `cost_category`, `data_classification`, `environment`, `managed_by`.
- `google_billing_budget`: **$20/month**, scoped to the `workload=gcp-proof-platform`
  label, alerts at 80% and 100% to `budget_alerts_email` via a Cloud Monitoring
  email channel. Google Cloud budgets support USD — the cap is the same number the
  AWS project uses (~£20).
- GKE (when enabled) carries the same labels for cost attribution.

## Security posture

- SSH on the VM restricted to `ssh_cidr`; app ports (3002/8010/8080) exposed for the
  public demo URL.
- Cloud Run job uses a dedicated least-privilege SA (`eval_sa`) with only
  `bigquery.dataEditor` + `run.invoker`.
- Secrets via environment/metadata; `.env` and `*.json` local keys gitignored.
- Startup script clones a **public** repo — no credentials baked into the VM.