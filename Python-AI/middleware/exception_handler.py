# middleware/exception_handler.py
"""Global exception handlers for the Brahmastra AI FastAPI application.

Registers custom handlers for all anticipated exception types, ensuring
consistent, secure JSON error responses.  In development mode, the
response may include a full traceback for debugging; in production,
only a sanitised message is returned.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_settings
from schemas.response import ErrorResponse
from utils.logger import get_logger

logger = get_logger(__name__)

_settings = get_settings()
_IS_DEBUG = _settings.application.debug

# Default error messages (module-level constants)
MSG_INTERNAL_ERROR = "Internal Server Error"
MSG_VALIDATION_ERROR = "Validation Error"
MSG_BAD_REQUEST = "Bad Request"
MSG_FORBIDDEN = "Forbidden"
MSG_NOT_FOUND = "Not Found"
MSG_NOT_IMPLEMENTED = "Not Implemented"
MSG_UNEXPECTED = "An unexpected error occurred."

# Type aliases for clarity
LogLevel = Callable[..., None]  # logger.info, logger.warning, etc.
ExceptionHandler = Callable[[Request, Exception], JSONResponse]


def _get_request_id(request: Request) -> str | None:
    """Extract request ID from request.state (set by middleware) or headers."""
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    return request.headers.get(_settings.application.request_id_header)


def _get_correlation_id(request: Request) -> str | None:
    """Extract correlation ID from request.state (set by middleware)."""
    return getattr(request.state, "correlation_id", None)


def _build_response(
    request: Request,
    http_status: int,
    error: str,
    detail: str | list[dict[str, object]] | None = None,
    error_code: str | None = None,
) -> JSONResponse:
    """Construct a standardised JSON error response, including traceback in debug."""
    response_detail = detail
    if _IS_DEBUG:
        tb = traceback.format_exc()
        if tb and tb != "NoneType: None\n":
            response_detail = {
                "message": str(detail) if detail else error,
                "traceback": tb,
            }
    return JSONResponse(
        status_code=http_status,
        content=ErrorResponse(
            request_id=_get_request_id(request),
            error=error,
            detail=response_detail,
            error_code=error_code,
        ).model_dump(),
    )


def _handle_exception(
    request: Request,
    exc: Exception,
    status: HTTPStatus,
    log_level: LogLevel,
    error_message: str,
    detail_func: Callable[[Exception], Any] | None = None,
    log_extra_func: Callable[[Request, Exception], dict[str, Any]] | None = None,
) -> JSONResponse:
    """Generic handler for any exception with a given configuration."""
    request_id = _get_request_id(request)
    correlation_id = _get_correlation_id(request)

    # Build base extra dict
    extra = {
        "request_id": request_id,
        "correlation_id": correlation_id,
        "path": str(request.url),
    }
    if log_extra_func:
        extra.update(log_extra_func(request, exc))

    # Log with the specified level; include exc_info only for error level
    log_level("Exception handled", extra=extra, exc_info=(log_level is logger.error))

    # Determine detail
    detail = detail_func(exc) if detail_func else None
    if detail is None and _IS_DEBUG:
        detail = str(exc)  # fallback to exception string in debug

    return _build_response(
        request,
        http_status=status.value,
        error=error_message,
        detail=detail,
    )


# Configuration mapping: exception type -> (status, log_level, error_message, detail_func, log_extra_func)
# Note: StarletteHTTPException is handled separately because status is dynamic.
EXCEPTION_CONFIG: dict[type[Exception], tuple] = {
    RequestValidationError: (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        logger.warning,
        MSG_VALIDATION_ERROR,
        lambda e: e.errors(),
        None,
    ),
    PydanticValidationError: (
        HTTPStatus.UNPROCESSABLE_ENTITY,
        logger.warning,
        MSG_VALIDATION_ERROR,
        lambda e: e.errors(),
        None,
    ),
    ValueError: (
        HTTPStatus.BAD_REQUEST,
        logger.warning,
        MSG_BAD_REQUEST,
        lambda e: str(e) if _IS_DEBUG else "Invalid input provided",
        None,
    ),
    PermissionError: (
        HTTPStatus.FORBIDDEN,
        logger.warning,
        MSG_FORBIDDEN,
        lambda _: "Access denied" if not _IS_DEBUG else None,
        None,
    ),
    FileNotFoundError: (
        HTTPStatus.NOT_FOUND,
        logger.warning,
        MSG_NOT_FOUND,
        lambda _: "Resource not found" if not _IS_DEBUG else None,
        None,
    ),
    RuntimeError: (
        HTTPStatus.INTERNAL_SERVER_ERROR,
        logger.error,
        MSG_INTERNAL_ERROR,
        lambda e: str(e) if _IS_DEBUG else "A runtime error occurred.",
        None,
    ),
    NotImplementedError: (
        HTTPStatus.NOT_IMPLEMENTED,
        logger.error,
        MSG_NOT_IMPLEMENTED,
        lambda _: "This functionality is not yet implemented.",
        None,
    ),
    Exception: (  # catch-all
        HTTPStatus.INTERNAL_SERVER_ERROR,
        logger.error,
        MSG_INTERNAL_ERROR,
        lambda _: MSG_UNEXPECTED,
        lambda req, exc: {"exception_type": type(exc).__name__},
    ),
}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to the FastAPI application."""

    # Special handler for HTTPException (status code is dynamic)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _handle_exception(
            request,
            exc,
            status=HTTPStatus(exc.status_code),
            log_level=logger.warning,
            error_message="HTTP Error",
            detail_func=lambda e: str(e.detail) if e.detail else None,
        )

    # Register all other exceptions from the configuration
    # Use a factory function to avoid closure issues with loop variables
    def _make_handler(
        status: HTTPStatus,
        log_level: LogLevel,
        error_message: str,
        detail_func: Callable[[Exception], Any] | None,
        log_extra_func: Callable[[Request, Exception], dict[str, Any]] | None,
    ) -> ExceptionHandler:
        async def handler(request: Request, exc: Exception) -> JSONResponse:
            return _handle_exception(
                request,
                exc,
                status=status,
                log_level=log_level,
                error_message=error_message,
                detail_func=detail_func,
                log_extra_func=log_extra_func,
            )

        return handler

    for exc_type, (
        status,
        log_level,
        error_msg,
        detail_func,
        extra_func,
    ) in EXCEPTION_CONFIG.items():
        # StarletteHTTPException is already handled separately
        if exc_type is StarletteHTTPException:
            continue
        app.add_exception_handler(
            exc_type,
            _make_handler(status, log_level, error_msg, detail_func, extra_func),
        )
