"""Asset records and the repository seam.

`AssetRepository` is the portable interface. `InMemoryAssetRepository` keeps the
agent runnable offline; `BigQueryAssetRepository` is the cloud adapter. The tool
never sees SQL or a client, so a different backend only has to implement `get`.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Protocol

ASSET_ID_PATTERN = re.compile(r"^[A-Z]{2,4}-\d{3,6}$")

ASSET_FIELDS = (
    "asset_id",
    "asset_type",
    "site",
    "criticality",
    "commissioned",
    "last_inspection",
    "next_inspection",
    "status",
    "notes",
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")


def normalise_asset_id(value: str | None) -> str:
    return (value or "").strip().upper()


class AssetRepository(Protocol):
    def get(self, asset_id: str) -> dict | None:
        """Return one asset record, or None when the id is unknown."""


class InMemoryAssetRepository:
    def __init__(self, assets: list[dict]) -> None:
        self._assets = {asset["asset_id"]: dict(asset) for asset in assets}

    def get(self, asset_id: str) -> dict | None:
        asset = self._assets.get(asset_id)
        return dict(asset) if asset else None


class BigQueryAssetRepository:
    """Read-only lookup against a BigQuery table.

    The query is parameterised and the column list is fixed. Configuration values
    are environment-controlled but still validated, because they are interpolated
    into the table reference.
    """

    def __init__(self, project: str, dataset: str, table: str) -> None:
        if not project:
            raise ValueError(
                "ASSETS_SOURCE=bigquery requires BQ_PROJECT or GOOGLE_CLOUD_PROJECT"
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

    def get(self, asset_id: str) -> dict | None:
        from google.cloud import bigquery

        query = (
            f"SELECT {', '.join(ASSET_FIELDS)} "
            f"FROM `{self.table_ref}` "
            "WHERE asset_id = @asset_id LIMIT 1"
        )
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("asset_id", "STRING", asset_id)
            ]
        )
        rows = list(self._get_client().query(query, job_config=config).result())
        return _json_safe(dict(rows[0])) if rows else None


def _json_safe(record: dict) -> dict:
    """BigQuery returns date/datetime objects; the tool contract is JSON."""
    return {
        key: value.isoformat() if isinstance(value, (date, datetime)) else value
        for key, value in record.items()
    }
