"""Delegate tool — spawn isolated subagents for parallel work."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("vision.delegate")


@dataclass
class SubagentTask:
    id: str
    prompt: str
    status: str  # "pending", "running", "done", "failed"
    result: str | None = None
    error: str | None = None


class DelegateManager:
    """Manages subagent spawning and result aggregation."""

    def __init__(self):
        self.tasks: dict[str, SubagentTask] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"sub_{self._counter}"

    async def spawn(
        self,
        prompt: str,
        handler: Callable[[str], str],
        task_id: str | None = None,
    ) -> dict:
        """Spawn a subagent to handle a task."""
        tid = task_id or self._next_id()
        task = SubagentTask(id=tid, prompt=prompt, status="running")
        self.tasks[tid] = task

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, handler, prompt)
            task.status = "done"
            task.result = result
            return {"id": tid, "status": "done", "result": result}
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.error(f"Subagent {tid} failed: {e}")
            return {"id": tid, "status": "failed", "error": str(e)}

    async def spawn_parallel(
        self,
        prompts: list[str],
        handler: Callable[[str], str],
    ) -> list[dict]:
        """Spawn multiple subagents in parallel."""
        tasks = [self.spawn(p, handler) for p in prompts]
        return await asyncio.gather(*tasks)

    def get_task(self, task_id: str) -> SubagentTask | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        return [
            {"id": t.id, "status": t.status, "prompt": t.prompt[:100]}
            for t in self.tasks.values()
        ]


# Singleton
_delegate_manager: DelegateManager | None = None


def get_delegate_manager() -> DelegateManager:
    global _delegate_manager
    if _delegate_manager is None:
        _delegate_manager = DelegateManager()
    return _delegate_manager
