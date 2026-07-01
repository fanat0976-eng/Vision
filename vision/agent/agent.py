"""Vision Agent — self-improving conversation loop."""

import json
import logging
from datetime import datetime
from typing import AsyncGenerator

from vision.core.database import Database
from vision.core.config import Config
from vision.core.memory import MemoryManager
from vision.agent.llm_client import LLMClient
from vision.agent.context import ContextManager
from vision.agent.skill_manager import SkillManager

logger = logging.getLogger("vision.agent")


class Agent:
    """Main agent — perceive → think → act loop with self-improving skills."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.memory = MemoryManager(db)
        self.llm = LLMClient(config.llm)
        self.context = ContextManager(config, db)
        self.skills = SkillManager(config, db)
        self.current_session: str | None = None
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return """You are Vision — a self-improving AI assistant.

CORE RULES:
- Be helpful, concise, and direct
- Use tools when needed to accomplish tasks
- After completing complex tasks, suggest creating a skill for future use
- Remember user preferences and adapt your style
- Respond in the same language the user uses

CAPABILITIES:
- File operations (read, write, edit)
- Shell commands (bash)
- Web browsing
- Memory (save/recall knowledge)
- Skill creation (self-improvement)
- Voice control (when enabled)
- Gesture control (when enabled)

SELF-IMPROVEMENT:
After completing a complex task, evaluate if it should become a reusable skill.
If yes, propose a SKILL.md with instructions for future similar tasks.
Skills improve each time they are used — update them with new learnings."""

    async def start_session(self, session_id: str | None = None, platform: str = "cli") -> str:
        if not session_id:
            import secrets
            session_id = f"ses_{int(datetime.now().timestamp())}_{secrets.token_hex(4)}"
        await self.db.execute(
            "INSERT OR IGNORE INTO sessions (id, platform) VALUES (?, ?)",
            (session_id, platform),
        )
        await self.db.commit()
        self.current_session = session_id
        return session_id

    async def process_message(self, user_input: str) -> AsyncGenerator[str, None]:
        if not self.current_session:
            await self.start_session()

        await self.memory.add_message(self.current_session, "user", user_input)

        # Check for slash commands
        if user_input.startswith("/"):
            async for chunk in self._handle_command(user_input):
                yield chunk
            return

        # Build context
        messages = await self.context.build_messages(
            self.current_session, self._system_prompt
        )

        # Get available skills context
        skills_context = await self.skills.get_active_skills_context()
        if skills_context:
            messages.insert(-1, {
                "role": "system",
                "content": f"Available skills:\n{skills_context}"
            })

        # Add tool definitions to system prompt
        tool_defs = self._get_tool_definitions()
        if tool_defs:
            messages.insert(1, {
                "role": "system",
                "content": f"""You are Vision AI assistant running on WINDOWS.

CRITICAL: When user asks you to DO something, you MUST call a tool using this EXACT format:
[TOOL:tool_name(param="value")]

DO NOT describe what you would do — ACTUALLY DO IT by calling the tool.

Available tools:
{tool_defs}

Windows paths: ALWAYS use C:\\Users\\badge\\Desktop\\... (never $HOME, never ~/Desktop)
PowerShell commands: New-Item, Get-ChildItem, Set-Content (never curl, never mkdir -p)

Examples:
User: "Create folder Test on desktop"
You: [TOOL:execute_bash(command="New-Item -ItemType Directory -Path 'C:\\Users\\badge\\Desktop\\Test' -Force")]

User: "Write hello to file"
You: [TOOL:write_file(path="C:\\Users\\badge\\Desktop\\file.txt", content="hello")]

