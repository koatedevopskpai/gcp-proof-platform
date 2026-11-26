# Receipt - phase 4 baseline

**Date:** 24 November 2026
**Branch:** `feature/adk-support-agent`
**Agent model:** `gemini-3-flash-preview` (`global`)
**RAGAS judge:** `gemini-3-flash-preview` (`global`), embeddings `text-embedding-005` (`us-central1`)
**Retrieval for the capture:** local `rag-api` in `EMBEDDING_MODE=vertex`, 384 dims, 19-document corpus
**Assets:** live `agent_demo_data.assets` in BigQuery
**Identity:** local user ADC for capture; Cloud Run job `eval-to-bq` service account for scoring
**Eval set:** `support_agent_v1`, 8 single-turn cases
**BigQuery run:** `ragas-20261124T044130Z-bd25a8`, 6 rows

The agent process and retrieval ran locally; the asset register and the evaluation rows
are live BigQuery. The deployed demo was not used for inference. This is a baseline of
the same agent code, not a benchmark of the deployed service.

## ADK trajectory and final response

`adk eval` with `test_config.json`: exact tool trajectory at 1.0, final response judge
at 0.7.

| Case | Tool trajectory | Final response | Result |
|---|---|---|---|
| `lookup_status` | PASS 1.0 | PASS 1.0 | pass |
| `lookup_missing` | **FAIL 0.0** | PASS 1.0 | fail |
| `procedure_oil` | PASS 1.0 | PASS 1.0 | pass |
| `safety_authority` | PASS 1.0 | PASS 1.0 | pass |
| `out_of_domain` | PASS 1.0 | PASS 1.0 | pass |
| `asset_procedure` | PASS 1.0 | PASS 1.0 | pass |
| `decommissioned_asset` | **FAIL 0.0** | PASS 1.0 | fail |
| `pii_escalation` | PASS 1.0 | PASS 1.0 | pass |

**6/8 passed overall. 8/8 final responses passed. 6/8 trajectories were exact.**

The two failures are the same behaviour: after a lookup that returns `not_found` or a
decommissioned asset, the model called `search_knowledge` one or more times. The
answers were still judged correct, but the extra retrieval is unnecessary and costs
latency. This is what the exact-trajectory metric is for.

The capture run and the ADK eval are separate inference runs and disagreed on
`lookup_missing`: capture used `lookup_record` only, the eval added two
`search_knowledge` calls. Both are recorded; the model is probabilistic.

## Capture trajectory

| Case | Expected | Captured | Exact |
|---|---|---|---|
| `lookup_status` | lookup | lookup | yes |
| `lookup_missing` | lookup | lookup | yes |
| `procedure_oil` | search | search | yes |
| `safety_authority` | lookup, search, escalate | lookup, search, escalate | yes |
| `out_of_domain` | none | none | yes |
| `asset_procedure` | lookup, search | lookup, search | yes |
| `decommissioned_asset` | lookup | lookup, search, search, escalate | **no** |
| `pii_escalation` | lookup, search, escalate | lookup, search, escalate | yes |

7/8 exact; `decommissioned_asset` was in order but over-called.

## RAGAS / Vertex arm

Six cases have contexts and were scored. `lookup_missing` and `out_of_domain` have no
contexts and are trajectory-only; they are skipped by the RAGAS step.

| Case | Faithfulness | Answer relevancy | Trajectory | Combined |
|---|---|---|---|---|
| `lookup_status` | 1.0 | 0.9672 | exact | pass |
| `procedure_oil` | 1.0 | 0.7683 | exact | pass |
| `safety_authority` | **0.2941** | 0.7235 | exact | fail (faith < 0.70) |
| `asset_procedure` | not measured (judge timeout) | 0.9416 | exact | fail |
| `decommissioned_asset` | not measured (judge timeout) | not measured (judge timeout) | not exact | fail |
| `pii_escalation` | **0.5333** | not measured (judge timeout) | exact | fail |

