"""eval-to-bq: run the deterministic evaluation gate, optionally score with RAGAS, load BigQuery.

Runs as a Cloud Run job. Reuses the evaluator package from services/evaluator, so the gate that
fails a build is the same gate that writes the row.

Order matters: record first, then fail. A regression is written to BigQuery and then exits 1 so
the job-failure alert fires — the row is the evidence, the exit code is the signal.

RAGAS scoring is off unless RAGAS_ENABLED=1, because it needs a provider credential and ~2 GiB.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

DATASET = Path("/app/datasets/eval_set.jsonl")
RAGAS_DATASET = Path("/app/datasets/ragas_set.jsonl")
REPORT = Path("/tmp/report.json")


def run_gate() -> int:
    """Invoke the evaluator CLI with the job's fixed arguments."""
    sys.argv = [
        "eval",
        "--dataset", str(DATASET),
        "--threshold", "0.8",
        "--report", str(REPORT),
    ]
    from evaluator.main import main as run_eval

    return run_eval()


def score_with_ragas() -> str | None:
    """Score the RAGAS dataset and return the trace URI, or None when disabled."""
    if os.getenv("RAGAS_ENABLED") != "1":
        return None

    arm = os.getenv("SCORING_ARM", "openai")
    if arm == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("SCORING_ARM=openai but no provider credential is mounted")
    if arm == "vertex" and not (os.getenv("VERTEX_PROJECT") or os.getenv("PROJECT_ID")):
        raise SystemExit("SCORING_ARM=vertex but no project is configured")

    from evaluator import ragas_runner

    if arm == "openai":
        judge_model = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    else:
        # JUDGE_MODEL belongs to the OpenAI judge and is always set on this job; the Vertex arm
        # must not inherit it.
        judge_model = os.getenv("VERTEX_MODEL", "gemini-3-flash-preview")
        embedding_model = os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-005")

    payload = ragas_runner.run(
        ragas_runner.load_rows(RAGAS_DATASET),
        dataset_path=RAGAS_DATASET,
        label=os.getenv("RUN_LABEL", "cloud-run"),
        judge_model=judge_model,
        embedding_model=embedding_model,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY", ""),
        arm=arm,
        project=os.getenv("VERTEX_PROJECT") or os.getenv("PROJECT_ID"),
        location=os.getenv("VERTEX_LOCATION", "global"),
        embedding_location=os.getenv("VERTEX_EMBEDDING_LOCATION", "us-central1"),
        trace_bucket=os.getenv("TRACE_BUCKET") or None,
        local_trace_dir=Path(os.getenv("TRACE_LOCAL_DIR", "/tmp/traces")),
    )
    return payload["trace_uri"]


def main() -> int:
    rc = run_gate()
    if rc not in (0, 1):
        # Exit 2 is an operational error; there is no trustworthy report to load.
        raise SystemExit(rc)

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    trace_uri = score_with_ragas()

    from evaluator.bq_rows import build_rows

    rows = build_rows(report, trace_uri=trace_uri, report_date=date.today().isoformat())
    if not rows:
        print("No rows to load.")
        raise SystemExit(0)

    from google.cloud import bigquery

    project = os.environ["PROJECT_ID"]
    dataset = os.environ["BQ_DATASET"]
    table = os.environ["BQ_TABLE"]
    table_ref = f"{project}.{dataset}.{table}"

    errors = bigquery.Client(project=project).insert_rows_json(table_ref, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")

    print(f"Loaded {len(rows)} eval rows into {table_ref} "
          f"(gate passed={report.get('passed')}, aggregate {report.get('aggregate_score')}, "
          f"trace {trace_uri or 'none'})")

    if rc == 1:
        print("EVAL GATE FAILED: failing the job after recording the report.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
