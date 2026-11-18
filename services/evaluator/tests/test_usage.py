import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import main as main_mod
from evaluator.llm import JudgeClient


def _post_with_usage(prompt_tokens, completion_tokens, content="0.5"):
    def post(url, **kwargs):
        body = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    return post


def test_usage_accumulates_and_costs(monkeypatch):
    monkeypatch.setattr(httpx, "post", _post_with_usage(1000, 10))
    c = JudgeClient()
    c.api_key, c.price_in, c.price_out = "k", 1.0, 2.0  # $1 and $2 per million tokens
    c.faithfulness("a", ["a"])
    c.answer_relevancy("q", "a")
    u = c.usage()
    assert u["calls"] == 2
    assert u["prompt_tokens"] == 2000
    assert u["completion_tokens"] == 20
    assert u["estimated_cost_usd"] == round((2000 * 1.0 + 20 * 2.0) / 1e6, 6)


def test_reset_clears_usage(monkeypatch):
    monkeypatch.setattr(httpx, "post", _post_with_usage(100, 5))
    c = JudgeClient()
    c.api_key = "k"
    c.faithfulness("a", ["a"])
    c.reset_usage()
    assert c.usage()["calls"] == 0 and c.usage()["estimated_cost_usd"] == 0


def test_missing_usage_field_counts_zero_tokens(monkeypatch):
    def post(url, **kwargs):
        body = {"choices": [{"message": {"content": "1.0"}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    c = JudgeClient()
    c.api_key = "k"
    c.faithfulness("a", ["a"])
    assert c.usage()["calls"] == 1 and c.usage()["prompt_tokens"] == 0


def test_lexical_report_shows_zero_spend(monkeypatch, tmp_path):
    monkeypatch.setattr(main_mod.judge, "api_key", "")
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"question": "q", "contexts": ["c"], "answer": "c", "ground_truth": "c"}) + "\n")
    report = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["eval", "--dataset", str(data), "--report", str(report)])
    main_mod.main()
    usage = json.loads(report.read_text())["usage"]
    assert usage["calls"] == 0 and usage["estimated_cost_usd"] == 0


def test_provider_report_records_usage(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "post", _post_with_usage(500, 4, "1.0"))
    monkeypatch.setattr(main_mod.judge, "api_key", "k")
    data = tmp_path / "d.jsonl"
    data.write_text(json.dumps({"question": "q", "contexts": ["c"], "answer": "c", "ground_truth": "c"}) + "\n")
    report = tmp_path / "r.json"
    monkeypatch.setattr(sys, "argv", ["eval", "--dataset", str(data), "--report", str(report)])
    main_mod.main()
    usage = json.loads(report.read_text())["usage"]
    assert usage["calls"] == 2 and usage["prompt_tokens"] == 1000
