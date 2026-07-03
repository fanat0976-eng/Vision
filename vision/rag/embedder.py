"""Embedder — generates embeddings for text using various backends."""

import logging
import hashlib
import json
from pathlib import Path

logger = logging.getLogger("vision.rag.embedder")


class Embedder:
    """Text embedding with local hash-based fallback."""

    def __init__(self, model: str = "nomic-embed-text", provider: str = "ollama"):
        self.model = model
        self.provider = provider
        self._cache_dir = Path("embedding_cache")
        self._cache_dir.mkdir(exist_ok=True)

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        # Check cache
        cache_key = hashlib.md5(text.encode()).hexdigest()
        cache_file = self._cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())

        # Try provider
        embedding = None
        if self.provider == "ollama":
            embedding = await self._embed_ollama(text)
        elif self.provider == "openai":
            embedding = await self._embed_openai(text)

        # Fallback: hash-based pseudo-embedding
        if embedding is None:
            embedding = self._hash_embedding(text)

        # Cache
        cache_file.write_text(json.dumps(embedding))
        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.embed(text) for text in texts]

    async def _embed_ollama(self, text: str) -> list[float] | None:
        """Embed using Ollama."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "http://127.0.0.1:11434/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                return resp.json()["embedding"]
        except Exception as e:
            logger.warning(f"Ollama embedding failed: {e}")
            return None

    async def _embed_openai(self, text: str) -> list[float] | None:
        """Embed using OpenAI API."""
        try:
            import httpx
            from vision.core.config import Config
            config = Config.load()

            if not config.llm.api_key:
                return None

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {config.llm.api_key}"},
                    json={"model": "text-embedding-ada-002", "input": text},
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"OpenAI embedding failed: {e}")
            return None

    def _hash_embedding(self, text: str, dim: int = 384) -> list[float]:
        """Generate pseudo-embedding from hash (fallback)."""
        h = hashlib.sha512(text.encode()).digest()
        # Convert bytes to floats in [-1, 1]
        values = []
        for i in range(0, min(len(h), dim), 1):
            values.append((h[i % len(h)] / 127.5) - 1.0)
        # Pad or truncate to dim
        while len(values) < dim:
            values.append(0.0)
        return values[:dim]
