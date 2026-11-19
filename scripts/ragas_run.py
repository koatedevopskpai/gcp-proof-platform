"""Run RAGAS scoring plus a per-statement trace over a stored-answer dataset.

Report-only: this writes a trace object and a report. It never changes a gate or an exit code
for quality reasons (it exits non-zero only on an operational failure).

    python scripts/ragas_run.py --dataset services/evaluator/datasets/ragas_set.jsonl --label local-1

Environment: OPENAI_API_KEY (required), OPENAI_BASE_URL, JUDGE_MODEL, EMBEDDING_MODEL,
TRACE_BUCKET (GCS sink; otherwise artifacts/traces/).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "evaluator"))

from evaluator import contract, faithfulness_trace, ragas_metrics, trace_store  # noqa: E402
from evaluator.llm import judge  # noqa: E402


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="RAGAS scoring + statement trace (report only)")
    parser.add_argument("--dataset", type=Path,
                        default=ROOT / "services/evaluator/datasets/ragas_set.jsonl")
    parser.add_argument("--label", default="local")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/ragas")
    parser.add_argument("--trace-bucket", default=os.getenv("TRACE_BUCKET") or None)
    parser.add_argument("--skip-trace", action="store_true",
                        help="score only, no per-statement judge calls")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY is required", file=sys.stderr)
        return 2
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    judge_model = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    rows = load_rows(args.dataset)
    started = time.time()
    run_id = "ragas-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]

    print(f"scoring {len(rows)} cases with {judge_model} / {embedding_model}", flush=True)
    scored = ragas_metrics.score(
        rows, judge_model=judge_model, judge_base_url=base_url,
        judge_api_key=api_key, embedding_model=embedding_model,
    )
    by_case = {entry["case_id"]: entry for entry in scored["per_sample"]}

    samples = []
    judge.reset_usage()
    for position, row in enumerate(rows):
        scores = {name: by_case.get(row["case_id"], {}).get(name) for name in contract.METRIC_NAMES}
        trace = ({"statements": [], "verdicts": [], "reasons": [], "supported": 0, "total": 0,
                  "faithfulness": None}
                 if args.skip_trace else faithfulness_trace.trace(row["answer"], row["contexts"]))
        samples.append({
            "case_id": row["case_id"],
            "split": row.get("split", "unknown"),
            "question": row["question"],
            "contexts": list(row["contexts"]),
            "retrieved_ids": row.get("retrieved_ids", []),
            "answer": row["answer"],
            "sources": row.get("retrieved_ids", []),
            "reference": row["reference"],
            "generation_mode": row.get("generation_mode", "stored"),
            "model": row.get("model"),
            "scores": scores,
            "statements": trace["statements"],
            "verdicts": trace["verdicts"],
            "reasons": trace["reasons"],
            "trace_supported": trace["supported"],
            "trace_total": trace["total"],
            "trace_faithfulness": trace["faithfulness"],
        })
        print(f"  {position + 1}/{len(rows)} {row['case_id']}: "
              f"faithfulness={scores['faithfulness']} trace={trace['faithfulness']}", flush=True)

    payload = {
        "run": {
            "run_id": run_id,
            "label": args.label,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge": {"model": judge_model, "base_url": base_url},
            "embedding_model": embedding_model,
            "dataset": {
                "path": str(args.dataset.relative_to(ROOT)) if args.dataset.is_relative_to(ROOT)
                        else str(args.dataset),
                "samples": len(rows),
                "sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                "splits": sorted({row.get("split", "unknown") for row in rows}),
            },
            "aggregate": scored["aggregate"],
            "judge_usage": {"ragas": scored["usage"], "trace": judge.usage()},
            "metric_names_returned": scored["metric_names_returned"],
            "duration_seconds": round(time.time() - started, 1),
            "limits": [
                "stored answers, not a live service - a scoring demonstration, not a benchmark",
                "one judge model at one point in time; not calibrated against human labels",
                "scores are probabilistic; repeat runs differ",
                "report-only: these scores do not gate promotion",
            ],
        },
        "samples": samples,
    }

    uri = trace_store.write_trace(payload, run_id=run_id, bucket=args.trace_bucket)
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{run_id}.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cost = (scored["usage"] or {}).get("total_cost_usd")
    trace_cost = judge.usage()["estimated_cost_usd"]
    print(json.dumps({"run_id": run_id, "trace": uri, "report": str(report_path),
                      "ragas_cost_usd": cost, "trace_cost_usd": trace_cost,
                      "aggregate": scored["aggregate"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
