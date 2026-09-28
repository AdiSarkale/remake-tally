"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import model_validator

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    app_name: str = "MiniTally ERP API"
    api_v1_prefix: str = "/api/v1"

    # Control-plane DB: users, companies, and tenant routing metadata.
    control_database_url: str | None = None

    database_url: str = "postgresql+psycopg://minitally:minitally@localhost:5432/minitally"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    cors_origins: list[str] = ["http://localhost:8080","http://localhost:8081","http://localhost:5173","http://localhost:8000"]


    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment.lower() == "production" and self.jwt_secret == "change-me-in-production":
            raise ValueError("JWT_SECRET must be explicitly configured in production")
        if self.environment.lower() == "production" and not self.control_database_url:
            raise ValueError("CONTROL_DATABASE_URL must be configured in production")
        return self

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