User: "Search python"
You: [TOOL:search_web(query="python")]"""
            })

        # Stream LLM response with peek-buffer for tool calls
        # Strategy: collect full response, yield non-tool text, hide [TOOL:...] from user
        full_response = ""
        pre_tool_text = ""     # text before tool call (yielded to user)
        in_tool_zone = False   # True once we see "[TOOL:" prefix forming
        tool_call_text = ""
        peek = ""              # peek buffer for detecting [TOOL:

        async for chunk in self.llm.stream_chat(messages):
            full_response += chunk

            if in_tool_zone:
                tool_call_text += chunk
                continue

            # Check if this chunk starts forming [TOOL:
            peek += chunk
            if "[TOOL:" in peek:
                # Found tool marker — everything before it was normal text
                tool_idx = peek.index("[TOOL:")
                pre_tool_text += peek[:tool_idx]
                if pre_tool_text:
                    yield pre_tool_text
                in_tool_zone = True
                tool_call_text = peek[tool_idx:]
                peek = ""
            elif "[" in peek and not peek.endswith("]"):
                # Potential start of [TOOL: — buffer and wait for more chars
                pass
            else:
                # No tool call possible — flush peek to user
                pre_tool_text += peek
                yield peek
                peek = ""

        # Flush remaining peek buffer (not a tool call)
        if peek and not in_tool_zone:
            pre_tool_text += peek
            yield peek

        # Multi-step tool loop: execute tools → feed results → LLM decides next
        max_tool_rounds = 10
        total_tools = 0
        for round_num in range(1, max_tool_rounds + 1):
            tool_calls = self._parse_tool_calls(full_response) if in_tool_zone else []
            if not tool_calls:
                break

            yield f"\n📋 Раунд {round_num}: {len(tool_calls)} тулов\n"

            # Execute ALL tool calls in this response
            for tool_name, tool_args in tool_calls:
                total_tools += 1
                yield f"  🔧 [{total_tools}] {tool_name}...\n"
                result = await self._execute_tool(tool_name, tool_args)
                result_text = self._format_result(result)
                yield f"  ✅ Готово ({len(result_text)} символов)\n"

                # Feed result back to LLM
                messages.append({"role": "assistant", "content": full_response})
                messages.append({"role": "user", "content": f"Tool result:\n{result_text}"})

            # Truncate messages to avoid context overflow
            if len(messages) > 30:
                messages = messages[:4] + messages[-26:]

            # Ask LLM what to do next (may call more tools or summarize)
            full_response = ""
            in_tool_zone = False

            yield f"  ⏳ Думаю...\n"

            # Stream with peek-buffer to hide [TOOL:] markers
            peek = ""
            async for chunk in self.llm.stream_chat(messages):
                full_response += chunk
                if "[TOOL:" in chunk:
                    in_tool_zone = True
                if in_tool_zone:
                    continue
                peek += chunk
                if "[TOOL:" in peek:
                    tool_idx = peek.index("[TOOL:")
                    yield peek[:tool_idx]
                    peek = ""
                elif "[" in peek and not peek.endswith("]"):
                    pass  # buffering
                else:
                    yield peek
                    peek = ""
            if peek and not in_tool_zone:
                yield peek

        # Save assistant message
        await self.memory.add_message(self.current_session, "assistant", full_response)

        # Self-improvement nudge (check if should create skill)
        if len(full_response) > 500:
            await self._maybe_suggest_skill(user_input, full_response)

    async def _handle_command(self, command: str) -> AsyncGenerator[str, None]:
        cmd = command.strip().split()
        name = cmd[0].lower()

        if name == "/new":
            session_id = await self.start_session()
            yield f"New session started: {session_id}\n"

        elif name == "/sessions":
            sessions = await self.db.fetch_all(
                "SELECT id, title, created_at FROM sessions ORDER BY created_at DESC LIMIT 20"
            )
            for s in sessions:
                yield f"  {s['id']} — {s['title'] or 'Untitled'} ({s['created_at']})\n"

        elif name == "/skills":
            skills = await self.db.fetch_all(
                "SELECT name, uses, auto_created FROM skills ORDER BY uses DESC"
            )
            if not skills:
                yield "No skills yet. Complete complex tasks to auto-create skills.\n"
            for s in skills:
                auto = " [auto]" if s["auto_created"] else ""
                yield f"  {s['name']} (used {s['uses']}x){auto}\n"

        elif name == "/memory":
            memories = await self.memory.get_all_memories()
            if not memories:
                yield "No memories saved yet.\n"
            for m in memories:
                yield f"  {m['key']}: {m['content'][:100]}...\n"

        elif name == "/compress":
            yield "Context compressed.\n"

        elif name == "/help":
            yield """Vision commands:
  /new        — Start new session
  /sessions   — List recent sessions
  /skills     — List learned skills
  /memory     — Show saved memories
  /compress   — Compress conversation context
  /help       — Show this help
