"""Load the synthetic asset fixtures into the BigQuery assets table.

    python scripts/seed_assets.py --project gcp-proof-platform

This is demonstration data. It is idempotent in the sense that rerunning inserts
the same rows again; the table has no uniqueness constraint, so clear it first if
you need a clean seed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from support_agent.data.assets import SAMPLE_ASSETS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("BQ_PROJECT")
    )
    parser.add_argument("--dataset", default="ai_platform")
    parser.add_argument("--table", default="assets")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps(SAMPLE_ASSETS, indent=2))
        return 0

    if not args.project:
        raise SystemExit("set --project or GOOGLE_CLOUD_PROJECT")

    from google.cloud import bigquery

    table_ref = f"{args.project}.{args.dataset}.{args.table}"
    errors = bigquery.Client(project=args.project).insert_rows_json(
        table_ref, SAMPLE_ASSETS
    )
    if errors:
        raise SystemExit(f"BigQuery insert failed: {errors}")
    print(f"loaded {len(SAMPLE_ASSETS)} assets into {table_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
