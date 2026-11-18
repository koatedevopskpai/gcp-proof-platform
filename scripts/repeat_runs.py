"""Repeat the evaluator N times per dataset and summarise the spread.

Provider arm needs a key, supplied by OPENAI_API_KEY or --key-file (first line). The key is never
printed or written to the output. Model is pinned with --model so the run is reproducible.

    python scripts/repeat_runs.py --arm provider --runs 5 --model gpt-4o-mini --key-file ~/.openai_key
    python scripts/repeat_runs.py --arm lexical --runs 3        # free, no key
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "services" / "evaluator"
DATASETS = [
    "eval_set",
    "control_verbatim",
    "control_verbatim_distracted",
    "control_unsupported",
    "control_unsupported_subtle",
]


def run_once(dataset: str, env: dict, report: Path) -> dict:
    cmd = [sys.executable, "-m", "evaluator", "--dataset", str(EVALUATOR / "datasets" / f"{dataset}.jsonl"),
           "--threshold", "0.80", "--report", str(report)]
    proc = subprocess.run(cmd, cwd=EVALUATOR, env=env, capture_output=True, text=True)
    out = json.loads(report.read_text()) if report.exists() else {"error": proc.stderr[-300:]}
    out["exit_code"] = proc.returncode
    return out


def summarise(reports: list[dict]) -> dict:
    ok = [r for r in reports if "aggregate_score" in r]
    scores = [r["aggregate_score"] for r in ok]
    summary = {
        "runs": len(reports),
        "errors": len(reports) - len(ok),
        "exit_codes": sorted({r["exit_code"] for r in reports}),
        "passed_all": all(r.get("passed") for r in ok) if ok else None,
        "cost_usd": round(sum(r.get("usage", {}).get("estimated_cost_usd", 0) for r in reports), 6),
        "calls": sum(r.get("usage", {}).get("calls", 0) for r in reports),
    }
    if scores:
        summary.update(scores=scores, median=statistics.median(scores), min=min(scores),
                       max=max(scores), spread=round(max(scores) - min(scores), 4))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["lexical", "provider"], required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--key-file", type=Path)
    ap.add_argument("--datasets", nargs="*", default=DATASETS)
    ap.add_argument("--out", type=Path, default=ROOT / "artifacts" / "repeat-runs")
    args = ap.parse_args()

    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "OPENAI_BASE_URL")}
    if args.arm == "provider":
        key = os.environ.get("OPENAI_API_KEY", "")
        if args.key_file:
            key = args.key_file.expanduser().read_text(encoding="utf-8").splitlines()[0].strip()
        if not key:
            print("provider arm needs OPENAI_API_KEY or --key-file", file=sys.stderr)
            return 2
        env["OPENAI_API_KEY"] = key
        env["JUDGE_MODEL"] = args.model

    args.out.mkdir(parents=True, exist_ok=True)
    result = {"arm": args.arm, "model": args.model if args.arm == "provider" else None,
              "runs_per_dataset": args.runs, "datasets": {}}
    for ds in args.datasets:
        reports = []
        for i in range(1, args.runs + 1):
            rep = run_once(ds, env, args.out / f"{args.arm}-{ds}-{i}.json")
            reports.append(rep)
            if args.arm == "provider" and rep.get("error") and "aggregate_score" not in rep:
                print(f"{ds} run {i}: judge error, stopping to avoid wasted spend", file=sys.stderr)
                result["datasets"][ds] = summarise(reports)
                (args.out / f"summary-{args.arm}.json").write_text(json.dumps(result, indent=2))
                return 2
        result["datasets"][ds] = summarise(reports)
        s = result["datasets"][ds]
        print(f"{ds:30s} median={s.get('median')} min={s.get('min')} max={s.get('max')} "
              f"spread={s.get('spread')} cost=${s['cost_usd']}")
    result["total_cost_usd"] = round(sum(d["cost_usd"] for d in result["datasets"].values()), 6)
    (args.out / f"summary-{args.arm}.json").write_text(json.dumps(result, indent=2))
    print(f"total estimated cost: ${result['total_cost_usd']}  ->  {args.out / ('summary-' + args.arm + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
