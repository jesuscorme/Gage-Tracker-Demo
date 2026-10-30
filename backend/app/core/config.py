"""Environment-driven configuration.

Values come from environment variables (or a local ``.env`` file). Nothing secret
is hardcoded for production: the app refuses to start in ``production`` with the
development JWT secret.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Gage Tracker API"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "postgresql+psycopg://gagetracker:gagetracker@localhost:5433/gagetracker"

    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=60, ge=5, le=24 * 60)
    # bcrypt work factor. Lowered only by the test suite to keep it fast.
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # Comma-separated list of allowed browser origins.
    cors_origins: str = "http://localhost:3000"

    # Self-service registration creates a new organization. Disable in private deployments
    # where tenants are provisioned by an administrator.
    allow_self_registration: bool = True

    # Uploaded documents. Local filesystem for now (see app/core/storage.py).
    storage_dir: str = "./var/storage"
    max_upload_mb: int = Field(default=20, ge=1, le=200)

    # Background jobs (webhook delivery, workflow escalation, overdue scan). Disabled in tests.
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = Field(default=30, ge=5, le=3600)
    # Plain-HTTP webhook targets are only accepted outside production.
    webhook_allow_http: bool = True
    webhook_timeout_seconds: float = Field(default=10, gt=0, le=60)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong value (>= 32 chars) in production")
            if self.bcrypt_rounds < 12:
                raise ValueError("BCRYPT_ROUNDS must be >= 12 in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
