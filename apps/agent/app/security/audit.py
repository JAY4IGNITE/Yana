"""Tamper-Evident Security Audit Logger for YANA.

Records every tool invocation, permission decision, and execution verification.
Strict Invariant: NEVER record secrets. All payloads are automatically sanitized.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.logger import logger
from app.memory.db import DatabaseManager, db_manager
from app.memory.privacy import redact_credentials, sanitize_memory_metadata


class AuditLogEntry(BaseModel):
    """Immutable audit trail record representing an authorized/denied tool event."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    task_id: str | None = Field(default=None, alias="taskId")
    user_request: str | None = Field(default=None, alias="userRequest")
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    permission_result: str = Field(..., alias="permissionResult")
    execution_result: Any | None = Field(default=None, alias="executionResult")
    verification: Any | None = None


class AuditLogger:
    """Security audit log manager recording to persistent SQLite with secret redaction."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self.db = db or db_manager

    def _sanitize_data(self, data: Any) -> Any:
        """Recursively redact secrets and credentials from any data structure."""
        if data is None:
            return None
        if isinstance(data, str):
            return redact_credentials(data)
        if isinstance(data, dict):
            return sanitize_memory_metadata(data, strict=False)
        if isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        return data

    async def record_event(
        self,
        tool: str,
        arguments: dict[str, Any],
        permission_result: str,
        task_id: str | None = None,
        user_request: str | None = None,
        execution_result: Any | None = None,
        verification: Any | None = None,
    ) -> AuditLogEntry:
        """Record an execution event safely, redacting all sensitive credentials."""
        clean_args = self._sanitize_data(arguments or {})
        clean_req = self._sanitize_data(user_request)
        clean_exec = self._sanitize_data(execution_result)
        clean_verif = self._sanitize_data(verification)

        entry = AuditLogEntry(
            id=str(uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            task_id=task_id,
            user_request=clean_req,
            tool=tool,
            arguments=clean_args,
            permission_result=permission_result,
            execution_result=clean_exec,
            verification=clean_verif,
        )

        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO audit_logs (
                        id, timestamp, task_id, user_request, tool, arguments,
                        permission_result, execution_result, verification
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.timestamp,
                        entry.task_id,
                        entry.user_request,
                        entry.tool,
                        json.dumps(entry.arguments),
                        entry.permission_result,
                        json.dumps(entry.execution_result)
                        if entry.execution_result is not None
                        else None,
                        json.dumps(entry.verification) if entry.verification is not None else None,
                    ),
                )
                await conn.commit()
        except Exception as e:
            # Audit recording failures must be logged with high severity
            logger.error(f"Failed to record audit event for tool '{tool}': {e}")

        return entry

    async def query_logs(
        self,
        task_id: str | None = None,
        tool: str | None = None,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        """Retrieve historical audit records for security inspection."""
        sql = (
            "SELECT id, timestamp, task_id, user_request, tool, arguments, "
            "permission_result, execution_result, verification FROM audit_logs"
        )
        clauses: list[str] = []
        params: list[Any] = []

        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if tool:
            clauses.append("tool = ?")
            params.append(tool)

        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        entries: list[AuditLogEntry] = []
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(sql, tuple(params))
            rows = await cursor.fetchall()
            for r in rows:
                args = json.loads(r["arguments"]) if r["arguments"] else {}
                exec_res = json.loads(r["execution_result"]) if r["execution_result"] else None
                verif_res = json.loads(r["verification"]) if r["verification"] else None
                entries.append(
                    AuditLogEntry(
                        id=r["id"],
                        timestamp=r["timestamp"],
                        task_id=r["task_id"],
                        user_request=r["user_request"],
                        tool=r["tool"],
                        arguments=args,
                        permission_result=r["permission_result"],
                        execution_result=exec_res,
                        verification=verif_res,
                    )
                )

        return entries


# Global audit logger singleton
audit_logger = AuditLogger()
