"""The scoring-arm seam: light checks that need no provider call."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator import ragas_metrics, vertex_llm


def test_unknown_arm_is_rejected_before_any_import():
    with pytest.raises(ValueError, match="unknown scoring arm"):
        ragas_metrics.build_adapters("m", "u", "k", "e", arm="bedrock")


def test_vertex_judge_reports_unpriced_usage():
    judge = vertex_llm.VertexJudge(model="gemini-3-flash-preview", project="p", location="global")
    assert judge.arm == "vertex"
    usage = judge.usage()
    assert usage["calls"] == 0
    assert usage["prompt_tokens"] == 0
    assert usage["estimated_cost_usd"] is None
    assert "not applied" in usage["pricing"]


def test_vertex_judge_resets_usage():
    judge = vertex_llm.VertexJudge(project="p")
    judge.calls = 3
    judge.prompt_tokens = 10
    judge.reset_usage()
    assert judge.usage()["calls"] == 0 and judge.usage()["prompt_tokens"] == 0
