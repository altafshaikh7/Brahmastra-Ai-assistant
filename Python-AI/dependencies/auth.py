# dependencies/auth.py
"""
Authentication and authorization dependency functions.

This module provides FastAPI dependency callables that enforce
authentication schemes (Bearer token, API key) and authorization
constraints (roles, permissions). The JWT verification layer is
designed to be easily replaced with a real identity provider later.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel, ConfigDict, Field

from core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User model (placeholder – can be replaced with DB‑backed model later)
# ---------------------------------------------------------------------------

class UserInfo(BaseModel):
    """Minimal representation of an authenticated user."""

    id: str = Field(..., description="Unique user identifier (sub claim).")
    username: str | None = Field(None, description="Human‑friendly username.")
    roles: List[str] = Field(default_factory=list, description="Assigned roles.")
    permissions: List[str] = Field(
        default_factory=list, description="Derived or assigned permissions."
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Additional JWT claims."
    )

    model_config = ConfigDict(strict=True)


# ---------------------------------------------------------------------------
# Role <-> Permission mapping (hard‑coded for Phase 1 – extendable)
# ---------------------------------------------------------------------------

_ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {"*"},
    "user": {"read:tools", "execute:tools"},
    "operator": {"read:tools", "execute:tools", "manage:automation"},
}


def _get_permissions_for_roles(roles: List[str]) -> Set[str]:
    """Resolve permissions from a list of role names."""
    perms: Set[str] = set()
    for role in roles:
        role_perms = _ROLE_PERMISSIONS.get(role, set())
        if "*" in role_perms:
            # Wildcard means all permissions; we signal it with a special value
            # but downstream checks will handle "*" explicitly.
            perms = {"*"}
            break
        perms |= role_perms
    return perms


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_settings = get_settings()

_JWT_SECRET: str = _settings.jwt.secret_key.get_secret_value()
_JWT_ALGORITHM: str = _settings.jwt.algorithm.value
_TOKEN_PREFIX: str = _settings.jwt.token_prefix.lower()

bearer_scheme = HTTPBearer(auto_error=False)
optional_bearer_scheme = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.

    Returns the decoded payload dictionary.  All relevant PyJWT
    exceptions are caught and re‑raised as HTTP 401.
    """
    try:
        payload: Dict[str, Any] = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=[_JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Expired JWT token encountered.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid JWT token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )
    except Exception as exc:
        logger.exception("Unexpected JWT decoding error.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
        )


# ---------------------------------------------------------------------------
# API‑Key security scheme
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(
    name=_settings.security.api_key_header,
    auto_error=False,
)


def _get_api_key() -> Optional[str]:
    """Return the expected API key from environment or settings."""
    # In production this would come from a secure vault.
    import os

    return os.environ.get("BRAHMSTRA_API_KEY")


# ---------------------------------------------------------------------------
# Core dependency functions
# ---------------------------------------------------------------------------

def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> Dict[str, Any]:
    """Verify a Bearer token and return its decoded payload.

    Raises 401 if the token is missing, invalid, or the scheme is wrong.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.scheme.lower() != _TOKEN_PREFIX:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Expected Bearer.",
        )
    return _decode_token(credentials.credentials)


def get_current_user(
    token_payload: Dict[str, Any] = Depends(verify_bearer_token),
) -> UserInfo:
    """Extract and return the current user from a verified JWT.

    This dependency requires a valid Bearer token.
    """
    user_id: str = token_payload.get("sub", "unknown")
    username: str | None = token_payload.get("username")
    roles: List[str] = token_payload.get("roles", [])
    permissions: List[str] = token_payload.get("permissions", [])

    # If no explicit permissions in token, derive them from roles.
    if not permissions and roles:
        permissions = sorted(_get_permissions_for_roles(roles))

    return UserInfo(
        id=user_id,
        username=username,
        roles=roles,
        permissions=permissions,
        extra={k: v for k, v in token_payload.items() if k not in {"sub", "username", "roles", "permissions"}},
    )


def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(optional_bearer_scheme),
) -> UserInfo | None:
    """Like :func:`get_current_user`, but returns ``None`` when no token is provided.

    Useful for endpoints that behave differently for authenticated users
    but do not strictly require authentication.
    """
    if credentials is None:
        return None
    try:
        payload = _decode_token(credentials.credentials)
        return get_current_user(token_payload=payload)
    except HTTPException:
        return None


def get_current_user_id(
    user: UserInfo = Depends(get_current_user),
) -> str:
    """Return the ID of the authenticated user."""
    return user.id


def get_admin_user(
    user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    """Require the current user to have the ``admin`` role.

    Raises 403 if the user is not an admin.
    """
    if "admin" not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


# ---------------------------------------------------------------------------
# API‑Key verification
# ---------------------------------------------------------------------------

def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Verify that the request carries a valid API key.

    Returns the key itself if valid; raises 403 otherwise.
    """
    expected_key = _get_api_key()
    # In development / if no key is configured, we skip enforcement.
    if expected_key is None:
        logger.debug("No API key configured; skipping validation.")
        return api_key or "development-key"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is missing.",
        )
    if api_key != expected_key:
        logger.warning("Invalid API key provided.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key


# ---------------------------------------------------------------------------
# Authorisation factories (permissions / roles)
# ---------------------------------------------------------------------------

def require_permissions(*required_permissions: str) -> Callable[..., UserInfo]:
    """Return a dependency that requires the user to have **all** listed permissions.

    Usage::

        @router.get("/admin")
        async def admin_panel(user: UserInfo = Depends(require_permissions("manage:system"))):
            ...
    """

    def dependency(
        user: UserInfo = Depends(get_current_user),
    ) -> UserInfo:
        if "*" in user.permissions:
            return user
        missing = [p for p in required_permissions if p not in user.permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}.",
            )
        return user

    return dependency


def require_roles(*required_roles: str) -> Callable[..., UserInfo]:
    """Return a dependency that requires the user to have **at least one** of the listed roles.

    Usage::

        @router.get("/tools/manage")
        async def manage_tools(user: UserInfo = Depends(require_roles("admin", "operator"))):
            ...
    """

    def dependency(
        user: UserInfo = Depends(get_current_user),
    ) -> UserInfo:
        if not set(user.roles) & set(required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(required_roles)}.",
            )
        return user

    return dependency