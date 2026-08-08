"""Safe AST-based arithmetic calculator tool."""

from __future__ import annotations

import ast
import math
import operator
from typing import Any

from schemas.tool import (
    ToolCategory,
    ToolMetadata,
    ToolParameter,
    ToolParameterType,
    ToolSchema,
)
from tools.base_tool import BaseTool

# ---------------------------------------------------------------------------
# AST allowlist
# ---------------------------------------------------------------------------

# Only these AST node types are permitted anywhere in the expression tree.
_SAFE_NODE_TYPES = frozenset(
    {
        ast.Expression,
        ast.Constant,
        # Python < 3.8 compat (Num/Str are still emitted by some tools)
        ast.Num,  # type: ignore[attr-defined]
        ast.BinOp,
        ast.UnaryOp,
        # Allowed operators
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.FloorDiv,
        ast.UAdd,
        ast.USub,
    }
)

# Operator mapping for safe evaluation without eval().
_BINOP_MAP = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_UNOP_MAP = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Safety limits
_MAX_EXPRESSION_LENGTH = 256
_MAX_AST_NODES = 64
_MAX_EXPONENT = 1_000
_MAX_RESULT_ABS = 1e308


class CalculatorError(ValueError):
    """Raised when an expression is invalid or unsafe."""


def _check_nodes(node: ast.AST, node_count: list[int]) -> None:
    """Recursively validate that every AST node is in the allowlist."""
    node_count[0] += 1
    if node_count[0] > _MAX_AST_NODES:
        raise CalculatorError(
            f"Expression is too complex (>{_MAX_AST_NODES} AST nodes)."
        )
    if type(node) not in _SAFE_NODE_TYPES:
        raise CalculatorError(
            f"Unsafe expression: node type '{type(node).__name__}' is not allowed."
        )
    for child in ast.iter_child_nodes(node):
        _check_nodes(child, node_count)


def _eval_node(node: ast.AST) -> float | int:
    """Recursively evaluate a validated AST node."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise CalculatorError(
                f"Unsupported constant type: {type(node.value).__name__}"
            )
        return node.value

    # Python < 3.8 compatibility
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return node.n  # type: ignore[attr-defined]

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINOP_MAP:
            raise CalculatorError(f"Unsupported binary operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)

        # Guard against huge exponents before computing.
        if op_type is ast.Pow:
            exp = right
            if isinstance(exp, float) and not exp.is_integer():
                pass  # fractional powers are fine (e.g. 2**0.5)
            elif abs(exp) > _MAX_EXPONENT:
                raise CalculatorError(
                    f"Exponent magnitude {abs(exp)} exceeds limit of {_MAX_EXPONENT}."
                )

        if op_type is ast.Div and right == 0:
            raise CalculatorError("Division by zero.")
        if op_type is ast.Mod and right == 0:
            raise CalculatorError("Modulo by zero.")
        if op_type is ast.FloorDiv and right == 0:
            raise CalculatorError("Floor division by zero.")

        result = _BINOP_MAP[op_type](left, right)
        if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
            raise CalculatorError("Result is not finite (NaN or Infinity).")
        return result

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNOP_MAP:
            raise CalculatorError(f"Unsupported unary operator: {op_type.__name__}")
        return _UNOP_MAP[op_type](_eval_node(node.operand))

    raise CalculatorError(f"Unexpected node type: {type(node).__name__}")


def safe_eval(expression: str) -> float | int:
    """Parse and evaluate *expression* safely without using eval().

    Raises :class:`CalculatorError` on any unsafe or invalid input.
    """
    if not isinstance(expression, str):
        raise CalculatorError("Expression must be a string.")
    if len(expression) > _MAX_EXPRESSION_LENGTH:
        raise CalculatorError(
            f"Expression exceeds maximum length of {_MAX_EXPRESSION_LENGTH} characters."
        )

    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Invalid syntax: {exc}") from exc

    # Validate every node against the allowlist.
    node_count: list[int] = [0]
    _check_nodes(tree, node_count)

    result = _eval_node(tree)

    if isinstance(result, float) and abs(result) > _MAX_RESULT_ABS:
        raise CalculatorError(f"Result magnitude exceeds limit ({_MAX_RESULT_ABS}).")

    # Return int when the result is a whole number.
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class CalculatorTool(BaseTool):
    """Safely evaluates basic arithmetic expressions using AST validation."""

    tool_schema = ToolSchema(
        name="calculator",
        display_name="Calculator",
        description=(
            "Evaluates a basic arithmetic expression and returns the result. "
            "Supports +, -, *, /, //, %, ** and parentheses. "
            "Does not use eval(); validated via AST allowlist."
        ),
        parameters=[
            ToolParameter(
                name="expression",
                type=ToolParameterType.string,
                required=True,
                description="Arithmetic expression to evaluate, e.g. '2 + 3 * 4'.",
                example="(10 + 5) * 2 / 3",
            ),
        ],
        metadata=ToolMetadata(
            author="Brahmastra AI",
            version="1.0.0",
            category=ToolCategory.data_processing,
            tags=["math", "arithmetic", "calculator"],
        ),
    )

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        expression: str = str(kwargs.get("expression", "")).strip()
        if not expression:
            return {"success": False, "error": "expression is required"}

        try:
            result = safe_eval(expression)
            return {
                "success": True,
                "expression": expression,
                "result": result,
            }
        except CalculatorError as exc:
            return {
                "success": False,
                "expression": expression,
                "error": str(exc),
            }


# Module-level singleton registered by ToolRegistry on auto-discovery.
tool = CalculatorTool()
