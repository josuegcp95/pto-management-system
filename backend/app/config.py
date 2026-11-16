"""Application settings loaded from environment variables.

On Render, values come from the service's Environment tab.
Locally, they come from backend/.env (never committed).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    jwt_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    ai_provider: str = "openai"  # "openai" or "mock" (no API calls)
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them."""
    return Settings()