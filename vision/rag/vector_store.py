"""Vector store — SQLite-based vector storage with cosine similarity."""

import json
import math
from pathlib import Path
from dataclasses import dataclass

from vision.core.database import Database


@dataclass
class VectorRecord:
    id: int | None = None
    content: str = ""
    source: str = ""
    embedding: list[float] = None
    metadata: dict = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = []
        if self.metadata is None:
            self.metadata = {}


class VectorStore:
    """SQLite-backed vector store with cosine similarity search."""

    def __init__(self, db: Database):
        self.db = db
        self._initialized = False

    async def initialize(self):
        """Create vectors table if not exists."""
        if self._initialized:
            return
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source TEXT,
                embedding TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.db.commit()
        self._initialized = True

    async def add(self, record: VectorRecord) -> int:
        """Add a vector record."""
        await self.initialize()
        cursor = await self.db.execute(
            "INSERT INTO vectors (content, source, embedding, metadata) VALUES (?, ?, ?, ?)",
            (
                record.content,
                record.source,
                json.dumps(record.embedding),
                json.dumps(record.metadata or {}),
            ),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def add_batch(self, records: list[VectorRecord]) -> list[int]:
        """Add multiple vector records."""
        ids = []
        for record in records:
            rid = await self.add(record)
            ids.append(rid)
        return ids

    async def search(self, query_embedding: list[float], limit: int = 5) -> list[dict]:
        """Search for similar vectors using cosine similarity."""
        await self.initialize()
        rows = await self.db.fetch_all("SELECT id, content, source, embedding, metadata FROM vectors")

        results = []
        for row in rows:
            emb = json.loads(row["embedding"])
            score = self._cosine_similarity(query_embedding, emb)
            results.append({
                "id": row["id"],
                "content": row["content"],
                "source": row["source"],
                "score": score,
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    async def delete(self, record_id: int):
        """Delete a vector record."""
        await self.db.execute("DELETE FROM vectors WHERE id = ?", (record_id,))
        await self.db.commit()

    async def clear(self):
        """Clear all vectors."""
        await self.db.execute("DELETE FROM vectors")
        await self.db.commit()

    async def count(self) -> int:
        """Count total vectors."""
        await self.initialize()
        row = await self.db.fetch_one("SELECT COUNT(*) as cnt FROM vectors")
        return row["cnt"] if row else 0

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            # Truncate to min length
            min_len = min(len(a), len(b))
            a, b = a[:min_len], b[:min_len]

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)
