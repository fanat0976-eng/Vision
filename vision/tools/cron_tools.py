"""Cron tools — scheduled tasks."""

import json
import logging
from datetime import datetime
from pathlib import Path
from croniter import croniter

logger = logging.getLogger("vision.cron")

CRON_FILE = "cron_jobs.json"


class CronManager:
    """Manages scheduled tasks."""

    def __init__(self):
        self.jobs: list[dict] = []
        self._load()

    def _load(self):
        p = Path(CRON_FILE)
        if p.exists():
            self.jobs = json.loads(p.read_text(encoding="utf-8"))

    def _save(self):
        Path(CRON_FILE).write_text(
            json.dumps(self.jobs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_job(
        self,
        name: str,
        cron_expr: str,
        command: str,
        enabled: bool = True,
    ) -> dict:
        """Add a cron job."""
        if not croniter.is_valid(cron_expr):
            return {"error": f"Invalid cron expression: {cron_expr}"}

        job = {
            "id": len(self.jobs) + 1,
            "name": name,
            "cron": cron_expr,
            "command": command,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "next_run": str(croniter(cron_expr).get_next(datetime)),
        }
        self.jobs.append(job)
        self._save()
        return {"success": True, "job": job}

    def remove_job(self, job_id: int) -> dict:
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        self._save()
        return {"success": True, "removed": job_id}

    def list_jobs(self) -> list[dict]:
        for job in self.jobs:
            if job.get("enabled"):
                try:
                    job["next_run"] = str(croniter(job["cron"]).get_next(datetime))
                except Exception:
                    job["next_run"] = "invalid"
        return self.jobs

    def enable_job(self, job_id: int) -> dict:
        for j in self.jobs:
            if j["id"] == job_id:
                j["enabled"] = True
                self._save()
                return {"success": True}
        return {"error": f"Job {job_id} not found"}

    def disable_job(self, job_id: int) -> dict:
        for j in self.jobs:
            if j["id"] == job_id:
                j["enabled"] = False
                self._save()
                return {"success": True}
        return {"error": f"Job {job_id} not found"}

    def clear(self):
        """Clear all jobs (for testing)."""
        self.jobs = []
        self._counter = 0
        self._save()


# Singleton
_cron_manager: CronManager | None = None


def get_cron_manager() -> CronManager:
    global _cron_manager
    if _cron_manager is None:
        _cron_manager = CronManager()
    return _cron_manager
