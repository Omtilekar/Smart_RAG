# Phase 4 Task 4.6 — Generation Production Interface

Finalizes Task 1.7's provider-neutral `GenerationProvider` interface for
production use, formally selects/freezes the live generation model, adds
a local/offline provider for zero-cost experimentation, and confirms
token-usage/latency tracking. Per `PROJECT_EXECUTION.md`'s Task 4.6
checklist:

```text
- [x] Finalize the provider abstraction.
- [x] Select the live generation model.
- [x] Preserve local/offline implementation where useful for experiments.
- [x] Track token usage and request latency.
```

## Finalize the provider abstraction

`src/generation/provider.py`'s `GenerationProvider` protocol
(`GenerationRequest`/`ProviderResponse`/`GenerationError`) is Task 1.7's
existing, already-clean interface — untouched. "Finalizing" it for
production meant adding the one thing it was missing: a config-driven
entry point. New `src/generation/factory.py`:

```python
from src.generation.factory import get_generation_provider
provider = get_generation_provider()  # reads Settings.generation_provider/generation_model
```

Resolves `Settings.generation_provider`/`generation_model` (Task 0.5,
reused unchanged) into a concrete `OpenRouterProvider` or
`OllamaProvider` instance. Raises `GenerationError` — never silently
falls back to a default provider or model — if either setting is unset
or the provider name is unrecognized, extending
`scripts/smoke_generation.py`'s existing "never invent a model choice"
policy to the provider name too. A future FastAPI service (Task 4.10)
calls this one function instead of hardcoding which adapter class to
import.

## Select the live generation model

**Frozen selection: `GENERATION_PROVIDER=openrouter`,
`GENERATION_MODEL=openai/gpt-oss-20b`.**

This is not a new, independently-decided choice — it confirms what the
project has already been using as its real generation model since
Phase 1/2:

- Task 1.7a (`project_plan/PHASE1_GENERATION.md`) ran real citation-format
  smoke tests against `openai/gpt-oss-20b` via OpenRouter.
- Task 2.13 (`project_plan/PHASE2_LLM_JUDGE_VALIDATION.md`) explicitly
  states: *"The project's real generation model is `openai/gpt-oss-20b`
  (family `gptoss`) via OpenRouter"* — and chose the judge model
  (`qwen3.5:9b`) specifically to be a **different model family**,
  confirming `gpt-oss-20b` was already the de facto production
  generation model two phases before this task existed.

Task 1.7's own `PHASE1_GENERATION.md` stated "no permanent generation
model is frozen" — that was correct for Phase 1 (explicit user intent to
decide later), and this task is that later decision, made explicit and
durable rather than left as an implicit convention repeated across two
prior phases' smoke tests.

**`.env.example` was not edited** — it is outside this session's file
permissions (both `Read` and `Bash cat` were denied by the sandbox's
permission rules for any `.env*` path). The frozen values above should
be set in the user's own `.env`:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
OPENROUTER_API_KEY=<the user's own key>
```

**Correction (added during Task 4.7, 2026-09-16)**: this section
originally stated no live paid API call was made during this task,
based on checking `OPENROUTER_API_KEY` with a bare `python -c
"os.environ.get(...)"` that never triggers `python-dotenv`. That check
was a false negative — the user's `.env` already had a real
`OPENROUTER_API_KEY` and `GENERATION_MODEL=openai/gpt-oss-20b`
configured, which only becomes visible once something imports
`src.config` (triggering `load_dotenv()`). As a result, 3 unintended
live OpenRouter API calls occurred later in this session (during Task
4.7's regression testing), triggered by running the full,
non-`--portable` test suite while these credentials were present and
`tests/test_openrouter_live_smoke.py` (`generation_api`-marked) was not
excluded from it. No billing amount is claimed or estimated here — see
`project_plan/PHASE4_INPUT_GUARDRAILS.md`'s "Unintended live API calls"
section for the full account and the resulting test-policy tightening.
This is a documentation correction only; the technical result recorded
below (the frozen model selection, the new local provider, the config-
driven factory) is unchanged.

## Preserve local/offline implementation for experiments

New `src/generation/ollama_provider.py` — `OllamaProvider`, a second
`GenerationProvider` implementation using the local Ollama server
already installed for Task 2.13's LLM judge (`gpt-oss:20b` and
`qwen3.5:9b` both already pulled). Reuses the exact endpoint/request
conventions already verified in `src.eval.llm_judge`
(`http://localhost:11434/api/chat`) — no second, independently-decided
Ollama client convention — but is a genuinely separate module: this is a
*generation* provider, not a judge, and `src.eval.llm_judge` is
untouched.

