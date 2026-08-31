"""Preprocessing/index orchestration and compatibility checks for persisted artifacts."""

import json
import time
from pathlib import Path

from fedresearch.corpus.manifest import load_manifest, matching_papers, pdf_path, validate_corpus
from fedresearch.indexing.embeddings import EmbeddingCache
from fedresearch.indexing.lexical_index import build_lexical_index
from fedresearch.indexing.vector_index import VectorIndex
from fedresearch.llm.client import Embedder, VoyageEmbedder
from fedresearch.preprocessing.pdf_parser import parse_id_for, parse_pdf
from fedresearch.preprocessing.validation import require_reviewed, validate_document
from fedresearch.schemas import Paper, ParsedDocument
from fedresearch.settings import Preprocessing, Settings
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.util import atomic_json, digest


def source_identity(paper: Paper, config: Preprocessing) -> dict:
    """Helper to indexing and retrieval: fingerprint a paper, its parser configuration and metadata."""
    return {
        "paper_id": paper.paper_id,
        "sha256": paper.sha256,
        "parse_id": parse_id_for(paper, config),
        "paper_metadata_hash": digest(paper.model_dump(mode="json")),
    }


def preprocess(settings: Settings, paper_ids: list[str] | None = None) -> dict:
    """Parse existing PDFs into traceable blocks, sections and chunks; save diagnostics."""
    papers = matching_papers(load_manifest(settings.paths.manifest), paper_ids)
    successes, failures = [], []
    for paper in papers:
        try:
            document = parse_pdf(pdf_path(settings, paper), paper, settings.preprocessing)
            validate_document(document)
            path = settings.paths.processed / paper.paper_id / f"{document.parse_id}.json"
            atomic_json(path, document)
            # A paper's active parse pointer is changed only after successful validation.
            atomic_json(
                settings.paths.processed / paper.paper_id / "current.json",
                {"parse_id": document.parse_id},
            )
            successes.append(
                {"paper_id": paper.paper_id, "parse_id": document.parse_id, **document.diagnostics}
            )
        except Exception as error:
            # A previous parse must not become the apparent result of a failed reparse.
            (settings.paths.processed / paper.paper_id / "current.json").unlink(missing_ok=True)
            failures.append({"paper_id": paper.paper_id, "error": str(error)})
    result = {
        "processed": len(successes),
        "requested": len(papers),
        "documents": successes,
        "failures": failures,
        "config_hash": digest(settings.preprocessing.model_dump()),
    }
    atomic_json(settings.paths.processed / "diagnostics.json", result)
    return result


def load_processed(settings: Settings) -> list[ParsedDocument]:
    """Load active parses after checking PDF hashes, parser settings and source provenance."""
    failures = validate_corpus(settings)["failures"]
    if failures:
        raise ValueError(f"Corpus integrity check failed: {failures}")
    documents = []
    for paper in load_manifest(settings.paths.manifest):
        folder = settings.paths.processed / paper.paper_id
        pointer = folder / "current.json"
        if not pointer.exists():
            raise ValueError(
                f"{paper.paper_id}: missing processed document; preprocess the full corpus first"
            )
        parse_id = json.loads(pointer.read_text())["parse_id"]
        doc = ParsedDocument.model_validate_json((folder / f"{parse_id}.json").read_text())
        if doc.paper.sha256 != paper.sha256 or doc.paper.document_version != paper.document_version:
            raise ValueError(f"{paper.paper_id}: stale PDF version; preprocess again")
        if doc.parse_id != parse_id_for(paper, settings.preprocessing):
            raise ValueError(f"{paper.paper_id}: stale parser/configuration; preprocess again")
        validate_document(doc)
        require_reviewed(doc)
        doc.paper = paper
        documents.append(doc)
    return documents


def canonical_store(settings: Settings) -> MetadataStore:
    """Build an in-memory source store for validating benchmark labels without a vector index."""
    store = MetadataStore(Path(":memory:"), create=True)
    try:
        for doc in load_processed(settings):
            store.add_document(doc)
    except Exception:
        store.close()
        raise
    return store


def build_index(settings: Settings, provider: Embedder | None = None) -> dict:
    """Build BM25, cache chunk embeddings and activate Chroma with SQLite source lookup."""
    started = time.perf_counter()
    documents = load_processed(settings)
    chunks = sorted([chunk for doc in documents for chunk in doc.chunks], key=lambda c: c.chunk_id)
    if not chunks:
        raise ValueError("Cannot index an empty corpus")
    provider = provider or VoyageEmbedder(settings)
    identity = {
        "schema_version": 1,
        "documents": [source_identity(d.paper, settings.preprocessing) for d in documents],
        "chunk_fingerprint": digest([c.model_dump(mode="json") for c in chunks]),
        "embedding": provider.identity,
    }
    index_id = digest(identity)[:24]
    folder = settings.paths.indexes / index_id
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "index.json").is_file():
        saved = json.loads((folder / "index.json").read_text())
        vectors = VectorIndex(folder / "chroma")
        with MetadataStore(folder / "metadata.sqlite") as store:
            if (
                saved["chunks"] != vectors.collection.count()
                or saved["chunks"] != store.statistics()["chunks"]
            ):
                raise ValueError(
                    "Existing completed index is inconsistent; inspect it before rebuilding"
                )
        lexical = build_lexical_index(
            folder / "bm25.sqlite", index_id, identity["chunk_fingerprint"], chunks
        )
        atomic_json(settings.paths.indexes / "CURRENT.json", {"index_id": index_id})
        return {
            **saved,
            "reused": True,
            "lexical": lexical,
            "current_build_usage": {},
            "current_build_seconds": time.perf_counter() - started,
        }
    lexical = build_lexical_index(
        folder / "bm25.sqlite", index_id, identity["chunk_fingerprint"], chunks
    )
    cache = EmbeddingCache(settings.paths.indexes / "embedding_cache.sqlite")
    try:
        vectors, hits = cache.embed_chunks(chunks, provider, settings.embedding.batch_size)
    finally:
        cache.close()
    metadata = folder / "metadata.sqlite"
    # Incomplete builds are never selected by CURRENT. A rebuild recreates metadata.
    metadata.unlink(missing_ok=True)
    with MetadataStore(metadata, create=True) as store:
        for document in documents:
            store.add_document(document)
    index = VectorIndex(folder / "chroma", create=True)
    index.add(chunks, vectors)
    if index.collection.count() != len(chunks):
        raise ValueError("Vector index count mismatch")
    result = {
        "index_id": index_id,
        **identity,
        "papers": len(documents),
        "chunks": len(chunks),
        "cache_hits": hits,
        "lexical": lexical,
        "usage": provider.usage,
        "seconds": time.perf_counter() - started,
    }
    atomic_json(folder / "index.json", result)
    atomic_json(settings.paths.indexes / "CURRENT.json", {"index_id": index_id})
    return result


def current_index(settings: Settings) -> tuple[Path, dict]:
    """Helper to RetrievalService: resolve the active completed index and check its manifest identity."""
    pointer = settings.paths.indexes / "CURRENT.json"
    if not pointer.exists():
        raise ValueError("No active index. Run fedresearch index first")
    identifier = json.loads(pointer.read_text())["index_id"]
    if len(identifier) != 24 or any(c not in "0123456789abcdef" for c in identifier):
        raise ValueError("Invalid active index identity")
    folder = settings.paths.indexes / identifier
    manifest = json.loads((folder / "index.json").read_text())
    if manifest["index_id"] != identifier:
        raise ValueError("Index identity mismatch")
    return folder, manifest
