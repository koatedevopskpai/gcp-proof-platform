"""Phase-4 helpers: the eval set must be valid before it costs a model call."""
from pathlib import Path

from eval_support import (
    build_bq_rows,
    case_expected_tools,
    case_kind,
    compare_trajectory,
    load_eval_config,
    load_evalset,
)

EVALSET = Path(__file__).resolve().parents[1] / "evals" / "support_agent_v1.evalset.json"
CONFIG = Path(__file__).resolve().parents[1] / "evals" / "test_config.json"


def test_evalset_is_valid_and_has_the_expected_cases():
    eval_set = load_evalset(EVALSET)

    assert eval_set.eval_set_id == "support_agent_v1"
    assert len(eval_set.eval_cases) == 8
    ids = {case.eval_id for case in eval_set.eval_cases}
    assert "lookup_status" in ids
    assert "safety_authority" in ids
    assert "out_of_domain" in ids


def test_out_of_domain_expects_no_tools():
    eval_set = load_evalset(EVALSET)
    case = next(case for case in eval_set.eval_cases if case.eval_id == "out_of_domain")

    assert case_expected_tools(case) == []
    assert case_kind(case) == "out"


def test_eval_config_is_valid():
    config = load_eval_config(CONFIG)

    assert config.criteria["tool_trajectory_avg_score"].threshold == 1.0
    assert config.criteria["final_response_match_v2"].threshold == 0.7


def test_trajectory_exact_and_in_order_are_distinct():
    exact = compare_trajectory(["a", "b"], ["a", "b"])
    extra = compare_trajectory(["a"], ["a", "b"])
    missing = compare_trajectory(["a", "b"], ["a"])

    assert exact["exact"] is True and exact["in_order"] is True
    assert extra["exact"] is False and extra["in_order"] is True
    assert extra["unexpected"] == ["b"]
    assert missing["exact"] is False and missing["in_order"] is False
    assert missing["missing"] == ["b"]


def _report(faithfulness: float = 0.9) -> dict:
    return {
        "run": {
            "run_id": "run-1",
            "judge": {"model": "gemini-3-flash-preview"},
            "aggregate": {"faithfulness": 0.8},
        },
        "trace_uri": "gs://traces/run-1.jsonl",
        "samples": [
            {
                "case_id": "lookup_status",
                "question": "Status of TR-1042?",
                "scores": {"faithfulness": faithfulness, "answer_relevancy": 0.8},
            }
        ],
    }


def test_bq_rows_carry_trajectory_and_quality():
    trajectory = {
        "lookup_status": {
            "case_kind": "lookup",
            "expected_tools": ["lookup_record"],
            "actual_tools": ["lookup_record"],
            "exact": True,
        }
    }

    row = build_bq_rows(_report(), trajectory, report_date="2026-11-24")[0]

    assert row["report_date"] == "2026-11-24"
    assert row["case_id"] == "lookup_status"
    assert row["case_kind"] == "lookup"
    assert row["expected_tools"] == "lookup_record"
    assert row["tool_trajectory_score"] == 1.0
    assert row["tool_trajectory_passed"] is True
    assert row["passed"] is True
    assert row["report_only"] is True
    assert row["run_id"] == "run-1"
    assert row["judge_model"] == "gemini-3-flash-preview"


def test_bq_rows_fail_when_trajectory_or_faithfulness_is_low():
    failed_trajectory = {
        "lookup_status": {
            "case_kind": "lookup",
            "expected_tools": ["lookup_record"],
            "actual_tools": ["lookup_record", "search_knowledge"],
            "exact": False,
        }
    }

    row = build_bq_rows(_report(faithfulness=0.95), failed_trajectory)[0]
    assert row["passed"] is False
    assert row["tool_trajectory_passed"] is False

    good_trajectory = {
        "lookup_status": {
            "case_kind": "lookup",
            "expected_tools": ["lookup_record"],
            "actual_tools": ["lookup_record"],
            "exact": True,
        }
    }
    row = build_bq_rows(_report(faithfulness=0.2), good_trajectory)[0]
    assert row["passed"] is False
