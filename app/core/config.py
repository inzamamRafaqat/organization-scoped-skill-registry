"""Application settings and configuration."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    PROJECT_NAME: str = "Organization-Scoped Skill Registry"
    API_V1_STR: str = "/api/v1"

    # Database: Default to sqlite for local zero-dependency testing;
    # overridden by DATABASE_URL in environment / docker-compose for PostgreSQL.
    DATABASE_URL: str = "sqlite+aiosqlite:///./skill_registry.db"

    # Security
    SECRET_KEY: str = "test-insecure-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Audit logging toggle
    AUDIT_LOG_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
