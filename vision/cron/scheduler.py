"""Cron scheduler — enhanced with daily reports and task automation."""

import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from croniter import croniter

logger = logging.getLogger("vision.cron")


class CronScheduler:
    """Advanced cron scheduler with daily reports and automation."""

    def __init__(self, db=None):
        self.db = db
        self.jobs: list[dict] = []
        self._running = False
        self._task_file = Path("cron_tasks.json")
        self._load()

    def _load(self):
        if self._task_file.exists():
            self.jobs = json.loads(self._task_file.read_text(encoding="utf-8"))

    def _save(self):
        self._task_file.write_text(
            json.dumps(self.jobs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_job(self, name: str, cron_expr: str, command: str, job_type: str = "command") -> dict:
        """Add a cron job."""
        if not croniter.is_valid(cron_expr):
            return {"error": f"Invalid cron: {cron_expr}"}

        job = {
            "id": max((j["id"] for j in self.jobs), default=0) + 1,
            "name": name,
            "cron": cron_expr,
            "command": command,
            "type": job_type,  # command, report, skill_cleanup
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0,
        }
        self.jobs.append(job)
        self._save()
        return {"success": True, "job": job}

    def remove_job(self, job_id: int) -> dict:
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        self._save()
        return {"success": True}

    def enable_job(self, job_id: int) -> dict:
        for j in self.jobs:
            if j["id"] == job_id:
                j["enabled"] = True
                self._save()
                return {"success": True}
        return {"error": "Not found"}

    def disable_job(self, job_id: int) -> dict:
        for j in self.jobs:
            if j["id"] == job_id:
                j["enabled"] = False
                self._save()
                return {"success": True}
        return {"error": "Not found"}

    def list_jobs(self) -> list[dict]:
        for job in self.jobs:
            if job.get("enabled"):
                try:
                    job["next_run"] = str(croniter(job["cron"]).get_next(datetime))
                except Exception:
                    job["next_run"] = "invalid"
        return self.jobs

    def clear(self):
        """Clear all jobs (for testing)."""
        self.jobs = []
        self._save()

    async def generate_daily_report(self) -> str:
        """Generate a daily report from database."""
        if not self.db:
            return "No database connected"

        report = f"# Vision Daily Report — {datetime.now().strftime('%Y-%m-%d')}\n\n"

        # Sessions
        sessions = await self.db.fetch_all(
            "SELECT COUNT(*) as cnt FROM sessions WHERE date(created_at) = date('now')"
        )
        report += f"- Sessions today: {sessions[0]['cnt'] if sessions else 0}\n"

        # Messages
        messages = await self.db.fetch_all(
            "SELECT COUNT(*) as cnt FROM messages WHERE date(timestamp) = date('now')"
        )
        report += f"- Messages today: {messages[0]['cnt'] if messages else 0}\n"

        # Skills
        skills = await self.db.fetch_all(
            "SELECT name, uses FROM skills ORDER BY uses DESC LIMIT 5"
        )
        if skills:
            report += "\n## Top Skills\n"
            for s in skills:
                report += f"- {s['name']}: {s['uses']} uses\n"

        # Memories
        memories = await self.db.fetch_all("SELECT COUNT(*) as cnt FROM memories")
        report += f"\n- Total memories: {memories[0]['cnt'] if memories else 0}\n"

        return report

    async def check_and_run(self):
        """Check for due jobs and execute them."""
        now = datetime.now()
        for job in self.jobs:
            if not job.get("enabled"):
                continue

            try:
                cron = croniter(job["cron"], now)
                prev = cron.get_prev(datetime)
                if job.get("last_run"):
                    last = datetime.fromisoformat(job["last_run"])
                    if prev <= last:
                        continue
                else:
                    # First run — check if within last minute
                    if (now - prev).total_seconds() > 60:
                        continue

                # Run job
                logger.info(f"Running cron job: {job['name']}")
                if job["type"] == "report":
                    result = await self.generate_daily_report()
                    logger.info(f"Report generated: {len(result)} chars")
                else:
                    result = await self._run_command(job["command"])

                job["last_run"] = now.isoformat()
                job["run_count"] = job.get("run_count", 0) + 1
                self._save()

            except Exception as e:
                logger.error(f"Cron job {job['name']} failed: {e}")

    async def _run_command(self, command: str) -> str:
        """Execute a shell command."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return stdout.decode(errors="replace")
