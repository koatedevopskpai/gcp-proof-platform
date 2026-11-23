"""The retrieval tool contract: shapes returned on success and on failure."""
import httpx

from support_agent.tools import knowledge


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_search_returns_ranked_passages(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        return FakeResponse(
            {
                "query": json["query"],
                "count": 1,
                "results": [{"id": "doc-1", "content": "Transformer oil is sampled annually.", "score": 0.82}],
            }
        )

    monkeypatch.setattr(knowledge.httpx, "post", fake_post)

    out = knowledge.search_knowledge("transformer oil sampling", top_k=3)

    assert seen["url"].endswith("/search")
    assert seen["json"] == {"query": "transformer oil sampling", "top_k": 3}
    assert out["status"] == "ok"
    assert out["count"] == 1
    assert out["passages"][0] == {
        "id": "doc-1",
        "content": "Transformer oil is sampled annually.",
        "score": 0.82,
    }


def test_search_clamps_top_k_to_api_bounds(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen.update(json)
        return FakeResponse({"query": json["query"], "results": []})

    monkeypatch.setattr(knowledge.httpx, "post", fake_post)

    knowledge.search_knowledge("anything", top_k=99)
    assert seen["top_k"] == 20

    knowledge.search_knowledge("anything", top_k=0)
    assert seen["top_k"] == 1


def test_search_failure_does_not_return_passages(monkeypatch):
    def fake_post(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(knowledge.httpx, "post", fake_post)

    out = knowledge.search_knowledge("transformer oil sampling")

    assert out["status"] == "error"
    assert out["error"] == "retrieval_unavailable"
    assert "passages" not in out
    assert "unavailable" in out["message"].lower()


def test_empty_query_is_rejected_without_calling_the_api(monkeypatch):
    def fake_post(*args, **kwargs):
        raise AssertionError("the API should not be called")

    monkeypatch.setattr(knowledge.httpx, "post", fake_post)

    out = knowledge.search_knowledge("   ")
    assert out["status"] == "error"
    assert out["error"] == "empty_query"


def test_passage_text_is_truncated(monkeypatch):
    long_text = "x" * 5_000

    monkeypatch.setattr(
        knowledge.httpx,
        "post",
        lambda url, json, timeout: FakeResponse(
            {"query": json["query"], "results": [{"id": "doc-1", "content": long_text, "score": 0.5}]}
        ),
    )

    out = knowledge.search_knowledge("long passage")
    assert out["passages"][0]["content"].endswith(" ...")
    assert len(out["passages"][0]["content"]) <= knowledge.settings.max_passage_chars + 4
