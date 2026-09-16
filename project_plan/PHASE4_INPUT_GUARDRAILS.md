# Phase 4 Task 4.7 — Input Guardrails

Implements and validates the production input-guardrail boundary:

```text
USER INPUT -> INPUT GUARDRAIL -> ALLOW or REJECT -> only allowed input
continues to routing / retrieval / generation
```

Deterministic, local, no network/model/LLM call anywhere in the guard
module (statically verified). Does not answer "is the retrieved context
safe" (Task 4.8) or "is the generated answer safe" (Task 4.9) — those
are separate, later guardrail layers.

## Unintended live API calls (incident during this task's own regression testing)

While running this task's full regression suite (`scripts/dev.py test`,
no marker filter), 3 unintended real, live, credentialed calls to
OpenRouter (`openai/gpt-oss-20b`, the frozen Task 4.6 model) occurred.
No dollar amount is claimed or estimated here.

**Root cause**: Task 4.6's documentation stated no live paid call had
been made, based on checking `OPENROUTER_API_KEY` with a bare `python -c
"os.environ.get(...)"` — that check never triggers `python-dotenv`, so it
produced a false negative. The user's `.env` already had a real
`OPENROUTER_API_KEY`/`GENERATION_MODEL=openai/gpt-oss-20b` configured
(for legitimate local generation work); `python-dotenv` populates
`os.environ` from `.env` as a side effect of importing `src.config`
anywhere in a test run. `tests/test_openrouter_live_smoke.py`
(`generation_api`-marked) is excluded from `--portable` but **not** from
plain `dev.py test`/`pytest` with no filter — so once real credentials
existed, every full-suite run silently made a real network call, with no
explicit intent expressed at that moment. That test then ran three times
in this session: once during Task 4.6's own regression check, twice
during Task 4.7's (see `Progress.md`'s Task 4.6 correction note for the
full account).

**Fixes applied (this task)**:

1. `tests/test_openrouter_live_smoke.py` now requires a **separate,
   explicit** `RUN_LIVE_GENERATION_API_TEST=1` opt-in, in addition to the
   API key and model — merely having credentials configured is no longer
   sufficient. Verified directly: with real credentials present but the
   opt-in var unset, the test now SKIPPED (not PASSED).
2. `project_plan/DEVELOPER_COMMANDS.md` documents the caveat and
   recommends `test -m "not generation_api"` on any machine with real
   OpenRouter credentials — without silently redesigning `dev.py test`'s
   own default behavior (a broader project-policy change, left for a
   later developer-command cleanup task per explicit user decision).
3. **Every regression check for the remainder of Task 4.7** used an
   explicit `-m "not generation_api"` (or `--portable`, which already
   excludes it) — see "Regression gates" below for the exact commands
   run and their results. Zero paid API calls occurred after this
   incident was found and fixed.

## Authoritative requirement — a material scope conflict, recorded

