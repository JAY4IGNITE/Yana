"""PostgreSQL Storage Adapter for enterprise and multi-session persistence."""

from typing import Any

from app.config import settings
from app.logger import logger


class PostgresDatabaseManager:
    """Async PostgreSQL client manager utilizing asyncpg connection pooling."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or settings.postgres_dsn.get_secret_value()
        self._pool: Any = None
        self._connected: bool = False

    async def connect(self) -> bool:
        """Attempt connection to PostgreSQL cluster."""
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=5, timeout=3.0)
            self._connected = True
            logger.info("Successfully connected to PostgreSQL cluster.")
            await self._init_schema()
            return True
        except Exception as e:
            logger.warning(
                "PostgreSQL connection unavailable (%s). Falling back to SQLite.", e
            )
            self._connected = False
            return False

    async def _init_schema(self) -> None:
        """Create PostgreSQL tables if they do not exist."""
        if not self._connected or not self._pool:
            return

        schema_sql = """
        CREATE TABLE IF NOT EXISTS pg_memories (
            id VARCHAR(64) PRIMARY KEY,
            key VARCHAR(256) NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(64) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pg_memories_key ON pg_memories (key);
        CREATE INDEX IF NOT EXISTS idx_pg_memories_category ON pg_memories (category);
        """
        async with self._pool.acquire() as conn:
            await conn.execute(schema_sql)

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected


postgres_manager = PostgresDatabaseManager()
