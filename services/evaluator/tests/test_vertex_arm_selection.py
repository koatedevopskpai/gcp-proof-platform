"""Judge-arm selection, what each arm records, and that Vertex fails closed.

`JUDGE_ARM` selects the judge used for the gate's report; `SCORING_ARM` selects RAGAS and the trace.
They are independent, and an explicit judge arm must win over a mounted key. No network: the Vertex
client is faked.
"""
import inspect

import pytest

from evaluator.llm import JudgeClient, JudgeError

CLEAR = ("OPENAI_API_KEY", "JUDGE_ARM", "SCORING_ARM", "VERTEX_MODEL", "JUDGE_MODEL")


@pytest.fixture
def clean_env(monkeypatch):
    for name in CLEAR:
        monkeypatch.delenv(name, raising=False)


def test_default_is_lexical_with_no_model(clean_env):
    judge = JudgeClient()
    assert judge.arm == "lexical" and judge.judge_model is None


def test_judge_arm_vertex_without_a_key(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    judge = JudgeClient()
    assert judge.arm == "vertex"
    assert judge.judge_model == "gemini-3-flash-preview"


def test_judge_arm_vertex_ignores_a_present_key(clean_env, monkeypatch):
    """Regression: a key used to win over an explicit arm, so "keyless" was only accidental."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    assert JudgeClient().arm == "vertex"


def test_judge_arm_lexical_wins_over_a_present_key(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JUDGE_ARM", "lexical")
    judge = JudgeClient()
    assert judge.arm == "lexical" and judge.judge_model is None


def test_unset_arm_with_a_key_is_provider(clean_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    judge = JudgeClient()
    assert judge.arm == "provider" and judge.judge_model == "gpt-4o-mini"


def test_judge_arm_openai_without_a_key_fails_closed(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "openai")
    with pytest.raises(JudgeError, match="requires OPENAI_API_KEY"):
        JudgeClient().faithfulness("an answer", ["a context"])


def test_scoring_arm_does_not_select_the_judge(clean_env, monkeypatch):
    """The two arms are separate: Vertex scoring must not silently move the gate's judge."""
    monkeypatch.setenv("SCORING_ARM", "vertex")
    assert JudgeClient().arm == "lexical"


def test_vertex_model_can_be_overridden(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    monkeypatch.setenv("VERTEX_MODEL", "gemini-3.5-flash-lite")
    assert JudgeClient().judge_model == "gemini-3.5-flash-lite"


def test_vertex_usage_is_unpriced_not_zero(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    usage = JudgeClient().usage()
    assert usage["estimated_cost_usd"] is None  # an unknown price must not look like a $0 price
    assert "not applied" in usage["pricing"]


class _FakeVertex:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls = answer, error, 0

    def complete(self, prompt):
        self.calls += 1
        if self.error:
            raise JudgeError(f"vertex call failed: {self.error}")
        return self.answer

    def reset_usage(self):
        pass

    def usage(self):
        return {"calls": self.calls}


def test_vertex_score_comes_from_the_model_answer(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    judge = JudgeClient()
    judge._vertex = _FakeVertex(answer="0.75")
    assert judge.faithfulness("an answer", ["a context"]) == pytest.approx(0.75)


def test_vertex_failure_raises_instead_of_becoming_a_score(clean_env, monkeypatch):
    monkeypatch.setenv("JUDGE_ARM", "vertex")
    judge = JudgeClient()
    judge._vertex = _FakeVertex(error="DeadlineExceeded")
    with pytest.raises(JudgeError):
        judge.faithfulness("an answer", ["a context"])


def test_report_block_names_the_same_model_as_the_provenance_header():
    """Regression: the report block showed model=None for the Vertex arm while provenance named it."""
    from evaluator import main

    src = inspect.getsource(main)
    assert '"model": judge.judge_model' in src
    assert 'judge.model if judge.arm == "provider"' not in src
