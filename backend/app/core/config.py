"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "MiniTally ERP API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://minitally:minitally@localhost:5433/minitally"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    cors_origins: list[str] = ["http://localhost:8080","http://localhost:8081","http://localhost:5173","http://localhost:8000"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
