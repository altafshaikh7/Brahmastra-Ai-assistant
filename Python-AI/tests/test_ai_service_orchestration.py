from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.chat import ChatRequest, TokenUsage
from schemas.tool import ToolExecutionResponse
from services.ai_service import AIService


# Mock the database to prevent real DB connections during test
@pytest.fixture(autouse=True)
def mock_db():
    with patch("services.ai_service.get_database") as mock_get_db:
        mock_db_instance = MagicMock()
        mock_db_instance.conversations.find_one = AsyncMock(return_value=None)
        mock_db_instance.conversations.update_one = AsyncMock()
        mock_get_db.return_value = mock_db_instance
        yield mock_get_db


@pytest.fixture
def mock_provider():
    with patch("services.ai_service.AIProviderFactory.get_provider") as mock_get:
        provider = AsyncMock()
        provider.provider_id = "test_provider"
        provider.default_model = "test_model"
        mock_get.return_value = provider
        yield provider


@pytest.fixture
def mock_registry():
    with patch("services.ai_service.ToolRegistryService") as mock_reg:
        registry_instance = MagicMock()

        tool1 = MagicMock()
        tool1.name = "calculator"
        tool1.description = "calc"
        tool1.model_dump.return_value = {"parameters": {}}

        tool2 = MagicMock()
        tool2.name = "current_time"
        tool2.description = "time"
        tool2.model_dump.return_value = {"parameters": {}}

        tool3 = MagicMock()
        tool3.name = "system_info"
        tool3.description = "sys"
        tool3.model_dump.return_value = {"parameters": {}}

        tool4 = MagicMock()
        tool4.name = "file_info"
        tool4.description = "file"
        tool4.model_dump.return_value = {"parameters": {}}

        tools_list = MagicMock()
        tools_list.tools = [tool1, tool2, tool3, tool4]
        registry_instance.list_tools.return_value = tools_list
        mock_reg.return_value = registry_instance
        yield registry_instance


@pytest.fixture
def mock_executor():
    with patch("services.ai_service.ToolExecutor") as mock_exec:
        executor_instance = MagicMock()
        mock_exec.return_value = executor_instance
        yield executor_instance


@pytest.mark.asyncio
async def test_normal_chat(mock_provider, mock_registry):
    mock_provider.generate_response.return_value = (
        "Hello world",
        TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    service = AIService()
    req = ChatRequest(message="Hi")
    resp = await service.chat(req)

    assert resp.response == "Hello world"
    assert resp.tokens.total_tokens == 15
    assert mock_provider.generate_response.call_count == 1


@pytest.mark.asyncio
async def test_calculator_tool(mock_provider, mock_registry, mock_executor):
    # First response is a tool call, second is the final answer
    mock_provider.generate_response.side_effect = [
        (
            '{"tool_call": {"name": "calculator", "arguments": {"expression": "2+2"}}}',
            TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        ),
        (
            "The answer is 4.",
            TokenUsage(prompt_tokens=30, completion_tokens=5, total_tokens=35),
        ),
    ]

    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="calculator",
        success=True,
        output={"result": 4},
        execution_time_ms=1.0,
    )

    service = AIService()
    req = ChatRequest(message="What is 2+2?")
    resp = await service.chat(req)

    assert resp.response == "The answer is 4."
    assert resp.tokens.total_tokens == 60
    assert mock_provider.generate_response.call_count == 2
    mock_executor.execute.assert_called_once()
    args = mock_executor.execute.call_args[0][0]
    assert args.tool_name == "calculator"


@pytest.mark.asyncio
async def test_current_time_tool(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        (
            '```json\n{"tool_call": {"name": "current_time", "arguments": {}}}\n```',
            TokenUsage(),
        ),
        ("It is noon.", TokenUsage()),
    ]
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="current_time", success=True, output="12:00 PM", execution_time_ms=1.0
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="Time?"))
    assert resp.response == "It is noon."
    assert mock_executor.execute.call_args[0][0].tool_name == "current_time"


