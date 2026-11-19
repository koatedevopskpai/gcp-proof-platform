"""Evaluation CLI — a deterministic gate, a probabilistic report.

Usage:
    python -m evaluator --dataset datasets/eval_set.jsonl --threshold 0.80

Exit codes: 0 gate passed, 1 gate failed, 2 error (empty dataset or judge failure).

The gate decides the exit code and is deterministic: retrieval quality (MAP@4,
nDCG@4) plus structural completeness and numeric consistency with the reference.
Judge scores (faithfulness, answer relevancy) are reported and never change the
exit code — the empirical case for that split is in evidence/eval-gate-audit.md.

A judge *failure* is still an error (exit 2). A failure is not a score, and a
report that silently omits the judge would read as if nothing were wrong.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluator.llm import JudgeError, judge
from evaluator import metrics

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def load_dataset(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _git_commit() -> str | None:
    """Commit the code was built from: GIT_COMMIT env var first, then git, else None."""
    env = os.getenv("GIT_COMMIT")
    if env:
        return env
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parent,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def build_provenance(dataset: Path) -> dict:
    """Where this report came from, so a number can be traced to a run."""
    return {
        "run_id": str(uuid.uuid4()),
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arm": judge.arm,
        "judge_model": judge.model if judge.arm == "provider" else None,
        "dataset": dataset.name,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "git_commit": _git_commit(),
    }


def _numbers(text: str) -> set[str]:
    """Normalised numeric tokens so 30, 30.0 and "30 days" compare equal."""
    values = set()
    for raw in NUMBER_RE.findall(text or ""):
        try:
            values.add(f"{float(raw.replace(',', '')):g}")
        except ValueError:
            continue
    return values


def check_structure(record: dict) -> list[str]:
    """Deterministic completeness checks. Empty list means the record is well formed."""
    problems = []
    if not str(record.get("answer", "")).strip():
        problems.append("empty answer")
    if not record.get("contexts"):
        problems.append("no contexts")
    if not record.get("retrieved"):
        problems.append("no retrieved ids")
    return problems


def check_numbers(answer: str, ground_truth: str, contexts: list[str]) -> list[str]:
    """Numbers in the answer that appear in neither the reference nor the context.

    Deterministic, and narrow on purpose: it catches a changed limit or date (the
    "30 days" -> "90 days" case) and does nothing about an unsupported sentence
    with no number in it. The limit is stated in the audit and in the tests.
    """
    if not ground_truth:
        return []
    allowed = _numbers(ground_truth)
    for context in contexts:
        allowed |= _numbers(context)
    unexpected = sorted(_numbers(answer) - allowed)
    return [f"unsupported number(s): {', '.join(unexpected)}"] if unexpected else []


def evaluate_record(record: dict) -> dict:
    question = record["question"]
    contexts = [c.get("content", c) if isinstance(c, dict) else c for c in record.get("contexts", [])]
    relevant = set(record.get("relevant_ids", []))
    retrieved = [c.get("id") if isinstance(c, dict) else c for c in record.get("retrieved", [])]
    ground_truth = record.get("ground_truth", "")
    answer = record.get("answer", contexts[0][:400] if contexts else "")

    return {
        "question": question,
        "map@4": metrics.map_at_k(relevant, retrieved, k=4),
        "ndcg@4": metrics.ndcg_at_k(relevant, retrieved, k=4),
        "rouge_l": metrics.rouge_l(answer, ground_truth) if ground_truth else None,
        # Report-only: judge scores are recorded, never compared to the threshold.
        "faithfulness": judge.faithfulness(answer, contexts),
        "answer_relevancy": judge.answer_relevancy(question, answer),
        "structure": check_structure(record),
        "numbers": check_numbers(answer, ground_truth, contexts),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI platform evaluation gate")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--threshold", default=0.80, type=float,
                        help="minimum MAP@4 and nDCG@4 for the deterministic gate")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    records = load_dataset(args.dataset)
    if not records:
        print("ERROR: empty evaluation dataset", file=sys.stderr)
        return 2

    provenance = build_provenance(args.dataset)
    judge.reset_usage()
    try:
        per_record = [evaluate_record(r) for r in records]
    except JudgeError as exc:
        # Fail closed: a broken judge is an error, never a score or a silent omission.
        error_report = {
            "provenance": provenance,
            "usage": judge.usage(),
            "records": len(records),
            "passed": False,
            "error": str(exc),
        }
        if args.report:
            args.report.write_text(json.dumps(error_report, indent=2))
        print(json.dumps(error_report, indent=2))
        print(f"EVAL ERROR (judge unavailable): {exc}", file=sys.stderr)
        return 2

    map_score = _mean([r["map@4"] for r in per_record])
    ndcg_score = _mean([r["ndcg@4"] for r in per_record])
    judge_faithfulness = _mean([r["faithfulness"] for r in per_record])
    judge_relevancy = _mean([r["answer_relevancy"] for r in per_record])
    rouge_values = [r["rouge_l"] for r in per_record if r["rouge_l"] is not None]

    # --- gate: deterministic, decides the exit code -------------------------
    failures = []
    if map_score < args.threshold:
        failures.append(f"map@4 {map_score:.4f} < {args.threshold}")
    if ndcg_score < args.threshold:
        failures.append(f"ndcg@4 {ndcg_score:.4f} < {args.threshold}")
    for index, record in enumerate(per_record):
        for problem in record["structure"]:
            failures.append(f"record {index}: {problem}")
        for problem in record["numbers"]:
            failures.append(f"record {index}: {problem}")

    gate = {
        "passed": not failures,
        "threshold": args.threshold,
        "checks": {"map@4": round(map_score, 4), "ndcg@4": round(ndcg_score, 4)},
        "failures": failures,
    }

    # --- report: probabilistic, never affects the exit code -----------------
    report_block = {
        "judge": {
            "arm": judge.arm,
            "model": judge.model if judge.arm == "provider" else None,
            "faithfulness": round(judge_faithfulness, 4),
            "answer_relevancy": round(judge_relevancy, 4),
        },
        "rouge_l": round(_mean(rouge_values), 4) if rouge_values else None,
        "gated": False,
    }

    report = {
        "provenance": provenance,
        "usage": judge.usage(),
        "records": len(records),
        "gate": gate,
        "report": report_block,
        # `passed` mirrors gate.passed; consumers (run_pipeline.py, BigQuery) read it.
        "passed": gate["passed"],
        "threshold": args.threshold,
        # Judge means, kept at the top level for the existing BigQuery column.
        "aggregate_score": round((judge_faithfulness + judge_relevancy) / 2, 4),
        "metrics": {
            "mean_faithfulness": round(judge_faithfulness, 4),
            "mean_answer_relevancy": round(judge_relevancy, 4),
        },
        "per_record": per_record,
    }

    if args.report:
        args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    if not gate["passed"]:
        print(
            "EVAL GATE FAILED: " + "; ".join(failures),
            file=sys.stderr,
        )
        return 1
    print(f"EVAL GATE PASSED: map@4 {map_score:.3f}, ndcg@4 {ndcg_score:.3f} >= {args.threshold}")
    print(
        f"report (not gated): faithfulness {judge_faithfulness:.3f}, "
        f"answer relevancy {judge_relevancy:.3f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
