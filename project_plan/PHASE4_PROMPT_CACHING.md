# Phase 4 - LLM Prompt-Prefix Caching (Task 4.14a)

Status: **implemented, off by default** (`PROMPT_CACHE_ENABLED=false`).
Numbering note: `PROJECT_EXECUTION.md` already owns Task 4.15 ("Production
performance evaluation"), so this follow-up is 4.14a.

## What this is (and is not)

Prompt caching lets an LLM provider skip re-processing a prompt prefix it
has already seen byte-for-byte. It is **not**:

| Mechanism | Where | Touched? |
|---|---|---|
| Provider-native prompt-prefix caching | OpenRouter -> Anthropic/OpenAI/DeepSeek/Gemini/... | **this task** |
| Local KV/prefix reuse | Ollama's runner | **this task** (layout only; Ollama does it itself) |
| Retrieval caching | `src/retrieval/cache.py` (Task 4.13) | no |
| Response caching (return a stored answer) | - | **not implemented**; never enabled implicitly. OpenRouter's separate response-cache feature is not used. |

The application keeps **no** prompt/answer cache of its own, so there are no
application cache keys, no staleness, and no cross-user leakage surface to
manage. The only cache is the provider's, which can only match a
byte-identical prefix.

## Request flow

```
POST /query -> input guard -> router -> (structured XBRL answer, no LLM)  |  dense route:
  retriever (+Task 4.13 exact retrieval cache)
    -> RetrievalSecurityGuard (Task 4.14)  -> check_dense_context (Task 4.8)
    -> build_user_prompt(layout)            <- only guard-approved evidence reaches here
    -> GenerationRequest(system, user, cacheable_prefix_len)
    -> provider adapter -> prompt_cache.build_messages(strategy)
          OpenRouter  explicit_breakpoints | automatic | none
          Ollama      local_prefix (payload unchanged)
    -> usage extraction -> structured log + PromptCacheMetrics
    -> parse_citations -> output guard (Task 4.9) -> response
```

Guard order is unchanged: input -> retrieval-security -> context -> (layout,
provider) -> output. Caching is bypassed (legacy two-message payload, legacy
layout) whenever it is disabled, the provider/model is not known to support
it, or `PROMPT_CACHE_PROVIDER_MODE=none`. A provider error is raised exactly
as before; there is no cache-specific failure path to fall back from.

## How the reusable prompt is built

`PROMPT_CACHE_ENABLED=false` (default) keeps the original layout:
`system = SYSTEM_PROMPT`, `user = "Question: ...\n\nContext:\n<evidence>"`.
The question comes first, so only the system prompt can ever be a shared
prefix.

`PROMPT_CACHE_ENABLED=true` switches to the cache-friendly layout:

1. `system` - the unchanged `SYSTEM_PROMPT` (grounding, citation format and
   abstention rules; stable, byte-identical across requests).
2. `user`, reusable block - `Context:\n<delimited evidence blocks>\n\n`
   (same `format_evidence_block()` markers, chunk IDs, company, fiscal year,
   document ID as before; still in the *user* role, i.e. untrusted data).
3. `user`, dynamic tail - `Question: <current question>`.

Items 1-3 map onto the requested order (stable instructions -> reusable
content -> retrieved evidence -> conversation -> query); the app has no
multi-turn state, so there is no conversation segment. Evidence is never
moved into the system role and no security instruction was reordered.

For `explicit_breakpoints` (Anthropic) the system prompt and the evidence
block each become a content block carrying
`{"cache_control": {"type": "ephemeral"}}`; the question block is never
cached. Concatenated block text equals the original `user_prompt`.

## Provider support

Verified against the current OpenRouter docs
(<https://openrouter.ai/docs/guides/best-practices/prompt-caching>):

| Provider / model id prefix | Strategy (`auto` mode) | Request change | Notes |
|---|---|---|---|
| `anthropic/*` | `explicit_breakpoints` | `cache_control` on system + evidence blocks | min 512-4096 tokens by model, 5 min TTL |
| `openai/*` (incl. `openai/gpt-oss-20b`, the live model), `deepseek/`, `x-ai/`, `moonshotai/`, `z-ai/`, `google/gemini-2.5*`, `google/gemini-3*` | `automatic` | none (stable prefix only) | OpenAI needs a >=1024-token prefix; for the open-weight `gpt-oss` the *backing provider* decides whether it caches |
| anything else (Llama, Qwen, Mistral, ...) | `none` | none | never sent parameters it may reject |
| Ollama (local) | `local_prefix` | none | see below |

Force a strategy for a model the table doesn't know with
`PROMPT_CACHE_PROVIDER_MODE=automatic|explicit_breakpoints` (e.g. Alibaba
Qwen explicit caching is model-specific and snapshot endpoints reject it, so
it is opt-in only). Not verified against live OpenRouter: **no paid request
was made**; OpenRouter behaviour is covered by mocked-HTTP tests only.

### Ollama (verified locally, Ollama 0.40.3, `gpt-oss:20b` and `qwen3.5:9b`)

* Ollama's runner **does** reuse KV state for a shared prompt prefix
  across `/api/chat` requests, automatically. There is no request parameter
  to enable it, so the adapter sends the same payload with caching on or off.
* It reports **no cached-token count**: `prompt_eval_count` is always the
  full prompt size. The only signal is `prompt_eval_duration`, recorded as
  `prompt_eval_ms`. Cached tokens for Ollama are therefore `null`, never
  estimated.
* Reuse is single-slot and prefix-only: an identical repeat and "same
  evidence, different question" (question last) both hit; changing the
  evidence (other company/period/chunks) misses. The legacy question-first
  layout can only hit on exact repeats - this is the real benefit of the
  layout change.
* `keep_alive` / model residency only avoids reloading weights
  (`load_duration` was 20-50 s cold vs ~8 ms warm); it is not prompt caching
  and is not configured here.
* Context window: the adapter sets no `num_ctx`. In a probe, an oversized
  prompt reported `prompt_eval_count=4098`, i.e. the default context here
  appears to be ~4k tokens and longer prompts are truncated by Ollama. A
  prompt of 5 x 512-token chunks plus the system prompt is ~3.4k tokens and
  fits. Out of scope for
  this task, but worth knowing - see limitations.

## Configuration

| Variable | Default | Values | Meaning |
|---|---|---|---|
| `PROMPT_CACHE_ENABLED` | `false` | true/false | Master switch. Enables the cache-friendly layout and provider-specific request shaping. |
| `PROMPT_CACHE_PROVIDER_MODE` | `auto` | `auto`, `none`, `automatic`, `explicit_breakpoints` | `auto` detects by model id; others force a strategy; `none` disables provider request shaping. Invalid -> `ConfigError`. |
| `PROMPT_CACHE_METRICS_ENABLED` | `true` | true/false | Record aggregate counters exposed via `GET /status`. |

## Observability

* One structured `generation_provider_call` log line per call: provider,
  model, `prompt_cache_enabled`, `cache_strategy`, input/output/total tokens,
  `cached_tokens`, `cache_write_tokens`, `cost_usd`, latency, Ollama
  `prompt_eval_ms`, and 12-char SHA-256 fingerprints of the system prompt and
  evidence prefix (for correlating hits - never prompt text, queries, or
  keys). Fields the provider did not report are `None`.
* `GET /status` -> `prompt_cache`: enabled flag, provider mode, requests,
  requests that reported cache usage, hit requests, `cache_hit_rate`
  (hits / reporting requests; `null` when nothing reported), input/output/
  cached/cache-write tokens, provider-reported cost, requests by strategy.
* Bug fixed on the way: `log_event()` redacted every field whose name
  contains "token", so `prompt_tokens`/`total_tokens` were logged as
  `[REDACTED]` since Task 4.6. The redaction now skips plural `*_tokens`
  count fields while still redacting `token`, `access_token`, etc.
* First-token latency: unavailable. The adapters are non-streaming (the app
  has no streaming endpoint); `build_messages()` is shared, so a future
  streaming path gets identical cache-aware payloads.

### Verifying a real cache hit

* OpenRouter: send the same evidence twice within the TTL (>= model minimum
  tokens) and check `cached_tokens > 0` in the log line / `cache_hit_rate`
  in `/status`; for Anthropic the first call shows `cache_write_tokens > 0`.
  A hit is read from the provider's own usage report, never inferred.
* Ollama: `prompt_eval_ms` collapses from seconds to ~0.05-0.25 s while
  `prompt_eval_count` stays the same.

## Benchmark (measured, local Ollama, `gpt-oss:20b`)

```bash
python scripts/benchmark_prompt_cache.py --provider ollama --model gpt-oss:20b --repeats 3
```

12 requests per mode per repeat, 3 repeats, synthetic 5 x ~512-token
evidence per request with a per-run salt, output capped at 64 tokens by the
harness (not by product code). "No caching" = legacy layout; "enabled" =
cache-friendly layout. Raw rows: `results/phase_4_14a_prompt_cache_benchmark.json`.

| Metric | No caching | Caching enabled | Difference |
|---|---|---|---|
| Input tokens / request (mean) | 3,431 | 3,431 | +1 (+0.0%) |
| Cached input tokens | unavailable (Ollama does not report) | unavailable | unavailable |
| P50 latency | 8,275 ms | 8,246 ms | -29 ms (-0.3%) |
| P95 latency | 8,459 ms | 8,523 ms | +64 ms (+0.8%) |
| P50 / P95 prompt-eval time | 3,728 / 3,773 ms | 3,720 / 3,766 ms | -0.2% |
| First-token latency | unavailable (non-streaming) | unavailable | unavailable |
| Cost per query | unavailable (local; no cost reported) | unavailable | unavailable |

Pooled percentiles hide the effect because 7 of the 12 scenario requests
are legitimately cold in both modes. Per scenario (mean provider latency /
mean prompt-eval):

| Scenario | No caching | Caching enabled |
|---|---|---|
| 1 repeated query | 5,904 / 1,274 ms | 5,902 / 1,279 ms |
| **2 same evidence, new question** | 8,348 / 3,743 ms | **4,853 / 220 ms** |
| 3 different company | 8,307 / 3,759 ms | 8,380 / 3,751 ms |
| 4 different fiscal period | 8,271 / 3,742 ms | 8,336 / 3,748 ms |
| 5 new retrieved context | 8,309 / 3,717 ms | 8,415 / 3,732 ms |
| 6 multi-turn | not applicable (no conversation state) | not applicable |

Reading the numbers:

* The gain comes from **Ollama's local KV-prefix reuse, unlocked by the
  layout change** - not from provider-native caching and not from the
  retrieval cache (the benchmark bypasses retrieval entirely).
* Exact repeats were already fast in both modes (Ollama reuses an identical
  prompt regardless of layout). The new layout adds reuse for *different
  questions over the same evidence* (prompt processing 3.7 s -> 0.22 s,
  all 9 samples 172-257 ms vs 3.7-3.8 s).
* Different company / fiscal period / chunk set correctly **miss** in both
  modes - the evidence differs, so the prefix differs. This is the
  isolation property, observed.
* Overhead: the added work is string slicing and one SHA-256 of the prompt
  for log fingerprints (microseconds); P95 differences above are noise.
* A first, single-run benchmark showed only a partial gain on scenario 2
  (~2.3-3.1 s prompt eval). A direct replay of the same request sequence and
  all 9 samples of the final 3-repeat run did not reproduce it; treated as
  an outlier (cause not established), which is why the harness now pools
  repeats.
* OpenRouter cost/latency savings are **not measured** (no paid calls
  authorized). Expect savings only where the selected model/backing
  provider caches and the prefix exceeds its minimum.

## Invalidation and security

* No application cache -> nothing to invalidate. Provider caches key on the
  exact prefix, so a re-ingested/updated filing (different text) or a
  different company/fiscal period produces a different prefix and a miss.
  Test coverage: `tests/test_prompt_cache.py` asserts prefixes differ across
  companies and fiscal periods and that evidence never enters the system role.
* A cache hit says only "this prefix was processed before"; it is never used
  as evidence of freshness or correctness of an answer.
* Only evidence that already passed the retrieval-security and context
  guards is laid out as a cacheable prefix. The filings are public SEC data
  and were already sent to the provider; caching adds the provider's
  retention window (OpenRouter/Anthropic: ~5 min default TTL; sticky routing
  up to ~10 min). Follow the selected provider's retention policy before
  enabling this for non-public corpora.
* Per-user isolation: the corpus and prompts contain no user-specific data
  (the question is in the uncached tail). If per-tenant evidence is ever
  added, tenant identity must go into the cacheable prefix or caching must
  stay off.

## Known limitations

* Changing the layout changes what the model sees (evidence before
  question). Answer-quality/citation-accuracy impact on FinanceBench or the
  dev eval set was **not** evaluated in this task (that needs paid calls or a
  full local eval run); this is why caching is opt-in. Citation-format and
  guard behaviour are covered by unit tests only.
* System prompt alone (~0.4k tokens) is below most providers' minimums; the
  benefit comes from the evidence prefix and applies only when the same
  evidence recurs.
* `gpt-oss` via OpenRouter: whether a hit occurs depends on the backing
  provider; the adapter reads `cached_tokens` and reports `null` if absent.
* Ollama: no cached-token count, single-slot prefix reuse, ~4k default
  context (no `num_ctx` is set by the adapter), and `gpt-oss`/other models
  may behave differently on other Ollama versions.
* No streaming or multi-turn path exists in the app today.
