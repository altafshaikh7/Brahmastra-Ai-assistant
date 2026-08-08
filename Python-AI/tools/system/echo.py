"""Echo tool – returns whatever text is sent to it."""

from __future__ import annotations

from typing import Any

from schemas.tool import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from tools.base_tool import BaseTool


class EchoTool(BaseTool):
    """Echoes the *message* argument back to the caller."""

    tool_schema = ToolSchema(
        name="echo",
        display_name="Echo",
        description="Returns the provided message unchanged. Useful for testing the tool pipeline.",
        parameters=[
            ToolParameter(
                name="message",
                type=ToolParameterType.string,
                required=True,
                description="Text to echo back.",
                example="Hello, world!",
            ),
        ],
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.system,
            tags=["system", "test", "echo"],
        ),
    )

    def execute(self, **kwargs: Any) -> dict[str, str]:
        message: str = str(kwargs.get("message", ""))
        return {"echo": message}


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = EchoTool()
