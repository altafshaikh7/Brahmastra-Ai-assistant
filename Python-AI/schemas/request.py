# schemas/request.py
"""Pydantic v2 request schemas for the Brahmastra AI API.

This module defines all incoming request bodies and query parameters as
strongly‑typed, validated models.  Every request model inherits from a
common ``BaseRequest`` that carries optional metadata (request ID,
timestamp) for traceability.

The design follows enterprise best practices:
- Strict validation with ``ConfigDict`` and field validators.
- Rich documentation with examples for OpenAPI generation.
- Reusable pagination and search primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Type variable for generic models
# ---------------------------------------------------------------------------

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Base Request
# ---------------------------------------------------------------------------


class BaseRequest(BaseModel):
    """Common optional metadata for incoming requests.

    These fields are typically populated by middleware (e.g., request ID
    is injected from the ``X-Request-ID`` header) but can also be set
    explicitly by clients for tracing.
    """

    request_id: Optional[str] = Field(
        None,
        description="Unique identifier for the request (echoed back in the response).",
        examples=["req_abc123"],
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key‑value pairs attached by the client for observability.",
    )
    timestamp: Optional[datetime] = Field(
        None,
        description="Client‑supplied timestamp; defaults to now if omitted.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
        strict=True,
    )


# ---------------------------------------------------------------------------
# Health Request
# ---------------------------------------------------------------------------


class HealthRequest(BaseRequest):
    """Request body for the ``/health`` endpoint (optional)."""

    include_details: bool = Field(
        False,
        description="If true, the response includes deeper system checks.",
    )


# ---------------------------------------------------------------------------
# Tool Execute Request
# ---------------------------------------------------------------------------


class ToolExecuteRequest(BaseRequest):
    """Payload to trigger execution of a registered tool.

    The tool is identified by ``tool_name`` and executed with the given
    ``arguments``.  Clients may specify a ``timeout`` and whether to run
    the tool asynchronously.
    """

    tool_name: str = Field(
        ...,
        min_length=1,
        description="Name of the tool to execute (must be registered).",
        examples=["ping", "echo"],
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments passed to the tool.",
        examples=[{"host": "127.0.0.1"}],
    )
    timeout: int = Field(
        30,
        ge=1,
        le=300,
        description="Maximum execution time in seconds before the process is terminated.",
    )
    async_execution: bool = Field(
        False,
        description="If true, the request returns immediately and the task runs in the background.",
    )

    @field_validator("tool_name")
    @classmethod
    def tool_name_must_be_valid(cls, v: str) -> str:
        """Ensure the tool name contains only permitted characters."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("tool_name must contain only letters, numbers, underscores, or hyphens")
        return v.strip()


# ---------------------------------------------------------------------------
# Automation Request
# ---------------------------------------------------------------------------


class AutomationRequest(BaseRequest):
    """Request to create or trigger an automation task."""

    task_name: str = Field(
        ...,
        min_length=1,
        description="Human‑readable name of the automation task.",
        examples=["daily-backup"],
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary data forwarded to the automation handler.",
    )
    schedule: Optional[str] = Field(
        None,
        description="Cron expression for recurring execution (e.g., '0 2 * * *').",
    )
    priority: Literal["low", "normal", "high", "critical"] = Field(
        "normal",
        description="Priority of the task in the execution queue.",
    )
    retry_count: int = Field(
        0,
        ge=0,
        le=10,
        description="Number of automatic retries on failure before giving up.",
    )

    @field_validator("schedule")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        """Basic validation for cron expressions (five fields)."""
        if v is not None:
            parts = v.split()
            if len(parts) != 5:
                raise ValueError("Schedule must be a valid cron expression with exactly 5 fields")
        return v


# ---------------------------------------------------------------------------
# Pagination Request (for query parameters)
# ---------------------------------------------------------------------------


class PaginationRequest(BaseModel):
    """Re‑usable pagination parameters.

    Intended to be used as a dependency or inside other request models.
    """

    page: int = Field(
        1,
        ge=1,
        description="Page number (1‑based).",
    )
    page_size: int = Field(
        20,
        ge=1,
        le=100,
        description="Number of items per page.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Search Request
# ---------------------------------------------------------------------------


class SearchRequest(BaseRequest):
    """Generic search request with filtering, sorting, and pagination."""

    query: str = Field(
        "",
        description="Free‑text search query.",
        examples=["Brahmastra AI"],
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key‑value pairs for exact or range filtering.",
        examples=[{"status": "active", "created_after": "2024-01-01"}],
    )
    sort: Optional[str] = Field(
        None,
        description="Field to sort by, optionally prefixed with '-' for descending order.",
        examples=["-created_at", "name"],
    )
    limit: int = Field(
        20,
        ge=1,
        le=200,
        description="Maximum number of items to return (used instead of page/page_size when simpler).",
    )
    offset: int = Field(
        0,
        ge=0,
        description="Number of items to skip before returning results.",
    )


# ---------------------------------------------------------------------------
# Batch Request (generic)
# ---------------------------------------------------------------------------


class BatchRequest(BaseRequest, Generic[T]):
    """Envelope for batch operations.

    The ``items`` list carries the domain‑specific request payloads.
    """

    items: List[T] = Field(
        ...,
        min_length=1,
        description="List of items to process in a single batch.",
    )

    model_config = ConfigDict(
        arbitrary_types_allowed=False,
        strict=True,
    )