@pytest.mark.asyncio
async def test_system_info_tool(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        ('{"tool_call": {"name": "system_info", "arguments": {}}}', TokenUsage()),
        ("Windows 11", TokenUsage()),
    ]
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="system_info",
        success=True,
        output="Windows 11",
        execution_time_ms=1.0,
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="OS?"))
    assert resp.response == "Windows 11"
    assert mock_executor.execute.call_args[0][0].tool_name == "system_info"


@pytest.mark.asyncio
async def test_file_info_tool(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        (
            '{"tool_call": {"name": "file_info", "arguments": {"path": "../secret.txt"}}}',
            TokenUsage(),
        ),
        ("Access denied", TokenUsage()),
    ]
    # Simulate the executor enforcing sandbox and returning error
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="file_info",
        success=False,
        output={"error": "Path traversal"},
        execution_time_ms=1.0,
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="Read secret"))
    assert resp.response == "Access denied"

    # Check that the error output is sent back in history
    history_arg = mock_provider.generate_response.call_args_list[1][0][1]
    assert "Path traversal" in history_arg[-1]["content"]


@pytest.mark.asyncio
async def test_unknown_tool(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        ('{"tool_call": {"name": "hack_mainframe", "arguments": {}}}', TokenUsage()),
        ("Cannot do that", TokenUsage()),
    ]
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="hack_mainframe",
        success=False,
        output={"error": "Tool not found"},
        execution_time_ms=1.0,
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="Hack it"))
    assert resp.response == "Cannot do that"


@pytest.mark.asyncio
async def test_malformed_tool_call(mock_provider, mock_registry, mock_executor):
    # Returns something that looks like a tool call but is invalid JSON
    mock_provider.generate_response.return_value = (
        '{"tool_call": {"name": "calculator", "arguments": {bad_json}}}',
        TokenUsage(),
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="calc"))
    # The JSON decode error is caught, and it just returns the raw string as final answer
    assert "bad_json" in resp.response
    mock_executor.execute.assert_not_called()


@pytest.mark.asyncio
async def test_tool_execution_error(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        (
            '{"tool_call": {"name": "calculator", "arguments": {"expression": "1/0"}}}',
            TokenUsage(),
        ),
        ("I cannot divide by zero", TokenUsage()),
    ]
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="calculator",
        success=False,
        output={"error": "Division by zero"},
        execution_time_ms=1.0,
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="1/0"))
    assert resp.response == "I cannot divide by zero"


@pytest.mark.asyncio
async def test_multiple_turn_conversation(mock_provider, mock_registry, mock_executor):
    mock_provider.generate_response.side_effect = [
        ('{"tool_call": {"name": "current_time", "arguments": {}}}', TokenUsage()),
        (
            '{"tool_call": {"name": "calculator", "arguments": {"expression": "5*5"}}}',
            TokenUsage(),
        ),
        ("It is noon and 5*5 is 25.", TokenUsage()),
    ]

    def exec_side_effect(req):
        if req.tool_name == "current_time":
            return ToolExecutionResponse(
                tool_name="current_time",
                success=True,
                output="noon",
                execution_time_ms=1.0,
            )
        return ToolExecutionResponse(
            tool_name="calculator", success=True, output="25", execution_time_ms=1.0
        )

    mock_executor.execute.side_effect = exec_side_effect

    service = AIService()
    resp = await service.chat(ChatRequest(message="complex request"))
    assert resp.response == "It is noon and 5*5 is 25."
    assert mock_executor.execute.call_count == 2
    assert mock_provider.generate_response.call_count == 3


@pytest.mark.asyncio
async def test_final_natural_language_response(
    mock_provider, mock_registry, mock_executor
):
    mock_provider.generate_response.side_effect = [
        (
            '{"tool_call": {"name": "ping", "arguments": {}}}',
            TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        ),
        (
            "Ping successful!",
            TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
        ),
    ]
    mock_executor.execute.return_value = ToolExecutionResponse(
        tool_name="ping", success=True, output="pong", execution_time_ms=1.0
    )

    service = AIService()
    resp = await service.chat(ChatRequest(message="ping"))
    assert resp.response == "Ping successful!"
    assert resp.tokens.total_tokens == 50
