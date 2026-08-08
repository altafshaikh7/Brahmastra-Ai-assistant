"""Current-time tool – returns the current timezone-aware UTC timestamp."""

from __future__ import annotations

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

from typing import Any

from schemas.tool import ToolCategory, ToolMetadata, ToolSchema
from tools.base_tool import BaseTool


class CurrentTimeTool(BaseTool):
    """Returns the current UTC date and time as a timezone-aware ISO-8601 string."""

    tool_schema = ToolSchema(
        name="current_time",
        display_name="Current Time",
        description=(
            "Returns the current date and time in ISO-8601 format "
            "(timezone-aware, UTC). Example output: '2024-01-15T10:30:00+00:00'."
        ),
        parameters=[],  # No parameters required.
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.system,
            tags=["time", "datetime", "clock", "utc"],
        ),
    )

    def execute(self, **kwargs: Any) -> dict[str, str]:
        now = datetime.now(tz=UTC)
        return {
            "utc": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timestamp_unix": str(int(now.timestamp())),
        }


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = CurrentTimeTool()
