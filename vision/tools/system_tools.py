"""System info tool — OS, CPU, RAM, disk info."""

import platform
import psutil
from datetime import datetime


async def get_system_info() -> dict:
    """Get system information."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "cpu_count": psutil.cpu_count(),
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_total_gb": round(psutil.disk_usage("/").total / (1024**3), 2) if platform.system() != "Windows" else round(psutil.disk_usage("C:\\").total / (1024**3), 2),
        "disk_used_gb": round(psutil.disk_usage("/").used / (1024**3), 2) if platform.system() != "Windows" else round(psutil.disk_usage("C:\\").used / (1024**3), 2),
        "timestamp": datetime.now().isoformat(),
    }


async def get_process_list(limit: int = 20) -> dict:
    """Get top processes by CPU usage."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu": info["cpu_percent"],
                "memory": round(info["memory_percent"], 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    processes.sort(key=lambda x: x["cpu"], reverse=True)
    return {"processes": processes[:limit], "total": len(processes)}
