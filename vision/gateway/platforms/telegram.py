"""Telegram platform — bot integration for Vision."""

import logging
import asyncio
from typing import AsyncGenerator

logger = logging.getLogger("vision.telegram")


class TelegramPlatform:
    """Telegram bot platform for Vision gateway."""

    def __init__(self, token: str, agent_factory):
        self.token = token
        self._agent_factory = agent_factory  # callable that returns fresh Agent
        self._running = False

    async def start(self):
        """Start the Telegram bot polling."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed. Run: pip install httpx")
            return

        self._running = True
        offset = 0

        async with httpx.AsyncClient() as client:
            logger.info("Telegram bot started")
            while self._running:
                try:
                    resp = await client.get(
                        f"https://api.telegram.org/bot{self.token}/getUpdates",
                        params={"offset": offset, "timeout": 30},
                        timeout=35,
                    )
                    data = resp.json()

                    if not data.get("ok"):
                        await asyncio.sleep(5)
                        continue

                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        await self._handle_update(client, update)

                except Exception as e:
                    logger.error(f"Telegram polling error: {e}")
                    await asyncio.sleep(5)

    async def _handle_update(self, client, update: dict):
        """Handle a single Telegram update."""
        message = update.get("message")
        if not message:
            return

        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})

        if not text:
            return

        logger.info(f"Telegram message from {user.get('first_name', 'unknown')}: {text[:50]}")

        # Handle commands
        if text.startswith("/"):
            response = await self._handle_command(text)
        else:
            # Each chat gets its own agent — no shared state
            agent = self._agent_factory()
            session_id = f"tg_{chat_id}"
            await agent.start_session(session_id, platform="telegram")

            response = ""
            async for chunk in agent.process_message(text):
                response += chunk

        # Send response
        await self._send_message(client, chat_id, response)

    async def _handle_command(self, text: str) -> str:
        """Handle slash commands."""
        cmd = text.strip().split()
        name = cmd[0].lower()

        if name == "/start":
            return ("👋 Привет! Я Vision — self-improving AI-ассистент.\n\n"
                    "Просто напишите мне сообщение, и я помогу!\n\n"
                    "Команды:\n"
                    "/new — Новая сессия\n"
                    "/skills — Мои скиллы\n"
                    "/help — Помощь")
        elif name == "/help":
            return ("Vision Commands:\n"
                    "/new — Start new session\n"
                    "/skills — List learned skills\n"
                    "/memory — Show memories\n"
                    "/help — This help")
        elif name == "/new":
            return "Новая сессия начата! ✅"
        elif name == "/skills":
            agent = self._agent_factory()
            skills = await agent.skills.list_skills()
            if not skills:
                return "Пока нет скиллов. Выполняйте сложные задачи — я создам скиллы автоматически! 🧠"
            lines = [f"• {s['name']} (использован {s['uses']}x)" for s in skills[:10]]
            return "📚 Ваши скиллы:\n" + "\n".join(lines)
        else:
            return f"Неизвестная команда: {name}. Напишите /help"

    async def _send_message(self, client, chat_id: int, text: str):
        """Send a message via Telegram API."""
        # Split long messages (Telegram limit 4096 chars)
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")

    async def stop(self):
        self._running = False
        logger.info("Telegram bot stopped")
