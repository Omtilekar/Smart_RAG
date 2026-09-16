"""Task 4.6 - local, zero-cost Ollama adapter behind the GenerationProvider
interface, for "preserve local/offline implementation where useful for
experiments" (PROJECT_EXECUTION.md's Task 4.6 checklist).

Reuses the exact Ollama HTTP endpoint/request-shape conventions already
verified in Task 2.13's `src.eval.llm_judge` (`http://localhost:11434`,
`/api/chat`, `{"model", "messages", "stream": false}`) - no second,
independently-decided Ollama client convention. `src.eval.llm_judge`
itself is untouched; this is a new, separate adapter for the
GenerationProvider protocol, not a judge.

Response shape verified directly against the installed Ollama 0.34.0
with a real local call (`gpt-oss:20b`, "What is 2+2?") before writing
this, not assumed from memory or from OpenAI/OpenRouter's differently-
shaped response:

    {"model": ..., "message": {"role", "content"}, "done": true,
     "prompt_eval_count": <input tokens>, "eval_count": <output tokens>,
     ...duration fields in nanoseconds, unused here}

No `"provider"` field exists for a local model - `response_provider` is
always None, honestly (never fabricated to look like an OpenRouter
response).
"""

from __future__ import annotations

import logging
import time

import requests

from src.logging_utils import get_logger, log_event

from .provider import GenerationError, GenerationRequest, ProviderResponse

log = get_logger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
# Matches src.eval.llm_judge.DEFAULT_REQUEST_TIMEOUT_SECONDS - local
# generation on shared GPU/CPU hardware can be slow, especially on a
# cold model load (measured directly: ~20s of a ~27s real call was
# `load_duration`, not generation).
REQUEST_TIMEOUT_S = 120


class OllamaProvider:
    """GenerationProvider implementation for a local Ollama server.
    Never reads or requires an API key - the only network target is
    localhost. Raises GenerationError (never hangs silently) if
    `ollama serve` is not reachable."""

    def __init__(self, model: str):
        if not model or not model.strip():
            raise ValueError("model must be a non-empty Ollama model tag (e.g. 'gpt-oss:20b')")
        self._model = model

    def __repr__(self) -> str:
        return f"OllamaProvider(model={self._model!r})"

    def generate(self, request: GenerationRequest) -> ProviderResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "options": {"temperature": request.temperature},
            "stream": False,
        }

        start = time.perf_counter()
        try:
            response = requests.post(CHAT_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException as e:
            raise GenerationError(
                f"Ollama request failed: {type(e).__name__} - is `ollama serve` running on {OLLAMA_BASE_URL}?"
            ) from None
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code != 200:
            raise GenerationError(f"Ollama returned HTTP {response.status_code} for model {self._model!r}")

        try:
            data = response.json()
        except ValueError:
            raise GenerationError("Ollama response was not valid JSON") from None

        try:
            text = data["message"]["content"]
        except (KeyError, TypeError):
            raise GenerationError("Ollama response missing message.content") from None

        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        total_tokens = (
            prompt_tokens + completion_tokens
            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int)
            else None
        )

        # Task 4.6 - "track token usage and request latency" (same
        # convention as src.generation.openrouter.OpenRouterProvider) -
        # never the prompt/answer text.
        log_event(
            log, logging.INFO, "generation_provider_call",
            provider="ollama", requested_model=self._model, response_model=data.get("model"),
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total_tokens, latency_ms=round(latency_ms, 1),
        )

        return ProviderResponse(
            text=text,
            requested_model=self._model,
            response_model=data.get("model"),
            provider_name="ollama",
            response_provider=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            temperature_requested=request.temperature,
            latency_ms=latency_ms,
        )
