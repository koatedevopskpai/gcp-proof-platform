"""Trace storage: one JSONL object per run, local by default and GCS when configured.

The object is the source of truth for a scoring run. It carries the run header (ids, models,
dataset hash) and one line per case with the RAGAS scores and the per-statement trace, so a
number can be re-read without re-spending judge calls.

Local filesystem is the default so the same code path runs in tests and on a laptop; setting
``TRACE_BUCKET`` switches the sink to GCS without changing the payload.
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluator.contract import assert_sample_shape


def _serialise(payload: dict) -> str:
    run = payload.get("run")
    samples = payload.get("samples")
    if not isinstance(run, dict) or not isinstance(samples, list):
        raise ValueError("trace payload needs a 'run' object and a 'samples' list")
    if not samples:
        raise ValueError("trace payload has no samples")
    for sample in samples:
        assert_sample_shape(sample)
    lines = [json.dumps({"kind": "run", **run}, ensure_ascii=False)]
    lines += [json.dumps({"kind": "sample", **sample}, ensure_ascii=False) for sample in samples]
    return "\n".join(lines) + "\n"


def write_trace(payload: dict, *, run_id: str, bucket: str | None = None,
                local_dir: Path | None = None) -> str:
    """Write the trace and return where it landed (`gs://…` or an absolute path)."""
    body = _serialise(payload).encode("utf-8")
    if bucket:
        from google.cloud import storage  # lazy: not installed in the base image

        client = storage.Client()
        blob = client.bucket(bucket).blob(f"ragas/{run_id}.jsonl")
        blob.upload_from_string(body, content_type="application/x-ndjson")
        return f"gs://{bucket}/{blob.name}"

    directory = local_dir or Path("artifacts") / "traces"
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / f"{run_id}.jsonl").resolve()
    path.write_bytes(body)
    return str(path)
