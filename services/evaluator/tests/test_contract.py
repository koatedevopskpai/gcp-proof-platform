"""Contract test against a pinned snapshot of the ai-platform-proof RAGAS run.

The two repositories produce the same per-sample score block. This test fails if either side
drifts: our constants against the snapshot, and a representative trace through the store.

The snapshot (`fixtures/ai_platform_proof_ragas.json`) holds key names only, taken from
`artifacts/experiments/ragas-judge-gpt4o-mini.json` at `ai-platform-proof` @ `6c14665`.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import contract, trace_store

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ai_platform_proof_ragas.json"


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_metric_names_match_the_aws_run(snapshot):
    assert set(contract.METRIC_NAMES) == set(snapshot["score_keys"])
    assert set(contract.METRIC_NAMES) == set(snapshot["aggregate_keys"])


def test_sample_fields_match_the_aws_run(snapshot):
    assert set(contract.SAMPLE_FIELDS) == set(snapshot["sample_fields"])


def test_run_fields_we_emit_exist_in_the_aws_run(snapshot):
    assert set(contract.RUN_FIELDS) <= set(snapshot["run_fields"])
    for required in ("run_id", "judge", "embedding_model", "aggregate", "judge_usage",
                     "metric_names_returned", "duration_seconds"):
        assert required in contract.RUN_FIELDS


def test_pinned_commit_is_the_one_documented(snapshot):
    assert snapshot["pinned_commit"] == contract.REFERENCE_COMMIT


def _sample(**overrides):
    sample = {
        "case_id": "heldout-retention",
        "split": "heldout",
        "question": "When must customer data be deleted after a contract ends?",
        "contexts": ["Customer data must be deleted within 30 days of contract termination."],
        "retrieved_ids": ["heldout-retention"],
        "answer": "Customer data must be deleted within 30 days of contract termination.",
        "sources": ["heldout-retention"],
        "reference": "Within 30 days of contract termination.",
        "generation_mode": "stored",
        "model": None,
        "scores": {name: 1.0 for name in contract.METRIC_NAMES},
        "statements": ["Customer data must be deleted within 30 days of contract termination."],
        "verdicts": ["supported"],
        "reasons": ["The context states the same sentence."],
    }
    sample.update(overrides)
    return sample


def test_a_conforming_sample_passes_and_serialises(tmp_path):
    payload = {
        "run": {"run_id": "test-run", "label": "unit", "judge": {"model": "gpt-4o-mini"},
                "embedding_model": "text-embedding-3-small",
                "aggregate": {name: 1.0 for name in contract.METRIC_NAMES},
                "judge_usage": None, "metric_names_returned": list(contract.METRIC_NAMES),
                "duration_seconds": 0.1},
        "samples": [_sample()],
    }
    uri = trace_store.write_trace(payload, run_id="test-run", local_dir=tmp_path)
    lines = Path(uri).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "run"
    assert json.loads(lines[1])["kind"] == "sample"
    assert json.loads(lines[1])["scores"]["faithfulness"] == 1.0


def test_unknown_score_key_is_rejected():
    with pytest.raises(ValueError, match="unknown score keys"):
        contract.assert_sample_shape(_sample(scores={"faithfulness": 1.0, "vibes": 0.9}))


def test_missing_trace_field_is_rejected():
    sample = _sample()
    del sample["verdicts"]
    with pytest.raises(ValueError, match="verdicts"):
        contract.assert_sample_shape(sample)


def test_trace_store_refuses_an_empty_run():
    with pytest.raises(ValueError, match="no samples"):
        trace_store._serialise({"run": {"run_id": "x"}, "samples": []})
