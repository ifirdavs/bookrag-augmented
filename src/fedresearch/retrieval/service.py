"""Shared filtered retrieval pipeline, optional reranking and final evidence budgeting."""

import time

import tiktoken

from fedresearch.corpus.manifest import load_manifest, matching_papers
from fedresearch.indexing.pipeline import current_index, source_identity
from fedresearch.indexing.vector_index import VectorIndex
from fedresearch.llm.client import Embedder, VoyageEmbedder
from fedresearch.retrieval.evidence import deduplicate_candidates, pack_evidence
from fedresearch.retrieval.reranking import VoyageReranker
from fedresearch.settings import Settings
from fedresearch.storage.metadata_store import MetadataStore


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        provider: Embedder | None = None,
        reranker: VoyageReranker | None = None,
    ):
        """Helper to retrieve: open a compatible index and configure its embedding/reranking providers."""
        self.settings = settings
        folder, self.manifest = current_index(settings)
        provider = provider or VoyageEmbedder(settings)
        if provider.identity != self.manifest["embedding"]:
            raise ValueError(
                "Embedding configuration differs from the index. Restore its model/provider/dimensions or rebuild."
            )
        source = load_manifest(settings.paths.manifest)
        expected = [source_identity(p, settings.preprocessing) for p in source]
        if expected != self.manifest["documents"]:
            raise ValueError(
                "Corpus or parser configuration differs from the index. Preprocess and rebuild."
            )
        self.store = MetadataStore(folder / "metadata.sqlite")
        self.vectors = VectorIndex(folder / "chroma")
        if self.vectors.collection.count() != self.manifest["chunks"]:
            self.store.close()
            raise ValueError("Dense index is incomplete")
        self.provider = provider
        self.reranker = reranker
        self.last_trace = {}

    def close(self):
        """Helper to retrieval cleanup: close the source metadata store."""
        self.store.close()

    def __enter__(self):
        """Helper to retrieval context management: return the open service."""
        return self

    def __exit__(self, *_):
        """Helper to retrieval context management: close the service after use."""
        self.close()

    def retrieve(
        self,
        query: str,
        paper_ids: list[str] | None = None,
        section_hint: str | None = None,
        mode: str = "dense",
        top_k: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        method: str | None = None,
    ):
        """Search filtered dense vectors, optionally rerank and pack source evidence within shared budgets."""
        started = time.perf_counter()
        if mode != "dense":
            raise ValueError("Only dense retrieval is implemented in Phase 2")
        config = self.settings.retrieval
        top_k = config.top_k if top_k is None else top_k
        if not 1 <= top_k <= min(20, config.candidate_limit):
            raise ValueError("top_k must be within the configured candidate limit and 1–20")
        encoding = tiktoken.get_encoding(self.settings.preprocessing.tokenizer)
        if (
            not query.strip()
            or len(encoding.encode(query, disallowed_special=())) > config.max_query_tokens
        ):
            raise ValueError("Query is empty or exceeds the configured token budget")
        papers = matching_papers(self.store.papers(), paper_ids)
        if year_from and year_to and year_from > year_to:
            raise ValueError("year_from must not exceed year_to")
        allowed = [
            p.paper_id
            for p in papers
            if (not year_from or p.year >= year_from)
            and (not year_to or p.year <= year_to)
            and (not method or method.casefold() in {m.casefold() for m in p.methods})
        ]
        chunk_ids = None
        if section_hint:
            chunk_ids = [
                c.chunk_id
                for c in self.store.chunks()
                if c.paper_id in allowed
                and any(
                    section_hint.casefold() in " / ".join(self.store.section(s).path).casefold()
                    for s in c.section_ids
                )
            ]
        before = dict(self.provider.usage)
        ranked = []
        if allowed and chunk_ids != []:
            vector = self.provider.embed([query], input_type="query")[0]
            ranked = self.vectors.query(vector, config.candidate_limit, allowed, chunk_ids)
        candidates = [{"chunk_id": identifier, "score": score} for identifier, score in ranked]
        ranked, duplicates = deduplicate_candidates(ranked, self.store)
        reranking = {"enabled": False}
        if self.settings.reranking.enabled:
            self.reranker = self.reranker or VoyageReranker(self.settings)
            rows, reranking = self.reranker.rerank(
                query, [self.store.chunk(identifier).text for identifier, _ in ranked]
            )
            reranking["results"] = [
                {
                    "chunk_id": ranked[index][0],
                    "original_rank": index + 1,
                    "original_score": ranked[index][1],
                    "rank": rank + 1,
                    "score": score,
                }
                for rank, (index, score) in enumerate(rows)
            ]
            ranked = [(ranked[index][0], score) for index, score in rows]
        evidence, packing = pack_evidence(ranked, self.store, top_k, config.evidence_tokens)
        packing["skipped"] = duplicates + packing["skipped"]
        usage = {
            key: self.provider.usage.get(key, 0) - before.get(key, 0)
            for key in ("input_tokens", "requests")
        }
        new_cost = self.provider.usage.get("estimated_cost_usd")
        old_cost = before.get("estimated_cost_usd")
        usage["estimated_cost_usd"] = new_cost - (old_cost or 0) if new_cost is not None else None
        self.last_trace = {
            "index_id": self.manifest["index_id"],
            "mode": mode,
            "routing": "disabled",
            "filters": {
                "paper_ids": paper_ids,
                "section_hint": section_hint,
                "year_from": year_from,
                "year_to": year_to,
                "method": method,
            },
            "candidates": candidates,
            "reranking": reranking,
            "ranking_score": "reranker_relevance" if reranking["enabled"] else "cosine_similarity",
            "embedding_usage": usage,
            "seconds": time.perf_counter() - started,
            **packing,
        }
        return evidence
