"""LLM-as-judge client with a deterministic lexical fallback.

Running evaluation in CI with a real LLM is expensive and flaky. The mock judge is a
well-understood lexical heuristic so the gate is reproducible; set OPENAI_API_KEY to use a real
judge model.
"""
from __future__ import annotations

import os
import re
from collections import Counter

import httpx


class JudgeError(RuntimeError):
    """The judge could not produce a score. Never converted into a number."""


class JudgeClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
        # USD per million tokens for gpt-4o-mini: $0.15 input, $0.60 output (standard tier).
        # Checked against OpenAI's model docs on 2026-11-18. Override via env when the model
        # or price changes.
        self.price_in = float(os.getenv("JUDGE_PRICE_IN_PER_M", "0.15"))
        self.price_out = float(os.getenv("JUDGE_PRICE_OUT_PER_M", "0.60"))
        self.reset_usage()

    def reset_usage(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def usage(self) -> dict:
        """Tokens used and estimated cost since the last reset. Zero for the lexical arm."""
        cost = (self.prompt_tokens * self.price_in + self.completion_tokens * self.price_out) / 1e6
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_usd": round(cost, 6),
            "price_basis_usd_per_m_tokens": {"input": self.price_in, "output": self.price_out},
        }

    @property
    def arm(self) -> str:
        return "provider" if self.api_key else "lexical"

    def faithfulness(self, answer: str, contexts: list[str]) -> float:
        """Proportion of answer claims supported by the context."""
        if self.api_key:
            prompt = (
                "Rate faithfulness of the ANSWER to the CONTEXT from 0.0 to 1.0. "
                "Return only the number.\n\n"
                f"CONTEXT:\n{' '.join(contexts)}\n\nANSWER:\n{answer}"
            )
            return self._llm_score(prompt)
        return self._lexical_faithfulness(answer, contexts)

    def answer_relevancy(self, question: str, answer: str) -> float:
        if self.api_key:
            prompt = (
                "Rate how well ANSWER addresses QUESTION from 0.0 to 1.0. Return only the number.\n\n"
                f"QUESTION:\n{question}\n\nANSWER:\n{answer}"
            )
            return self._llm_score(prompt)
        return self._lexical_relevancy(question, answer)

    def complete(self, prompt: str) -> str:
        """Raw judge completion. Raises JudgeError; counts spend as soon as the provider answers."""
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise JudgeError(f"judge call failed: {type(exc).__name__}: {exc}") from exc
        self.calls += 1
        used = body.get("usage") or {}
        self.prompt_tokens += int(used.get("prompt_tokens", 0))
        self.completion_tokens += int(used.get("completion_tokens", 0))
        return text

    def _llm_score(self, prompt: str) -> float:
        """Return a score in [0, 1], or raise JudgeError. Fails closed: no fallback value."""
        text = self.complete(prompt)
        match = re.search(r"\b(?:0(?:\.\d+)?|1(?:\.0+)?)\b", text)
        if not match:
            raise JudgeError(f"judge returned no parseable score: {text[:80]!r}")
        return min(max(float(match.group()), 0.0), 1.0)

    @staticmethod
    def _tokens(text: str) -> Counter:
        return Counter(
            JudgeClient._stem(t)
            for t in re.findall(r"[a-z0-9]+", text.lower())
        )

    @staticmethod
    def _stem(word: str) -> str:
        stemmed = word
        for suffix in ("ing", "ed", "es", "s"):
            if len(stemmed) > 4 and stemmed.endswith(suffix):
                stemmed = stemmed[: -len(suffix)]
                break
        if len(stemmed) > 3 and stemmed.endswith("e"):
            stemmed = stemmed[:-1]
        return stemmed

    def _lexical_faithfulness(self, answer: str, contexts: list[str]) -> float:
        context_bag = sum((self._tokens(c) for c in contexts), Counter())
        ans = self._tokens(answer)
        if not ans:
            return 0.0
        supported = sum(count for tok, count in ans.items() if tok in context_bag)
        return min(supported / sum(ans.values()), 1.0)

    def _lexical_relevancy(self, question: str, answer: str) -> float:
        q = self._tokens(question)
        a = self._tokens(answer)
        if not a:
            return 0.0
        overlap = sum(count for tok, count in q.items() if tok in a)
        return min(overlap / max(sum(q.values()), 1) * 2.0, 1.0)


judge = JudgeClient()