The task prompt this work started from described a narrower scope
(structural validation + optional injection detection). Per its own
instruction ("if scope materially differs from `PROJECT_EXECUTION.md`,
follow the roadmap and report the difference"), the actual authoritative
`PROJECT_EXECUTION.md` Task 4.7 checklist is materially broader:

```text
### 4.7 Input guardrails
Add:
- [x] request length limits
- [x] scope enforcement
- [x] advice detection/refusal
- [x] PII checks appropriate to the SEC use case
- [x] injection-pattern handling
- [ ] rate limiting strategy  (documented, not implemented in-process — see below)
```

All six items are addressed. The first five are implemented as
deterministic content checks in `src/guards/input.py`. The sixth (rate
limiting) is a **documented architectural decision**, not application
code — see "Rate limiting strategy" below.

## Four explicit user decisions (2026-09-16)

None of the following had a concrete value anywhere in the repository —
per the task's own "STOP AND ASK, do not invent a threshold" rule, these
were resolved with the user before writing guard code:

| Decision | Chosen | Why |
|---|---|---|
| Max input length | **2,000 characters** | `PROJECT_SPEC.md`'s "Length cap \| Hard limit" names no number. 2,000 is generous for a real question, far under Qwen3-Embedding-0.6B's 32,768-token max_seq_length, small enough to bound abuse. |
| PII tooling | **Regex-only** (SSN/credit-card/email/phone) | `PROJECT_SPEC.md` names Presidio (spaCy + language-model download — a new, heavy dependency). Not adopted unilaterally for this task; documented as the spec's eventual target. |
| Scope-enforcement rule | **Loose deny-list** — reject only inputs with *zero* financial/SEC-domain signal | Task 3.8's router's own out-of-scope rule (`no_resolvable_financial_signal`) requires a resolvable CIK/fiscal_year/XBRL-concept — too strict; it would reject Task 1.7's own legitimate smoke question "What are the main risk factors described in this filing?" (no CIK/concept at all). |
| Rate limiting | **Document the strategy only** | `PROJECT_SPEC.md` assigns this to infrastructure ("Rate limiting \| API Gateway"), and this task explicitly forbids building the FastAPI/serving layer that a limiter would sit in front of. |

## Implemented contract

```python
from src.guards.input import GuardDecision, check_input, check_input_with_settings

@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason_code: str | None
    detail: str | None

check_input(question: str, *, max_length: int) -> GuardDecision
check_input_with_settings(question, settings=None) -> GuardDecision  # reads Settings.input_guard_max_length
```

### Guard order (first violation wins)

```text
1. invalid_type                    - not a str
2. empty_input                     - empty or whitespace-only after strip()
3. input_too_long                  - len(question) > max_length
4. disallowed_control_character    - any Unicode category "Cc" char except \t \n \r
5. prompt_injection_detected       - matches src.router.rules.INJECTION_KEYWORDS
6. advice_request_detected         - matches src.router.rules.ADVICE_KEYWORDS
7. pii_detected                    - SSN / credit-card / email / phone regex
8. out_of_scope                    - no financial/SEC-domain keyword, form-type, or fiscal-year signal
(else)                             - allowed=True, reason_code=None
```

Cheapest/most-structural checks run first (matches
`src.index.lancedb_index.validate_chunk_table`'s own "return on first
violated invariant" convention). Injection is checked before advice/PII/
scope since a malicious input's other properties are irrelevant once
it's already rejected for that reason.

### Reason codes

```text
invalid_type, empty_input, input_too_long, disallowed_control_character,
prompt_injection_detected, advice_request_detected, pii_detected, out_of_scope
```

Exactly one code per implemented check — no reason code exists without a
corresponding real check behind it. `src.guards.input.REASON_CODES` is
the tracked list a future API layer can translate into HTTP responses
without parsing human-readable text.

### No duplicated keyword lists

`prompt_injection_detected` and `advice_request_detected` reuse
`src.router.rules.INJECTION_KEYWORDS`/`ADVICE_KEYWORDS` directly — two
new public read-only aliases added to `src/router/rules.py` for exactly
this reuse (`classify_intent()`'s own behavior is byte-for-byte
unchanged; the private `_INJECTION_KEYWORDS`/`_ADVICE_KEYWORDS` names
remain the module's real source of truth). This avoids "two competing
guardrail APIs" maintaining the same keyword semantics independently.

### Scope enforcement (loose deny-list)

`_has_domain_signal()` accepts the input if it contains **any** of:
a ~50-term financial/SEC-domain keyword (`10-K`, `revenue`, `risk
factor`, `fiscal year`, `company`, ...), a recognized form type
(`src.router.rules.extract_form_type()`, reused), or a plausible
19xx/20xx year (`extract_fiscal_years()`, reused). This is deliberately
loose — it screens out only inputs with *zero* connection to the
domain (weather, recipes, jokes), never inputs that merely lack a
resolvable company/concept the way the router's stricter rule does.

### PII (regex-only baseline)

```text
SSN:           \b\d{3}-\d{2}-\d{4}\b
credit card:   \b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b
email:         [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}
phone:         (+1) ddd-ddd-dddd (with separators)
```

Verified not to false-positive on large dollar figures
(`$1,234,567,890`) or SEC accession numbers
(`0000320193-24-000123`) — neither matches the SSN/credit-card shapes
(wrong digit grouping). Presidio remains a documented future upgrade for
broader PII coverage (names, addresses, more locales) — not adopted here
per the explicit user decision above.

### Rate limiting strategy

```python
RATE_LIMITING_STRATEGY = "delegated_to_api_gateway"
```

A named constant recording the decision, not a limiter class. No
in-process request-counting state was added — building one now would
sit in front of a request boundary (FastAPI, Task 4.10) that doesn't
exist yet, and `PROJECT_SPEC.md` already assigns this responsibility to
infrastructure. A future Task 4.10 integrator reads this constant/doc
rather than rediscovering the decision.

## Configuration

New `Settings.input_guard_max_length: int` (`src/config.py`), env var
`INPUT_GUARD_MAX_LENGTH`, default `2000`. Validated at config-load time
(`ConfigError` for a non-integer or non-positive value) — same pattern
as `APP_ENV`/`LOG_LEVEL`/`DEVICE`. Documented in
`project_plan/CONFIGURATION.md`. **`.env.example` was not edited** — as
with Task 4.6, both `Read` and `Bash cat` are denied by the sandbox's
permission rules for any `.env*` path; `2000` is a safe built-in
default, so no user action is required unless they want a different
value.

## Integration boundary

Wired into `src/cli/phase1.py`'s `cmd_answer()` — the one existing
pre-FastAPI production request boundary this project has — as the very
first step, before generator construction (which loads the embedding
model and opens LanceDB) or any `generator.answer()` call. Supersedes
the old inline `isinstance/strip()`-only check that function had
(now covered by `empty_input`/`invalid_type` with proper reason codes).

Proven by test (`tests/test_input_guard_integration.py`), using mocked/
injected callables only, never a real service call:

- 7 rejection categories -> the injected `FakeGenerator.calls` stays
  empty, and (separately) `_construct_generator` — the function that
  would load the embedding model and open LanceDB — is proven never
  called at all for a rejected question.
- 3 accepted questions -> the injected generator is called **exactly
  once**, with the **unchanged** original question string (including
  leading/trailing whitespace — the guard only uses `.strip()`
  internally to test for emptiness, never to rewrite the accepted value).
- A downstream `GenerationError` after acceptance still propagates as a
  normal failure — never silently reinterpreted as a guard rejection.

Five pre-existing `tests/test_phase1_cli.py` tests used a placeholder
question string (`"question"`) that would now be legitimately rejected
as `out_of_scope` (it has no domain signal) — updated to real financial
questions, since those tests are about citation/error-display behavior,
not guard behavior; the `test_empty_question_rejected` assertion
(`"empty" in err.lower()`) still passes unchanged (`reason_code=
"empty_input"` contains "empty").

## Logging

One `log_event()` call per decision via the existing `src.logging_utils`
convention:

```text
event=input_guard_decision allowed=<bool> reason_code=<code or None> input_length=<int or None>
```

Never the raw input text, never the matched keyword/pattern, never an
API key. Verified by test: a rejected SSN/injection payload's actual
content never appears in any emitted log record.

## Tests

```text
tests/test_input_guards.py                 57 tests - every guard category, exact
                                            boundary (1999/2000/2001 chars), determinism
                                            (10x repeat + 9 varied inputs), stable reason
                                            codes, config-error, logging redaction
tests/test_input_guards_static_safety.py     4 tests - AST-verified: no forbidden import
                                            (requests/lancedb/sentence_transformers/torch/
                                            OpenRouter/Ollama/src.index/src.embeddings/
                                            src.retrieval/src.sql/src.nav/duckdb/
                                            protected-TEST loader), no network-shaped call,
                                            no random/time import, src.config imported
                                            lazily only
tests/test_input_guard_integration.py       13 tests - rejection blocks all downstream
                                            work (including embedding/LanceDB via
                                            _construct_generator), acceptance invokes
                                            downstream exactly once unchanged
tests/test_config.py                        +6 tests - INPUT_GUARD_MAX_LENGTH default/
                                            override/validation
tests/test_router_rules.py                  unchanged (classify_intent() behavior
                                            byte-for-byte identical)
tests/test_phase1_cli.py                    14 tests, 5 fixture strings updated (see above)
```

Every rejection/acceptance fixture in this task is original test data —
never a protected-TEST example.

## Regression gates

Verified before and after: Task 4.1 normalization artifact, Task 4.2
chunk artifact, Task 4.3 embedding artifact, Task 4.4 full-corpus vector
index, and Task 4.5 XBRL serving export are all untouched (this task
never opened any of `artifacts/normalized_full/`, `artifacts/chunks_full/`,
`artifacts/embeddings_full/`, `artifacts/indexes_full/`,
`artifacts/xbrl_serving/`). Task 4.6 generation semantics unchanged
except this task's own explicitly-approved input-boundary wiring into
`cmd_answer()` — `src/generation/*` itself is untouched; the only
generation-related test file change is
`tests/test_openrouter_live_smoke.py`'s new opt-in gate (see "Unintended
live API calls" above), which changes when that one live test runs,
never `OpenRouterProvider`'s behavior. Frozen Phase 3 retrieval
decisions, the CRAG threshold, and `src.router.rules.classify_intent()`'s
behavior are all unchanged — `INJECTION_KEYWORDS`/`ADVICE_KEYWORDS` are
new *read-only aliases* of the same private tuples, not new values. No
BM25/RRF/reranker reintroduced, no re-embedding, no generation-provider/
model change. No LLM used anywhere in the guard. Protected TEST:
unopened, **0/3** official runs used.

**Paid API calls during this task, after the incident fix: 0.** Every
regression command run afterward explicitly excluded the live network
test:

```text
python scripts/dev.py doctor                          -> PASS
python scripts/dev.py test --portable                  -> 2062 passed, 37 deselected
python -m pytest -m "not generation_api"               -> 2098 passed, 1 deselected (248.24s)
python -m pytest -m generation_api                     -> 1 skipped (opt-in var unset - verified the fix holds)
```

(Before the fix, 3 real OpenRouter calls occurred - see "Unintended live
API calls" above; none of those runs are the ones tallied here.)

## Files created/modified

```text
src/guards/input.py                          (new)
src/router/rules.py                          (additive: INJECTION_KEYWORDS/ADVICE_KEYWORDS aliases)
src/config.py                                (additive: input_guard_max_length)
src/cli/phase1.py                            (guard wired in as the first step of cmd_answer)
tests/test_input_guards.py                   (new)
tests/test_input_guards_static_safety.py     (new)
tests/test_input_guard_integration.py        (new)
tests/test_config.py                         (additive: 6 new tests)
tests/test_phase1_cli.py                     (5 fixture strings updated)
tests/test_openrouter_live_smoke.py          (incident fix: explicit opt-in gate added)
project_plan/PHASE4_INPUT_GUARDRAILS.md      (this file)
project_plan/CONFIGURATION.md                (updated)
project_plan/REPOSITORY_STRUCTURE.md         (updated)
project_plan/DEVELOPER_COMMANDS.md           (updated: generation_api caveat documented)
project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md  (correction: false no-paid-call claim fixed)
results/phase_4_7_input_guardrails_summary.json  (new, tracked)
Progress.md                                  (updated + Task 4.6 correction)
```

## Known limitations

- PII detection is regex-only (SSN/credit-card/email/phone) — no name/
  address/broader-locale coverage. Presidio remains the documented
  future upgrade if the project later accepts that dependency.
- Scope enforcement is a keyword/pattern deny-list, not a semantic
  classifier — a well-phrased off-topic question using enough financial-
  sounding words could pass, and a legitimate but oddly-phrased question
  using none of the ~50 domain keywords could be rejected. This is the
  accepted tradeoff of "loose deny-list" (favor false negatives over
  false positives).
- Injection/advice detection is deterministic keyword matching (reused
  from Task 3.8), not a learned classifier — known to be evadable by
  sufficiently indirect phrasing; this is a documented limitation, not a
  claimed comprehensive security boundary (per the task's own explicit
  instruction not to overclaim this).
- Rate limiting has no in-process implementation — by design, pending
  the FastAPI/API-Gateway layer (Task 4.10) it is meant to sit in front
  of.
- The guard is wired into the CLI's `cmd_answer()` only — Task 4.10's
  FastAPI service will need its own call to `check_input_with_settings()`
  (or the same wiring pattern) at its own request boundary; this task
  does not build that layer.

## Next roadmap task

Phase 4, Task 4.8 — Context guardrails.
