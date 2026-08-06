# schemas/automation.py
"""Pydantic v2 schemas for the Automation Engine.

This module defines all models required for task creation, execution,
status tracking, and health monitoring within the Brahmastra AI
automation pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AutomationStatus(str, Enum):
    """Enumeration of possible states for an automation task."""

    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AutomationPriority(str, Enum):
    """Priority levels for task scheduling."""

    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


# ---------------------------------------------------------------------------
# Automation Task (persistent record)
# ---------------------------------------------------------------------------


class AutomationTask(BaseModel):
    """Full representation of an automation task, including its lifecycle."""

    task_id: str = Field(
        ...,
        description="Unique identifier for the automation task.",
        examples=["task_4f8a1b2c3d"],
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human‑readable name of the task.",
        examples=["daily-data-sync"],
    )
    description: str = Field(
        "",
        description="Detailed description of what the task performs.",
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the task was created.",
    )
    updated_at: datetime | None = Field(
        None,
        description="UTC timestamp of the last status change.",
    )
    status: AutomationStatus = Field(
        ...,
        description="Current lifecycle status of the task.",
    )
    priority: AutomationPriority = Field(
        AutomationPriority.normal,
        description="Execution priority.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary data that the task carries for execution.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of tags for filtering and organisation.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Automation Execution Request (incoming API payload)
# ---------------------------------------------------------------------------


class AutomationExecutionRequest(BaseModel):
    """Request body to create and optionally trigger an automation task."""

    task_name: str = Field(
        ...,
        min_length=1,
        description="Human‑readable name for the task to be created.",
        examples=["daily-data-sync"],
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Data forwarded to the automation handler during execution.",
    )
    priority: AutomationPriority = Field(
        AutomationPriority.normal,
        description="Execution priority in the queue.",
    )
    timeout: int = Field(
        300,
        ge=1,
        le=3600,
        description="Maximum allowed execution time in seconds before the task is forcefully terminated.",
    )
    schedule: str | None = Field(
        None,
        description="Cron expression for recurring execution (e.g., '0 2 * * *').",
    )
    async_execution: bool = Field(
        False,
        description="If true, the API returns immediately and the task runs in the background.",
    )

    model_config = ConfigDict(
        strict=True,
    )

    @field_validator("schedule")
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        """Basic validation for a cron expression (must have five fields)."""
        if v is not None:
            parts = v.split()
            if len(parts) != 5:
                raise ValueError(
                    "Schedule must be a valid cron expression with exactly 5 fields"
                )
        return v

    @field_validator("task_name")
    @classmethod
    def validate_task_name(cls, v: str) -> str:
        """Ensure the task name contains only valid characters."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "task_name must contain only letters, numbers, underscores, or hyphens"
            )
        return v.strip()


# ---------------------------------------------------------------------------
# Automation Execution Response (immediate acknowledgement)
# ---------------------------------------------------------------------------


class AutomationExecutionResponse(BaseModel):
    """Response returned immediately after accepting an automation request."""

    task_id: str = Field(
        ...,
        description="Unique identifier assigned to the new task.",
    )
    status: AutomationStatus = Field(
        ...,
        description="Initial status of the task (typically 'pending' or 'queued').",
    )
    accepted: bool = Field(
        True,
        description="Whether the task was successfully accepted by the scheduler.",
    )
    message: str = Field(
        "Task accepted successfully",
        description="Human‑readable confirmation message.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the task was created.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Automation Result (final outcome)
# ---------------------------------------------------------------------------


class AutomationResult(BaseModel):
    """Final result of an automation task after completion or failure."""

    task_id: str = Field(
        ...,
        description="The identifier of the task this result belongs to.",
    )
    status: AutomationStatus = Field(
        ...,
        description="Final status of the task.",
    )
    started_at: datetime | None = Field(
        None,
        description="UTC timestamp when execution began.",
    )
    finished_at: datetime | None = Field(
        None,
        description="UTC timestamp when execution finished.",
    )
    execution_time_ms: float | None = Field(
        None,
        ge=0.0,
        description="Total wall‑clock execution time in milliseconds.",
    )
    result: Any = Field(
        None,
        description="Arbitrary result data produced by the task.",
    )
    logs: list[str] = Field(
        default_factory=list,
        description="Captured log lines from the task execution.",
    )
    error: str | None = Field(
        None,
        description="Error message if the task failed.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Automation List Response
# ---------------------------------------------------------------------------


class AutomationListResponse(BaseModel):
    """Envelope for listing automation tasks."""

    total: int = Field(
        ...,
        ge=0,
        description="Total number of tasks matching the query.",
    )
    tasks: list[AutomationTask] = Field(
        default_factory=list,
        description="Paginated list of automation tasks.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Automation Health
# ---------------------------------------------------------------------------


class AutomationHealth(BaseModel):
    """Health and workload statistics for the automation engine."""

    scheduler_running: bool = Field(
        ...,
        description="Whether the background scheduler is actively processing jobs.",
    )
    worker_count: int = Field(
        ...,
        ge=0,
        description="Number of active worker processes or threads.",
    )
    queued_jobs: int = Field(
        ...,
        ge=0,
        description="Number of jobs waiting in the queue.",
    )
    running_jobs: int = Field(
        ...,
        ge=0,
        description="Number of jobs currently executing.",
    )
    failed_jobs: int = Field(
        ...,
        ge=0,
        description="Count of jobs that have failed (since the last restart).",
    )
    completed_jobs: int = Field(
        ...,
        ge=0,
        description="Count of jobs that completed successfully (since the last restart).",
    )

    model_config = ConfigDict(
        strict=True,
    )
