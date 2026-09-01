"""SQLite lookup of papers, hierarchy, chunks and original source spans."""

import sqlite3
from pathlib import Path

from fedresearch.schemas import Block, Chunk, Paper, ParsedDocument, Section


class MetadataStore:
    def __init__(self, path: Path, create: bool = False):
        """Helper to source storage: open SQLite and create provenance tables when requested."""
        in_memory = str(path) == ":memory:"
        if not create and not in_memory and not path.is_file():
            raise ValueError("Metadata store does not exist; build an index first")
        if not in_memory:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys = ON")
        if create:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS papers (paper_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sections (section_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers, parent_id TEXT REFERENCES sections, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS blocks (block_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers, section_id TEXT NOT NULL REFERENCES sections, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers, section_id TEXT NOT NULL REFERENCES sections, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunk_spans (chunk_id TEXT NOT NULL REFERENCES chunks, ordinal INTEGER NOT NULL, block_id TEXT NOT NULL REFERENCES blocks, start INTEGER NOT NULL, end INTEGER NOT NULL, PRIMARY KEY(chunk_id, ordinal), CHECK(start >= 0 AND end > start));
                CREATE INDEX IF NOT EXISTS blocks_by_paper ON blocks(paper_id);
                CREATE INDEX IF NOT EXISTS chunks_by_paper ON chunks(paper_id);
                CREATE INDEX IF NOT EXISTS spans_by_block ON chunk_spans(block_id);
            """)

    def close(self):
        """Helper to source-store cleanup: close the SQLite connection."""
        self.db.close()

    def __enter__(self):
        """Helper to source-store context management: return the open store."""
        return self

    def __exit__(self, *_):
        """Helper to source-store context management: close the store after use."""
        self.close()

    def add_document(self, doc: ParsedDocument):
        """Insert one canonical paper, sections, blocks, chunks and source spans in a transaction."""
        with self.db:
            self.db.execute(
                "INSERT INTO papers VALUES (?, ?)",
                (doc.paper.paper_id, doc.paper.model_dump_json()),
            )
            self.db.executemany(
                "INSERT INTO sections VALUES (?, ?, ?, ?)",
                [
                    (s.section_id, s.paper_id, s.parent_id, s.model_dump_json())
                    for s in doc.sections
                ],
            )
            self.db.executemany(
                "INSERT INTO blocks VALUES (?, ?, ?, ?)",
                [(b.block_id, b.paper_id, b.section_id, b.model_dump_json()) for b in doc.blocks],
            )
            self.db.executemany(
                "INSERT INTO chunks VALUES (?, ?, ?, ?)",
                [(c.chunk_id, c.paper_id, c.section_id, c.model_dump_json()) for c in doc.chunks],
            )
            self.db.executemany(
                "INSERT INTO chunk_spans VALUES (?, ?, ?, ?, ?)",
                [
                    (c.chunk_id, i, s.block_id, s.start, s.end)
                    for c in doc.chunks
                    for i, s in enumerate(c.spans)
                ],
            )

    def _get(self, table, key, identifier, model):
        # Table/column names are internal constants, never user inputs.
        """Helper to typed source lookups: load one JSON record using internal table/column names."""
        row = self.db.execute(
            f"SELECT payload FROM {table} WHERE {key} = ?", (identifier,)
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown {key}: {identifier}")
        return model.model_validate_json(row[0])

    def paper(self, identifier: str) -> Paper:
        """Helper to citations and filters: load a paper by its stable ID."""
        return self._get("papers", "paper_id", identifier, Paper)

    def chunk(self, identifier: str) -> Chunk:
        """Helper to retrieval: load chunk text and provenance by chunk ID."""
        return self._get("chunks", "chunk_id", identifier, Chunk)

    def block(self, identifier: str) -> Block:
        """Helper to citation validation: load original text and PDF coordinates by block ID."""
        return self._get("blocks", "block_id", identifier, Block)

    def section(self, identifier: str) -> Section:
        """Helper to section lookup: load a section and its hierarchy path by ID."""
        return self._get("sections", "section_id", identifier, Section)

    def papers(self) -> list[Paper]:
        """Helper to corpus filters: list paper metadata in stable paper-ID order."""
        return [
            Paper.model_validate_json(row[0])
            for row in self.db.execute("SELECT payload FROM papers ORDER BY paper_id")
        ]

    def chunks(self) -> list[Chunk]:
        """Helper to retrieval filters: list chunks in stable chunk-ID order."""
        return [
            Chunk.model_validate_json(row[0])
            for row in self.db.execute("SELECT payload FROM chunks ORDER BY chunk_id")
        ]

    def sections(self) -> list[Section]:
        """Helper to hierarchy expansion: list persisted sections and their direct parent links."""
        return [
            Section.model_validate_json(row[0])
            for row in self.db.execute("SELECT payload FROM sections ORDER BY section_id")
        ]

    def statistics(self) -> dict:
        """Helper to index validation: count stored papers, sections, blocks and chunks."""
        return {
            table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("papers", "sections", "blocks", "chunks")
        }
