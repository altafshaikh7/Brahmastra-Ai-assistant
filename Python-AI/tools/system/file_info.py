"""File-info tool – returns file/directory metadata safely within a sandboxed root."""

from __future__ import annotations

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017

from pathlib import Path
from typing import Any

from core.config import get_settings
from schemas.tool import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from tools.base_tool import BaseTool


class FileInfoError(ValueError):
    """Raised when a file path is invalid or outside the allowed root directory."""


def _get_sandboxed_path(path_str: str, root_path: Path | None = None) -> Path:
    """Resolve *path_str* and enforce that it remains strictly inside *root_path*.

    Raises :class:`FileInfoError` if the path escapes the allowed root directory.
    """
    if root_path is None:
        try:
            root_path = get_settings().tool_root_path
        except Exception:
            root_path = Path.cwd()

    root_path = root_path.resolve()

    raw_path = Path(path_str)
    if not raw_path.is_absolute():
        target_path = (root_path / raw_path).resolve()
    else:
        target_path = raw_path.resolve()

    try:
        target_path.relative_to(root_path)
    except ValueError:
        raise FileInfoError(
            f"Access denied: path '{path_str}' is outside the allowed root directory '{root_path}'."
        ) from None

    return target_path


class FileInfoTool(BaseTool):
    """Retrieves file or directory metadata safely within the allowed root directory."""

    tool_schema = ToolSchema(
        name="file_info",
        display_name="File Information",
        description=(
            "Retrieves file or directory metadata (size, timestamps, permissions, "
            "file/directory status) within the allowed workspace root directory. "
            "Does not read or expose file contents."
        ),
        parameters=[
            ToolParameter(
                name="path",
                type=ToolParameterType.string,
                required=True,
                description="Relative or absolute path within the workspace root.",
                example="storage/logs/app.log",
            ),
        ],
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.file_operations,
            tags=["file", "filesystem", "metadata", "info"],
        ),
    )

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        path_str: str = str(kwargs.get("path", "")).strip()
        if not path_str:
            return {"success": False, "error": "path parameter is required"}

        root_override = kwargs.get("root_path")
        custom_root = Path(root_override) if root_override else None

        try:
            target_path = _get_sandboxed_path(path_str, root_path=custom_root)
        except FileInfoError as exc:
            return {
                "success": False,
                "path": path_str,
                "error": str(exc),
            }

        if not target_path.exists():
            return {
                "success": False,
                "path": str(target_path),
                "error": "File or directory does not exist.",
            }

        try:
            stat = target_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
            ctime = datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat()

            return {
                "success": True,
                "name": target_path.name,
                "path": str(target_path),
                "is_file": target_path.is_file(),
                "is_directory": target_path.is_dir(),
                "is_symlink": target_path.is_symlink(),
                "size_bytes": stat.st_size if target_path.is_file() else 0,
                "extension": (
                    target_path.suffix.lower() if target_path.is_file() else ""
                ),
                "modified_time_utc": mtime,
                "created_time_utc": ctime,
            }
        except OSError as exc:
            return {
                "success": False,
                "path": str(target_path),
                "error": f"Failed to inspect path: {exc}",
            }


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = FileInfoTool()
