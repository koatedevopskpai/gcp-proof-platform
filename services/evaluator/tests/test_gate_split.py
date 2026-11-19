"""The split that this project exists for: the gate is deterministic, the judge reports.

Each test runs the CLI against a real control dataset so the assertions are about
behaviour, not about a mock that agrees with the implementation.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import main as main_mod

DATASETS = Path(__file__).resolve().parents[1] / "datasets"


def run(monkeypatch, tmp_path, dataset: str):
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(main_mod.judge, "api_key", "")  # lexical arm: no network
    monkeypatch.setattr(sys, "argv", [
        "eval", "--dataset", str(DATASETS / dataset), "--threshold", "0.80",
        "--report", str(report_path),
    ])
    code = main_mod.main()
    return code, json.loads(report_path.read_text())


def test_verbatim_control_passes_the_gate(monkeypatch, tmp_path):
    code, out = run(monkeypatch, tmp_path, "control_verbatim.jsonl")
    assert code == 0
    assert out["gate"]["passed"] is True
    assert out["gate"]["failures"] == []
    assert out["report"]["judge"]["faithfulness"] == 1.0
    assert out["report"]["gated"] is False


def test_changed_number_fails_the_gate(monkeypatch, tmp_path):
    code, out = run(monkeypatch, tmp_path, "control_unsupported.jsonl")
    assert code == 1
    assert out["gate"]["passed"] is False
    assert any("unsupported number" in failure for failure in out["gate"]["failures"])


def test_unsupported_sentence_without_a_number_passes_the_gate(monkeypatch, tmp_path):
    """Documented limit: the deterministic gate cannot see an unsupported claim.

    The judge reports it (faithfulness drops); the gate passes it. This is the
    trade-off the audit records, kept as an executable statement rather than prose.
    """
    code, out = run(monkeypatch, tmp_path, "control_unsupported_subtle.jsonl")
    assert code == 0
    assert out["gate"]["passed"] is True
    assert out["report"]["judge"]["faithfulness"] < 1.0


def test_a_low_judge_score_cannot_fail_the_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod.judge, "faithfulness", lambda *a, **k: 0.0)
    monkeypatch.setattr(main_mod.judge, "answer_relevancy", lambda *a, **k: 0.0)
    code, out = run(monkeypatch, tmp_path, "control_verbatim.jsonl")
    assert code == 0
    assert out["gate"]["passed"] is True
    assert out["report"]["judge"]["faithfulness"] == 0.0
    assert out["aggregate_score"] == 0.0


def test_missing_answer_fails_structure(monkeypatch, tmp_path):
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({
        "question": "q", "contexts": [{"id": "c1", "content": "c"}],
        "retrieved": ["c1"], "relevant_ids": ["c1"], "ground_truth": "c", "answer": "",
    }) + "\n")
    report_path = tmp_path / "r.json"
    monkeypatch.setattr(main_mod.judge, "api_key", "")
    monkeypatch.setattr(sys, "argv", ["eval", "--dataset", str(data), "--report", str(report_path)])
    assert main_mod.main() == 1
    out = json.loads(report_path.read_text())
    assert any("empty answer" in failure for failure in out["gate"]["failures"])
