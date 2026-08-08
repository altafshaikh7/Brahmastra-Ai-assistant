"""Ping tool – checks reachability of a host using platform ping command."""

from __future__ import annotations

import platform
import subprocess
from typing import Any

from schemas.tool import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from tools.base_tool import BaseTool


class PingTool(BaseTool):
    """Sends ICMP echo requests to a target host and returns reachability info."""

    tool_schema = ToolSchema(
        name="ping",
        display_name="Network Ping",
        description=(
            "Sends ICMP Echo Request packets to a target host and reports "
            "whether it is reachable."
        ),
        parameters=[
            ToolParameter(
                name="host",
                type=ToolParameterType.string,
                required=True,
                description="Hostname or IP address to ping.",
                example="8.8.8.8",
            ),
            ToolParameter(
                name="count",
                type=ToolParameterType.integer,
                required=False,
                default=3,
                description="Number of echo requests to send (1–10).",
                example=3,
            ),
        ],
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.network,
            tags=["network", "ping", "diagnostics"],
        ),
    )

    # Maximum allowed ping count to prevent abuse.
    _MAX_COUNT = 10

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        host: str = str(kwargs.get("host", "")).strip()
        if not host:
            return {"success": False, "error": "host is required"}

        count = int(kwargs.get("count", 3))
        count = max(1, min(count, self._MAX_COUNT))

        cmd = self._build_command(host, count)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            success = result.returncode == 0
            return {
                "success": success,
                "host": host,
                "count": count,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "host": host, "error": "ping timed out"}
        except FileNotFoundError:
            return {"success": False, "host": host, "error": "ping command not found"}

    @staticmethod
    def _build_command(host: str, count: int) -> list[str]:
        if platform.system().lower() == "windows":
            return ["ping", "-n", str(count), host]
        return ["ping", "-c", str(count), host]


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = PingTool()
