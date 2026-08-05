# schemas/health.py
"""Health-check schema definitions for the Brahmastra AI API.

This module provides strongly‑typed models for liveness, readiness, and
comprehensive health endpoints.  The models are designed for use with
Kubernetes probes as well as custom monitoring dashboards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    """Enumeration of possible health states for components and the system."""

    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"


# ---------------------------------------------------------------------------
# Component Health
# ---------------------------------------------------------------------------


class ComponentHealth(BaseModel):
    """Health status of an individual application component (e.g., a database)."""

    name: str = Field(
        ...,
        description="Name of the component being checked.",
        examples=["PostgreSQL", "Redis", "LocalStorage"],
    )
    status: HealthStatus = Field(
        ...,
        description="Current health status of the component.",
        examples=[HealthStatus.healthy],
    )
    message: Optional[str] = Field(
        None,
        description="Human‑readable message providing additional detail.",
        examples=["Connection pool is stable"],
    )
    response_time_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="Response time of the health check in milliseconds.",
    )
    version: Optional[str] = Field(
        None,
        description="Version of the component (e.g., database server version).",
        examples=["14.3"],
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional data relevant to the component.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# System Health (host metrics)
# ---------------------------------------------------------------------------


class SystemHealth(BaseModel):
    """Host‑level resource utilisation metrics."""

    cpu_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="CPU usage percentage (0–100).",
        examples=[34.7],
    )
    memory_percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Memory usage percentage (0–100).",
        examples=[62.1],
    )
    disk_percent: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Disk usage percentage on the main volume (if applicable).",
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
# Dependency Health
# ---------------------------------------------------------------------------


class DependencyHealth(BaseModel):
    """Aggregated health of external dependencies.

    Each field represents a critical subsystem; if a dependency does not
    apply in the current deployment, its value may be ``None``.
    """

    database: Optional[ComponentHealth] = Field(
        None,
        description="Health of the primary database.",
    )
    storage: Optional[ComponentHealth] = Field(
        None,
        description="Health of the persistent storage layer.",
    )
    registry: Optional[ComponentHealth] = Field(
        None,
        description="Health of the tool/plugin registry.",
    )
    ai_engine: Optional[ComponentHealth] = Field(
        None,
        description="Health of the AI inference engine (if deployed).",
    )
    automation: Optional[ComponentHealth] = Field(
        None,
        description="Health of the automation service.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Comprehensive Health Check Response
# ---------------------------------------------------------------------------


class HealthCheckResponse(BaseModel):
    """Full health‑check response returned by ``/health``."""

    status: HealthStatus = Field(
        ...,
        description="Aggregate health status of the entire application.",
    )
    application_name: str = Field(
        ...,
        description="Name of the application.",
        examples=["Brahmastra AI"],
    )
    application_version: str = Field(
        ...,
        description="Semantic version of the running application.",
        examples=["0.1.0"],
    )
    environment: str = Field(
        ...,
        description="Current deployment environment.",
        examples=["production"],
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the health check was performed.",
    )
    request_id: Optional[str] = Field(
        None,
        description="Echo of the X-Request-ID header, if present.",
    )
    system: SystemHealth = Field(
        ...,
        description="Host‑level system metrics.",
    )
    dependencies: DependencyHealth = Field(
        ...,
        description="Status of critical external dependencies.",
    )
    components: List[ComponentHealth] = Field(
        default_factory=list,
        description="Detailed health status of all internal application components.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Readiness Probe Response
# ---------------------------------------------------------------------------


class ReadinessResponse(BaseModel):
    """Response returned by the ``/health/ready`` endpoint.

    Indicates whether the application is ready to accept traffic.
    Kubernetes readiness probes expect a 200‑status response; this model
    provides a standardised JSON body.
    """

    ready: bool = Field(
        ...,
        description="True when the application has completed startup and can serve requests.",
        examples=[True],
    )
    message: Optional[str] = Field(
        None,
        description="Human‑readable description of the readiness state.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Liveness Probe Response
# ---------------------------------------------------------------------------


class LivenessResponse(BaseModel):
    """Response returned by the ``/health/live`` endpoint.

    Indicates whether the application is still running.  Kubernetes
    liveness probes expect a 200‑status response; this model provides a
    standardised JSON body.
    """

    alive: bool = Field(
        ...,
        description="True while the application is alive and has not deadlocked.",
        examples=[True],
    )

    model_config = ConfigDict(
        strict=True,
    )