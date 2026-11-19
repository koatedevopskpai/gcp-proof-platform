# Receipt — evaluation pipeline running on GCP

**Date:** 19 November 2026
**Project:** `gcp-proof-platform` (number `353662139603`)
**Execution:** `eval-to-bq-lqzl7`, 00:57:54Z → 01:00:37Z (163 s), succeeded
**Image:** `us-central1-docker.pkg.dev/gcp-proof-platform/ai-platform/eval-to-bq@sha256:c3004f0c…`
**Code:** branch `phase-3/gcp-integration`, `d1e1b51` plus the `google-cloud-storage` dependency
**Trace:** `gs://gcp-proof-platform-eval-traces/ragas/ragas-20261119T005937Z-8f5e3c.jsonl` (12.7 KB, 10 samples)
**Dataset hash:** `0fd41c8a…` (`ragas_set.jsonl`, 10 cases)

This is the first execution of the pipeline against real GCP services. It ran the deterministic
gate, scored the RAGAS set with `gpt-4o-mini`, wrote one trace object to GCS and loaded four rows
into BigQuery.

## What the run produced

**Gate (4 cases, provider arm):** passed. Retrieval MAP@4 and nDCG@4 both 1.0; judge mean 0.9375,
reported only.

**RAGAS (10 cases):**

| Case | Faithfulness | Answer relevancy | Statement trace |
|---|---|---|---|
| `o02-refund` | 1.0 | 0.8938 | 1.0 |
| `o02-software` | 1.0 | 0.9381 | 1.0 |
| `o02-meals` | 1.0 | 1.0 | 1.0 |
| `heldout-travel` | 1.0 | 0.0 | 0.5 |
| `heldout-hardware` | 1.0 | 1.0 | 0.5 |
| `heldout-retention` | **0.3333** | 0.7891 | 0.6667 |
| `control-verbatim-retention` | **0.3333** | 0.7214 | 1.0 |
| `control-verbatim-distracted` | 0.3333 | 0.8260 | 0.6667 |
| `control-unsupported-number` | 0.0 | 0.6591 | 0.0 |
| `control-unsupported-subtle` | 0.3333 | 0.7188 | 0.5 |
| **Aggregate** | **0.6333** | **0.7546** | — |

The 0.3333 for the verbatim answer reproduces in the deployed job, on the same case and with the
same value as the local run A. The statement trace again says 1.0 for that case, with three
supported statements and reasons in the object.

**BigQuery** (`ai_platform.eval_reports`, run `ec56f651-0e5e-4795-8a96-6dffa20e4b4e`, 4 rows):

| report_date | case_id | judge_model | passed | faithfulness | trace_uri |
|---|---|---|---|---|---|
| 2026-11-19 | case-1..4 | gpt-4o-mini | true | 1.0, 1.0, 1.0, 0.8 | `gs://…/ragas-20261119T005937Z-8f5e3c.jsonl` |

## Cost

| Item | Measured |
|---|---|
| RAGAS judge | 94 requests, 70,505 tokens, **$0.012412** |
| Statement trace | 31 calls, 3,032 + 725 tokens, **$0.00089** |
| Job runtime | 163 s at 2 vCPU / 2 GiB (within free tier at this volume) |
| **This execution** | **≈ $0.014** |

Not an invoice: provider cost is computed from the reported token usage and the price basis in the
report; the job cost is an estimate from runtime.

## What was applied, and what was not

Applied (`terraform apply`, targeted to the evaluation path):

- BigQuery schema: `run_id`, `case_id`, `judge_model`, `trace_uri`, `report_only` (additive)
- `eval-to-bq` job: 2 vCPU / 2 GiB / 1800 s, `max_retries = 0`, secret-mounted key, `RAGAS_ENABLED=1`
- Trace bucket `gcp-proof-platform-eval-traces` with write-only access for the eval SA
- Secret `eval-judge-api-key` (one version; value never in Terraform state)
- **Destroyed:** the daily Cloud Scheduler job and its token-creator binding

Not applied: the always-on VM, VPC, Workload Identity Federation, monitoring SLO/dashboard, WIF CI
identity. The plan's `terraform plan` showed 29 additions including those; they were deliberately
left out to keep the eval path at roughly **$1/month** instead of **$14/month**.

## Limits

- The image was built and pushed from this workstation, not Cloud Build, so there is **no Cloud
  Build run id**. The digest is recorded above.
- One execution, one judge model, one point in time. Re-running will produce different numbers —
  that is the finding, not a flaw.
- Stored answers, not a live service. No traffic, no SLO, no on-call.
- Provider spend is computed, not invoiced; the job cost is an estimate.
- `refs` and provenance are in the report and the trace; BigQuery carries the pointer, not the
  trace body.

## Reproduce

```bash
gcloud run jobs execute eval-to-bq --region us-central1 --project gcp-proof-platform

bq query --use_legacy_sql=false '
  SELECT report_date, run_id, case_id, judge_model, passed, faithfulness, trace_uri
  FROM `gcp-proof-platform.ai_platform.eval_reports`
  ORDER BY report_date DESC LIMIT 8'

gcloud storage cat gs://gcp-proof-platform-eval-traces/ragas/<run>.jsonl | head -1
```
