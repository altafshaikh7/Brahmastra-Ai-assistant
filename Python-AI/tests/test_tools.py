"""Tests for BaseTool, ToolRegistry, and built-in system tools."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from schemas.tool import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from tools.base_tool import BaseTool
from tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry
from tools.system.calculator import CalculatorError, CalculatorTool, safe_eval
from tools.system.current_time import CurrentTimeTool
from tools.system.echo import EchoTool
from tools.system.file_info import FileInfoTool, _get_sandboxed_path
from tools.system.ping import PingTool
from tools.system.system_info import SystemInfoTool

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class _AddTool(BaseTool):
    """Minimal concrete tool used for registry tests."""

    tool_schema = ToolSchema(
        name="test_add",
        display_name="Test Add",
        description="Adds two integers.",
        parameters=[
            ToolParameter(name="a", type=ToolParameterType.integer, required=True),
            ToolParameter(name="b", type=ToolParameterType.integer, required=True),
        ],
        metadata=ToolMetadata(category=ToolCategory.custom),
    )

    def execute(self, **kwargs: Any) -> dict[str, int]:  # type: ignore[override]
        return {"result": int(kwargs["a"]) + int(kwargs["b"])}


@pytest.fixture()
def fresh_registry() -> ToolRegistry:
    """Return a brand-new ToolRegistry (not the singleton) for isolation."""
    return ToolRegistry()


@pytest.fixture()
def add_tool() -> _AddTool:
    return _AddTool()


# ---------------------------------------------------------------------------
# BaseTool
# ---------------------------------------------------------------------------


class TestBaseTool:
    def test_name_delegates_to_schema(self, add_tool: _AddTool) -> None:
        assert add_tool.name == "test_add"

    def test_display_name_delegates(self, add_tool: _AddTool) -> None:
        assert add_tool.display_name == "Test Add"

    def test_description_delegates(self, add_tool: _AddTool) -> None:
        assert add_tool.description == "Adds two integers."

    def test_parameters_returns_mapping(self, add_tool: _AddTool) -> None:
        params = add_tool.parameters
        assert "a" in params
        assert "b" in params
        assert params["a"].type == ToolParameterType.integer

    def test_execute_returns_correct_result(self, add_tool: _AddTool) -> None:
        result = add_tool.execute(a=3, b=4)
        assert result == {"result": 7}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_register_and_get(
        self, fresh_registry: ToolRegistry, add_tool: _AddTool
    ) -> None:
        fresh_registry.register(add_tool)
        assert fresh_registry.get("test_add") is add_tool

    def test_list_names_includes_registered(
        self, fresh_registry: ToolRegistry, add_tool: _AddTool
    ) -> None:
        fresh_registry.register(add_tool)
        assert "test_add" in fresh_registry.list_names()

    def test_list_tools_returns_schemas(
        self, fresh_registry: ToolRegistry, add_tool: _AddTool
    ) -> None:
        fresh_registry.register(add_tool)
        schemas = fresh_registry.list_tools()
        assert any(s.name == "test_add" for s in schemas)

    def test_len(self, fresh_registry: ToolRegistry, add_tool: _AddTool) -> None:
        assert len(fresh_registry) == 0
        fresh_registry.register(add_tool)
        assert len(fresh_registry) == 1

    def test_contains(self, fresh_registry: ToolRegistry, add_tool: _AddTool) -> None:
        fresh_registry.register(add_tool)
        assert "test_add" in fresh_registry
        assert "nonexistent" not in fresh_registry

    def test_duplicate_registration_raises(
        self, fresh_registry: ToolRegistry, add_tool: _AddTool
    ) -> None:
        fresh_registry.register(add_tool)
        with pytest.raises(DuplicateToolError):
            fresh_registry.register(add_tool)

    def test_replace_overwrites(
        self, fresh_registry: ToolRegistry, add_tool: _AddTool
    ) -> None:
        fresh_registry.register(add_tool)
        new_instance = _AddTool()
        fresh_registry.replace(new_instance)
        assert fresh_registry.get("test_add") is new_instance

    def test_get_unknown_raises_not_found(self, fresh_registry: ToolRegistry) -> None:
        with pytest.raises(ToolNotFoundError):
            fresh_registry.get("ghost_tool")

    def test_singleton_contains_builtins(self) -> None:
        registry = ToolRegistry.get_instance()
        names = registry.list_names()
        assert "echo" in names
        assert "ping" in names
        assert "system_info" in names
        assert "calculator" in names
        assert "current_time" in names
        assert "file_info" in names


# ---------------------------------------------------------------------------
# EchoTool
# ---------------------------------------------------------------------------


class TestEchoTool:
    def test_name(self) -> None:
        assert EchoTool().name == "echo"

    def test_execute_returns_message(self) -> None:
        result = EchoTool().execute(message="hello")
        assert result == {"echo": "hello"}

    def test_execute_empty_string(self) -> None:
        result = EchoTool().execute(message="")
        assert result == {"echo": ""}

    def test_execute_converts_non_string(self) -> None:
        result = EchoTool().execute(message=42)
        assert result == {"echo": "42"}

    def test_execute_missing_message_defaults_empty(self) -> None:
        result = EchoTool().execute()
        assert result == {"echo": ""}

    def test_schema_has_required_parameter(self) -> None:
        params = EchoTool().parameters
        assert "message" in params
        assert params["message"].required is True

    def test_result_is_json_serialisable(self) -> None:
        result = EchoTool().execute(message="test")
        json.dumps(result)  # Must not raise.


# ---------------------------------------------------------------------------
# PingTool
# ---------------------------------------------------------------------------


class TestPingTool:
    def test_name(self) -> None:
        assert PingTool().name == "ping"

    def test_execute_loopback(self) -> None:
        """Loopback should almost always succeed in CI."""
        result = PingTool().execute(host="127.0.0.1", count=1)
        assert isinstance(result, dict)
        assert "success" in result
        assert result["host"] == "127.0.0.1"

    def test_execute_missing_host_returns_error(self) -> None:
        result = PingTool().execute()
        assert result["success"] is False
        assert "error" in result

    def test_count_clamped_to_max(self) -> None:
        tool = PingTool()
        result = tool.execute(host="127.0.0.1", count=999)
        assert isinstance(result, dict)

    def test_result_is_json_serialisable(self) -> None:
        result = PingTool().execute(host="127.0.0.1", count=1)
        json.dumps(result)  # Must not raise.

    def test_schema_host_required(self) -> None:
        params = PingTool().parameters
        assert "host" in params
        assert params["host"].required is True

    def test_schema_count_optional(self) -> None:
        params = PingTool().parameters
        assert "count" in params
        assert params["count"].required is False


# ---------------------------------------------------------------------------
# SystemInfoTool
# ---------------------------------------------------------------------------


class TestSystemInfoTool:
    def test_name(self) -> None:
        assert SystemInfoTool().name == "system_info"

    def test_execute_returns_expected_keys(self) -> None:
        result = SystemInfoTool().execute()
        for key in ("os", "os_release", "machine", "python_version", "platform"):
            assert key in result, f"Missing key: {key}"

    def test_os_is_non_empty_string(self) -> None:
        result = SystemInfoTool().execute()
        assert isinstance(result["os"], str)
        assert len(result["os"]) > 0

    def test_python_version_is_string(self) -> None:
        result = SystemInfoTool().execute()
        assert isinstance(result["python_version"], str)

    def test_result_is_json_serialisable(self) -> None:
        result = SystemInfoTool().execute()
        json.dumps(result)  # Must not raise.

    def test_no_parameters_required(self) -> None:
        assert SystemInfoTool().parameters == {}


# ---------------------------------------------------------------------------
# CalculatorTool
# ---------------------------------------------------------------------------


class TestCalculatorTool:
    def test_name(self) -> None:
        assert CalculatorTool().name == "calculator"

    @pytest.mark.parametrize(
        ("expr", "expected"),
        [
            ("2 + 3", 5),
            ("10 - 4", 6),
            ("3 * 4", 12),
            ("15 / 3", 5),
            ("15 // 4", 3),
            ("17 % 5", 2),
            ("2 ** 3", 8),
            ("-5 + 10", 5),
            ("+5 + +5", 10),
            ("(2 + 3) * 4", 20),
            ("3 + 4 * 2 / ( 1 - 5 ) ** 2", 3.5),
        ],
    )
    def test_normal_operations(self, expr: str, expected: float) -> None:
        assert safe_eval(expr) == pytest.approx(expected)

    def test_execute_success(self) -> None:
        res = CalculatorTool().execute(expression="10 + 20")
        assert res["success"] is True
        assert res["result"] == 30

    def test_execute_missing_expression(self) -> None:
        res = CalculatorTool().execute()
        assert res["success"] is False
        assert "expression is required" in res["error"]

    def test_division_by_zero(self) -> None:
        res = CalculatorTool().execute(expression="1 / 0")
        assert res["success"] is False
        assert "Division by zero" in res["error"]

    def test_invalid_syntax(self) -> None:
        res = CalculatorTool().execute(expression="2 + +")
        assert res["success"] is False
        assert "Invalid syntax" in res["error"]

    @pytest.mark.parametrize(
        "unsafe_expr",
        [
            "__import__('os').system('dir')",
            "eval('2+2')",
            "exec('a=1')",
            "open('/etc/passwd')",
            "x = 5",
            "[x for x in range(10)]",
            "lambda x: x + 1",
            "foo()",
            "math.sin(1)",
            "'hello' + 'world'",
        ],
    )
    def test_unsafe_expressions_rejected(self, unsafe_expr: str) -> None:
        with pytest.raises(CalculatorError):
            safe_eval(unsafe_expr)

    def test_exponent_magnitude_limit(self) -> None:
        with pytest.raises(CalculatorError, match="Exponent magnitude"):
            safe_eval("2 ** 1001")

    def test_ast_node_count_limit(self) -> None:
        # Construct an expression with > 64 nodes: 1 + 1 + 1 + ...
        long_expr = " + ".join(["1"] * 50)
        with pytest.raises(CalculatorError, match="too complex"):
            safe_eval(long_expr)

    def test_result_is_json_serialisable(self) -> None:
        result = CalculatorTool().execute(expression="100 / 4")
        json.dumps(result)  # Must not raise.


# ---------------------------------------------------------------------------
# CurrentTimeTool
# ---------------------------------------------------------------------------


class TestCurrentTimeTool:
    def test_name(self) -> None:
        assert CurrentTimeTool().name == "current_time"

    def test_execute_keys(self) -> None:
        res = CurrentTimeTool().execute()
        assert "utc" in res
        assert "date" in res
        assert "time" in res
        assert "timestamp_unix" in res

    def test_timezone_aware_iso(self) -> None:
        res = CurrentTimeTool().execute()
        iso_str = res["utc"]
        dt = datetime.fromisoformat(iso_str)
        assert dt.tzinfo is not None

    def test_result_is_json_serialisable(self) -> None:
        res = CurrentTimeTool().execute()
        json.dumps(res)  # Must not raise.


# ---------------------------------------------------------------------------
# FileInfoTool
# ---------------------------------------------------------------------------


class TestFileInfoTool:
    def test_name(self) -> None:
        assert FileInfoTool().name == "file_info"

    def test_execute_existing_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "sample.txt"
        test_file.write_text("Hello World", encoding="utf-8")

        # Call helper with tmp_path as root
        sandboxed = _get_sandboxed_path("sample.txt", root_path=tmp_path)
        assert sandboxed == test_file.resolve()

        res = FileInfoTool().execute(path=str(test_file), root_path=tmp_path)
        assert res["success"] is True
        assert res["name"] == "sample.txt"
        assert res["is_file"] is True
        assert res["is_directory"] is False
        assert res["size_bytes"] == 11

    def test_execute_existing_directory(self, tmp_path: Path) -> None:
        sub_dir = tmp_path / "sub"
        sub_dir.mkdir()

        res = FileInfoTool().execute(path=str(sub_dir), root_path=tmp_path)
        assert res["success"] is True
        assert res["name"] == "sub"
        assert res["is_directory"] is True

    def test_execute_nonexistent_file(self, tmp_path: Path) -> None:
        no_file = tmp_path / "missing.txt"
        res = FileInfoTool().execute(path=str(no_file), root_path=tmp_path)
        assert res["success"] is False
        assert "does not exist" in res["error"]

    def test_execute_missing_path_param(self) -> None:
        res = FileInfoTool().execute()
        assert res["success"] is False
        assert "path parameter is required" in res["error"]

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_text("secret", encoding="utf-8")

        with pytest.raises(ValueError, match="Access denied"):
            _get_sandboxed_path("../secret.txt", root_path=root)

    def test_result_is_json_serialisable(self, tmp_path: Path) -> None:
        f = tmp_path / "dummy.txt"
        f.write_text("dummy", encoding="utf-8")
        res = FileInfoTool().execute(path=str(f), root_path=tmp_path)
        json.dumps(res)  # Must not raise.
