"""Run RAGAS scoring plus a per-statement trace over a stored-answer dataset.

    python scripts/ragas_run.py --arm openai --label local-1
    python scripts/ragas_run.py --arm vertex --label local-vertex-1

Report-only: it writes a trace object and a report, and never changes a gate or an exit code for
quality reasons (non-zero only on an operational failure).

Environment: OPENAI_API_KEY (openai arm only), OPENAI_BASE_URL, JUDGE_MODEL, EMBEDDING_MODEL,
SCORING_ARM, VERTEX_PROJECT, VERTEX_LOCATION, VERTEX_EMBEDDING_LOCATION,
TRACE_BUCKET (GCS sink; otherwise artifacts/traces/).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "evaluator"))

from evaluator import ragas_runner  # noqa: E402

DEFAULTS = {
    "openai": {"model": "gpt-4o-mini", "embedding": "text-embedding-3-small"},
    "vertex": {"model": "gemini-3-flash-preview", "embedding": "text-embedding-005"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="RAGAS scoring + statement trace (report only)")
    parser.add_argument("--dataset", type=Path,
                        default=ROOT / "services/evaluator/datasets/ragas_set.jsonl")
    parser.add_argument("--arm", choices=("openai", "vertex"),
                        default=os.getenv("SCORING_ARM", "openai"))
    parser.add_argument("--label", default="local")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/ragas")
    parser.add_argument("--trace-bucket", default=os.getenv("TRACE_BUCKET") or None)
    parser.add_argument("--project", default=os.getenv("VERTEX_PROJECT") or os.getenv("PROJECT_ID"))
    parser.add_argument("--location", default=os.getenv("VERTEX_LOCATION", "global"))
    parser.add_argument("--embedding-location",
                        default=os.getenv("VERTEX_EMBEDDING_LOCATION", "us-central1"))
    parser.add_argument("--skip-trace", action="store_true",
                        help="score only, no per-statement judge calls")
    args = parser.parse_args()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if args.arm == "openai" and not api_key:
        print("OPENAI_API_KEY is required for the openai arm", file=sys.stderr)
        return 2

    if args.arm == "vertex":
        judge_model = os.getenv("VERTEX_MODEL", DEFAULTS["vertex"]["model"])
        embedding_model = os.getenv("VERTEX_EMBEDDING_MODEL", DEFAULTS["vertex"]["embedding"])
    else:
        judge_model = os.getenv("JUDGE_MODEL", DEFAULTS["openai"]["model"])
        embedding_model = os.getenv("EMBEDDING_MODEL", DEFAULTS["openai"]["embedding"])

    rows = ragas_runner.load_rows(args.dataset)
    payload = ragas_runner.run(
        rows,
        dataset_path=args.dataset,
        label=args.label,
        judge_model=judge_model,
        embedding_model=embedding_model,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=api_key,
        arm=args.arm,
        project=args.project,
        location=args.location,
        embedding_location=args.embedding_location,
        trace_bucket=args.trace_bucket,
        local_trace_dir=ROOT / "artifacts" / "traces",
        skip_trace=args.skip_trace,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.out / f"{payload['run']['run_id']}.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    usage = payload["run"]["judge_usage"]
    print(json.dumps({
        "run_id": payload["run"]["run_id"],
        "arm": args.arm,
        "trace": payload["trace_uri"],
        "report": str(report_path),
        "ragas_cost_usd": (usage["ragas"] or {}).get("total_cost_usd"),
        "trace_cost_usd": usage["trace"]["estimated_cost_usd"],
        "aggregate": payload["run"]["aggregate"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
