"""Tests for src/generation/openrouter.py.

No live network - requests.post is monkeypatched with a fake response
object throughout. Uses a fake key ("test-key-not-real"), never a real
secret. The one test requiring a real live OpenRouter call is marked
`generation_api` and is exercised separately by
scripts/smoke_generation.py, not by this portable suite.
"""

import pytest

from src.generation.openrouter import OpenRouterProvider, OPENROUTER_ENDPOINT, API_KEY_ENV_VAR
from src.generation.provider import GenerationError, GenerationRequest

FAKE_KEY = "test-key-not-real"


class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_data=None, text="not json"):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no JSON body")
        return self._json_data


def _success_body(model="anthropic/claude-3-haiku", content="Answer. [doc.htm::chunk0]"):
    return {
        "id": "gen-123",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV_VAR, FAKE_KEY)


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError, match=API_KEY_ENV_VAR):
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))


def test_empty_model_rejected():
    with pytest.raises(ValueError):
        OpenRouterProvider(model="")


def test_request_construction(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeHTTPResponse(200, _success_body())

    monkeypatch.setattr("src.generation.openrouter.requests.post", fake_post)

    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    provider.generate(GenerationRequest(system_prompt="sys", user_prompt="usr", temperature=0.0))

    assert captured["url"] == OPENROUTER_ENDPOINT
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["json"]["model"] == "anthropic/claude-3-haiku"
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert captured["json"]["temperature"] == 0.0
    assert captured["json"]["stream"] is False
    assert captured["timeout"] == 60


def test_response_text_extraction(monkeypatch):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(200, _success_body(content="The answer. [x.htm::chunk1]")),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    result = provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))
    assert result.text == "The answer. [x.htm::chunk1]"


def test_response_model_and_usage_recorded(monkeypatch):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(200, _success_body(model="anthropic/claude-3-haiku-20240307")),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    result = provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))
    assert result.requested_model == "anthropic/claude-3-haiku"
    assert result.response_model == "anthropic/claude-3-haiku-20240307"
    assert result.prompt_tokens == 50
    assert result.completion_tokens == 10
    assert result.total_tokens == 60
    assert result.provider_name == "openrouter"


@pytest.mark.parametrize("status", [401, 402, 403, 404, 429, 500, 502, 503, 524, 529])
def test_error_status_codes_raise_generation_error(monkeypatch, status):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(status, json_data=None),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError):
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))


def test_malformed_json_response_raises(monkeypatch):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(200, json_data=None),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError, match="JSON"):
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))


def test_missing_choices_field_raises(monkeypatch):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(200, json_data={"id": "x", "model": "m"}),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError, match="choices"):
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))


def test_network_exception_translated(monkeypatch):
    import requests

    def raise_conn_error(*a, **k):
        raise requests.ConnectionError("boom")

    monkeypatch.setattr("src.generation.openrouter.requests.post", raise_conn_error)
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError):
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))


def test_api_key_never_appears_in_repr():
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    assert FAKE_KEY not in repr(provider)
    assert "Authorization" not in repr(provider)


def test_api_key_never_appears_in_error_message(monkeypatch):
    monkeypatch.setattr(
        "src.generation.openrouter.requests.post",
        lambda *a, **k: _FakeHTTPResponse(401, json_data=None),
    )
    provider = OpenRouterProvider(model="anthropic/claude-3-haiku")
    with pytest.raises(GenerationError) as exc_info:
        provider.generate(GenerationRequest(system_prompt="s", user_prompt="u"))
    assert FAKE_KEY not in str(exc_info.value)
