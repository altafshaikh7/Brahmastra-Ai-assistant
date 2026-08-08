"""MongoDB dependency module for FastAPI.

This module exposes singleton accessors for the shared Motor client and
application database used by services and routers. The dependency layer is
responsible only for access, lifecycle handling, and health checks.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

try:
    from datetime import UTC, datetime
except ImportError:  # Python < 3.11
    from datetime import datetime
    from datetime import timezone as _tz

    UTC = _tz.utc  # type: ignore[assignment]  # noqa: UP017
from time import perf_counter
from typing import Annotated, Final, TypedDict

import pymongo.errors
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import get_settings
from utils.logger import get_logger

logger: Final = get_logger(__name__)


@dataclass(frozen=True)
class MongoRuntimeConfig:
    """Immutable runtime configuration for the MongoDB dependency."""

    uri: str
    database_name: str
    connect_timeout_ms: int
    server_selection_timeout_ms: int
    max_pool_size: int
    min_pool_size: int
    retry_writes: bool
    retry_attempts: int
    retry_backoff_seconds: float
    ping_timeout_seconds: float
    tls: bool


class DatabaseHealth(TypedDict):
    """Structured health information for the MongoDB dependency."""

    status: str
    latency_ms: float
    database_name: str
    timestamp: str


_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None
_database_name: str | None = None
_runtime_config: MongoRuntimeConfig | None = None
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    """Return a process-wide lock used to serialize initialization."""
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def _ping_with_timeout(
    client: AsyncIOMotorClient,
    timeout_seconds: float,
) -> None:
    """Ping the MongoDB server with a bounded timeout.

    Args:
        client: The Motor client to use for the health check.
        timeout_seconds: Maximum wait time for the ping operation.

    Raises:
        asyncio.TimeoutError: If the ping takes too long.
        pymongo.errors.PyMongoError: If the server responds with a MongoDB error.
    """
    await asyncio.wait_for(client.admin.command("ping"), timeout=timeout_seconds)


async def _initialize_client_with_retries() -> AsyncIOMotorClient:
    """Create and verify the singleton client using retries and backoff."""
    global _runtime_config

    settings = get_settings()
    mongo = settings.mongodb
    runtime_config = MongoRuntimeConfig(
        uri=mongo.uri,
        database_name=mongo.database_name,
        connect_timeout_ms=mongo.connect_timeout_ms,
        server_selection_timeout_ms=mongo.server_selection_timeout_ms,
        max_pool_size=mongo.max_pool_size,
        min_pool_size=mongo.min_pool_size,
        retry_writes=mongo.retry_writes,
        retry_attempts=mongo.retry_attempts,
        retry_backoff_seconds=mongo.retry_backoff_seconds,
        ping_timeout_seconds=mongo.ping_timeout_seconds,
        tls=mongo.tls,
    )
    _runtime_config = runtime_config

    logger.info(
        "Initializing MongoDB client for database '%s' with pool %d-%d.",
        runtime_config.database_name,
        runtime_config.min_pool_size,
        runtime_config.max_pool_size,
    )

    last_error: BaseException | None = None

    for attempt in range(1, runtime_config.retry_attempts + 1):
        try:
            client = AsyncIOMotorClient(
                runtime_config.uri,
                connectTimeoutMS=runtime_config.connect_timeout_ms,
                serverSelectionTimeoutMS=runtime_config.server_selection_timeout_ms,
                maxPoolSize=runtime_config.max_pool_size,
                minPoolSize=runtime_config.min_pool_size,
                retryWrites=runtime_config.retry_writes,
                tls=runtime_config.tls,
            )
            await _ping_with_timeout(client, runtime_config.ping_timeout_seconds)
            return client
        except (
            TimeoutError,
            pymongo.errors.ConnectionFailure,
            pymongo.errors.ServerSelectionTimeoutError,
            pymongo.errors.OperationFailure,
            pymongo.errors.ConfigurationError,
        ) as exc:
            last_error = exc
            if attempt == runtime_config.retry_attempts:
                break
            backoff_seconds = runtime_config.retry_backoff_seconds
            logger.warning(
                "MongoDB initialization attempt %d/%d failed; retrying in %.2fs.",
                attempt,
                runtime_config.retry_attempts,
                backoff_seconds,
            )
            await asyncio.sleep(backoff_seconds)

    if isinstance(last_error, pymongo.errors.ConfigurationError):
        logger.exception("MongoDB configuration error during initialization.")
        raise RuntimeError(  # noqa: TRY004
            "MongoDB configuration is invalid."
        ) from last_error
    if isinstance(last_error, asyncio.TimeoutError):
        logger.exception("MongoDB initialization timed out.")
        raise RuntimeError(  # noqa: TRY004
            "MongoDB initialization timed out."
        ) from last_error
    logger.exception(
        "MongoDB initialization failed after %d attempts.",
        runtime_config.retry_attempts,
    )
    raise RuntimeError("MongoDB initialization failed.") from last_error


async def init_mongo_client() -> AsyncIOMotorClient:
    """Initialize and cache the singleton Motor client.

    Purpose:
        Ensure the application uses one shared MongoDB client for the full
        process lifetime.

    Parameters:
        None.

    Returns:
        The initialized asynchronous Motor client.

    Raises:
        RuntimeError: If the configuration is invalid or initialization fails.

    Usage:
        client = await init_mongo_client()

    Notes:
        This function is safe for concurrent startup calls because it serializes
        initialization with an asyncio lock.
    """
    global _client, _database, _database_name

    if _client is not None:
        logger.debug("MongoDB client already initialized; reusing singleton client.")
        return _client

    lock = _get_init_lock()
    async with lock:
        if _client is not None:
            logger.debug(
                "MongoDB client already initialized; reusing singleton client."
            )
            return _client

        client = await _initialize_client_with_retries()
        _client = client
        _database_name = _runtime_config.database_name if _runtime_config else None
        _database = _client[_database_name] if _database_name else None
        logger.info("MongoDB client initialized successfully.")
        return _client


async def close_mongo_connection() -> None:
    """Gracefully close the singleton MongoDB client.

    Purpose:
        Release the singleton connection pool during application shutdown.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        None.

    Usage:
        await close_mongo_connection()
    """
    global _client, _database, _database_name

    if _client is None:
        return

    logger.info("Closing MongoDB client connection pool.")
    _client.close()
    _client = None
    _database = None
    _database_name = None


def get_mongo_client() -> AsyncIOMotorClient:
    """Return the singleton Motor client.

    Purpose:
        Provide a dependency-safe accessor for the shared MongoDB client.

    Parameters:
        None.

    Returns:
        The initialized asynchronous Motor client.

    Raises:
        RuntimeError: If the client has not been initialized yet.

    Usage:
        client = get_mongo_client()
    """
    if _client is None:
        raise RuntimeError(
            "MongoDB client is not initialized. Ensure initialize_mongo_client() "
            "is called during application startup."
        )
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the singleton application database handle.

    Purpose:
        Provide the primary dependency used by routers and services.

    Parameters:
        None.

    Returns:
        The initialized asynchronous database object.

    Raises:
        RuntimeError: If the client has not been initialized yet.

    Usage:
        database = get_database()
    """
    global _database, _database_name

    if _database is None:
        if _client is None:
            raise RuntimeError(
                "MongoDB database is not available. Ensure init_mongo_client() "
                "is called during application startup."
            )
        if _database_name is None and _runtime_config is not None:
            _database_name = _runtime_config.database_name
        if _database_name is None:
            raise RuntimeError("MongoDB database name is not available.")
        _database = _client[_database_name]

    return _database


