"""Task 4.14a - provider-aware LLM prompt-prefix caching integration layer.

This module is the ONLY place that knows how each provider caches prompt
prefixes. It is deliberately about *prompt-prefix* caching and nothing else:

- provider-native prompt caching (OpenRouter -> OpenAI/DeepSeek/Grok/Gemini
  automatic; Anthropic explicit `cache_control` breakpoints),
- local inference KV/prefix reuse (Ollama's llama runner, automatic),

and NOT response caching (never returns a stored answer) or retrieval
caching (src/retrieval/cache.py, untouched). No application-level cache
of prompts or answers is maintained here, so there are no application cache
keys to isolate: a provider can only reuse a prefix that is byte-for-byte
identical, so evidence for a different company / fiscal period / document
version can never be substituted for another's.

Verified against the current OpenRouter documentation
(https://openrouter.ai/docs/guides/best-practices/prompt-caching):

- Automatic (nothing to send): OpenAI (>=1024-token prefix), DeepSeek,
  Grok, Moonshot, Z.AI, Gemini 2.5+ implicit caching.
- Explicit: Anthropic needs `"cache_control": {"type": "ephemeral"}` on a
  content block inside `messages[].content` (max 4 breakpoints, model-
  dependent 512-4096 token minimum, 5-minute default TTL).
- Usage: `usage.prompt_tokens_details.cached_tokens` (reads) and
  `.cache_write_tokens` (writes); cost in `usage.cost` when reported.

Verified empirically against the installed Ollama 0.40.3 (see
project_plan/PHASE4_PROMPT_CACHING.md): the runner reuses KV state for a
shared prompt prefix automatically, but reports NO cached-token count -
`prompt_eval_count` is always the full prompt size. Only
`prompt_eval_duration` reveals reuse, so Ollama cache hits are *never*
reported as cached tokens here (that would be an invented value).
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Any

from .provider import GenerationRequest

STRATEGY_NONE = "none"
STRATEGY_AUTOMATIC = "automatic"
STRATEGY_EXPLICIT = "explicit_breakpoints"
STRATEGY_LOCAL_PREFIX = "local_prefix"

# PROMPT_CACHE_PROVIDER_MODE values. "auto" detects from the model id;
# the others force an OpenRouter strategy for models the table below does
# not know. "none" bypasses provider-specific request changes entirely.
PROVIDER_MODES: tuple[str, ...] = ("auto", STRATEGY_NONE, STRATEGY_AUTOMATIC, STRATEGY_EXPLICIT)

# OpenRouter model-id prefixes. Anything unlisted resolves to STRATEGY_NONE
# in "auto" mode: no request is ever modified for a model that is not known
# to accept the parameter. (Alibaba/Qwen explicit caching is model-specific
# and snapshots reject it, so it is opt-in via PROMPT_CACHE_PROVIDER_MODE.)
_EXPLICIT_PREFIXES: tuple[str, ...] = ("anthropic/",)
_AUTOMATIC_PREFIXES: tuple[str, ...] = (
    "openai/", "deepseek/", "x-ai/", "moonshotai/", "z-ai/",
    "google/gemini-2.5", "google/gemini-3",
)


@dataclass(frozen=True)
class PromptCacheConfig:
    enabled: bool = False
    provider_mode: str = "auto"
    metrics_enabled: bool = True

    def __post_init__(self) -> None:
        if self.provider_mode not in PROVIDER_MODES:
            raise ValueError(f"provider_mode={self.provider_mode!r} invalid; expected one of {PROVIDER_MODES}")

    @classmethod
    def from_settings(cls, settings: Any) -> "PromptCacheConfig":
        """Tolerates settings objects without the Task 4.14a fields (older
        test fakes) by falling back to the disabled default."""
        return cls(
            enabled=bool(getattr(settings, "prompt_cache_enabled", False)),
            provider_mode=getattr(settings, "prompt_cache_provider_mode", "auto"),
            metrics_enabled=bool(getattr(settings, "prompt_cache_metrics_enabled", True)),
        )


DISABLED = PromptCacheConfig(enabled=False)


def resolve_strategy(provider_name: str, model: str, config: PromptCacheConfig) -> str:
    """The cache strategy for one provider/model. Pure; never raises."""
    if not config.enabled or config.provider_mode == STRATEGY_NONE:
        return STRATEGY_NONE
    if provider_name == "ollama":
        return STRATEGY_LOCAL_PREFIX
    if provider_name != "openrouter":
        return STRATEGY_NONE
    if config.provider_mode != "auto":
        return config.provider_mode
    lowered = model.strip().lower()
    if lowered.startswith(_EXPLICIT_PREFIXES):
        return STRATEGY_EXPLICIT
    if lowered.startswith(_AUTOMATIC_PREFIXES):
        return STRATEGY_AUTOMATIC
    return STRATEGY_NONE


_CACHE_CONTROL = {"type": "ephemeral"}


def build_messages(request: GenerationRequest, strategy: str) -> list[dict]:
    """Chat messages for `request`. For every strategy except
    STRATEGY_EXPLICIT the result is exactly the pre-Task-4.15 two plain
    string messages. For STRATEGY_EXPLICIT the system prompt and the
    reusable evidence prefix become content blocks carrying a
    `cache_control` breakpoint; the question stays in its own un-cached
    trailing block. Roles and text are never altered, so retrieved
    evidence stays in the *user* message (untrusted data) and is never
    promoted to the system role."""
    if strategy != STRATEGY_EXPLICIT:
        return [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]

    system_content = [{"type": "text", "text": request.system_prompt, "cache_control": dict(_CACHE_CONTROL)}]
    split = request.cacheable_prefix_len
    if 0 < split < len(request.user_prompt):
        user_content: Any = [
            {"type": "text", "text": request.user_prompt[:split], "cache_control": dict(_CACHE_CONTROL)},
            {"type": "text", "text": request.user_prompt[split:]},
        ]
    else:
        # No reusable evidence prefix: a breakpoint here would pay the
        # cache-write premium on query-specific text that never recurs.
        user_content = request.user_prompt
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def prefix_fingerprints(request: GenerationRequest) -> tuple[str, str | None]:
    """(system_prompt_fp, evidence_prefix_fp) - short SHA-256 hex digests
    for log correlation only. Never the text itself."""
    def fp(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    split = request.cacheable_prefix_len
    prefix_fp = fp(request.user_prompt[:split]) if split > 0 else None
    return fp(request.system_prompt), prefix_fp


@dataclass(frozen=True)
class CacheUsage:
    """What the provider *reported*. `None` means unreported, never zero."""
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    cost_usd: float | None = None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def extract_openrouter_cache_usage(usage: Any) -> CacheUsage:
    if not isinstance(usage, dict):
        return CacheUsage()
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    cost = usage.get("cost")
    return CacheUsage(
        cached_tokens=_as_int(details.get("cached_tokens")),
        cache_write_tokens=_as_int(details.get("cache_write_tokens")),
        cost_usd=float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
    )


class PromptCacheMetrics:
    """In-process, thread-safe aggregate of provider-reported cache usage,
    surfaced through the existing GET /status snapshot (no separate
    dashboard). Counters only count what providers reported:
    `hit_rate` is hits / requests-that-reported-cache-usage, and is None
    (not 0) when nothing was reported."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset()

    def _reset(self) -> None:
        self._requests = 0
        self._reporting = 0
        self._hits = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cached_tokens = 0
        self._write_tokens = 0
        self._cost = 0.0
        self._cost_reported = 0
        self._by_strategy: dict[str, int] = {}

    def record(self, *, strategy: str, input_tokens: int | None, output_tokens: int | None,
               usage: CacheUsage) -> None:
        with self._lock:
            self._requests += 1
            self._by_strategy[strategy] = self._by_strategy.get(strategy, 0) + 1
            self._input_tokens += input_tokens or 0
            self._output_tokens += output_tokens or 0
            if usage.cached_tokens is not None:
                self._reporting += 1
                self._cached_tokens += usage.cached_tokens
                if usage.cached_tokens > 0:
                    self._hits += 1
            self._write_tokens += usage.cache_write_tokens or 0
            if usage.cost_usd is not None:
                self._cost += usage.cost_usd
                self._cost_reported += 1

    def snapshot(self) -> dict[str, bool | int | float | str | None]:
        with self._lock:
            return {
                "requests": self._requests,
                "requests_reporting_cache_usage": self._reporting,
                "cache_hit_requests": self._hits,
                "cache_hit_rate": (self._hits / self._reporting) if self._reporting else None,
                "input_tokens": self._input_tokens,
                "output_tokens": self._output_tokens,
                "cached_input_tokens": self._cached_tokens,
                "cache_write_tokens": self._write_tokens,
                "reported_cost_usd": self._cost if self._cost_reported else None,
                "requests_by_strategy": ",".join(f"{k}={v}" for k, v in sorted(self._by_strategy.items())),
            }


__all__ = [
    "CacheUsage", "DISABLED", "PROVIDER_MODES", "PromptCacheConfig", "PromptCacheMetrics",
    "STRATEGY_AUTOMATIC", "STRATEGY_EXPLICIT", "STRATEGY_LOCAL_PREFIX", "STRATEGY_NONE",
    "build_messages", "extract_openrouter_cache_usage", "prefix_fingerprints", "resolve_strategy",
]
