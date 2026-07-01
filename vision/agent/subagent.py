"""Subagent — isolated agent instance for delegated tasks."""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field

from vision.core.config import Config
from vision.core.database import Database
from vision.core.memory import MemoryManager
from vision.agent.llm_client import LLMClient

logger = logging.getLogger("vision.subagent")


@dataclass
class SubagentResult:
    task_id: str
    status: str  # "running", "done", "failed"
    result: str | None = None
    error: str | None = None
    started_at: str = ""
    finished_at: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tokens_used: int = 0


class Subagent:
    """Isolated agent with its own context and memory."""

    def __init__(
        self,
        task_id: str,
        config: Config,
        db: Database,
        parent_session: str | None = None,
    ):
        self.task_id = task_id
        self.config = config
        self.db = db
        self.memory = MemoryManager(db)
        self.llm = LLMClient(config.llm)
        self.parent_session = parent_session
        self.session_id = f"sub_{task_id}_{int(datetime.now().timestamp())}"
        self.result = SubagentResult(
            task_id=task_id,
            status="running",
            started_at=datetime.now().isoformat(),
        )

    def _build_system_prompt(self) -> str:
        return f"""You are a subagent (task {self.task_id}) working on a delegated task.

RULES:
- Complete the task assigned to you
- Use tools when needed
- Be concise and focused
- Return your final result clearly
- Do NOT create new sessions or modify parent state

YOUR TASK: Focus on completing your assigned work."""

    async def _ensure_session(self):
        """Create session in database if it doesn't exist."""
        existing = await self.db.fetch_one(
            "SELECT id FROM sessions WHERE id = ?", (self.session_id,)
        )
        if not existing:
            await self.db.execute(
                "INSERT INTO sessions (id, platform) VALUES (?, ?)",
                (self.session_id, "subagent"),
            )
            await self.db.commit()

    async def run(self, prompt: str, tools: dict | None = None) -> SubagentResult:
        """Execute the delegated task."""
        try:
            await self._ensure_session()
            await self.memory.add_message(self.session_id, "user", prompt)

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ]

            # Add tool definitions if provided
            if tools:
                messages.insert(0, {
                    "role": "system",
                    "content": f"Available tools: {', '.join(tools.keys())}"
                })

            response = ""
            try:
                async for chunk in self.llm.stream_chat(messages):
                    response += chunk
            finally:
                await self.llm.close()

            await self.memory.add_message(self.session_id, "assistant", response)

            self.result.status = "done"
            self.result.result = response
            self.result.finished_at = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Subagent {self.task_id} failed: {e}")
            self.result.status = "failed"
            self.result.error = str(e)
            self.result.finished_at = datetime.now().isoformat()

        return self.result

    async def run_with_tools(self, prompt: str, tool_executor) -> SubagentResult:
        """Execute with tool calling loop."""
        try:
            await self._ensure_session()
            await self.memory.add_message(self.session_id, "user", prompt)

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": prompt},
            ]

            max_iterations = 5
            for _ in range(max_iterations):
                response = await self.llm.chat(messages)

                # Check for tool calls (simple marker-based parsing)
                if "[TOOL:" in response:
                    tool_name, tool_args = self._parse_tool_call(response)
                    if tool_name:
                        result = await tool_executor(tool_name, tool_args)
                        messages.append({"role": "assistant", "content": response})
                        messages.append({"role": "user", "content": f"Tool result: {result}"})
                        self.result.tool_calls.append({"tool": tool_name, "args": tool_args})
                        continue

                # No tool call — final response
                await self.memory.add_message(self.session_id, "assistant", response)
                self.result.status = "done"
                self.result.result = response
                self.result.finished_at = datetime.now().isoformat()
                return self.result

            # Max iterations reached — save final message
            await self.memory.add_message(self.session_id, "assistant", response)
            self.result.status = "done"
            self.result.result = response
            self.result.finished_at = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Subagent {self.task_id} failed: {e}")
            self.result.status = "failed"
            self.result.error = str(e)
            self.result.finished_at = datetime.now().isoformat()

        return self.result

    def _parse_tool_call(self, text: str) -> tuple[str | None, dict]:
        """Parse [TOOL:name(args)] markers."""
        import re
        match = re.search(r"\[TOOL:(\w+)\((.+?)\)\]", text)
        if match:
            name = match.group(1)
            args_str = match.group(2)
            # Reuse Agent's robust arg parser
            from vision.agent.agent import Agent
            args = Agent._parse_args(None, args_str)
            return name, args
        return None, {}

    async def get_history(self):
        return await self.memory.get_history(self.session_id)
