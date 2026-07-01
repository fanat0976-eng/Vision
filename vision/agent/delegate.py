"""Enhanced delegate manager — spawning, parallel execution, result aggregation."""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable

from vision.core.config import Config
from vision.core.database import Database
from vision.agent.subagent import Subagent, SubagentResult

logger = logging.getLogger("vision.delegate")


@dataclass
class DelegateTask:
    id: str
    prompt: str
    status: str  # "pending", "running", "done", "failed"
    result: SubagentResult | None = None
    created_at: str = ""
    dependencies: list[str] = field(default_factory=list)


class DelegateManager:
    """Manages subagent spawning, parallel execution, and result aggregation."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.tasks: dict[str, DelegateTask] = {}
        self._counter = 0
        self._lock = asyncio.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f"task_{self._counter}"

    async def spawn(
        self,
        prompt: str,
        task_id: str | None = None,
        parent_session: str | None = None,
    ) -> DelegateTask:
        """Spawn a subagent for a task."""
        tid = task_id or self._next_id()
        task = DelegateTask(
            id=tid,
            prompt=prompt,
            status="running",
            created_at=datetime.now().isoformat(),
        )
        self.tasks[tid] = task

        subagent = Subagent(tid, self.config, self.db, parent_session)
        result = await subagent.run(prompt)

        task.result = result
        task.status = result.status
        return task

    async def spawn_with_tools(
        self,
        prompt: str,
        tool_executor: Callable,
        task_id: str | None = None,
        parent_session: str | None = None,
    ) -> DelegateTask:
        """Spawn a subagent with tool calling capabilities."""
        tid = task_id or self._next_id()
        task = DelegateTask(
            id=tid,
            prompt=prompt,
            status="running",
            created_at=datetime.now().isoformat(),
        )
        self.tasks[tid] = task

        subagent = Subagent(tid, self.config, self.db, parent_session)
        result = await subagent.run_with_tools(prompt, tool_executor)

        task.result = result
        task.status = result.status
        return task

    async def spawn_parallel(
        self,
        prompts: list[str],
        parent_session: str | None = None,
    ) -> list[DelegateTask]:
        """Spawn multiple subagents in parallel."""
        tasks = []
        for prompt in prompts:
            task = DelegateTask(
                id=self._next_id(),
                prompt=prompt,
                status="running",
                created_at=datetime.now().isoformat(),
            )
            self.tasks[task.id] = task
            tasks.append(task)

        async def run_task(task: DelegateTask):
            subagent = Subagent(
                task.id, self.config, self.db, parent_session
            )
            result = await subagent.run(task.prompt)
            task.result = result
            task.status = result.status

        await asyncio.gather(*[run_task(t) for t in tasks])
        return tasks

    async def spawn_dag(
        self,
        dag: list[dict],
        parent_session: str | None = None,
    ) -> list[DelegateTask]:
        """Execute tasks in dependency order (DAG).

        dag format: [{"id": "t1", "prompt": "...", "deps": []}, ...]
        """
        task_map = {}
        for spec in dag:
            tid = spec.get("id", self._next_id())
            task = DelegateTask(
                id=tid,
                prompt=spec["prompt"],
                status="pending",
                created_at=datetime.now().isoformat(),
                dependencies=spec.get("deps", []),
            )
            self.tasks[tid] = task
            task_map[tid] = task

        # Execute in topological order
        completed = set()
        results = []

        while len(completed) < len(dag):
            ready = []
            for tid, task in task_map.items():
                if tid in completed:
                    continue
                if all(dep in completed for dep in task.dependencies):
                    ready.append(task)

            if not ready:
                logger.error("Circular dependency detected")
                break

            # Execute ready tasks in parallel
            async def run_one(task: DelegateTask):
                # Build context from dependencies
                dep_results = []
                for dep_id in task.dependencies:
                    dep_task = task_map.get(dep_id)
                    if dep_task and dep_task.result:
                        dep_results.append(
                            f"Result from {dep_id}: {dep_task.result.result[:500]}"
                        )

                full_prompt = task.prompt
                if dep_results:
                    full_prompt += "\n\nContext from previous tasks:\n" + "\n".join(dep_results)

                subagent = Subagent(
                    task.id, self.config, self.db, parent_session
                )
                result = await subagent.run(full_prompt)
                task.result = result
                task.status = result.status
                completed.add(task.id)
                results.append(task)

            await asyncio.gather(*[run_one(t) for t in ready])

        return results

    def aggregate_results(self, tasks: list[DelegateTask]) -> str:
        """Aggregate results from multiple tasks."""
        parts = []
        for t in tasks:
            status_icon = "✓" if t.status == "done" else "✗"
            if t.result and t.result.result:
                result_text = t.result.result[:500]
            elif t.result and t.result.error:
                result_text = f"ERROR: {t.result.error}"
            else:
                result_text = "No result"
            parts.append(f"[{status_icon}] {t.id}: {result_text}")
        return "\n\n".join(parts)

    def get_task(self, task_id: str) -> DelegateTask | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        return [
            {
                "id": t.id,
                "status": t.status,
                "prompt": t.prompt[:100],
                "created_at": t.created_at,
            }
            for t in self.tasks.values()
        ]
