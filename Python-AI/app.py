# app.py
"""Main entry point for the Brahmastra AI FastAPI application.

This module creates the FastAPI instance, registers routers, applies
middleware, and configures the application lifespan.  All heavy lifting
(e.g., logger initialization, tool registration) is delegated to the
corresponding sub‑modules to keep the entry point minimal and
maintainable.

The design follows Clean Architecture principles:
- Dependency injection via the ``Settings`` singleton.
- No business logic resides in this module.
- All I/O‑related concerns are handled by dedicated layers (routers,
  services, middleware).

The application can be started with::

    uvicorn app:app --host 0.0.0.0 --port 8000

"""

from __future__ import annotations

from fastapi import FastAPI

from core.config import get_settings
from core.lifespan import lifespan
from middleware.cors import cors_middleware
from middleware.logging import logging_middleware
from middleware.request_id import request_id_middleware
from middleware.timing import timing_middleware
from middleware.rate_limit import rate_limit_middleware
from core.exception_handler import register_exception_handlers

# Routers -------------------------------------------------------------
from routers.health import router as health_router
from routers.status import router as status_router
from routers.tools import router as tools_router
from routers.automation import router as automation_router


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application.

    Returns
    -------
    FastAPI
        Fully configured FastAPI application instance.
    """
    settings = get_settings()

    # FastAPI core configuration
    app = FastAPI(
        title="Brahmastra AI",
        version=settings.application.version,
        debug=settings.application.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # -----------------------------------------------------------------
    # Middleware registration (order matters for request/response flow)
    # -----------------------------------------------------------------
    app.add_middleware(cors_middleware)          # CORS handling
    app.add_middleware(request_id_middleware)    # Request‑ID propagation
    app.add_middleware(timing_middleware)        # Request timing metrics
    app.add_middleware(rate_limit_middleware)    # Simple rate limiting
    app.add_middleware(logging_middleware)       # Structured logging

    # -----------------------------------------------------------------
    # Exception handling
    # -----------------------------------------------------------------
    register_exception_handlers(app)

    # -----------------------------------------------------------------
    # Router registration
    # -----------------------------------------------------------------
    app.include_router(health_router, prefix="/health", tags=["Health"])
    app.include_router(status_router, prefix="/status", tags=["Status"])
    app.include_router(tools_router, prefix="/tools", tags=["Tools"])
    app.include_router(automation_router, prefix="/automation", tags=["Automation"])

    return app


# The public ASGI application instance used by Uvicorn / Hypercorn.
app: FastAPI = create_app()