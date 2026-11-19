"""Per-statement faithfulness trace.

RAGAS returns one number per case. That number cannot be audited after the fact: you cannot
see which claim was judged unsupported or why. This module records the reasoning — the answer
is split into atomic statements and each one is checked against the retrieved contexts — so a
score of 0.3333 can be read as "one of three statements was supported, and here is the reason".

It is a report, never a gate. Statements come from a single judge call, verdicts from one call
per statement, all at temperature 0, and every call is counted in `judge.usage()`.
"""
from __future__ import annotations

import json
import re

from evaluator.llm import judge

MAX_STATEMENTS = 12

_SPLIT_PROMPT = (
    "Split the ANSWER into atomic factual statements. One statement per line, no numbering, "
    "no bullets, no commentary. Keep numbers and units exactly as written. "
    "If the answer is a single statement, return that line only.\n\n"
    "ANSWER:\n{answer}"
)

_VERIFY_PROMPT = (
    "Decide whether the STATEMENT is supported by the CONTEXT. A statement is supported only "
    "if the context entails it. A changed number, date or scope is not supported.\n\n"
    "Reply with JSON only, no prose: "
    '{{"verdict": "supported" or "unsupported", "reason": "<one short sentence>"}}\n\n'
    "CONTEXT:\n{context}\n\nSTATEMENT:\n{statement}"
)


def split_statements(answer: str) -> list[str]:
    """Atomic statements, in the answer's own words."""
    text = judge.complete(_SPLIT_PROMPT.format(answer=answer))
    statements = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if line:
            statements.append(line)
    return statements[:MAX_STATEMENTS]


def _parse_verdict(text: str) -> tuple[str, str]:
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        try:
            payload = json.loads(match.group())
            verdict = str(payload.get("verdict", "")).strip().lower()
            reason = str(payload.get("reason", "")).strip()
            if verdict in {"supported", "unsupported"}:
                return verdict, reason
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    lowered = text.lower()
    if "unsupported" in lowered or "not supported" in lowered:
        return "unsupported", text.strip()[:200]
    if "supported" in lowered:
        return "supported", text.strip()[:200]
    return "unsupported", f"unparseable verdict: {text.strip()[:120]}"


def verify_statement(statement: str, contexts: list[str]) -> tuple[str, str]:
    context = "\n".join(f"- {c}" for c in contexts)
    return _parse_verdict(judge.complete(_VERIFY_PROMPT.format(context=context, statement=statement)))


def trace(answer: str, contexts: list[str]) -> dict:
    """Statements, per-statement verdicts and reasons, plus the ratio they imply."""
    statements = split_statements(answer)
    verdicts, reasons = [], []
    for statement in statements:
        verdict, reason = verify_statement(statement, contexts)
        verdicts.append(verdict)
        reasons.append(reason)
    supported = sum(1 for verdict in verdicts if verdict == "supported")
    return {
        "statements": statements,
        "verdicts": verdicts,
        "reasons": reasons,
        "supported": supported,
        "total": len(statements),
        "faithfulness": round(supported / len(statements), 4) if statements else None,
    }
