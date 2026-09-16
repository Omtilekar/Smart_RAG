"""Task 4.6 - "finalize the provider abstraction": one config-driven entry
point that resolves `Settings.generation_provider`/`generation_model`
(src.config, Task 0.5 - reused unchanged) into a concrete
`GenerationProvider` instance, so a caller (a future FastAPI service,
Task 4.10) never hardcodes which adapter class to import.

Never guesses a provider or model - refuses (GenerationError) exactly
like scripts/smoke_generation.py's existing "never invents a model
choice" policy, extended here to the provider name too.
"""

from __future__ import annotations

from .provider import GenerationError, GenerationProvider

KNOWN_PROVIDERS: tuple[str, ...] = ("openrouter", "ollama")


def get_generation_provider(settings=None) -> GenerationProvider:
    """`settings` defaults to `src.config.get_settings()`. Raises
    GenerationError if `generation_provider`/`generation_model` are unset
    or the provider name is unrecognized - never silently falls back to a
    default provider or model."""
    if settings is None:
        from src.config import get_settings
        settings = get_settings()

    provider_name = (settings.generation_provider or "").strip().lower()
    model = (settings.generation_model or "").strip()

    if not provider_name:
        raise GenerationError("GENERATION_PROVIDER is not set")
    if not model:
        raise GenerationError("GENERATION_MODEL is not set")

    if provider_name == "openrouter":
        from .openrouter import OpenRouterProvider
        return OpenRouterProvider(model=model)
    if provider_name == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(model=model)

    raise GenerationError(
        f"unknown GENERATION_PROVIDER {provider_name!r} - expected one of {KNOWN_PROVIDERS}"
    )


__all__ = ["KNOWN_PROVIDERS", "get_generation_provider"]
