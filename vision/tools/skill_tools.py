"""Skill suggestion tool — auto-creates skills from completed tasks."""

from datetime import datetime
from vision.core.database import Database
from vision.agent.skill_manager import SkillManager


class SkillSuggester:
    """Suggests and auto-creates skills after complex tasks."""

    def __init__(self, db: Database, skill_manager: SkillManager):
        self.db = db
        self.skills = skill_manager
        self._nudge_count = 0

    async def maybe_create_skill(
        self, task: str, result: str, force: bool = False
    ) -> dict | None:
        """Evaluate if a skill should be created."""
        if not force and not self._should_create(task, result):
            return None

        name = self._suggest_name(task)
        content = self._generate_skill_content(task, result)

        created = await self.skills.create_skill(name, content, auto_created=True)
        return created

    def _should_create(self, task: str, result: str) -> bool:
        indicators = [
            len(task) > 200,
            any(kw in task.lower() for kw in [
                "создай", "напиши", "сделай", "настрой", "замени", "внедри",
                "create", "write", "build", "setup", "configure", "implement",
            ]),
            result.count("\n") > 10,
            "error" not in result.lower() and len(result) > 500,
        ]
        return sum(indicators) >= 2

    def _suggest_name(self, task: str) -> str:
        words = task.lower().split()
        stop = {"и", "в", "на", "с", "для", "от", "до", "по", "не", "что", "как",
                "the", "a", "an", "is", "are", "was", "to", "for", "in", "on", "at"}
        keywords = [w.strip(".,!?;:") for w in words if w not in stop and len(w) > 2][:4]
        base = "-".join(keywords) if keywords else "auto-skill"
        # Add date to avoid collisions
        date_str = datetime.now().strftime("%Y%m%d")
        return f"{base}-{date_str}"

    def _generate_skill_content(self, task: str, result: str) -> str:
        return f"""# {task[:100]}

## Task
{task}

## Solution
{result[:2000]}

## Steps
1. Analyze the request
2. Implement the solution
3. Verify the result

## Notes
- Auto-created on {datetime.now().strftime('%Y-%m-%d %H:%M')}
- Update this skill when using it for similar tasks
"""
