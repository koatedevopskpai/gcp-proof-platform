"""Retrieval tool: the agent's only route into the knowledge base.

It calls `rag-api`'s `POST /search` over HTTP. The agent never talks to Postgres,
so the retrieval contract stays behind one service boundary.
"""
from __future__ import annotations

import httpx

from support_agent.config import settings

METADATA_IDENTITY_URL = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/identity"
)


def _authorization_headers() -> dict:
    """Return an ID token for rag-api when an audience is configured.

    On Cloud Run the metadata server is the identity source; there is no key. If
    the audience is unset (local Compose), the call stays unauthenticated.
    """
    audience = settings.rag_api_audience
    if not audience:
        return {}
    response = httpx.get(
        METADATA_IDENTITY_URL,
        params={"audience": audience, "format": "full"},
        headers={"Metadata-Flavor": "Google"},
        timeout=5.0,
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.text.strip()}"}


def search_knowledge(query: str, top_k: int | None = None) -> dict:
    """Search the asset knowledge base for passages relevant to a question.

    Use this before answering any question about rail or utility assets. It returns
    ranked passages; if it returns none, tell the user the knowledge base does not
    cover the question instead of answering from general knowledge.

    Args:
        query: A self-contained search query. Do not include credentials or personal
            data; include the asset type and the topic (for example, "substation
            transformer oil sampling interval").
        top_k: How many passages to return, 1-20. Defaults to the service setting.

    Returns:
        A dict with `status` set to "ok" or "error". On success it carries `passages`,
        each with an `id`, `content`, and relevance `score`. On failure it carries a
        short `message` explaining that retrieval is unavailable.
    """
    query = (query or "").strip()
    if not query:
        return {
            "status": "error",
            "error": "empty_query",
            "message": "The search query was empty; ask the user to restate the question.",
        }

    k = top_k if isinstance(top_k, int) else settings.rag_top_k
    k = max(1, min(k, 20))

    try:
        response = httpx.post(
            f"{settings.rag_api_url.rstrip('/')}/search",
            json={"query": query, "top_k": k},
            headers=_authorization_headers(),
            timeout=settings.rag_api_timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {
            "status": "error",
            "error": "retrieval_unavailable",
            "message": (
                "The knowledge base is unreachable, so this question cannot be grounded. "
                f"Tell the user retrieval is unavailable and do not answer from memory. ({type(exc).__name__})"
            ),
        }
    except ValueError:
        return {
            "status": "error",
            "error": "invalid_response",
            "message": (
                "The knowledge base returned an unreadable response. Tell the user "
                "retrieval is unavailable and do not answer from memory."
            ),
        }

    passages = []
    for item in payload.get("results", [])[:k]:
        content = str(item.get("content", ""))
        if len(content) > settings.max_passage_chars:
            content = content[: settings.max_passage_chars].rstrip() + " ..."
        passages.append(
            {
                "id": item.get("id"),
                "content": content,
                "score": item.get("score"),
            }
        )

    return {
        "status": "ok",
        "query": query,
        "count": len(passages),
        "passages": passages,
    }
