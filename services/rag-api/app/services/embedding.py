"""Embedding service: mock, OpenAI-compatible, or Vertex AI.

Modes are explicit. A real mode that cannot be served raises at construction time
instead of silently falling back to mock vectors: a demo that claims semantic
retrieval while serving hashed trigrams is worse than a service that refuses to
start.
"""
from __future__ import annotations

import hashlib
import math
import os
import threading
from typing import Callable, Sequence

import google.auth
import google.auth.transport
import httpx

from app.core.config import settings

SCOPE = "https://www.googleapis.com/auth/cloud-platform"

MOCK = "mock"
OPENAI = "openai"
VERTEX = "vertex"
MODES = (MOCK, OPENAI, VERTEX)

RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
RETRIEVAL_QUERY = "RETRIEVAL_QUERY"

VERTEX_BATCH = 50


class EmbeddingConfigurationError(RuntimeError):
    """The configured embedding mode cannot be served."""


class _HttpxResponse(google.auth.transport.Response):
    """Concrete google-auth response, since its `Response` is an abstract base."""

    def __init__(self, status, headers, data) -> None:
        self._status = status
        self._headers = headers
        self._data = data

    @property
    def status(self):
        return self._status

    @property
    def headers(self):
        return self._headers

    @property
    def data(self):
        return self._data


class _HttpxRequest(google.auth.transport.Request):
    """google-auth refresh transport without pulling in `requests`."""

    def __call__(self, url, method="GET", body=None, headers=None, timeout=60, **kwargs):
        response = httpx.request(method, url, content=body, headers=headers, timeout=timeout)
        return _HttpxResponse(
            response.status_code, response.headers, response.content
        )


class EmbeddingService:
    def __init__(
        self,
        mode: str | None = None,
        dim: int | None = None,
        project: str | None = None,
        location: str | None = None,
        encoder: Callable[[list[str], str], list[list[float]]] | None = None,
    ) -> None:
        self.mode = (mode or settings.embedding_mode).strip().lower()
        if self.mode not in MODES:
            raise EmbeddingConfigurationError(
                f"unknown embedding mode {self.mode!r}; expected one of {', '.join(MODES)}"
            )

        self.dim = int(dim if dim is not None else settings.embedding_dim)
        self.project = (
            project
            or settings.vertex_project
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("PROJECT_ID")
            or ""
        )
        self.location = location or settings.vertex_location
        self._encoder = encoder
        self._lock = threading.Lock()
        self._credentials = None
        self._request = None

        if self.mode == OPENAI and not settings.openai_api_key:
            raise EmbeddingConfigurationError(
                "EMBEDDING_MODE=openai requires OPENAI_API_KEY; refusing to fall back to mock"
            )
        if self.mode == VERTEX and not self.project:
            raise EmbeddingConfigurationError(
                "EMBEDDING_MODE=vertex requires VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT"
            )

    @property
    def embedding_model(self) -> str:
        if self.mode == VERTEX:
            return settings.vertex_embedding_model
        if self.mode == OPENAI:
            return settings.embedding_model
        return MOCK

    def embed(self, text: str, task: str = RETRIEVAL_DOCUMENT) -> list[float]:
        return self.embed_texts([text], task=task)[0]

    def embed_texts(
        self, texts: Sequence[str], task: str = RETRIEVAL_DOCUMENT
    ) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []

        if self.mode == MOCK:
            vectors = [self._embed_mock(t) for t in items]
        elif self._encoder is not None:
            vectors = self._encoder(items, task)
        elif self.mode == OPENAI:
            vectors = self._embed_openai(items)
        else:
            vectors = self._embed_vertex(items, task)

        self._check_dimensions(vectors)
        return vectors

    def _check_dimensions(self, vectors: list[list[float]]) -> None:
        for vector in vectors:
            if len(vector) != self.dim:
                raise EmbeddingConfigurationError(
                    f"embedding returned {len(vector)} dimensions but EMBEDDING_DIM is "
                    f"{self.dim}; recreate the documents table and re-ingest the corpus"
                )

    def _embed_mock(self, text: str) -> list[float]:
        """Deterministic seeded vector from hashed character trigrams.

        Character trigrams give morphological similarity (e.g. "refund" ~ "refunds"),
        so retrieval behaves plausibly without an external model. This is not semantic
        retrieval and must not be presented as such.
        Must be byte-identical to the .NET mock embedder so the shared pgvector
        store is interoperable across languages.
        """
        vec = [0.0] * self.dim
        for word in text.lower().split():
            padded = f"#{word}#"
            for i in range(len(padded) - 2):
                tri = padded[i : i + 3]
                digest = hashlib.sha256(tri.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload = {
            "model": settings.embedding_model,
            "input": texts,
            "dimensions": self.dim,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{settings.openai_base_url}/embeddings", json=payload, headers=headers
            )
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]

    def _embed_vertex(self, texts: list[str], task: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), VERTEX_BATCH):
            batch = texts[start : start + VERTEX_BATCH]
            payload = {
                "instances": [{"task_type": task, "content": text} for text in batch],
                "parameters": {"outputDimensionality": self.dim},
            }
            response = httpx.post(
                self._vertex_url(),
                headers={"Authorization": f"Bearer {self._token()}"},
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            vectors.extend(
                item["embeddings"]["values"] for item in response.json()["predictions"]
            )
        return vectors

    def _vertex_url(self) -> str:
        host = (
            "aiplatform.googleapis.com"
            if self.location == "global"
            else f"{self.location}-aiplatform.googleapis.com"
        )
        return (
            f"https://{host}/v1/projects/{self.project}/locations/{self.location}"
            f"/publishers/google/models/{settings.vertex_embedding_model}:predict"
        )

    def _token(self) -> str:
        """Runtime identity: ADC locally, the Cloud Run service account in the job."""
        with self._lock:
            if self._credentials is None:
                credentials, _ = google.auth.default(scopes=[SCOPE])
                self._credentials = credentials
                self._request = _HttpxRequest()
            if not self._credentials.valid:
                self._credentials.refresh(self._request)
            return self._credentials.token


embedding_service = EmbeddingService()
