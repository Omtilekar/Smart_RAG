"""Task 1.7 - OpenRouter adapter behind the GenerationProvider interface.

API contract verified directly from OpenRouter's own documentation
(https://openrouter.ai/docs/api-reference/chat-completion and
https://openrouter.ai/docs/api-reference/authentication), not from memory:

- POST https://openrouter.ai/api/v1/chat/completions
- Authorization: Bearer <OPENROUTER_API_KEY>
- Content-Type: application/json
- request body: {"model": str, "messages": [{"role","content"}, ...],
  "temperature": float, "stream": false (explicit, not the implicit default)}
- response body: choices[0].message.content holds the generated text;
  top-level "model" echoes the model actually used; "usage" holds
  prompt_tokens/completion_tokens/total_tokens
- error status codes: 401 (auth), 402 (insufficient credits), 403
  (permissions/guardrail), 404 (model not found), 429 (rate limit), 500/502/
  503/524/529 (server/upstream/timeout/overload)

No "provider" field is documented in the base chat-completion response
schema - `response_provider` is populated from the response's top-level
"provider" key only if the API actually returns one; otherwise it stays
None (not fabricated).

Uses `requests` (already a project dependency, requirements.txt) - no new
SDK dependency. Timeout reuses the existing 60s convention already
established for API-style requests in src/ingest/common.py's `get()`.
"""

from __future__ import annotations

import logging
import os
import time

import requests

from src.logging_utils import get_logger, log_event

from .provider import GenerationError, GenerationRequest, ProviderResponse

log = get_logger(__name__)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
API_KEY_ENV_VAR = "OPENROUTER_API_KEY"
REQUEST_TIMEOUT_S = 60  # matches src/ingest/common.py's get() default for API-style requests

_ERROR_MEANINGS = {
    401: "authentication failed (invalid or missing API key)",
    402: "insufficient OpenRouter credits",
    403: "insufficient permissions or guardrail block",
    404: "model not found",
    429: "rate limit exceeded",
    500: "OpenRouter internal server error",
    502: "upstream provider failure",
    503: "service temporarily unavailable",
    524: "infrastructure timeout",
    529: "provider overloaded",
}


class OpenRouterProvider:
    """GenerationProvider implementation for OpenRouter. Reads
    OPENROUTER_API_KEY from the process environment at call time - never
    stored on the instance beyond the single request, never included in
    __repr__, never logged."""

    def __init__(self, model: str):
        if not model or not model.strip():
            raise ValueError("model must be a non-empty OpenRouter model ID")
        self._model = model

    def __repr__(self) -> str:
        return f"OpenRouterProvider(model={self._model!r})"

    def generate(self, request: GenerationRequest) -> ProviderResponse:
        api_key = os.environ.get(API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise GenerationError(f"{API_KEY_ENV_VAR} is not set in the environment")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        start = time.perf_counter()
        try:
            response = requests.post(
                OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as e:
            raise GenerationError(f"OpenRouter request failed: {type(e).__name__}") from None
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code != 200:
            meaning = _ERROR_MEANINGS.get(response.status_code, "unexpected error")
            raise GenerationError(
                f"OpenRouter returned HTTP {response.status_code} ({meaning}) for model {self._model!r}"
            )

        try:
            data = response.json()
        except ValueError:
            raise GenerationError("OpenRouter response was not valid JSON") from None

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise GenerationError("OpenRouter response missing choices[0].message.content") from None

        usage = data.get("usage") or {}

        # Task 4.6 - "track token usage and request latency": one
        # structured log line per call, never the prompt/answer text or
        # the API key (log_event redacts secret-looking field names as a
        # second layer of defense, but this line never passes one anyway).
        log_event(
            log, logging.INFO, "generation_provider_call",
            provider="openrouter", requested_model=self._model, response_model=data.get("model"),
            prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"), latency_ms=round(latency_ms, 1),
        )

        return ProviderResponse(
            text=text,
            requested_model=self._model,
            response_model=data.get("model"),
            provider_name="openrouter",
            response_provider=data.get("provider"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            temperature_requested=request.temperature,
            latency_ms=latency_ms,
        )
