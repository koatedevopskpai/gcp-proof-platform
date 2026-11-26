"""Cloud adapters checked without cloud credentials: query shape and error paths."""
from datetime import date

import pytest

from support_agent.adapters.assets import BigQueryAssetRepository
from support_agent.adapters.escalations import BigQueryEscalationSink


class FakeJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeQueryClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, sql, job_config=None):
        self.calls.append((sql, job_config))
        return FakeJob(self.rows)


def test_asset_query_is_parameterised_and_dates_are_json_safe():
    client = FakeQueryClient(
        [
            {
                "asset_id": "TR-1042",
                "asset_type": "33/11 kV transformer",
                "site": "Ashford Grid",
                "criticality": 5,
                "commissioned": date(2009, 3, 12),
                "last_inspection": date(2026, 9, 2),
                "next_inspection": date(2027, 9, 2),
                "status": "in service",
                "notes": "Annual DGA.",
            }
        ]
    )
    repo = BigQueryAssetRepository("project", "ai_platform", "assets")
    repo._client = client

    asset = repo.get("TR-1042")

    sql, config = client.calls[0]
    assert "WHERE asset_id = @asset_id LIMIT 1" in sql
    assert config.query_parameters[0].name == "asset_id"
    assert config.query_parameters[0].value == "TR-1042"
    assert asset["commissioned"] == "2009-03-12"
    assert asset["next_inspection"] == "2027-09-02"


def test_unknown_asset_returns_none():
    repo = BigQueryAssetRepository("project", "ai_platform", "assets")
    repo._client = FakeQueryClient([])

    assert repo.get("ZZ-0000") is None


def test_bigquery_requires_a_project():
    with pytest.raises(ValueError, match="requires BQ_PROJECT"):
        BigQueryAssetRepository("", "ai_platform", "assets")
    with pytest.raises(ValueError, match="requires BQ_PROJECT"):
        BigQueryEscalationSink("", "ai_platform", "agent_escalations")


def test_identifiers_cannot_carry_sql():
    with pytest.raises(ValueError, match="invalid BigQuery table"):
        BigQueryAssetRepository("project", "ai_platform", "assets`; DROP TABLE x")


def test_escalation_insert_rows_and_surfaces_errors():
    class Client:
        def __init__(self, errors):
            self.errors = errors
            self.calls = []

        def insert_rows_json(self, table, rows):
            self.calls.append((table, rows))
            return self.errors

    sink = BigQueryEscalationSink("project", "ai_platform", "agent_escalations")
    sink._client = Client([])
    sink.create({"escalation_id": "ESC-1", "status": "open"})

    table, rows = sink._client.calls[0]
    assert table == "project.ai_platform.agent_escalations"
    assert rows[0]["escalation_id"] == "ESC-1"

    sink._client = Client([{"index": 0, "errors": ["bad row"]}])
    with pytest.raises(RuntimeError, match="BigQuery insert failed"):
        sink.create({"escalation_id": "ESC-2"})