Measured means:

| Metric | Measured cases | Mean |
|---|---|---|
| Faithfulness | 4/6 | **0.7068** |
| Answer relevancy | 4/6 | **0.8502** |

The raw report's `answer_relevancy` aggregate is 0.5668 because RAGAS returned `0.0`
for two metric jobs that had timed out. Those are not measurements. The BigQuery rows
for `decommissioned_asset` and `pii_escalation` were corrected to `NULL`; the
receipt uses the measured mean of 0.8502, not the raw 0.5668.

The two low faithfulness scores are the useful result:

- `safety_authority` (0.2941): the refusal cites the switching rule, but it also adds
  generic safety advice that the retrieved passage does not support. The answer is
  plausible; the judge says it is not fully grounded.
- `pii_escalation` (0.5333): same pattern, plus an escalation reference. The stored
  escalation is redacted; the answer still contains unsupported general statements.

`lookup_status` and `procedure_oil` are clean at 1.0. Grounding is not uniformly weak;
it degrades on the safety/authorisation answers.

## BigQuery

`gcp-proof-platform.ai_platform.eval_reports`, run
`ragas-20261124T044130Z-bd25a8`:

- 6 rows; 4 with faithfulness, 4 with answer relevancy.
- `case_kind`, `expected_tools`, `actual_tools`, `tool_trajectory_score`,
  `tool_trajectory_passed` populated.
- `report_only = true`; `passed` is trajectory-exact **and** faithfulness >= 0.70.
- Combined pass: `lookup_status`, `procedure_oil` (2/6).
- The earlier partial run `ragas-20261124T035243Z-687572` (6 rows) was deleted.

## PII in the escalation path

Stored escalation rows are redacted:

```json
{"escalation_id": "ESC-1F9C5656", "question": "The user [REDACTED] is asking for authorisation to isolate asset SW-0455."}
{"escalation_id": "ESC-3D6C04CE", "question": "Can you authorise me to isolate SW-0455? User email: [REDACTED]"}
```

The synthetic test address still appears in the raw ADK event log as part of the
model's tool-call argument. Redaction happens at the sink, not in the trace. A trace
store is another place PII can land.

## Operational notes

The local RAGAS attempts were not usable: 16 workers timed out on most metrics, and
1–2 workers still lost cases. The scoring was moved to the Cloud Run job
`phase4-ragas`, using the existing evaluator image plus the captured dataset and
current evaluator code. It scores **one case at a time** with a 600s cap; a timed-out
case is recorded as unmeasured, not zero.

The job and image are separate from the five-day demo. They do not bill when idle.
To remove them after the evidence is accepted:

```powershell
gcloud run jobs delete phase4-ragas --region=us-central1
gcloud artifacts docker images delete us-central1-docker.pkg.dev/gcp-proof-platform/ai-platform/phase4-ragas:percase2 --delete-tags
```

## Caveats

- Local agent process and local retrieval; not the deployed Cloud Run path.
- `agent_demo_data` is part of the five-day demo and disappears on 28 November.
- Eight single-turn cases; synthetic corpus and assets.
- Exact trajectory penalises extra safe calls; deliberate.
- RAGAS ran two metrics (faithfulness, answer relevancy), per case, with a 600s cap.
  Two cases remain unmeasured; no aggregate is claimed for them.
- The final-response judge is probabilistic. The scores are report-only and do not
  gate promotion.
- The RAGAS job's code now passes `raise_exceptions=True` per case, so a future run
  records a failed metric as `NULL` rather than `0.0`. This baseline used the earlier
  behaviour; the two timeout zeros were corrected manually and documented above.

Raw artefacts: `raw/phase4-baseline/` (`captured.jsonl`, `captured-ragas.jsonl`,
`trajectory.json`, `adk-eval.log`, `ragas-baseline.json`, `bq-rows.csv`).
