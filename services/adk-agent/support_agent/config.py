from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Names are deliberately plain so Cloud Run can inject them as environment
    variables. Vertex settings (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`,
    `GOOGLE_GENAI_USE_VERTEXAI`) are read by google-genai directly; they are not
    duplicated here.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    agent_model: str = "gemini-3-flash-preview"
    rag_api_url: str = "http://localhost:8010"
    rag_api_timeout_s: float = 20.0
    rag_top_k: int = 4
    max_passage_chars: int = 1_200

    # Phase 2: asset lookup. `memory` uses the synthetic fixtures; `bigquery`
    # reads the register. No silent fallback between the two.
    assets_source: Literal["memory", "bigquery"] = "memory"
    # Phase 2: escalation. `file` is a local JSONL stand-in; `bigquery` is durable.
    escalation_sink: Literal["file", "bigquery"] = "file"
    escalation_file: str = "artifacts/escalations.jsonl"

    bq_project: str = ""
    assets_dataset: str = "ai_platform"
    escalations_dataset: str = "agent_ops"
    assets_table: str = "assets"
    escalations_table: str = "agent_escalations"

    @field_validator("assets_source", "escalation_sink", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


settings = Settings()
