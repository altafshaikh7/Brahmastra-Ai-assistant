# middleware/timing.py
"""Request timing middleware that attaches an ``X-Process-Time`` header.

Measures wall‑clock duration of each request and stores it on the
request state for downstream consumption (e.g., by the logging
middleware).  The duration is returned to the client as a header.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TimingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that records request processing time."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000.0

        # Store duration on request state for potential use by other components
        request.state.process_time = duration_ms

        # Expose processing time to the client
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        return response


# Public alias expected by app.py
timing_middleware = TimingMiddleware
