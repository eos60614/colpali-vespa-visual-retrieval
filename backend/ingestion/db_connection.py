"""
PostgreSQL database connection management using asyncpg.
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlparse

import asyncpg

from backend.ingestion.exceptions import ConnectionError


@dataclass
class ConnectionConfig:
    """Database connection configuration."""

    host: str
    port: int
    database: str
    user: str
    password: str
    ssl: bool = True
    pool_size: int = 5

    @classmethod
    def from_url(cls, url: str) -> "ConnectionConfig":
        """Parse PostgreSQL connection URL.

        Supports format: postgresql://user:password@host:port/database
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError(f"Invalid scheme: {parsed.scheme}. Expected postgresql://")

        if not parsed.hostname:
            raise ValueError("Missing hostname in connection URL")

        return cls(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") if parsed.path else "",
            user=parsed.username or "",
            password=parsed.password or "",
            ssl="sslmode" not in parsed.query or "disable" not in parsed.query,
        )


class DatabaseConnection:
    """Async PostgreSQL connection manager with connection pooling."""

    def __init__(self, config: ConnectionConfig, logger: Optional[logging.Logger] = None):
        """Initialize connection with config."""
        self._config = config
        self._pool: Optional[asyncpg.Pool] = None
        self._logger = logger or logging.getLogger(__name__)

    async def connect(self) -> None:
        """Establish connection pool."""
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                ssl="prefer" if self._config.ssl else "disable",
                min_size=1,
                max_size=self._config.pool_size,
            )
            self._logger.info(
                f"Connected to database {self._config.database} at {self._config.host}"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}") from e

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._logger.info("Database connection closed")

    async def execute(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """Execute query and return results as list of dicts."""
        if self._pool is None:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            raise ConnectionError(f"Query execution failed: {e}") from e

    async def execute_many(self, query: str, args_list: list[tuple]) -> int:
        """Execute query for multiple parameter sets. Returns row count."""
        if self._pool is None:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                result = await conn.executemany(query, args_list)
                return len(args_list)
        except asyncpg.PostgresError as e:
            raise ConnectionError(f"Batch execution failed: {e}") from e

    async def stream(
        self, query: str, *args: Any, batch_size: int = 1000
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Stream query results in batches."""
        if self._pool is None:
            raise ConnectionError("Not connected to database")

        try:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    cursor = await conn.cursor(query, *args)
                    while True:
                        rows = await cursor.fetch(batch_size)
                        if not rows:
                            break
                        yield [dict(row) for row in rows]
        except asyncpg.PostgresError as e:
            raise ConnectionError(f"Stream query failed: {e}") from e

    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        if self._pool is None:
            raise ConnectionError("Not connected to database")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._pool is not None and not self._pool._closed
