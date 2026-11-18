import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import main as main_mod
from evaluator.llm import JudgeClient, JudgeError


def _client() -> JudgeClient:
    c = JudgeClient()
    c.api_key = "test-key"
    return c


def _fake_post(status=200, body=None):
    def post(url, **kwargs):
        req = httpx.Request("POST", url)
        return httpx.Response(status, json=body or {}, request=req)
    return post


def test_http_error_raises_not_half(monkeypatch):
    monkeypatch.setattr(httpx, "post", _fake_post(401, {"error": "bad key"}))
    with pytest.raises(JudgeError):
        _client().faithfulness("a", ["a"])


def test_unparseable_reply_raises(monkeypatch):
    body = {"choices": [{"message": {"content": "no idea"}}]}
    monkeypatch.setattr(httpx, "post", _fake_post(200, body))
    with pytest.raises(JudgeError):
        _client().faithfulness("a", ["a"])


def test_valid_reply_scores(monkeypatch):
    body = {"choices": [{"message": {"content": "0.75"}}]}
    monkeypatch.setattr(httpx, "post", _fake_post(200, body))
    assert _client().faithfulness("a", ["a"]) == 0.75


def test_cli_exits_2_with_error_field_on_judge_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "post", _fake_post(401, {"error": "bad key"}))
    monkeypatch.setattr(main_mod.judge, "api_key", "test-key")
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"question": "q", "contexts": ["c"], "answer": "c"}) + "\n")
    report = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["eval", "--dataset", str(data), "--report", str(report)])
    assert main_mod.main() == 2
    out = json.loads(report.read_text())
    assert out["passed"] is False
    assert "error" in out
    assert "aggregate_score" not in out
