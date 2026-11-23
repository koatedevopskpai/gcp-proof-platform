from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ai:ai@localhost:5432/aiplatform"
    embedding_mode: Literal["mock", "openai", "vertex"] = "mock"
    embedding_dim: int = Field(default=384, ge=1, le=2_000)
    embedding_model: str = "text-embedding-3-small"
    vertex_embedding_model: str = "text-embedding-005"
    vertex_project: str = ""
    vertex_location: str = "us-central1"
    openai_base_url: str = ""
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    rag_top_k: int = 4
    rag_min_score: float = 0.10

    @field_validator("embedding_mode", mode="before")
    @classmethod
    def _normalise_mode(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


settings = Settings()
