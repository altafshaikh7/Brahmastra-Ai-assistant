# core/constants.py
"""Centralized constants for the Brahmastra AI application.

All values are immutable and typed using `Final`.
This module serves as the single source of truth for every
configuration token used across the project.

Organisation:
    - Project metadata
    - Directory paths
    - API endpoints
    - HTTP protocol elements
    - Authentication & Security
    - User roles & permissions
    - Database, Cache, AI providers
    - Time, Limits, Regex patterns
    - Feature flags, Status values
    - Error & success messages
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

# ============================================================================
# 1. PROJECT INFORMATION
# ============================================================================

PROJECT_NAME: Final[str] = "Brahmastra AI"
PROJECT_DESCRIPTION: Final[str] = (
    "Enterprise-grade AI orchestration platform built with FastAPI."
)
COMPANY: Final[str] = "Brahmastra Inc."
AUTHOR: Final[str] = "Brahmastra Engineering Team"
VERSION: Final[str] = "0.1.0"
LICENSE: Final[str] = "Proprietary"
REPOSITORY: Final[str] = "https://github.com/brahmastra/brahmastra"
SUPPORT_EMAIL: Final[str] = "support@brahmastra.ai"

# ============================================================================
# 2. DIRECTORY PATHS
# ============================================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent

CONFIG_DIR: Final[Path] = BASE_DIR / "config"
STORAGE_DIR: Final[Path] = BASE_DIR / "storage"
LOGS_DIR: Final[Path] = BASE_DIR / "logs"
UPLOADS_DIR: Final[Path] = STORAGE_DIR / "uploads"
CACHE_DIR: Final[Path] = STORAGE_DIR / "cache"
TEMP_DIR: Final[Path] = STORAGE_DIR / "temp"
EXPORTS_DIR: Final[Path] = STORAGE_DIR / "exports"
BACKUPS_DIR: Final[Path] = STORAGE_DIR / "backups"
MODELS_DIR: Final[Path] = BASE_DIR / "models"
DOCS_DIR: Final[Path] = BASE_DIR / "docs"
STATIC_DIR: Final[Path] = BASE_DIR / "static"
TEMPLATES_DIR: Final[Path] = BASE_DIR / "templates"
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"

# ============================================================================
# 3. API ENDPOINTS
# ============================================================================

API_PREFIX: Final[str] = "/api"
API_VERSION: Final[str] = "v1"
API_V1: Final[str] = f"{API_PREFIX}/{API_VERSION}"

HEALTH_ENDPOINT: Final[str] = "/health"
STATUS_ENDPOINT: Final[str] = "/status"
METRICS_ENDPOINT: Final[str] = "/metrics"
DOCS_ENDPOINT: Final[str] = "/docs"
REDOC_ENDPOINT: Final[str] = "/redoc"
OPENAPI_ENDPOINT: Final[str] = "/openapi.json"

AUTH_ENDPOINT: Final[str] = f"{API_V1}/auth"
USERS_ENDPOINT: Final[str] = f"{API_V1}/users"
ADMIN_ENDPOINT: Final[str] = f"{API_V1}/admin"
AI_ENDPOINT: Final[str] = f"{API_V1}/ai"
TOOLS_ENDPOINT: Final[str] = f"{API_V1}/tools"
AUTOMATION_ENDPOINT: Final[str] = f"{API_V1}/automation"
WEBSOCKET_ENDPOINT: Final[str] = f"{API_V1}/ws"
WEBHOOK_ENDPOINT: Final[str] = f"{API_V1}/webhook"

# ============================================================================
# 4. HTTP METHODS
# ============================================================================

HTTP_GET: Final[str] = "GET"
HTTP_POST: Final[str] = "POST"
HTTP_PUT: Final[str] = "PUT"
HTTP_PATCH: Final[str] = "PATCH"
HTTP_DELETE: Final[str] = "DELETE"
HTTP_OPTIONS: Final[str] = "OPTIONS"
HTTP_HEAD: Final[str] = "HEAD"

# ============================================================================
# 5. HTTP HEADERS
# ============================================================================

HEADER_AUTHORIZATION: Final[str] = "Authorization"
HEADER_CONTENT_TYPE: Final[str] = "Content-Type"
HEADER_ACCEPT: Final[str] = "Accept"
HEADER_ACCEPT_ENCODING: Final[str] = "Accept-Encoding"
HEADER_ACCEPT_LANGUAGE: Final[str] = "Accept-Language"
HEADER_CACHE_CONTROL: Final[str] = "Cache-Control"
HEADER_REQUEST_ID: Final[str] = "X-Request-ID"
HEADER_CORRELATION_ID: Final[str] = "X-Correlation-ID"
HEADER_API_KEY: Final[str] = "X-API-Key"
HEADER_USER_AGENT: Final[str] = "User-Agent"
HEADER_ORIGIN: Final[str] = "Origin"
HEADER_HOST: Final[str] = "Host"
HEADER_ETAG: Final[str] = "ETag"
HEADER_IF_NONE_MATCH: Final[str] = "If-None-Match"
HEADER_LOCATION: Final[str] = "Location"

# ============================================================================
# 6. CONTENT TYPES
# ============================================================================

CONTENT_TYPE_JSON: Final[str] = "application/json"
CONTENT_TYPE_XML: Final[str] = "application/xml"
CONTENT_TYPE_PLAIN: Final[str] = "text/plain"
CONTENT_TYPE_HTML: Final[str] = "text/html"
CONTENT_TYPE_FORM: Final[str] = "multipart/form-data"
CONTENT_TYPE_OCTET_STREAM: Final[str] = "application/octet-stream"

# ============================================================================
# 7. AUTHENTICATION
# ============================================================================

AUTH_SCHEME_BEARER: Final[str] = "Bearer"
AUTH_JWT: Final[str] = "JWT"
ACCESS_TOKEN: Final[str] = "access_token"
REFRESH_TOKEN: Final[str] = "refresh_token"
TOKEN_PREFIX: Final[str] = "Bearer"
JWT_ALGORITHM: Final[str] = "HS256"
DEFAULT_CLOCK_SKEW: Final[int] = 30  # seconds

# ============================================================================
# 8. USER ROLES
# ============================================================================

ROLE_SUPER_ADMIN: Final[str] = "super_admin"
ROLE_ADMIN: Final[str] = "admin"
ROLE_MANAGER: Final[str] = "manager"
ROLE_MODERATOR: Final[str] = "moderator"
ROLE_OPERATOR: Final[str] = "operator"
ROLE_USER: Final[str] = "user"
ROLE_GUEST: Final[str] = "guest"
ROLE_ANONYMOUS: Final[str] = "anonymous"

# ============================================================================
# 9. PERMISSIONS
# ============================================================================

PERM_READ: Final[str] = "read"
PERM_WRITE: Final[str] = "write"
PERM_UPDATE: Final[str] = "update"
PERM_DELETE: Final[str] = "delete"
PERM_EXECUTE: Final[str] = "execute"
PERM_MANAGE: Final[str] = "manage"
PERM_ADMINISTER: Final[str] = "administer"

# ============================================================================
# 10. CACHE
# ============================================================================

CACHE_PREFIX: Final[str] = "brahmastra:"
CACHE_USER_PREFIX: Final[str] = f"{CACHE_PREFIX}user:"
CACHE_TOKEN_PREFIX: Final[str] = f"{CACHE_PREFIX}token:"
CACHE_SESSION_PREFIX: Final[str] = f"{CACHE_PREFIX}session:"
CACHE_PERMISSION_PREFIX: Final[str] = f"{CACHE_PREFIX}perm:"
CACHE_AI_PREFIX: Final[str] = f"{CACHE_PREFIX}ai:"

# ============================================================================
# 11. DATABASE
# ============================================================================

DB_TYPE_MONGO: Final[str] = "mongodb"
DB_TYPE_REDIS: Final[str] = "redis"
DB_TYPE_POSTGRES: Final[str] = "postgresql"
DB_TYPE_SQLITE: Final[str] = "sqlite"
DB_TYPE_MYSQL: Final[str] = "mysql"

DEFAULT_CONNECTION_TIMEOUT: Final[int] = 20  # seconds
DEFAULT_QUERY_TIMEOUT: Final[int] = 30       # seconds

# ============================================================================
# 12. AI PROVIDERS
# ============================================================================

AI_PROVIDER_OPENAI: Final[str] = "openai"
AI_PROVIDER_AZURE_OPENAI: Final[str] = "azure_openai"
AI_PROVIDER_GEMINI: Final[str] = "gemini"
AI_PROVIDER_ANTHROPIC: Final[str] = "anthropic"
AI_PROVIDER_OPENROUTER: Final[str] = "openrouter"
AI_PROVIDER_OLLAMA: Final[str] = "ollama"

DEFAULT_AI_MODEL: Final[str] = "gpt-4"
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_TOP_P: Final[float] = 1.0
DEFAULT_AI_TIMEOUT: Final[int] = 60  # seconds

# ============================================================================
# 13. ENVIRONMENTS
# ============================================================================

ENV_DEVELOPMENT: Final[str] = "development"
ENV_TESTING: Final[str] = "testing"
ENV_STAGING: Final[str] = "staging"
ENV_PRODUCTION: Final[str] = "production"

# ============================================================================
# 14. LOGGING
# ============================================================================

DEFAULT_LOG_LEVEL: Final[str] = "INFO"
LOG_FILE_NAME: Final[str] = "brahmastra.log"
LOG_FORMAT: Final[str] = (
    "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s"
)
LOG_ROTATION: Final[str] = "10 MB"
LOG_RETENTION: Final[str] = "10 days"
JSON_LOGGING_ENABLED: Final[bool] = False

# ============================================================================
# 15. FILE EXTENSIONS
# ============================================================================

EXT_JSON: Final[str] = ".json"
EXT_TXT: Final[str] = ".txt"
EXT_CSV: Final[str] = ".csv"
EXT_PDF: Final[str] = ".pdf"
EXT_PNG: Final[str] = ".png"
EXT_JPG: Final[str] = ".jpg"
EXT_JPEG: Final[str] = ".jpeg"
EXT_WEBP: Final[str] = ".webp"
EXT_ZIP: Final[str] = ".zip"
EXT_MP4: Final[str] = ".mp4"

# ============================================================================
# 16. MIME TYPES
# ============================================================================

MIME_JSON: Final[str] = "application/json"
MIME_XML: Final[str] = "application/xml"
MIME_PLAIN: Final[str] = "text/plain"
MIME_HTML: Final[str] = "text/html"
MIME_FORM: Final[str] = "multipart/form-data"
MIME_OCTET: Final[str] = "application/octet-stream"
MIME_PNG: Final[str] = "image/png"
MIME_JPEG: Final[str] = "image/jpeg"
MIME_WEBP: Final[str] = "image/webp"
MIME_PDF: Final[str] = "application/pdf"
MIME_ZIP: Final[str] = "application/zip"
MIME_MP4: Final[str] = "video/mp4"

# ============================================================================
# 17. TIME CONSTANTS (in seconds)
# ============================================================================

SECOND: Final[int] = 1
MINUTE: Final[int] = 60
HOUR: Final[int] = 3600
DAY: Final[int] = 86400
WEEK: Final[int] = 604800
MONTH: Final[int] = 2592000   # 30 days
YEAR: Final[int] = 31536000   # 365 days

# ============================================================================
# 18. LIMITS
# ============================================================================

MAX_UPLOAD_SIZE: Final[int] = 50 * 1024 * 1024  # 50 MB
MAX_REQUEST_SIZE: Final[int] = 10 * 1024 * 1024 # 10 MB
MAX_PASSWORD_LENGTH: Final[int] = 128
MAX_USERNAME_LENGTH: Final[int] = 64
DEFAULT_PAGINATION_SIZE: Final[int] = 20
DEFAULT_RETRY_ATTEMPTS: Final[int] = 3

# ============================================================================
# 19. REGEX PATTERNS (compiled)
# ============================================================================

REGEX_EMAIL: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)
REGEX_PHONE: Final[re.Pattern[str]] = re.compile(
    r"^\+?[1-9]\d{1,14}$"  # E.164 simplified
)
REGEX_USERNAME: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9_]{3,64}$"
)
REGEX_UUID: Final[re.Pattern[str]] = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
REGEX_PASSWORD: Final[re.Pattern[str]] = re.compile(
    r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@$!%*?&#])[A-Za-z\d@$!%*?&#]{8,128}$"
)
REGEX_URL: Final[re.Pattern[str]] = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)

# ============================================================================
# 20. CORS DEFAULTS
# ============================================================================

CORS_ALLOW_ORIGINS: Final[list[str]] = ["*"]
CORS_ALLOW_METHODS: Final[list[str]] = ["*"]
CORS_ALLOW_HEADERS: Final[list[str]] = ["*"]
CORS_EXPOSE_HEADERS: Final[list[str]] = [
    HEADER_REQUEST_ID,
    HEADER_CORRELATION_ID,
]

# ============================================================================
# 21. SECURITY HEADERS & LIMITS
# ============================================================================

CSRF_HEADER: Final[str] = "X-CSRF-Token"
API_KEY_HEADER: Final[str] = HEADER_API_KEY
REQUEST_ID_HEADER: Final[str] = HEADER_REQUEST_ID
CORRELATION_ID_HEADER: Final[str] = HEADER_CORRELATION_ID
PASSWORD_MIN_LENGTH: Final[int] = 8
PASSWORD_MAX_LENGTH: Final[int] = MAX_PASSWORD_LENGTH

# ============================================================================
# 22. COMMON STRINGS
# ============================================================================

YES: Final[str] = "yes"
NO: Final[str] = "no"
SUCCESS: Final[str] = "success"
FAILURE: Final[str] = "failure"
UNKNOWN: Final[str] = "unknown"

# ============================================================================
# 23. FEATURE FLAGS
# ============================================================================

FEATURE_AI: Final[str] = "enable_ai"
FEATURE_REDIS: Final[str] = "enable_redis"
FEATURE_EMAIL: Final[str] = "enable_email"
FEATURE_METRICS: Final[str] = "enable_metrics"
FEATURE_AUDIT: Final[str] = "enable_audit"
FEATURE_WEBSOCKET: Final[str] = "enable_websocket"

# ============================================================================
# 24. STATUS VALUES
# ============================================================================

STATUS_ACTIVE: Final[str] = "active"
STATUS_INACTIVE: Final[str] = "inactive"
STATUS_PENDING: Final[str] = "pending"
STATUS_DELETED: Final[str] = "deleted"
STATUS_BLOCKED: Final[str] = "blocked"
STATUS_DISABLED: Final[str] = "disabled"

# ============================================================================
# 25. ERROR MESSAGES
# ============================================================================

# Generic
ERROR_INTERNAL: Final[str] = "An internal error occurred."
ERROR_NOT_FOUND: Final[str] = "Resource not found."
ERROR_VALIDATION: Final[str] = "Validation error."

# Authentication & Authorization
ERROR_AUTHENTICATION: Final[str] = "Authentication failed."
ERROR_AUTHORIZATION: Final[str] = "Insufficient permissions."
ERROR_TOKEN_EXPIRED: Final[str] = "Token has expired."
ERROR_INVALID_TOKEN: Final[str] = "Invalid token."

# Configuration
ERROR_CONFIG_MISSING: Final[str] = "Required configuration is missing."
ERROR_CONFIG_INVALID: Final[str] = "Configuration is invalid."

# Database
ERROR_DB_CONNECTION: Final[str] = "Database connection failed."
ERROR_DB_QUERY: Final[str] = "Database query failed."

# AI
ERROR_AI_REQUEST: Final[str] = "AI service request failed."
ERROR_AI_TIMEOUT: Final[str] = "AI service timed out."
ERROR_AI_RATE_LIMIT: Final[str] = "AI rate limit exceeded."

# ============================================================================
# 26. SUCCESS MESSAGES
# ============================================================================

SUCCESS_CREATED: Final[str] = "Resource created successfully."
SUCCESS_UPDATED: Final[str] = "Resource updated successfully."
SUCCESS_DELETED: Final[str] = "Resource deleted successfully."
SUCCESS_AUTHENTICATED: Final[str] = "Authentication successful."

# ============================================================================
# 27. PUBLIC API
# ============================================================================

__all__ = [
    # Project
    "PROJECT_NAME",
    "PROJECT_DESCRIPTION",
    "COMPANY",
    "AUTHOR",
    "VERSION",
    "LICENSE",
    "REPOSITORY",
    "SUPPORT_EMAIL",
    # Paths
    "BASE_DIR",
    "CONFIG_DIR",
    "STORAGE_DIR",
    "LOGS_DIR",
    "UPLOADS_DIR",
    "CACHE_DIR",
    "TEMP_DIR",
    "EXPORTS_DIR",
    "BACKUPS_DIR",
    "MODELS_DIR",
    "DOCS_DIR",
    "STATIC_DIR",
    "TEMPLATES_DIR",
    "ASSETS_DIR",
    # API
    "API_PREFIX",
    "API_VERSION",
    "API_V1",
    "HEALTH_ENDPOINT",
    "STATUS_ENDPOINT",
    "METRICS_ENDPOINT",
    "DOCS_ENDPOINT",
    "REDOC_ENDPOINT",
    "OPENAPI_ENDPOINT",
    "AUTH_ENDPOINT",
    "USERS_ENDPOINT",
    "ADMIN_ENDPOINT",
    "AI_ENDPOINT",
    "TOOLS_ENDPOINT",
    "AUTOMATION_ENDPOINT",
    "WEBSOCKET_ENDPOINT",
    "WEBHOOK_ENDPOINT",
    # HTTP
    "HTTP_GET",
    "HTTP_POST",
    "HTTP_PUT",
    "HTTP_PATCH",
    "HTTP_DELETE",
    "HTTP_OPTIONS",
    "HTTP_HEAD",
    # Headers
    "HEADER_AUTHORIZATION",
    "HEADER_CONTENT_TYPE",
    "HEADER_ACCEPT",
    "HEADER_ACCEPT_ENCODING",
    "HEADER_ACCEPT_LANGUAGE",
    "HEADER_CACHE_CONTROL",
    "HEADER_REQUEST_ID",
    "HEADER_CORRELATION_ID",
    "HEADER_API_KEY",
    "HEADER_USER_AGENT",
    "HEADER_ORIGIN",
    "HEADER_HOST",
    "HEADER_ETAG",
    "HEADER_IF_NONE_MATCH",
    "HEADER_LOCATION",
    # Content Types
    "CONTENT_TYPE_JSON",
    "CONTENT_TYPE_XML",
    "CONTENT_TYPE_PLAIN",
    "CONTENT_TYPE_HTML",
    "CONTENT_TYPE_FORM",
    "CONTENT_TYPE_OCTET_STREAM",
    # Auth
    "AUTH_SCHEME_BEARER",
    "AUTH_JWT",
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
    "TOKEN_PREFIX",
    "JWT_ALGORITHM",
    "DEFAULT_CLOCK_SKEW",
    # Roles
    "ROLE_SUPER_ADMIN",
    "ROLE_ADMIN",
    "ROLE_MANAGER",
    "ROLE_MODERATOR",
    "ROLE_OPERATOR",
    "ROLE_USER",
    "ROLE_GUEST",
    "ROLE_ANONYMOUS",
    # Permissions
    "PERM_READ",
    "PERM_WRITE",
    "PERM_UPDATE",
    "PERM_DELETE",
    "PERM_EXECUTE",
    "PERM_MANAGE",
    "PERM_ADMINISTER",
    # Cache
    "CACHE_PREFIX",
    "CACHE_USER_PREFIX",
    "CACHE_TOKEN_PREFIX",
    "CACHE_SESSION_PREFIX",
    "CACHE_PERMISSION_PREFIX",
    "CACHE_AI_PREFIX",
    # DB
    "DB_TYPE_MONGO",
    "DB_TYPE_REDIS",
    "DB_TYPE_POSTGRES",
    "DB_TYPE_SQLITE",
    "DB_TYPE_MYSQL",
    "DEFAULT_CONNECTION_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
    # AI
    "AI_PROVIDER_OPENAI",
    "AI_PROVIDER_AZURE_OPENAI",
    "AI_PROVIDER_GEMINI",
    "AI_PROVIDER_ANTHROPIC",
    "AI_PROVIDER_OPENROUTER",
    "AI_PROVIDER_OLLAMA",
    "DEFAULT_AI_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TOP_P",
    "DEFAULT_AI_TIMEOUT",
    # Environments
    "ENV_DEVELOPMENT",
    "ENV_TESTING",
    "ENV_STAGING",
    "ENV_PRODUCTION",
    # Logging
    "DEFAULT_LOG_LEVEL",
    "LOG_FILE_NAME",
    "LOG_FORMAT",
    "LOG_ROTATION",
    "LOG_RETENTION",
    "JSON_LOGGING_ENABLED",
    # Extensions
    "EXT_JSON",
    "EXT_TXT",
    "EXT_CSV",
    "EXT_PDF",
    "EXT_PNG",
    "EXT_JPG",
    "EXT_JPEG",
    "EXT_WEBP",
    "EXT_ZIP",
    "EXT_MP4",
    # MIME
    "MIME_JSON",
    "MIME_XML",
    "MIME_PLAIN",
    "MIME_HTML",
    "MIME_FORM",
    "MIME_OCTET",
    "MIME_PNG",
    "MIME_JPEG",
    "MIME_WEBP",
    "MIME_PDF",
    "MIME_ZIP",
    "MIME_MP4",
    # Time
    "SECOND",
    "MINUTE",
    "HOUR",
    "DAY",
    "WEEK",
    "MONTH",
    "YEAR",
    # Limits
    "MAX_UPLOAD_SIZE",
    "MAX_REQUEST_SIZE",
    "MAX_PASSWORD_LENGTH",
    "MAX_USERNAME_LENGTH",
    "DEFAULT_PAGINATION_SIZE",
    "DEFAULT_RETRY_ATTEMPTS",
    # Regex
    "REGEX_EMAIL",
    "REGEX_PHONE",
    "REGEX_USERNAME",
    "REGEX_UUID",
    "REGEX_PASSWORD",
    "REGEX_URL",
    # CORS
    "CORS_ALLOW_ORIGINS",
    "CORS_ALLOW_METHODS",
    "CORS_ALLOW_HEADERS",
    "CORS_EXPOSE_HEADERS",
    # Security
    "CSRF_HEADER",
    "API_KEY_HEADER",
    "REQUEST_ID_HEADER",
    "CORRELATION_ID_HEADER",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_MAX_LENGTH",
    # Common Strings
    "YES",
    "NO",
    "SUCCESS",
    "FAILURE",
    "UNKNOWN",
    # Features
    "FEATURE_AI",
    "FEATURE_REDIS",
    "FEATURE_EMAIL",
    "FEATURE_METRICS",
    "FEATURE_AUDIT",
    "FEATURE_WEBSOCKET",
    # Status
    "STATUS_ACTIVE",
    "STATUS_INACTIVE",
    "STATUS_PENDING",
    "STATUS_DELETED",
    "STATUS_BLOCKED",
    "STATUS_DISABLED",
    # Errors
    "ERROR_INTERNAL",
    "ERROR_NOT_FOUND",
    "ERROR_VALIDATION",
    "ERROR_AUTHENTICATION",
    "ERROR_AUTHORIZATION",
    "ERROR_TOKEN_EXPIRED",
    "ERROR_INVALID_TOKEN",
    "ERROR_CONFIG_MISSING",
    "ERROR_CONFIG_INVALID",
    "ERROR_DB_CONNECTION",
    "ERROR_DB_QUERY",
    "ERROR_AI_REQUEST",
    "ERROR_AI_TIMEOUT",
    "ERROR_AI_RATE_LIMIT",
    # Success
    "SUCCESS_CREATED",
    "SUCCESS_UPDATED",
    "SUCCESS_DELETED",
    "SUCCESS_AUTHENTICATED",
]