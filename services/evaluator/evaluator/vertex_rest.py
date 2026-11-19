"""Vertex AI access over plain HTTP.

Why not the vendor SDKs: ``langchain-google-vertexai`` pulls ``google-cloud-aiplatform``, which
speaks gRPC, and both the chat and embedding clients intermittently hit ``DeadlineExceeded`` or hung
in this environment. The REST endpoints answered in about a second every time, so this module uses
them directly:

* chat through Vertex's OpenAI-compatible endpoint, so the existing ``ChatOpenAI`` adapter can be
  reused and returns plain string content (which RAGAS expects);
* embeddings through the ``:predict`` endpoint with a small LangChain ``Embeddings`` wrapper.

Authentication is the runtime identity: ADC locally, the Cloud Run service account in the job. No key.
"""
from __future__ import annotations

import httpx
from langchain_core.embeddings import Embeddings

SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def access_token() -> str:
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(scopes=[SCOPE])
    credentials.refresh(Request())
    return credentials.token


def chat_base_url(project: str, location: str) -> str:
    """The OpenAI-compatible surface of Vertex AI."""
    return (f"https://aiplatform.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/endpoints/openapi")


def _embedding_host(location: str) -> str:
    return "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"


class VertexRestEmbeddings(Embeddings):
    """LangChain embeddings backed by the Vertex REST predict endpoint."""

    def __init__(self, model: str, project: str, location: str = "us-central1",
                 timeout: float = 60.0, batch_size: int = 50) -> None:
        self.model = model
        self.project = project
        self.location = location
        self.timeout = timeout
        self.batch_size = batch_size
        self._token = None

    def _headers(self) -> dict:
        if self._token is None:
            self._token = access_token()
        return {"Authorization": f"Bearer {self._token}"}

    def _url(self) -> str:
        return (f"https://{_embedding_host(self.location)}/v1/projects/{self.project}"
                f"/locations/{self.location}/publishers/google/models/{self.model}:predict")

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {"instances": [{"content": text} for text in texts]}
        response = httpx.post(self._url(), headers=self._headers(), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return [item["embeddings"]["values"] for item in response.json()["predictions"]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start:start + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed_batch([text])[0]
