"""Escalation sinks and the human-in-the-loop record.

An escalation is a row with `status=open`. That is a durable flag for a human to
pick up; it is not a ticket system, a pager, or an SLA. The sink seam keeps the
agent portable: BigQuery in GCP, another queue elsewhere.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Protocol

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")


class EscalationSink(Protocol):
    def create(self, record: dict) -> None:
        """Persist one escalation record. Raise if it cannot be stored."""


class FileEscalationSink:
    """Local stand-in: append JSONL. One process, one file; not a shared queue."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def create(self, record: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class BigQueryEscalationSink:
    def __init__(self, project: str, dataset: str, table: str) -> None:
        if not project:
            raise ValueError(
                "ESCALATION_SINK=bigquery requires BQ_PROJECT or GOOGLE_CLOUD_PROJECT"
            )
        for name, value in (("project", project), ("dataset", dataset), ("table", table)):
            if not _IDENTIFIER.match(value):
                raise ValueError(f"invalid BigQuery {name}: {value!r}")
        self.project = project
        self.dataset = dataset
        self.table = table
        self._client = None

    @property
    def table_ref(self) -> str:
        return f"{self.project}.{self.dataset}.{self.table}"

    def _get_client(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project)
        return self._client

    def create(self, record: dict) -> None:
        errors = self._get_client().insert_rows_json(self.table_ref, [record])
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")
