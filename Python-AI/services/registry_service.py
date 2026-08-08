"""Service wrapper around ToolRegistry for discovery, metadata, and health status."""

from __future__ import annotations

import logging

from schemas.tool import ToolHealth, ToolListResponse, ToolSchema
from tools.registry import ToolNotFoundError, ToolRegistry

logger = logging.getLogger(__name__)


class ToolRegistryService:
    """Service providing discovery, schema lookup, and health status for registered tools.

    Usage::

        service = ToolRegistryService()
        tools_list = service.list_tools()
        schema = service.get_tool_info("calculator")
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry.get_instance()

    def list_tools(self) -> ToolListResponse:
        """Return a :class:`ToolListResponse` containing all registered tools."""
        schemas = self._registry.list_tools()
        return ToolListResponse(total=len(schemas), tools=schemas)

    def get_tool_info(self, name: str) -> ToolSchema:
        """Return the :class:`ToolSchema` for the specified tool name.

        Raises :class:`ToolNotFoundError` if the tool is not registered.
        """
        tool = self._registry.get(name)
        return tool.tool_schema

    def get_health(self, name: str) -> ToolHealth:
        """Return health metadata for the specified tool.

        Raises :class:`ToolNotFoundError` if the tool is not registered.
        """
        tool = self._registry.get(name)
        return ToolHealth(
            tool_name=tool.name,
            status="healthy",
            last_execution=None,
            average_execution_time=None,
        )

    def list_health(self) -> list[ToolHealth]:
        """Return health status for all registered tools."""
        health_list: list[ToolHealth] = []
        for name in self._registry.list_names():
            try:
                health_list.append(self.get_health(name))
            except ToolNotFoundError:
                continue
        return health_list
