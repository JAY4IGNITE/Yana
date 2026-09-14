"""Repository abstractions for tasks and conversations."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.ai.models import (
    Conversation,
    ConversationSummary,
    Message,
    MessageMetadata,
    MessageRole,
)
from app.memory.db import DatabaseManager, db_manager


class TaskRepository:
    """Persists and queries tasks in the SQLite database."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or db_manager

    async def save_task(self, task_id: str, description: str, status: str, created_at: str) -> None:
        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO tasks (id, description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (task_id, description, status, created_at, created_at),
            )
            await conn.commit()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        async with self.db.get_connection() as conn:
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


class ConversationRepository:
    """Persists and queries conversations and structured messages."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or db_manager

    async def create_conversation(
        self,
        title: str = "New Chat",
        conversation_id: str | None = None,
    ) -> Conversation:
        """Create a new conversation session."""
        cid = conversation_id or str(uuid4())
        now = datetime.now(UTC).isoformat()
        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (cid, title, now, now),
            )
            await conn.commit()

        return Conversation(id=cid, title=title, created_at=now, updated_at=now, messages=[])

    async def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Get full conversation with its messages."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            c = Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                messages=[],
            )

            msg_cursor = await conn.execute(
                """
                SELECT id, conversation_id, role, content, timestamp, metadata
                FROM messages WHERE conversation_id = ?
                ORDER BY timestamp ASC
                """,
                (conversation_id,),
            )
            msg_rows = await msg_cursor.fetchall()
            messages: list[Message] = []
            for m in msg_rows:
                meta_dict = json.loads(m["metadata"]) if m["metadata"] else {}
                messages.append(
                    Message(
                        id=m["id"],
                        conversation_id=m["conversation_id"],
                        role=MessageRole(m["role"]),
                        content=m["content"],
                        timestamp=m["timestamp"],
                        metadata=MessageMetadata(**meta_dict),
                    )
                )
            c.messages = messages
            return c

    async def list_conversations(self) -> list[ConversationSummary]:
        """List summary of all conversation sessions."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """
            )
            rows = await cursor.fetchall()
            return [
                ConversationSummary(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=row["message_count"],
                )
                for row in rows
            ]

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages."""
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            await conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            await conn.commit()

    async def clear_messages(self, conversation_id: str) -> None:
        """Clear all messages inside a conversation without deleting the conversation."""
        now = datetime.now(UTC).isoformat()
        async with self.db.get_connection() as conn:
            await conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            await conn.commit()

    async def add_message(self, message: Message) -> None:
        """Add a structured message to a conversation."""
        now = datetime.now(UTC).isoformat()
        meta_json = json.dumps(message.metadata.model_dump(by_alias=True))
        async with self.db.get_connection() as conn:
            # Ensure conversation exists
            await conn.execute(
                """
                INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (message.conversation_id, "New Chat", message.timestamp, now),
            )
            # Insert message
            await conn.execute(
                """
                INSERT OR REPLACE INTO messages
                (id, conversation_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.conversation_id,
                    message.role.value,
                    message.content,
                    message.timestamp,
                    meta_json,
                ),
            )
            # Update conversation timestamp
            await conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, message.conversation_id),
            )
            await conn.commit()

    async def get_messages(self, conversation_id: str, limit: int = 100) -> list[Message]:
        """Fetch messages for a conversation up to limit."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, conversation_id, role, content, timestamp, metadata
                FROM messages WHERE conversation_id = ?
                ORDER BY timestamp ASC LIMIT ?
                """,
                (conversation_id, limit),
            )
            rows = await cursor.fetchall()
            messages: list[Message] = []
            for m in rows:
                meta_dict = json.loads(m["metadata"]) if m["metadata"] else {}
                messages.append(
                    Message(
                        id=m["id"],
                        conversation_id=m["conversation_id"],
                        role=MessageRole(m["role"]),
                        content=m["content"],
                        timestamp=m["timestamp"],
                        metadata=MessageMetadata(**meta_dict),
                    )
                )
            return messages


task_repository = TaskRepository()
conversation_repository = ConversationRepository()
