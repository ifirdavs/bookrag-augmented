"""Tests for generation api behavior and regression boundaries."""

import json

import httpx
import pytest
from anthropic import Anthropic

import fedresearch.llm.client as provider_module
from fedresearch.llm.client import ClaudeGenerator, ProviderError
from fedresearch.settings import Settings


def mock_generator(monkeypatch, handler):
    """Helper to SDK transport tests: configure a test key and replace external HTTP requests."""
    client = Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(provider_module, "Anthropic", lambda **_: client)
    return ClaudeGenerator(Settings()), client


def response(text, stop_reason="end_turn"):
    """Helper to Claude transport tests: construct a structured Messages API response."""
    return httpx.Response(
        200,
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
    )


def test_claude_structured_answer_and_usage(monkeypatch):
    """Verify claude structured answer and usage."""

    def handler(request):
        """Helper to SDK transport tests: inspect or reject the request and return a controlled response."""
        payload = json.loads(request.content)
        assert request.url.path == "/v1/messages"
        assert payload["model"] == "claude-haiku-5-5"
        assert payload["output_config"]["format"]["type"] == "json_schema"
        assert payload["system"] == "Use source evidence."
        assert "temperature" not in payload
        return response(
            json.dumps(
                {
                    "sufficiency": "insufficient",
                    "claims": [],
                    "limitations": "No evidence.",
                }
            )
        )

    generator, client = mock_generator(monkeypatch, handler)
    try:
        assert (
            generator.generate("Use source evidence.", "No evidence.").sufficiency == "insufficient"
        )
        assert generator.usage["input_tokens"] == 5
        assert generator.usage["output_tokens"] == 7
    finally:
        client.close()


@pytest.mark.parametrize(
    "stop_reason,text",
    [
        ("max_tokens", '{"sufficiency":'),
        ("refusal", "I cannot answer this request."),
        ("max_tokens", '{"sufficiency":"insufficient","claims":[],"limitations":"No evidence."}'),
    ],
)
def test_claude_rejects_refusal_or_incomplete_answer(monkeypatch, stop_reason, text):
    """Verify claude rejects refusal or incomplete answer."""
    generator, client = mock_generator(monkeypatch, lambda _: response(text, stop_reason))
    try:
        with pytest.raises(ProviderError, match="structured answer"):
            generator.generate("Use evidence.", "Question")
    finally:
        client.close()


def test_claude_error_does_not_expose_response_body(monkeypatch):
    """Verify claude error does not expose response body."""
    generator, client = mock_generator(
        monkeypatch,
        lambda _: httpx.Response(
            401,
            json={
                "type": "error",
                "error": {"type": "authentication_error", "message": "sensitive-marker"},
            },
        ),
    )
    try:
        with pytest.raises(ProviderError) as error:
            generator.generate("Use evidence.", "Question")
        assert "401" in str(error.value) and "sensitive-marker" not in str(error.value)
    finally:
        client.close()


def test_claude_requires_its_own_key(monkeypatch):
    """Verify claude requires its own key."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        ClaudeGenerator(Settings())
