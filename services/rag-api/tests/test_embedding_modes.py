"""Embedding mode selection: explicit, testable, and never silently downgraded."""
import pytest

from app.core.config import Settings, settings
from app.services import embedding
from app.services.embedding import EmbeddingConfigurationError, EmbeddingService


def test_mode_is_normalised():
    assert Settings(embedding_mode="VERTEX").embedding_mode == "vertex"


def test_unknown_mode_is_rejected():
    with pytest.raises(EmbeddingConfigurationError, match="unknown embedding mode"):
        EmbeddingService(mode="sentence-transformers")


def test_openai_without_key_refuses_to_degrade(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(EmbeddingConfigurationError, match="OPENAI_API_KEY"):
        EmbeddingService(mode="openai")


def test_vertex_without_project_refuses_to_start(monkeypatch):
    monkeypatch.setattr(settings, "vertex_project", "")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("PROJECT_ID", raising=False)
    with pytest.raises(EmbeddingConfigurationError, match="VERTEX_PROJECT"):
        EmbeddingService(mode="vertex")


def test_vertex_passes_task_type_and_dimension_to_the_encoder():
    seen = {}

    def encoder(texts, task):
        seen["texts"] = texts
        seen["task"] = task
        return [[0.1] * 384 for _ in texts]

    svc = EmbeddingService(mode="vertex", dim=384, project="p", encoder=encoder)
    vector = svc.embed("transformer oil", task=embedding.RETRIEVAL_QUERY)

    assert len(vector) == 384
    assert seen == {"texts": ["transformer oil"], "task": embedding.RETRIEVAL_QUERY}


def test_dimension_mismatch_is_rejected():
    svc = EmbeddingService(
        mode="vertex", dim=384, project="p", encoder=lambda texts, task: [[0.0] * 768 for _ in texts]
    )
    with pytest.raises(EmbeddingConfigurationError, match="768 dimensions"):
        svc.embed("transformer oil")


def test_vertex_request_uses_the_predict_endpoint(monkeypatch):
    seen = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"predictions": [{"embeddings": {"values": [0.0] * 384}}]}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResponse()

    svc = EmbeddingService(mode="vertex", dim=384, project="gcp-proof-platform", location="us-central1")
    monkeypatch.setattr(embedding.httpx, "post", fake_post)
    monkeypatch.setattr(svc, "_token", lambda: "test-token")

    svc.embed("transformer oil", task=embedding.RETRIEVAL_QUERY)

    assert seen["url"] == (
        "https://us-central1-aiplatform.googleapis.com/v1/projects/gcp-proof-platform"
        "/locations/us-central1/publishers/google/models/text-embedding-005:predict"
    )
    assert seen["headers"] == {"Authorization": "Bearer test-token"}
    assert seen["json"]["instances"] == [
        {"task_type": "RETRIEVAL_QUERY", "content": "transformer oil"}
    ]
    assert seen["json"]["parameters"] == {"outputDimensionality": 384}


def test_mock_never_claims_a_real_model():
    svc = EmbeddingService(mode="mock")
    assert svc.embedding_model == "mock"
    assert svc.mode == "mock"


def test_refresh_transport_returns_a_google_auth_response(monkeypatch):
    class FakeHttpResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        content = b'{"access_token": "x"}'

    monkeypatch.setattr(embedding.httpx, "request", lambda *args, **kwargs: FakeHttpResponse())

    response = embedding._HttpxRequest()("https://oauth2.example/token", method="POST")

    assert response.status == 200
    assert response.headers["content-type"] == "application/json"
    assert response.data == b'{"access_token": "x"}'
