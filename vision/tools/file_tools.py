"""File operations tools — read, write, edit, list, search."""

import os
import tempfile
import glob as glob_module
from pathlib import Path

# Allowed base directories for file operations.
# Set VISION_FILE_ROOTS="*" to disable path checking (dev/test mode).
_roots_env = os.environ.get("VISION_FILE_ROOTS", "")
if _roots_env == "*":
    ALLOWED_ROOTS = None  # disabled
else:
    ALLOWED_ROOTS = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Projects",
        Path(tempfile.gettempdir()),
        Path("C:/Users/badge/Desktop"),
        Path("C:/Users/badge/Documents"),
        Path("C:/Users/badge/Downloads"),
    ]


def _is_safe_path(path: Path) -> bool:
    """Check if path is within allowed directories."""
    if ALLOWED_ROOTS is None:
        return True  # disabled
    try:
        resolved = path.resolve()
        return any(
            str(resolved).startswith(str(root.resolve()))
            for root in ALLOWED_ROOTS
        )
    except Exception:
        return False


async def read_file(path: str, offset: int = 0, limit: int = 2000) -> dict:
    """Read a file with optional offset and limit."""
    try:
        p = Path(path)
        if not _is_safe_path(p):
            return {"error": f"Access denied: {path} is outside allowed directories"}
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.is_dir():
            entries = sorted([str(e) for e in p.iterdir()][:100])
            return {"type": "directory", "entries": entries}
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        total = len(lines)
        sliced = lines[offset:offset + limit]
        numbered = [f"{i + offset + 1}: {line}" for i, line in enumerate(sliced)]
        return {
            "type": "file",
            "path": str(p),
            "total_lines": total,
            "offset": offset,
            "shown": len(sliced),
            "content": "\n".join(numbered),
        }
    except Exception as e:
        return {"error": str(e)}


async def write_file(path: str, content: str) -> dict:
    """Write content to a file."""
    try:
        p = Path(path)
        if not _is_safe_path(p):
            return {"error": f"Access denied: {path} is outside allowed directories"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(p), "bytes": len(content.encode())}
    except Exception as e:
        return {"error": str(e)}


async def edit_file(path: str, old_string: str, new_string: str) -> dict:
    """Edit a file by replacing exact string match."""
    try:
        p = Path(path)
        if not _is_safe_path(p):
            return {"error": f"Access denied: {path} is outside allowed directories"}
        if not p.exists():
            return {"error": f"File not found: {path}"}
        content = p.read_text(encoding="utf-8")
        if old_string not in content:
            return {"error": "old_string not found in file"}
        count = content.count(old_string)
        if count > 1:
            return {"error": f"Found {count} matches. Provide more context."}
        new_content = content.replace(old_string, new_string, 1)
        p.write_text(new_content, encoding="utf-8")
        return {"success": True, "path": str(p)}
    except Exception as e:
        return {"error": str(e)}


async def list_directory(path: str = ".", pattern: str = "*") -> dict:
    """List directory contents with optional glob pattern."""
    try:
        p = Path(path)
        if not _is_safe_path(p):
            return {"error": f"Access denied: {path} is outside allowed directories"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}
        entries = []
        for entry in sorted(p.glob(pattern))[:200]:
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return {"path": str(p), "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"error": str(e)}


async def search_files(directory: str, pattern: str) -> dict:
    """Search for files matching a pattern."""
    try:
        p = Path(directory)
        if not _is_safe_path(p):
            return {"error": f"Access denied: {directory} is outside allowed directories"}
        matches = glob_module.glob(
            os.path.join(directory, "**", pattern), recursive=True
        )[:100]
        return {"pattern": pattern, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"error": str(e)}
