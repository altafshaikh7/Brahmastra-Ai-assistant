"""Tool registry – manages registration and retrieval of BaseTool instances."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TYPE_CHECKING

from schemas.tool import ToolSchema

if TYPE_CHECKING:
    from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ToolNotFoundError(KeyError):
    """Raised when a requested tool is not in the registry."""


class DuplicateToolError(ValueError):
    """Raised when a tool with the same name is registered twice."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Singleton registry that stores and exposes :class:`~tools.base_tool.BaseTool`
    instances.

    Usage::

        registry = ToolRegistry.get_instance()
        registry.register(my_tool_instance)
        tool = registry.get("my_tool")
    """

    _instance: ToolRegistry | None = None

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        """Return the process-wide singleton instance, creating it if needed."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._auto_register_builtins()
        return cls._instance

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register *tool* in the registry.

        Raises :class:`DuplicateToolError` if a tool with the same name has
        already been registered.
        """
        name = tool.name
        if name in self._tools:
            raise DuplicateToolError(
                f"A tool named '{name}' is already registered. "
                "Use replace() to override it explicitly."
            )
        self._tools[name] = tool
        logger.debug("Registered tool: %s", name)

    def replace(self, tool: BaseTool) -> None:
        """Register *tool*, overwriting any existing entry with the same name."""
        self._tools[tool.name] = tool
        logger.debug("Replaced tool: %s", tool.name)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseTool:
        """Return the tool registered under *name*.

        Raises :class:`ToolNotFoundError` if not found.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(
                f"Tool '{name}' is not registered. "
                f"Available tools: {list(self._tools.keys())}"
            ) from None

    def list_tools(self) -> list[ToolSchema]:
        """Return a list of :class:`~schemas.tool.ToolSchema` for all registered tools."""
        return [tool.tool_schema for tool in self._tools.values()]

    def list_names(self) -> list[str]:
        """Return the names of all registered tools."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    # ------------------------------------------------------------------
    # Auto-discovery of built-in tools
    # ------------------------------------------------------------------

    def _auto_register_builtins(self) -> None:
        """Discover and register all tools in the ``tools.system`` package."""
        import tools.system as system_pkg

        for module_info in pkgutil.iter_modules(system_pkg.__path__):
            module_name = f"tools.system.{module_info.name}"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                logger.exception("Failed to import tool module: %s", module_name)
                continue

            # Each tool module is expected to expose a ``tool`` singleton.
            tool_instance = getattr(module, "tool", None)
            if tool_instance is None:
                logger.debug("No 'tool' attribute in %s; skipping.", module_name)
                continue

            from tools.base_tool import BaseTool as _BaseTool

            if not isinstance(tool_instance, _BaseTool):
                logger.warning(
                    "tools.system.%s.tool is not a BaseTool instance; skipping.",
                    module_info.name,
                )
                continue

            try:
                self.register(tool_instance)
            except DuplicateToolError:
                logger.warning("Duplicate tool skipped: %s", tool_instance.name)
