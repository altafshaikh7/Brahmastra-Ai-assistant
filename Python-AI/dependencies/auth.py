# dependencies/auth.py
"""
FastAPI dependency injection layer for authentication and authorization.

All business logic – JWT handling, API‑key validation, role/permission
enforcement – is owned by ``core.security``.  This module *only* adapts
those primitives into ``Depends`` / ``Security`` callables and maps
security‑related exceptions into HTTP responses.

Conforms to Clean Architecture: no cryptographic, authorisation, or
token validation logic lives here.  Every security operation is delegated
to ``core.security``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Annotated, Final, NoReturn

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from schemas.user import UserInfo

from core.config import Settings, get_settings
from core.security import (
    AuthenticationError,
    AuthorizationError,
    SecurityError,
    TokenError,
    check_user_is_active,
    has_any_role,
    has_permission,
    validate_token,
)
from core.security import (
    validate_api_key as _validate_api_key,
)

# ---------------------------------------------------------------------------
# Lazy configuration access (no import‑time calls to get_settings())
# ---------------------------------------------------------------------------

_settings: Settings | None = None


def _get_settings() -> Settings:
    """Thread‑safe, cached access to application settings."""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


@lru_cache
def _get_token_prefix() -> str:
    """Return the lower‑cased token prefix (e.g. ``bearer``)."""
    return _get_settings().jwt.token_prefix.lower()


@lru_cache
def _get_api_key_header_name() -> str:
    """Return the name of the API‑key HTTP header."""
    return _get_settings().security.api_key_header


# ---------------------------------------------------------------------------
# Security scheme factories (no module‑level instantiation)
# ---------------------------------------------------------------------------


def _bearer_scheme() -> HTTPBearer:
    return HTTPBearer(auto_error=False)


def _optional_bearer_scheme() -> HTTPBearer:
    return HTTPBearer(auto_error=False)


def _api_key_scheme() -> APIKeyHeader:
    return APIKeyHeader(name=_get_api_key_header_name(), auto_error=False)


# ---------------------------------------------------------------------------
# Strongly‑typed JWT claims
# ---------------------------------------------------------------------------

from typing import TypedDict


class JWTClaims(TypedDict, total=False):
    """Representation of a decoded and validated JWT payload."""

    sub: str
    username: str
    is_active: bool
    roles: list[str]
    permissions: list[str]


# ---------------------------------------------------------------------------
# Exception mapping (single central converter)
# ---------------------------------------------------------------------------


def _security_exception_to_http(
    exc: SecurityError,
    extra_headers: dict[str, str] | None = None,
) -> NoReturn:
    """Translate a ``SecurityError`` from ``core.security`` into an ``HTTPException``.

    Status codes are derived from the exception type:
    - ``TokenError``, ``AuthenticationError`` → 401
    - ``AuthorizationError`` → 403
    - Any other ``SecurityError`` → 403 (fallback)

    If the original exception carries an ``http_headers`` attribute (a dict),
    those headers are merged into the response.
    """
    if isinstance(exc, (TokenError, AuthenticationError)):
        status_code = status.HTTP_401_UNAUTHORIZED
    else:
        status_code = status.HTTP_403_FORBIDDEN

    headers = {}
    if extra_headers:
        headers.update(extra_headers)
    if hasattr(exc, "http_headers"):
        headers.update(exc.http_headers)

    raise HTTPException(
        status_code=status_code, detail=str(exc), headers=headers or None
    )


# ---------------------------------------------------------------------------
# Payload → UserInfo adapter
# ---------------------------------------------------------------------------


def _claims_to_user(claims: JWTClaims) -> UserInfo:
    """Build a ``UserInfo`` instance from validated JWT claims."""
    return UserInfo(
        id=claims.get("sub", ""),
        username=claims.get("username"),
        is_active=claims.get("is_active", True),
        roles=claims.get("roles", []),
        permissions=claims.get("permissions", []),
        extra={
            k: v
            for k, v in claims.items()
            if k not in {"sub", "username", "is_active", "roles", "permissions"}
        },
    )


# ---------------------------------------------------------------------------
# Public dependency callables
# ---------------------------------------------------------------------------


def verify_bearer_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_bearer_scheme),
    ] = None,
) -> JWTClaims:
    """Verify the presence and validity of a Bearer token.

    Parameters
    ----------
    credentials : Optional[HTTPAuthorizationCredentials]
        Extracted by ``HTTPBearer`` from the ``Authorization`` header.

    Returns
    -------
    JWTClaims
        The validated JWT claims dictionary.

    Raises
    ------
    HTTPException (401)
        If the token is missing, has an unsupported scheme, or is
        considered invalid by ``core.security.validate_token``.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.scheme.lower() != _get_token_prefix():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication scheme. Expected {_get_token_prefix()}.",
        )
    try:
        # validate_token returns the decoded payload (a dict) – cast to JWTClaims
        return validate_token(credentials.credentials)  # type: ignore[return-value]
    except (TokenError, AuthenticationError) as exc:
        _security_exception_to_http(exc)
        raise  # unreachable, kept for type checker


def get_current_user(
    claims: Annotated[JWTClaims, Depends(verify_bearer_token)],
) -> UserInfo:
    """Extract the currently authenticated user from a valid JWT.

    Parameters
    ----------
    claims : JWTClaims
        The validated claims dictionary returned by
        :func:`verify_bearer_token`.

    Returns
    -------
    UserInfo
        The user principal.
    """
    return _claims_to_user(claims)


