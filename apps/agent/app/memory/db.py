"""Database Abstraction and SQLite Storage Engine for YANA."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import settings
from app.logger import logger

# Initial schema migration script
SCHEMA_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        summary TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS task_steps (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        status TEXT NOT NULL,
        arguments TEXT,
        output TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks (id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        task_id TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        metadata TEXT,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
    );
    """,
]


class DatabaseManager:
    """Manages SQLite connections and schema initialization with migration support."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.storage_path

    async def initialize(self) -> None:
        """Create database directory and apply baseline migrations."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            for statement in SCHEMA_MIGRATIONS:
                await db.executescript(statement)
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Obtain an active database connection within an async context."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db


# Global database manager
db_manager = DatabaseManager()
