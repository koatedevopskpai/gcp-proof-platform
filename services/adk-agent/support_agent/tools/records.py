"""Asset lookup tool.

The tool validates the id, asks the repository for one record, and returns a
small JSON object. It never accepts SQL and never exposes a database error.
"""
from __future__ import annotations

import logging
import os
from typing import Callable

from support_agent.adapters.assets import (
    ASSET_ID_PATTERN,
    AssetRepository,
    BigQueryAssetRepository,
    InMemoryAssetRepository,
    normalise_asset_id,
)
from support_agent.config import settings
from support_agent.data.assets import SAMPLE_ASSETS

logger = logging.getLogger(__name__)


def build_lookup_record(repository: AssetRepository) -> Callable[[str], dict]:
    def lookup_record(asset_id: str) -> dict:
        """Look up one asset record by its asset id.

        Call this when the user names a specific asset, for example "TR-1042" or
        "asset TC-2210". Use the returned fields for asset-specific facts such as
        site, criticality, status and inspection dates. The record does not say
        what procedure to follow: use search_knowledge for that.

        Args:
            asset_id: The asset identifier, formatted as two to four letters, a
                hyphen, then three to six digits (for example TR-1042).

        Returns:
            A dict with `status` set to "ok", "not_found", "invalid_asset_id" or
            "error". On success the `asset` field holds the record. On
            `not_found`, say so and offer to escalate; do not invent a record.
            On `error`, retrieval is unavailable, so do not answer from memory.
        """
        asset_id = normalise_asset_id(asset_id)
        if not ASSET_ID_PATTERN.match(asset_id):
            return {
                "status": "invalid_asset_id",
                "message": (
                    "Asset ids look like TR-1042: two to four letters, a hyphen, "
                    "then three to six digits."
                ),
            }

        try:
            asset = repository.get(asset_id)
        except Exception:
            logger.exception("asset lookup failed for %s", asset_id)
            return {
                "status": "error",
                "error": "lookup_unavailable",
                "message": (
                    "The asset register is unreachable. Tell the user the lookup is "
                    "unavailable, do not answer asset questions from memory, and "
                    "offer to escalate."
                ),
            }

        if asset is None:
            return {
                "status": "not_found",
                "asset_id": asset_id,
                "message": (
                    "No asset with that id exists in the register. Do not guess or "
                    "substitute a similar id, and do not call search_knowledge for "
                    "this asset; offer to escalate."
                ),
            }

        return {"status": "ok", "asset": asset}

    return lookup_record


def build_default_repository() -> AssetRepository:
    if settings.assets_source == "bigquery":
        return BigQueryAssetRepository(
            project=settings.bq_project or os.getenv("GOOGLE_CLOUD_PROJECT", ""),
            dataset=settings.assets_dataset,
            table=settings.assets_table,
        )
    return InMemoryAssetRepository(SAMPLE_ASSETS)


lookup_record = build_lookup_record(build_default_repository())
