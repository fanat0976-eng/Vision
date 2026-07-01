"""Retriever — combines loader, embedder, and vector store for RAG."""

import logging
from vision.rag.loader import DocumentLoader
from vision.rag.embedder import Embedder
from vision.rag.vector_store import VectorStore, VectorRecord
from vision.core.database import Database

logger = logging.getLogger("vision.rag.retriever")


class Retriever:
    """RAG retriever — index documents and search with context."""

    def __init__(self, db: Database):
        self.loader = DocumentLoader()
        self.embedder = Embedder()
        self.vector_store = VectorStore(db)

    async def index_file(self, path: str) -> dict:
        """Index a file into the vector store."""
        docs = self.loader.load_file(path)
        if not docs:
            return {"error": f"Could not load file: {path}"}

        records = []
        for doc in docs:
            embedding = await self.embedder.embed(doc.content)
            records.append(VectorRecord(
                content=doc.content,
                source=doc.source,
                embedding=embedding,
                metadata=doc.metadata,
            ))

        ids = await self.vector_store.add_batch(records)
        return {"indexed": len(ids), "source": path}

    async def index_directory(self, path: str) -> dict:
        """Index all files in a directory."""
        docs = self.loader.load_directory(path)
        if not docs:
            return {"error": f"No documents found in: {path}"}

        records = []
        for doc in docs:
            embedding = await self.embedder.embed(doc.content)
            records.append(VectorRecord(
                content=doc.content,
                source=doc.source,
                embedding=embedding,
                metadata=doc.metadata,
            ))

        ids = await self.vector_store.add_batch(records)
        sources = set(doc.source for doc in docs)
        return {"indexed": len(ids), "sources": len(sources)}

    async def index_text(self, text: str, source: str = "inline") -> dict:
        """Index raw text."""
        docs = self.loader.load_text(text, source)
        records = []
        for doc in docs:
            embedding = await self.embedder.embed(doc.content)
            records.append(VectorRecord(
                content=doc.content,
                source=doc.source,
                embedding=embedding,
            ))
        ids = await self.vector_store.add_batch(records)
        return {"indexed": len(ids), "source": source}

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search for relevant documents."""
        query_embedding = await self.embedder.embed(query)
        results = await self.vector_store.search(query_embedding, limit)
        return results

    async def search_with_context(self, query: str, limit: int = 3) -> str:
        """Search and format results as context for LLM."""
        results = await self.search(query, limit)
        if not results:
            return ""

        parts = []
        for r in results:
            source = r["source"].split("/")[-1] if r["source"] else "unknown"
            score = r["score"]
            content = r["content"][:500]
            parts.append(f"[{source} (score: {score:.2f})]\n{content}")

        return "\n\n---\n\n".join(parts)

    async def get_stats(self) -> dict:
        """Get vector store statistics."""
        count = await self.vector_store.count()
        return {"total_documents": count}
