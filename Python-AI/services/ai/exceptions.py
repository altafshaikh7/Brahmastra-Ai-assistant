# services/ai/exceptions.py
"""Centralized Exception Hierarchy for the AI Service module.

This module defines all domain exceptions used across AI providers, factories,
and service layers, deriving from ApplicationError for standardized FastAPI handling.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from core.exceptions import ApplicationError, ErrorCode


class AIServiceException(ApplicationError):
    """Base exception for all AI Service failures."""

    def __init__(
        self,
        message: str = "AI service error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.APPLICATION_ERROR,
            status_code=status_code,
            details=details,
        )


class APIKeyMissingException(AIServiceException):
    """Raised when a provider API key is missing or unconfigured."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            message=f"API key for provider '{provider}' is missing or unconfigured.",
            status_code=401,
            details={"provider": provider},
        )


class TimeoutException(AIServiceException):
    """Raised when an AI provider request times out."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            message=f"AI request to provider '{provider}' timed out after {timeout_seconds} seconds.",
            status_code=504,
            details={"provider": provider, "timeout_seconds": timeout_seconds},
        )


class RateLimitException(AIServiceException):
    """Raised when an AI provider rate limit is exceeded."""

    def __init__(self, provider: str, details: Optional[str] = None) -> None:
        super().__init__(
            message=f"Rate limit exceeded for AI provider '{provider}'. {details or ''}".strip(),
            status_code=429,
            details={"provider": provider, "error": details},
        )


class NetworkErrorException(AIServiceException):
    """Raised when a network communication error occurs with an AI provider."""

    def __init__(self, provider: str, details: str) -> None:
        super().__init__(
            message=f"Network error communicating with AI provider '{provider}': {details}",
            status_code=502,
            details={"provider": provider, "network_error": details},
        )


class ProviderErrorException(AIServiceException):
    """Raised when an AI provider returns an API error response."""

    def __init__(self, provider: str, error_message: str, status_code: int = 502) -> None:
        super().__init__(
            message=f"AI provider '{provider}' error: {error_message}",
            status_code=status_code,
            details={"provider": provider, "error_message": error_message},
        )


class InvalidModelException(AIServiceException):
    """Raised when an unsupported or invalid model is requested."""

    def __init__(self, model: str, provider: str) -> None:
        super().__init__(
            message=f"Model '{model}' is invalid or unsupported for provider '{provider}'.",
            status_code=400,
            details={"model": model, "provider": provider},
        )
