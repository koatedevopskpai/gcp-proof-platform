"""The URL can be assembled from a Cloud Run secret without exposing the password."""
from app.core import db


def test_database_url_from_parts(monkeypatch):
    monkeypatch.setattr(db.settings, "database_url", "")
    monkeypatch.setattr(db.settings, "db_host", "10.0.0.2")
    monkeypatch.setattr(db.settings, "db_port", 5432)
    monkeypatch.setattr(db.settings, "db_name", "aiplatform")
    monkeypatch.setattr(db.settings, "db_user", "rag")
    monkeypatch.setattr(db.settings, "db_password", "p@ss word")

    assert db.database_url() == (
        "postgresql+psycopg://rag:p%40ss+word@10.0.0.2:5432/aiplatform?sslmode=require"
    )


def test_explicit_database_url_wins(monkeypatch):
    monkeypatch.setattr(db.settings, "database_url", "postgresql+psycopg://x:y@z/db")
    monkeypatch.setattr(db.settings, "db_host", "10.0.0.2")

    assert db.database_url() == "postgresql+psycopg://x:y@z/db"
