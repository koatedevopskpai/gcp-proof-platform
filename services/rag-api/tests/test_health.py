"""`/health` must report the mode the service is actually using."""
from types import SimpleNamespace

from app.api import routes


class FakeDb:
    def execute(self, _statement):
        return None


def test_health_reports_the_effective_embedding_mode(monkeypatch):
    fake_service = SimpleNamespace(
        mode="vertex", embedding_model="text-embedding-005", dim=384
    )
    monkeypatch.setattr(routes, "embedding_service", fake_service)

    body = routes.health(db=FakeDb())

    assert body == {
        "status": "ok",
        "embedding_mode": "vertex",
        "embedding_model": "text-embedding-005",
        "embedding_dim": 384,
    }
