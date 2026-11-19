"""Schema shared with `ai-platform-proof`, so the two evaluators cannot drift apart.

The GCP port scores with the same metrics and writes the same per-sample score block as the
AWS repository. This file is the single place those names live; `tests/test_contract.py`
compares them against a pinned snapshot of the AWS run and fails on any difference.

Pinned source: `ai-platform-proof` @ `6c14665`, artefacts
``evidence/ragas-eval.md`` and ``artifacts/experiments/ragas-judge-gpt4o-mini.json``.
The snapshot lives in ``tests/fixtures/ai_platform_proof_ragas.json``; regenerate it from a
recorded run rather than by hand.
"""
from __future__ import annotations

# Commit of ai-platform-proof the snapshot was taken from. A change here is a deliberate act.
REFERENCE_COMMIT = "6c14665"

# Metric columns emitted by the legacy ragas 0.4.4 singletons. A version bump that renames one
# fails the contract test instead of silently dropping a column.
METRIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
    "answer_correctness",
)

# Per-sample fields in the AWS run artefact.
SAMPLE_FIELDS = (
    "case_id",
    "split",
    "question",
    "contexts",
    "retrieved_ids",
    "answer",
    "sources",
    "reference",
    "generation_mode",
    "model",
    "scores",
)

# What a GCP trace record adds on top of the AWS sample: the per-statement reasoning that a
# single aggregate score throws away.
TRACE_FIELDS = ("statements", "verdicts", "reasons")

# Top-level keys of the AWS run artefact that describe the run rather than the samples.
RUN_FIELDS = (
    "run_id",
    "label",
    "judge",
    "embedding_model",
    "dataset",
    "aggregate",
    "judge_usage",
    "metric_names_returned",
    "duration_seconds",
    "limits",
)


def assert_sample_shape(sample: dict) -> None:
    """Fail loudly if a record we are about to write does not match the shared shape."""
    missing = [field for field in ("case_id", "question", "contexts", "answer", "reference",
                                   "scores") if field not in sample]
    if missing:
        raise ValueError(f"trace sample missing fields: {', '.join(missing)}")
    unknown = sorted(set(sample["scores"]) - set(METRIC_NAMES))
    if unknown:
        raise ValueError(f"trace sample has unknown score keys: {', '.join(unknown)}")
    for field in TRACE_FIELDS:
        if field not in sample:
            raise ValueError(f"trace sample missing trace field: {field}")
