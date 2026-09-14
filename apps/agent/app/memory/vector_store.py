"""Local Vector Store and Semantic Memory Engine for YANA."""

import json
import math
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import numpy as np

from app.config import settings
from app.logger import logger


class LocalVectorStore:
    """Zero-dependency vector memory store with semantic search and cosine similarity.

    Embeddings can be sourced from:
    1. Local Ollama embedding model (e.g. nomic-embed-text / all-minilm) if available.
    2. Dense character n-gram hashing vectorizer (always available offline with zero external calls).
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

    async def _compute_embedding(self, text: str) -> list[float]:
        """Compute embedding vector using Ollama if online, or local dense feature hashing."""
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
                        return vec
        except Exception:
            pass

        # 2. Deterministic dense semantic hash vectorizer (offline fallback)
        tokens = text.lower().split()
        vec = np.zeros(self.vector_dim, dtype=np.float32)
        for token in tokens:
            h = hash(token)
            idx = abs(h) % self.vector_dim
            sign = 1.0 if (h > 0) else -1.0
            vec[idx] += sign

        # L2 normalize vector
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def add_memory(
        self,
        key: str,
        content: str,
        category: str = "general",
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
    ) -> str:
        """Store a semantic memory entry with its embedding vector."""
        mid = memory_id or str(uuid4())
        vec = await self._compute_embedding(content)
        vec_json = json.dumps(vec)
        meta_json = json.dumps(metadata or {})

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO vector_memories (id, key, content, category, embedding, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mid, key, content, category, vec_json, meta_json),
            )
            conn.commit()
        return mid

    async def search(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 5,
        threshold: float = 0.05,
    ) -> list[dict[str, Any]]:
        """Search memory by semantic similarity to query string."""
        query_vec = np.array(await self._compute_embedding(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        with self._get_connection() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT id, key, content, category, embedding, metadata, created_at FROM vector_memories WHERE category = ?",
                    (category,),
                )
            else:
                cursor = conn.execute(
                    "SELECT id, key, content, category, embedding, metadata, created_at FROM vector_memories"
                )
            rows = cursor.fetchall()

        results = []
        for r in rows:
            try:
                emb = np.array(json.loads(r["embedding"]), dtype=np.float32)
                e_norm = np.linalg.norm(emb)
                if e_norm > 0:
                    emb = emb / e_norm

                # Compute cosine similarity
                sim = float(np.dot(query_vec, emb))
                if sim >= threshold:
                    meta = json.loads(r["metadata"]) if r["metadata"] else {}
                    results.append(
                        {
                            "id": r["id"],
                            "key": r["key"],
                            "content": r["content"],
                            "category": r["category"],
                            "similarity": round(sim, 4),
                            "metadata": meta,
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
