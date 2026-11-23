from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


def database_url() -> str:
    """Compose the URL from parts so a Cloud Run secret can supply only the password."""
    if settings.database_url:
        return settings.database_url
    if settings.db_host:
        return (
            "postgresql+psycopg://"
            f"{quote_plus(settings.db_user)}:{quote_plus(settings.db_password)}"
            f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
            "?sslmode=require"
        )
    return "postgresql+psycopg://ai:ai@localhost:5432/aiplatform"


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
