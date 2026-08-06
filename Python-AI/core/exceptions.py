"""Centralized exception hierarchy and FastAPI error handling for the Brahmastra AI project."""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorCode(str, Enum):
    """Machine-readable error codes for the API."""

    APPLICATION_ERROR = "application_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    CONFLICT_ERROR = "conflict_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
    AI_SERVICE_ERROR = "ai_service_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    CONFIGURATION_ERROR = "configuration_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"


class ApplicationError(Exception):
    """Base class for all application-specific errors."""

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | str = ErrorCode.APPLICATION_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code if isinstance(code, str) else code.value
        self.status_code = status_code
        self.details = dict(details or {})
        super().__init__(message)


class AuthenticationError(ApplicationError):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.AUTHENTICATION_ERROR,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(ApplicationError):
    """Raised when a caller lacks required authorization."""

    def __init__(
        self, message: str = "Not authorized", details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.AUTHORIZATION_ERROR,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ValidationError(ApplicationError):
    """Raised when request or domain validation fails."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ResourceNotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ConflictError(ApplicationError):
    """Raised when a resource already exists or conflicts with state."""

    def __init__(
        self, message: str = "Conflict", details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.CONFLICT_ERROR,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class DatabaseError(ApplicationError):
    """Raised when a persistence layer operation fails."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.DATABASE_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ExternalServiceError(ApplicationError):
    """Raised when an upstream external service fails."""

    def __init__(
        self,
        message: str = "External service error",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class AIServiceError(ApplicationError):
    """Raised when an AI provider operation fails."""

    def __init__(
        self,
        message: str = "AI service error",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.AI_SERVICE_ERROR,
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class RateLimitError(ApplicationError):
    """Raised when a caller exceeds a rate limit."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.RATE_LIMIT_ERROR,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ConfigurationError(ApplicationError):
    """Raised when required configuration is missing or invalid."""

    def __init__(
        self,
        message: str = "Configuration error",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.CONFIGURATION_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class InternalServerError(ApplicationError):
    """Raised for unexpected internal failures."""

    def __init__(
        self,
        message: str = "Internal server error",
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ErrorResponseModel(BaseModel):
    """Standard API error envelope following RFC 7807-style Problem Details."""

    success: bool = Field(default=False)
    error: str = Field(default="error")
    code: str = Field(default=ErrorCode.APPLICATION_ERROR.value)
    message: str = Field(default="An unexpected error occurred")
    details: dict[str, Any] = Field(default_factory=dict)
    path: str = Field(default="")
    request_id: str = Field(default="")
    correlation_id: str | None = Field(default=None)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


def _get_request_id(request: Request) -> str:
    return (
        request.headers.get("x-request-id") or request.headers.get("X-Request-ID") or ""
    )


def _get_correlation_id(request: Request) -> str | None:
    return request.headers.get("x-correlation-id") or request.headers.get(
        "X-Correlation-ID"
    )


def _build_error_response(
    *,
    request: Request,
    message: str,
    code: str,
    status_code: int,
    details: Mapping[str, Any] | None = None,
    exc: Exception | None = None,
    include_traceback: bool = False,
) -> JSONResponse:
    payload = ErrorResponseModel(
        error="error",
        code=code,
        message=message,
        details=dict(details or {}),
        path=str(request.url.path),
        request_id=_get_request_id(request),
        correlation_id=_get_correlation_id(request),
    )
    if include_traceback and exc is not None:
        payload.details["traceback"] = "\n".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _log_exception(
    *,
    request: Request,
    exc: Exception,
    status_code: int,
    include_traceback: bool,
) -> None:
    extra: dict[str, Any] = {
        "event": "api_exception",
        "exception_type": type(exc).__name__,
        "path": str(request.url.path),
        "method": request.method,
        "status_code": status_code,
    }
    if include_traceback:
        extra["traceback"] = traceback.format_exception(
            type(exc), exc, exc.__traceback__
        )
    logger.exception(
        "Unhandled exception",
        extra=extra,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized FastAPI exception handlers for the application."""

    @app.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        _log_exception(
            request=request,
            exc=exc,
            status_code=exc.status_code,
            include_traceback=False,
        )
        return _build_error_response(
            request=request,
            message=exc.message,
            code=exc.code,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        _log_exception(
            request=request,
            exc=exc,
            status_code=exc.status_code,
            include_traceback=False,
        )
        return _build_error_response(
            request=request,
            message=exc.detail if isinstance(exc.detail, str) else "HTTP error",
            code=ErrorCode.APPLICATION_ERROR.value,
            status_code=exc.status_code,
            details={"reason": exc.reason_phrase},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: dict[str, Any] = {
            "errors": [
                {
                    "loc": list(error.get("loc", [])),
                    "msg": error.get("msg", "Validation error"),
                    "type": error.get("type", "validation_error"),
                }
                for error in exc.errors()
            ]
        }
        _log_exception(
            request=request,
            exc=exc,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            include_traceback=False,
        )
        return _build_error_response(
            request=request,
            message="Request validation failed",
            code=ErrorCode.VALIDATION_ERROR.value,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )

    @app.exception_handler(ValidationError)
    async def handle_validation_error(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        _log_exception(
            request=request,
            exc=exc,
            status_code=exc.status_code,
            include_traceback=False,
        )
        return _build_error_response(
            request=request,
            message=exc.message,
            code=exc.code,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        _log_exception(
            request=request,
            exc=exc,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            include_traceback=True,
        )
        return _build_error_response(
            request=request,
            message="Internal server error",
            code=ErrorCode.INTERNAL_SERVER_ERROR.value,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={},
            exc=exc,
            include_traceback=False,
        )


__all__ = [
    "AIServiceError",
    "ApplicationError",
    "AuthenticationError",
    "AuthorizationError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseError",
    "ErrorCode",
    "ErrorResponseModel",
    "ExternalServiceError",
    "InternalServerError",
    "RateLimitError",
    "ResourceNotFoundError",
    "ValidationError",
    "register_exception_handlers",
]
