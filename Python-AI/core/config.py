# core/config.py
"""Centralized configuration for the Brahmastra AI application.

This module provides type-safe, validated configuration using Pydantic v2.
Settings are loaded from environment variables and .env files, with support
for nested configuration sections. Secrets are loaded from environment
variables only – no insecure defaults.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DEFAULT_STORAGE_PATH: Final[Path] = PROJECT_ROOT / "storage"
DEFAULT_LOGS_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "logs"
DEFAULT_UPLOADS_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "uploads"
DEFAULT_CACHE_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "cache"
DEFAULT_TEMP_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "temp"
DEFAULT_BACKUPS_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "backups"
DEFAULT_EXPORTS_PATH: Final[Path] = DEFAULT_STORAGE_PATH / "exports"

# Type aliases
EnvStr: TypeAlias = str
LogLevel: TypeAlias = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
ProviderType: TypeAlias = Literal[
    "openai", "azure_openai", "anthropic", "gemini", "ollama", "openrouter"
]
AlgorithmType: TypeAlias = Literal[
    "HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512"
]
MongoReadPreference: TypeAlias = Literal[
    "PRIMARY", "SECONDARY", "NEAREST", "PRIMARY_PREFERRED", "SECONDARY_PREFERRED"
]
MongoWriteConcern: TypeAlias = Literal[
    "majority", "acknowledged", "unacknowledged", "journaled"
]


# =============================================================================
# Environment
# =============================================================================


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


# =============================================================================
# Shared Validation Helpers
# =============================================================================


def _validate_secret_strength(value: SecretStr, min_length: int = 32) -> SecretStr:
    """Validate that a SecretStr meets minimum length requirements."""
    if value.get_secret_value() and len(value.get_secret_value()) < min_length:
        raise ValueError(f"secret must be at least {min_length} characters long")
    return value


def _validate_optional_secret(
    value: SecretStr | None, min_length: int = 32
) -> SecretStr | None:
    """Validate an optional SecretStr if present."""
    if (
        value is not None
        and value.get_secret_value()
        and len(value.get_secret_value()) < min_length
    ):
        raise ValueError(
            f"optional secret must be at least {min_length} characters long"
        )
    return value


def _resolve_path(value: Any) -> Path:
    """Normalize a path relative to PROJECT_ROOT and resolve symlinks safely."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve(strict=False)


