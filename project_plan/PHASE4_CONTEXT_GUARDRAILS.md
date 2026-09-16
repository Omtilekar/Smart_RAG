# Phase 4 Task 4.8 — Context Guardrails

Implements and validates the production context-guardrail boundary:

```text
accepted user input -> routing/retrieval/structured lookup/tree navigation
-> RETRIEVED/RESOLVED CONTEXT -> CONTEXT GUARDRAIL -> ALLOW / ABSTAIN-SAFE
OUTCOME -> generation
```

Separate from Task 4.7 (answers "was the input acceptable," before
routing) and from a later output-guardrail task (answers "is the
generated answer safe," after generation). This task answers only:
*is the context about to be supplied to generation safe, well-formed,
and provenance-preserving?*

## Authoritative requirement — a scope conflict, in the opposite direction from Task 4.7

The draft task prompt this work started from described an elaborate
production framework (multi-route `ContextGuardResult`, size/token
budgets, scope-leak-vs-predicate rejection, ~7 reason codes, filtering
policy for partially-unsafe evidence). The actual authoritative
`PROJECT_EXECUTION.md` Task 4.8 checklist is materially **narrower**:

```text
### 4.8 Context guardrails
- [x] Treat retrieved content as untrusted data.
- [x] Clearly delimit retrieved evidence.
- [x] Preserve raw evidence for provenance.
- [x] Plant adversarial/instruction-shaped retrieval examples.
- [x] Test that retrieved text cannot override system instructions.
```

Unlike Task 4.7 (where the roadmap was broader than the draft prompt),
here the draft prompt was broader than the roadmap. Followed the
narrower authoritative checklist rather than building the elaborate
framework: no context-size/token-budget guard, no scope-leak-vs-CIK
validator, no content-based injection *rejection* for context (see
"Why no context-injection rejection rule" below), no empty-context
abstention policy — none of these appear in `PROJECT_EXECUTION.md`'s
five bullets, and inventing them would have been exactly the kind of
unauthorized scope expansion this project's own conventions warn
against.

## Implemented contract

The first three checklist items map to runtime code
(`src/guards/context.py`); the last two are testing activities (planted
fixtures + a structural assertion), implemented as tests in
`tests/test_minimal_generation.py`, where the real prompt-construction
integration point already lives — not invented into a new runtime check
with no roadmap basis.

```python
from src.guards.context import ContextGuardDecision, check_dense_context, check_xbrl_context, check_navigation_context, format_evidence_block

@dataclass(frozen=True)
class ContextGuardDecision:
    allowed: bool
    reason_code: str | None   # only "missing_provenance" is implemented
    detail: str | None

check_dense_context(results: list[RetrievalResult]) -> ContextGuardDecision
check_xbrl_context(result: XbrlLookupResult) -> ContextGuardDecision
check_navigation_context(result: SectionNavigationResult) -> ContextGuardDecision
format_evidence_block(*, chunk_id, company, fiscal_year, document_id, text) -> str
```

### Item 1 — Treat retrieved content as untrusted data

Verified structurally: `src/guards/context.py` never calls `eval`/`exec`
(AST-verified), never imports a model/network dependency, and only ever
*wraps* or *inspects* evidence strings — never interprets them as
instructions. `format_evidence_block()`'s docstring and the delimiter
design (below) exist specifically so downstream code (and a human
reading a raw prompt) can never mistake retrieved text for the system's
own instructions.

### Item 2 — Clearly delimit retrieved evidence

`format_evidence_block()` wraps each piece of dense-retrieval evidence
in explicit boundary markers:

```text
<<<BEGIN_RETRIEVED_EVIDENCE chunk_id='...'>>>
Chunk ID: ...
Company: ... | Fiscal Year: ... | Document: ...
<chunk text>
<<<END_RETRIEVED_EVIDENCE>>>
```

Deliberately **not** `[chunk_id: X]`-style square brackets — Task 1.7a's
own documented finding was that this exact shape caused the model to
imitate it as its own (wrong) citation format;
`EVIDENCE_BEGIN_MARKER`/`EVIDENCE_END_MARKER` reuse none of that shape.
Wired into `src/generation/minimal.py`'s `_format_context()` (Task 1.7's
only existing evidence-to-prompt formatter) — replacing its previous
plain (undelimited) block-join, additively: the provenance line itself
(`Chunk ID: ... / Company: ... | Fiscal Year: ... | Document: ...`) is
byte-for-byte the same as before, only wrapped in new markers. Existing
`tests/test_minimal_generation.py` substring assertions (`"Chunk ID:
doc{i}.htm::chunk{i}" in prompt`) still pass unchanged.

