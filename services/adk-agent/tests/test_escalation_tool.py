"""The escalation contract: open records, redaction, and fail-closed behaviour."""
import json
from datetime import datetime, timezone

from support_agent.adapters.escalations import FileEscalationSink
from support_agent.tools.escalation import build_escalate

FIXED_NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


class MemorySink:
    def __init__(self):
        self.records = []

    def create(self, record):
        self.records.append(record)


def escalation(sink):
    return build_escalate(sink, clock=lambda: FIXED_NOW, new_id=lambda: "ESC-TEST01")


def test_creates_an_open_hitl_record():
    sink = MemorySink()
    out = escalation(sink)(
        "user asks for HV switching authority",
        "Can I isolate SW-0455 myself?",
        asset_id=" sw-0455 ",
        urgency="HIGH",
    )

    assert out["status"] == "logged"
    assert out["escalation_id"] == "ESC-TEST01"
    record = sink.records[0]
    assert record["status"] == "open"
    assert record["asset_id"] == "SW-0455"
    assert record["urgency"] == "high"
    assert record["source"] == "adk-support-agent"
    assert record["created_at"] == "2026-11-23T12:00:00+00:00"


def test_missing_reason_or_question_is_rejected():
    sink = MemorySink()

    assert escalation(sink)("", "question")["status"] == "error"
    assert escalation(sink)("reason", "   ")["status"] == "error"
    assert sink.records == []


def test_invalid_asset_id_is_rejected():
    sink = MemorySink()

    out = escalation(sink)("reason", "question", asset_id="SW 0455")

    assert out["error"] == "invalid_asset_id"
    assert sink.records == []


def test_sink_failure_fails_closed():
    class Broken:
        def create(self, record):
            raise RuntimeError("bigquery unavailable")

    out = escalation(Broken())("reason", "question")

    assert out["status"] == "error"
    assert out["error"] == "escalation_unavailable"
    assert "do not claim" in out["message"]
    assert "duty controller" in out["message"]


def test_pii_is_redacted_before_storage():
    sink = MemorySink()
    escalation(sink)(
        "contact a.b@example.com",
        "call 07700 900123 about card 4111 1111 1111 1111",
    )

    record = sink.records[0]
    assert "@" not in record["reason"]
    assert "07700" not in record["question"]
    assert "4111" not in record["question"]
    assert "[REDACTED]" in record["question"]


def test_file_sink_appends_one_json_line_per_escalation(tmp_path):
    path = tmp_path / "escalations.jsonl"
    sink = FileEscalationSink(path)

    escalation(sink)("first", "question one")
    escalation(sink)("second", "question two")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["reason"] == "first"
    assert json.loads(lines[1])["status"] == "open"
