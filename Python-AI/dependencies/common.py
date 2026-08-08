# dependencies/common.py
"""Reusable FastAPI dependencies for common request‑level information.

This module provides small, composable dependency callables that extract
metadata from the incoming HTTP request (request ID, IP, user agent) as
well as standard query‑parameter parsing (pagination, search, sorting).

All dependencies return validated Pydantic models or simple types,
making them easy to compose and test.
"""

from __future__ import annotations

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017
from typing import Annotated, Literal

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from schemas.request import PaginationRequest

# ---------------------------------------------------------------------------
# Local helper models
# ---------------------------------------------------------------------------


class SearchQueryParams(BaseModel):
    """Structured representation of common search query parameters."""

    query: str = Field(
        default="",
        description="Free‑text search query.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of items to return.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip before returning results.",
    )
    sort: str | None = Field(
        default=None,
        description="Field to sort by, optionally prefixed with '-' for descending order.",
    )

    model_config = ConfigDict(strict=True)


class SortingParams(BaseModel):
    """Sort specification extracted from query parameters."""

    sort_by: str | None = Field(
        default=None,
        description="Field name to sort on.",
    )
    order: Literal["asc", "desc"] = Field(
        default="asc",
        description="Sort direction.",
    )

    model_config = ConfigDict(strict=True)


class RequestContext(BaseModel):
    """Aggregation of common request metadata."""

    request_id: str | None
    client_ip: str
    user_agent: str | None
    timestamp: datetime

    model_config = ConfigDict(strict=True)


# ---------------------------------------------------------------------------
# Dependency functions
# ---------------------------------------------------------------------------


def get_request_id(request: Request) -> str | None:
    """Extract the request ID set by the ``request_id_middleware``."""
    return getattr(request.state, "request_id", None)


def get_client_ip(
    request: Request,
    x_forwarded_for: Annotated[str | None, Header(alias="X-Forwarded-For")] = None,
) -> str:
    """Return the client IP address, respecting the ``X-Forwarded-For`` header.

    If the header is present, the left‑most IP is returned; otherwise the
    direct client IP from the transport is used.
    """
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> str | None:
    """Extract the ``User-Agent`` header from the request."""
    return user_agent


def get_pagination(
    page: Annotated[int, Query(ge=1, description="Page number (1‑based).")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page.")] = 20,
) -> PaginationRequest:
    """Return a validated :class:`PaginationRequest` from query parameters."""
    return PaginationRequest(page=page, page_size=page_size)


def get_search_parameters(
    query: Annotated[str, Query(description="Free‑text search query.")] = "",
    limit: Annotated[int, Query(ge=1, le=200, description="Max items returned.")] = 20,
    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0,
    sort: Annotated[
        str | None,
        Query(
            description="Sort field, prefix with '-' for descending.",
        ),
    ] = None,
) -> SearchQueryParams:
    """Aggregate search query parameters into a validated model."""
    return SearchQueryParams(query=query, limit=limit, offset=offset, sort=sort)


def get_sorting(
    sort_by: Annotated[
        str | None,
        Query(description="Field name to sort on."),
    ] = None,
    order: Annotated[
        Literal["asc", "desc"],
        Query(description="Sort direction (asc or desc)."),
    ] = "asc",
) -> SortingParams:
    """Return a validated :class:`SortingParams` model."""
    return SortingParams(sort_by=sort_by, order=order)


def get_request_context(
    request_id: str | None = Depends(get_request_id),
    client_ip: str = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
) -> RequestContext:
    """Aggregate request metadata into a single ``RequestContext`` object."""
    return RequestContext(
        request_id=request_id,
        client_ip=client_ip,
        user_agent=user_agent,
        timestamp=datetime.now(UTC),
    )


def get_current_timestamp() -> datetime:
    """Return the current UTC timestamp.

    Useful as a dependency to inject a consistent timestamp across
    multiple parts of a single request (the timestamp is generated
    each time the dependency is resolved).
    """
    return datetime.now(UTC)
