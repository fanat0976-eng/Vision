"""Delegate tools — spawn subagents, parallel work, result aggregation."""

import json
from vision.agent.delegate import DelegateManager
from vision.core.config import Config
from vision.core.database import Database


class DelegateTools:
    """Tool handlers for agent delegation."""

    def __init__(self, config: Config, db: Database):
        self.manager = DelegateManager(config, db)

    async def delegate_task(self, prompt: str, task_id: str | None = None) -> dict:
        """Spawn a subagent to handle a task."""
        task = await self.manager.spawn(prompt, task_id)
        return {
            "task_id": task.id,
            "status": task.status,
            "result": task.result.result if task.result else None,
            "error": task.result.error if task.result else None,
        }

    async def delegate_parallel(self, prompts: list[str]) -> dict:
        """Spawn multiple subagents in parallel."""
        tasks = await self.manager.spawn_parallel(prompts)
        return {
            "tasks": [
                {
                    "id": t.id,
                    "status": t.status,
                    "result": t.result.result[:500] if t.result and t.result.result else None,
                }
                for t in tasks
            ],
            "count": len(tasks),
        }

    async def delegate_dag(self, dag: list[dict]) -> dict:
        """Execute tasks in dependency order."""
        tasks = await self.manager.spawn_dag(dag)
        return {
            "tasks": [
                {
                    "id": t.id,
                    "status": t.status,
                    "result": t.result.result[:500] if t.result and t.result.result else None,
                }
                for t in tasks
            ],
            "aggregated": self.manager.aggregate_results(tasks),
        }

    async def get_task_result(self, task_id: str) -> dict:
        """Get result of a specific task."""
        task = self.manager.get_task(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}
        return {
            "id": task.id,
            "status": task.status,
            "result": task.result.result if task.result else None,
            "error": task.result.error if task.result else None,
        }

    async def list_tasks(self) -> dict:
        """List all delegated tasks."""
        return {"tasks": self.manager.list_tasks()}
