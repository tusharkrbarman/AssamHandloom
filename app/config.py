from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str = Field(min_length=32)
    environment: str = "development"
    public_base_url: AnyHttpUrl
    catalogue_preview_enabled: bool = False

    @model_validator(mode="after")
    def validate_database_url(self) -> Settings:
        if self.environment != "test" and not self.database_url.startswith("postgresql"):
            raise ValueError("DATABASE_URL must use PostgreSQL outside the test environment")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""

    return Settings()
