"""Memory tools — save, search, and recall knowledge."""

from vision.core.database import Database
from vision.core.memory import MemoryManager


class MemoryTools:
    """Tool handlers for memory operations."""

    def __init__(self, db: Database):
        self.memory = MemoryManager(db)

    async def save_memory(self, key: str, content: str, mem_type: str = "free") -> dict:
        await self.memory.save_memory(key, content, mem_type)
        return {"success": True, "key": key, "type": mem_type}

    async def get_memory(self, key: str) -> dict:
        row = await self.memory.get_memory(key)
        if row:
            return {"key": row["key"], "content": row["content"], "type": row["type"]}
        return {"error": f"Memory not found: {key}"}

    async def search_memory(self, query: str, limit: int = 10) -> dict:
        results = await self.memory.search(query, limit)
        return {
            "query": query,
            "results": [
                {"content": r["content"], "session": r.get("session_title", "unknown")}
                for r in results
            ],
            "count": len(results),
        }

    async def list_memories(self, mem_type: str | None = None) -> dict:
        memories = await self.memory.get_all_memories(mem_type)
        return {
            "memories": [
                {"key": m["key"], "content": m["content"][:200], "type": m["type"]}
                for m in memories
            ],
            "count": len(memories),
        }

    async def delete_memory(self, key: str) -> dict:
        await self.memory.delete_memory(key)
        return {"success": True, "deleted": key}

    async def set_profile(self, key: str, value: str) -> dict:
        await self.memory.set_profile(key, value)
        return {"success": True, "key": key}

    async def get_profile(self, key: str | None = None) -> dict:
        if key:
            value = await self.memory.get_profile(key)
            return {key: value}
        return await self.memory.get_full_profile()
