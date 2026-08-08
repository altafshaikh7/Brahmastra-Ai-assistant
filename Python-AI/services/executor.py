"""Tool execution service – validates and executes tools safely."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from schemas.tool import (
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolParameter,
    ToolParameterType,
)
from tools.registry import ToolNotFoundError, ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when argument validation or tool execution fails."""


class ToolExecutor:
    """Service responsible for executing registered tools with argument validation
    and exception handling.

    Usage::

        executor = ToolExecutor()
        response = executor.execute(
            ToolExecutionRequest(tool_name="calculator", arguments={"expression": "2+2"})
        )
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or ToolRegistry.get_instance()

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResponse:
        """Execute the tool described by *request* and return a :class:`ToolExecutionResponse`.

        Guarantees that no execution exception will crash the process; any error is
        captured in the response's ``success`` and ``output`` fields.
        """
        start_time = time.perf_counter()
        tool_name = request.tool_name

        try:
            tool = self._registry.get(tool_name)
        except ToolNotFoundError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResponse(
                tool_name=tool_name,
                success=False,
                output={"error": str(exc)},
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Validate arguments against the tool's parameter definitions
        try:
            validated_kwargs = self._validate_arguments(
                tool.parameters, request.arguments
            )
        except ToolExecutionError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResponse(
                tool_name=tool_name,
                success=False,
                output={"error": f"Invalid arguments for tool '{tool_name}': {exc}"},
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Execute the tool
        try:
            raw_output = tool.execute(**validated_kwargs)
            # Ensure output is JSON-serialisable
            try:
                json.dumps(raw_output)
                serialised_output = raw_output
            except (TypeError, ValueError):
                serialised_output = str(raw_output)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Determine success based on tool return value if dict contains "success"
            success = True
            if isinstance(raw_output, dict) and "success" in raw_output:
                success = bool(raw_output["success"])

            return ToolExecutionResponse(
                tool_name=tool_name,
                success=success,
                output=serialised_output,
                execution_time_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            logger.exception("Error executing tool '%s'", tool_name)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolExecutionResponse(
                tool_name=tool_name,
                success=False,
                output={"error": f"Execution error in tool '{tool_name}': {exc}"},
                execution_time_ms=round(elapsed_ms, 2),
            )

    @staticmethod
    def _validate_arguments(
        param_defs: dict[str, ToolParameter], provided_args: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and coerce *provided_args* against *param_defs*.

        Raises :class:`ToolExecutionError` if a required parameter is missing or
        coercion fails.
        """
        validated: dict[str, Any] = {}

        # 1. Check for unexpected arguments
        for arg_name in provided_args:
            if arg_name not in param_defs:
                # Allow root_path for internal testing/file_info sandbox overrides
                if arg_name == "root_path":
                    validated["root_path"] = provided_args["root_path"]
                    continue
                logger.debug("Unknown argument '%s' passed to tool", arg_name)

        # 2. Validate declared parameters
        for name, param in param_defs.items():
            if name in provided_args:
                raw_val = provided_args[name]
                validated[name] = ToolExecutor._coerce_type(name, raw_val, param.type)
            elif param.required:
                raise ToolExecutionError(f"Missing required parameter: '{name}'")
            elif param.default is not None:
                validated[name] = param.default

        return validated

    @staticmethod
    def _coerce_type(param_name: str, value: Any, param_type: ToolParameterType) -> Any:
        """Coerce *value* to the expected *param_type*."""
        if value is None:
            return None

        if param_type == ToolParameterType.integer:
            try:
                return int(value)
            except (ValueError, TypeError):
                raise ToolExecutionError(
                    f"Parameter '{param_name}' must be an integer, got {type(value).__name__}"
                ) from None

        if param_type == ToolParameterType.float:
            try:
                return float(value)
            except (ValueError, TypeError):
                raise ToolExecutionError(
                    f"Parameter '{param_name}' must be a float, got {type(value).__name__}"
                ) from None

        if param_type == ToolParameterType.boolean:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ("true", "1", "yes"):
                    return True
                if value.lower() in ("false", "0", "no"):
                    return False
            raise ToolExecutionError(
                f"Parameter '{param_name}' must be a boolean, got {type(value).__name__}"
            )

        if param_type == ToolParameterType.string:
            return str(value)

        if param_type == ToolParameterType.json:
            if isinstance(value, (dict, list)):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    raise ToolExecutionError(
                        f"Parameter '{param_name}' must be valid JSON string"
                    ) from None

        return value
