"""Vision tools — file, bash, memory, browser, cron, system, and more."""

from vision.tools.registry import ToolRegistry
from vision.tools.approval import ApprovalManager
from vision.tools.delegate_tool import DelegateManager
from vision.tools.skill_tools import SkillSuggester

__all__ = ["ToolRegistry", "ApprovalManager", "DelegateManager", "SkillSuggester"]


def create_default_registry() -> ToolRegistry:
    """Create registry with all default tools registered."""
    from vision.tools.file_tools import read_file, write_file, edit_file, list_directory, search_files
    from vision.tools.bash_tool import execute_bash
    from vision.tools.browser_tools import fetch_url, search_web
    from vision.tools.system_tools import get_system_info, get_process_list
    from vision.tools.cron_tools import get_cron_manager

    registry = ToolRegistry()

    # File tools
    registry.register(
        "read_file", "Read a file or list directory",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "File or directory path"},
            "offset": {"type": "integer", "description": "Line offset", "default": 0},
            "limit": {"type": "integer", "description": "Max lines", "default": 2000},
        }, "required": ["path"]},
        read_file,
    )
    registry.register(
        "write_file", "Write content to a file",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"},
        }, "required": ["path", "content"]},
        write_file, requires_approval=True,
    )
    registry.register(
        "edit_file", "Edit a file by replacing exact string",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Text to replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
        }, "required": ["path", "old_string", "new_string"]},
        edit_file, requires_approval=True,
    )
    registry.register(
        "list_directory", "List directory contents",
        {"type": "object", "properties": {
            "path": {"type": "string", "description": "Directory path", "default": "."},
            "pattern": {"type": "string", "description": "Glob pattern", "default": "*"},
        }, "required": []},
        list_directory,
    )
    registry.register(
        "search_files", "Search for files by pattern",
        {"type": "object", "properties": {
            "directory": {"type": "string", "description": "Root directory"},
            "pattern": {"type": "string", "description": "Glob pattern"},
        }, "required": ["directory", "pattern"]},
        search_files,
    )

    # Bash tool
    registry.register(
        "execute_bash", "Execute shell command",
        {"type": "object", "properties": {
            "command": {"type": "string", "description": "Shell command"},
            "timeout": {"type": "integer", "description": "Timeout seconds", "default": 60},
            "workdir": {"type": "string", "description": "Working directory"},
        }, "required": ["command"]},
        execute_bash, requires_approval=True,
    )

    # Browser tools
    registry.register(
        "fetch_url", "Fetch URL content",
        {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "format": {"type": "string", "enum": ["text", "html"], "default": "text"},
        }, "required": ["url"]},
        fetch_url,
    )
    registry.register(
        "search_web", "Search the web",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {"type": "integer", "default": 5},
        }, "required": ["query"]},
        search_web,
    )

    # System tools
    registry.register(
        "get_system_info", "Get system information",
        {"type": "object", "properties": {}, "required": []},
        get_system_info,
    )
    registry.register(
        "get_process_list", "Get running processes",
        {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20},
        }, "required": []},
        get_process_list,
    )

    # Cron tools
    cron = get_cron_manager()
    registry.register(
        "cron_add", "Add a scheduled task",
        {"type": "object", "properties": {
            "name": {"type": "string", "description": "Job name"},
            "cron": {"type": "string", "description": "Cron expression (e.g. '0 9 * * *')"},
            "command": {"type": "string", "description": "Command to run"},
        }, "required": ["name", "cron", "command"]},
        cron.add_job,
    )
    registry.register(
        "cron_list", "List scheduled tasks",
        {"type": "object", "properties": {}, "required": []},
        cron.list_jobs,
    )
    registry.register(
        "cron_remove", "Remove a scheduled task",
        {"type": "object", "properties": {
            "job_id": {"type": "integer", "description": "Job ID"},
        }, "required": ["job_id"]},
        cron.remove_job,
    )

    # Delegate tools (registered with placeholder — real handler needs config+db)
    # Actual registration happens in DelegateTools class

    return registry
