"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    app_name: str = "MiniTally ERP API"
    api_v1_prefix: str = "/api/v1"

    # Control-plane DB: company routing metadata only. Tenant DB credentials
    # are resolved from database_secret_ref at runtime.
    control_database_url: str | None = None

    # Legacy/default local tenant DB used for migrations and development.
    database_url: str = "postgresql+psycopg://minitally:minitally@localhost:5432/minitally"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    tenant_engine_cache_size: int = 32
    tenant_pool_size: int = 2
    tenant_pool_max_overflow: int = 1
    tenant_pool_timeout_seconds: int = 30
    tenant_pool_recycle_seconds: int = 1800

    cors_origins: list[str] = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.jwt_secret == "change-me-in-production" or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be a strong secret of at least 32 characters in production")
            if not self.control_database_url:
                raise ValueError("CONTROL_DATABASE_URL must be configured in production")
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must contain the production frontend origin")
            if any(origin.startswith("http://localhost") for origin in self.cors_origins):
                raise ValueError("Production CORS_ORIGINS must not contain localhost")
            if "*" in self.cors_origins:
                raise ValueError("Production CORS_ORIGINS must be explicit; wildcard is forbidden")
        return self

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
