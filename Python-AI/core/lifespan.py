"""Production-grade FastAPI lifespan manager for the Brahmastra AI project."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI

from core.config import get_settings
from core.exceptions import ConfigurationError, register_exception_handlers
from dependencies.database import close_mongo_connection, get_database_health, init_mongo_client
from utils.logger import get_logger

try:
    from middleware import register_middleware
except ImportError:
    def register_middleware(app: FastAPI) -> None:
        """No-op middleware registration placeholder when middleware is not configured."""
        logger.debug("Middleware registration skipped", extra={"event": "middleware_registration_skipped"})

logger = get_logger(__name__)
settings = get_settings()


class LifecycleHooks:
    """Extension points for future background services such as schedulers and workers."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        """Start optional background services."""
        logger.debug("Lifecycle hooks initialized", extra={"event": "lifecycle_hooks_start"})

    async def stop(self) -> None:
        """Stop optional background services and wait for cleanup."""
        if not self._tasks:
            return
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.debug("Lifecycle hooks stopped", extra={"event": "lifecycle_hooks_stop"})


async def _validate_startup_requirements() -> None:
    """Validate configuration and runtime requirements before serving traffic."""
    if not settings.application.title:
        raise ConfigurationError("Application title is not configured")
    if not settings.application.version:
        raise ConfigurationError("Application version is not configured")
    if not settings.mongodb.uri:
        raise ConfigurationError("MongoDB URI is not configured")

    storage_paths = [
        settings.storage.base_path,
        settings.storage.logs_path,
        settings.storage.uploads_path,
        settings.storage.cache_path,
        settings.storage.temp_path,
    ]
    for path in storage_paths:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

    health = await get_database_health()
    if not health.get("ok"):
        raise ConfigurationError("MongoDB health check failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown for the entire FastAPI app."""
    started_at = time.perf_counter()
    hooks = LifecycleHooks()
    app.state.lifecycle_hooks = hooks
    app.state.startup_duration_seconds = None
    app.state.shutdown_duration_seconds = None

    logger.info(
        "Application startup initiated",
        extra={
            "event": "startup_started",
            "environment": settings.application.environment.value,
            "app_version": settings.application.version,
        },
    )

    try:
        register_exception_handlers(app)
        register_middleware(app)
        await init_mongo_client()
        await _validate_startup_requirements()
        await hooks.start()
        app.state.startup_duration_seconds = round(time.perf_counter() - started_at, 6)
        logger.info(
            "Application startup completed",
            extra={
                "event": "startup_completed",
                "startup_duration_seconds": app.state.startup_duration_seconds,
                "environment": settings.application.environment.value,
                "app_version": settings.application.version,
            },
        )
        yield
    except Exception as exc:
        app.state.startup_duration_seconds = round(time.perf_counter() - started_at, 6)
        logger.exception(
            "Application startup failed",
            extra={
                "event": "startup_failed",
                "startup_duration_seconds": app.state.startup_duration_seconds,
                "environment": settings.application.environment.value,
                "app_version": settings.application.version,
            },
        )
        await hooks.stop()
        await close_mongo_connection()
        raise
    finally:
        shutdown_started_at = time.perf_counter()
        logger.info("Application shutdown initiated", extra={"event": "shutdown_started"})
        try:
            await hooks.stop()
            await close_mongo_connection()
            logger.info(
                "Application shutdown completed",
                extra={
                    "event": "shutdown_completed",
                    "shutdown_duration_seconds": round(time.perf_counter() - shutdown_started_at, 6),
                },
            )
        except Exception:
            logger.exception("Application shutdown failed", extra={"event": "shutdown_failed"})


__all__ = ["LifecycleHooks", "lifespan"]