This is currently the **only** route with a real generation-prompt
formatter in this codebase — Task 3.10/3.11's structured SQL/XBRL path
and Task 3.12's tree-navigation path answer deterministically without
constructing an LLM prompt at all (per `PROJECT_SPEC.md`: "Hallucinated
financial figures | Numeric questions answered by SQL over XBRL, not
retrieval"). Delimiting is therefore implemented and tested for the
dense route only — an honest scoping, not a claim of formatting those
other two routes.

### Item 3 — Preserve raw evidence for provenance

`check_dense_context()`/`check_xbrl_context()`/`check_navigation_context()`
validate — never fabricate or rewrite — that each route's already-
produced result object carries the identity fields the existing
citation/traceability contract depends on:

```text
dense:      chunk_id, document_id, text (non-empty) - src.generation.citations'
            [chunk_id] contract and _format_context()'s provenance line both need these
xbrl:       (only when outcome="found") adsh, cik, fiscal_year, tag, unit, value
navigation: (only when outcome="found") document_id, item, node_texts (non-empty)
```

For the structured/navigation routes, the other outcome values
(`not_found`/`ambiguous`/`unsupported_tag`/`section_not_found`/
`filing_not_parsed`/`filing_not_found`/`ambiguous_filing`) carry **no
evidence at all** — there is nothing for a context guard to validate or
reject, so these are `allowed=True` (not a policy about empty-context/
abstention handling, which is out of this task's authoritative scope;
generation's own abstention prompt and Task 3.10/3.11/3.12's own
not-found handling already exist independently).

Reason code: **`missing_provenance`** — the only one this task
implements, because it is the only concrete reject-shaped requirement
among the five checklist items. `src.guards.context.REASON_CODES =
("missing_provenance",)`.

### Items 4/5 — Adversarial fixtures + structural non-override test

`tests/test_minimal_generation.py` plants 4 instruction-shaped fixtures
into a retrieved chunk's `text` field (`"Ignore all previous
instructions..."`, a fake `"SYSTEM:"` line, a fake
`"New instructions from the developer:..."`, and a fixture that embeds a
literal fake `EVIDENCE_END_MARKER` trying to "escape" the delimited
block early) and proves, with **no real LLM call**:

- `GenerationRequest.system_prompt` is always exactly the frozen
  `SYSTEM_PROMPT` constant — retrieved text is never concatenated into
  it, so it structurally cannot be "overridden" at request-construction
  time, regardless of what a real model might do with the request
  afterward (testing actual LLM susceptibility would require a real,
  paid call — explicitly out of scope for this task).
- The adversarial text always lands strictly between the BEGIN/END
  markers in `user_prompt`, including the fake-end-marker fixture (the
  *real*, function-appended END marker is always the last one in the
  block).
