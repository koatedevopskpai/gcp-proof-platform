"""The lookup contract: validation, not-found, and fail-closed errors."""
from support_agent.adapters.assets import InMemoryAssetRepository
from support_agent.data.assets import SAMPLE_ASSETS
from support_agent.tools.records import build_lookup_record


def lookup():
    return build_lookup_record(InMemoryAssetRepository(SAMPLE_ASSETS))


def test_known_asset_is_returned():
    out = lookup()("TR-1042")

    assert out["status"] == "ok"
    assert out["asset"]["asset_id"] == "TR-1042"
    assert out["asset"]["site"] == "Ashford Grid"


def test_id_is_normalised():
    out = lookup()("  tr-1042 ")

    assert out["asset"]["asset_id"] == "TR-1042"


def test_unknown_id_is_not_found_without_guessing():
    out = lookup()("ZZ-0000")

    assert out["status"] == "not_found"
    assert "asset" not in out
    assert "escalate" in out["message"]


def test_invalid_id_does_not_reach_the_repository():
    class Exploding:
        def get(self, asset_id):
            raise AssertionError("the repository should not be called")

    out = build_lookup_record(Exploding())("not-an-asset-id")

    assert out["status"] == "invalid_asset_id"
    assert "TR-1042" in out["message"]


def test_repository_failure_is_reported_not_raised():
    class Broken:
        def get(self, asset_id):
            raise RuntimeError("bigquery unavailable")

    out = build_lookup_record(Broken())("TR-1042")

    assert out["status"] == "error"
    assert out["error"] == "lookup_unavailable"
    assert "bigquery unavailable" not in out["message"]
    assert "escalate" in out["message"]
