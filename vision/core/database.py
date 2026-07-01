"""SQLite database with FTS5 support for full-text search."""

import aiosqlite
from pathlib import Path


class Database:
    """Async SQLite database with FTS5 full-text search."""

    def __init__(self, db_path: str | Path = "vision.db"):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._init_tables()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def _init_tables(self):
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT,
                platform TEXT DEFAULT 'cli'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens_used INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                type TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL,
                uses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                auto_created INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nudges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                shown INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;
        """)
        await self._conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        return self._conn

    async def execute(self, query: str, params=None):
        if params:
            return await self._conn.execute(query, params)
        return await self._conn.execute(query)

    async def commit(self):
        await self._conn.commit()

    async def fetch_one(self, query: str, params=None):
        cursor = await self.execute(query, params)
        return await cursor.fetchone()

    async def fetch_all(self, query: str, params=None):
        cursor = await self.execute(query, params)
        return await cursor.fetchall()

    async def search_messages(self, query: str, limit: int = 20):
        cursor = await self.execute(
            """SELECT m.*, s.title as session_title
               FROM messages_fts f
               JOIN messages m ON m.id = f.rowid
               JOIN sessions s ON s.id = m.session_id
               WHERE messages_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        )
        return await cursor.fetchall()
