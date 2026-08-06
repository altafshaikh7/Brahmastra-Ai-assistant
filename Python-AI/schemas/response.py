# schemas/response.py
"""Pydantic v2 response schemas for the Brahmastra AI API.

This module defines consistent, strongly‑typed response models used
across all endpoints.  Every response inherits from a common base model
that includes metadata (timestamp, request ID) to support observability
and traceability.

The models follow enterprise best practices:
- Strict validation with ``model_config``.
- JSON‑serializable defaults for optional fields.
- Generic variants where applicable (e.g., ``SuccessResponse``,
  ``PaginatedResponse``) for maximum reusability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Type variable for generic response payloads
# ---------------------------------------------------------------------------

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Base Response
# ---------------------------------------------------------------------------


class BaseResponse(BaseModel):
    """Common metadata included in every API response."""

    request_id: str | None = Field(
        None,
        description="Echo of the X-Request-ID header, if present.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the response was generated.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
        strict=True,
    )


# ---------------------------------------------------------------------------
# Generic Success Response
# ---------------------------------------------------------------------------


class SuccessResponse(BaseResponse, Generic[T]):
    """Standard envelope for successful API operations.

    The ``data`` field holds the domain‑specific payload and is typed
    according to the route's contract.
    """

    message: str = Field(
        "OK",
        description="Human‑readable success message.",
    )
    data: T = Field(
        ...,
        description="Domain payload returned by the operation.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=False,
        strict=True,
    )


# ---------------------------------------------------------------------------
# Error Response
# ---------------------------------------------------------------------------


class ErrorResponse(BaseResponse):
    """Standard error envelope returned for all handled exceptions."""

    error: str = Field(
        ...,
        description="Short error identifier (e.g., 'Validation Error').",
    )
    detail: Any = Field(
        None,
        description="Detailed information about the error (Pydantic errors, str, etc.).",
    )
    error_code: str | None = Field(
        None,
        description="Machine‑readable error code for automated handling.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Paginated Response
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseResponse, Generic[T]):
    """Envelope for paginated collections."""

    items: list[T] = Field(
        ...,
        description="List of items for the current page.",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of items across all pages.",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number (1‑based).",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Number of items per page.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Health Check Response
# ---------------------------------------------------------------------------


class HealthResponse(BaseResponse):
    """Detailed health status returned by the ``/health`` endpoint."""

    status: str = Field(
        "healthy",
        description="Overall health status (healthy, degraded, unhealthy).",
    )
    version: str = Field(
        ...,
        description="Current application version.",
    )
    uptime_seconds: float = Field(
        ...,
        ge=0.0,
        description="Process uptime in seconds.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Tool Execution Response
# ---------------------------------------------------------------------------


class ToolResponse(BaseResponse):
    """Response returned after executing a registered tool."""

    tool_name: str = Field(
        ...,
        description="Name of the executed tool.",
    )
    success: bool = Field(
        ...,
        description="Indicates whether the tool completed without error.",
    )
    output: Any = Field(
        None,
        description="Stdout or primary result from the tool.",
    )
    exit_code: int | None = Field(
        None,
        description="Process exit code (if applicable).",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Automation Response
# ---------------------------------------------------------------------------


class AutomationResponse(BaseResponse):
    """Response returned when an automation job is triggered."""

    task_id: str = Field(
        ...,
        description="Unique identifier for the automation task.",
    )
    status: str = Field(
        "accepted",
        description="Current status of the automation job.",
    )
    result: Any | None = Field(
        None,
        description="Result payload once the job completes.",
    )

    model_config = ConfigDict(
        strict=True,
    )
