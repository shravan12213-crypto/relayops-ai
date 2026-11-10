"""Application settings, loaded from environment and `.env` files.

Every knob the app needs is declared here once, so the rest of the codebase can
depend on a typed `Settings` object instead of reading `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "openai", "replay"]
Environment = Literal["dev", "prod"]

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

DEFAULT_SECRET_KEY = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    """Runtime configuration. Env vars win over `.env`, `.env` wins over defaults."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RelayOps"
    env: Environment = "dev"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/relayops.db"
    secret_key: str = DEFAULT_SECRET_KEY

    llm_provider: LLMProvider = "replay"
    llm_model: str = "claude-sonnet-4-5"
    llm_timeout_seconds: float = 60.0
    llm_token_budget_per_job: int = 100000
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    github_token: str | None = None

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_upload_mb: int = 20
    seed_on_start: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            val = value.strip()
            if val.startswith("postgres://"):
                return "postgresql+psycopg2://" + val[len("postgres://") :]
            if val.startswith("postgresql://"):
                return "postgresql+psycopg2://" + val[len("postgresql://") :]
            return val
        return value

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _normalise_provider(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("env", mode="before")
    @classmethod
    def _normalise_env(cls, value: object) -> object:
        if isinstance(value, str):
            val = value.strip().lower()
            if val in ("prod", "production"):
                return "prod"
            if val in ("dev", "development"):
                return "dev"
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql") or self.database_url.startswith("postgres")

    @property
    def llm_mode(self) -> LLMProvider:
        """The mode the app will actually run in, given the configured keys."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            return "replay"
        if self.llm_provider == "openai" and not self.openai_api_key:
            return "replay"
        return self.llm_provider

    def check_prod_safety(self) -> None:
        """Fail fast on the settings that are fine locally and dangerous in production."""
        if self.env != "prod":
            return
        if self.secret_key == DEFAULT_SECRET_KEY or len(self.secret_key) < 32:
            raise RuntimeError(
                "FATAL: Unsafe production configuration detected!\n"
                "When ENV=prod or ENV=production, SECRET_KEY cannot use the default value "
                "and must be at least 32 characters long.\n"
                'Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