def _normalize_url(value: Any) -> Any:
    """Strip whitespace from string URLs; return as-is for other types."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _normalize_csv_list(value: Any) -> list[str]:
    """Convert comma-separated string or iterable to a list of strings."""
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return ["*"]


# =============================================================================
# Retry Settings (reusable)
# =============================================================================


class RetrySettings(BaseModel):
    """Common retry configuration."""

    model_config = ConfigDict(frozen=True)

    retry_attempts: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)


# =============================================================================
# Application Settings
# =============================================================================


class ApplicationSettings(BaseModel):
    """Application-wide runtime configuration."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(default="Brahmastra AI")
    version: str = Field(default="0.1.0")
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)
    workers: int = Field(default=1, ge=1)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = Field(default="/api/v1")
    root_path: str = Field(default="")
    trusted_hosts: list[str] = Field(default_factory=lambda: ["*"])
    excluded_logging_prefixes: list[str] = Field(
        default_factory=lambda: [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
    )
    request_id_header: str = Field(default="X-Request-ID")
    docs_enabled: bool = Field(default=True)
    swagger_enabled: bool = Field(default=True)
    redoc_enabled: bool = Field(default=True)
    openapi_enabled: bool = Field(default=True)

    @model_validator(mode="after")
    def _enforce_production_constraints(self) -> ApplicationSettings:
        if self.environment == Environment.PRODUCTION:
            if self.debug:
                raise ValueError("debug must be False in production environment")
            if self.reload:
                raise ValueError("reload must be False in production environment")
            if (
                self.docs_enabled
                or self.swagger_enabled
                or self.redoc_enabled
                or self.openapi_enabled
            ):
                raise ValueError(
                    "docs, swagger, redoc, and openapi must be disabled in production"
                )
            if not self.trusted_hosts or self.trusted_hosts == ["*"]:
                raise ValueError(
                    "trusted_hosts must be explicitly set in production (not ['*'])"
                )
        return self

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def _normalize_trusted_hosts(cls, value: Any) -> list[str]:
        return _normalize_csv_list(value)


# =============================================================================
# Logging Settings
# =============================================================================


class LoggingSettings(BaseModel):
    """Structured logging configuration."""

    model_config = ConfigDict(frozen=True)

    level: LogLevel = Field(default="INFO")
    console: bool = Field(default=True)
    file: bool = Field(default=True)
    file_path: Path = Field(default=DEFAULT_LOGS_PATH / "brahmastra.log")
    rotation: str = Field(default="10 MB")
    retention: str = Field(default="10 days")
    format: str = Field(
        default="%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
    )
    json_logging: bool = Field(default=False)
    structured_logging: bool = Field(default=True)
    utc_timestamps: bool = Field(default=True)
    backup_count: int = Field(default=5, ge=0)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    access_log_enabled: bool = Field(default=True)
    error_log_enabled: bool = Field(default=True)
    audit_log_enabled: bool = Field(default=False)
    rotation_strategy: Literal["size", "time", "size_time"] = Field(default="size")
    compress: bool = Field(default=False)
    enqueue: bool = Field(default=False)
    serialize: bool = Field(default=False)

    @field_validator("file_path", mode="before")
    @classmethod
    def _resolve_path(cls, value: Any) -> Path:
        return _resolve_path(value)


# =============================================================================
# MongoDB Settings (with RetrySettings composition)
# =============================================================================


class MongoDBSettings(BaseModel):
    """MongoDB connection configuration."""

    model_config = ConfigDict(frozen=True)

    uri: str = Field(default="mongodb://localhost:27017")
    database_name: str = Field(default="brahmastra")
    connect_timeout_ms: int = Field(default=20000, ge=1000)
    server_selection_timeout_ms: int = Field(default=30000, ge=1000)
    max_pool_size: int = Field(default=100, ge=1)
    min_pool_size: int = Field(default=0, ge=0)
    retry_writes: bool = Field(default=True)
    retry_attempts: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)
    ping_timeout_seconds: float = Field(default=5.0, ge=0.1)
    tls: bool = Field(default=False)
    read_preference: MongoReadPreference = Field(default="PRIMARY")
    write_concern: MongoWriteConcern = Field(default="majority")

    @field_validator("uri")
    @classmethod
    def _validate_uri(cls, value: str) -> str:
        if not value.startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError("MongoDB URI must use mongodb:// or mongodb+srv://")
        return value

    @model_validator(mode="after")
    def _validate_pool_size(self) -> MongoDBSettings:
        if self.min_pool_size > self.max_pool_size:
            raise ValueError("min_pool_size must be <= max_pool_size")
        return self

    @computed_field
    @property
    def retry(self) -> RetrySettings:
        return RetrySettings(
            retry_attempts=self.retry_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )


# =============================================================================
# Redis Settings (with RetrySettings composition)
# =============================================================================


class RedisSettings(BaseModel):
    """Redis connection configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    password: SecretStr | None = Field(default=None)
    database: int = Field(default=0, ge=0)
    ssl: bool = Field(default=False)
    connect_timeout_seconds: float = Field(default=5.0, ge=0.1)
    read_timeout_seconds: float = Field(default=5.0, ge=0.1)
    retry_attempts: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)

    @computed_field
    @property
    def retry(self) -> RetrySettings:
        return RetrySettings(
            retry_attempts=self.retry_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )


# =============================================================================
# Security Settings
# =============================================================================


class SecuritySettings(BaseModel):
    """Security and authentication configuration."""

    model_config = ConfigDict(frozen=True)

    secret_key: SecretStr = Field(default=SecretStr(""))
    jwt_algorithm: AlgorithmType = Field(default="HS256")
    api_key_header: str = Field(default="X-API-Key")
    password_salt_rounds: int = Field(default=12, ge=4, le=31)
    token_blacklist_enabled: bool = Field(default=True)
    rbac_enabled: bool = Field(default=True)
    csrf_secret: SecretStr | None = Field(default=None)
    api_secret: SecretStr | None = Field(default=None)

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, value: SecretStr) -> SecretStr:
        return _validate_secret_strength(value, min_length=32)

    @field_validator("api_secret", "csrf_secret")
    @classmethod
    def _validate_optional_secret(cls, value: SecretStr | None) -> SecretStr | None:
        return _validate_optional_secret(value, min_length=32)


# =============================================================================
# JWT Settings
# =============================================================================


class JWTSettings(BaseModel):
    """JWT handling configuration."""

    model_config = ConfigDict(frozen=True)

    secret_key: SecretStr = Field(default=SecretStr(""))
    algorithm: AlgorithmType = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    token_prefix: str = Field(default="Bearer")
    issuer: str | None = Field(default=None)
    audience: str | None = Field(default=None)
    clock_skew_seconds: int = Field(default=30, ge=0)

    @field_validator("secret_key")
    @classmethod
    def _validate_secret(cls, value: SecretStr) -> SecretStr:
        return _validate_secret_strength(value, min_length=32)


# =============================================================================
# Rate Limit Settings
# =============================================================================


class RateLimitSettings(BaseModel):
    """Rate limiting configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=60, ge=1)
    burst_limit: int = Field(default=10, ge=1)
    window_seconds: int = Field(default=60, ge=1)

    @model_validator(mode="after")
    def _validate_burst(self) -> RateLimitSettings:
        if self.burst_limit > self.requests_per_minute:
            raise ValueError("burst_limit cannot exceed requests_per_minute")
        return self


