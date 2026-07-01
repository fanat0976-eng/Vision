"""Skill manager — self-improving skills system."""

import re
from datetime import datetime
from pathlib import Path

from vision.core.config import Config
from vision.core.database import Database


class SkillManager:
    """Manages skills — auto-creation, self-improvement, and usage tracking."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.skills_dir = Path(config.skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    async def get_active_skills_context(self) -> str:
        """Get top skills as context for LLM."""
        skills = await self.db.fetch_all(
            "SELECT name, content, uses FROM skills ORDER BY uses DESC LIMIT 10"
        )
        if not skills:
            return ""
        parts = []
        for s in skills:
            preview = s["content"][:500]
            parts.append(f"### {s['name']} (used {s['uses']}x)\n{preview}")
        return "\n\n".join(parts)

    async def create_skill(
        self, name: str, content: str, auto_created: bool = False
    ) -> dict:
        """Create or update a skill."""
        name = self._sanitize_name(name)
        if not name:
            name = "auto-skill"
        existing = await self.db.fetch_one(
            "SELECT id, content, uses FROM skills WHERE name = ?", (name,)
        )

        if existing:
            # Merge with existing skill (self-improvement)
            merged = (
                f"{existing['content']}\n\n"
                f"---\n\n"
                f"## Update ({datetime.now().strftime('%Y-%m-%d')})\n\n"
                f"{content}"
            )
            await self.db.execute(
                "UPDATE skills SET content = ?, updated_at = ? WHERE name = ?",
                (merged, datetime.now().isoformat(), name),
            )
            action = "updated"
        else:
            await self.db.execute(
                "INSERT INTO skills (name, content, auto_created) VALUES (?, ?, ?)",
                (name, content, int(auto_created)),
            )
            action = "created"

        await self.db.commit()

        # Also save as file
        skill_file = self.skills_dir / f"{name}.md"
        final_content = content if action == "created" else (
            await self.db.fetch_one("SELECT content FROM skills WHERE name = ?", (name,))
        )["content"]
        skill_file.write_text(final_content, encoding="utf-8")

        return {"name": name, "action": action, "auto_created": auto_created}

    async def use_skill(self, name: str):
        """Increment usage counter for a skill."""
        await self.db.execute(
            "UPDATE skills SET uses = uses + 1, updated_at = ? WHERE name = ?",
            (datetime.now().isoformat(), name),
        )
        await self.db.commit()

    async def list_skills(self) -> list[dict]:
        """List all skills."""
        rows = await self.db.fetch_all(
            "SELECT name, content, uses, auto_created, created_at, updated_at "
            "FROM skills ORDER BY uses DESC"
        )
        return [dict(r) for r in rows]

    async def get_skill(self, name: str) -> dict | None:
        """Get a skill by name."""
        row = await self.db.fetch_one(
            "SELECT * FROM skills WHERE name = ?", (name,)
        )
        return dict(row) if row else None

    async def delete_skill(self, name: str):
        """Delete a skill."""
        await self.db.execute("DELETE FROM skills WHERE name = ?", (name,))
        await self.db.commit()
        skill_file = self.skills_dir / f"{name}.md"
        if skill_file.exists():
            skill_file.unlink()

    async def should_auto_create(self, task: str, result: str) -> str | None:
        """Evaluate if a task should auto-create a skill."""
        indicators = [
            len(task) > 300,
            any(kw in task.lower() for kw in [
                "создай", "напиши", "сделай", "настрой", "замени", "внедри",
                "create", "write", "build", "setup", "configure", "implement",
            ]),
            result.count("\n") > 10,
        ]
        if sum(indicators) >= 2:
            return self._suggest_name(task)
        return None

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Sanitize skill name for filesystem safety."""
        return re.sub(r'[^a-zA-Z0-9_-]', '', name)[:100]

    def _suggest_name(self, task: str) -> str:
        words = task.lower().split()
        stop_words = {
            "и", "в", "на", "с", "для", "от", "до", "по", "не", "что", "как",
            "the", "a", "an", "is", "are", "was", "to", "for", "in", "on", "at",
        }
        keywords = [w.strip(".,!?;:") for w in words if w not in stop_words and len(w) > 2][:4]
        name = "-".join(keywords) if keywords else "auto-skill"
        return self._sanitize_name(name)
