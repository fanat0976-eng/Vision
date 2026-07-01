"""Tests for Vision Phase 4 — Gateway + Telegram."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from vision.core.config import Config
from vision.core.database import Database
from vision.agent.agent import Agent


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def config():
    return Config()


# === Telegram Platform Tests ===

def test_telegram_platform_init(config, db):
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token_123", agent)
    assert platform.token == "test_token_123"
    assert platform._running is False


@pytest.mark.asyncio
async def test_telegram_handle_command_start(config, db):
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token", lambda: agent)

    response = await platform._handle_command("/start")
    assert "Vision" in response
    assert "помогу" in response


@pytest.mark.asyncio
async def test_telegram_handle_command_help(config, db):
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token", lambda: agent)

    response = await platform._handle_command("/help")
    assert "Commands" in response or "Команды" in response


@pytest.mark.asyncio
async def test_telegram_handle_command_skills_empty(config, db):
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token", lambda: agent)

    response = await platform._handle_command("/skills")
    assert "скилл" in response.lower() or "skill" in response.lower()


@pytest.mark.asyncio
async def test_telegram_handle_command_unknown(config, db):
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token", lambda: agent)

    response = await platform._handle_command("/blah")
    assert "неизвестная" in response.lower() or "unknown" in response.lower()


# === Gateway Server Tests ===

def test_gateway_create_app():
    from vision.gateway.server import create_app
    app = create_app()
    assert app.title == "Vision Gateway"
    assert app.version == "0.1.0"


def test_gateway_routes():
    from vision.gateway.server import create_app
    app = create_app()
    routes = [r.path for r in app.routes]
    assert "/api/health" in routes
    assert "/api/sessions" in routes
    assert "/api/skills" in routes
    assert "/api/memory" in routes
    assert "/api/chat" in routes
    assert "/ws" in routes


# === Config Gateway Tests ===

def test_config_gateway_defaults():
    config = Config()
    assert config.gateway.host == "0.0.0.0"
    assert config.gateway.port == 8080
    assert config.gateway.ws_port == 8081
    assert config.gateway.auth_token == ""


def test_config_gateway_save_load(tmp_path):
    config = Config()
    config.gateway.auth_token = "my_telegram_token"
    config.gateway.port = 9090
    path = tmp_path / "config.json"
    config.save(path)

    loaded = Config.load(path)
    assert loaded.gateway.auth_token == "my_telegram_token"
    assert loaded.gateway.port == 9090


# === Integration: Agent + Gateway ===

@pytest.mark.asyncio
async def agent_gateway_integration(config, db):
    """Test agent can be used from gateway context."""
    agent = Agent(config, db)
    session_id = await agent.start_session(platform="test")
    assert session_id is not None

    # Verify session exists
    row = await db.fetch_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    assert row is not None
    assert row["platform"] == "test"


@pytest.mark.asyncio
async def test_telegram_message_flow(config, db):
    """Test full Telegram message flow (mocked HTTP)."""
    from vision.gateway.platforms.telegram import TelegramPlatform
    agent = Agent(config, db)
    platform = TelegramPlatform("test_token", lambda: agent)

    # Mock the agent's process_message
    async def mock_process(msg):
        yield f"Echo: {msg}"

    agent.process_message = mock_process

    # Mock httpx client
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True, "result": []}
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # Test _send_message
    await platform._send_message(mock_client, 12345, "Hello!")
    mock_client.post.assert_called_once()


# === Platform __init__ Tests ===

def test_platform_import():
    from vision.gateway.platforms import TelegramPlatform
    assert TelegramPlatform is not None
