"""Bash tool — execute shell commands (PowerShell on Windows)."""

import asyncio
import platform
import logging

logger = logging.getLogger("vision.tools.bash")


async def execute_bash(
    command: str, timeout: int = 60, workdir: str | None = None
) -> dict:
    """Execute a shell command with timeout. Uses PowerShell on Windows."""
    try:
        if platform.system() == "Windows":
            # Use PowerShell explicitly
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-NoProfile", "-Command", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
                shell=True,
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"error": f"Command timed out after {timeout}s", "command": command}

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        return {
            "exit_code": proc.returncode,
            "stdout": stdout_text[:10000],
            "stderr": stderr_text[:5000],
            "command": command,
        }
    except Exception as e:
        logger.error(f"Bash error: {e}")
        return {"error": str(e), "command": command}
