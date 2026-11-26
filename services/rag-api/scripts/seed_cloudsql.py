"""Create the Cloud SQL schema and load the seed corpus.

Runs as a Cloud Run job with the rag-api image and the admin database credential.
The application user (`rag` by default) is granted only the table privileges it
needs; the service itself starts with DB_AUTO_INIT=false.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Document  # noqa: E402
from app.services.embedding import embedding_service  # noqa: E402

APP_USER = re.compile(r"^[a-z_][a-z0-9_]*$")
DATASET = Path(__file__).resolve().parents[1] / "datasets" / "rail_utilities_seed.jsonl"


def main() -> int:
    app_user = os.getenv("APP_DB_USER", "rag")
    if not APP_USER.match(app_user):
        raise SystemExit(f"invalid APP_DB_USER: {app_user!r}")

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)

    records = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    with SessionLocal() as db:
        existing = {row[0] for row in db.execute(text("SELECT id FROM documents"))}
        added = 0
        for record in records:
            if record["id"] in existing:
                continue
            db.add(
                Document(
                    id=record["id"],
                    content=record["content"],
                    embedding=embedding_service.embed(record["content"]),
                )
            )
            added += 1
        db.commit()

    with engine.connect() as conn:
        conn.execute(text(f"GRANT CONNECT ON DATABASE {engine.url.database} TO {app_user}"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {app_user}"))
        conn.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO {app_user}")
        )
        conn.commit()

    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar_one()

    print(f"seeded {added} new documents ({total} total); granted document access to {app_user}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
