# Receipt — full platform live, then torn down

**Date:** 19 November 2026
**Project:** `gcp-proof-platform` (`<project-number>`)
**Lifetime:** VM created 01:10:40Z, health returned 200 at 01:19:29Z, stack destroyed by 01:21:36Z
**Commit:** the commit that adds this file (signed)
**Applied:** 25 resources (VM, VPC, WIF, monitoring, CI identities) on top of the evaluation path

This is the always-on half of the platform — the part the earlier receipt deliberately left out
because it costs ~$14/month. It was applied, exercised, evidenced here, and destroyed inside
eleven minutes so the portfolio keeps the proof without the bill.

## What was live

| Resource | Identifier |
|---|---|
| VM | `gcp-proof-platform-dev-app`, `e2-small`, `us-central1-a`, RUNNING, 30 GB `pd-balanced` |
| Addresses | external `<vm-public-ip>`, internal `10.0.0.2` |
| VPC / subnet | `gcp-proof-platform-dev-vpc`, subnet `gcp-proof-platform-dev-app` `10.0.0.0/24`, private Google access |
| Firewall | `tcp:3002,8010,8080` (app), `tcp:22` (SSH) — both from `0.0.0.0/0` as configured |
| WIF pool | `github-pool`, provider `github-oidc`, issuer `token.actions.githubusercontent.com` |
| WIF condition | `assertion.repository_owner == 'koatedevopskpai'` |
| Monitoring service | `gcp-proof-platform-app` ("gcp-proof-platform gateway") |
| SLO | `availability-99` — 99% availability, rolling 30 days |
| Uptime check | `gateway health` → `/health` |
| Dashboard | `gcp-proof-platform` (`aba228d1-04aa-425b-a5b6-d7d61fa4c8fd`) |
| Alert policies | `gcp-proof-platform gateway down`, `eval-to-bq job failed` (both enabled) |

## The proof it ran

Captured at `2026-11-19T01:19:29Z`, `GET http://<vm-public-ip>:3002/health`:

```json
{"status":"ok","services":[{"service":"http://rag-api:8000","status":"ok"},{"service":"http://dotnet-ingest:8080","status":"ok"}]}
```

The gateway is the TypeScript service; the two it reports are the Python RAG API and the .NET
ingest service. Docker Compose was started by the VM's startup script from a clone of this
repository, so that response also proves the deployment path in `startup.sh.tftpl` works.

## What was not applied — the one failure

`google_billing_budget.budget` was rejected by the API:

```
Error 403: billingbudgets.googleapis.com ... SERVICE_DISABLED
Your application is authenticating by using local Application Default Credentials.
The billingbudgets.googleapis.com API requires a quota project, which is not set by default.
```

Terraform was driven by a short-lived OAuth token for `<operator account>`; that service wants a
quota project on the credential, which token auth does not carry. Everything else applied. The
budget is the only piece of the config that has never been created, and it is still pending in the
configuration for the next apply.

## Teardown

`terraform destroy` targeted at the platform resources (the evaluation path was deliberately kept):

```
Destroy complete! Resources: 26 destroyed.
```

Verified afterwards:

| Check | Result |
|---|---|
| Compute instances in the project | **0** |
| VPC networks | only `default` |
| Workload Identity pools | none |
| Uptime checks | **0** |
| Terraform state | 13 resources — the evaluation path only |
| Eval job / trace bucket / secret / tables | still present, still executable |

The public IP is released. The stack existed for roughly eleven minutes and cost well under $0.01
(`e2-small` plus 30 GB `pd-balanced` disk at that duration).

### After the teardown

To show the two halves are independent, the job was executed again with no VM, VPC, WIF or
monitoring in the project:

| | |
|---|---|
| Execution | `eval-to-bq-9ngq4`, 01:22:33Z → 01:24:48Z, succeeded |
| BigQuery rows | 4, run id `c754857c-b324-4a08-b8b3-da77e4f47318` |
| Trace | `gs://gcp-proof-platform-eval-traces/ragas/ragas-20261119T012340Z-0895e9.jsonl` |

The evaluation path depends on Cloud Run, BigQuery, Secret Manager and GCS, not on the platform VM.


## Limits

- The SLO and uptime check were destroyed minutes after creation, so neither produced any measured
  history. They prove the configuration exists, not that it detected anything.
- No Cloud Build run: the VM's images were built on the VM by Compose, and the job image was pushed
  from a workstation earlier. There is still no CI build id in any receipt.
- Monitoring alert policies were created but never fired.
- The VM had SSH open to `0.0.0.0/0` for the window, as configured. That is the repository's
  default and is called out here rather than left implicit.

## Reproduce

```bash
terraform -chdir=infra/terraform/environments/dev apply \
  -var enable_judge=true -var enable_ragas=true
terraform -chdir=infra/terraform/environments/dev output -json

# wait ~6 minutes for the startup script, then
curl http://<vm_ip>:3002/health

# and tear the platform down, keeping the evaluation path
terraform -chdir=infra/terraform/environments/dev destroy -target=google_compute_instance.app ...
```
