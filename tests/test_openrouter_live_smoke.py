"""generation_api-marked: a real OpenRouter chat-completion call.

Requires OPENROUTER_API_KEY and an explicit GENERATION_MODEL in the
process environment - skips cleanly if either is absent (never invents a
model choice), fails if both are present but the call is broken. Never
downloads anything. Never prints/logs the API key. Not part of the
routine portable/full test expectations - always a real network call.
"""

import os

import pytest

from src.generation.openrouter import OpenRouterProvider, API_KEY_ENV_VAR
from src.generation.provider import GenerationRequest


@pytest.mark.generation_api
def test_real_openrouter_call_succeeds():
    api_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
    model = os.environ.get("GENERATION_MODEL", "").strip()

    if not api_key:
        pytest.skip(f"{API_KEY_ENV_VAR} not set in environment")
    if not model:
        pytest.skip("GENERATION_MODEL not set in environment")

    provider = OpenRouterProvider(model=model)
    response = provider.generate(GenerationRequest(
        system_prompt="Answer in exactly one short sentence.",
        user_prompt="What is 2 + 2?",
        temperature=0.0,
    ))

    assert response.text
    assert response.requested_model == model
    assert response.latency_ms > 0
