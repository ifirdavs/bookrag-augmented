"""Persistent SQLite FTS5 BM25 search over the same source chunks as Chroma."""

import json
import re
import sqlite3
from pathlib import Path

from fedresearch.schemas import Chunk


def lexical_identity(index_id: str, chunk_fingerprint: str) -> dict:
    """Helper to lexical persistence: identify the source chunks, tokenizer and BM25 implementation."""
    return {
        "schema_version": 1,
        "index_id": index_id,
        "chunk_fingerprint": chunk_fingerprint,
        "implementation": "sqlite-fts5-bm25",
        "sqlite_version": sqlite3.sqlite_version,
        "tokenizer": "unicode61 remove_diacritics 0",
        "k1": 1.2,
        "b": 0.75,
    }


def build_lexical_index(path: Path, index_id: str, fingerprint: str, chunks: list[Chunk]) -> dict:
    """Build a local BM25 sidecar atomically, without requesting or changing embeddings."""
    identity = lexical_identity(index_id, fingerprint)
    temporary = path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        with connection:
            connection.execute("CREATE TABLE metadata (payload TEXT NOT NULL)")
            connection.execute("INSERT INTO metadata VALUES (?)", (json.dumps(identity),))
            connection.execute(
                "CREATE VIRTUAL TABLE passages USING fts5("
                "chunk_id UNINDEXED, paper_id UNINDEXED, text, "
                "tokenize='unicode61 remove_diacritics 0')"
            )
            connection.executemany(
                "INSERT INTO passages VALUES (?, ?, ?)",
                [(chunk.chunk_id, chunk.paper_id, chunk.text) for chunk in chunks],
            )
    finally:
        connection.close()
    temporary.replace(path)
    return {**identity, "chunks": len(chunks)}


class LexicalIndex:
    def __init__(self, path: Path, index_id: str, fingerprint: str, chunks: int):
        """Helper to hybrid retrieval: open a BM25 index bound to the active dense index."""
        if not path.is_file():
            raise ValueError("BM25 index is missing. Run fedresearch index first")
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            self.identity = json.loads(
                self.db.execute("SELECT payload FROM metadata").fetchone()[0]
            )
            if (
                self.identity != lexical_identity(index_id, fingerprint)
                or self.db.execute("SELECT count(*) FROM passages").fetchone()[0] != chunks
            ):
                raise ValueError("BM25 index is incompatible. Run fedresearch index again")
        except Exception:
            self.db.close()
            raise

    def close(self):
        """Helper to retrieval cleanup: close the read-only lexical database."""
        self.db.close()

    def query(
        self, query: str, limit: int, paper_ids: list[str], chunk_ids: list[str] | None = None
    ) -> list[tuple[str, float]]:
        """Rank matching chunks with BM25, applying the same source filters before the result cap."""
        # Quote each word so user text cannot become an FTS operator or column expression.
        terms = list(dict.fromkeys(re.findall(r"[^\W_]+", query)))
        if not terms or not paper_ids or chunk_ids == []:
            return []
        expression = " OR ".join(f'"{term}"' for term in terms)
        conditions = ["passages MATCH ?", f"paper_id IN ({','.join('?' for _ in paper_ids)})"]
        parameters = [expression, *paper_ids]
        if chunk_ids is not None:
            conditions.append(f"chunk_id IN ({','.join('?' for _ in chunk_ids)})")
            parameters.extend(chunk_ids)
        rows = self.db.execute(
            "SELECT chunk_id, rank FROM passages WHERE "
            + " AND ".join(conditions)
            + " ORDER BY rank, chunk_id LIMIT ?",
            [*parameters, limit],
        )
        # SQLite returns better BM25 matches as more negative numbers; expose higher-is-better.
        return [(identifier, -score) for identifier, score in rows]
