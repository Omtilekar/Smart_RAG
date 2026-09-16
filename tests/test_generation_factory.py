"""Tests for src/generation/factory.py (Task 4.6)."""

from dataclasses import dataclass

import pytest

from src.generation.factory import get_generation_provider
from src.generation.openrouter import OpenRouterProvider
from src.generation.ollama_provider import OllamaProvider
from src.generation.provider import GenerationError


@dataclass
class _FakeSettings:
    generation_provider: str | None
    generation_model: str | None


def test_resolves_openrouter():
    provider = get_generation_provider(_FakeSettings("openrouter", "openai/gpt-oss-20b"))
    assert isinstance(provider, OpenRouterProvider)
    assert repr(provider) == "OpenRouterProvider(model='openai/gpt-oss-20b')"


def test_resolves_ollama():
    provider = get_generation_provider(_FakeSettings("ollama", "gpt-oss:20b"))
    assert isinstance(provider, OllamaProvider)
    assert repr(provider) == "OllamaProvider(model='gpt-oss:20b')"


def test_is_case_insensitive_on_provider_name():
    provider = get_generation_provider(_FakeSettings("OpenRouter", "openai/gpt-oss-20b"))
    assert isinstance(provider, OpenRouterProvider)


def test_raises_when_provider_unset():
    with pytest.raises(GenerationError, match="GENERATION_PROVIDER"):
        get_generation_provider(_FakeSettings(None, "openai/gpt-oss-20b"))


def test_raises_when_model_unset():
    with pytest.raises(GenerationError, match="GENERATION_MODEL"):
        get_generation_provider(_FakeSettings("openrouter", None))


def test_raises_on_unknown_provider():
    with pytest.raises(GenerationError, match="unknown GENERATION_PROVIDER"):
        get_generation_provider(_FakeSettings("anthropic-direct", "claude-3"))


def test_never_falls_back_to_a_default_model():
    # Regression guard: an empty-string model must be treated the same as
    # None - never silently coerced to a hardcoded default.
    with pytest.raises(GenerationError, match="GENERATION_MODEL"):
        get_generation_provider(_FakeSettings("openrouter", "   "))
