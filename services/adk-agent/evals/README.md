# Phase 4 - evaluation

**Status:** scaffolded. The eval set and config are validated by unit tests; the
capture, ADK trajectory eval and RAGAS/Vertex arm have **not** been run yet. The
`eval_reports` table has the new nullable trajectory columns.

Phase 4 answers two separate questions:

1. **Did the agent choose the right tools, in the right order?** That is the ADK
   trajectory eval. It is deterministic per case and cheap to read.
2. **Was the answer grounded and relevant?** That is the existing RAGAS/Vertex arm,
   run over the agent's own answers and the contexts the tools returned.

Keeping them separate matters: a correct tool sequence can still produce an
ungrounded answer, and a plausible answer can come from the wrong tool path.

## Files

| File | Purpose |
|---|---|
| `support_agent_v1.evalset.json` | 8 single-turn cases: expected tool trajectory, reference answer |
| `test_config.json` | ADK criteria: exact tool trajectory at 1.0, final response judge at 0.7 |
| `run_phase4.py` | `capture`, `score`, `load` subcommands |
| `../support_agent/eval_support.py` | case access, trajectory comparison, BigQuery row mapping |
| `../tests/test_phase4_evals.py` | validates the eval set/config and the pure logic; no model calls |

## Two inference runs, on purpose

`adk eval` owns the official trajectory and final-response score. It does not expose
the retrieved passages.

The capture run executes the same cases through the same `root_agent` and records the
final answer, the tool calls, and the tool responses. Those contexts are what RAGAS
needs. It is a second model run; that cost is the price of not approximating contexts
from the knowledge base afterwards.

The ADK eval and the capture run may disagree on a tool call because the model is
probabilistic. Record both; do not reconcile them by hand.

## Prerequisites

- The agent's dependencies: `services/adk-agent/requirements-dev.txt`.
- For scoring: a Python environment with `services/evaluator/requirements-ragas.txt`.
- For loading: `google-cloud-bigquery` and ADC.
- A running `rag-api` and the corpus. For a local capture:
  ```powershell
  docker compose up -d postgres rag-api
  python services/rag-api/scripts/ingest_corpus.py --url http://localhost:8010
  ```
- Asset rows in the dataset the capture will read. While the five-day demo is up,
  `agent_demo_data.assets` has them. **Before destroying the demo**, either run phase 4
  or seed a permanent `agent_eval_data` dataset and set `ASSETS_DATASET` to it.

The rail/utilities corpus is synthetic; these scores are a prototype measurement, not a
benchmark.

## Run

From `services/adk-agent`:

```powershell
$env:GOOGLE_GENAI_USE_VERTEXAI = "true"
$env:GOOGLE_CLOUD_PROJECT      = "gcp-proof-platform"
$env:GOOGLE_CLOUD_LOCATION     = "global"

# live BQ assets, local retrieval, no HITL rows in BigQuery
$env:ASSETS_SOURCE      = "bigquery"
$env:BQ_PROJECT         = "gcp-proof-platform"
$env:ASSETS_DATASET     = "agent_demo_data"
$env:ESCALATION_SINK    = "file"
$env:ESCALATION_FILE    = "artifacts/phase4/escalations.jsonl"
$env:RAG_API_URL        = "http://localhost:8010"
$env:RAG_API_AUDIENCE   = ""

python evals/run_phase4.py capture
```

Then the official ADK eval:

```powershell
adk eval support_agent evals/support_agent_v1.evalset.json `
  --config_file_path evals/test_config.json `
  --num_runs 1 --print_detailed_results
```

`--num_runs 1` keeps the cost down; repeat runs are a variance study, not a first
look. The config disables per-run sampling variations with `num_samples: 1` for the
judge.

Score the captured answers with the existing RAGAS/Vertex arm (in the RAGAS
environment; this subcommand does not import ADK):

```powershell
python evals/run_phase4.py score --captured artifacts/phase4/captured.jsonl `
  --arm vertex --label phase4-agent --skip-trace
```

Drop `--skip-trace` when the per-statement trace is wanted; it adds one judge call per
sample.

Shape and inspect the BigQuery rows, then load:

```powershell
python evals/run_phase4.py load `
  --report artifacts/phase4/ragas/<run>.json `
  --trajectory artifacts/phase4/trajectory.json --dry-run

python evals/run_phase4.py load `
  --report artifacts/phase4/ragas/<run>.json `
  --trajectory artifacts/phase4/trajectory.json
```

The `eval_reports` schema was extended in
`infra/terraform/environments/dev/schemas/eval_reports.json` with nullable columns:
`case_kind`, `expected_tools`, `actual_tools`, `tool_trajectory_score`,
`tool_trajectory_passed`. Existing evaluator rows leave them null. The table change was
applied in place.

## Cases

| eval_id | Expected path | What it protects |
|---|---|---|
| `lookup_status` | `lookup_record` | asset facts come from the register |
| `lookup_missing` | `lookup_record` | no invented asset; escalate offered |
| `procedure_oil` | `search_knowledge` | procedure comes from the corpus |
| `safety_authority` | lookup, search, escalate | refusal plus a real hand-off |
| `out_of_domain` | none | no tool spend on trivia |
| `asset_procedure` | lookup, search | record plus procedure, not one without the other |
| `decommissioned_asset` | `lookup_record` | do not apply a live procedure to a dead asset |
| `pii_escalation` | lookup, search, escalate | refusal and redacted escalation |

`tool_trajectory_avg_score` is **EXACT** with `ignore_args: true`. Extra tools fail the
case: over-calling costs latency and noise. Tool arguments are covered by the tool unit
tests and by the capture row's `actual_tools`; the ADK metric is about selection and
order, not query wording, which varies legitimately.

The final-response judge is `gemini-3-flash-preview` with one sample and a 0.7
threshold. It compares the actual answer with the reference answer semantically. It is
probabilistic; treat a borderline score as a prompt question, not a verdict.

## First run: what to expect

The live smoke run showed the model sometimes adds `search_knowledge` after a
`lookup_record` failure, or searches when a record would be enough. Those cases will
fail EXACT. That is the finding, not a reason to relax the cases. Read the capture
trajectories first, then decide whether the prompt should be tightened or the case was
wrong.

The ADK eval writes its own result output; keep it with the RAGAS report and the
capture JSONL under `artifacts/phase4/` and copy the evidence into
`evidence/adk-agent/` once a run is worth keeping.

## Not measured

- Human labels or inter-rater agreement.
- Retrieval recall against a labelled gold set; phase 1 measured hit@1/hit@3 on 8
  queries, which is a smaller claim.
- Latency and cost per case beyond what the ADK result reports.
- Multi-turn conversations. The eval set is single-turn; the escalation flow may need
  a confirming follow-up, which is phase 4b.
- Production safety: the corpus and assets are synthetic; this is a prototype.

## Feedback loop

If a case fails, first check whether the agent's tool choice was wrong or the expected
trajectory was too strict. Change the prompt or the case, re-run, and record both runs.
Do not edit the reference answer to match the output. The point of the set is to keep
that temptation visible.
