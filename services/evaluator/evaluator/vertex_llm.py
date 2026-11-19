"""Vertex AI judge for the statement trace and for RAGAS adapters.

Runs as either the local user (ADC) or the Cloud Run service account, so no API key is involved.
Cost is not computed here: Vertex pricing changes by model and region, and a made-up number is worse
than none. Tokens are recorded; the receipt states that spend is unpriced.
"""
from __future__ import annotations

import os

from evaluator.llm import JudgeError

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_LOCATION = "global"


class VertexJudge:
    def __init__(self, model: str | None = None, project: str | None = None,
                 location: str | None = None) -> None:
        self.model = model or os.getenv("VERTEX_MODEL", DEFAULT_MODEL)
        self.project = (project or os.getenv("VERTEX_PROJECT")
                        or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID"))
        self.location = location or os.getenv("VERTEX_LOCATION", DEFAULT_LOCATION)
        self._client = None
        self.reset_usage()

    @property
    def arm(self) -> str:
        return "vertex"

    def _chat(self):
        if self._client is None:
            from langchain_google_vertexai import ChatVertexAI

            self._client = ChatVertexAI(
                model=self.model,
                project=self.project,
                location=self.location,
                temperature=0,
            )
        return self._client

    def complete(self, prompt: str) -> str:
        try:
            response = self._chat().invoke(prompt)
        except Exception as exc:  # provider errors are errors, never scores
            raise JudgeError(f"vertex call failed: {type(exc).__name__}: {exc}") from exc

        self.calls += 1
        usage = getattr(response, "usage_metadata", None) or {}
        self.prompt_tokens += int(usage.get("input_tokens") or 0)
        self.completion_tokens += int(usage.get("output_tokens") or 0)

        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = "".join(
                part if isinstance(part, str) else str(part.get("text", "")) for part in content
            )
        return str(content)

    def reset_usage(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def usage(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": None,
            "pricing": "not applied: Vertex pricing is model- and region-specific",
        }
