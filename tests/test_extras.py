"""Tests for Vision Phase 6 — Cron + Extras (RAG, Docker, Installer)."""

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock
from vision.core.config import Config
from vision.core.database import Database
from vision.rag.loader import DocumentLoader, Document
from vision.rag.embedder import Embedder
from vision.rag.vector_store import VectorStore, VectorRecord
from vision.rag.retriever import Retriever
from vision.cron.scheduler import CronScheduler


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


# === DocumentLoader Tests ===

def test_loader_init():
    loader = DocumentLoader(chunk_size=500, chunk_overlap=100)
    assert loader.chunk_size == 500
    assert loader.chunk_overlap == 100


def test_loader_split_text():
    loader = DocumentLoader(chunk_size=100, chunk_overlap=20)
    text = "word " * 20  # 100 chars
    chunks = loader._split_text(text)
    assert len(chunks) >= 1


def test_loader_split_short_text():
    loader = DocumentLoader()
    chunks = loader._split_text("Hello world")
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_loader_load_text():
    loader = DocumentLoader()
    docs = loader.load_text("Test content for RAG", source="test.txt")
    assert len(docs) >= 1
    assert docs[0].source == "test.txt"


def test_loader_load_file(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Test\nHello world")
    loader = DocumentLoader()
    docs = loader.load_file(str(f))
    assert len(docs) >= 1
    assert "Test" in docs[0].content


def test_loader_load_nonexistent():
    loader = DocumentLoader()
    docs = loader.load_file("/nonexistent/file.txt")
    assert len(docs) == 0


def test_loader_supported_extensions():
    loader = DocumentLoader()
    assert ".py" in loader.SUPPORTED_EXTENSIONS
    assert ".md" in loader.SUPPORTED_EXTENSIONS
    assert ".xyz" not in loader.SUPPORTED_EXTENSIONS


# === Embedder Tests ===

def test_embedder_init():
    embedder = Embedder(model="test-model", provider="ollama")
    assert embedder.model == "test-model"
    assert embedder.provider == "ollama"


def test_embedder_hash_embedding():
    embedder = Embedder()
    emb = embedder._hash_embedding("test text", dim=128)
    assert len(emb) == 128
    assert all(-1 <= v <= 1 for v in emb)


def test_embedder_hash_deterministic():
    embedder = Embedder()
    emb1 = embedder._hash_embedding("same text")
    emb2 = embedder._hash_embedding("same text")
    assert emb1 == emb2


def test_embedder_hash_different():
    embedder = Embedder()
    emb1 = embedder._hash_embedding("text one")
    emb2 = embedder._hash_embedding("text two")
    assert emb1 != emb2


# === VectorStore Tests ===

@pytest.mark.asyncio
async def test_vector_store_init(db):
    store = VectorStore(db)
    await store.initialize()
    count = await store.count()
    assert count == 0


@pytest.mark.asyncio
async def test_vector_store_add(db):
    store = VectorStore(db)
    await store.initialize()
    record = VectorRecord(
        content="test content",
        source="test.py",
        embedding=[0.1, 0.2, 0.3],
    )
    rid = await store.add(record)
    assert rid is not None
    assert await store.count() == 1


@pytest.mark.asyncio
async def test_vector_store_search(db):
    store = VectorStore(db)
    await store.initialize()
    await store.add(VectorRecord(content="hello", source="a", embedding=[1, 0, 0]))
    await store.add(VectorRecord(content="world", source="b", embedding=[0, 1, 0]))
    results = await store.search([1, 0, 0], limit=1)
    assert len(results) == 1
    assert results[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_vector_store_delete(db):
    store = VectorStore(db)
    await store.initialize()
    rid = await store.add(VectorRecord(content="del", embedding=[1, 2, 3]))
    await store.delete(rid)
    assert await store.count() == 0


@pytest.mark.asyncio
async def test_vector_store_clear(db):
    store = VectorStore(db)
    await store.initialize()
    await store.add(VectorRecord(content="a", embedding=[1]))
    await store.add(VectorRecord(content="b", embedding=[2]))
    await store.clear()
    assert await store.count() == 0


# === Cosine Similarity Tests ===

def test_cosine_similarity_identical():
    store = VectorStore(None)
    score = store._cosine_similarity([1, 0, 0], [1, 0, 0])
    assert abs(score - 1.0) < 0.001


def test_cosine_similarity_orthogonal():
    store = VectorStore(None)
    score = store._cosine_similarity([1, 0, 0], [0, 1, 0])
    assert abs(score) < 0.001


def test_cosine_similarity_opposite():
    store = VectorStore(None)
    score = store._cosine_similarity([1, 0], [-1, 0])
    assert abs(score - (-1.0)) < 0.001


# === Retriever Tests ===

@pytest.mark.asyncio
async def test_retriever_index_text(db):
    retriever = Retriever(db)
    result = await retriever.index_text("Test document content", source="test")
    assert result["indexed"] >= 1


@pytest.mark.asyncio
async def test_retriever_search(db):
    retriever = Retriever(db)
    await retriever.index_text("Python is a programming language", source="lang")
    await retriever.index_text("JavaScript is also a language", source="lang2")
    results = await retriever.search("programming", limit=2)
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_retriever_stats(db):
    retriever = Retriever(db)
    await retriever.index_text("content", source="test")
    stats = await retriever.get_stats()
    assert stats["total_documents"] >= 1


@pytest.mark.asyncio
async def test_retriever_index_file(db, tmp_path):
    f = tmp_path / "readme.md"
    f.write_text("# Vision\nAI agent with gesture control")
    retriever = Retriever(db)
    result = await retriever.index_file(str(f))
    assert result["indexed"] >= 1


# === CronScheduler Tests ===

def test_cron_add_job():
    scheduler = CronScheduler()
    result = scheduler.add_job("test", "0 9 * * *", "echo hello")
    assert result.get("success") is True


def test_cron_invalid_expression():
    scheduler = CronScheduler()
    scheduler.clear()
    result = scheduler.add_job("bad", "invalid", "cmd")
    assert "error" in result


def test_cron_list_jobs():
    scheduler = CronScheduler()
    scheduler.clear()
    scheduler.add_job("j1", "0 9 * * *", "cmd1")
    scheduler.add_job("j2", "30 18 * * *", "cmd2")
    jobs = scheduler.list_jobs()
    assert len(jobs) == 2


def test_cron_remove_job():
    scheduler = CronScheduler()
    scheduler.clear()
    scheduler.add_job("to-remove", "0 9 * * *", "cmd")
    jobs = scheduler.list_jobs()
    result = scheduler.remove_job(jobs[0]["id"])
    assert result.get("success") is True
    assert len(scheduler.list_jobs()) == 0


def test_cron_enable_disable():
    scheduler = CronScheduler()
    scheduler.clear()
    scheduler.add_job("toggle", "0 9 * * *", "cmd")
    jobs = scheduler.list_jobs()
    scheduler.disable_job(jobs[0]["id"])
    assert scheduler.list_jobs()[0]["enabled"] is False
    scheduler.enable_job(jobs[0]["id"])
    assert scheduler.list_jobs()[0]["enabled"] is True


@pytest.mark.asyncio
async def test_cron_daily_report(db):
    scheduler = CronScheduler(db)
    report = await scheduler.generate_daily_report()
    assert "Vision Daily Report" in report
    assert "Sessions today" in report


# === Config Extras Tests ===

def test_config_save_load_with_rag(tmp_path):
    config = Config()
    path = tmp_path / "config.json"
    config.save(path)
    loaded = Config.load(path)
    assert loaded.llm.provider == "ollama"


# === Docker/Installer Tests ===

def test_dockerfile_exists():
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists()


def test_docker_compose_exists():
    compose = Path("docker-compose.yml")
    assert compose.exists()


def test_installer_exists():
    installer = Path("scripts/install.bat")
    assert installer.exists()
