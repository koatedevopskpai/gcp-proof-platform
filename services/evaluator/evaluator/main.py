"""Evaluation CLI — the CI quality gate.

Usage:
    python -m evaluator --dataset datasets/eval_set.jsonl --threshold 0.80

Emits a JSON report. Exit codes: 0 passed, 1 below threshold, 2 error (empty dataset or judge failure).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluator.llm import JudgeError, judge
from evaluator import metrics


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
        "faithfulness": judge.faithfulness(answer, contexts),
        "answer_relevancy": judge.answer_relevancy(question, answer),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI platform evaluation gate")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--threshold", default=0.80, type=float)
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
        # Fail closed: a broken judge is an error, never a score.
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
    scored = [r for r in per_record if all(v is not None for v in r.values())]
    if not scored:
        msg = "no scorable records (every record is missing a ground_truth or a metric)"
        error_report = {"provenance": provenance, "usage": judge.usage(), "records": len(records), "passed": False, "error": msg}
        if args.report:
            args.report.write_text(json.dumps(error_report, indent=2))
        print(json.dumps(error_report, indent=2))
        print(f"EVAL ERROR: {msg}", file=sys.stderr)
        return 2
    aggregate = sum(r["faithfulness"] + r["answer_relevancy"] for r in scored) / (2 * len(scored))

    report = {
        "provenance": provenance,
        "usage": judge.usage(),
        "records": len(records),
        "aggregate_score": round(aggregate, 4),
        "threshold": args.threshold,
        "passed": aggregate >= args.threshold,
        "metrics": {
            "mean_faithfulness": round(
                sum(r["faithfulness"] for r in scored) / len(scored), 4
            ),
            "mean_answer_relevancy": round(
                sum(r["answer_relevancy"] for r in scored) / len(scored), 4
            ),
        },
        "per_record": per_record,
    }

    if args.report:
        args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    if not report["passed"]:
        print(
            f"EVAL GATE FAILED: aggregate {aggregate:.3f} < threshold {args.threshold}",
            file=sys.stderr,
        )
        return 1
    print(f"EVAL GATE PASSED: aggregate {aggregate:.3f} >= {args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())