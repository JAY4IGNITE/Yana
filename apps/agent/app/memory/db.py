"""Database Abstraction and SQLite Storage Engine with Migration Support for YANA."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings
from app.logger import logger

# Versioned migrations mapping integer versions to migration scripts
MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        summary TEXT
    );

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

    CREATE TABLE IF NOT EXISTS conversation_messages (
        id TEXT PRIMARY KEY,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        task_id TEXT
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

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
    2: """
    -- Phase 09 Persistent Memory Subsystem
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        key TEXT NOT NULL,
        content TEXT NOT NULL,
        memory_type TEXT NOT NULL,
        category TEXT NOT NULL,
        session_id TEXT,
        metadata TEXT,
        tags TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_memories_key ON memories (key);
    CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (memory_type);
    CREATE INDEX IF NOT EXISTS idx_memories_category ON memories (category);
    CREATE INDEX IF NOT EXISTS idx_memories_session ON memories (session_id);

    -- Dedicated Project Memory
    CREATE TABLE IF NOT EXISTS project_memories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        path TEXT NOT NULL,
        technology TEXT NOT NULL,
        description TEXT NOT NULL,
        last_used TEXT NOT NULL,
        metadata TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_projects_name ON project_memories (name);

    -- Known Windows Applications
    CREATE TABLE IF NOT EXISTS application_memories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        executable_path TEXT NOT NULL,
        category TEXT,
        last_launched TEXT NOT NULL,
        metadata TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_apps_name ON application_memories (name);

    -- Reusable Workflow Recipes
    CREATE TABLE IF NOT EXISTS workflow_memories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        trigger TEXT NOT NULL,
        description TEXT NOT NULL,
        steps TEXT NOT NULL,
        metadata TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_workflows_name ON workflow_memories (name);

    -- User Preferences
    CREATE TABLE IF NOT EXISTS user_preferences (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_pref_category ON user_preferences (category);
    """,
    3: """
    -- Phase 10: Security Audit Logging (Tamper-evident, zero secrets stored)
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        task_id TEXT,
        user_request TEXT,
        tool TEXT NOT NULL,
        arguments TEXT NOT NULL,
        permission_result TEXT NOT NULL,
        execution_result TEXT,
        verification TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_logs (task_id);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs (timestamp);
    CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_logs (tool);
    """,
}


class DatabaseManager:
    """Manages SQLite connections and schema initialization with migration support."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.storage_path

    async def get_current_version(self, db: aiosqlite.Connection) -> int:
        """Retrieve highest applied schema migration version."""
        try:
            cursor = await db.execute("SELECT MAX(version) FROM schema_version")
            row = await cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0
        except Exception:
            return 0

    async def initialize(self, target_version: int | None = None) -> None:
        """Create database directory and apply versioned migrations sequentially."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            # First ensure schema_version table exists
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await db.commit()

            current_ver = await self.get_current_version(db)
            available_versions = sorted(MIGRATIONS.keys())

            for ver in available_versions:
                if target_version is not None and ver > target_version:
                    break
                if ver > current_ver:
                    logger.info(f"Applying database schema migration v{ver}...")
                    script = MIGRATIONS[ver]
                    await db.executescript(script)
                    await db.execute(
                        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                        (ver,),
                    )
                    await db.commit()
                    logger.info(f"Database schema migration v{ver} applied successfully.")

        logger.info(f"Database initialized at {self.db_path}")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Obtain an active database connection within an async context."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def check_health(self) -> dict[str, Any]:
        """Verify database connectivity and query responsiveness."""
        import asyncio
        import sqlite3

        def _sync_check() -> dict[str, Any]:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(str(self.db_path), timeout=3.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    row = cursor.fetchone()
                    if row and row[0] == 1:
                        try:
                            cursor.execute("SELECT MAX(version) FROM schema_version")
                            vrow = cursor.fetchone()
                            ver = int(vrow[0]) if vrow and vrow[0] is not None else 0
                        except Exception:
                            ver = 0
                        return {
                            "status": "healthy",
                            "schema_version": ver,
                            "path": str(self.db_path),
                        }
                    return {
                        "status": "degraded",
                        "message": "Query failed to return expected result",
                    }
            except Exception as e:
                return {"status": "degraded", "error": str(e)}

        return await asyncio.to_thread(_sync_check)


# Global database manager
db_manager = DatabaseManager()
