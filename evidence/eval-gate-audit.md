# Evaluation-gate audit — does the GCP gate reject correct answers?

**Date:** 18 November 2026
**Source revision:** `gcp-proof-platform` @ `67b0a05` (recorded as `11fdac0` before the 18 Nov history
rewrite; the evaluator code is unchanged by it. Datasets added, listed below)
**Grade:** E3 — dated local run against an external provider, output recorded. E4 would require recorded
provider cost, which this code cannot produce (§7).
**Question:** H0 — the current GCP gate rejects a correct, verbatim-supported answer.

---

## Why this was asked

`ai-platform-proof` measured a RAGAS faithfulness of **0.3333** for an answer that was
character-identical to its retrieved context (`evidence/ragas-eval.md`, §"Faithfulness 0.3333 for a
verbatim copy"). `gcp-proof-platform` gates builds on a different judge — a single-prompt LLM score
with a lexical fallback — at a **0.80** threshold. Before porting anything, the question was whether
that gate has the same failure, a different one, or none.

## Method

Five controls, each run through the shipped CLI (`python -m evaluator --threshold 0.80`) in a
`python:3.12-slim` container (`@sha256:5e2bdb1b…`), one arm at a time — 11 scored runs, plus repeat
passes over all five datasets to test determinism and judge stability:

- **lexical** — no `OPENAI_API_KEY`, i.e. the arm the Cloud Run job actually runs today (the job has
  no provider credential).
- **provider** — `gpt-4o-mini`, `temperature=0`, via `OPENAI_BASE_URL=https://api.openai.com/v1`.

| Dataset (SHA-256) | What it is |
|---|---|
| `datasets/control_verbatim.jsonl` (`b7c83924…`) | The RAGAS retention sentence, answer character-identical to a **single** clean context |
| `datasets/control_verbatim_distracted.jsonl` (`9d1de607…`) | Same question and answer, with the **same three contexts and retrieved ids, in the same order** as the RAGAS run that scored 0.3333 |
| `datasets/control_unsupported.jsonl` | Same context, answer changes 30 → 90 days and permits indefinite retention |
| `datasets/control_unsupported_subtle.jsonl` | Correct sentence, plus one unsupported claim ("a copy is retained indefinitely for analytics and model training") |
| `datasets/eval_set.jsonl` (`1a01811d…`) | The four shipped gate cases, unchanged |

## What runs in production (verified, not assumed)

Two different call sites, both using the lexical arm, neither recording that fact:

| Call site | Definition | Arm | Effect of a low score |
|---|---|---|---|
| Cloud Build `eval-gate` step | `infra/cloudbuild/cloudbuild.yaml` | lexical — no provider env in the step | **fails the build** (non-zero exit) |
| Scheduled job `eval-to-bq` | `infra/terraform/environments/dev/cloudrun.tf` (env: `PROJECT_ID`, `BQ_DATASET`, `BQ_TABLE` only — no secret, no `JUDGE_MODEL`) | lexical | **writes `passed=false` and exits 0** — `mlops/bigquery/run_pipeline.py` accepts rc 1 and only raises on other codes |

So the number that can block a build is the 0.839 lexical aggregate over four cases, and the number
that is recorded daily is the same one, unenforced. The Cloud Run job's own monitoring alert fires on
crashes, not on `passed=false`.

## Results

| # | Dataset | Arm | Faithfulness | Relevancy | Aggregate | Exit |
|---|---|---|---|---|---|---|
| 1 | control_verbatim | lexical | 1.0000 | 1.0000 | **1.0000** | 0 |
| 2 | control_verbatim | provider | 1.0000 | 1.0000 | **1.0000** | 0 |
| 3 | control_verbatim_distracted | lexical | 1.0000 | 1.0000 | **1.0000** | 0 |
| 4 | control_verbatim_distracted | provider | 1.0000 | 1.0000 | **1.0000** | 0 |
| 5 | control_unsupported | lexical | 0.5500 | 1.0000 | 0.7750 | 1 |
| 6 | control_unsupported | provider | 0.0000 | 0.8000 | 0.4000 | 1 |
| 7 | control_unsupported_subtle | lexical | 0.5238 | 1.0000 | 0.7619 | 1 |
| 8 | control_unsupported_subtle | provider | 0.5000 | 0.8000 | 0.6500 | 1 |
| 9 | eval_set.jsonl (shipped) | lexical | 0.6781 | 1.0000 | **0.8390** | 0 |
| 10 | eval_set.jsonl (shipped) | provider | 0.9500 | 0.9250 | **0.9375** | 0 |
| 11 | control_verbatim | **deliberately invalid key** | 0.5000 | 0.5000 | 0.5000 | 1 |

**Repeat pass** (`repro.ps1`, same day, independent invocation): all five lexical reports came back
byte-identical to runs 1, 3, 5, 7 and 9. The provider arm reproduced four of five aggregates exactly;
`control_unsupported_subtle` moved **0.65 → 0.40** (faithfulness 0.5 → 0.0, relevancy 0.8). Same
verdict, 0.25 of movement on one case.

No report field distinguishes runs 1, 2 and 11. That is finding 3.

---

## Findings

### 1. H0 is not confirmed. The gate passes every correct control, in both arms.

Runs 1–4: the verbatim answer scores 1.0 four times. The gate does not block correct work on this
evidence. The project is therefore **a port plus a separation of gate from report**, not a defect
fix — the second row of the decision table in the plan.

### 2. The two judges disagree on identical input — in opposite directions.

Run 4 and the RAGAS run use the same question, the same answer sentence, the same three context
strings and the same retrieved ids. RAGAS scored faithfulness **0.3333**; this judge scored
**1.0000**. Neither number describes the answer.

The mechanisms differ. RAGAS decomposes the answer into claims and asks a judge to verify each
against the context. This judge asks for one holistic number, and its lexical fallback counts tokens
present in the **union** of contexts — so adding distractor documents can only raise the score. The
distractor set is invisible to it.

Consequence for the plan: the GCP port cannot claim to reproduce the RAGAS result. It has the
complementary failure — a metric that cannot see unsupported content it has already seen the words
for.

### 3. Three different producers write the same number, and nothing records which one ran.

The report contains `records`, `aggregate_score`, `threshold`, `passed`, `metrics` and `per_record`.
It contains no arm, no model id, no run id, no dataset hash, no token usage, no error flag, no
verdict text.

So an aggregate of 0.5 can mean: a lexical heuristic computed 0.5; a model returned 0.5; or
`httpx` raised and `llm._llm_score` returned its constant `0.5` after silently swallowing the
exception (`llm.py:59–61`). Run 11 is the third case: a rejected API key, reported as

```
EVAL GATE FAILED: aggregate 0.500 < threshold 0.80
```

An authentication failure presented as a quality verdict, blocking a build for a reason the report
cannot express.

### 4. Which arm runs is decided by whether a secret exists, and it moves the score by ~0.1.

`eval_set.jsonl` scores **0.839** lexical and **0.9375** provider. The Cloud Run job has no provider
credential, so the deployed gate is the lexical one at 0.839 — 0.039 above the threshold. The same
four cases, same day, differ by 0.0985 depending on an unrecorded deployment fact.

### 5. The shipped gate's headroom is 0.039, and per-case faithfulness is 0.54–0.82 for answers that are all correct.

Lexical per-case faithfulness on `eval_set.jsonl` is 0.5455, 0.7600, 0.5833, 0.8235 for four
correct, grounded answers. The metric responds to paraphrase, not to correctness. A paraphrase-heavy
answer set would fail this gate while being right; a near-verbatim answer set clears it without the
metric checking anything (run 1 is that shape).

### 6. Rejection does work — but only narrowly.

Runs 5–8 show both arms rejecting both unsupported controls, so the gate is not vacuous. But the
margin is thin where it matters: the 90-days fabrication scored 0.7750 lexically, **0.025 below the
threshold**, because `aggregate = (faithfulness + answer_relevancy) / 2` with relevancy pinned at 1.0
gives faithfulness an effective floor of 0.60. By token count, an answer can have 40% of its content
unsupported and still pass.

### 7. Judge spend is unmeasured.

Sixteen provider requests were made in the first pass (runs 2, 4, 6, 8, 10) and sixteen again in the
repeat. `llm.py` discards the response body and any usage counters, so the cost cannot be stated from
the artefacts — a small amount, recorded here as *unknown* rather than estimated. RAGAS in
`ai-platform-proof` captured 45,091 tokens and $0.0077 for 60 requests through a callback; there is no
equivalent hook here.

### 8. The scheduled job records the gate; it does not enforce it.

`run_pipeline.py` runs the evaluator, accepts exit code 1 (`if rc not in (0, 1): raise`), then loads
the rows with `passed=false` and exits 0. The alert on the job fires only when the job itself fails.
Today's daily run therefore generates a row that says quality regressed, and nothing acts on it —
while the build-blocking gate is a different invocation of the same lexical code on the same four
cases. Two call sites, one unlabelled number, two different consequences.

### 9. The lexical arm is deterministic; the provider arm is not.

Two full lexical passes over all five datasets produced **byte-identical** reports (`raw/det-a-*` vs
`raw/det-b-*`), and a third independent pass through `repro.ps1` did the same. That is the property
Phase 1 can rely on.

The provider arm does not have it. A second pass reproduced four of five aggregates exactly and moved
`control_unsupported_subtle` from 0.65 to 0.40 — faithfulness 0.5 → 0.0 on a temperature-0,
single-prompt judge. The verdict did not change, but a 0.25 swing on one case is not something to put
in front of a build.

---

## What this changes in the plan

| Plan item | Change |
|---|---|
| §6 hypothesis | **Answered: not a false negative.** Re-scope the project as port + separation (decision-table row 2) |
| Phase 1 | Fix the demonstrated defects: API failure becomes a hard error (exit 2), not `0.5`; the report records arm/model/run id/dataset hash; the judge block becomes report-only and cannot change the exit code |
| Phase 2 | The distractor control must be kept: it is the case where the two judges disagree, and the only regression test that will catch a future "just use the union of contexts" shortcut |
| Phase 4 receipt | State that GCP's judge and RAGAS disagree on the same input (1.0 vs 0.3333), rather than implying parity |
| Decision D5 | Reusing the six `ai-platform-proof` cases still holds, but add these four controls; one of them is already RAGAS-matched |

## What this does not establish

- That the gate rejects correct answers in general — five controls, one judge model.
- That the provider judge is miscalibrated — no human labels, no kappa. Its instability is now
  observed once (0.65 → 0.40 on one case), which is a reason to distrust it, not a measurement.
- That the lexical arm behaves like the provider arm — it demonstrably does not (§4).
- Anything executed in GCP. The Cloud Run job, BigQuery table and schedule were read, not run.

## Reproduce

```sh
cd C:/Users/koate/development/gcp-proof-platform

# lexical arm (the deployed configuration)
docker run --rm -v "$PWD:/src" -w /src/services/evaluator python:3.12-slim \
  sh -c "pip -q install -r requirements.txt && python -m evaluator \
         --dataset datasets/control_verbatim_distracted.jsonl --threshold 0.80 \
         --report /src/artifacts/control-distracted-lexical.json"

# provider arm
docker run --rm -e OPENAI_API_KEY -e OPENAI_BASE_URL -e JUDGE_MODEL=gpt-4o-mini \
  -v "$PWD:/src" -w /src/services/evaluator python:3.12-slim \
  sh -c "pip -q install -r requirements.txt && python -m evaluator \
         --dataset datasets/control_verbatim_distracted.jsonl --threshold 0.80 \
         --report /src/artifacts/control-distracted-llm.json"

# the silent-fallback demonstration
docker run --rm -e OPENAI_API_KEY="sk-invalid" -e OPENAI_BASE_URL="https://api.openai.com/v1" \
  -v "$PWD:/src" -w /src/services/evaluator python:3.12-slim \
  sh -c "pip -q install -r requirements.txt && python -m evaluator \
         --dataset datasets/control_verbatim.jsonl --threshold 0.80"
```

Reports land in `artifacts/` (git-ignored). Local interpreter is Python 3.14.5, which cannot import
`httpx==0.27.*`; the container is required.

---

## Correction — 20 November 2026

The line above says reports "land in `artifacts/` (git-ignored)". That was not true when it was
written: the `*.json` rule in `.gitignore` carried an inline comment, and Git treats the whole line as
a pattern, so the rule matched nothing and JSON was never ignored. No secret was ever committed, but
local key files were not protected by that rule. Fixed in `c364fec`: the comment is on its own line,
`artifacts/` is ignored explicitly, and the JSON evidence that must be tracked is excepted.

