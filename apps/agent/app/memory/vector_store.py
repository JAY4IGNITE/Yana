"""Local Vector Store and Semantic Memory Engine for YANA."""

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import numpy as np

from app.config import settings
from app.logger import logger

ENCODER_OLLAMA = "ollama:nomic-embed-text"
ENCODER_LEXICAL = "lexical_blake2b_128"


class LocalVectorStore:
    """Local vector memory store with cosine-similarity search.

    Embeddings can be sourced from:
    1. A real semantic embedding model via local Ollama (e.g. nomic-embed-text)
       when it is running — this provides genuine semantic similarity.
    2. A deterministic LEXICAL feature-hashing fallback (offline, zero external
       calls). This is token-overlap based, NOT semantic: two texts that share
       no tokens score ~0 even if they mean the same thing. It is reproducible
       across process restarts (stable hashing), so persisted vectors remain
       comparable.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(settings.storage_path)
        self.vector_dim = 128
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_memories (
                    id TEXT PRIMARY KEY,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vec_category ON vector_memories (category);"
            )
            conn.commit()

    async def _compute_embedding(self, text: str) -> tuple[list[float], str]:
        """Compute embedding vector using Ollama if online, or local dense feature hashing.

        Returns (vector, encoder_id).
        """
        # 1. Try local Ollama embedding if running
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                )
                if res.status_code == 200:
                    data = res.json()
                    vec = data.get("embedding", [])
                    if vec:
                        return vec, ENCODER_OLLAMA
        except Exception:
            pass

        # 2. Deterministic lexical feature-hashing fallback (offline).
        import hashlib

        tokens = text.lower().split()
        vec = np.zeros(self.vector_dim, dtype=np.float32)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            h = int.from_bytes(digest, "big")
            idx = h % self.vector_dim
            sign = 1.0 if (h & 1) else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist(), ENCODER_LEXICAL

    async def add_memory(
        self,
        key: str,
        content: str,
        category: str = "general",
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
        scope: str = "user",
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """Store a semantic memory entry with its embedding vector and encoder identity."""
        mid = memory_id or str(uuid4())
        vec, encoder_id = await self._compute_embedding(content)
        vec_json = json.dumps(vec)

        meta = dict(metadata or {})
        meta["encoder_id"] = encoder_id
        meta["scope"] = scope
        if session_id:
            meta["session_id"] = session_id
        if project_id:
            meta["project_id"] = project_id
        meta_json = json.dumps(meta)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vector_memories (
                    id, key, content, category, embedding, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mid, key, content, category, vec_json, meta_json),
            )
            conn.commit()
        return mid

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a vector memory row by id."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM vector_memories WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def delete_by_session(self, session_id: str) -> int:
        """Purge all vector memories belonging to a specific session."""
        deleted = 0
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT id, metadata FROM vector_memories")
            rows = cursor.fetchall()
            to_delete = []
            for r in rows:
                try:
                    m = json.loads(r["metadata"]) if r["metadata"] else {}
                    if m.get("session_id") == session_id:
                        to_delete.append(r["id"])
                except Exception:
                    pass
            for mid in to_delete:
                conn.execute("DELETE FROM vector_memories WHERE id = ?", (mid,))
                deleted += 1
            conn.commit()
        return deleted

    async def search(
        self,
        query: str,
        category: str | None = None,
        scope: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        top_k: int = 5,
        threshold: float = 0.05,
    ) -> list[dict[str, Any]]:
        """Search memory by similarity, respecting scope boundaries and encoder identities."""
        raw_vec, query_encoder = await self._compute_embedding(query)
        query_vec = np.array(raw_vec, dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        with self._get_connection() as conn:
            if category:
                cursor = conn.execute(
                    """
                    SELECT id, key, content, category, embedding, metadata, created_at
                    FROM vector_memories WHERE category = ?
                    """,
                    (category,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, key, content, category, embedding, metadata, created_at
                    FROM vector_memories
                    """
                )
            rows = cursor.fetchall()

        results = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
                row_encoder = meta.get(
                    "encoder_id",
                    ENCODER_LEXICAL
                    if len(json.loads(r["embedding"])) == self.vector_dim
                    else "unknown",
                )

                # Incompatible embedding identities do not silently mix
                if row_encoder != query_encoder:
                    logger.debug(
                        "Skipping memory row %s: query encoder '%s' != stored encoder '%s'",
                        r["id"],
                        query_encoder,
                        row_encoder,
                    )
                    continue

                # Scope enforcement
                row_scope = meta.get("scope", "user")
                if scope is not None and row_scope != scope:
                    continue

                # Session scope isolation: a session memory is only visible within its session
                if row_scope == "session":
                    if not session_id or meta.get("session_id") != session_id:
                        continue

                # Project scope isolation: a project memory is only visible within its project
                if row_scope == "project":
                    if not project_id or meta.get("project_id") != project_id:
                        continue

                emb = np.array(json.loads(r["embedding"]), dtype=np.float32)
                if emb.shape != query_vec.shape:
                    continue

                e_norm = np.linalg.norm(emb)
                if e_norm > 0:
                    emb = emb / e_norm

                sim = float(np.dot(query_vec, emb))
                if sim >= threshold:
                    results.append(
                        {
                            "id": r["id"],
                            "key": r["key"],
                            "content": r["content"],
                            "category": r["category"],
                            "similarity": round(sim, 4),
                            "metadata": meta,
                            "encoder": row_encoder,
                            "scope": row_scope,
                            "created_at": r["created_at"],
                        }
                    )
            except Exception as e:
                logger.warning("Error computing similarity for row %s: %s", r["id"], e)

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]


# Global vector memory instance
vector_store = LocalVectorStore()
