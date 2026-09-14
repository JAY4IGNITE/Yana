"""Repository abstractions for tasks and conversations."""

from typing import Any

from app.memory.db import DatabaseManager, db_manager


class TaskRepository:
    """Persists and queries tasks in the SQLite database."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or db_manager

    async def save_task(self, task_id: str, description: str, status: str, created_at: str) -> None:
        async with await self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO tasks (id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, description, status, created_at, created_at),
            )
            await conn.commit()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with await self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, description, status, created_at, updated_at, summary
                FROM tasks WHERE id = ?
                """,
                (task_id,),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


task_repository = TaskRepository()
