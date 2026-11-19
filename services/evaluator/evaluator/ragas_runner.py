"""Run RAGAS scoring plus the per-statement trace, and write one trace object.

Shared by `scripts/ragas_run.py` (local) and `mlops/bigquery/run_pipeline.py` (Cloud Run), so
the job and a laptop produce the same artefact.

The output is a report: it never changes an exit code for quality reasons.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from evaluator import contract, faithfulness_trace, ragas_metrics, trace_store
from evaluator.llm import judge


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run(
    rows: list[dict],
    *,
    dataset_path: Path,
    label: str,
    judge_model: str,
    embedding_model: str,
    base_url: str,
    api_key: str,
    trace_bucket: str | None = None,
    local_trace_dir: Path | None = None,
    skip_trace: bool = False,
    log=print,
) -> dict:
    """Score, trace, write the trace object, return the payload plus its URI."""
    started = time.time()
    run_id = "ragas-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]

    log(f"scoring {len(rows)} cases with {judge_model} / {embedding_model}")
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
                 if skip_trace else faithfulness_trace.trace(row["answer"], row["contexts"]))
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
        log(f"  {position + 1}/{len(rows)} {row['case_id']}: "
            f"faithfulness={scores['faithfulness']} trace={trace['faithfulness']}")

    payload = {
        "run": {
            "run_id": run_id,
            "label": label,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge": {"model": judge_model, "base_url": base_url},
            "embedding_model": embedding_model,
            "dataset": {
                "path": str(dataset_path),
                "samples": len(rows),
                "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
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

    payload["trace_uri"] = trace_store.write_trace(
        payload, run_id=run_id, bucket=trace_bucket, local_dir=local_trace_dir
    )
    payload["run"]["trace_uri"] = payload["trace_uri"]
    return payload