def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_optional_bearer_scheme),
    ] = None,
) -> UserInfo | None:
    """Return the authenticated user if a valid token is present, else ``None``.

    Unlike :func:`get_current_user`, missing or invalid tokens do **not**
    cause an error.  Useful for endpoints that optionally benefit from
    authentication.

    Parameters
    ----------
    credentials : Optional[HTTPAuthorizationCredentials]
        Extracted by ``HTTPBearer`` (auto_error=False).

    Returns
    -------
    Optional[UserInfo]
        The user principal or ``None``.
    """
    if credentials is None:
        return None
    try:
        claims = validate_token(credentials.credentials)  # type: ignore[return-value]
        return _claims_to_user(claims)
    except (TokenError, AuthenticationError):
        return None


def get_current_user_id(
    user: Annotated[UserInfo, Depends(get_current_user)],
) -> str:
    """Extract the unique identifier of the authenticated user.

    Parameters
    ----------
    user : UserInfo
        The authenticated user.

    Returns
    -------
    str
        The user id (``sub`` claim).
    """
    return user.id


def get_current_active_user(
    user: Annotated[UserInfo, Depends(get_current_user)],
) -> UserInfo:
    """Require that the authenticated user is active.

    Parameters
    ----------
    user : UserInfo
        The authenticated user.

    Returns
    -------
    UserInfo
        The same user instance if active.

    Raises
    ------
    HTTPException (403)
        If the user is inactive (as determined by
        ``core.security.check_user_is_active``).
    """
    try:
        check_user_is_active(user)
    except AuthorizationError as exc:
        _security_exception_to_http(exc)
    return user


def get_admin_user(
    user: Annotated[UserInfo, Depends(get_current_user)],
) -> UserInfo:
    """Require that the user holds the ``admin`` role.

    Parameters
    ----------
    user : UserInfo
        The authenticated user.

    Returns
    -------
    UserInfo
        The user if they are an admin.

    Raises
    ------
    HTTPException (403)
        If the user does not have the ``admin`` role.
    """
    # Role check delegated to core.security
    if not has_any_role(user, ["admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


# ---------------------------------------------------------------------------
# API‑Key verification
# ---------------------------------------------------------------------------


def verify_api_key(
    api_key: Annotated[str | None, Security(_api_key_scheme)] = None,
) -> str:
    """Verify a request‑scoped API key.

    Delegates validation to ``core.security.validate_api_key``.

    Parameters
    ----------
    api_key : Optional[str]
        The API key value extracted from the configured header.

    Returns
    -------
    str
        The validated API key.

    Raises
    ------
    HTTPException (403)
        If the key is missing or invalid.
    """
    try:
        return _validate_api_key(api_key)
    except (AuthenticationError, SecurityError) as exc:
        _security_exception_to_http(exc, extra_headers={"X-API-Key": "required"})
        raise  # unreachable


# ---------------------------------------------------------------------------
# Authorisation factories (roles and permissions)
# ---------------------------------------------------------------------------


def require_roles(*required_roles: str) -> Callable[..., UserInfo]:
    """Create a dependency that requires at least one of the given roles.

    Parameters
    ----------
    required_roles : str
        One or more role names (e.g., ``"admin"``, ``"operator"``).

    Returns
    -------
    Callable[..., UserInfo]
        A FastAPI dependency that checks the current user's roles.

    Usage::

        @router.get("/manage")
        async def manage(user = Depends(require_roles("admin", "operator"))):
            ...
    """
    role_list: Final[Sequence[str]] = list(required_roles)

    def dependency(
        user: Annotated[UserInfo, Depends(get_current_user)],
    ) -> UserInfo:
        if not has_any_role(user, role_list):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(role_list)}.",
            )
        return user

    return dependency


def require_permissions(*required_permissions: str) -> Callable[..., UserInfo]:
    """Create a dependency that requires **all** listed permissions.

    Permissions are checked by ``core.security.has_permission``.
    A user with the ``*`` wildcard permission satisfies any check
    (this logic is handled inside ``core.security``).

    Parameters
    ----------
    required_permissions : str
        One or more permission strings (e.g., ``"manage:system"``).

    Returns
    -------
    Callable[..., UserInfo]
        A FastAPI dependency that checks the current user's permissions.

    Usage::

        @router.get("/admin")
        async def admin(user = Depends(require_permissions("manage:system"))):
            ...
    """
    perm_list: Final[Sequence[str]] = list(required_permissions)

    def dependency(
        user: Annotated[UserInfo, Depends(get_current_user)],
    ) -> UserInfo:
        missing = [p for p in perm_list if not has_permission(user, p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing)}.",
            )
        return user

    return dependency


# ---------------------------------------------------------------------------
# Type aliases for common dependency signatures
# ---------------------------------------------------------------------------

CurrentUserDep = Annotated[UserInfo, Depends(get_current_user)]
CurrentActiveUserDep = Annotated[UserInfo, Depends(get_current_active_user)]
CurrentAdminDep = Annotated[UserInfo, Depends(get_admin_user)]
OptionalUserDep = Annotated[UserInfo | None, Depends(get_optional_user)]
BearerCredentialsDep = Annotated[HTTPAuthorizationCredentials, Security(_bearer_scheme)]
APIKeyDep = Annotated[str, Depends(verify_api_key)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "APIKeyDep",
    "BearerCredentialsDep",
    "CurrentActiveUserDep",
    "CurrentAdminDep",
    "CurrentUserDep",
    "OptionalUserDep",
    "UserInfo",
    "get_admin_user",
    "get_current_active_user",
    "get_current_user",
    "get_current_user_id",
    "get_optional_user",
    "require_permissions",
    "require_roles",
    "verify_api_key",
    "verify_bearer_token",
]
