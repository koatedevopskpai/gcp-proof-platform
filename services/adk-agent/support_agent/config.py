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


settings = Settings()
