# middleware/request_id.py
"""Request context middleware for enterprise-grade request tracing.

Manages request ID, correlation ID, client IP, user agent, and processing time.
Integrates with centralized logging and ensures tracing headers on all responses.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from core.config import get_settings
from utils.logger import (
    clear_correlation_id,
    clear_request_id,
    get_logger,
    set_correlation_id,
    set_request_id,
)

logger = get_logger(__name__)

# Default header names (fallback if configuration is missing)
DEFAULT_REQUEST_ID_HEADER = "X-Request-ID"
DEFAULT_CORRELATION_ID_HEADER = "X-Correlation-ID"
DEFAULT_PROCESS_TIME_HEADER = "X-Process-Time"
UNKNOWN_CLIENT = "unknown"
USER_AGENT_MAX_LENGTH = 512


class RequestIDMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that manages request-scoped context and tracing headers.

    Responsibilities:
        - Generates or validates request ID and correlation ID.
        - Stores context in `request.state` and `ContextVar` for logging.
        - Measures request processing time (nanosecond precision) in milliseconds.
        - Logs structured request/response events.
        - Ensures tracing headers on all responses, even on exceptions.
        - Cleans up context variables to prevent leakage.
    """

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        app_config = getattr(settings, "application", None)
        self._request_id_header = getattr(
            app_config, "request_id_header", DEFAULT_REQUEST_ID_HEADER
        )
        self._correlation_id_header = getattr(
            app_config, "correlation_id_header", DEFAULT_CORRELATION_ID_HEADER
        )
        self._process_time_header = getattr(
            app_config, "process_time_header", DEFAULT_PROCESS_TIME_HEADER
        )

    @staticmethod
    def _validate_uuid4(value: str | None) -> str | None:
        """Validate a string as a canonical UUIDv4.

        Args:
            value: The string to validate, or None.

        Returns:
            The validated UUID string if valid, otherwise None.
        """
        if not value:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            uid = uuid.UUID(cleaned)
            # Accept only version 4 (and variant as per RFC)
            if uid.version != 4:
                return None
            return str(uid)
        except ValueError:
            return None

    def _get_request_id(self, request: Request) -> str:
        """Generate or retrieve a valid request ID from the configured header."""
        header_value = request.headers.get(self._request_id_header)
        validated = self._validate_uuid4(header_value)
        if validated is not None:
            return validated
        new_id = str(uuid.uuid4())
        logger.debug("Generated new request ID: %s", new_id)
        return new_id

    def _get_correlation_id(self, request: Request) -> str:
        """Generate or retrieve a valid correlation ID from the configured header."""
        header_value = request.headers.get(self._correlation_id_header)
        validated = self._validate_uuid4(header_value)
        if validated is not None:
            return validated
        new_id = str(uuid.uuid4())
        logger.debug("Generated new correlation ID: %s", new_id)
        return new_id

    def _get_client_ip(self, request: Request) -> str:
        """Determine the client IP using standard proxy headers.

        Priority: CF-Connecting-IP, X-Forwarded-For, X-Real-IP, direct host.
        """
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the leftmost IP (client original)
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return UNKNOWN_CLIENT

    def _get_user_agent(self, request: Request) -> str:
        """Extract and sanitize the User-Agent header."""
        ua = request.headers.get("User-Agent", UNKNOWN_CLIENT)
        return ua.strip()[:USER_AGENT_MAX_LENGTH]

    def _attach_tracing_headers(
        self,
        response: Response,
        request_id: str,
        correlation_id: str,
        duration_ms: float,
    ) -> None:
        """Attach tracing headers to the response."""
        response.headers[self._request_id_header] = request_id
        response.headers[self._correlation_id_header] = correlation_id
        response.headers[self._process_time_header] = f"{duration_ms:.3f}"

    def _log_request(
        self,
        method: str,
        url: str,
        client_ip: str,
        user_agent: str,
    ) -> None:
        """Emit structured log for incoming request."""
        logger.info(
            "Incoming request",
            extra={
                "method": method,
                "url": url,
                "client_ip": client_ip,
                "user_agent": user_agent,
            },
        )

    def _log_response(
        self,
        method: str,
        url: str,
        status_code: int,
        client_ip: str,
        user_agent: str,
        duration_ms: float,
    ) -> None:
        """Emit structured log for completed request."""
        logger.info(
            "Completed request",
            extra={
                "method": method,
                "url": url,
                "status_code": status_code,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "duration_ms": duration_ms,
            },
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Main entry point for the middleware."""
        # Read headers and generate identifiers
        request_id = self._get_request_id(request)
        correlation_id = self._get_correlation_id(request)

        # Set context variables for logging
        set_request_id(request_id)
        set_correlation_id(correlation_id)

        # Extract client info
        client_ip = self._get_client_ip(request)
        user_agent = self._get_user_agent(request)

        # Store in request.state
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent

        # Start timing (nanoseconds)
        start_ns = time.perf_counter_ns()
        request.state.request_start_ns = start_ns

        # Cache for logging
        method = request.method
        url = str(request.url)

        self._log_request(method, url, client_ip, user_agent)

        try:
            response = await call_next(request)
        finally:
            # Always clear context variables to prevent leakage
            clear_request_id()
            clear_correlation_id()

        # Compute duration in milliseconds (rounded to 3 decimals)
        end_ns = time.perf_counter_ns()
        duration_ns = end_ns - start_ns
        duration_ms = duration_ns / 1_000_000.0  # convert to ms
        request.state.process_time_ms = duration_ms

        # Attach tracing headers
        self._attach_tracing_headers(response, request_id, correlation_id, duration_ms)

        # Log completion
        self._log_response(
            method,
            url,
            response.status_code,
            client_ip,
            user_agent,
            duration_ms,
        )

        return response


# Public alias for backward compatibility
request_id_middleware = RequestIDMiddleware
