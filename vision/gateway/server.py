"""Vision gateway server — FastAPI + WebSocket + Telegram."""

import json
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from vision.core.config import Config
from vision.core.database import Database
from vision.agent.agent import Agent

logger = logging.getLogger("vision.gateway")


def create_app(config: Config | None = None) -> FastAPI:
    if config is None:
        config = Config.load()

    app = FastAPI(title="Vision Gateway", version="0.1.0")

    # CORS: whitelist local origins only
    allowed_origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:1420",
        "http://127.0.0.1:1420",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _state = {"db": None, "config": config}

    @app.on_event("startup")
    async def startup():
        db = Database(config.db_path)
        await db.connect()
        _state["db"] = db
        logger.info("Vision gateway started")

        if config.gateway.auth_token:
            from vision.gateway.platforms.telegram import TelegramPlatform
            agent_factory = lambda: Agent(config, db)
            tg = TelegramPlatform(config.gateway.auth_token, agent_factory)
            _state["telegram"] = tg
            asyncio.create_task(tg.start())
            logger.info("Telegram bot started")

    @app.on_event("shutdown")
    async def shutdown():
        if _state.get("telegram"):
            await _state["telegram"].stop()
        if _state["db"]:
            await _state["db"].close()

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/sessions")
    async def list_sessions():
        db = _state["db"]
        rows = await db.fetch_all(
            "SELECT id, title, platform, created_at FROM sessions ORDER BY created_at DESC LIMIT 50"
        )
        return {"sessions": [dict(r) for r in rows]}

    @app.get("/api/skills")
    async def list_skills():
        db = _state["db"]
        rows = await db.fetch_all(
            "SELECT name, content, uses, auto_created, created_at FROM skills ORDER BY uses DESC"
        )
        return {"skills": [dict(r) for r in rows]}

    @app.get("/api/memory")
    async def list_memory():
        db = _state["db"]
        rows = await db.fetch_all("SELECT key, content, type FROM memories ORDER BY updated_at DESC")
        return {"memories": [dict(r) for r in rows]}

    @app.post("/api/chat")
    async def chat(payload: dict):
        # Each request gets its own Agent — no shared state
        agent = Agent(_state["config"], _state["db"])
        message = payload.get("message", "")
        await agent.start_session()

        response = ""
        async for chunk in agent.process_message(message):
            response += chunk

        return {"response": response, "session_id": agent.current_session}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        # Each WS connection gets its own Agent
        agent = Agent(_state["config"], _state["db"])
        session_id = await agent.start_session(platform="websocket")

        try:
            while True:
                data = await ws.receive_text()

                # Validate message size (1MB limit)
                if len(data) > 1_000_000:
                    await ws.send_json({"type": "error", "content": "Message too large"})
                    continue

                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "content": "Invalid JSON"})
                    continue

                message = payload.get("message", "")

                await ws.send_json({"type": "start", "session_id": session_id})

                async for chunk in agent.process_message(message):
                    await ws.send_json({"type": "chunk", "content": chunk})

                await ws.send_json({"type": "done"})
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")

    # Serve chat UI
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding="utf-8")
        return "<h1>Vision Gateway</h1><p>Static UI not found. Use <a href='/docs'>/docs</a></p>"

    return app
