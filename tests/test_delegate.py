"""Tests for Vision Phase 3 — Agent Delegation."""

import pytest
import asyncio
from vision.core.config import Config
from vision.core.database import Database
from vision.agent.subagent import Subagent, SubagentResult
from vision.agent.delegate import DelegateManager, DelegateTask
from vision.tools.delegate_tools import DelegateTools


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def config():
    cfg = Config()
    # Use a mock-like approach: we'll test the structure, not real LLM calls
    return cfg


# === Subagent Tests ===

@pytest.mark.asyncio
async def test_subagent_init(config, db):
    sub = Subagent("test_1", config, db)
    assert sub.task_id == "test_1"
    assert sub.session_id.startswith("sub_test_1_")
    assert sub.result.status == "running"


def test_subagent_system_prompt(config, db):
    sub = Subagent("test_2", config, db)
    prompt = sub._build_system_prompt()
    assert "test_2" in prompt
    assert "subagent" in prompt.lower()


def test_subagent_parse_tool_call(config, db):
    sub = Subagent("test_3", config, db)
    text = 'I need to read a file. [TOOL:read_file(path="test.txt")] Done.'
    name, args = sub._parse_tool_call(text)
    assert name == "read_file"
    assert args.get("path") == "test.txt"


def test_subagent_parse_no_tool(config, db):
    sub = Subagent("test_4", config, db)
    name, args = sub._parse_tool_call("Just a normal response.")
    assert name is None


# === DelegateManager Tests ===

@pytest.mark.asyncio
async def test_delegate_next_id(config, db):
    mgr = DelegateManager(config, db)
    id1 = mgr._next_id()
    id2 = mgr._next_id()
    assert id1 != id2
    assert id1.startswith("task_")
    assert id2.startswith("task_")


@pytest.mark.asyncio
async def test_delegate_task_lifecycle(config, db):
    mgr = DelegateManager(config, db)
    # Create a task entry manually to test lifecycle
    task = DelegateTask(
        id="manual_1",
        prompt="test prompt",
        status="pending",
        created_at="2026-01-01T00:00:00",
    )
    mgr.tasks["manual_1"] = task
    assert mgr.get_task("manual_1") is not None
    assert mgr.get_task("nonexistent") is None


@pytest.mark.asyncio
async def test_delegate_list_tasks(config, db):
    mgr = DelegateManager(config, db)
    mgr.tasks["a"] = DelegateTask(id="a", prompt="task a", status="done")
    mgr.tasks["b"] = DelegateTask(id="b", prompt="task b", status="failed")
    tasks = mgr.list_tasks()
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_delegate_aggregate_results(config, db):
    mgr = DelegateManager(config, db)
    t1 = DelegateTask(id="t1", prompt="p1", status="done")
    t1.result = SubagentResult(task_id="t1", status="done", result="Result A")
    t2 = DelegateTask(id="t2", prompt="p2", status="failed")
    t2.result = SubagentResult(task_id="t2", status="failed", error="Error B")

    aggregated = mgr.aggregate_results([t1, t2])
    assert "Result A" in aggregated
    assert "Error B" in aggregated
    assert "✓" in aggregated
    assert "✗" in aggregated


# === DelegateTools Tests ===

@pytest.mark.asyncio
async def test_delegate_tools_list(config, db):
    tools = DelegateTools(config, db)
    result = await tools.list_tasks()
    assert "tasks" in result


@pytest.mark.asyncio
async def test_delegate_tools_get_nonexistent(config, db):
    tools = DelegateTools(config, db)
    result = await tools.get_task_result("nonexistent")
    assert "error" in result


# === Parallel Execution Tests ===

@pytest.mark.asyncio
async def test_delegate_parallel_structure(config, db):
    """Test that parallel spawn creates correct task structure."""
    mgr = DelegateManager(config, db)
    # We can't actually call LLM in tests, so test the task creation
    prompts = ["task 1", "task 2", "task 3"]
    for p in prompts:
        tid = mgr._next_id()
        task = DelegateTask(id=tid, prompt=p, status="pending")
        mgr.tasks[tid] = task

    assert len(mgr.tasks) == 3


# === DAG Execution Tests ===

@pytest.mark.asyncio
async def test_delegate_dag_structure(config, db):
    """Test DAG structure creation."""
    mgr = DelegateManager(config, db)
    dag = [
        {"id": "t1", "prompt": "Step 1", "deps": []},
        {"id": "t2", "prompt": "Step 2", "deps": ["t1"]},
        {"id": "t3", "prompt": "Step 3", "deps": ["t1", "t2"]},
    ]
    for spec in dag:
        task = DelegateTask(
            id=spec["id"],
            prompt=spec["prompt"],
            status="pending",
            dependencies=spec["deps"],
        )
        mgr.tasks[spec["id"]] = task

    # Verify dependencies
    t2 = mgr.get_task("t2")
    assert "t1" in t2.dependencies
    t3 = mgr.get_task("t3")
    assert "t1" in t3.dependencies
    assert "t2" in t3.dependencies


# === Integration Tests ===

@pytest.mark.asyncio
async def test_subagent_memory_isolation(config, db):
    """Test that subagents have isolated memory."""
    sub1 = Subagent("iso_1", config, db)
    sub2 = Subagent("iso_2", config, db)

    # Create sessions in DB first
    await db.execute("INSERT INTO sessions (id, platform) VALUES (?, ?)", (sub1.session_id, "test"))
    await db.execute("INSERT INTO sessions (id, platform) VALUES (?, ?)", (sub2.session_id, "test"))
    await db.commit()

    await sub1.memory.add_message(sub1.session_id, "user", "Message for sub1")
    await sub2.memory.add_message(sub2.session_id, "user", "Message for sub2")

    history1 = await sub1.memory.get_history(sub1.session_id)
    history2 = await sub2.memory.get_history(sub2.session_id)

    assert len(history1) == 1
    assert len(history2) == 1
    assert history1[0]["content"] == "Message for sub1"
    assert history2[0]["content"] == "Message for sub2"


@pytest.mark.asyncio
async def test_subagent_result_dataclass():
    """Test SubagentResult dataclass."""
    result = SubagentResult(
        task_id="test",
        status="done",
        result="hello",
        tokens_used=100,
    )
    assert result.task_id == "test"
    assert result.status == "done"
    assert result.tokens_used == 100
    assert result.error is None


@pytest.mark.asyncio
async def test_delegate_task_dataclass():
    """Test DelegateTask dataclass."""
    task = DelegateTask(
        id="dt_1",
        prompt="do something",
        status="running",
        dependencies=["dt_0"],
    )
    assert task.id == "dt_1"
    assert task.dependencies == ["dt_0"]
    assert task.result is None
