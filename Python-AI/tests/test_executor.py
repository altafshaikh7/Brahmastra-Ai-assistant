"""Tests for ToolExecutor, ToolRegistryService, and routers/tools.py FastAPI endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import create_app
from schemas.tool import ToolExecutionRequest, ToolExecutionResponse
from services.executor import ToolExecutor
from services.registry_service import ToolRegistryService
from tools.registry import ToolNotFoundError


@pytest.fixture()
def executor() -> ToolExecutor:
    return ToolExecutor()


@pytest.fixture()
def registry_service() -> ToolRegistryService:
    return ToolRegistryService()


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# ToolExecutor Unit Tests
# ---------------------------------------------------------------------------


class TestToolExecutor:
    def test_execute_echo_success(self, executor: ToolExecutor) -> None:
        req = ToolExecutionRequest(
            tool_name="echo", arguments={"message": "hello world"}
        )
        res = executor.execute(req)
        assert isinstance(res, ToolExecutionResponse)
        assert res.tool_name == "echo"
        assert res.success is True
        assert res.output == {"echo": "hello world"}
        assert res.execution_time_ms >= 0.0

    def test_execute_calculator_success(self, executor: ToolExecutor) -> None:
        req = ToolExecutionRequest(
            tool_name="calculator", arguments={"expression": "10 + 5 * 2"}
        )
        res = executor.execute(req)
        assert res.success is True
        assert res.output["result"] == 20

    def test_execute_unknown_tool(self, executor: ToolExecutor) -> None:
        req = ToolExecutionRequest(tool_name="nonexistent_tool", arguments={})
        res = executor.execute(req)
        assert res.success is False
        assert "is not registered" in str(res.output)

    def test_execute_missing_required_argument(self, executor: ToolExecutor) -> None:
        # echo requires 'message'
        req = ToolExecutionRequest(tool_name="echo", arguments={})
        res_echo = executor.execute(req)
        assert res_echo.success is False
        assert "Missing required parameter" in str(res_echo.output)
        # echo tool defaults missing message to "", but calculator requires 'expression'
        req_calc = ToolExecutionRequest(tool_name="calculator", arguments={})
        res_calc = executor.execute(req_calc)
        assert res_calc.success is False

    def test_execute_invalid_argument_type(self, executor: ToolExecutor) -> None:
        # ping requires 'count' as integer
        req = ToolExecutionRequest(
            tool_name="ping", arguments={"host": "127.0.0.1", "count": "not_an_int"}
        )
        res = executor.execute(req)
        assert res.success is False
        assert "must be an integer" in str(res.output)

    def test_execute_file_info_sandbox_behaviour(
        self, executor: ToolExecutor, tmp_path: Path
    ) -> None:
        f = tmp_path / "test.txt"
        f.write_text("content", encoding="utf-8")

        req = ToolExecutionRequest(
            tool_name="file_info",
            arguments={"path": str(f), "root_path": str(tmp_path)},
        )
        res = executor.execute(req)
        assert res.success is True
        assert res.output["name"] == "test.txt"
        assert res.output["size_bytes"] == 7

    def test_execute_file_info_path_traversal_blocked(
        self, executor: ToolExecutor, tmp_path: Path
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()

        req = ToolExecutionRequest(
            tool_name="file_info",
            arguments={"path": "../secret.txt", "root_path": str(sub)},
        )
        res = executor.execute(req)
        assert res.success is False
        assert "Access denied" in str(res.output)

    def test_response_is_json_serialisable(self, executor: ToolExecutor) -> None:
        req = ToolExecutionRequest(tool_name="current_time", arguments={})
        res = executor.execute(req)
        serialized = json.dumps(res.model_dump(mode="json"))
        assert isinstance(serialized, str)


# ---------------------------------------------------------------------------
# ToolRegistryService Tests
# ---------------------------------------------------------------------------


class TestToolRegistryService:
    def test_list_tools(self, registry_service: ToolRegistryService) -> None:
        res = registry_service.list_tools()
        assert res.total >= 6
        names = [t.name for t in res.tools]
        assert "calculator" in names
        assert "echo" in names

    def test_get_tool_info_success(self, registry_service: ToolRegistryService) -> None:
        schema = registry_service.get_tool_info("calculator")
        assert schema.name == "calculator"
        assert schema.display_name == "Calculator"

    def test_get_tool_info_unknown_raises(
        self, registry_service: ToolRegistryService
    ) -> None:
        with pytest.raises(ToolNotFoundError):
            registry_service.get_tool_info("invalid_tool")

    def test_get_health(self, registry_service: ToolRegistryService) -> None:
        health = registry_service.get_health("echo")
        assert health.tool_name == "echo"
        assert health.status == "healthy"


# ---------------------------------------------------------------------------
# FastAPI Router Endpoints Tests (/tools)
# ---------------------------------------------------------------------------


class TestToolsRouter:
    def test_get_tools_list(self, client: TestClient) -> None:
        resp = client.get("/tools/")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "tools" in data
        assert data["total"] >= 6

    def test_get_tools_list_alias(self, client: TestClient) -> None:
        resp = client.get("/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 6

    def test_get_tool_info_success(self, client: TestClient) -> None:
        resp = client.get("/tools/info/calculator")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "calculator"

    def test_get_tool_info_not_found(self, client: TestClient) -> None:
        resp = client.get("/tools/info/nonexistent_tool")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_post_execute_tool_success(self, client: TestClient) -> None:
        payload = {
            "tool_name": "echo",
            "arguments": {"message": "hello api"},
        }
        resp = client.post("/tools/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_name"] == "echo"
        assert data["success"] is True
        assert data["output"] == {"echo": "hello api"}

    def test_post_execute_tool_unknown(self, client: TestClient) -> None:
        payload = {
            "tool_name": "unknown_tool",
            "arguments": {},
        }
        resp = client.post("/tools/execute", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "is not registered" in str(data["output"]).lower()