"""
        else:
            yield f"Unknown command: {name}. Type /help for available commands.\n"

    async def _maybe_suggest_skill(self, task: str, result: str):
        """Periodically suggest creating a skill after complex tasks."""
        nudge_check = await self.db.fetch_one(
            "SELECT COUNT(*) as cnt FROM nudges WHERE type = 'skill_suggest' AND date(created_at) = date('now')"
        )
        if nudge_check and nudge_check["cnt"] < 3:
            if len(task) > 200 or any(kw in task.lower() for kw in [
                "создай", "напиши", "сделай", "настрой", "замени",
                "create", "write", "build", "setup", "configure"
            ]):
                skill_name = self._suggest_skill_name(task)
                await self.db.execute(
                    "INSERT INTO nudges (type, message) VALUES (?, ?)",
                    ("skill_suggest", f"Consider creating skill '{skill_name}' for this type of task."),
                )
                await self.db.commit()

    def _suggest_skill_name(self, task: str) -> str:
        words = task.lower().split()
        keywords = [w for w in words if len(w) > 3][:3]
        return "-".join(keywords) if keywords else "new-skill"

    async def create_skill(self, name: str, content: str, auto: bool = False):
        """Create or update a skill (self-improvement)."""
        existing = await self.db.fetch_one(
            "SELECT id, content FROM skills WHERE name = ?", (name,)
        )
        if existing:
            merged = f"{existing['content']}\n\n---\n\n## Update {datetime.now().isoformat()}\n{content}"
            await self.db.execute(
                "UPDATE skills SET content = ?, updated_at = ? WHERE name = ?",
                (merged, datetime.now().isoformat(), name),
            )
        else:
            await self.db.execute(
                "INSERT INTO skills (name, content, auto_created) VALUES (?, ?, ?)",
                (name, content, int(auto)),
            )
        await self.db.commit()

    async def use_skill(self, name: str):
        """Mark a skill as used (increment counter)."""
        await self.db.execute(
            "UPDATE skills SET uses = uses + 1, updated_at = ? WHERE name = ?",
            (datetime.now().isoformat(), name),
        )
        await self.db.commit()

    def _get_tool_definitions(self) -> str:
        """Get tool definitions for LLM system prompt."""
        tools = [
            'execute_bash(command="...") — Execute PowerShell command on Windows',
            'write_file(path="...", content="...") — Write content to file',
            'read_file(path="...") — Read file contents',
            'list_directory(path="...") — List directory',
            'search_web(query="...", num_results=5) — Search internet via DuckDuckGo',
            'fetch_url(url="...") — Fetch content from a URL',
            'save_memory(key="...", content="...") — Save knowledge',
            'get_system_info() — Get CPU, RAM, disk info',
            'delegate_task(prompt="...") — Spawn subagent for complex task',
        ]
        return "\n".join(f"- {t}" for t in tools)

    def _parse_tool_calls(self, text: str) -> list[tuple[str, dict]]:
        """Parse tool calls from LLM response — balanced paren scanning."""
        import re
        results = []

        # Format 1: [TOOL:name(args)] — scan for [TOOL: then balanced parens
        i = 0
        while i < len(text):
            marker = text.find("[TOOL:", i)
            if marker == -1:
                break
            name_start = marker + 6
            paren_start = text.find("(", name_start)
            if paren_start == -1 or paren_start - name_start > 50:
                i = marker + 1
                continue
            name = text[name_start:paren_start]
            if not re.match(r'^\w+$', name):
                i = marker + 1
                continue
            depth = 1
            j = paren_start + 1
            while j < len(text) and depth > 0:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                j += 1
            if depth == 0 and j + 1 <= len(text) and text[j - 1] == ')':
                args_str = text[paren_start + 1:j - 1]
                results.append((name, self._parse_args(args_str)))
            i = j

        if results:
            return results

        # Format 2: tool_name(param="value") without [TOOL:] wrapper
        pattern2 = r'(?<!\w)(execute_bash|write_file|read_file|list_directory|search_web|fetch_url|save_memory|get_system_info|delegate_task)\('
        for match in re.finditer(pattern2, text):
            start = match.end()
            depth = 1
            j = start
            while j < len(text) and depth > 0:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                j += 1
            args_str = text[start:j - 1]
            results.append((match.group(1), self._parse_args(args_str)))

        return results
    
    def _parse_args(self, args_str: str) -> dict:
        """Parse tool arguments from string like key="value", key2="value2"."""
        args = {}
        if not args_str:
            return args

        i = 0
        while i < len(args_str):
            # Skip leading comma + whitespace (argument separator)
            while i < len(args_str) and args_str[i] in (',', ' '):
                i += 1
            if i >= len(args_str):
                break

            # Find next key=
            eq_pos = args_str.find('=', i)
            if eq_pos == -1:
                break

            key = args_str[i:eq_pos].strip()
            i = eq_pos + 1

            # Skip whitespace
            while i < len(args_str) and args_str[i] == ' ':
                i += 1

            # Find the opening quote
            if i < len(args_str) and args_str[i] in ('"', "'"):
                quote = args_str[i]
                i += 1
                # Find the matching closing quote (handle \\, \", \')
                start = i
                while i < len(args_str):
                    if args_str[i] == '\\' and i + 1 < len(args_str):
                        next_ch = args_str[i + 1]
                        if next_ch in ('\\', '"', "'"):
                            i += 2  # Skip escaped backslash or quote
                        else:
                            i += 1  # Not a valid escape — treat \ as literal
                    elif args_str[i] == quote:
                        break
                    else:
                        i += 1
                value = args_str[start:i]
                i += 1  # Skip closing quote
            else:
                # No quote - take until comma or end
                start = i
                while i < len(args_str) and args_str[i] != ',':
                    i += 1
                value = args_str[start:i].strip()

            # Unescape
            value = value.replace('\\\\', '\\')
            args[key] = value

        return args

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool by name with arguments."""
        from vision.tools.file_tools import read_file, write_file, list_directory
        from vision.tools.bash_tool import execute_bash
        from vision.tools.system_tools import get_system_info
        from vision.core.memory import MemoryManager

        # Normalize tool names (LLM may use different names)
        TOOL_ALIASES = {
            "list_files": "list_directory",
            "ls": "list_directory",
            "dir": "list_directory",
            "cat": "read_file",
            "type": "read_file",
            "echo": "execute_bash",
            "browse_web": "search_web",
            "web_search": "search_web",
            "google": "search_web",
            "fetch": "fetch_url",
            "download": "fetch_url",
            "curl": "fetch_url",
        }
        name = TOOL_ALIASES.get(name, name)

        # Normalize arg names
        if "Directory" in args and "path" not in args:
            args["path"] = args.pop("Directory")
        if "file" in args and "path" not in args:
            args["path"] = args.pop("file")
        if "text" in args and "content" not in args:
            args["content"] = args.pop("text")
        
        # Fix Linux-style paths to Windows
        if "path" in args:
            args["path"] = args["path"].replace("$HOME", "C:\\Users\\badge")
            args["path"] = args["path"].replace("~", "C:\\Users\\badge")
            args["path"] = args["path"].replace("/", "\\")
        if "command" in args:
            args["command"] = args["command"].replace("$HOME", "C:\\Users\\badge")
            args["command"] = args["command"].replace("~", "C:\\Users\\badge")
            args["command"] = args["command"].replace("ls ", "Get-ChildItem ")

        try:
            if name == "execute_bash":
                result = await execute_bash(args.get("command", ""), timeout=30)
            elif name == "write_file":
                result = await write_file(args.get("path", ""), args.get("content", ""))
            elif name == "read_file":
                result = await read_file(args.get("path", ""))
            elif name == "list_directory":
                result = await list_directory(args.get("path", "."))
            elif name == "search_web":
                from vision.tools.browser_tools import search_web
                result = await search_web(args.get("query", ""), args.get("num_results", 5))
            elif name == "fetch_url":
                from vision.tools.browser_tools import fetch_url
                result = await fetch_url(args.get("url", ""))
            elif name == "save_memory":
                mem = MemoryManager(self.db)
                await mem.save_memory(args.get("key", ""), args.get("content", ""))
                result = {"success": True}
            elif name == "get_system_info":
                result = await get_system_info()
            elif name == "delegate_task":
                from vision.tools.delegate_tools import DelegateTools
                delegate = DelegateTools(self.config, self.db)
                result = await delegate.delegate_task(args.get("prompt", ""))
            else:
                result = {"error": f"Unknown tool: {name}"}

            if isinstance(result, dict):
                import json
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            return f"Error executing {name}: {e}"
    
    def _format_result(self, result) -> str:
        """Format tool result for human-readable output."""
        import json
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return result[:500]
        
        if isinstance(result, dict):
            if "error" in result:
                return f"Ошибка: {result['error']}"
            elif "success" in result:
                return f"Успешно: {json.dumps(result, ensure_ascii=False)[:200]}"
            elif "content" in result:
                return f"Содержимое:\n{result['content'][:500]}"
            elif "results" in result:
                items = result["results"][:5]
                return f"Найдено {len(items)} результатов:\n" + "\n".join(
                    f"• {r.get('title', r.get('url', ''))[:80]}" for r in items
                )
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)[:500]
        return str(result)[:500]