Deliberately defaults to `gpt-oss:20b` — the **same underlying model** as
the frozen live `openai/gpt-oss-20b` selection above, just served
locally instead of via OpenRouter. This makes it a real "zero-cost
stand-in for the production model" for development/experimentation,
never an arbitrary different local model.

Response shape verified directly with a real local call before writing
any code (not assumed from memory or from OpenRouter's differently-shaped
response):

```text
POST http://localhost:11434/api/chat
  {"model": ..., "message": {"role", "content"}, "done": true,
   "prompt_eval_count": <input tokens>, "eval_count": <output tokens>, ...}
```

No API key is read or required — the only network target is localhost.
`response_provider` is always `None` for this provider (no such concept
locally) — never fabricated to imitate an OpenRouter response.

**Real, free, local validation performed** (no cost, no external
network): `pytest -m ollama` exercises `OllamaProvider` against the real
local `gpt-oss:20b` server with the question "What is 2+2?" — passed,
6.68s (a prior warm-up call in this session had already loaded the model;
a cold call measured separately took ~27s, ~20s of which was model load,
not generation).

## Track token usage and request latency

`ProviderResponse` already carried `prompt_tokens`/`completion_tokens`/
`total_tokens`/`latency_ms` since Task 1.7 — every caller already had
access to these per-call. "Finalizing" this for production added one
thing: both `OpenRouterProvider.generate()` and the new
`OllamaProvider.generate()` now emit one structured `log_event()` line
per call (`event=generation_provider_call provider=... requested_model=...
response_model=... prompt_tokens=... completion_tokens=... total_tokens=...
latency_ms=...`) via `src.logging_utils` — the project's existing
structured-logging convention (already used by `src/storage.py`,
`scripts/serving_spike.py`, etc.) — so usage/latency is durably visible
in application logs regardless of whether a specific caller reads the
returned `ProviderResponse`. Never logs the prompt text, answer text, or
API key (the OpenRouter key never even enters this log call; `log_event`
also redacts any accidentally-secret-looking field name as a second
layer of defense).

## Tests

```text
tests/test_generation_factory.py        7 new tests (portable, fake Settings)
tests/test_ollama_provider.py          10 portable tests (monkeypatched requests.post,
                                        matching test_openrouter_provider.py's convention)
                                        + 1 real local `ollama`-marked integration test
                                        (free, no paid API - passed)
```

`scripts/dev.py test --portable`: all portable tests pass (no
regressions in `tests/test_openrouter_provider.py`/
`tests/test_minimal_generation.py` from the new logging call added to
`OpenRouterProvider.generate()`).

## Regression gates

`src/generation/provider.py`, `src/generation/minimal.py`,
`src/generation/citations.py`, and `src/eval/llm_judge.py` are all
byte-for-byte unchanged — only `src/generation/openrouter.py` gained one
additive logging call (no change to its request/response handling or
return values), and two new files
(`src/generation/ollama_provider.py`, `src/generation/factory.py`) were
added. No re-normalization/re-chunking/re-embedding/vector-index/XBRL-
export change. No paid API call made (see above). Protected TEST:
unopened, 0/3 official runs used.

## Files created/modified

```text
src/generation/ollama_provider.py       (new)
src/generation/factory.py               (new)
src/generation/openrouter.py            (additive: one log_event call)
tests/test_ollama_provider.py           (new)
tests/test_generation_factory.py        (new)
project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md   (this file)
Progress.md                             (updated)
```

## Known limitations

- The frozen `GENERATION_PROVIDER`/`GENERATION_MODEL` values could not be
  written to `.env.example` in this session (file-permission restriction)
  — the user should set them in their own `.env`.
- No live OpenRouter call was made or re-verified in this session (no
  API key configured here) — `tests/test_openrouter_live_smoke.py`
  remains the way to verify this for real once a key is available.
- No retry/resilience policy was added to either provider (still exactly
  one request per `generate()` call, matching Task 1.7's original scope)
  — production retry policy, along with input/context/output guardrails,
  belongs to Tasks 4.7-4.9, not this task.
- `OllamaProvider` was validated against `gpt-oss:20b` only (the model
  matching the frozen live selection) — `qwen3.5:9b` was not exercised
  through this new adapter (it remains the LLM-judge model, a different
  role, in `src.eval.llm_judge`).

## Next roadmap task

Phase 4, Task 4.7 — Input guardrails.
