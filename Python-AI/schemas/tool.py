# schemas/tool.py
"""Pydantic v2 schemas for the Tool Registry and execution pipeline.

This module defines all models related to tool metadata, registration,
execution, and health, providing a consistent contract for both the API
and internal services.
"""

from __future__ import annotations

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ToolParameterType(str, Enum):
    """Supported data types for tool parameters."""

    string = "string"
    integer = "integer"
    float = "float"
    boolean = "boolean"
    json = "json"
    file = "file"


class ToolCategory(str, Enum):
    """Pre‑defined categories for organising tools."""

    system = "system"
    network = "network"
    file_operations = "file_operations"
    data_processing = "data_processing"
    automation = "automation"
    custom = "custom"


# ---------------------------------------------------------------------------
# Tool Parameter
# ---------------------------------------------------------------------------


class ToolParameter(BaseModel):
    """Description of a single parameter accepted by a tool."""

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the parameter (e.g., 'host', 'port').",
        examples=["host"],
    )
    type: ToolParameterType = Field(
        ...,
        description="Expected data type of the parameter.",
        examples=[ToolParameterType.string],
    )
    required: bool = Field(
        False,
        description="Whether the parameter is mandatory.",
    )
    default: Any | None = Field(
        None,
        description="Default value if the parameter is not provided.",
    )
    description: str = Field(
        "",
        description="Human‑readable explanation of the parameter's purpose.",
        examples=["Target hostname or IP address."],
    )
    example: Any | None = Field(
        None,
        description="Example value for documentation purposes.",
    )

    model_config = ConfigDict(
        strict=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


# ---------------------------------------------------------------------------
# Tool Metadata
# ---------------------------------------------------------------------------


class ToolMetadata(BaseModel):
    """Metadata describing the origin and classification of a tool."""

    author: str = Field(
        "Brahmastra AI",
        description="Author or maintainer of the tool.",
    )
    version: str = Field(
        "1.0.0",
        description="Semantic version of the tool implementation.",
        examples=["1.2.3"],
    )
    category: ToolCategory = Field(
        ToolCategory.custom,
        description="Category under which the tool is grouped.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of tags for filtering and discovery.",
        examples=[["network", "diagnostics"]],
    )
    documentation_url: str | None = Field(
        None,
        description="URL to the tool's full documentation.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Tool Schema (full definition)
# ---------------------------------------------------------------------------


class ToolSchema(BaseModel):
    """Complete schema defining a tool's interface and metadata."""

    name: str = Field(
        ...,
        min_length=1,
        description="Unique internal name of the tool.",
        examples=["ping"],
    )
    display_name: str = Field(
        ...,
        min_length=1,
        description="Human‑friendly name for UI presentation.",
        examples=["Network Ping"],
    )
    description: str = Field(
        "",
        description="Detailed description of what the tool does.",
        examples=["Sends ICMP Echo Request packets to a target host."],
    )
    parameters: list[ToolParameter] = Field(
        default_factory=list,
        description="List of parameters the tool accepts.",
    )
    metadata: ToolMetadata = Field(
        default_factory=ToolMetadata,
        description="Additional classification and versioning information.",
    )

    model_config = ConfigDict(
        strict=True,
    )

    @field_validator("name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure the tool name uses only permitted characters."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Tool name must contain only letters, numbers, underscores, or hyphens"
            )
        return v.strip()


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------


class ToolRegistration(BaseModel):
    """Record of a tool that has been registered in the system."""

    tool_id: str = Field(
        ...,
        description="Unique identifier assigned to the tool upon registration.",
    )
    enabled: bool = Field(
        True,
        description="Whether the tool is currently available for execution.",
    )
    loaded: bool = Field(
        False,
        description="Whether the tool's implementation has been loaded into memory.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the tool was registered.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Tool Execution Request
# ---------------------------------------------------------------------------


class ToolExecutionRequest(BaseModel):
    """Payload to execute a tool, as used by internal services."""

    tool_name: str = Field(
        ...,
        min_length=1,
        description="Name of the tool to execute.",
        examples=["ping"],
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments passed to the tool's execute method.",
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

    model_config = ConfigDict(
        strict=True,
    )

    @field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Ensure the tool name contains only valid characters."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Tool name must contain only letters, numbers, underscores, or hyphens"
            )
        return v.strip()


# ---------------------------------------------------------------------------
# Tool Execution Response
# ---------------------------------------------------------------------------


class ToolExecutionResponse(BaseModel):
    """Result of a tool execution returned by the service."""

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
    execution_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Wall‑clock execution time in milliseconds.",
    )
    exit_code: int | None = Field(
        None,
        description="Process exit code if the tool was executed as a subprocess.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when execution completed.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )


# ---------------------------------------------------------------------------
# Tool List Response
# ---------------------------------------------------------------------------


class ToolListResponse(BaseModel):
    """Envelope for listing registered tools."""

    total: int = Field(
        ...,
        ge=0,
        description="Total number of registered tools.",
    )
    tools: list[ToolSchema] = Field(
        default_factory=list,
        description="List of tool schemas currently available.",
    )

    model_config = ConfigDict(
        strict=True,
    )


# ---------------------------------------------------------------------------
# Tool Health
# ---------------------------------------------------------------------------


class ToolHealth(BaseModel):
    """Health status of an individual tool within the registry."""

    tool_name: str = Field(
        ...,
        description="Name of the tool.",
    )
    status: str = Field(
        ...,
        description="Current health status (e.g., 'healthy', 'error').",
        examples=["healthy"],
    )
    last_execution: datetime | None = Field(
        None,
        description="UTC timestamp of the tool's last execution.",
    )
    average_execution_time: float | None = Field(
        None,
        ge=0.0,
        description="Rolling average execution time in milliseconds.",
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        strict=True,
    )
