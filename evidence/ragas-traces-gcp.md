# RAGAS + statement traces on GCP — Phase 2 receipt

**Date:** 19 November 2026
**Branch:** `phase-2/ragas-traces` (from `main` @ `e9df6c6`)
**Dataset:** `services/evaluator/datasets/ragas_set.jsonl` — 10 cases, stored answers
**Judge:** `gpt-4o-mini`, temperature 0 · **Embeddings:** `text-embedding-3-small`
**Framework:** `ragas==0.4.4` with the pins in `requirements-ragas.txt`

Two identical runs, 10 cases each, no live service — every answer is stored, so the scoring is
what is under test, not generation.

| | Run A | Run B |
|---|---|---|
| Run id | `ragas-20261119T001558Z-29fdee` | `ragas-20261119T001834Z-d162b9` |
| Duration | 143.3 s | 138.9 s |
| RAGAS judge cost | $0.012451 | $0.012321 |
| Trace cost | $0.000891 | $0.000894 |
| Faithfulness (aggregate) | 0.6333 | 0.6667 |

## Per-case results

| Case | RAGAS faith A | RAGAS faith B | Trace A | Trace B | RAGAS relevancy A → B | RAGAS correctness A → B |
|---|---|---|---|---|---|---|
| `o02-refund` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.8939 → 0.8939 | 0.9558 → **0.8058** |
| `o02-software` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9381 → 0.9381 | 1.0000 → 1.0000 |
| `o02-meals` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 → 1.0000 | 1.0000 → 1.0000 |
| `heldout-travel` | 1.0000 | 1.0000 | **0.5000** | 0.5000 | 0.0000 → 0.0000 | 0.8956 → 0.8958 |
| `heldout-hardware` | 1.0000 | 1.0000 | **0.5000** | 0.5000 | 1.0000 → 1.0000 | 0.9038 → 0.9038 |
| `heldout-retention` | **0.3333** | 0.3333 | 0.6667 | 0.6667 | 0.8259 → 0.7891 | 0.5584 → 0.5584 |
| `control-verbatim-retention` | **0.3333** | **0.6667** | 1.0000 | 1.0000 | 0.6816 → 0.7214 | 0.7500 → **1.0000** |
| `control-verbatim-distracted` | 0.3333 | 0.3333 | 0.6667 | 0.6667 | 0.8259 → 0.7891 | 0.5584 → 0.5584 |
| `control-unsupported-number` | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.6594 → 0.7465 | 0.4725 → 0.4725 |
| `control-unsupported-subtle` | 0.3333 | 0.3333 | 0.5000 | 0.5000 | 0.7214 → 0.7188 | 0.4744 → 0.5244 |

## Findings

### 1. A verbatim answer scores 0.3333 with **one** clean context

The Phase 0 audit matched the RAGAS case by reproducing its three-context retrieval set, which left
open the possibility that distractor documents caused the low score. This run closes that:
`control-verbatim-retention` has a single context, the answer is character-identical, and RAGAS
scores it **0.3333** in run A and **0.6667** in run B.

So the failure belongs to RAGAS's faithfulness decomposition, not to the retrieval set. The Phase 0
distractor control is still useful — it is the case where the GCP judge and RAGAS disagree by the
widest margin — but it is not the cause.

### 2. RAGAS is not reproducible case by case

Between two identical runs on stored answers:

- **7 of 10 cases** differ on at least one metric.
- Faithfulness moves by **+0.3334** on `control-verbatim-retention`.
- Answer correctness moves by **−0.1500** on `o02-refund` and **+0.2500** on the verbatim control.
- Answer relevancy moves by up to **0.0871**.

The aggregate moved 0.0334 — small, and exactly the kind of number that would look stable while
individual cases were not. This is the empirical case for reporting per case and never gating on the
mean.

### 3. The statement trace was identical across both runs

Every statement and every verdict matched between run A and run B. That is a better stability result
than RAGAS, on two runs and ten cases — not proof, but enough to be worth keeping.

It also disagrees with RAGAS in both directions:

| Case | RAGAS faithfulness | Trace | Who is right |
|---|---|---|---|
| `control-verbatim-retention` | 0.3333 / 0.6667 | 1.0000 | the trace |
| `heldout-travel` | 1.0000 | 0.5000 | arguably the trace — the answer says "three-hour flight", the context approves economy "under four hours"; the trace's second statement is the inference, not a quote |
| `control-unsupported-number` | 0.0000 | 0.0000 | agree |

The trace is inspectable, which is the point. For the verbatim control it produces:

```
- Customer data must be deleted.                      supported — the context specifies a timeframe
- The deletion must occur within 30 days.             supported — the context states 30 days
- The deletion is required after contract termination. supported — the context states this
```

RAGAS returns `0.3333` for the same input and no way to see which claim it discounted.

### 4. Neither number may gate

Both are judge-based. The trace is more stable and more explainable, not correct by construction —
`heldout-travel` shows it treating an inference as unsupported. This does not change the gate: it
stays deterministic (`evidence/eval-gate-split.md`).

## Cost

$0.0133 per run for 10 cases (RAGAS $0.0125 + trace $0.0009), about 2.5 minutes. The gate image does
not carry these dependencies; `requirements-ragas.txt` is installed only where scoring runs.

## Limits

- Stored answers from the AWS run and this repo's controls; not a benchmark, not live generation.
- One judge model, two runs, ten cases. The stability claim is directional.
- Both metrics are LLM-judged; there are no human labels and no kappa.
- Traces were written to the local filesystem. The GCS sink is implemented and unit-tested but was
  not exercised against a bucket.

## Reproduce

```sh
docker build -t gcp-eval-ragas -f /tmp/ragas.Dockerfile .   # requirements-ragas.txt only

docker run --rm -e OPENAI_API_KEY -e OPENAI_BASE_URL \
  -e JUDGE_MODEL=gpt-4o-mini -e EMBEDDING_MODEL=text-embedding-3-small \
  -v "$PWD:/src" -w /src gcp-eval-ragas \
  python scripts/ragas_run.py --label local-1

docker run --rm -v "$PWD:/src" -w /src gcp-eval-ragas \
  python scripts/ragas_diff.py artifacts/ragas/<a>.json artifacts/ragas/<b>.json
```
