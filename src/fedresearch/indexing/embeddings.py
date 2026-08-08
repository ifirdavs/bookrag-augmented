"""Persistent embedding cache used to resume builds without repeating successful model calls."""

import json
import sqlite3
from pathlib import Path

from fedresearch.llm.client import Embedder, validate_vectors
from fedresearch.schemas import Chunk
from fedresearch.util import digest


class EmbeddingCache:
    def __init__(self, path: Path):
        """Helper to embed_chunks: open the persistent SQLite embedding cache."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS embeddings (cache_key TEXT PRIMARY KEY, vector TEXT NOT NULL)"
        )

    def close(self):
        """Helper to embedding-cache cleanup: close the SQLite connection."""
        self.db.close()

    def embed_chunks(
        self, chunks: list[Chunk], provider: Embedder, batch_size: int
    ) -> tuple[list[list[float]], int]:
        """Reuse cached vectors and embed missing chunks in batches, preserving original chunk order."""
        keys = [
            digest({"identity": provider.identity, "chunk_id": chunk.chunk_id, "text": chunk.text})
            for chunk in chunks
        ]
        vectors, missing = [], []
        for i, key in enumerate(keys):
            row = self.db.execute(
                "SELECT vector FROM embeddings WHERE cache_key=?", (key,)
            ).fetchone()
            if row:
                vectors.append(json.loads(row[0]))
            else:
                vectors.append([])
                missing.append(i)
        hits = len(chunks) - len(missing)
        for start in range(0, len(missing), batch_size):
            batch = missing[start : start + batch_size]
            new_vectors = provider.embed([chunks[i].text for i in batch])
            validate_vectors(new_vectors, len(batch), provider.identity["dimensions"])
            with self.db:
                for i, vector in zip(batch, new_vectors, strict=True):
                    self.db.execute(
                        "INSERT OR REPLACE INTO embeddings VALUES (?,?)",
                        (keys[i], json.dumps(vector)),
                    )
                    vectors[i] = vector
        validate_vectors(vectors, len(chunks), provider.identity["dimensions"])
        return vectors, hits
