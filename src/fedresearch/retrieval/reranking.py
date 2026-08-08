"""Optional Atlas rerank-3 adapter that rescores passages without changing source identities."""

import math
import time

from voyageai.error import VoyageError

from fedresearch.llm.client import ProviderError, cost, voyage_client
from fedresearch.settings import Settings


class VoyageReranker:
    """Rescore the bounded candidate passages with Atlas rerank-3, preserving their source IDs."""

    def __init__(self, settings: Settings):
        """Helper to rerank: configure the Atlas-aware SDK, model, timeout and retries."""
        self.config = settings.reranking
        self.client = voyage_client(self.config.timeout_seconds, self.config.max_retries)

    def rerank(self, query: str, texts: list[str]) -> tuple[list[tuple[int, float]], dict]:
        """Rerank candidate text without truncation and return input indices, scores and usage."""
        started = time.perf_counter()
        if not texts:
            return [], {"enabled": True, "model": self.config.model, "requests": 0}
        try:
            result = self.client.rerank(
                query,
                texts,
                model=self.config.model,
                top_k=len(texts),
                truncation=False,
            )
        except VoyageError as error:
            raise ProviderError(
                f"Reranking request failed: {type(error).__name__} (status {error.http_status})"
            ) from None
        except IndexError:
            raise ProviderError(
                "Reranker returned missing/duplicate indices or invalid scores"
            ) from None
        if sorted(row.index for row in result.results) != list(range(len(texts))) or any(
            not math.isfinite(row.relevance_score) for row in result.results
        ):
            raise ProviderError("Reranker returned missing/duplicate indices or invalid scores")
        rows = sorted(result.results, key=lambda row: (-row.relevance_score, row.index))
        reranked = [(row.index, row.relevance_score) for row in rows]
        return reranked, {
            "enabled": True,
            "model": self.config.model,
            "truncation": False,
            "input_tokens": result.total_tokens,
            "requests": 1,
            "estimated_cost_usd": cost(result.total_tokens, "FEDRESEARCH_RERANKING_INPUT_PRICE"),
            "seconds": time.perf_counter() - started,
        }
