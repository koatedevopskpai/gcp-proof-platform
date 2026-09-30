# GCP Proof Platform

**Production-grade GCP Platform/DevOps reference implementation** — a public,
NDA-proof demonstration of Google Cloud Platform engineering: Compute Engine,
Cloud Run, BigQuery, Artifact Registry, Cloud Build CI/CD, optional GKE + Helm,
all FinOps-labelled and capped at a **$20/month budget**.

Built to support a **GCP DevOps / Platform Engineer** application — the GCP-native
companion to the AWS `ai-platform-proof` project.

## Architecture

```
                     ┌──────────────────────────────────────────┐
   clients ─────────▶│  ALWAYS-ON VM (Compute Engine e2-small)  │  ~$12-14/mo
                     │  gateway (TS) + rag-api (Python)         │
                     │  + dotnet-ingest (C#) + postgres/pgvector│
                     │  Docker Compose (startup script)         │
                     └──────────────────────────────────────────┘

   MLOps / analytics plane
   ┌────────────────────────────────────────────────────────────┐
   │ Cloud Scheduler ─▶ Cloud Run job (eval-to-bq) ─▶ BigQuery  │
   │ Cloud Build CI/CD: build → push → test → eval gate         │
   │ Artifact Registry: container images                        │
   │ Cloud Billing Budget: hard $20/mo, label-scoped, alerts    │
   │ GKE + Helm (OPTIONAL, ephemeral, disabled by default)      │
   └────────────────────────────────────────────────────────────┘
```

## Capabilities demonstrated (maps to the target role)

| Requirement | Where |
|---|---|
| **Compute Engine** | Always-on `e2-small` VM running the full stack (`infra/terraform/.../main.tf`) |
| **Cloud Run** | `eval-to-bq` job that runs the MLOps eval gate and loads reports into BigQuery |
| **BigQuery** | `ai_platform.eval_reports` dataset/table + loader pipeline (`mlops/bigquery`) |
| **GKE + Helm** | Optional module (`gke.tf`, on the hardened VPC) + charts (`infra/helm`) — spin up for demos |
| **Terraform** | Entire GCP footprint, `default_labels` FinOps taxonomy |
| **Cloud Build / DevSecOps** | `infra/cloudbuild/cloudbuild.yaml` — build → push → **Checkov (IaC)** → **Trivy (images)** → **SBOM** → eval gate → tests |
| **Networking** | Custom VPC + subnets + private Google access + **Private Service Connect** (`networking.tf`) |
| **Identity** | **Workload Identity Federation** for GitHub Actions (`wif.tf`) |
| **Observability** | Availability **SLO**, error-budget alert, ops dashboard (`monitoring.tf`) |
| **Data perimeter** | **VPC Service Controls** module, org-guarded (`vpcsc.tf`) |
| **FinOps** | Every resource labelled (`cost_center`, `workload`, `budget_owner`, ...) + **$20/mo budget** with 80%/100% alerts |

## Cost model (us-central1, always-on)

| Component | ~$/mo |
|---|---|
| Compute Engine e2-small VM | 12 |
| Cloud Run job (daily) + Cloud Scheduler | ~1 |
| BigQuery (small eval pipeline) | ~1 |
| Artifact Registry (few GB) | ~0.50 |
| VPC / subnets / PSC / WIF / VPC-SC / Monitoring | $0 |
| Cloud Build / Monitoring (free tier) | 0 |
| **Total** | **~14** — within the hard **$20** budget |

> **Cloud NAT** is intentionally NOT deployed (flat ~$9–35/mo even when idle would
> break the cap; the VM egresses via its public IP). Documented as a pattern in
> `docs/architecture.md` for private-only workloads.

GKE management fee (~$73/mo) is intentionally **excluded** — GKE is on-demand only
(`enable_gke = true` → demo → `false`).

## Quick start

```bash
# 1. Provision (need gcloud authed as the project owner + terraform)
scripts\up.ps1

# 2. Live URL after the VM boots (~5 min)
curl http://<public-ip>:3002/health

# 3. Redeploy the stack to the VM
scripts\deploy.ps1

# 4. Run the eval-to-bigquery pipeline manually
gcloud run jobs execute eval-to-bq --region us-central1

# 5. Query the eval history
bq query --use_legacy_sql=false \
  'SELECT report_date, aggregate_score, passed FROM `gcp-proof-platform.ai_platform.eval_reports` ORDER BY report_date'

# 6. Tear down (back to ~$0/month)
scripts\down.ps1
```

## CI/CD (Cloud Build)

```bash
gcloud builds submit --config infra/cloudbuild/cloudbuild.yaml \
  --substitutions=_TAG=<git-sha>
```

Builds + pushes the 4 services and the eval pipeline to Artifact Registry, runs the
unit tests (Python/Node/.NET), and **fails the build if the evaluation gate drops
below 0.80** — quality enforced in CI, exactly like the AWS project.

## Repository map

```
├── services/                # gateway (TS), rag-api (Python), dotnet-ingest (C#), evaluator
├── infra/
│   ├── terraform/environments/dev/   # VM, Cloud Run, BigQuery, AR, budget, GKE(opt)
│   ├── helm/ai-platform/             # charts for the optional GKE demo
│   └── cloudbuild/                   # CI/CD pipeline with eval gate
├── mlops/
│   ├── bigquery/            # eval-to-bq pipeline (Cloud Run job)
│   └── ...
├── scripts/                 # up/down/status/deploy (gcloud-based)
└── docs/
```