"""eval-to-bq: run the MLOps evaluation gate and load the report into BigQuery.

Runs as a Cloud Run job (scheduled by Cloud Scheduler). Reuses the evaluator
package from services/evaluator - the same gate that runs in CI.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

# Reuse the evaluator's gate logic; point it at the bundled dataset.
sys.argv = [
    "eval",
    "--dataset", "/app/datasets/eval_set.jsonl",
    "--threshold", "0.8",
    "--report", "/tmp/report.json",
]

from evaluator.main import main as run_eval  # noqa: E402

rc = run_eval()
if rc not in (0, 1):
    raise SystemExit(rc)

with open("/tmp/report.json", encoding="utf-8") as fh:
    report = json.load(fh)

rows = []
for r in report.get("per_record", []):
    rows.append(
        {
            "report_date": date.today().isoformat(),
            "question": r.get("question"),
            "map_4": r.get("map@4"),
            "ndcg_4": r.get("ndcg@4"),
            "rouge_l": r.get("rouge_l"),
            "faithfulness": r.get("faithfulness"),
            "answer_relevancy": r.get("answer_relevancy"),
            "aggregate_score": report.get("aggregate_score"),
            "passed": report.get("passed"),
        }
    )

if not rows:
    print("No rows to load.")
    raise SystemExit(0)

from google.cloud import bigquery  # noqa: E402

project = os.environ["PROJECT_ID"]
dataset = os.environ["BQ_DATASET"]
table = os.environ["BQ_TABLE"]

client = bigquery.Client(project=project)
table_ref = f"{project}.{dataset}.{table}"
errors = client.insert_rows_json(table_ref, rows)
if errors:
    raise RuntimeError(f"BigQuery insert failed: {errors}")

print(f"Loaded {len(rows)} eval rows into {table_ref} (aggregate {report.get('aggregate_score')}, passed={report.get('passed')})")