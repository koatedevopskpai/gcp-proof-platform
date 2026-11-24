"""Pure helpers for phase-4 evaluation: case access, trajectory comparison, BQ rows.

The ADK evaluator owns the official trajectory score. These helpers are used by the
capture runner to record the same facts for RAGAS and for the BigQuery row shape.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable

PASS_FAITHFULNESS = 0.70


def load_evalset(path: str | Path) -> "EvalSet":
    from google.adk.evaluation.eval_set import EvalSet

    return EvalSet.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_eval_config(path: str | Path) -> "EvalConfig":
    from google.adk.evaluation.eval_config import get_evaluation_criteria_or_default

    # Use ADK's loader so metric names are mapped to their criterion classes.
    return get_evaluation_criteria_or_default(str(path))


def _first_invocation(case):
    if not case.conversation:
        raise ValueError(f"{case.eval_id}: no conversation")
    return case.conversation[0]


def case_question(case) -> str:
    content = _first_invocation(case).user_content
    return " ".join(part.text for part in content.parts if part.text).strip()


def case_reference(case) -> str:
    response = _first_invocation(case).final_response
    if response is None:
        return ""
    return " ".join(part.text for part in response.parts if part.text).strip()


def case_expected_tools(case) -> list[str]:
    data = _first_invocation(case).intermediate_data
    tool_uses = getattr(data, "tool_uses", None) or []
    return [call.name for call in tool_uses]


def case_kind(case) -> str:
    return case.eval_id.split("_", 1)[0]


def compare_trajectory(expected: Iterable[str], actual: Iterable[str]) -> dict:
    expected_list = list(expected)
    actual_list = list(actual)
    position = 0
    for name in actual_list:
        if position < len(expected_list) and name == expected_list[position]:
            position += 1
    return {
        "exact": expected_list == actual_list,
        "in_order": position == len(expected_list),
        "missing": [name for name in expected_list if name not in actual_list],
        "unexpected": [name for name in actual_list if name not in expected_list],
    }


def build_bq_rows(
    report: dict,
    trajectory: dict[str, dict],
    *,
    report_date: str | None = None,
    threshold: float = PASS_FAITHFULNESS,
) -> list[dict]:
    """Map a RAGAS payload plus captured trajectories to `eval_reports` rows."""
    day = report_date or date.today().isoformat()
    run = report.get("run") or {}
    judge = run.get("judge") or {}
    aggregate = (run.get("aggregate") or {}).get("faithfulness")
    rows = []

    for sample in report.get("samples", []):
        case_id = sample.get("case_id")
        captured = trajectory.get(case_id) or {}
        scores = sample.get("scores") or {}
        faithfulness = scores.get("faithfulness")
        exact = bool(captured.get("exact"))
        rows.append(
            {
                "report_date": day,
                "question": sample.get("question"),
                "map_4": None,
                "ndcg_4": None,
                "rouge_l": None,
                "faithfulness": faithfulness,
                "answer_relevancy": scores.get("answer_relevancy"),
                "aggregate_score": aggregate,
                "passed": exact and faithfulness is not None and faithfulness >= threshold,
                "run_id": run.get("run_id"),
                "case_id": case_id,
                "judge_model": judge.get("model"),
                "trace_uri": report.get("trace_uri"),
                "report_only": True,
                "case_kind": captured.get("case_kind") or sample.get("case_kind"),
                "expected_tools": ", ".join(captured.get("expected_tools", [])),
                "actual_tools": ", ".join(captured.get("actual_tools", [])),
                "tool_trajectory_score": 1.0 if exact else 0.0,
                "tool_trajectory_passed": exact,
            }
        )
    return rows


def write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
