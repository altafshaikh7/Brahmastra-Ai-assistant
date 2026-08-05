"""Production-grade security utilities for the Brahmastra AI project."""

from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from typing import Annotated, Any, Callable, Iterable, Mapping, Optional, Sequence

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from core.config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SecurityError(Exception):
    """Base class for security-related failures."""


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""


class TokenError(SecurityError):
    """Raised when a JWT token is invalid, expired, or malformed."""


class APIKeyError(SecurityError):
    """Raised when an API key is missing or invalid."""


class Role(str, Enum):
    """Canonical application roles."""

    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class Permission(str, Enum):
    """Canonical application permissions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMINISTER = "administer"


ROLE_HIERARCHY: dict[Role, set[Role]] = {
    Role.SUPERADMIN: {Role.ADMIN, Role.USER, Role.GUEST},
    Role.ADMIN: {Role.USER, Role.GUEST},
    Role.USER: {Role.GUEST},
    Role.GUEST: set(),
}

_PWD_CONTEXT = CryptContext(schemes=["bcrypt", "argon2", "pbkdf2_sha256"], deprecated="auto")
_OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _get_jwt_secret() -> str:
    secret = settings.jwt.secret_key
    if hasattr(secret, "get_secret_value"):
        secret_value = secret.get_secret_value()
    else:
        secret_value = str(secret)
    if not secret_value or secret_value == "change-me":
        raise AuthenticationError("JWT secret is not configured")
    return secret_value


def _get_default_issuer() -> str:
    return settings.application.title.replace(" ", "-").lower()


def _get_default_audience() -> str:
    return f"{_get_default_issuer()}-api"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    raise TokenError("Token timestamp claim is invalid")


def _coerce_roles(value: Any) -> set[Role]:
    if value is None:
        return set()
    if isinstance(value, (str, Role)):
        return {Role(str(value).lower())}
    if isinstance(value, Iterable):
        roles = set()
        for item in value:
            if item is None:
                continue
            roles.add(Role(str(item).lower()))
        return roles
    raise AuthorizationError("User roles must be a string or iterable of strings")


def _coerce_permissions(value: Any) -> set[Permission]:
    if value is None:
        return set()
    if isinstance(value, (str, Permission)):
        return {Permission(str(value).lower())}
    if isinstance(value, Iterable):
        permissions = set()
        for item in value:
            if item is None:
                continue
            permissions.add(Permission(str(item).lower()))
        return permissions
    raise AuthorizationError("User permissions must be a string or iterable of strings")


def hash_password(password: str) -> str:
    """Hash a plain-text password with a modern adaptive hash."""
    if not password:
        raise ValueError("Password cannot be empty")
    return _PWD_CONTEXT.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password and upgrade the hash when the algorithm changes."""
    if not plain_password:
        raise ValueError("Password cannot be empty")
    if not hashed_password:
        raise ValueError("Hashed password cannot be empty")
    verified, updated_hash = _PWD_CONTEXT.verify_and_update(plain_password, hashed_password)
    if verified and updated_hash:
        logger.debug("Password hash upgraded", extra={"event": "password_rehash"})
    return verified


def create_access_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Mapping[str, Any]] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> str:
    """Create a signed JWT access token with standard and custom claims."""
    if not subject:
        raise AuthenticationError("Token subject is required")
    now = _utc_now()
    ttl = expires_delta or timedelta(minutes=settings.jwt.access_token_expire_minutes)
    expiry = now + ttl
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expiry.timestamp()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "iss": issuer or _get_default_issuer(),
        "aud": audience or _get_default_audience(),
        "jti": secrets.token_urlsafe(16),
        "type": "access",
    }
    if extra_claims:
        payload.update(dict(extra_claims))
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.jwt.algorithm)


