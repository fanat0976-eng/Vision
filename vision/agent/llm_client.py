"""LLM client — non-blocking with stall detection."""

import json
import logging
import asyncio
from typing import AsyncGenerator
import requests

from vision.core.config import LLMConfig

logger = logging.getLogger("vision.llm")

STALL_TIMEOUT = 60


class LLMClient:
    """Multi-provider LLM client. All blocking I/O runs in a thread pool."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._warmed_up = False

    def _make_session(self) -> requests.Session:
        """Create a fresh session for each request (thread-safe)."""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        if self.config.api_key:
            s.headers["Authorization"] = f"Bearer {self.config.api_key}"
        return s

    @property
    def _base_url(self) -> str:
        if self.config.provider == "ollama":
            return f"{self.config.base_url}/v1"
        elif self.config.provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return self.config.base_url

    async def _warmup(self):
        if self._warmed_up or self.config.provider != "ollama":
            return
        try:
            # Quick check if Ollama is reachable
            check_session = self._make_session()
            try:
                check_resp = await asyncio.to_thread(
                    check_session.get,
                    f"{self.config.base_url}/api/tags",
                    timeout=3,
                )
                if check_resp.status_code != 200:
                    logger.warning("Ollama not reachable at %s — check if Ollama is running", self.config.base_url)
                    return
            finally:
                check_session.close()

            logger.info("Warming up Ollama model...")
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
                "stream": False,
            }
            session = self._make_session()
            try:
                resp = await asyncio.to_thread(
                    session.post,
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    timeout=60,
                )
                if resp.status_code == 200:
                    self._warmed_up = True
                    logger.info("Model warmed up")
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Warmup failed (non-critical): {e}")

    async def chat(self, messages: list[dict]) -> str:
        """Non-streaming chat with retry."""
        await self._warmup()
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        for attempt in range(3):
            session = self._make_session()
            try:
                resp = await asyncio.to_thread(
                    session.post,
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    timeout=120,
                )
                if resp.status_code == 503 and attempt < 2:
                    logger.warning(f"Model loading (attempt {attempt+1}/3)...")
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"LLM chat error: {e}")
                if attempt == 2:
                    if "Connection" in str(e) or "refused" in str(e).lower():
                        return f"Ошибка: Ollama не доступен на {self.config.base_url}. Запустите Ollama."
                    return f"Error: {e}"
                await asyncio.sleep(2)
            finally:
                session.close()

    async def stream_chat(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Streaming chat with stall detection. Non-blocking."""
        await self._warmup()
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }

        for attempt in range(3):
            session = self._make_session()
            resp = None
            try:
                resp = await asyncio.to_thread(
                    session.post,
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    stream=True,
                    timeout=120,
                )
                if resp.status_code == 503 and attempt < 2:
                    logger.warning(f"Model loading (attempt {attempt+1}/3)...")
                    resp.close()
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()

                # Capture event loop BEFORE entering thread
                loop = asyncio.get_running_loop()
                line_queue: asyncio.Queue[str | None] = asyncio.Queue()

                def _read_lines():
                    try:
                        for line in resp.iter_lines():
                            if line is None:
                                continue
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                asyncio.run_coroutine_threadsafe(
                                    line_queue.put(line_str[6:]),
                                    loop,
                                )
                    except Exception:
                        pass
                    finally:
                        asyncio.run_coroutine_threadsafe(
                            line_queue.put(None),
                            loop,
                        )

                reader_task = asyncio.to_thread(_read_lines)

                while True:
                    try:
                        data_str = await asyncio.wait_for(
                            line_queue.get(), timeout=STALL_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.warning("LLM stream stalled — no data for %ds", STALL_TIMEOUT)
                        yield "\n[Стриминг завис — нет данных]\n"
                        return

                    if data_str is None:
                        break
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

                await reader_task
                return

            except Exception as e:
                logger.error(f"LLM stream error: {e}")
                yield f"\n[Error: {e}]\n"
                return
            finally:
                if resp is not None:
                    resp.close()
                session.close()

    async def close(self):
        pass
