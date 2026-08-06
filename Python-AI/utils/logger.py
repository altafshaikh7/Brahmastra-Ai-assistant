# utils/logger.py
"""Centralized logging utilities for the Brahmastra AI application."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging import Filter, Formatter, LogRecord
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any, Final

from core.config import get_settings

REQUEST_ID: Final[ContextVar[str | None]] = ContextVar(
    "request_id",
    default=None,
)
CORRELATION_ID: Final[ContextVar[str | None]] = ContextVar(
    "correlation_id",
    default=None,
)

_SENSITIVE_KEYS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "jwt",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "cookies",
    "mongodb_uri",
    "uri",
)

_LOGGER_CONFIG_LOCK: Final[Lock] = Lock()
_CONFIGURED: bool = False

# Pre‑compiled regex patterns for performance
_MASK_PATTERNS: Final[tuple[re.Pattern, ...]] = (
    re.compile(
        r"(?i)(password|passwd|pwd|secret|token|jwt|api[_-]?key|authorization|cookie)\s*[:=]\s*([^\s,;]+)"
    ),
    re.compile(r"(?i)(mongodb://[^\s]+)"),
    re.compile(r"(?i)(bearer\s+[a-z0-9\-_.~+/]+=*)"),
)


class ContextFilter(Filter):
    """Inject request and correlation metadata into log records."""

    def filter(self, record: LogRecord) -> bool:
        record.request_id = REQUEST_ID.get() or "-"
        record.correlation_id = CORRELATION_ID.get() or "-"
        return True


class SensitiveDataFilter(Filter):
    """Mask sensitive values in log messages and extra fields before emission."""

    def filter(self, record: LogRecord) -> bool:
        # Mask the main message
        if isinstance(record.msg, str):
            record.msg = self._mask_text(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(self._mask_value(arg) for arg in record.args)

        # Mask extra attributes (from `extra={...}` in logging calls)
        # Internal/safe attributes to skip
        safe_keys = {
            "msg",
            "args",
            "exc_info",
            "exc_text",
            "stack_info",
            "created",
            "asctime",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "process",
            "processName",
            "module",
            "funcName",
            "lineno",
            "name",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "request_id",
            "correlation_id",
        }
        for key, value in record.__dict__.items():
            if key in safe_keys:
                continue
            # If the key itself is sensitive, redact the value
            if any(
                sens in key.lower()
                for sens in (
                    "password",
                    "secret",
                    "token",
                    "jwt",
                    "api_key",
                    "authorization",
                    "cookie",
                )
            ):
                setattr(record, key, "[REDACTED]")
            else:
                # Recursively mask the value (in case it's a dict/list)
                setattr(record, key, self._mask_value(value))
        return True

    def _mask_text(self, value: str) -> str:
        for pattern in _MASK_PATTERNS:
            value = pattern.sub(r"\1=[REDACTED]", value)
        return value

    def _mask_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._mask_text(value)
        if isinstance(value, dict):
            return {
                k: (
                    self._mask_value(v)
                    if k.lower() not in _SENSITIVE_KEYS
                    else "[REDACTED]"
                )
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return type(value)(self._mask_value(item) for item in value)
        return value


class JsonFormatter(Formatter):
    """Formatter that emits structured JSON logs."""

    def format(self, record: LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "request_id": getattr(record, "request_id", "-"),
            "correlation_id": getattr(record, "correlation_id", "-"),
            "message": self.formatMessage(record),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class PlainFormatter(Formatter):
    """Formatter that emits human-readable logs with millisecond precision."""

    def formatTime(self, record: LogRecord, datefmt: str | None = None) -> str:
        # Use UTC time and include milliseconds
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return dt.strftime(datefmt)
        # Default: ISO8601 with milliseconds and UTC offset (Z means UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"

    def format(self, record: LogRecord) -> str:
        return (
            f"{self.formatTime(record, self.datefmt)} | "
            f"{record.levelname:<8} | "
            f"{getattr(record, 'request_id', '-'):<12} | "
            f"{getattr(record, 'correlation_id', '-'):<12} | "
            f"{record.name:<20} | "
            f"{record.module}:{record.funcName}:{record.lineno} | "
            f"{record.getMessage()}"
        )


class ColorFormatter(PlainFormatter):
    """Formatter that adds ANSI colors for local development."""

    COLORS: Final[dict[int, str]] = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }

    def format(self, record: LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "\033[0m")
        return f"{color}{super().format(record)}\033[0m"


def _get_log_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def _resolve_log_path(path_value: str | os.PathLike[str] | None) -> Path:
    if path_value is None:
        path_value = "storage/logs/brahmastra.log"
    path = Path(path_value).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging() -> None:
    """Apply the shared logging configuration once for the process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    with _LOGGER_CONFIG_LOCK:
        if _CONFIGURED:
            return

        settings = get_settings()
        logging_settings = settings.logging
        application_settings = settings.application

        root_logger = logging.getLogger()
        root_logger.setLevel(_get_log_level(logging_settings.level))
        root_logger.handlers.clear()
        root_logger.propagate = False

        formatter: Formatter
        if application_settings.environment == "production":
            formatter = PlainFormatter()
        else:
            formatter = ColorFormatter()

        if logging_settings.console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(root_logger.level)
            console_handler.setFormatter(formatter)
            console_handler.addFilter(ContextFilter())
            console_handler.addFilter(SensitiveDataFilter())
            root_logger.addHandler(console_handler)

        if logging_settings.file:
            log_path = _resolve_log_path(logging_settings.file_path)
            rotating_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8",
            )
            rotating_handler.setLevel(root_logger.level)
            rotating_handler.setFormatter(PlainFormatter())
            rotating_handler.addFilter(ContextFilter())
            rotating_handler.addFilter(SensitiveDataFilter())
            root_logger.addHandler(rotating_handler)

            timed_handler = TimedRotatingFileHandler(
                log_path.with_suffix(".access.log"),
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            )
            timed_handler.setLevel(root_logger.level)
            timed_handler.setFormatter(PlainFormatter())
            timed_handler.addFilter(ContextFilter())
            timed_handler.addFilter(SensitiveDataFilter())
            root_logger.addHandler(timed_handler)

        _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    configure_logging()
    # Do NOT set propagate=False – we want logs to reach root handlers.
    return logging.getLogger(name)


def set_request_id(request_id: str | None) -> None:
    """Set the request ID for the current context."""
    REQUEST_ID.set(request_id)


def clear_request_id() -> None:
    """Clear the request ID for the current context."""
    REQUEST_ID.set(None)


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID for the current context."""
    CORRELATION_ID.set(correlation_id)


def clear_correlation_id() -> None:
    """Clear the correlation ID for the current context."""
    CORRELATION_ID.set(None)


def get_contextual_log_fields() -> dict[str, str | None]:
    """Return the current request and correlation IDs."""
    return {
        "request_id": REQUEST_ID.get(),
        "correlation_id": CORRELATION_ID.get(),
    }


def mask_sensitive_data(value: Any) -> Any:
    """Mask sensitive values from a payload before logging."""
    return SensitiveDataFilter()._mask_value(value)


def get_access_logger() -> logging.Logger:
    """Return a logger intended for access logs."""
    return get_logger("access")


def get_app_logger() -> logging.Logger:
    """Return a logger intended for application logs."""
    return get_logger("application")


def get_error_logger() -> logging.Logger:
    """Return a logger intended for error logs."""
    return get_logger("error")
