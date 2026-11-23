"""Model-input guardrails.

Runs as an ADK `before_model_callback`: it can short-circuit a turn by returning a
response, or mutate the request in place (PII redaction) and let the model run.
"""
from __future__ import annotations

import re

from google.adk.agents.context import Context
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

BLOCKED_MESSAGE = (
    "I can't help with that request. Rephrase it as a question about the asset "
    "knowledge base."
)

# Same intent as rag-api's guardrail, with the "reveal your instructions" family added.
INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?(previous|prior|above) (instructions|rules)", re.I),
    re.compile(r"(reveal|show|print|repeat) (me )?(your|the) (system )?(prompt|instructions)", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"you are now (a|an|dan)", re.I),
    re.compile(r"<\|im_start\|>", re.I),
]

# Deliberately narrower than rag-api's digit run so rail asset numbers survive:
# an email, a UK phone number, or a 13-16 digit card number.
PII_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"(?:\+44\s?|0)(?:\d[\s-]?){9,10}\d"),
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),
]

REDACTED = "[REDACTED]"


def before_model_callback(context: Context, llm_request: LlmRequest) -> LlmResponse | None:
    """Block prompt injection and redact personal data before the model sees it."""
    text = latest_user_text(llm_request)
    if not text:
        return None

    if any(pattern.search(text) for pattern in INJECTION_PATTERNS):
        return LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=BLOCKED_MESSAGE)])
        )

    redact_pii(llm_request)
    return None


def latest_user_text(llm_request: LlmRequest) -> str:
    """Return the most recent user turn as plain text, or an empty string."""
    for content in reversed(llm_request.contents or []):
        if content.role != "user":
            continue
        return " ".join(part.text for part in content.parts or [] if part.text).strip()
    return ""


def redact_pii(llm_request: LlmRequest) -> None:
    """Replace emails, phone numbers and card numbers in user turns, in place."""
    for content in llm_request.contents or []:
        if content.role != "user":
            continue
        for part in content.parts or []:
            if part.text:
                part.text = redact_text(part.text)


def redact_text(text: str) -> str:
    for pattern in PII_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text
