"""Context management — builds messages with history, memories, and system prompt."""

from pathlib import Path
from vision.core.config import Config
from vision.core.database import Database


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return len(text) // 4


class ContextManager:
    """Builds LLM context from history, memories, and project context."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self._max_prompt_tokens = 3000  # reserve space for completion

    async def build_messages(
        self, session_id: str, system_prompt: str
    ) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        used_tokens = _estimate_tokens(system_prompt)

        # Add project context if exists
        project_context = self._load_project_context()
        if project_context:
            messages.append({
                "role": "system",
                "content": f"Project context:\n{project_context}"
            })
            used_tokens += _estimate_tokens(project_context)

        # Add user profile
        profile_rows = await self.db.fetch_all("SELECT key, value FROM user_profile")
        if profile_rows:
            profile_text = "\n".join(f"- {r['key']}: {r['value']}" for r in profile_rows)
            messages.append({
                "role": "system",
                "content": f"User profile:\n{profile_text}"
            })
            used_tokens += _estimate_tokens(profile_text)

        # Add recent memories (budget-aware)
        memories = await self.db.fetch_all(
            "SELECT key, content FROM memories ORDER BY updated_at DESC LIMIT 10"
        )
        if memories:
            mem_text = "\n".join(f"- {m['key']}: {m['content'][:200]}" for m in memories)
            messages.append({
                "role": "system",
                "content": f"Saved knowledge:\n{mem_text}"
            })
            used_tokens += _estimate_tokens(mem_text)

        # Add conversation history (budget-aware — keep most recent)
        max_history_tokens = max(500, self.config.llm.max_tokens - used_tokens - self._max_prompt_tokens)
        history = await self.db.fetch_all(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 50",
            (session_id,),
        )

        # Add from most recent, respecting token budget
        history_msgs = []
        history_tokens = 0
        for msg in reversed(history):
            msg_tokens = _estimate_tokens(msg["content"])
            if history_tokens + msg_tokens > max_history_tokens:
                break
            history_msgs.insert(0, {"role": msg["role"], "content": msg["content"]})
            history_tokens += msg_tokens

        messages.extend(history_msgs)

        return messages

    def _load_project_context(self) -> str:
        # Look for AGENTS.md in project root (relative to this file)
        project_root = Path(__file__).parent.parent.parent
        context_file = project_root / "AGENTS.md"
        if context_file.exists():
            return context_file.read_text(encoding="utf-8")[:2000]
        return ""
