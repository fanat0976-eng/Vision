"""Tests for Vision Phase 2 — Tool System."""

import pytest
from vision.tools.registry import ToolRegistry
from vision.tools.approval import ApprovalManager
from vision.tools.delegate_tool import DelegateManager
from vision.tools.cron_tools import CronManager
from vision.tools.skill_tools import SkillSuggester
from vision.tools.system_tools import get_system_info, get_process_list
from vision.tools.file_tools import read_file, write_file, list_directory
from vision.tools.bash_tool import execute_bash
from vision.core.config import Config
from vision.core.database import Database
from vision.agent.skill_manager import SkillManager


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def config():
    return Config()


# === ToolRegistry Tests ===

def test_registry_register():
    reg = ToolRegistry()
    reg.register("test_tool", "A test tool", {"type": "object", "properties": {}}, lambda: "ok")
    assert reg.get_tool("test_tool") is not None
    assert len(reg.list_tools()) == 1


def test_registry_definitions_for_llm():
    reg = ToolRegistry()
    reg.register("my_tool", "desc", {"type": "object", "properties": {"x": {"type": "string"}}}, lambda x: x)
    defs = reg.get_definitions_for_llm()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "my_tool"


@pytest.mark.asyncio
async def test_registry_call():
    reg = ToolRegistry()
    reg.register("echo", "Echo input", {"type": "object", "properties": {"msg": {"type": "string"}}}, lambda msg: {"echoed": msg})
    result = await reg.call("echo", {"msg": "hello"})
    assert "hello" in result


@pytest.mark.asyncio
async def test_registry_call_unknown():
    reg = ToolRegistry()
    result = await reg.call("nonexistent", {})
    assert "error" in result


# === ApprovalManager Tests ===

def test_approval_defaults():
    mgr = ApprovalManager()
    assert mgr.check("read_file") == "allow"
    assert mgr.check("execute_bash") == "ask"
    assert mgr.check("delete_file") == "deny"
    assert mgr.check("unknown_tool") == "ask"


def test_approval_add_rule():
    mgr = ApprovalManager()
    mgr.add_rule("custom_tool", "allow")
    assert mgr.check("custom_tool") == "allow"


def test_approval_list_rules():
    mgr = ApprovalManager()
    rules = mgr.list_rules()
    assert len(rules) > 0


# === CronManager Tests ===

def test_cron_add_job():
    mgr = CronManager()
    mgr.clear()
    result = mgr.add_job("test-job", "0 9 * * *", "echo hello")
    assert result.get("success") is True
    assert result["job"]["name"] == "test-job"


def test_cron_invalid_expression():
    mgr = CronManager()
    mgr.clear()
    result = mgr.add_job("bad", "not-a-cron", "echo hi")
    assert "error" in result


def test_cron_list_jobs():
    mgr = CronManager()
    mgr.clear()
    mgr.add_job("j1", "0 9 * * *", "cmd1")
    mgr.add_job("j2", "30 18 * * 1-5", "cmd2")
    jobs = mgr.list_jobs()
    assert len(jobs) == 2


def test_cron_remove_job():
    mgr = CronManager()
    mgr.clear()
    mgr.add_job("to-remove", "0 9 * * *", "cmd")
    jobs_before = mgr.list_jobs()
    result = mgr.remove_job(jobs_before[0]["id"])
    assert result.get("success") is True
    assert len(mgr.list_jobs()) == 0


def test_cron_enable_disable():
    mgr = CronManager()
    mgr.clear()
    mgr.add_job("toggle", "0 9 * * *", "cmd")
    jobs = mgr.list_jobs()
    mgr.disable_job(jobs[0]["id"])
    job = mgr.list_jobs()[0]
    assert job["enabled"] is False
    mgr.enable_job(jobs[0]["id"])
    job = mgr.list_jobs()[0]
    assert job["enabled"] is True


# === DelegateManager Tests ===

@pytest.mark.asyncio
async def test_delegate_spawn():
    mgr = DelegateManager()
    result = await mgr.spawn("test task", lambda x: f"done: {x}")
    assert result["status"] == "done"
    assert "done: test task" in result["result"]


@pytest.mark.asyncio
async def test_delegate_parallel():
    mgr = DelegateManager()
    results = await mgr.spawn_parallel(
        ["task1", "task2", "task3"],
        lambda x: f"result_{x}",
    )
    assert len(results) == 3
    assert all(r["status"] == "done" for r in results)


@pytest.mark.asyncio
async def test_delegate_list_tasks():
    mgr = DelegateManager()
    await mgr.spawn("task a", lambda x: "ok")
    await mgr.spawn("task b", lambda x: "ok")
    tasks = mgr.list_tasks()
    assert len(tasks) == 2


# === File Tools Tests ===

@pytest.mark.asyncio
async def test_file_write_read(tmp_path):
    f = tmp_path / "test.txt"
    result = await write_file(str(f), "hello world")
    assert result["success"]

    result = await read_file(str(f))
    assert "hello world" in result["content"]


@pytest.mark.asyncio
async def test_file_list_directory(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    result = await list_directory(str(tmp_path))
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_file_read_not_found():
    result = await read_file("/nonexistent/path/file.txt")
    assert "error" in result


# === Bash Tool Tests ===

@pytest.mark.asyncio
async def test_bash_echo():
    result = await execute_bash("echo hello", timeout=5)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


@pytest.mark.asyncio
async def test_bash_error():
    result = await execute_bash("exit 1", timeout=5)
    assert result["exit_code"] == 1


# === System Tools Tests ===

@pytest.mark.asyncio
async def test_system_info():
    info = await get_system_info()
    assert "os" in info
    assert "cpu_count" in info
    assert "ram_total_gb" in info


@pytest.mark.asyncio
async def test_process_list():
    result = await get_process_list(limit=5)
    assert "processes" in result
    assert len(result["processes"]) <= 5


# === SkillSuggester Tests ===

@pytest.mark.asyncio
async def test_skill_suggester_create(config, db):
    sm = SkillManager(config, db)
    suggester = SkillSuggester(db, sm)
    result = await suggester.maybe_create_skill(
        "Создай автоматизацию для деплоя проекта на сервер",
        "\n".join([f"Step {i}: completed" for i in range(15)]),
        force=True,
    )
    assert result is not None
    assert result["action"] == "created"


@pytest.mark.asyncio
async def test_skill_suggester_skip(config, db):
    sm = SkillManager(config, db)
    suggester = SkillSuggester(db, sm)
    result = await suggester.maybe_create_skill("hi", "ok")
    assert result is None
