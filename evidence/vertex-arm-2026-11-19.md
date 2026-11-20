# Receipt — a second scoring arm on Vertex AI

**Date:** 19 November 2026
**Branch:** `main` (uncommitted at the time of the runs; committed with this file)
**Arm:** `SCORING_ARM=vertex` — `gemini-3-flash-preview` (global), `text-embedding-005` (`us-central1`)
**Control:** `SCORING_ARM=openai` — `gpt-4o-mini`, `text-embedding-3-small`, same image and dataset
**Dataset:** `ragas_set.jsonl`, 10 cases, stored answers

The point of this work was not to replace OpenAI but to compare judges on the same platform with the
same contract: identical metric names, identical trace fields, identical cases. A reviewer can now
ask "which judge, and why" and get a measured answer.

## Deployed — no API key at all

The job was deployed with `enable_judge = false` (so no credential is mounted), `SCORING_ARM=vertex`,
`RAGAS_ENABLED=1`, and executed in Cloud Run:

| | |
|---|---|
| Execution | `eval-to-bq-sbsvq`, 17:53:41Z → 18:02:24Z, succeeded |
| Trace | `gs://gcp-proof-platform-eval-traces/ragas/ragas-20261119T175436Z-91641a.jsonl` (10 samples, 12.5 KB) |
| BigQuery | 4 rows, run `4f0c4b32-760b-4d0d-8bf6-9837492655e4`, `trace_uri` populated |
| Header | `arm=vertex`, `model=gemini-3-flash-preview`, `location=global`, `trace_errors=0` |
| Aggregate | faithfulness **0.8333**, relevancy 0.9560, correctness 0.8475 |
| Usage | RAGAS 91 requests / 71,296 tokens; trace 26 calls / 3,050 tokens; spend unpriced |

That is the claim this arm exists to support: the evaluation ran in Google Cloud using only its
service account. Nothing was mounted from Secret Manager, and no third-party key touched the job.

Two earlier attempts failed and are worth recording: `eval-to-bq-lk9gp` asked Vertex for
`gpt-4o-mini` because the job's `JUDGE_MODEL` leaked into the Vertex arm (fixed by choosing the model
per arm), and `eval-to-bq-jxnnw` hit an `APITimeoutError` on a trace call and lost the whole run
(trace failures are now recorded per case instead of aborting, and the client timeout is 180s with
four retries).

## Keyless by default — 20 November 2026

The judge arm and the scoring arm are now separate settings. `JUDGE_ARM=lexical` (default) keeps the
gate's report free and independent; `SCORING_ARM=vertex` puts the spend where it buys something.
`JUDGE_MODEL` is emitted only for the openai arm, and the judge secret is destroyed by default.

Deployed and executed after that change:

| | |
|---|---|
| Execution | `eval-to-bq-8f6bq`, 10:53:36Z → 11:06:31Z, succeeded |
| Trace | `gs://gcp-proof-platform-eval-traces/ragas/ragas-20261120T105444Z-4df278.jsonl` |
| BigQuery | 4 rows, run `698f0070-1fa6-4725-9ed9-b37226dcc3d0`, `judge_model=lexical` |
| Gate report | faithfulness 0.678 — the lexical values, not a model call |
| Scoring | `arm=vertex`, `gemini-3-flash-preview`, faithfulness 0.8333, `trace_errors=0` |
| Secret Manager | no secrets in the project |

So the earlier deployed run (`eval-to-bq-sbsvq`) had the gate judge on Vertex; that is no longer the
default, and the run above is the configuration a reviewer should read.

## Results

| Run | Arm | Faithfulness | Relevancy | Correctness |
|---|---|---|---|---|
| `ragas-20261119T172014Z-aa64ba` | vertex | **0.8333** | 0.9472 | 0.8566 |
| `ragas-20261119T172654Z-fbe3a4` | vertex | **0.8333** | 0.9517 | 0.8566 |
| `ragas-20261119T173248Z-231ba1` | openai | 0.6333 | 0.7450 | 0.7794 |

Per case:

