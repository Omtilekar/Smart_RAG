# Phase 4 Task 4.9 — Output Guardrails

Implements and validates the production output-guardrail boundary:

```text
provider.generate(...) -> ProviderResponse/generated answer -> OUTPUT
GUARD -> public GenerationResult / safe fallback
```

Separate from Task 4.7 (was the input acceptable, before routing) and
Task 4.8 (was retrieved context structurally safe/provenance-complete,
before generation). This task answers only: *can this generated answer
be released to the user under the project's frozen output contract?*

## Authoritative requirement

`PROJECT_EXECUTION.md`'s Task 4.9 checklist (6 items):

```text
- [x] Verify cited chunk IDs exist.
- [x] Verify citations refer to provided evidence.
- [x] Add groundedness checks.
- [x] Validate numeric provenance for structured answers.
- [x] Refuse unsupported financial advice.
- [x] Avoid unsupported claims.
```

All 6 map onto 4 deterministic checks (documented collapsing, not silent
scope changes):

| Roadmap item(s) | Implemented as |
|---|---|
| 1. Verify cited chunk IDs exist<br>2. Verify citations refer to provided evidence | **One** check: every citation must be among the chunk_ids actually *supplied* to this generation call. Never checked against "exists somewhere in the global corpus" — this project's own explicit precedent (Task 1.8/4.8) is that only supplied-evidence membership matters. |
| 3. Add groundedness checks<br>6. Avoid unsupported claims | The same citation-validity check, applied to whatever citations *are present*. A zero-citation answer is never blocked for "missing citation" — see "Why no missing-citation reason code" below. |
| 4. Validate numeric provenance for structured answers | Task 4.8's `check_xbrl_context()`, re-exported **unchanged** as `check_structured_numeric_output` — there is no separate generation step for the structured/XBRL route (Task 4.8 already established this), so the same provenance check already is the release gate. |
| 5. Refuse unsupported financial advice | Reuses `src.router.rules.ADVICE_KEYWORDS` (Task 3.8/4.7's frozen list) against the generated answer text — no new keyword set. |

## Why no "missing_citation" reason code (resolved from existing precedent, not invented)

The draft prompt flagged "whether every non-abstaining answer must
contain a citation" as a choice that must not be guessed. This resolves
directly from two things already true in this repository, not a new
decision:

1. This very task's own "Abstention Semantics" section: *"do not
   require a citation for a legitimate abstention unless the roadmap
   explicitly says otherwise"* — `PROJECT_EXECUTION.md`'s checklist does
   not say otherwise (it never mentions abstention).
2. `src.eval.citation_integrity.evaluate_citation_integrity()` (Task
   1.8) already flags a zero-citation answer as `missing_required_
   citation` **only** using a caller-supplied `abstention_expected`
   boolean — explicitly documented as *"never inferred here from the
   answer text."* A live production output guard has no ground-truth
   "was this actually unanswerable" signal to supply. Reusing that
   function's logic honestly means: without ground truth, this check
   cannot be run at all — not that it should be approximated with an
   invented phrase-matching heuristic (the kind of heuristic
   `scripts/smoke_generation.py` already uses for its own informational
   labeling only, explicitly captioned "not a claim that this reliably
   detects every abstention phrasing").

So "groundedness" here means exactly: *every citation that is present
must be valid* — not *every answer must have a citation*. This is
documented as a real, intentional limitation, not silently downgraded.

## Why no content-based rejection beyond the reused keyword list

Advice detection reuses `ADVICE_KEYWORDS` verbatim rather than a new,
output-specific list ("reuse the existing deterministic helpers where
semantically appropriate"). This has a real, measured gap: the list's
phrases are first-person ("should i buy...") because Task 3.8 designed
them to catch a *user's own question*. A model's advice-giving output is
more naturally second-person ("you should buy...") or a recommendation
("I recommend..."), which the reused list does not match. Verified
directly and kept as an honest, visible test
(`test_known_limitation_second_person_advice_phrasing_not_caught`) rather
than silently expanding the keyword list (which the roadmap does not
authorize) or hiding the gap.

## Failure policy: reject the whole answer (reused precedent, not invented)

Any citation problem (unknown citation, malformed marker) fails the
**entire** answer — never a partial strip-and-keep. This mirrors
`evaluate_citation_integrity()`'s own `status = "PASS" if not reasons
else "FAIL"` semantics (Task 1.8), applied here as a live release gate
instead of an offline evaluation, rather than inventing a new
redact-vs-reject policy from nothing.

## Implemented contract

```python
from src.guards.output import OutputGuardDecision, check_dense_output, check_structured_numeric_output

@dataclass(frozen=True)
class OutputGuardDecision:
    allowed: bool
    reason_code: str | None   # "malformed_citation" | "unknown_citation" | "unsupported_advice"
    detail: str | None

check_dense_output(answer_text: str, citations: list[str], *, supplied_chunk_ids: set[str]) -> OutputGuardDecision
check_structured_numeric_output = check_xbrl_context  # Task 4.8's function, re-exported verbatim
```

Order (first violation wins, same convention as Tasks 4.7/4.8):
`malformed_citation -> unknown_citation -> unsupported_advice`.
`detect_citation_attempts()` (Task 1.8's own malformed-marker detector,
`src.eval.citation_integrity`) is imported and reused directly — not
re-derived — so fullwidth brackets, truncated chunk IDs, and the
`[chunk_id: X]` context-label-imitation form are all classified exactly
as Task 1.7a/1.8 already established (the last one specifically
resolves to `unknown_citation`, per Task 1.8's own documented finding
that it is strict-parser-valid but never a real chunk_id — verified by
test, not assumed).

## Integration boundary

Wired into `src/generation/minimal.py`'s `MinimalGenerator.
_answer_with_diagnostics()`, immediately after `provider.generate(...)`
and citation parsing, before the public `GenerationResult` is built. On
rejection: `GenerationResult(answer=OUTPUT_GUARD_ABSTENTION_MESSAGE,
citations=[])` is returned publicly, but **`provider_response` (the real
`ProviderResponse`, with its true latency/token counts) is still
returned to the caller of `_answer_with_diagnostics()`** — the provider
really was called, so that diagnostic data remains valid and is not
destroyed; only the public answer contract is sanitized ("Preserve
Diagnostic Separation": internal diagnostics vs. public answer contract
are handled differently, matching the least-invasive existing-precedent
choice rather than a new invented policy).

Only the dense route has a real generation-integration point (same
honest scoping as Task 4.8) — `check_structured_numeric_output()` is
implemented and portably tested but has no existing XBRL/navigation
orchestrator to wire into (both routes still answer deterministically
without an LLM call).

Proven by test (no real provider/model/network call anywhere):

- Unknown-citation, malformed-citation, and unsupported-advice provider
  outputs are all blocked — the public `GenerationResult` never contains
  the raw candidate text — while `provider.calls` still shows exactly
  one invocation and `provider_response` remains available with its real
  `ProviderResponse.text` in diagnostics.
- A validly-cited answer and a legitimate zero-citation abstention both
  pass through **byte-for-byte unchanged**.
- All 50 pre-existing `tests/test_minimal_generation.py` tests (Task
  1.7/1.7a/4.8) still pass unchanged with the new output-guard step in
  place.

## Logging

One `log_event()` call per decision via `src.logging_utils`:

```text
event=output_guard_decision allowed=<bool> reason_code=<code or None> citation_count=<int> unknown_citation_count=<int>
```

Never the generated answer text, never the raw prompt, never provider
metadata beyond the decision fields — verified by test that a
confidential-looking blocked answer never appears in any emitted log
record.

## Configuration

None introduced — every check is structural/keyword-based with no
numeric threshold, so there was nothing to add to `src.config`/
`CONFIGURATION.md` (matching the roadmap's own "prefer no new config
file merely for symmetry" guidance).

## Tests

```text
tests/test_output_guards.py                 30 tests - citation validity (valid/
                                             unknown/malformed/context-label-imitation),
                                             advice detection (incl. the documented
                                             second-person gap), zero-citation
                                             abstention allowed, structured-route
                                             re-export identity, determinism, reason
                                             codes, logging redaction
tests/test_output_guards_static_safety.py     4 tests - AST-verified: no forbidden
                                             import, no network-shaped call, no
                                             eval/exec, no random/time import
tests/test_minimal_generation.py            +6 tests (56 total, 50 pre-existing
                                             unchanged) - blocked-output integration
                                             proofs (provider called once, diagnostics
                                             preserved, public result sanitized),
                                             valid/abstention pass-through unchanged
```

## Regression gates

Task 4.1–4.5 artifacts untouched. Task 4.6 provider/model contract
unchanged except this task's own explicitly-approved output-boundary
wiring into `MinimalGenerator` — `OpenRouterProvider`/`OllamaProvider`
code untouched. Task 4.7 (`src/guards/input.py`) and Task 4.8
(`src/guards/context.py`, only reused/re-exported, never modified)
completely untouched. Frozen Phase 3 retrieval/routing decisions, the
CRAG threshold (`0.5531`), dense-only selection unchanged. No BM25/RRF/
reranker reintroduced, no re-embedding, no provider/model change.

**Paid API calls during Task 4.9: 0.** `RUN_LIVE_GENERATION_API_TEST`
was never set; `scripts/smoke_generation.py` was not run.

```text
python scripts/dev.py doctor                     -> PASS
python scripts/dev.py test --portable             -> 2154 passed, 37 deselected
python -m pytest -m "not generation_api"          -> 2190 passed, 1 deselected (230.79s)
```

Protected TEST: unopened, **0/3** official runs used.

## Files created/modified

```text
src/guards/output.py                               (new)
src/generation/minimal.py                          (output-guard step wired in)
tests/test_output_guards.py                        (new)
tests/test_output_guards_static_safety.py          (new)
tests/test_minimal_generation.py                   (+6 tests)
project_plan/PHASE4_OUTPUT_GUARDRAILS.md           (this file)
project_plan/REPOSITORY_STRUCTURE.md               (updated)
results/phase_4_9_output_guardrails_summary.json   (new, tracked)
Progress.md                                        (updated)
```

## Known limitations

- No "missing citation" / groundedness-on-absence check — a deliberate,
  documented non-decision (see above), not an oversight.
- Advice detection reuses a keyword list designed for first-person user
  questions; second-person/recommendation-phrased model output
  ("you should buy...") is not caught — a real, tested, documented gap.
- Citation validity check reuses `detect_citation_attempts()`'s existing
  malformed-marker classification, so it inherits any of that function's
  own known scope (ASCII/fullwidth brackets containing chunk-shaped
  content only — see `src/eval/citation_integrity.py`).
- Output guard integration is proven for the dense route only —
  `check_structured_numeric_output()` is a correct, tested function with
  no existing orchestrator to wire into for the XBRL/navigation routes.
- This module does not and cannot verify that a cited claim is
  *factually* supported by the cited text (semantic entailment) —
  structural citation validity is a proxy, not a factual-correctness
  guarantee, and an LLM judge for that was explicitly out of scope.

## Next roadmap task

Phase 4, Task 4.10 — FastAPI service.
