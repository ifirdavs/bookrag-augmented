"""Tests for embeddings api behavior and regression boundaries."""

import json

import pytest
import requests

from fedresearch.llm.client import ProviderError, VoyageEmbedder
from fedresearch.settings import Settings


def mock_embedder(monkeypatch, handler):
    """Helper to SDK transport tests: configure a test key and replace external HTTP requests."""

    def request(_session, method, url, **kwargs):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        assert method.lower() == "post" and url == "https://api.voyageai.com/v1/embeddings"
        status, body = handler(json.loads(kwargs["data"]))
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode()
        response.headers["Content-Type"] = "application/json"
        return response

    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setattr(requests.Session, "request", request)
    settings = Settings()
    settings.embedding.dimensions = 256
    settings.embedding.max_retries = 0
    return VoyageEmbedder(settings)


def test_voyage_document_query_transport_and_usage(monkeypatch):
    """Verify voyage document query transport and usage."""
    roles = []

    def handler(payload):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        roles.append(payload["input_type"])
        assert payload["model"] == "voyage-4-large"
        assert payload["output_dimension"] == 256
        assert payload["output_dtype"] == "float" and payload["truncation"] is False
        return 200, {
            "data": [
                {"index": i, "embedding": [float(i + 1)] + [0.0] * 255}
                for i, _ in enumerate(payload["input"])
            ],
            "usage": {"total_tokens": 7},
        }

    embedder = mock_embedder(monkeypatch, handler)
    assert [vector[0] for vector in embedder.embed(["first", "second"])] == [1.0, 2.0]
    assert len(embedder.embed(["question"], input_type="query")[0]) == 256
    assert roles == ["document", "query"]
    assert embedder.usage["input_tokens"] == 14 and embedder.usage["requests"] == 2


def test_voyage_error_does_not_expose_response_body(monkeypatch):
    """Verify voyage error does not expose response body."""
    embedder = mock_embedder(monkeypatch, lambda _: (401, {"detail": "sensitive-marker"}))
    with pytest.raises(ProviderError) as error:
        embedder.embed(["text"])
    assert "401" in str(error.value) and "sensitive-marker" not in str(error.value)


@pytest.mark.parametrize("vectors", [[], [[0.0] * 256], [[1.0] * 255]])
def test_voyage_rejects_invalid_vectors(monkeypatch, vectors):
    """Verify voyage rejects invalid vectors."""
    embedder = mock_embedder(
        monkeypatch,
        lambda _: (
            200,
            {
                "data": [{"index": i, "embedding": vector} for i, vector in enumerate(vectors)],
                "usage": {"total_tokens": 1},
            },
        ),
    )
    with pytest.raises(ProviderError, match="Embedding provider returned"):
        embedder.embed(["text"])


def test_voyage_requires_separate_key(monkeypatch):
    """Verify voyage requires separate key."""
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    with pytest.raises(ProviderError, match="VOYAGE_API_KEY"):
        VoyageEmbedder(Settings())
