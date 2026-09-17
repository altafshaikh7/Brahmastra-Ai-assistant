"""Authentication for trusted service-to-service requests."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status
from core.config import get_settings


async def verify_internal_api_key(
    x_internal_api_key: str | None = Header(default=None),
) -> None:
    """Require the shared Node/Python key when configured for deployment."""
    expected = os.getenv("PYTHON_AI_API_KEY")
    if not expected:
        configured = get_settings().security.api_secret
        expected = configured.get_secret_value() if configured else None
    if expected and not x_internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if expected and not hmac.compare_digest(x_internal_api_key or "", expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid service key")