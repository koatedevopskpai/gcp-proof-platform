# Handoff - demo escalation export and permanent eval assets

**Date:** 27 November 2026
**Purpose:** preserve the demo-specific escalation evidence and remove the last
dependency on `agent_demo_data` before the 28 November teardown.

## Demo escalations exported

`agent_demo_ops.agent_escalations` contained two rows, both synthetic and already
PII-redacted:

| Escalation | Asset | Urgency | Status |
|---|---|---|---|
| `ESC-1CD3C97E` | `SW-0455` | high | open |
| `ESC-46E785F1` | `SW-0455` | normal | open |

Exported to:

```
gs://gcp-proof-platform-eval-traces/phase4/agent_demo_escalations.jsonl
evidence/adk-agent/raw/agent-demo-ops/escalations.jsonl
```

The GCS object survives the demo teardown; the local copy is in the repository.

## Permanent evaluation assets

Created in the dev Terraform root:

- `agent_eval_data` dataset
- `agent_eval_data.assets` table, same `assets.json` schema

Seeded with the seven synthetic fixtures:

```
loaded 7 assets into gcp-proof-platform.agent_eval_data.assets
```

Terraform apply: 2 added, 0 changed, 0 destroyed.

Use this dataset for phase-4 re-runs after the demo is gone:

```powershell
$env:ASSETS_DATASET = "agent_eval_data"
```

The local `rag-api`/Postgres stack and the 19-document corpus remain reproducible;
the demo's `agent_demo_data` and `agent_demo_ops` datasets are temporary and will be
destroyed with the demo.

## Teardown

**Completed 28 November 2026.** The demo compute, database, datasets, secrets, service
accounts, VPC, jobs and demo images are gone. The permanent `agent_eval_data.assets`
dataset remains with seven rows. See
[`2026-11-28-demo-teardown.md`](2026-11-28-demo-teardown.md).

## Cost

BigQuery storage for seven rows and one JSONL object is negligible. No compute was
created for this handoff.
