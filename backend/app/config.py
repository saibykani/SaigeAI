"""Application settings loaded from environment variables (never hard-coded)."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # env_ignore_empty: a blank variable (common when pasting .env files into a hosting
    # dashboard) falls back to the default instead of failing validation.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore",
                                      env_ignore_empty=True)

    environment: str = "development"

    mongodb_uri: str = Field(..., description="MongoDB Atlas connection string")
    mongodb_db: str = "saige_ai"

    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30  # sliding: every refresh issues a fresh 30-day cookie
    cookie_secure: bool = False

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:3000/api/auth/google/callback"

    openai_api_key: str | None = None
    # Optional Claude enrichment for job-description parsing. Everything works without it.
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"

    frontend_url: str = "http://localhost:3000"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    max_upload_mb: int = 5

    # Shared secret for /api/cron/daily (Vercel Cron sends it as a Bearer token).
    cron_secret: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def llm_enabled(self) -> bool:
        # Only a real Anthropic key enables Claude; placeholders or stray env values don't.
        return bool(self.anthropic_api_key and self.anthropic_api_key.startswith("sk-ant-"))

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
