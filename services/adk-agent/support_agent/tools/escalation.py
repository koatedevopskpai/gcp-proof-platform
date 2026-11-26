"""Human-in-the-loop escalation tool.

It writes one record with `status=open` and returns a reference. It deliberately
does not claim the request is resolved, and it fails closed if the sink fails.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from support_agent.adapters.assets import ASSET_ID_PATTERN, normalise_asset_id
from support_agent.adapters.escalations import (
    BigQueryEscalationSink,
    EscalationSink,
    FileEscalationSink,
)
from support_agent.config import settings
from support_agent.guardrails import redact_text

logger = logging.getLogger(__name__)

Urgency = str
ALLOWED_URGENCY = {"low", "normal", "high"}


def build_escalate(
    sink: EscalationSink,
    *,
    clock: Callable[[], datetime] | None = None,
    new_id: Callable[[], str] | None = None,
) -> Callable[..., dict]:
    clock = clock or (lambda: datetime.now(timezone.utc))
    new_id = new_id or (lambda: f"ESC-{uuid4().hex[:8].upper()}")

    def escalate(
        reason: str,
        question: str,
        asset_id: str = "",
        urgency: str = "normal",
    ) -> dict:
        """Raise a human-in-the-loop escalation and return a reference.

        Call this when the user asks for an authorisation or decision you cannot
        make, when the knowledge base does not cover a support question, or when
        the user asks for a human. Do not call it for questions you can answer
        from the knowledge base, and never escalate silently.

        Args:
            reason: A short reason for the hand-off (for example "request for HV
                switching authority").
            question: The user's question, restated so a reviewer can act on it.
            asset_id: The related asset id, if one was named. Leave empty if not.
            urgency: "low", "normal" or "high". Use "high" only when the user
                reports a safety-critical or supply-affecting situation.

        Returns:
            A dict with `status` "logged" and an `escalation_id`, or "error" if
            the record could not be stored. On error, tell the user to contact
            the duty controller directly and do not claim a ticket was raised.
        """
        reason = " ".join((reason or "").split())[:500]
        question = " ".join((question or "").split())[:2_000]
        if not reason or not question:
            return {
                "status": "error",
                "error": "invalid_escalation",
                "message": "Both a reason and the user's question are required.",
            }

        asset = normalise_asset_id(asset_id)
        if asset and not ASSET_ID_PATTERN.match(asset):
            return {
                "status": "error",
                "error": "invalid_asset_id",
                "message": "Asset ids look like TR-1042; omit the id if none was given.",
            }

        urgency = (urgency or "normal").strip().lower()
        if urgency not in ALLOWED_URGENCY:
            urgency = "normal"

        record = {
            "escalation_id": new_id(),
            "created_at": clock().isoformat(),
            "asset_id": asset or None,
            "reason": redact_text(reason),
            "question": redact_text(question),
            "urgency": urgency,
            "status": "open",
            "source": "adk-support-agent",
        }

        try:
            sink.create(record)
        except Exception:
            logger.exception("escalation sink failed")
            return {
                "status": "error",
                "error": "escalation_unavailable",
                "message": (
                    "The escalation could not be recorded. Tell the user to "
                    "contact the duty controller directly; do not claim a ticket "
                    "was raised."
                ),
            }

        return {
            "status": "logged",
            "escalation_id": record["escalation_id"],
            "created_at": record["created_at"],
            "message": (
                "Tell the user the reference and that a human will review it. "
                "It is not resolved yet."
            ),
        }

    return escalate


def build_default_sink() -> EscalationSink:
    if settings.escalation_sink == "bigquery":
        return BigQueryEscalationSink(
            project=settings.bq_project or os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            dataset=settings.escalations_dataset,
            table=settings.escalations_table,
        )
    return FileEscalationSink(settings.escalation_file)


escalate = build_escalate(build_default_sink())
