"""Task 1.7 - provider-neutral generation interface.

Isolates provider-specific concepts (URL, auth headers, request/response
schema, error translation) behind a small interface so the OpenRouter
adapter (src/generation/openrouter.py) can be replaced later without
touching retrieval or prompt-construction code. OpenRouter is the Phase 1
*testing* provider, not a frozen architectural choice - see
project_plan/PHASE1_GENERATION.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GenerationRequest:
    """Provider-neutral request. `system_prompt` and `user_prompt` are
    already fully composed by the orchestrator (src/generation/minimal.py)
    - the provider adapter does no prompt construction of its own."""
    system_prompt: str
    user_prompt: str
    temperature: float = 0.0


@dataclass(frozen=True)
class ProviderResponse:
    """Provider-neutral response. Never includes the API key, raw HTTP
    response, or authorization header. `response_model`/`response_provider`
    are None when the provider's response schema doesn't report them."""
    text: str
    requested_model: str
    response_model: str | None
    provider_name: str
    response_provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    temperature_requested: float
    latency_ms: float


class GenerationError(Exception):
    """Safe, credential-free error for provider/network failures. Never
    includes the Authorization header or API key value in its message."""


class GenerationProvider(Protocol):
    def generate(self, request: GenerationRequest) -> ProviderResponse: ...
