"""Document loader — loads and chunks documents for RAG."""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Document:
    content: str
    source: str
    chunk_index: int = 0
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DocumentLoader:
    """Loads documents from files and splits into chunks."""

    SUPPORTED_EXTENSIONS = {
        ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
        ".csv", ".log", ".sh", ".bat", ".ps1", ".toml", ".cfg",
    }

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_file(self, path: str) -> list[Document]:
        """Load a single file and split into chunks."""
        p = Path(path)
        if not p.exists():
            return []

        ext = p.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            return []

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        chunks = self._split_text(content)
        return [
            Document(
                content=chunk,
                source=str(p),
                chunk_index=i,
                metadata={"extension": ext, "size": len(content)},
            )
            for i, chunk in enumerate(chunks)
        ]

    def load_directory(self, path: str, recursive: bool = True) -> list[Document]:
        """Load all supported files from a directory."""
        p = Path(path)
        if not p.is_dir():
            return []

        documents = []
        pattern = "**/*" if recursive else "*"
        for file_path in p.glob(pattern):
            if file_path.is_file():
                documents.extend(self.load_file(str(file_path)))

        return documents

    def load_text(self, text: str, source: str = "inline") -> list[Document]:
        """Load raw text as documents."""
        chunks = self._split_text(text)
        return [
            Document(content=chunk, source=source, chunk_index=i)
            for i, chunk in enumerate(chunks)
        ]

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence/line boundary
            if end < len(text):
                last_newline = chunk.rfind("\n")
                last_period = chunk.rfind(".")
                break_at = max(last_newline, last_period)
                if break_at > self.chunk_size // 2:
                    chunk = chunk[:break_at + 1]
                    end = start + break_at + 1

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if c]