# =============================================================================
# AI Settings (with RetrySettings composition and provider-specific validation)
# =============================================================================


class AISettings(BaseModel):
    """AI service configuration."""

    model_config = ConfigDict(frozen=True)

    # Original fields (backward compatible)
    model_name: str = Field(default="gpt-4")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=1024, ge=1)

    # New fields
    provider: ProviderType = Field(default="gemini")
    api_key: SecretStr | None = Field(default=None)
    base_url: HttpUrl | None = Field(default=None)
    timeout_seconds: int = Field(default=60, ge=1)
    retry_attempts: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)

    # Provider-specific configurations
    azure_endpoint: HttpUrl | None = Field(default=None)
    azure_deployment: str | None = Field(default=None)
    azure_api_version: str | None = Field(default=None)
    anthropic_version: str | None = Field(default="2023-06-01")
    gemini_model: str = Field(default="gemini-2.5-flash")
    openrouter_model: str | None = Field(default=None)

    @field_validator("base_url", mode="before")
    @classmethod
    def _normalize_base_url(cls, value: Any) -> Any:
        return _normalize_url(value)

    @model_validator(mode="after")
    def _validate_provider_config(self) -> AISettings:
        """Enforce provider-specific required fields."""
        if self.provider == "openai":
            if self.api_key is None or not self.api_key.get_secret_value():
                raise ValueError("api_key is required for OpenAI provider")
        elif self.provider == "azure_openai":
            if not self.azure_endpoint or not self.azure_deployment:
                raise ValueError(
                    "azure_endpoint and azure_deployment are required for Azure OpenAI"
                )
            if self.api_key is None or not self.api_key.get_secret_value():
                raise ValueError("api_key is required for Azure OpenAI")
            if not self.azure_api_version:
                raise ValueError("azure_api_version is required for Azure OpenAI")
        elif self.provider == "anthropic":
            if self.api_key is None or not self.api_key.get_secret_value():
                raise ValueError("api_key is required for Anthropic provider")
        elif self.provider == "gemini":
            if self.api_key is None or not self.api_key.get_secret_value():
                raise ValueError("api_key is required for Gemini provider")
            if not self.gemini_model:
                raise ValueError("gemini_model is required for Gemini provider")
        elif self.provider == "openrouter":
            if self.api_key is None or not self.api_key.get_secret_value():
                raise ValueError("api_key is required for OpenRouter provider")
            if not self.openrouter_model:
                raise ValueError("openrouter_model is required for OpenRouter provider")
        # Ollama does not require an API key; base_url may be optional.
        return self

    @computed_field
    @property
    def retry(self) -> RetrySettings:
        return RetrySettings(
            retry_attempts=self.retry_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )


# =============================================================================
# Storage Settings
# =============================================================================


class StorageSettings(BaseModel):
    """Filesystem storage configuration."""

    model_config = ConfigDict(frozen=True)

    # Original fields
    base_path: Path = Field(default=DEFAULT_STORAGE_PATH)
    logs_path: Path = Field(default=DEFAULT_LOGS_PATH)
    uploads_path: Path = Field(default=DEFAULT_UPLOADS_PATH)
    cache_path: Path = Field(default=DEFAULT_CACHE_PATH)
    temp_path: Path = Field(default=DEFAULT_TEMP_PATH)

    # New fields
    backups_path: Path = Field(default=DEFAULT_BACKUPS_PATH)
    exports_path: Path = Field(default=DEFAULT_EXPORTS_PATH)

    @field_validator("*", mode="before")
    @classmethod
    def _resolve_path(cls, value: Any) -> Path:
        return _resolve_path(value)