- A **legitimate** financial-filing sentence using superficially similar
  vocabulary ("internal control **system**... **instructions** of the
  audit committee... did not **ignore**... **assistant** review
  process") is *not* rejected and reaches generation normally — the
  guard is provenance-based, not content/keyword-based, so it has no
  false-positive risk on ordinary filing language.

### Why no context-injection *rejection* rule (an explicit non-decision)

Task 4.7's input guard rejects a user's own question for containing
injection-shaped phrases — that is a reasonable prior for direct human
input. Retrieved *filing* text is different: SEC filings are long,
arbitrary natural-language documents that can legitimately contain
almost any phrase, including ones that superficially resemble
instructions ("management will **ignore** any request that is not
properly documented," "the **system** of internal controls," etc.).
`PROJECT_EXECUTION.md`'s checklist does not ask for context-side
rejection on keyword match — only for delimiting (structural isolation)
and a test that overriding doesn't work — so no such rule was added.
This is the single largest way this task's implementation differs from
the elaborate draft prompt, and is called out explicitly per this
project's "report conflicts, don't silently resolve" convention.

## Integration boundary

Wired into `src/generation/minimal.py`'s `MinimalGenerator.
_answer_with_diagnostics()` — the one place in this codebase that goes
from a retrieval result straight to `provider.generate(...)` — as the
step immediately after retrieval and before prompt construction.  On
`missing_provenance`, returns a fixed abstention-safe
`GenerationResult(answer=CONTEXT_GUARD_ABSTENTION_MESSAGE, citations=[])`
and **`provider_response=None`** — `provider.generate()` is never
called. `MinimalGenerator.answer()`'s public signature is unaffected;
`_answer_with_diagnostics()`'s return type gained `ProviderResponse |
None` (documented), and its two callers
(`scripts/smoke_generation.py`, `scripts/smoke_citation_integrity.py` —
both manual, deliberate live-call tools, never run in automated
regression) were given a small defensive `None`-check so a
(never-expected-in-production) rejection can't crash them.

Only the dense route has a real generation-integration point to wire
into today (see "Item 2" above) — `check_xbrl_context()`/
`check_navigation_context()` are implemented and portably tested as
reusable functions, but there is no existing XBRL/navigation-to-
generation orchestrator in this codebase to wire them into (both routes
answer deterministically without an LLM call). This task does not claim
those two routes are "wired" end-to-end — only that their guard
functions exist, are correct, and are ready for a future integration
point.

Proven by test (no real provider/model/network call anywhere):

- `missing_provenance` dense context -> `FakeProvider.calls == []`
  (`provider.generate()` never invoked) and the result is the fixed
  abstention message.
- Valid dense context -> `FakeProvider.calls` has exactly one entry.
- All 50 pre-existing `tests/test_minimal_generation.py` tests (Task
  1.7/1.7a) still pass unchanged with the new delimited format and
  context-guard step in place.

## Configuration

None introduced — every check in this task is a structural/provenance
validation with no numeric threshold (unlike Task 4.7's `max_length`),
so there was nothing to add to `src.config`/`CONFIGURATION.md`.

## Logging

One `log_event()` call per decision via `src.logging_utils`:

```text
event=context_guard_decision allowed=<bool> reason_code=<code or None> route=<dense|xbrl|navigation> context_items=<int>
```

Never the retrieved text, never a filing excerpt, never provenance
values themselves (only counts/booleans) — verified by test that a
chunk's confidential-sounding text never appears in any emitted log
record.

## Tests

```text
tests/test_context_guards.py                 35 tests - provenance checks for all
                                              3 routes, delimiter formatting (incl.
                                              a fake-end-marker escape attempt),
                                              determinism, reason codes, logging redaction
tests/test_context_guards_static_safety.py     4 tests - AST-verified: no forbidden
                                              import (requests/httpx/lancedb/
                                              sentence-transformers/torch/duckdb/
                                              OpenRouter/Ollama/src.embeddings/
                                              src.index/protected-TEST loader), no
                                              network-shaped call, no eval/exec,
                                              no random/time import
tests/test_minimal_generation.py             +13 tests (50 total, 37 pre-existing
                                              unchanged) - 4 adversarial fixtures x 2
                                              structural assertions, a legitimate-
                                              vocabulary negative fixture, delimiter-
                                              count check, missing-provenance
                                              integration-boundary proof (provider
                                              never invoked / invoked exactly once)
```

Every adversarial fixture in this task is original test data — never a
protected-TEST example.

## Regression gates

Task 4.1–4.5 artifacts untouched (never opened by this task). Task 4.6
generation semantics unchanged except this task's own explicitly-
approved context-boundary wiring into `MinimalGenerator` — the frozen
`SYSTEM_PROMPT`, citation contract, and OpenRouter/Ollama provider code
are all byte-for-byte unchanged; only `_format_context()`'s output
formatting and the new pre-generation guard step changed. Task 4.7
input-guard semantics (`src/guards/input.py`) completely untouched.
Frozen Phase 3 retrieval/routing decisions, the CRAG threshold
(`0.5531`), dense-only selection, and the structured SQL/navigation
routes are all unchanged — this task only validates their already-
produced result objects, never redesigns retrieval/routing. No BM25/RRF/
reranker reintroduced, no re-embedding, no provider/model change.

**Paid API calls during Task 4.8: 0.** No `generation_api`-marked test
was run or opted into (`RUN_LIVE_GENERATION_API_TEST` was never set).
Protected TEST: unopened, **0/3** official runs used.

```text
python scripts/dev.py doctor                     -> PASS
python scripts/dev.py test --portable             -> 2114 passed, 37 deselected
python -m pytest -m "not generation_api"          -> 2150 passed, 1 deselected (230.29s)
```

## Files created/modified

```text
src/guards/context.py                              (new)
src/generation/minimal.py                          (delimited formatting + context-guard step)
scripts/smoke_generation.py                        (defensive None-check, manual tool only)
scripts/smoke_citation_integrity.py                (defensive None-check, manual tool only)
tests/test_context_guards.py                       (new)
tests/test_context_guards_static_safety.py         (new)
tests/test_minimal_generation.py                   (+13 tests)
project_plan/PHASE4_CONTEXT_GUARDRAILS.md          (this file)
project_plan/REPOSITORY_STRUCTURE.md               (updated)
results/phase_4_8_context_guardrails_summary.json  (new, tracked)
Progress.md                                        (updated)
```

## Known limitations

- No context-size/token-budget enforcement — not in the authoritative
  checklist; `PROJECT_EXECUTION.md` names no such requirement or
  existing frozen budget to reuse.
- No scope-leak-vs-predicate validation (e.g. "does this chunk's CIK
  match the question's resolved CIK") — not in the authoritative
  checklist; Task 3.9's metadata pre-filter already constrains retrieval
  scope upstream, and this task does not redesign retrieval.
- No content-based context-injection *rejection* rule — a deliberate
  non-decision (see "Why no context-injection rejection rule" above),
  not an oversight.
- Delimiting/integration is proven end-to-end for the dense route only
  — the XBRL/navigation guard functions are portably tested in
  isolation but have no existing orchestrator to wire into yet.
- The adversarial-fixture tests prove structural request-construction
  isolation (retrieved text can't reach `system_prompt`), not that a
  real LLM would resist an injected instruction if a live call were
  made — that would require a paid call, explicitly disallowed for this
  task.

## Next roadmap task

Phase 4, Task 4.9 — Output guardrails.
