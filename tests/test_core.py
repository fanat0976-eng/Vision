"""Tests for Vision core modules."""

import pytest
import asyncio
from vision.core.config import Config
from vision.core.database import Database
from vision.core.memory import MemoryManager
from vision.agent.skill_manager import SkillManager


@pytest.fixture
def config():
    return Config()


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_config_defaults():
    config = Config()
    assert config.llm.provider == "ollama"
    assert config.llm.model == "qwen2.5:14b"
    assert config.voice.enabled is False
    assert config.gestures.enabled is False


@pytest.mark.asyncio
async def test_config_save_load(tmp_path):
    config = Config()
    config.llm.model = "test-model"
    path = tmp_path / "config.json"
    config.save(path)

    loaded = Config.load(path)
    assert loaded.llm.model == "test-model"


@pytest.mark.asyncio
async def test_database_tables(db):
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r["name"] for r in await cursor.fetchall()]
    assert "sessions" in tables
    assert "messages" in tables
    assert "memories" in tables
    assert "skills" in tables
    assert "user_profile" in tables


@pytest.mark.asyncio
async def test_memory_save_get(db):
    memory = MemoryManager(db)
    await memory.save_memory("test_key", "test_value", "free")
    row = await memory.get_memory("test_key")
    assert row is not None
    assert row["key"] == "test_key"
    assert row["content"] == "test_value"


@pytest.mark.asyncio
async def test_memory_delete(db):
    memory = MemoryManager(db)
    await memory.save_memory("to_delete", "value")
    await memory.delete_memory("to_delete")
    row = await memory.get_memory("to_delete")
    assert row is None


@pytest.mark.asyncio
async def test_memory_profile(db):
    memory = MemoryManager(db)
    await memory.set_profile("language", "ru")
    value = await memory.get_profile("language")
    assert value == "ru"

    await memory.set_profile("language", "en")
    value = await memory.get_profile("language")
    assert value == "en"


@pytest.mark.asyncio
async def test_skill_create(config, db):
    skill_mgr = SkillManager(config, db)
    result = await skill_mgr.create_skill("test-skill", "# Test\nDo something")
    assert result["action"] == "created"

    skills = await skill_mgr.list_skills()
    assert len(skills) == 1
    assert skills[0]["name"] == "test-skill"


@pytest.mark.asyncio
async def test_skill_update(config, db):
    skill_mgr = SkillManager(config, db)
    await skill_mgr.create_skill("merge-skill", "Version 1")
    result = await skill_mgr.create_skill("merge-skill", "Version 2")
    assert result["action"] == "updated"

    skill = await skill_mgr.get_skill("merge-skill")
    assert "Version 1" in skill["content"]
    assert "Version 2" in skill["content"]


@pytest.mark.asyncio
async def test_skill_use(config, db):
    skill_mgr = SkillManager(config, db)
    await skill_mgr.create_skill("used-skill", "content")
    await skill_mgr.use_skill("used-skill")
    await skill_mgr.use_skill("used-skill")
    skill = await skill_mgr.get_skill("used-skill")
    assert skill["uses"] == 2


@pytest.mark.asyncio
async def test_fts_search(db):
    await db.execute(
        "INSERT INTO sessions (id) VALUES (?)", ("test_session",)
    )
    await db.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        ("test_session", "user", "Hello world"),
    )
    await db.commit()

    results = await db.search_messages("Hello")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_skill_auto_create_suggest(config, db):
    skill_mgr = SkillManager(config, db)
    # Long task + keyword "создай" + many result lines = should suggest
    task = "Создай скрипт для автоматической сборки проекта с тестами и деплоем на сервер через Docker"
    result = "\n".join([f"Step {i}: done" for i in range(15)])
    name = await skill_mgr.should_auto_create(task, result)
    assert name is not None
    assert len(name) > 0
