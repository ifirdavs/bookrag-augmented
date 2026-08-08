"""Official Claude and Voyage SDK adapters with vector checks, usage and sanitized errors."""

import math
import os
from typing import Literal, Protocol

import voyageai
from anthropic import Anthropic
from anthropic import APIError as AnthropicAPIError
from voyageai.error import VoyageError

from fedresearch.schemas import GeneratedAnswer
from fedresearch.settings import Settings


class ProviderError(RuntimeError):
    pass


class Embedder(Protocol):
    identity: dict
    usage: dict

    def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Embed document passages or queries using the declared provider identity."""
        ...


class Generator(Protocol):
    usage: dict

    def generate(self, instructions: str, input_text: str) -> GeneratedAnswer:
        """Generate a structured answer from the supplied instructions and evidence payload."""
        ...


def validate_vectors(vectors: list[list[float]], count: int, dimensions: int):
    """Helper to vector storage and retrieval: check count, dimensions and finite nonzero vectors."""
    if len(vectors) != count:
        raise ProviderError("Embedding provider returned the wrong number of vectors")
    if any(
        len(v) != dimensions or not all(math.isfinite(x) for x in v) or sum(x * x for x in v) <= 0
        for v in vectors
    ):
        raise ProviderError(
            "Embedding provider returned invalid dimensions, nonfinite values, or a zero vector"
        )


def cost(tokens: int, variable: str) -> float | None:
    """Helper to provider usage: estimate nominal USD cost from an optional per-million-token price."""
    price = os.getenv(variable)
    if not price:
        return None
    value = float(price)
    if value < 0 or not math.isfinite(value):
        raise ValueError(f"{variable} must be a finite nonnegative USD price per million tokens")
    return tokens * value / 1_000_000


def voyage_client(timeout: float, retries: int) -> voyageai.Client:
    """Helper to Voyage providers: create the SDK client, which routes Atlas keys automatically."""
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        raise ProviderError("Set VOYAGE_API_KEY in .env for Voyage embeddings and reranking")
    return voyageai.Client(api_key=key, timeout=timeout, max_retries=retries)


class VoyageEmbedder:
    """Embed passages and questions with Voyage's retrieval-specific input types."""

    def __init__(self, settings: Settings):
        """Helper to embed: configure the SDK client, vector identity and cumulative usage."""
        self.config = settings.embedding
        self.client = voyage_client(self.config.timeout_seconds, self.config.max_retries)
        self.identity = {
            "provider": "voyageai",
            "model": self.config.model,
            "dimensions": self.config.dimensions,
            "document_input_type": "document",
            "output_dtype": "float",
            "truncation": False,
        }
        self.usage = {"input_tokens": 0, "requests": 0}

    def embed(
        self, texts: list[str], *, input_type: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Embed passages or questions without truncation, validate vectors and record API usage."""
        if not texts:
            return []
        if input_type not in {"document", "query"} or any(not text.strip() for text in texts):
            raise ValueError("Embeddings require nonempty text and a document/query input type")
        try:
            result = self.client.embed(
                texts,
                model=self.config.model,
                input_type=input_type,
                output_dimension=self.config.dimensions,
                output_dtype="float",
                truncation=False,
            )
        except VoyageError as error:
            raise ProviderError(
                f"Voyage request failed: {type(error).__name__} (status {error.http_status})"
            ) from None
        validate_vectors(result.embeddings, len(texts), self.config.dimensions)
        self.usage["input_tokens"] += result.total_tokens
        self.usage["requests"] += 1
        self.usage["estimated_cost_usd"] = cost(
            self.usage["input_tokens"], "FEDRESEARCH_EMBEDDING_INPUT_PRICE"
        )
        return result.embeddings


class ClaudeGenerator:
    """Generate structured, cited claims through the Claude Messages API."""

    def __init__(self, settings: Settings):
        """Helper to generate: configure the Claude SDK using the project API key and request limits."""
        self.config = settings.generation
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("Set ANTHROPIC_API_KEY in .env for Claude generation")
        self.client = Anthropic(
            api_key=key, timeout=self.config.timeout_seconds, max_retries=self.config.max_retries
        )
        self.usage = {}

    def generate(self, instructions: str, input_text: str) -> GeneratedAnswer:
        """Generate and parse cited claims, rejecting refusals or incomplete structured output."""
        try:
            result = self.client.messages.parse(
                model=self.config.model,
                max_tokens=self.config.max_output_tokens,
                system=instructions,
                messages=[{"role": "user", "content": input_text}],
                output_format=GeneratedAnswer,
            )
        except AnthropicAPIError as error:
            raise ProviderError(
                f"Claude request failed: {type(error).__name__} (status {getattr(error, 'status_code', None)})"
            ) from None
        except ValueError:
            raise ProviderError(
                "Claude returned an invalid or incomplete structured answer"
            ) from None
        if result.stop_reason != "end_turn" or result.parsed_output is None:
            raise ProviderError("Claude refused or returned an incomplete structured answer")
        input_tokens = result.usage.input_tokens
        output_tokens = result.usage.output_tokens
        input_cost = cost(input_tokens, "FEDRESEARCH_GENERATION_INPUT_PRICE")
        output_cost = cost(output_tokens, "FEDRESEARCH_GENERATION_OUTPUT_PRICE")
        self.usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": result.model,
            "response_id": result.id,
            "estimated_cost_usd": input_cost + output_cost
            if input_cost is not None and output_cost is not None
            else None,
        }
        return result.parsed_output
