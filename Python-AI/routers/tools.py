"""FastAPI router for tool discovery, metadata inspection, and execution."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from schemas.tool import (
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolListResponse,
    ToolSchema,
)
from services.executor import ToolExecutor
from services.registry_service import ToolRegistryService
from tools.registry import ToolNotFoundError

router = APIRouter()
registry_service = ToolRegistryService()
executor = ToolExecutor()


@router.get(
    "",
    response_model=ToolListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all registered tools",
    description="Returns schemas and metadata for all currently registered tools.",
)
@router.get(
    "/",
    response_model=ToolListResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@router.get(
    "/list",
    response_model=ToolListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all registered tools (alias)",
    include_in_schema=False,
)
async def list_tools() -> ToolListResponse:
    """Return the list of all registered tools."""
    return registry_service.list_tools()


@router.get(
    "/info/{tool_name}",
    response_model=ToolSchema,
    status_code=status.HTTP_200_OK,
    summary="Get tool metadata",
    description="Returns the full schema definition for a specific tool by name.",
)
async def get_tool_info(tool_name: str) -> ToolSchema:
    """Return metadata and schema for *tool_name*."""
    try:
        return registry_service.get_tool_info(tool_name)
    except ToolNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found.",
        ) from None


@router.post(
    "/execute",
    response_model=ToolExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a tool",
    description="Executes the specified tool with provided arguments and returns the result.",
)
async def execute_tool(request: ToolExecutionRequest) -> ToolExecutionResponse:
    """Execute a tool request and return the execution response."""
    response = executor.execute(request)
    return response
