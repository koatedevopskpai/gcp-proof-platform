"""Cloud Run job entrypoint for the phase-4 RAGAS/Vertex baseline.

Scoring is per case, with a bounded timeout. A hung judge call marks that case null
instead of losing the whole run. The report is uploaded to GCS and per-case rows are
inserted into `ai_platform.eval_reports`.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery, storage

from evaluator import ragas_metrics
from eval_support import build_bq_rows

DATASET = Path("/app/phase4/captured.jsonl")
TRAJECTORY = Path("/app/phase4/trajectory.json")
PROJECT = os.environ["VERTEX_PROJECT"]
BUCKET = os.environ.get("REPORT_BUCKET", "gcp-proof-platform-eval-traces")
TABLE = f"{os.environ['BQ_PROJECT']}.ai_platform.eval_reports"
METRICS = ("faithfulness", "answer_relevancy")


def _mean(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return round(sum(present) / len(present), 4) if present else None


def main() -> None:
    rows = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = [
        value.strip()
        for value in os.getenv("PHASE4_CASE_IDS", "").split(",")
        if value.strip()
    ]
    if selected:
        rows = [row for row in rows if row["case_id"] in selected]
        if not rows:
            raise SystemExit(f"no captured rows match {selected}")
    load_bq = os.getenv("PHASE4_LOAD", "true").lower() != "false"
    started = time.time()
    judge_model = os.environ.get("VERTEX_MODEL", "gemini-3-flash-preview")
    embedding_model = os.environ.get("VERTEX_EMBEDDING_MODEL", "text-embedding-005")
    location = os.environ.get("VERTEX_LOCATION", "global")
    embedding_location = os.environ.get("VERTEX_EMBEDDING_LOCATION", "us-central1")

    samples = []
    for position, row in enumerate(rows, start=1):
        print(f"[{position}/{len(rows)}] {row['case_id']}", flush=True)
        try:
            result = ragas_metrics.score(
                [row],
                judge_model=judge_model,
                judge_base_url="",
                judge_api_key="",
                embedding_model=embedding_model,
                arm="vertex",
                project=PROJECT,
                location=location,
                embedding_location=embedding_location,
                raise_exceptions=True,
            )
            per_case = result["per_sample"][0]
            scores = {name: per_case.get(name) for name in METRICS}
            error = None
            print(f"  scores {scores}", flush=True)
        except Exception as exc:  # one bad case must not lose the run
            scores = {name: None for name in METRICS}
            error = f"{type(exc).__name__}: {exc}"
            print(f"  FAILED {error}", flush=True)

        samples.append(
            {
                "case_id": row["case_id"],
                "question": row["question"],
                "answer": row["answer"],
                "contexts": list(row["contexts"]),
                "reference": row["reference"],
                "scores": scores,
                "error": error,
            }
        )

    run_id = (
        "ragas-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + hashlib.sha256(str(time.time()).encode()).hexdigest()[:6]
    )
    aggregate = {name: _mean([sample["scores"][name] for sample in samples]) for name in METRICS}
    payload = {
        "run": {
            "run_id": run_id,
            "label": "phase4-baseline",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge": {"arm": "vertex", "model": judge_model, "project": PROJECT, "location": location},
            "embedding_model": embedding_model,
            "dataset": {
                "path": str(DATASET),
                "samples": len(rows),
                "sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            },
            "aggregate": aggregate,
            "metric_names_returned": list(METRICS),
            "duration_seconds": round(time.time() - started, 1),
            "trace_errors": sum(1 for sample in samples if sample["error"]),
            "limits": [
                "per-case scoring with a bounded timeout; failed cases are null, not omitted",
                "captured agent answers, not a benchmark",
                "report-only: these scores do not gate promotion",
            ],
        },
        "samples": samples,
        "trace_uri": None,
    }

    report_path = Path("/tmp") / f"{run_id}.json"
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    report_uri = f"phase4/ragas/{run_id}.json"
    storage.Client(project=PROJECT).bucket(BUCKET).blob(report_uri).upload_from_filename(
        str(report_path)
    )
    print(f"REPORT_URI gs://{BUCKET}/{report_uri}", flush=True)

    if load_bq:
        trajectory = json.loads(TRAJECTORY.read_text(encoding="utf-8"))
        bq_rows = build_bq_rows(payload, trajectory)
        errors = bigquery.Client(project=PROJECT).insert_rows_json(TABLE, bq_rows)
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")
        print(f"LOADED {len(bq_rows)} rows into {TABLE}", flush=True)
    else:
        print("LOAD_SKIPPED (PHASE4_LOAD=false)", flush=True)


if __name__ == "__main__":
    main()
