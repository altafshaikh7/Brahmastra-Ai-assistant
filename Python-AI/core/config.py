"""Centralized configuration for the Brahmastra AI application."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "storage"
DEFAULT_LOGS_PATH = DEFAULT_STORAGE_PATH / "logs"
DEFAULT_UPLOADS_PATH = DEFAULT_STORAGE_PATH / "uploads"
DEFAULT_CACHE_PATH = DEFAULT_STORAGE_PATH / "cache"
DEFAULT_TEMP_PATH = DEFAULT_STORAGE_PATH / "temp"


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ApplicationSettings(BaseModel):
    """Application-wide runtime configuration."""

    title: str = Field(default="Brahmastra AI")
    version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    request_id_header: str = Field(default="X-Request-ID")


class LoggingSettings(BaseModel):
    """Structured logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    console: bool = Field(default=True)
    file: bool = Field(default=True)
    file_path: Path = Field(default=DEFAULT_LOGS_PATH / "brahmstra.log")
    rotation: str = Field(default="10 MB")
    retention: str = Field(default="10 days")
    format: str = Field(
        default="%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
    )

    @field_validator("file_path", mode="before")
    @classmethod
    def _resolve_file_path(cls, value: Any) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class MongoDBSettings(BaseModel):
    """MongoDB connection configuration."""

    uri: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="brahmstra")
    connect_timeout_ms: int = Field(default=20000, ge=1000)
    server_selection_timeout_ms: int = Field(default=30000, ge=1000)
    max_pool_size: int = Field(default=100, ge=1)
    min_pool_size: int = Field(default=0, ge=0)
    retry_writes: bool = Field(default=True)
    retry_attempts: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)
    ping_timeout_seconds: float = Field(default=5.0, ge=0.1)
    tls: bool = Field(default=False)

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        if not value.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MongoDB URI must use mongodb:// or mongodb+srv://")
        return value


class SecuritySettings(BaseModel):
    """Security and authentication configuration."""

    secret_key: SecretStr = Field(default=SecretStr("change-me"))
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = Field(default="HS256")
    api_key_header: str = Field(default="X-API-Key")
    password_salt_rounds: int = Field(default=12, ge=4, le=31)
    token_blacklist_enabled: bool = Field(default=True)
    rbac_enabled: bool = Field(default=True)


class JWTSettings(BaseModel):
    """JWT handling configuration."""

    secret_key: SecretStr = Field(default=SecretStr("change-me"))
    algorithm: Literal["HS256", "HS384", "HS512"] = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    token_prefix: str = Field(default="Bearer")


class RateLimitSettings(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=60, ge=1)
    burst_limit: int = Field(default=10, ge=1)
    window_seconds: int = Field(default=60, ge=1)


class AISettings(BaseModel):
    """AI service configuration."""

    model_name: str = Field(default="gpt-4")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=1024, ge=1)


class StorageSettings(BaseModel):
    """Filesystem storage configuration."""

    base_path: Path = Field(default=DEFAULT_STORAGE_PATH)
    logs_path: Path = Field(default=DEFAULT_LOGS_PATH)
    uploads_path: Path = Field(default=DEFAULT_UPLOADS_PATH)
    cache_path: Path = Field(default=DEFAULT_CACHE_PATH)
    temp_path: Path = Field(default=DEFAULT_TEMP_PATH)

    @field_validator(
        "base_path",
        "logs_path",
        "uploads_path",
        "cache_path",
        "temp_path",
        mode="before",
    )
    @classmethod
    def _resolve_path(cls, value: Any) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path


class CORSSettings(BaseModel):
    """Cross-origin resource sharing configuration."""

    allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = Field(default=True)
    expose_headers: list[str] = Field(default_factory=list)
    max_age: int = Field(default=600, ge=1)

    @field_validator("allow_origins", mode="before")
    @classmethod
    def _validate_origins(cls, value: Any) -> list[str]:
        if value is None:
            return ["*"]
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        raise TypeError("allow_origins must be a string or iterable of strings")


class EmailSettings(BaseModel):
    """Email delivery configuration."""

    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))
    from_address: str = Field(default="noreply@example.com")
    use_tls: bool = Field(default=True)


class ExternalAPISettings(BaseModel):
    """External service integration configuration."""

    github_token: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    base_url: HttpUrl = Field(default="https://api.example.com")


class Settings(BaseSettings):
    """Root settings object for the application."""

    model_config = SettingsConfigDict(
        env_prefix="BRAHMSTRA_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        strict=False,
        extra="ignore",
    )

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mongodb: MongoDBSettings = Field(default_factory=MongoDBSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    ai: AISettings = Field(default_factory=AISettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    external_api: ExternalAPISettings = Field(default_factory=ExternalAPISettings)

    @property
    def is_production(self) -> bool:
        """Return whether the current environment is production."""
        return self.application.environment == Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()


__all__ = [
    "ApplicationSettings",
    "AISettings",
    "CORSSettings",
    "EmailSettings",
    "Environment",
    "ExternalAPISettings",
    "JWTSettings",
    "LoggingSettings",
    "MongoDBSettings",
    "RateLimitSettings",
    "SecuritySettings",
    "Settings",
    "StorageSettings",
    "get_settings",
]