def create_refresh_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Mapping[str, Any]] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> str:
    """Create a signed JWT refresh token with standard and custom claims."""
    if not subject:
        raise AuthenticationError("Token subject is required")
    now = _utc_now()
    ttl = expires_delta or timedelta(days=settings.jwt.refresh_token_expire_days)
    expiry = now + ttl
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expiry.timestamp()),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "iss": issuer or _get_default_issuer(),
        "aud": audience or _get_default_audience(),
        "jti": secrets.token_urlsafe(16),
        "type": "refresh",
    }
    if extra_claims:
        payload.update(dict(extra_claims))
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.jwt.algorithm)


def decode_token(
    token: str,
    *,
    expected_type: Optional[str] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> dict[str, Any]:
    """Decode and validate a JWT token, raising security-specific errors."""
    if not token or not str(token).strip():
        raise TokenError("Token is required")
    normalized = str(token).strip()
    if normalized.count(".") != 2:
        raise TokenError("Malformed token")
    try:
        payload = jwt.decode(
            normalized,
            _get_jwt_secret(),
            algorithms=[settings.jwt.algorithm],
            audience=audience or _get_default_audience(),
            issuer=issuer or _get_default_issuer(),
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.InvalidSignatureError as exc:
        raise TokenError("Invalid token signature") from exc
    except jwt.InvalidIssuerError as exc:
        raise TokenError("Invalid token issuer") from exc
    except jwt.InvalidAudienceError as exc:
        raise TokenError("Invalid token audience") from exc
    except jwt.ImmatureSignatureError as exc:
        raise TokenError("Token is not yet valid") from exc
    except jwt.DecodeError as exc:
        raise TokenError("Malformed token") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise TokenError(f"Token is missing required claim: {exc.claim}") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token validation failed") from exc

    if not isinstance(payload, dict):
        raise TokenError("Token payload is invalid")

    now = _utc_now()
    exp = payload.get("exp")
    if exp is None:
        raise TokenError("Token is missing expiration")
    if _normalize_datetime(exp) < now:
        raise TokenError("Token has expired")

    iat = payload.get("iat")
    if iat is None:
        raise TokenError("Token is missing issued-at")
    issued_at = _normalize_datetime(iat)
    if issued_at > now + timedelta(seconds=5):
        raise TokenError("Token was issued in the future")

    nbf = payload.get("nbf")
    if nbf is None:
        raise TokenError("Token is missing not-before")
    not_before = _normalize_datetime(nbf)
    if not_before > now + timedelta(seconds=5):
        raise TokenError("Token is not yet valid")

    if not payload.get("sub"):
        raise TokenError("Token is missing subject")
    if not payload.get("iss"):
        raise TokenError("Token is missing issuer")
    if not payload.get("aud"):
        raise TokenError("Token is missing audience")
    if not payload.get("jti"):
        raise TokenError("Token is missing identifier")
    if not payload.get("type"):
        raise TokenError("Token is missing type")
    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"Token type {payload.get('type')} is not allowed")
    return payload


def validate_token(
    token: str,
    *,
    expected_type: Optional[str] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> dict[str, Any]:
    """Validate a JWT token and return its payload."""
    return decode_token(token, expected_type=expected_type, audience=audience, issuer=issuer)


def get_token_subject(token: str) -> str:
    """Return the subject claim from a validated token."""
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token is missing subject")
    return str(subject)


def extract_bearer_token(authorization: str | None) -> str:
    """Extract a bearer token from an Authorization header."""
    if not authorization:
        raise AuthenticationError("Authorization header is missing")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise AuthenticationError("Authorization header must use Bearer scheme")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise AuthenticationError("Bearer token is empty")
    return token


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    if length <= 0:
        raise ValueError("Token length must be positive")
    return secrets.token_urlsafe(length)


def compare_digest(left: str, right: str) -> bool:
    """Compare two strings using a constant-time digest comparison."""
    return hmac.compare_digest(left, right)


def extract_api_key(headers: Mapping[str, str] | None) -> str:
    """Extract an API key from the X-API-Key header."""
    if not headers:
        raise APIKeyError("Missing request headers")
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    if not api_key:
        raise APIKeyError("Missing X-API-Key header")
    return str(api_key).strip()


def validate_api_key(api_key: str | None, expected_api_key: str | None) -> str:
    """Validate an API key using constant-time comparison."""
    if not api_key:
        raise APIKeyError("API key is required")
    if not expected_api_key:
        raise APIKeyError("API key is not configured")
    if not compare_digest(api_key.strip(), expected_api_key.strip()):
        raise APIKeyError("Invalid API key")
    return api_key.strip()


def has_role(user: Any, required_role: Role | str) -> bool:
    """Return whether the user or role collection includes the required role."""
    if user is None:
        return False
    if isinstance(user, (str, Role)):
        roles = _coerce_roles(user)
    else:
        roles = _coerce_roles(getattr(user, "roles", None) or getattr(user, "role", None))
    required = Role(str(required_role).lower())
    if required in roles:
        return True
    for role in roles:
        if required in ROLE_HIERARCHY.get(role, set()):
            return True
    return False


def has_any_role(user: Any, required_roles: Sequence[Role | str] | None) -> bool:
    """Return whether the user has any of the required roles."""
    if not required_roles:
        return False
    return any(has_role(user, role) for role in required_roles)


def has_permission(user: Any, required_permission: Permission | str) -> bool:
    """Return whether the user or permission collection includes the required permission."""
    if user is None:
        return False
    if isinstance(user, (str, Permission)):
        permissions = _coerce_permissions(user)
    else:
        permissions = _coerce_permissions(getattr(user, "permissions", None))
    required = Permission(str(required_permission).lower())
    return required in permissions


def has_any_permission(user: Any, required_permissions: Sequence[Permission | str] | None) -> bool:
    """Return whether the user has any of the required permissions."""
    if not required_permissions:
        return False
    return any(has_permission(user, permission) for permission in required_permissions)


def require_roles(*required_roles: Role | str):
    """Decorator enforcing one or more roles on the wrapped callable."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = kwargs.get("current_user") or kwargs.get("user")
            if user is None and args:
                user = args[0]
            if not has_any_role(user, required_roles):
                raise AuthorizationError("Insufficient privileges")
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permissions(*required_permissions: Permission | str):
    """Decorator enforcing one or more permissions on the wrapped callable."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = kwargs.get("current_user") or kwargs.get("user")
            if user is None and args:
                user = args[0]
            if not has_any_permission(user, required_permissions):
                raise AuthorizationError("Insufficient permissions")
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def get_current_user(token: Annotated[str, Depends(_OAUTH2_SCHEME)]) -> dict[str, Any]:
    """FastAPI dependency returning the validated JWT claims for the current user."""
    try:
        return decode_token(token)
    except SecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_admin(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """FastAPI dependency enforcing administrator privileges."""
    if not has_any_role(current_user, [Role.ADMIN, Role.SUPERADMIN]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


async def get_current_active_user(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """FastAPI dependency enforcing an active account state."""
    if current_user.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return current_user


CurrentUserDep = Annotated[dict[str, Any], Depends(get_current_user)]
CurrentAdminDep = Annotated[dict[str, Any], Depends(get_current_admin)]
CurrentActiveUserDep = Annotated[dict[str, Any], Depends(get_current_active_user)]
OAuth2Scheme = _OAUTH2_SCHEME


__all__ = [
    "APIKeyError",
    "AuthenticationError",
    "AuthorizationError",
    "CurrentActiveUserDep",
    "CurrentAdminDep",
    "CurrentUserDep",
    "OAuth2Scheme",
    "Permission",
    "Role",
    "SecurityError",
    "TokenError",
    "compare_digest",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "extract_api_key",
    "extract_bearer_token",
    "generate_secure_token",
    "hash_password",
    "has_any_permission",
    "has_any_role",
    "has_permission",
    "has_role",
    "require_permissions",
    "require_roles",
    "validate_api_key",
    "validate_token",
    "verify_password",
]
