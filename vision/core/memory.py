"""Memory system for Vision — short-term, long-term, user profile."""

from datetime import datetime
from vision.core.database import Database


class MemoryManager:
    """Manages short-term (session) and long-term (persistent) memory."""

    def __init__(self, db: Database):
        self.db = db

    async def add_message(self, session_id: str, role: str, content: str, tokens: int = 0):
        await self.db.execute(
            "INSERT INTO messages (session_id, role, content, tokens_used) VALUES (?, ?, ?, ?)",
            (session_id, role, content, tokens),
        )
        await self.db.commit()

    async def get_history(self, session_id: str, limit: int = 50):
        return await self.db.fetch_all(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )

    async def search(self, query: str, limit: int = 20):
        return await self.db.search_messages(query, limit)

    async def save_memory(self, key: str, content: str, mem_type: str = "free"):
        existing = await self.db.fetch_one(
            "SELECT id FROM memories WHERE key = ?", (key,)
        )
        if existing:
            await self.db.execute(
                "UPDATE memories SET content = ?, type = ?, updated_at = ? WHERE key = ?",
                (content, mem_type, datetime.now().isoformat(), key),
            )
        else:
            await self.db.execute(
                "INSERT INTO memories (key, content, type) VALUES (?, ?, ?)",
                (key, content, mem_type),
            )
        await self.db.commit()

    async def get_memory(self, key: str):
        return await self.db.fetch_one("SELECT * FROM memories WHERE key = ?", (key,))

    async def get_all_memories(self, mem_type: str | None = None):
        if mem_type:
            return await self.db.fetch_all(
                "SELECT * FROM memories WHERE type = ? ORDER BY updated_at DESC", (mem_type,)
            )
        return await self.db.fetch_all("SELECT * FROM memories ORDER BY updated_at DESC")

    async def delete_memory(self, key: str):
        await self.db.execute("DELETE FROM memories WHERE key = ?", (key,))
        await self.db.commit()

    async def set_profile(self, key: str, value: str):
        existing = await self.db.fetch_one(
            "SELECT key FROM user_profile WHERE key = ?", (key,)
        )
        if existing:
            await self.db.execute(
                "UPDATE user_profile SET value = ?, updated_at = ? WHERE key = ?",
                (value, datetime.now().isoformat(), key),
            )
        else:
            await self.db.execute(
                "INSERT INTO user_profile (key, value) VALUES (?, ?)", (key, value)
            )
        await self.db.commit()

    async def get_profile(self, key: str):
        row = await self.db.fetch_one(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        )
        return row["value"] if row else None

    async def get_full_profile(self):
        rows = await self.db.fetch_all("SELECT key, value FROM user_profile")
        return {r["key"]: r["value"] for r in rows}