async def get_database_health() -> DatabaseHealth:
    """Return structured MongoDB health information.

    Purpose:
        Support startup diagnostics and health endpoints with richer observability.

    Parameters:
        None.

    Returns:
        A structured dictionary containing the health status, latency, database
        name, and timestamp.

    Raises:
        None.

    Usage:
        health = await get_database_health()
    """
    database_name = _database_name or ""
    timestamp = datetime.now(UTC).isoformat()

    try:
        client = get_mongo_client()
        started_at = perf_counter()
        await _ping_with_timeout(
            client, _runtime_config.ping_timeout_seconds if _runtime_config else 5.0
        )
        latency_ms = (perf_counter() - started_at) * 1000.0
        logger.debug("MongoDB health check succeeded.")
        return {
            "status": "ok",
            "latency_ms": round(latency_ms, 3),
            "database_name": database_name,
            "timestamp": timestamp,
        }
    except (TimeoutError, pymongo.errors.PyMongoError, RuntimeError) as exc:
        logger.warning("MongoDB health check failed: %s", exc)
        return {
            "status": "degraded",
            "latency_ms": 0.0,
            "database_name": database_name,
            "timestamp": timestamp,
        }


async def ping_database() -> bool:
    """Verify MongoDB connectivity by executing the ping command.

    Purpose:
        Provide a boolean compatibility health check for existing callers.

    Parameters:
        None.

    Returns:
        True if the database responds successfully, otherwise False.

    Raises:
        None.

    Usage:
        is_ready = await ping_database()
    """
    health = await get_database_health()
    return health["status"] == "ok"


DatabaseDep = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
ClientDep = Annotated[AsyncIOMotorClient, Depends(get_mongo_client)]
