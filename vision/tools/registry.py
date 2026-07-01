"""Tool registry — manages tool registration, invocation, and approval."""

import asyncio
import inspect
import json
import logging
from typing import Any, Callable
from dataclasses import dataclass, field

logger = logging.getLogger("vision.tools")


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable
    requires_approval: bool = False


class ToolRegistry:
    """Central registry for all agent tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
        requires_approval: bool = False,
    ):
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            requires_approval=requires_approval,
        )

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_definitions_for_llm(self) -> list[dict]:
        """Get tool definitions in OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    async def call(self, name: str, arguments: dict) -> str:
        """Invoke a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**arguments)
            else:
                result = tool.handler(**arguments)
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            logger.error(f"Tool {name} error: {e}")
            return json.dumps({"error": str(e)})

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "requires_approval": t.requires_approval}
            for t in self._tools.values()
        ]
