"""Load a JSONL corpus into a running rag-api via POST /ingest.

    python services/rag-api/scripts/ingest_corpus.py --url http://localhost:8010

The API embeds each document at ingest time, so re-run this after changing the
embedding mode, dimension or model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "datasets" / "rail_utilities_seed.jsonl"


def load_documents(path: Path) -> list[dict]:
    documents = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{number}: invalid JSON ({exc})") from exc
        if not item.get("id") or not item.get("content"):
            raise SystemExit(f"{path}:{number}: each line needs 'id' and 'content'")
        documents.append(item)
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8010")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="skip documents the API reports as already present",
    )
    args = parser.parse_args()

    documents = load_documents(args.file)
    failed = 0
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{args.url.rstrip('/')}/health")
        health.raise_for_status()
        info = health.json()
        print(
            f"target {args.url} mode={info.get('embedding_mode')} "
            f"model={info.get('embedding_model')} dim={info.get('embedding_dim')}"
        )

        for document in documents:
            response = client.post(
                f"{args.url.rstrip('/')}/ingest",
                json={"id": document["id"], "content": document["content"]},
            )
            if response.status_code == 409 and args.allow_existing:
                print(f"{document['id']}: already present")
                continue
            if response.status_code >= 400:
                failed += 1
                print(f"{document['id']}: FAILED {response.status_code} {response.text[:200]}")
                continue
            print(f"{document['id']}: {response.json().get('dimensions')} dims")

    print(f"{len(documents) - failed}/{len(documents)} ingested")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
