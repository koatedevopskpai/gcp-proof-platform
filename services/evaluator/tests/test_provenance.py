import hashlib
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import main as main_mod

KEYS = {"run_id", "evaluated_at", "arm", "judge_model", "dataset", "dataset_sha256", "git_commit"}


def _dataset(tmp_path):
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"question": "q", "contexts": ["c"], "answer": "c", "ground_truth": "c"}) + "\n")
    return data


def _run(monkeypatch, tmp_path, data):
    report = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["eval", "--dataset", str(data), "--report", str(report)])
    rc = main_mod.main()
    return rc, json.loads(report.read_text())


def test_lexical_report_has_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod.judge, "api_key", "")
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    data = _dataset(tmp_path)
    rc, out = _run(monkeypatch, tmp_path, data)
    prov = out["provenance"]
    assert rc in (0, 1)  # score is irrelevant here; provenance is under test
    assert set(prov) == KEYS
    assert prov["arm"] == "lexical"
    assert prov["judge_model"] is None
    assert prov["dataset_sha256"] == hashlib.sha256(data.read_bytes()).hexdigest()
    assert prov["git_commit"] == "abc123"


def test_error_report_also_has_provenance(monkeypatch, tmp_path):
    def post(url, **kwargs):
        return httpx.Response(401, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(main_mod.judge, "api_key", "test-key")
    rc, out = _run(monkeypatch, tmp_path, _dataset(tmp_path))
    assert rc == 2
    assert out["provenance"]["arm"] == "provider"
    assert out["provenance"]["judge_model"] == main_mod.judge.model


def test_run_ids_differ(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod.judge, "api_key", "")
    data = _dataset(tmp_path)
    a = main_mod.build_provenance(data)["run_id"]
    b = main_mod.build_provenance(data)["run_id"]
    assert a != b


def test_unscorable_dataset_exits_2_with_error(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod.judge, "api_key", "")
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"question": "q", "contexts": ["c"], "answer": "c"}) + "\n")
    rc, out = _run(monkeypatch, tmp_path, data)
    assert rc == 2
    assert "error" in out and out["passed"] is False
    assert "provenance" in out
