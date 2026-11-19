"""Shape a gate report into BigQuery rows.

Kept separate from the loader so the mapping is testable without BigQuery. One row per eval
question; `passed` is the deterministic gate, `aggregate_score` is the judge mean, and
`report_only` says which of the two the numbers are.
"""
from __future__ import annotations

from datetime import date


def build_rows(report: dict, *, trace_uri: str | None = None,
               report_date: str | None = None) -> list[dict]:
    provenance = report.get("provenance") or {}
    day = report_date or date.today().isoformat()
    rows = []
    for index, record in enumerate(report.get("per_record", []), start=1):
        rows.append({
            "report_date": day,
            "question": record.get("question"),
            "map_4": record.get("map@4"),
            "ndcg_4": record.get("ndcg@4"),
            "rouge_l": record.get("rouge_l"),
            "faithfulness": record.get("faithfulness"),
            "answer_relevancy": record.get("answer_relevancy"),
            "aggregate_score": report.get("aggregate_score"),
            "passed": report.get("passed"),
            "run_id": provenance.get("run_id"),
            "case_id": f"case-{index}",
            "judge_model": provenance.get("judge_model") or provenance.get("arm"),
            "trace_uri": trace_uri,
            "report_only": True,
        })
    return rows
