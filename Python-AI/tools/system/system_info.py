"""System-info tool – returns OS and runtime metadata."""

from __future__ import annotations

import platform
import sys
from typing import Any

from schemas.tool import ToolCategory, ToolMetadata, ToolSchema
from tools.base_tool import BaseTool


class SystemInfoTool(BaseTool):
    """Returns information about the host operating system and Python runtime."""

    tool_schema = ToolSchema(
        name="system_info",
        display_name="System Info",
        description=(
            "Returns metadata about the host operating system and Python "
            "interpreter (OS name, version, architecture, Python version, etc.)."
        ),
        parameters=[],  # No parameters required.
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.system,
            tags=["system", "diagnostics", "info"],
        ),
    )

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        uname = platform.uname()
        return {
            "os": uname.system,
            "os_release": uname.release,
            "os_version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
            "node": uname.node,
            "python_version": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
        }


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = SystemInfoTool()
