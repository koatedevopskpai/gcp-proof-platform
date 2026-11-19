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
    arm: str = "openai",
    project: str | None = None,
    location: str | None = None,
    embedding_location: str | None = None,
    trace_bucket: str | None = None,
    local_trace_dir: Path | None = None,
    skip_trace: bool = False,
    log=print,
) -> dict:
    """Score, trace, write the trace object, return the payload plus its URI."""
    started = time.time()
    run_id = "ragas-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]

    log(f"scoring {len(rows)} cases with {arm}:{judge_model} / {embedding_model}")
    scored = ragas_metrics.score(
        rows, judge_model=judge_model, judge_base_url=base_url,
        judge_api_key=api_key, embedding_model=embedding_model,
        arm=arm, project=project, location=location,
        embedding_location=embedding_location,
    )
    by_case = {entry["case_id"]: entry for entry in scored["per_sample"]}

    if arm == "vertex":
        from evaluator.vertex_llm import VertexJudge

        client = VertexJudge(model=judge_model, project=project, location=location)
    else:
        client = judge

    samples = []
    client.reset_usage()
    trace_errors = 0
    for position, row in enumerate(rows):
        scores = {name: by_case.get(row["case_id"], {}).get(name) for name in contract.METRIC_NAMES}
        if skip_trace:
            trace = {"statements": [], "verdicts": [], "reasons": [], "supported": 0, "total": 0,
                     "faithfulness": None}
        else:
            try:
                trace = faithfulness_trace.trace(row["answer"], row["contexts"], client)
            except Exception as exc:  # a failed trace is recorded, not a reason to lose the run
                trace_errors += 1
                trace = {"statements": [], "verdicts": [], "reasons": [], "supported": 0, "total": 0,
                         "faithfulness": None, "error": f"{type(exc).__name__}: {exc}"}
                log(f"  {row['case_id']}: trace failed ({type(exc).__name__})")
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
            "trace_error": trace.get("error"),
        })
        log(f"  {position + 1}/{len(rows)} {row['case_id']}: "
            f"faithfulness={scores['faithfulness']} trace={trace['faithfulness']}")

    payload = {
        "run": {
            "run_id": run_id,
            "label": label,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge": {"arm": arm, "model": judge_model,
                      "base_url": base_url if arm == "openai" else None,
                      "project": project if arm == "vertex" else None,
                      "location": location if arm == "vertex" else None},
            "embedding_model": embedding_model,
            "dataset": {
                "path": str(dataset_path),
                "samples": len(rows),
                "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                "splits": sorted({row.get("split", "unknown") for row in rows}),
            },
            "aggregate": scored["aggregate"],
            "judge_usage": {"ragas": scored["usage"], "trace": client.usage()},
            "metric_names_returned": scored["metric_names_returned"],
            "duration_seconds": round(time.time() - started, 1),
            "trace_errors": trace_errors,
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
