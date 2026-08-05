# middleware/rate_limit.py
"""In‑memory rate‑limiting middleware based on client IP.

Uses a simple fixed‑window algorithm with configurable limits.  If a
client exceeds the request limit within the window, the middleware
short‑circuits with a ``429 Too Many Requests`` response and a
``Retry-After`` header.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable constants (can be moved to settings in the future)
# ---------------------------------------------------------------------------

RATE_LIMIT_REQUESTS: int = 100   # max requests per window
RATE_LIMIT_WINDOW: int = 60       # window size in seconds

_settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed‑window rate limiter keyed by client IP address.

    Thread‑safe: uses an ``asyncio.Lock`` to guard the internal counter
    dictionary.
    """

    def __init__(self, app, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._window: int = kwargs.get("window_seconds", RATE_LIMIT_WINDOW)
        self._limit: int = kwargs.get("max_requests", RATE_LIMIT_REQUESTS)
        # Internal state: ip -> (count, window_start)
        self._counters: Dict[str, Tuple[int, float]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the client IP, accounting for reverse proxies."""
        # X-Forwarded-For can contain multiple IPs; take the first.
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        ip = self._get_client_ip(request)

        async with self._lock:
            count, window_start = self._counters.get(ip, (0, time.monotonic()))
            now = time.monotonic()

            # If the current window has expired, reset the counter.
            if now - window_start > self._window:
                count = 0
                window_start = now

            count += 1
            self._counters[ip] = (count, window_start)

            # Check limit
            if count > self._limit:
                logger.warning(
                    "Rate limit exceeded for %s (%d req in %ds window)",
                    ip,
                    count - 1,  # count was incremented; actual requests is count-1
                    self._window,
                )
                # Retry-After: seconds until window reset.
                retry_after = int(window_start + self._window - now)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "detail": (
                            f"Rate limit exceeded. "
                            f"Try again in {retry_after} seconds."
                        ),
                    },
                    headers={"Retry-After": str(retry_after)},
                )

        # Not rate‑limited – continue normally.
        return await call_next(request)


# Public alias expected by app.py
rate_limit_middleware = RateLimitMiddleware