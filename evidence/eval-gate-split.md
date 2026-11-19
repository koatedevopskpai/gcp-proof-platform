# Phase 1 receipt — gate split from report

**Date:** 19 November 2026
**Branch:** `phase-2/fix-ai-judge-issue` @ `122fd60` (rebased on `main` @ `aba9145`)
**Code:** `services/evaluator` (main.py rewritten), `tests/test_gate_split.py` added
**Evidence:** `evidence/eval-gate-audit.md` (the audit this responds to)

---

## What changed

| Before | After |
|---|---|
| `aggregate = (faithfulness + answer_relevancy) / 2` decided `passed` | Gate is deterministic; judge scores are reported |
| Judge score below 0.80 failed the build | Judge score cannot change the exit code |
| `passed` meant "the judge average cleared 0.80" | `passed` means the gate cleared |
| Report had no arm/model/run id (fixed on this branch) | Provenance + usage in every report |
| A judge HTTP error became `0.5` (fixed on this branch) | Judge error is exit 2 with an `error` field |

The gate now checks three deterministic things:

1. **Retrieval** — mean MAP@4 and nDCG@4 must be ≥ `--threshold` (default 0.80).
2. **Structure** — every record has an answer, contexts and retrieved ids.
3. **Numeric consistency** — every number in the answer must appear in the reference or
   in the contexts. This is what catches a changed limit ("30 days" → "90 days").

Reported but never gated: faithfulness, answer relevancy, ROUGE-L.

## Result on the Phase 0 controls

Lexical arm. `python -m evaluator --dataset … --threshold 0.80`.

| Dataset | Exit | Gate | MAP@4 | nDCG@4 | Judge faithfulness | ROUGE-L | Gate failure |
|---|---|---|---|---|---|---|---|
| `control_verbatim` | 0 | pass | 1.0 | 1.0 | 1.0 | 1.0 | — |
| `control_verbatim_distracted` | 0 | pass | 1.0 | 1.0 | 1.0 | 0.7059 | — |
| `control_unsupported` (90 days) | **1** | fail | 1.0 | 1.0 | 0.55 | 0.6452 | `record 0: unsupported number(s): 90` |
| `control_unsupported_subtle` | 0 | **pass** | 1.0 | 1.0 | 0.5238 | 0.6875 | — |
| `eval_set` | 0 | pass | 1.0 | 1.0 | 0.6781 | 0.4110 | — |

A low judge score cannot fail the gate: `test_a_low_judge_score_cannot_fail_the_gate`
stubs both judge metrics to 0.0 and still exits 0 with the gate passed.

## Where this does *not* match the plan's acceptance

The rewritten Phase 1 acceptance said "the four controls give the verdicts in the audit
table". They do not, and the difference is the point:

- In the audit, **both** unsupported controls failed — the judge rejected the subtle one
  because faithfulness dropped to 0.52.
- Under the deterministic gate, the subtle control **passes**: its claim ("a copy is
  retained indefinitely") contains no number, so none of the three checks sees it.

That is the trade the project makes deliberately: a probabilistic score that also scored
a verbatim answer 1.0 while RAGAS scored it 0.3333 — and moved 0.25 between identical
runs — is not allowed to block a build. The consequence is real: **numeric-free
unsupported claims are no longer blocked at the gate.** The judge still reports them, and
`test_unsupported_sentence_without_a_number_passes_the_gate` states it as a test rather
than leaving it in prose.

If that gap has to close, the options are:
1. A deterministic claim-level check against the context (hard: paraphrase).
2. A calibrated judge used as a **warning** or review trigger, not a gate.
3. A human review step for answers above a risk threshold.

None of those is in this phase.

## Other consequences

- `aggregate_score` keeps its meaning (judge mean) and stays in the BigQuery column;
  `passed` now means the gate. Both are in the report, so the row is not ambiguous to a
  reader who knows the split.
- A dataset with no `ground_truth` no longer errors: there is simply no ROUGE-L, and
  retrieval still gates. The previous "no scorable records → exit 2" path is gone.
- BigQuery still has nine columns; provenance (`run_id`, arm, model, dataset hash,
  commit) is report-only until the additive schema migration in the plan's Phase 3.

## Verification

- `pytest services/evaluator/tests` → **24 passed** (5 new in `test_gate_split.py`).
- The five-row matrix above is reproducible in one container run; reports in `artifacts/`.
- `terraform fmt -check` clean; Cloud Build config parses (17 steps).

## Reproduce

```sh
docker run --rm -v "$PWD:/src" -w /src/services/evaluator python:3.12-slim \
  sh -c "pip -q install -r requirements.txt && python -m evaluator \
         --dataset datasets/control_unsupported.jsonl --threshold 0.80"
# exit 1, gate failure: unsupported number(s): 90
```