# =============================================================================
# Email Settings
# =============================================================================


class EmailSettings(BaseModel):
    """Email delivery configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=False)
    host: str = Field(default="localhost")
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="")
    password: SecretStr = Field(default=SecretStr(""))
    from_address: EmailStr = Field(
        default="noreply@example.com",
        validate_default=False,  # Skip DNS deliverability check for default placeholder
    )
    use_tls: bool = Field(default=True)
    use_ssl: bool = Field(default=False)
    timeout_seconds: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def _validate_tls_ssl(self) -> EmailSettings:
        if self.use_tls and self.use_ssl:
            raise ValueError("cannot use both TLS and SSL simultaneously")
        return self


# =============================================================================
# External API Settings (with RetrySettings composition)
# =============================================================================


class ExternalAPISettings(BaseModel):
    """External service integration configuration."""

    model_config = ConfigDict(frozen=True)

    github_token: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    base_url: HttpUrl = Field(default="https://api.example.com")
    timeout_seconds: int = Field(default=30, ge=1)
    retry_attempts: int = Field(default=3, ge=0)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0)

    @computed_field
    @property
    def retry(self) -> RetrySettings:
        return RetrySettings(
            retry_attempts=self.retry_attempts,
            retry_backoff_seconds=self.retry_backoff_seconds,
        )


# =============================================================================
# CORS Settings (Enterprise-grade with strict validation)
# =============================================================================


class CORSSettings(BaseModel):
    """Cross-origin resource sharing configuration.

    Strictly enforces that if allow_credentials is True, allow_origins
    cannot contain '*' because browsers reject credentials with wildcard origins.
    """

    model_config = ConfigDict(frozen=True)

    allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = Field(default=False)  # Safer default
    expose_headers: list[str] = Field(default_factory=list)
    max_age: int = Field(default=600, ge=1)

    @model_validator(mode="after")
    def _validate_credentials_wildcard(self) -> CORSSettings:
        if self.allow_credentials and any(
            origin == "*" for origin in self.allow_origins
        ):
            raise ValueError(
                "allow_credentials cannot be True when allow_origins includes '*'"
            )
        return self

    @field_validator("allow_origins", mode="before")
    @classmethod
    def _normalize_origins(cls, value: Any) -> list[str]:
        return _normalize_csv_list(value)


# =============================================================================
# Observability Settings
# =============================================================================


class ObservabilitySettings(BaseModel):
    """Observability and telemetry configuration."""

    model_config = ConfigDict(frozen=True)

    service_name: str = Field(default="brahmastra")
    service_version: str = Field(default="0.1.0")
    environment: Environment = Field(default=Environment.DEVELOPMENT)

    opentelemetry_enabled: bool = Field(default=False)
    otlp_endpoint: HttpUrl | None = Field(default=None)
    otlp_headers: dict[str, str] = Field(default_factory=dict)
    resource_attributes: dict[str, str] = Field(default_factory=dict)
    trace_sampling_ratio: float = Field(default=0.1, ge=0.0, le=1.0)

    jaeger_enabled: bool = Field(default=False)
    jaeger_agent_host: str = Field(default="localhost")
    jaeger_agent_port: int = Field(default=6831)

    prometheus_enabled: bool = Field(default=True)
    prometheus_endpoint: str = Field(default="/metrics")

    grafana_enabled: bool = Field(default=False)
    loki_enabled: bool = Field(default=False)
    loki_endpoint: HttpUrl | None = Field(default=None)

    datadog_enabled: bool = Field(default=False)
    datadog_api_key: SecretStr | None = Field(default=None)

    sentry_enabled: bool = Field(default=False)
    sentry_dsn: HttpUrl | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_otlp(self) -> ObservabilitySettings:
        if self.opentelemetry_enabled and not self.otlp_endpoint:
            raise ValueError("otlp_endpoint is required when opentelemetry is enabled")
        return self


# =============================================================================
# Metrics Settings
# =============================================================================


class MetricsSettings(BaseModel):
    """Metrics collection configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=True)
    endpoint: str = Field(default="/metrics")
    include_route: bool = Field(default=True)
    include_database: bool = Field(default=True)
    include_cache: bool = Field(default=True)
    include_ai: bool = Field(default=True)


