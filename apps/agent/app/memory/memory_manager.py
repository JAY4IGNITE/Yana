"""Core Memory API managing Temporary, Session, and Long-Term SQLite knowledge."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.logger import logger
from app.memory.db import DatabaseManager, db_manager
from app.memory.models import (
    ApplicationMemory,
    MemoryCategory,
    MemoryItem,
    MemoryType,
    ProjectMemory,
    UserPreference,
    WorkflowMemory,
)
from app.memory.privacy import (
    sanitize_memory_content,
    sanitize_memory_metadata,
)


class MemoryManager:
    """Unified manager for local persistent memory with privacy safeguards and search."""

    def __init__(
        self,
        db: DatabaseManager | None = None,
        strict_privacy: bool = False,
    ) -> None:
        self.db = db or db_manager
        self.strict_privacy = strict_privacy
        # Temporary in-memory working context
        self._temp_context: dict[str, dict[str, Any]] = {}

    # =========================================================================
    # Tier 1: Temporary Context (Working Memory)
    # =========================================================================

    def set_temp(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Store ephemeral working context in RAM."""
        expires_at = None
        if ttl_seconds is not None:
            expires_at = datetime.now(UTC).timestamp() + ttl_seconds

        self._temp_context[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.now(UTC).isoformat(),
        }

    def get_temp(self, key: str) -> Any | None:
        """Retrieve ephemeral working context, verifying expiration."""
        item = self._temp_context.get(key)
        if not item:
            return None

        if item.get("expires_at") is not None:
            if datetime.now(UTC).timestamp() > item["expires_at"]:
                del self._temp_context[key]
                return None

        return item["value"]

    def clear_temp(self) -> None:
        """Purge all temporary working context."""
        self._temp_context.clear()

    # =========================================================================
    # General Memory CRUD & Search (Session & Long-Term)
    # =========================================================================

    async def create_memory(
        self,
        key: str,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        category: MemoryCategory = MemoryCategory.GENERAL,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        expires_at: str | None = None,
    ) -> MemoryItem:
        """Create a sanitized memory item with privacy filtering."""
        meta = metadata or {}
        tag_list = tags or []

        # Privacy guard: scan and redact credentials
        clean_content = sanitize_memory_content(content, strict=self.strict_privacy)
        clean_metadata = sanitize_memory_metadata(meta, strict=self.strict_privacy)

        now = datetime.now(UTC).isoformat()
        item = MemoryItem(
            id=str(uuid4()),
            key=key,
            content=clean_content,
            memory_type=memory_type,
            category=category,
            session_id=session_id,
            metadata=clean_metadata,
            tags=tag_list,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )

        if memory_type == MemoryType.TEMPORARY:
            self.set_temp(key, item.model_dump())
            return item

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO memories (
                    id, key, content, memory_type, category, session_id,
                    metadata, tags, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.key,
                    item.content,
                    item.memory_type.value,
                    item.category.value,
                    item.session_id,
                    json.dumps(item.metadata),
                    json.dumps(item.tags),
                    item.created_at,
                    item.updated_at,
                    item.expires_at,
                ),
            )
            await conn.commit()

        logger.info(f"Memory created: [{item.memory_type.value}] '{item.key}' ({item.id})")
        return item

    async def get_memory(self, memory_id: str) -> MemoryItem | None:
        """Retrieve a specific memory item by ID."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, key, content, memory_type, category, session_id,
                       metadata, tags, created_at, updated_at, expires_at
                FROM memories WHERE id = ?
                """,
                (memory_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return MemoryItem(
                id=row["id"],
                key=row["key"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                category=MemoryCategory(row["category"]),
                session_id=row["session_id"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                tags=json.loads(row["tags"]) if row["tags"] else [],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                expires_at=row["expires_at"],
            )

    async def get_by_key(
        self,
        key: str,
        memory_type: MemoryType | None = None,
        session_id: str | None = None,
    ) -> MemoryItem | None:
        """Retrieve the latest memory item matching a unique key."""
        if memory_type == MemoryType.TEMPORARY:
            data = self.get_temp(key)
            if data:
                return MemoryItem.model_validate(data)

        query = "SELECT * FROM memories WHERE key = ?"
        params: list[Any] = [key]

        if memory_type is not None:
            query += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY updated_at DESC LIMIT 1"

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, tuple(params))
            row = await cursor.fetchone()
            if not row:
                return None

            return MemoryItem(
                id=row["id"],
                key=row["key"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                category=MemoryCategory(row["category"]),
                session_id=row["session_id"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                tags=json.loads(row["tags"]) if row["tags"] else [],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                expires_at=row["expires_at"],
            )

    async def search_memories(
        self,
        query: str,
        category: MemoryCategory | None = None,
        memory_type: MemoryType | None = None,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryItem]:
        """Search memory content, keys, and tags using keyword/pattern matching."""
        sql = """
            SELECT id, key, content, memory_type, category, session_id,
                   metadata, tags, created_at, updated_at, expires_at
            FROM memories
            WHERE (content LIKE ? OR key LIKE ? OR tags LIKE ?)
        """
        like_pattern = f"%{query}%"
        params: list[Any] = [like_pattern, like_pattern, like_pattern]

        if category is not None:
            sql += " AND category = ?"
            params.append(category.value)

        if memory_type is not None:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id is not None:
            sql += " AND session_id = ?"
            params.append(session_id)

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        results: list[MemoryItem] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, tuple(params))
            rows = await cursor.fetchall()
            for row in rows:
                results.append(
                    MemoryItem(
                        id=row["id"],
                        key=row["key"],
                        content=row["content"],
                        memory_type=MemoryType(row["memory_type"]),
                        category=MemoryCategory(row["category"]),
                        session_id=row["session_id"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        tags=json.loads(row["tags"]) if row["tags"] else [],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        expires_at=row["expires_at"],
                    )
                )
        return results

    async def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem | None:
        """Update an existing memory item with privacy sanitization."""
        existing = await self.get_memory(memory_id)
        if not existing:
            return None

        new_content = existing.content
        if content is not None:
            new_content = sanitize_memory_content(content, strict=self.strict_privacy)

        new_meta = existing.metadata
        if metadata is not None:
            new_meta = sanitize_memory_metadata(metadata, strict=self.strict_privacy)

        new_tags = tags if tags is not None else existing.tags
        now = datetime.now(UTC).isoformat()

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE memories
                SET content = ?, metadata = ?, tags = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_content, json.dumps(new_meta), json.dumps(new_tags), now, memory_id),
            )
            await conn.commit()

        return await self.get_memory(memory_id)

    async def forget_memory(self, memory_id: str) -> bool:
        """Forget/delete a specific memory item by ID."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Memory forgotten: {memory_id}")
            return deleted

    async def forget_by_key(self, key: str, category: MemoryCategory | None = None) -> int:
        """Forget memories matching a specific key."""
        if key in self._temp_context:
            del self._temp_context[key]

        sql = "DELETE FROM memories WHERE key = ?"
        params: list[Any] = [key]
        if category is not None:
            sql += " AND category = ?"
            params.append(category.value)

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, tuple(params))
            await conn.commit()
            count = cursor.rowcount
            logger.info(f"Forgotten {count} memories with key '{key}'")
            return count

    async def forget_all(
        self,
        category: MemoryCategory | None = None,
        memory_type: MemoryType | None = None,
        session_id: str | None = None,
    ) -> int:
        """Bulk forget memories matching specified filter (user privacy control)."""
        if memory_type == MemoryType.TEMPORARY or (memory_type is None and session_id is None):
            self.clear_temp()

        sql = "DELETE FROM memories WHERE 1=1"
        params: list[Any] = []

        if category is not None:
            sql += " AND category = ?"
            params.append(category.value)

        if memory_type is not None:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id is not None:
            sql += " AND session_id = ?"
            params.append(session_id)

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, tuple(params))
            await conn.commit()
            count = cursor.rowcount
            logger.info(f"Bulk forgotten {count} memories.")
            return count

    # =========================================================================
    # Project Memory Domain
    # =========================================================================

    async def save_project(
        self,
        name: str,
        path: str,
        technology: str = "unknown",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProjectMemory:
        """Store or update developer workspace project memory (e.g. IntelliRepo)."""
        clean_desc = sanitize_memory_content(description, strict=self.strict_privacy)
        clean_meta = sanitize_memory_metadata(metadata or {}, strict=self.strict_privacy)
        now = datetime.now(UTC).isoformat()

        proj = ProjectMemory(
            id=str(uuid4()),
            name=name.strip(),
            path=path.strip(),
            technology=technology.strip(),
            description=clean_desc,
            last_used=now,
            metadata=clean_meta,
        )

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO project_memories (
                    id, name, path, technology, description, last_used, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    path = excluded.path,
                    technology = excluded.technology,
                    description = excluded.description,
                    last_used = excluded.last_used,
                    metadata = excluded.metadata
                """,
                (
                    proj.id,
                    proj.name,
                    proj.path,
                    proj.technology,
                    proj.description,
                    proj.last_used,
                    json.dumps(proj.metadata),
                ),
            )
            await conn.commit()

        logger.info(f"Project memory saved: '{proj.name}' at {proj.path}")
        return proj

    async def get_project(self, name_or_id: str) -> ProjectMemory | None:
        """Retrieve project memory by unique project name or ID."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, name, path, technology, description, last_used, metadata
                FROM project_memories
                WHERE name = ? OR id = ?
                """,
                (name_or_id, name_or_id),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return ProjectMemory(
                id=row["id"],
                name=row["name"],
                path=row["path"],
                technology=row["technology"],
                description=row["description"],
                last_used=row["last_used"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )

    async def list_projects(self) -> list[ProjectMemory]:
        """List all indexed developer projects."""
        projects: list[ProjectMemory] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, name, path, technology, description, last_used, metadata
                FROM project_memories
                ORDER BY last_used DESC
                """
            )
            rows = await cursor.fetchall()
            for row in rows:
                projects.append(
                    ProjectMemory(
                        id=row["id"],
                        name=row["name"],
                        path=row["path"],
                        technology=row["technology"],
                        description=row["description"],
                        last_used=row["last_used"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
        return projects

    async def search_projects(self, query: str) -> list[ProjectMemory]:
        """Search projects by name, technology, or description."""
        pattern = f"%{query}%"
        projects: list[ProjectMemory] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, name, path, technology, description, last_used, metadata
                FROM project_memories
                WHERE name LIKE ? OR technology LIKE ? OR description LIKE ?
                ORDER BY last_used DESC
                """,
                (pattern, pattern, pattern),
            )
            rows = await cursor.fetchall()
            for row in rows:
                projects.append(
                    ProjectMemory(
                        id=row["id"],
                        name=row["name"],
                        path=row["path"],
                        technology=row["technology"],
                        description=row["description"],
                        last_used=row["last_used"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
        return projects

    async def forget_project(self, name_or_id: str) -> bool:
        """Remove a project from persistent memory."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM project_memories WHERE name = ? OR id = ?",
                (name_or_id, name_or_id),
            )
            await conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # User Preferences Domain
    # =========================================================================

    async def set_preference(
        self,
        key: str,
        value: Any,
        category: str = "general",
    ) -> UserPreference:
        """Persist a user preference key-value configuration."""
        clean_val = value
        if isinstance(value, str):
            clean_val = sanitize_memory_content(value, strict=self.strict_privacy)

        val_str = json.dumps(clean_val)
        now = datetime.now(UTC).isoformat()

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO user_preferences (key, value, category, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, val_str, category, now),
            )
            await conn.commit()

        return UserPreference(key=key, value=clean_val, category=category, updated_at=now)

    async def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a stored preference value."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
            if not row:
                return default
            return json.loads(row["value"])

    async def list_preferences(self, category: str | None = None) -> list[UserPreference]:
        """List all user preferences, optionally filtered by category."""
        sql = "SELECT key, value, category, updated_at FROM user_preferences"
        params: tuple[Any, ...] = ()
        if category is not None:
            sql += " WHERE category = ?"
            params = (category,)

        prefs: list[UserPreference] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            for row in rows:
                prefs.append(
                    UserPreference(
                        key=row["key"],
                        value=json.loads(row["value"]),
                        category=row["category"],
                        updated_at=row["updated_at"],
                    )
                )
        return prefs

    async def forget_preference(self, key: str) -> bool:
        """Delete a stored preference."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute("DELETE FROM user_preferences WHERE key = ?", (key,))
            await conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # Applications Domain
    # =========================================================================

    async def save_application(
        self,
        name: str,
        executable_path: str,
        category: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApplicationMemory:
        """Store or update a recognized Windows application."""
        clean_meta = sanitize_memory_metadata(metadata or {}, strict=self.strict_privacy)
        now = datetime.now(UTC).isoformat()

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM application_memories WHERE LOWER(name) = LOWER(?)",
                (name.strip(),),
            )
            row = await cursor.fetchone()
            if row:
                app_id = row["id"]
                await conn.execute(
                    """
                    UPDATE application_memories
                    SET executable_path = ?, category = ?, last_launched = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        executable_path.strip(),
                        category,
                        now,
                        json.dumps(clean_meta),
                        app_id,
                    ),
                )
            else:
                app_id = str(uuid4())
                await conn.execute(
                    """
                    INSERT INTO application_memories (
                        id, name, executable_path, category, last_launched, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        app_id,
                        name.strip(),
                        executable_path.strip(),
                        category,
                        now,
                        json.dumps(clean_meta),
                    ),
                )
            await conn.commit()

        return ApplicationMemory(
            id=app_id,
            name=name.strip(),
            executable_path=executable_path.strip(),
            category=category,
            last_launched=now,
            metadata=clean_meta,
        )

    async def get_application(self, name_or_id: str) -> ApplicationMemory | None:
        """Retrieve an application memory by name or ID."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, name, executable_path, category, last_launched, metadata
                FROM application_memories
                WHERE LOWER(name) = LOWER(?) OR id = ?
                """,
                (name_or_id.strip(), name_or_id.strip()),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return ApplicationMemory(
                id=row["id"],
                name=row["name"],
                executable_path=row["executable_path"],
                category=row["category"],
                last_launched=row["last_launched"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )

    async def list_applications(self, category: str | None = None) -> list[ApplicationMemory]:
        """List registered applications, optionally filtered by category."""
        sql = (
            "SELECT id, name, executable_path, category, last_launched, metadata "
            "FROM application_memories"
        )
        params: tuple[Any, ...] = ()
        if category:
            sql += " WHERE category = ?"
            params = (category,)
        sql += " ORDER BY last_launched DESC"

        apps: list[ApplicationMemory] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            for row in rows:
                apps.append(
                    ApplicationMemory(
                        id=row["id"],
                        name=row["name"],
                        executable_path=row["executable_path"],
                        category=row["category"],
                        last_launched=row["last_launched"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )
        return apps

    async def forget_application(self, name_or_id: str) -> bool:
        """Remove an application from memory."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM application_memories WHERE LOWER(name) = LOWER(?) OR id = ?",
                (name_or_id.strip(), name_or_id.strip()),
            )
            await conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # Workflows Domain
    # =========================================================================

    async def save_workflow(
        self,
        name: str,
        trigger: str,
        steps: list[dict[str, Any]],
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowMemory:
        """Store an automated workflow recipe."""
        clean_desc = sanitize_memory_content(description, strict=self.strict_privacy)
        clean_meta = sanitize_memory_metadata(metadata or {}, strict=self.strict_privacy)
        now = datetime.now(UTC).isoformat()

        wf = WorkflowMemory(
            id=str(uuid4()),
            name=name.strip(),
            trigger=trigger.strip(),
            steps=steps,
            description=clean_desc,
            metadata=clean_meta,
            created_at=now,
            updated_at=now,
        )

        async with self.db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO workflow_memories (
                    id, name, trigger, description, steps, metadata, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    trigger = excluded.trigger,
                    description = excluded.description,
                    steps = excluded.steps,
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at
                """,
                (
                    wf.id,
                    wf.name,
                    wf.trigger,
                    wf.description,
                    json.dumps(wf.steps),
                    json.dumps(wf.metadata),
                    wf.created_at,
                    wf.updated_at,
                ),
            )
            await conn.commit()

        return wf

    async def list_workflows(self) -> list[WorkflowMemory]:
        """List all saved workflow recipes."""
        workflows: list[WorkflowMemory] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, name, trigger, description, steps, metadata, created_at, updated_at "
                "FROM workflow_memories ORDER BY updated_at DESC"
            )
            rows = await cursor.fetchall()
            for row in rows:
                workflows.append(
                    WorkflowMemory(
                        id=row["id"],
                        name=row["name"],
                        trigger=row["trigger"],
                        description=row["description"],
                        steps=json.loads(row["steps"]) if row["steps"] else [],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
        return workflows

    async def forget_workflow(self, name_or_id: str) -> bool:
        """Delete a saved workflow recipe."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM workflow_memories WHERE name = ? OR id = ?",
                (name_or_id, name_or_id),
            )
            await conn.commit()
            return cursor.rowcount > 0


# Global memory manager singleton
memory_manager = MemoryManager()
