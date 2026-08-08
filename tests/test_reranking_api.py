"""Tests for reranking api behavior and regression boundaries."""

import json

import pytest
import requests

from fedresearch.llm.client import ProviderError
from fedresearch.retrieval.reranking import VoyageReranker
from fedresearch.settings import Settings


def mock_reranker(monkeypatch, handler):
    """Helper to SDK transport tests: configure a test key and replace external HTTP requests."""

    def request(_session, method, url, **kwargs):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        assert method.lower() == "post" and url == "https://ai.mongodb.com/v1/rerank"
        status, body = handler(json.loads(kwargs["data"]))
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode()
        response.headers["Content-Type"] = "application/json"
        return response

    monkeypatch.setenv("VOYAGE_API_KEY", "al-test-key")
    monkeypatch.setattr(requests.Session, "request", request)
    settings = Settings()
    settings.reranking.max_retries = 0
    return VoyageReranker(settings)


def test_atlas_reranking_preserves_indices_and_usage(monkeypatch):
    """Verify atlas reranking preserves indices and usage."""

    def handler(payload):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        assert payload["model"] == "rerank-3" and payload["truncation"] is False
        assert payload["query"] == "query" and payload["documents"] == ["first", "second"]
        return 200, {
            "data": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}],
            "usage": {"total_tokens": 15},
        }

    reranker = mock_reranker(monkeypatch, handler)
    ranked, usage = reranker.rerank("query", ["first", "second"])
    assert ranked == [(1, 0.9), (0, 0.1)]
    assert usage["input_tokens"] == 15 and usage["requests"] == 1


@pytest.mark.parametrize("indices", [[0, 0], [0, 4]])
def test_reranker_rejects_invalid_indices(monkeypatch, indices):
    """Verify reranker rejects duplicate or out-of-range document indices."""
    reranker = mock_reranker(
        monkeypatch,
        lambda _: (
            200,
            {
                "data": [
                    {"index": indices[0], "relevance_score": 0.9},
                    {"index": indices[1], "relevance_score": 0.1},
                ],
                "usage": {"total_tokens": 15},
            },
        ),
    )
    with pytest.raises(ProviderError, match="missing/duplicate"):
        reranker.rerank("query", ["first", "second"])


def test_reranker_empty_scope_never_calls_api(monkeypatch):
    """Verify reranker empty scope never calls api."""

    def unexpected_request(_payload):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        raise AssertionError("An empty candidate list must not call the API")

    reranker = mock_reranker(monkeypatch, unexpected_request)
    assert reranker.rerank("query", [])[1]["requests"] == 0


def test_reranker_error_does_not_expose_response(monkeypatch):
    """Verify reranker error does not expose response."""
    reranker = mock_reranker(monkeypatch, lambda _: (401, {"detail": "sensitive-marker"}))
    with pytest.raises(ProviderError) as error:
        reranker.rerank("query", ["first"])
    assert "401" in str(error.value) and "sensitive-marker" not in str(error.value)