| Case | Vertex faith (run 1 / 2) | OpenAI faith | Vertex trace | OpenAI trace |
|---|---|---|---|---|
| `o02-refund` | 1.00 / 1.00 | 1.00 | 1.00 | 1.00 |
| `o02-software` | 1.00 / 1.00 | 1.00 | 1.00 | 1.00 |
| `o02-meals` | 1.00 / 1.00 | 1.00 | 1.00 | 1.00 |
| `heldout-travel` | 1.00 / 1.00 | 1.00 | 0.50 | 0.50 |
| `heldout-hardware` | 1.00 / 1.00 | 1.00 | **0.00** | 0.50 |
| `heldout-retention` | 1.00 / 1.00 | **0.33** | 1.00 | 0.67 |
| `control-verbatim-retention` | 1.00 / 1.00 | **0.33** | 1.00 | 1.00 |
| `control-verbatim-distracted` | 1.00 / 1.00 | **0.33** | 1.00 | 0.67 |
| `control-unsupported-number` | 0.00 / 0.00 | 0.00 | 0.00 | 0.00 |
| `control-unsupported-subtle` | 0.33 / 0.33 | 0.33 | 0.33 | 0.50 |

**Vertex faithfulness was identical in 10 of 10 cases across two runs**, and its aggregate did not
move. OpenAI's faithfulness moved on 1 of 10 between runs in the earlier comparison and 7 of 10 on at
least one metric.

The three cases where OpenAI returns **0.33** for a correct answer are the same three that started
this project (`heldout-retention` and the two verbatim controls). Vertex returns **1.00** for all
three. That does not make Vertex "right" — it makes it less conservative, and the trace is the place
to check which it is.

## What is genuinely better about the Vertex arm

- **No API key.** Authentication is the runtime identity: ADC locally, the Cloud Run service account
  in the job. The secret and the `enable_judge` flag become unnecessary for this arm.
- **No third-party egress** for scoring; the data stays in Google Cloud.
- **Stability.** Ten identical faithfulness scores across two runs, against a judge that has moved
  0.25–0.33 on the same inputs.

## How it is implemented, and why not the vendor SDK

`evaluator/vertex_rest.py` talks to two REST endpoints:

- **Chat** through Vertex's OpenAI-compatible surface
  (`…/locations/global/endpoints/openapi/chat/completions`), which the existing `ChatOpenAI`
  adapter can use and which returns plain string content.
- **Embeddings** through `text-embedding-005:predict`, behind a small LangChain `Embeddings` wrapper.

`langchain-google-vertexai` was tried first and its SDK path (`google-cloud-aiplatform`, gRPC) was
unreliable here: one run hung for over an hour, another failed with `DeadlineExceeded` after 60s,
while the same prompts over REST answered in 1.1–3.4 seconds every time. The REST path also keeps
`httpx` at the AWS replication's 0.27.2, because the vendor integration required 0.28.

One transient timeout still appeared on the first trace call of one run; a retry of the same run
completed. That is recorded rather than smoothed over.

## Cost

Vertex spend is **not computed**. Pricing depends on model and region, and a guessed number would be
worse than none, so the report carries tokens only:

```json
{"calls": 31, "prompt_tokens": …, "completion_tokens": …, "estimated_cost_usd": null,
 "pricing": "not applied: Vertex pricing is model- and region-specific"}
```

The OpenAI arm on the same image cost **$0.0133** for the same ten cases, for comparison.

## Limits

- `gemini-3-flash-preview` is a preview model and is only served from the **global** endpoint; a
  regional deployment would need a different model.
- Two runs, ten cases, one project, stored answers. Directional, not a benchmark.
- The trace is judge-based too, and it disagreed with itself on two cases between Vertex runs
  (`o02-refund`, `heldout-hardware`) — a reminder that the trace is more explainable, not infallible.
- No human labels, no kappa, no inter-judge agreement analysis beyond the per-case table above.

## Reproduce

```bash
docker build -t gcp-eval-ragas -f /tmp/ragas.Dockerfile .

docker run --rm -v "$PWD:/src" -v "$HOME/.config/gcloud/application_default_credentials.json:/adc.json" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json -e GOOGLE_CLOUD_PROJECT=gcp-proof-platform \
  -w /src gcp-eval-ragas python -u scripts/ragas_run.py --arm vertex --project gcp-proof-platform

docker run --rm -v "$PWD:/src" -e OPENAI_API_KEY -w /src gcp-eval-ragas \
  python -u scripts/ragas_run.py --arm openai
```
