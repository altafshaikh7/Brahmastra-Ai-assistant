"""Live integration checks for Node -> Python-AI routing."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable

import httpx

NODE = os.getenv("NODE_URL", "http://127.0.0.1:5000")
PY = os.getenv("PYTHON_AI_URL", "http://127.0.0.1:8000")
NO_REALTIME = re.compile(
    r"do not have real[- ]time|text-based AI and do not have", re.IGNORECASE
)


def safe_text(response: httpx.Response, limit: int = 300) -> str:
    return response.text.encode("ascii", "backslashreplace").decode("ascii")[:limit]


def run(name: str, fn: Callable[[], tuple[bool, str]]) -> tuple[str, bool, str]:
    try:
        ok, detail = fn()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {detail.encode('ascii', 'backslashreplace').decode('ascii')[:300]}")
        return name, ok, detail
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return name, False, str(exc)


def chat_py(msg: str) -> httpx.Response:
    return httpx.post(f"{PY}/ai/chat", json={"message": msg}, timeout=120.0)


def chat_node(msg: str) -> httpx.Response:
    return httpx.post(f"{NODE}/api/chat", json={"query": msg}, timeout=120.0)


def check_json_response(
    response: httpx.Response, predicate: Callable[[dict], bool]
) -> tuple[bool, str]:
    try:
        data = response.json()
    except json.JSONDecodeError:
        return False, safe_text(response)

    ok = response.status_code == 200 and predicate(data)
    return ok, json.dumps(data, default=str)[:250]


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    results.append(
        run(
            "A Node GET /health",
            lambda: (
                (r := httpx.get(f"{NODE}/health", timeout=10.0)).status_code == 200
                and r.json().get("success") is True,
                safe_text(r, 120),
            ),
        )
    )
    results.append(
        run(
            "A Python GET /health",
            lambda: (
                (r := httpx.get(f"{PY}/health", timeout=10.0)).status_code == 200,
                safe_text(r, 120),
            ),
        )
    )
    results.append(
        run(
            "B Python GET /tools",
            lambda: (
                (r := httpx.get(f"{PY}/tools", timeout=10.0)).status_code == 200
                and "current_time" in r.text,
                safe_text(r, 200),
            ),
        )
    )
    results.append(
        run(
            "C POST /ai/chat time",
            lambda: check_json_response(
                chat_py("What time is it now?"),
                lambda data: data.get("success") is True
                and not NO_REALTIME.search(data.get("response", ""))
                and bool(re.search(r"\d", data.get("response", ""))),
            ),
        )
    )
    results.append(
        run(
            "D POST /api/chat time",
            lambda: check_json_response(
                chat_node("What time is it now?"),
                lambda data: data.get("success") is True
                and not NO_REALTIME.search(data.get("data", {}).get("answer", ""))
                and bool(re.search(r"\d", data.get("data", {}).get("answer", ""))),
            ),
        )
    )
    results.append(
        run(
            "F calculator",
            lambda: check_json_response(
                chat_node(
                    "Calculate 144 divided by 12 using the calculator tool."
                ),
                lambda data: "12" in data.get("data", {}).get("answer", ""),
            ),
        )
    )
    results.append(
        run(
            "G system_info",
            lambda: check_json_response(
                chat_node("What operating system am I using?"),
                lambda data: len(data.get("data", {}).get("answer", "")) > 5,
            ),
        )
    )
    results.append(
        run(
            "H ping",
            lambda: check_json_response(
                chat_node("Ping google.com"),
                lambda data: len(data.get("data", {}).get("answer", "")) > 5,
            ),
        )
    )
    results.append(
        run(
            "I file_info traversal",
            lambda: check_json_response(
                chat_node("Get file info for ../../../etc/passwd"),
                lambda data: data.get("success") is True
                and any(
                    word in ans
                    for word in (
                        "denied",
                        "traversal",
                        "invalid",
                        "not allowed",
                        "error",
                        "outside",
                        "reject",
                        "forbidden",
                        "sandbox",
                        "safe",
                        "cannot",
                        "unable",
                    )
                    if (ans := data.get("data", {}).get("answer", "").lower())
                ),
            ),
        )
    )
    results.append(
        run(
            "J unknown tool",
            lambda: check_json_response(
                chat_node("Use a tool called hack_everything."),
                lambda data: len(data.get("data", {}).get("answer", "")) > 0,
            ),
        )
    )

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nSUMMARY: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
