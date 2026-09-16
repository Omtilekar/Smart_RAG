"""Tests for src/generation/ollama_provider.py (Task 4.6).

No live network for the portable tests - requests.post is monkeypatched
with a fake response object, matching tests/test_openrouter_provider.py's
convention. The one test requiring a real local Ollama call is marked
`ollama` (same marker/skip convention as tests/test_llm_judge.py's real
integration test) - free/local, never a paid API call.
"""

import pytest
import requests

from src.generation.ollama_provider import OllamaProvider, CHAT_ENDPOINT
from src.generation.provider import GenerationError, GenerationRequest


class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("no JSON body")
        return self._json_data


def _success_body(model="gpt-oss:20b", content="Answer. [doc.htm::chunk0]",
                   prompt_eval_count=94, eval_count=91):
    return {
        "model": model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
    }


def _request():
    return GenerationRequest(system_prompt="sys", user_prompt="user", temperature=0.0)


# ------------------------------------------------------- construction

def test_rejects_empty_model():
    with pytest.raises(ValueError):
        OllamaProvider(model="")


def test_repr_shows_model_only():
    provider = OllamaProvider(model="gpt-oss:20b")
    assert repr(provider) == "OllamaProvider(model='gpt-oss:20b')"


# ------------------------------------------------------- generate() success

def test_generate_success_returns_provider_response(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeHTTPResponse(200, _success_body())

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OllamaProvider(model="gpt-oss:20b")
    result = provider.generate(_request())

    assert captured["url"] == CHAT_ENDPOINT
    assert captured["json"]["model"] == "gpt-oss:20b"
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]

    assert result.text == "Answer. [doc.htm::chunk0]"
    assert result.requested_model == "gpt-oss:20b"
    assert result.response_model == "gpt-oss:20b"
    assert result.provider_name == "ollama"
    assert result.response_provider is None
    assert result.prompt_tokens == 94
    assert result.completion_tokens == 91
    assert result.total_tokens == 185
    assert result.temperature_requested == 0.0
    assert result.latency_ms >= 0


def test_generate_sends_temperature_in_options(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return _FakeHTTPResponse(200, _success_body())

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OllamaProvider(model="gpt-oss:20b")
    provider.generate(GenerationRequest(system_prompt="s", user_prompt="u", temperature=0.7))
    assert captured["json"]["options"]["temperature"] == 0.7


def test_generate_handles_missing_token_counts(monkeypatch):
    body = _success_body()
    del body["prompt_eval_count"]
    del body["eval_count"]

    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeHTTPResponse(200, body))
    provider = OllamaProvider(model="gpt-oss:20b")
    result = provider.generate(_request())
    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None


# ------------------------------------------------------- error paths

def test_generate_raises_on_connection_error(monkeypatch):
    def fake_post(*a, **k):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", fake_post)
    provider = OllamaProvider(model="gpt-oss:20b")
    with pytest.raises(GenerationError, match="is `ollama serve` running"):
        provider.generate(_request())


def test_generate_raises_on_non_200_status(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeHTTPResponse(500, {}))
    provider = OllamaProvider(model="gpt-oss:20b")
    with pytest.raises(GenerationError, match="HTTP 500"):
        provider.generate(_request())


def test_generate_raises_on_invalid_json(monkeypatch):
    class _BadJSON(_FakeHTTPResponse):
        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(requests, "post", lambda *a, **k: _BadJSON(200))
    provider = OllamaProvider(model="gpt-oss:20b")
    with pytest.raises(GenerationError, match="not valid JSON"):
        provider.generate(_request())


def test_generate_raises_on_missing_message_content(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeHTTPResponse(200, {"model": "gpt-oss:20b"}))
    provider = OllamaProvider(model="gpt-oss:20b")
    with pytest.raises(GenerationError, match="missing message.content"):
        provider.generate(_request())


def test_no_api_key_required(monkeypatch):
    # Unlike OpenRouterProvider, OllamaProvider must never look for or
    # require an API key - it is the local/offline provider.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeHTTPResponse(200, _success_body()))
    provider = OllamaProvider(model="gpt-oss:20b")
    result = provider.generate(_request())
    assert result.text


# --------------------------------------------------- real local Ollama (free)

@pytest.mark.ollama
class TestRealOllamaGeneration:
    def test_real_local_generation_call(self):
        import requests as real_requests

        try:
            real_requests.get("http://localhost:11434/api/version", timeout=5)
        except real_requests.exceptions.RequestException:
            pytest.skip("Ollama server not reachable at localhost:11434")

        provider = OllamaProvider(model="gpt-oss:20b")
        request = GenerationRequest(
            system_prompt="Answer in one short sentence.", user_prompt="What is 2+2?", temperature=0.0,
        )
        try:
            result = provider.generate(request)
        except GenerationError as e:
            pytest.skip(f"gpt-oss:20b not available: {e}")

        assert result.text.strip()
        assert result.provider_name == "ollama"
        assert result.requested_model == "gpt-oss:20b"
        assert isinstance(result.prompt_tokens, int) and result.prompt_tokens > 0
        assert isinstance(result.completion_tokens, int) and result.completion_tokens > 0
        assert result.latency_ms > 0
