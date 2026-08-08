"""Abstract base class for all Brahmastra AI tools."""

from __future__ import annotations

import abc
from typing import Any

from schemas.tool import ToolParameter, ToolSchema


class BaseTool(abc.ABC):
    """Abstract base class for all tools.

    Subclasses must define a ``tool_schema`` class attribute describing the
    tool (name, display_name, description, parameters, metadata) and must
    implement :meth:`execute`.
    """

    tool_schema: ToolSchema

    # ------------------------------------------------------------------
    # Convenience properties (delegate to tool_schema)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Unique internal name of the tool."""
        return self.tool_schema.name

    @property
    def display_name(self) -> str:
        """Human-friendly display name."""
        return self.tool_schema.display_name

    @property
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        return self.tool_schema.description

    @property
    def parameters(self) -> dict[str, ToolParameter]:
        """Mapping of parameter name → ToolParameter for this tool."""
        return {p.name: p for p in self.tool_schema.parameters}

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the supplied keyword arguments.

        ``kwargs`` are validated by the caller against ``self.parameters``
        before this method is invoked. The return value **must** be
        JSON-serialisable.
        """