# =============================================================================
# Feature Flags
# =============================================================================


class FeatureFlagSettings(BaseModel):
    """Feature flag configuration."""

    model_config = ConfigDict(frozen=True)

    enable_ai: bool = Field(default=True)
    enable_async_processing: bool = Field(default=True)
    enable_batch_operations: bool = Field(default=False)
    enable_websocket: bool = Field(default=False)
    enable_webhook: bool = Field(default=False)
    enable_audit_logging: bool = Field(default=False)


# =============================================================================
# Health Check Settings
# =============================================================================


class HealthCheckSettings(BaseModel):
    """Health check configuration."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(default=True)
    endpoint: str = Field(default="/health")
    include_details: bool = Field(default=False)
    check_database: bool = Field(default=True)
    check_cache: bool = Field(default=False)
    check_storage: bool = Field(default=False)
    timeout_seconds: int = Field(default=5, ge=1)


# =============================================================================
# Root Settings
# =============================================================================


class Settings(BaseSettings):
    """Root settings object for the application."""

    model_config = SettingsConfigDict(
        env_prefix="BRAHMASTRA_",
        case_sensitive=False,
        env_file=PROJECT_ROOT / ".env",  # Absolute path anchored to project root
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        strict=False,
        extra="ignore",
        frozen=True,  # Entire configuration tree is immutable after load
    )

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mongodb: MongoDBSettings = Field(default_factory=MongoDBSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    ai: AISettings = Field(default_factory=AISettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    external_api: ExternalAPISettings = Field(default_factory=ExternalAPISettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)
    feature_flags: FeatureFlagSettings = Field(default_factory=FeatureFlagSettings)
    health: HealthCheckSettings = Field(default_factory=HealthCheckSettings)
    # Tool configuration
    tool_max_iterations: int = Field(
        default=5, ge=1, description="Maximum tool call iterations per request."
    )
    tool_root_path: Path = Field(
        default=PROJECT_ROOT, description="Root directory for tool file operations."
    )

    @computed_field
    @property
    def is_production(self) -> bool:
        """Return whether the current environment is production."""
        return self.application.environment == Environment.PRODUCTION

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> Settings:
        """Ensure required secrets are present when environment is production."""
        if self.is_production:
            # Security.secret_key is required
            if not self.security.secret_key.get_secret_value():
                raise ValueError(
                    "security.secret_key must be set in production environment"
                )
            # JWT.secret_key is required
            if not self.jwt.secret_key.get_secret_value():
                raise ValueError("jwt.secret_key must be set in production environment")
            # AI: enforce provider-specific requirements again in production
            if self.ai.provider == "openai" and (
                self.ai.api_key is None or not self.ai.api_key.get_secret_value()
            ):
                raise ValueError(
                    "ai.api_key is required when using OpenAI provider in production"
                )
            if self.ai.provider == "azure_openai" and (
                self.ai.api_key is None or not self.ai.api_key.get_secret_value()
            ):
                raise ValueError(
                    "ai.api_key is required when using Azure OpenAI in production"
                )
            # Redis: if enabled with SSL, password is required
            if (
                self.redis.enabled
                and self.redis.ssl
                and (
                    self.redis.password is None
                    or not self.redis.password.get_secret_value()
                )
            ):
                raise ValueError(
                    "redis.password is required when redis SSL is enabled in production"
                )
            # Observability: if sentry enabled, require DSN
            if self.observability.sentry_enabled and not self.observability.sentry_dsn:
                raise ValueError(
                    "observability.sentry_dsn must be set when sentry is enabled"
                )
        return self


# =============================================================================
# Singleton Accessor
# =============================================================================


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "AISettings",
    "ApplicationSettings",
    "CORSSettings",
    "EmailSettings",
    "Environment",
    "ExternalAPISettings",
    "FeatureFlagSettings",
    "HealthCheckSettings",
    "JWTSettings",
    "LoggingSettings",
    "MetricsSettings",
    "MongoDBSettings",
    "ObservabilitySettings",
    "RateLimitSettings",
    "RedisSettings",
    "SecuritySettings",
    "Settings",
    "StorageSettings",
    "get_settings",
]
