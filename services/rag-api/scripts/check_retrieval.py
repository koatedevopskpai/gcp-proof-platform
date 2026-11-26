"""Replay a fixed query set against a running rag-api and report retrieval quality.

    python services/rag-api/scripts/check_retrieval.py --url http://localhost:8010 \
        --output evidence/adk-agent/raw/retrieval-vertex.json

The query set contains paraphrases on purpose: they show whether retrieval is
matching meaning or only surface words. Results are reported as-is; a low score is
a finding, not something to tune away in the script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

QUERIES = [
    {
        "query": "How often is transformer oil tested for dissolved gases?",
        "expected": "rail-001",
        "kind": "direct",
    },
    {
        "query": "lubricant analysis frequency for traction units",
        "expected": "rail-001",
        "kind": "paraphrase",
    },
    {
        "query": "What happens when a track circuit fails?",
        "expected": "rail-006",
        "kind": "direct",
    },
    {
        "query": "How do we locate a burst water main?",
        "expected": "util-001",
        "kind": "direct",
    },
    {
        "query": "When is a gas governor pressure-tested?",
        "expected": "util-003",
        "kind": "direct",
    },
    {
        "query": "What is the maximum allowed gauge widening on plain line?",
        "expected": "rail-003",
        "kind": "direct",
    },
    {
        "query": "How is a rail defect found before it breaks?",
        "expected": "rail-004",
        "kind": "paraphrase",
    },
    {
        "query": "What keeps SCADA alarms under control?",
        "expected": "util-006",
        "kind": "paraphrase",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8010")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    base = args.url.rstrip("/")
    rows = []
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()
        info = health.json()

        for item in QUERIES:
            response = client.post(
                f"{base}/search", json={"query": item["query"], "top_k": args.top_k}
            )
            response.raise_for_status()
            payload = response.json()
            hits = payload.get("results", [])
            ids = [hit["id"] for hit in hits]
            rank = ids.index(item["expected"]) + 1 if item["expected"] in ids else None
            rows.append(
                {
                    **item,
                    "rank": rank,
                    "top": [
                        {"id": hit["id"], "score": hit["score"]} for hit in hits
                    ],
                }
            )

    total = len(rows)
    hit_at_1 = sum(1 for row in rows if row["rank"] == 1) / total
    hit_at_k = sum(1 for row in rows if row["rank"]) / total
    mrr = sum(1 / row["rank"] for row in rows if row["rank"]) / total

    report = {
        "embedding_mode": info.get("embedding_mode"),
        "embedding_model": info.get("embedding_model"),
        "embedding_dim": info.get("embedding_dim"),
        "top_k": args.top_k,
        "queries": total,
        "hit_at_1": round(hit_at_1, 4),
        "hit_at_k": round(hit_at_k, 4),
        "mrr": round(mrr, 4),
        "results": rows,
    }

    for row in rows:
        top = ", ".join(f"{hit['id']}@{hit['score']}" for hit in row["top"])
        rank = row["rank"] if row["rank"] else "miss"
        print(f"[{row['kind']:<10}] {row['expected']} rank={rank:<4} {top}")
        print(f"             {row['query']}")

    print(
        f"\nmode={report['embedding_mode']} model={report['embedding_model']} "
        f"dim={report['embedding_dim']} hit@1={hit_at_1:.2f} "
        f"hit@{args.top_k}={hit_at_k:.2f} mrr={mrr:.2f}"
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
