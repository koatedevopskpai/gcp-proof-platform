"""The report → BigQuery row mapping, without BigQuery."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluator.bq_rows import build_rows


def _report():
    return {
        "provenance": {"run_id": "run-123", "arm": "provider", "judge_model": "gpt-4o-mini"},
        "aggregate_score": 0.9375,
        "passed": True,
        "per_record": [
            {"question": "q1", "map@4": 1.0, "ndcg@4": 1.0, "rouge_l": 0.32,
             "faithfulness": 1.0, "answer_relevancy": 1.0},
            {"question": "q2", "map@4": 0.5, "ndcg@4": 0.6, "rouge_l": None,
             "faithfulness": 0.8, "answer_relevancy": 0.9},
        ],
    }


def test_one_row_per_record_with_provenance():
    rows = build_rows(_report(), trace_uri="gs://bucket/ragas/x.jsonl", report_date="2026-11-19")
    assert len(rows) == 2
    first, second = rows
    assert first["report_date"] == "2026-11-19"
    assert first["case_id"] == "case-1" and second["case_id"] == "case-2"
    assert first["run_id"] == "run-123"
    assert first["judge_model"] == "gpt-4o-mini"
    assert first["trace_uri"] == "gs://bucket/ragas/x.jsonl"
    assert first["report_only"] is True
    assert first["passed"] is True
    assert first["aggregate_score"] == 0.9375
    assert second["rouge_l"] is None


def test_lexical_arm_records_the_arm_as_judge_model():
    report = _report()
    report["provenance"]["judge_model"] = None
    rows = build_rows(report, report_date="2026-11-19")
    assert rows[0]["judge_model"] == "provider"


def test_missing_trace_is_null_not_absent():
    rows = build_rows(_report(), report_date="2026-11-19")
    assert rows[0]["trace_uri"] is None
