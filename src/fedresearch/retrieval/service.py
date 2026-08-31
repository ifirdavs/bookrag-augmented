"""Shared filtered retrieval pipeline, optional reranking and final evidence budgeting."""

import math
import time

from fedresearch.corpus.manifest import load_manifest, matching_papers
from fedresearch.indexing.lexical_index import LexicalIndex, lexical_identity
from fedresearch.indexing.pipeline import current_index, source_identity
from fedresearch.indexing.vector_index import VectorIndex
from fedresearch.llm.client import Embedder, VoyageEmbedder
from fedresearch.retrieval.evidence import deduplicate_candidates, pack_evidence
from fedresearch.retrieval.fusion import reciprocal_rank_fusion
from fedresearch.retrieval.reranking import VoyageReranker
from fedresearch.settings import Settings
from fedresearch.storage.metadata_store import MetadataStore
from fedresearch.tokenization import load_tokenizer


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
        self.folder = folder
        self.lexical = None
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
        if self.lexical is not None:
            self.lexical.close()

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
        mode: str | None = None,
        top_k: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        method: str | None = None,
        *,
        candidate_pool: list[tuple[str, float]] | None = None,
        candidate_rankings: dict | None = None,
    ):
        """Search dense/hybrid candidates or replay a pool, then optionally rerank and pack evidence."""
        started = time.perf_counter()
        config = self.settings.retrieval
        mode = config.mode if mode is None else mode
        if mode not in {"dense", "hybrid"}:
            raise ValueError("Only dense and hybrid retrieval are implemented")
        top_k = config.top_k if top_k is None else top_k
        if not 1 <= top_k <= min(20, config.candidate_limit):
            raise ValueError("top_k must be within the configured candidate limit and 1–20")
        preprocessing = self.settings.preprocessing
        tokenizer = load_tokenizer(preprocessing.tokenizer, preprocessing.tokenizer_revision)
        if (
            not query.strip()
            or len(tokenizer.encode(query, add_special_tokens=False)) > config.max_query_tokens
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
        rankings = candidate_rankings or {}
        if candidate_pool is not None:
            ranked = list(candidate_pool)
            if (
                len(ranked) > config.candidate_limit
                or len({identifier for identifier, _ in ranked}) != len(ranked)
                or any(not math.isfinite(score) for _, score in ranked)
                or any(
                    self.store.chunk(identifier).paper_id not in allowed for identifier, _ in ranked
                )
                or (chunk_ids is not None and any(i not in chunk_ids for i, _ in ranked))
            ):
                raise ValueError(
                    "Saved candidates violate the candidate limit, scores or source filters"
                )
        elif allowed and chunk_ids != []:
            if mode == "hybrid":
                self.lexical = self.lexical or LexicalIndex(
                    self.folder / "bm25.sqlite",
                    self.manifest["index_id"],
                    self.manifest["chunk_fingerprint"],
                    self.manifest["chunks"],
                )
            vector = self.provider.embed([query], input_type="query")[0]
            ranked = self.vectors.query(vector, config.candidate_limit, allowed, chunk_ids)
            rankings = {"dense": ranked}
            if mode == "hybrid":
                rankings["bm25"] = self.lexical.query(
                    query, config.candidate_limit, allowed, chunk_ids
                )
                ranked = reciprocal_rank_fusion(
                    list(rankings.values()), config.candidate_limit, config.rrf_constant
                )
        candidates = [{"chunk_id": identifier, "score": score} for identifier, score in ranked]
        ranked, duplicates = deduplicate_candidates(ranked, self.store)
        deduplicated = [{"chunk_id": identifier, "score": score} for identifier, score in ranked]
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
        evidence, packing = pack_evidence(ranked, self.store, top_k, config.evidence_tokens, mode)
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
            "deduplicated_candidates": deduplicated,
            "rankings": {
                name: [
                    {"chunk_id": identifier, "rank": rank, "score": score}
                    for rank, (identifier, score) in enumerate(rows, start=1)
                ]
                for name, rows in rankings.items()
            },
            "fusion": {"constant": config.rrf_constant, "candidate_limit": config.candidate_limit}
            if mode == "hybrid"
            else None,
            "lexical_index": lexical_identity(
                self.manifest["index_id"], self.manifest["chunk_fingerprint"]
            )
            if mode == "hybrid"
            else None,
            "candidate_source": "saved_pool" if candidate_pool is not None else f"{mode}_search",
            "reranking": reranking,
            "ranking_score": "reranker_relevance"
            if reranking["enabled"]
            else ("rrf" if mode == "hybrid" else "cosine_similarity"),
            "embedding_usage": usage,
            "seconds": time.perf_counter() - started,
            **packing,
        }
        return evidence
