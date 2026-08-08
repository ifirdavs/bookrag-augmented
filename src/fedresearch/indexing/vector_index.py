"""Chroma persistence and dense vector search with metadata filters."""

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from fedresearch.schemas import Chunk


class VectorIndex:
    def __init__(self, path: Path, create: bool = False):
        """Helper to vector operations: create or open the persistent cosine-similarity collection."""
        if not create and not path.is_dir():
            raise ValueError("Dense index does not exist")
        self.client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        if create:
            self.collection = self.client.get_or_create_collection(
                "fixed_dense", embedding_function=None, metadata={"hnsw:space": "cosine"}
            )
        else:
            self.collection = self.client.get_collection("fixed_dense", embedding_function=None)

    def add(self, chunks: list[Chunk], vectors: list[list[float]]):
        """Store chunk vectors and their source identities in bounded Chroma batches."""
        for start in range(0, len(chunks), 128):
            batch = chunks[start : start + 128]
            self.collection.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=vectors[start : start + len(batch)],
                metadatas=[
                    {"paper_id": c.paper_id, "parse_id": c.parse_id, "chunk_id": c.chunk_id}
                    for c in batch
                ],
            )

    def query(
        self,
        vector: list[float],
        limit: int,
        paper_ids: list[str] | None = None,
        chunk_ids: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Return dense candidates with cosine scores and optional paper/chunk filters."""
        if paper_ids == [] or chunk_ids == [] or not self.collection.count():
            return []
        filters = []
        if paper_ids is not None:
            filters.append({"paper_id": {"$in": paper_ids}})
        if chunk_ids is not None:
            filters.append({"chunk_id": {"$in": chunk_ids}})
        kwargs = (
            {"where": filters[0] if len(filters) == 1 else {"$and": filters}} if filters else {}
        )
        result = self.collection.query(
            query_embeddings=[vector],
            n_results=min(limit, self.collection.count()),
            include=["distances"],
            **kwargs,
        )
        return sorted(
            [
                (identifier, 1 - distance)
                for identifier, distance in zip(
                    result["ids"][0], result["distances"][0], strict=True
                )
            ],
            key=lambda pair: (-pair[1], pair[0]),
        )
