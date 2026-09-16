# Task 4.8 — Context Guardrails

## Objective

Implement and validate the production **context-guardrail boundary** for the
Production RAG system.

Task 4.7 established deterministic input validation before any expensive
downstream work. Task 4.8 now protects the next boundary:

```text
accepted user input
    ->
routing / retrieval / structured lookup / tree navigation
    ->
RETRIEVED / RESOLVED CONTEXT
    ->
CONTEXT GUARDRAIL
    ->
ALLOW / REJECT / ABSTAIN-SAFE OUTCOME
    ->
generation
```

This task is deliberately limited to context guardrails.

Do NOT implement output guardrails.
Do NOT build the FastAPI serving layer.
Do NOT deploy infrastructure.
Do NOT reopen Phase 3 retrieval/model/routing decisions.
Do NOT re-normalize, re-chunk, re-embed, or rebuild production indexes.
Do NOT make paid LLM/API calls.
Do NOT open protected TEST.

The authoritative definition is the exact Task 4.8 section in:

`project_plan/PROJECT_EXECUTION.md`

Before coding, read that section directly.

If the authoritative Task 4.8 checklist materially differs from this prompt,
follow `PROJECT_EXECUTION.md` and report the difference explicitly rather
than silently reconciling it.

---

# Repository

Project root:

`C:\Om\Codes\RAG`

Before modifying anything, inspect at minimum:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PROJECT_SPEC.md`
- `project_plan/GIT_CONVENTIONS.md`
- `project_plan/TESTING.md`
- `project_plan/CONFIGURATION.md`
- `project_plan/LOGGING.md`
- `project_plan/REPOSITORY_STRUCTURE.md`
- `project_plan/PHASE4_INPUT_GUARDRAILS.md`
- `project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md`
- current `src/guards/`
- current router/orchestrator/request-boundary code
- current retrieval result contracts
- current SQL/XBRL result contracts
- current tree-navigation result contracts
- current generation prompt/context formatting
- current citation/provenance utilities
- `scripts/dev.py`
- `pytest.ini`

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not assume repository state from this prompt alone.

---

# Hard Precondition — Task 4.7

Task 4.8 may begin only if Task 4.7 is actually COMPLETE.

Current Progress.md records:

```text
Phase 4 — Make It Real
  4.1 Full-corpus normalization               — COMPLETE
  4.2 Full-corpus chunking                    — COMPLETE
  4.3 Full-corpus embedding                   — COMPLETE
  4.4 Full-corpus vector index                — COMPLETE
  4.5 XBRL serving representation             — COMPLETE
  4.6 Generation production interface         — COMPLETE
  4.7 Input guardrails                        — COMPLETE

Next: 4.8 Context guardrails
```

Verify the real Task 4.7 implementation and tests before proceeding.

At minimum confirm:

- `src/guards/input.py` exists and matches its documented contract
- input guard executes before downstream work
- `INPUT_GUARD_MAX_LENGTH` behavior is tested
- rejection reason codes are stable
- no network/model/LLM call exists in the input guard
- the explicit live-generation opt-in protection is present
- protected TEST remains unopened

If Task 4.7 is incomplete or the repository materially contradicts
Progress.md:

STOP.

Do not repair Task 4.7 inside Task 4.8 unless a tiny documentation correction
is required to state an already-observed fact accurately.

---

# Documentation Consistency Preflight

Before Task 4.8 implementation, inspect the Task 4.6 and Task 4.7 entries in
`Progress.md`.

There was a documented incident in which **3 unintended live OpenRouter API
calls** occurred across the Task 4.6/4.7 regression work because a
`generation_api` test ran while credentials were available.

The correction text is already present, but ensure there is no remaining
stale sentence elsewhere in the Task 4.6 entry claiming that no paid/live API
call occurred.

If such a stale sentence remains, correct only that factual contradiction
before Task 4.8 work.

Do NOT rewrite Task 4.6's technical result.

Do NOT estimate billing.

---

# Frozen Task 4.7 Input-Guard Decisions

Do not reopen these during Task 4.8:

```text
max input length:
  2,000 characters

PII:
  regex-only for now
  supported patterns: SSN / credit-card-like / email / phone
  Presidio documented as a later production-hardening option

scope enforcement:
  loose deny-list / domain-signal strategy

rate limiting:
  strategy documented only
  implementation deferred to infrastructure/API layer

input guard order:
  invalid_type
  empty_input
  input_too_long
  disallowed_control_character
  prompt_injection_detected
  advice_request_detected
  pii_detected
  out_of_scope
```

Task 4.8 must not modify these semantics merely to simplify context handling.

---

# Frozen Retrieval / Routing / Generation Decisions

Treat the selected Phase 3/4 stack as immutable unless
`PROJECT_EXECUTION.md` explicitly says otherwise.

Relevant frozen decisions:

```text
chunking:
  fixed 256 content tokens
  overlap 0

embedding:
  Qwen/Qwen3-Embedding-0.6B
  revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
  dimension 1024
  normalized vectors

dense retrieval:
  selected

RRF hybrid:
  NOT selected

cross-encoder reranking:
  NOT selected

metadata prefilter:
  selected

CRAG threshold:
  0.5531

structured SQL/XBRL route:
  selected / frozen

tree-navigation route:
  selected / frozen

generation:
  provider-neutral interface
  production config:
    GENERATION_PROVIDER=openrouter
    GENERATION_MODEL=openai/gpt-oss-20b
  local/offline experiment provider:
    Ollama
```

Task 4.8 must protect the context boundary without changing how these
components scientifically rank, route, or retrieve.

---

# Protected TEST

Protected TEST remains sealed.

Official usage before Task 4.8:

`0 / 3`

Rules:

- Do not open protected TEST.
- Do not inspect TEST questions.
- Do not run TEST.
- Do not use TEST examples to tune context rules.
- Do not consume an official TEST run.

At completion explicitly report:

`official TEST usage: 0/3`

If any proposed validation requires TEST access:

STOP.

---

# Zero Paid / External Generation Calls

Task 4.8 must make **zero paid generation API calls**.

The Task 4.7 incident established that merely checking for credentials is not
sufficient protection.

Therefore:

- do not invoke OpenRouter,
- do not run a live generation test,
- do not set `RUN_LIVE_GENERATION_API_TEST=1`,
- do not run a regression command that can trigger `generation_api`,
- use deterministic stubs/mocks/fakes for generation-boundary tests,
- explicitly exclude `generation_api` from any non-portable regression
  command.

Preferred regression commands:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

If repository policy has since introduced a safer explicit live-test command,
inspect it, but Task 4.8 still must not opt into it.

Record:

```text
Task 4.8 paid API calls: 0
```

Do not state that the entire project/session historically had zero calls.

---

# Core Design Principle

Context guardrails answer:

```text
Is the context that is about to be supplied to generation safe,
well-formed, in-scope, provenance-preserving, and acceptable under the
frozen retrieval/routing contract?
```

They do NOT answer:

```text
Was the original user question acceptable?
```

Task 4.7 owns that.

They also do NOT answer:

```text
Is the generated answer safe/correct?
```

That belongs to output guardrails / later validation.

Keep these three boundaries separate:

```text
INPUT GUARD
    before routing/retrieval

CONTEXT GUARD
    after evidence acquisition, before generation

OUTPUT GUARD
    after generation
```

---

# First Implementation Step — Resolve the Exact Task 4.8 Contract

Before writing code, extract the exact Task 4.8 checklist from
`PROJECT_EXECUTION.md`.

Write down internally:

```text
Task 4.8 exact title:
Required context checks:
Required behavior on guard failure:
Required result/reason-code schema:
Required integration point:
Required provenance checks:
Required injection handling:
Required size/token limits:
Required tests:
Required logs:
Required config:
Explicit non-goals:
```

Do not invent missing policy.

If the roadmap requires a threshold but does not define its value and no
existing frozen configuration defines it:

STOP AND ASK.

Examples of values that must not be invented:

- maximum context characters
- maximum context tokens
- maximum number of retrieved chunks
- minimum evidence count
- allowed source types
- allowed metadata/provenance fields
- truncation strategy
- deduplication policy
- behavior when one of several chunks is unsafe
- behavior when structured results lack provenance
- whether context should be rejected, filtered, or cause abstention

---

# Context Types

The project has multiple production evidence paths.

Task 4.8 must inspect the real contracts before assuming one uniform context
shape.

Potential evidence families include:

```text
dense retrieval:
  chunk_id
  document_id
  text
  CIK
  fiscal_year
  source
  provenance metadata

structured SQL/XBRL:
  deterministic fact/value rows
  tag
  unit
  fiscal year / period
  CIK
  accession / filing provenance where available

tree navigation:
  resolved filing
  resolved section
  exact source/provenance
  scoped text / table evidence
```

If Task 4.8 applies to more than one route, define a narrow normalized
context-guard input contract without erasing route-specific provenance.

Do not convert deterministic structured facts into free-form text merely to
make the guard implementation easier unless the existing generation boundary
already does so.

---

# Recommended Guard Result Contract

If no context-guard contract already exists, prefer a small deterministic
result shape analogous to Task 4.7, for example:

```python
ContextGuardDecision(
    allowed: bool,
    reason_code: str | None,
    detail: str | None,
)
```

or, if the authoritative roadmap requires guarded context to be returned:

```python
ContextGuardResult(
    allowed: bool,
    context: ...,
    reason_code: str | None,
    detail: str | None,
)
```

Exact names should follow repository style.

Do not invent a second incompatible guard framework if `src/guards/` already
defines reusable types.

---

# Stable Reason Codes

Every rejection / abstention-triggering guard outcome must expose a stable,
machine-readable reason code.

Use only categories required by the authoritative Task 4.8 contract.

Possible examples — NOT pre-approved policy:

```text
empty_context
context_too_large
context_injection_detected
invalid_context_shape
missing_provenance
scope_leak_detected
unsupported_source
```

Do not implement a reason code solely because it appears in this prompt.

The API layer must eventually be able to act on reason codes without parsing
human-readable text.

---

# Context Is Untrusted Data

Treat retrieved/document text as data, not instructions.

A retrieved SEC filing can contain phrases that resemble instructions,
templates, disclaimers, or malicious injected content.

The context guard must never execute or obey instruction-shaped content.

If the roadmap requires context prompt-injection detection:

- use deterministic rules,
- never call an LLM classifier,
- reuse already-frozen injection rules where semantically appropriate
  instead of maintaining divergent copies,
- preserve evidence as data,
- document false-positive/false-negative limitations,
- test both malicious/instruction-like fixtures and legitimate SEC text.

Do not assume every occurrence of words such as `ignore`, `system`,
`instruction`, `assistant`, or `prompt` is malicious.

Financial filings can legitimately contain arbitrary natural language.

---

# Provenance Integrity

Context that reaches generation must retain the provenance required by the
existing citation contract.

At minimum, inspect the real generation formatter and route contracts to
determine what identity fields are required.

Do not silently drop:

- chunk IDs,
- document IDs,
- filing identity,
- CIK,
- fiscal year / period,
- section identity,
- XBRL tag/unit provenance,
- source route/type,

when those fields are required by the existing downstream citation or
traceability path.

If required provenance is missing or inconsistent, fail deterministically
according to the authoritative Task 4.8 contract.

Do not fabricate provenance.

---

# Scope-Leak Prevention

Task 3.x tree navigation and metadata-prefilter work already established
scope constraints.

Task 4.8 must not broaden them.

If the context guard is required to validate request/context scope, test that
evidence cannot silently leak outside an already-resolved predicate such as:

- wrong CIK,
- wrong fiscal year,
- wrong filing,
- wrong section,
- wrong structured-fact identity.

Do not implement new retrieval filters here.

The guard verifies the evidence it was given; it does not redesign retrieval.

---

# Context Size / Budget

If `PROJECT_EXECUTION.md` requires a context-size/token-budget guard, derive
its exact policy from existing frozen generation/prompt configuration.

Do not choose an arbitrary context limit.

If there is an existing top-k/context-budget contract, reuse it.

If context exceeds the allowed budget, follow the authoritative behavior:

- reject,
- abstain,
- deterministically truncate,
- or another specified action.

Do NOT silently introduce truncation if the policy has not already approved
it, because truncation changes evidence supplied to generation.

Any deterministic truncation rule must be tested for:

- stable ordering,
- provenance preservation,
- no mid-record corruption,
- no hidden preference for later/earlier evidence unless explicitly defined.

---

# Empty / Missing Context

The project already has abstention behavior at generation time.

Task 4.8 should make empty/missing context handling explicit if required by
the roadmap.

Do not let a no-evidence request reach a grounded generator as if valid
context existed.

Do not fabricate placeholder evidence.

If the correct behavior is an abstention-safe outcome, represent it clearly
and test it without making an LLM call.

---

# Context Mutation Policy

Default principle:

**validate context, do not rewrite evidence.**

Unless Task 4.8 explicitly authorizes sanitization/transformation:

- do not paraphrase retrieved text,
- do not remove sentences,
- do not “repair” evidence,
- do not rewrite XBRL facts,
- do not rewrite citations,
- do not alter chunk IDs,
- do not reorder evidence,
- do not redact arbitrary filing text.

If a context element is unacceptable, follow the defined guard outcome.

If the roadmap explicitly allows filtering unsafe elements while retaining
safe ones, implement that deterministically and test exact element
accounting.

---

# Integration Boundary

The context guard must execute:

```text
AFTER evidence acquisition
BEFORE provider.generate(...)
```

Prove this with dependency-injected tests.

For rejected/blocked context:

- generation provider must not be constructed/called if construction can be
  deferred,
- `provider.generate()` invocation count must be zero,
- no OpenRouter/Ollama call occurs.

For allowed context:

- generator receives the same approved evidence/provenance unless an
  explicitly-frozen normalization rule exists,
- generation boundary is invoked exactly once in synthetic tests.

Do not run a real generation provider for integration proof.

---

# Route Coverage

Inspect the authoritative Task 4.8 scope.

If context guardrails are required across multiple production routes, cover
each real route with synthetic fixtures:

```text
dense evidence
structured SQL/XBRL evidence
tree-navigation evidence
```

If the roadmap only requires one route at this stage, do not broaden scope
without reason.

Do not claim cross-route protection unless each route is actually wired and
tested.

---

# Logging

Use `src.logging_utils`.

Prefer structured events such as:

```text
event=context_guard_decision
allowed=true/false
reason_code=...
context_items=...
context_chars=...
route=...
```

Do not log:

- full retrieved chunks,
- full filing text,
- full prompts,
- embeddings,
- API keys,
- authorization headers,
- generated answers,
- PII discovered in context unless the project explicitly requires a safe
  redacted diagnostic.

Guard logs should provide operational observability without duplicating
sensitive/untrusted evidence.

---

# Configuration

If Task 4.8 introduces configuration, integrate through the existing typed
`src.config` boundary.

Requirements:

- no scattered environment reads,
- no invented threshold,
- validation at load time,
- documentation in `project_plan/CONFIGURATION.md`,
- `.env.example` updated only if repository permissions permit and only with
  non-secret values.

If `.env.example` is still blocked by sandbox permissions, report it rather
than attempting a workaround.

---

# Error Policy

Separate:

```text
expected guard decision
  -> normal result, no traceback

invalid guard configuration
  -> clear early configuration error

malformed context from internal code
  -> deterministic guard rejection or explicit contract error according to
     the authoritative design

unexpected internal bug
  -> do not silently convert into "context rejected"
```

Do not hide pipeline bugs as user-facing safety refusals.

---

# Determinism

For identical context + identical configuration, the decision must be
identical.

No random sampling.
No time-based behavior.
No external network call.
No LLM.
No embedding model.
No generation model.

Add determinism tests for every implemented check.

---

# Portable Tests

Add portable tests for every actual Task 4.8 rule.

At minimum, where applicable:

- valid dense context allowed
- valid structured/XBRL context allowed
- valid tree-navigation context allowed
- empty context handling
- malformed context handling
- missing required provenance
- inconsistent provenance
- context size boundary below / at / above limit
- context injection positive fixtures
- context-injection legitimate-financial-text negative fixtures
- scope-leak rejection
- unsupported context/source type
- stable reason codes
- deterministic repeated decisions
- evidence remains unchanged on allow
- generation callable is never invoked on rejection
- generation callable invoked exactly once on allow
- logging does not expose raw evidence
- config validation
- no forbidden external dependencies

Only include categories actually required by the authoritative roadmap.

---

# Static Safety Tests

Where useful, add AST/source-inspection tests proving the context guard
module does not import/call:

- OpenRouter
- Ollama
- `requests`
- `httpx`
- sentence-transformers
- torch
- LanceDB query APIs
- protected TEST loaders

The guard should consume already-retrieved context, not fetch new evidence or
call models itself.

---

# No Expensive Full-Corpus Retrieval in Unit Tests

Task 4.4 measured local exact-flat full-corpus retrieval in the tens-of-
seconds range on the development machine.

Do NOT make portable context-guard tests query the 10.49M-row index.

Use tiny synthetic context objects.

If the authoritative task requires one real wiring smoke test, keep it
minimal and clearly marked `local_data`, but do not repeatedly perform
full-corpus searches merely to test guard logic.

---

# Results Artifact

Write a small tracked summary following repository naming conventions,
likely:

`results/phase_4_8_context_guardrails_summary.json`

Use the actual repository convention if different.

Record at minimum:

- task
- status
- authoritative guard requirements
- implemented context types
- reason codes
- configured thresholds, if any
- integration point
- deterministic behavior
- portable test result
- non-generation regression result
- paid API calls = 0 for Task 4.8
- protected TEST usage = 0/3
- files modified
- known limitations

Do not include raw retrieved context, prompt text, secrets, or malicious
payload bodies unnecessarily.

---

# Documentation

Create/update task documentation consistent with existing Phase 4 docs,
likely:

`project_plan/PHASE4_CONTEXT_GUARDRAILS.md`

Document:

- exact Task 4.8 roadmap checklist
- context-guard contract
- supported context/evidence shapes
- guard order
- reason codes
- provenance requirements
- context-injection handling
- size/budget policy
- scope-leak policy
- integration boundary
- logging
- tests
- known limitations
- separation from Task 4.7 input guards
- separation from later output guards

Update `project_plan/REPOSITORY_STRUCTURE.md`,
`project_plan/CONFIGURATION.md`, and other docs only if the actual
implementation changes them.

---

# Progress.md

Only after implementation and validation pass, append a detailed Task 4.8
entry matching the established style.

Record:

- objective
- exact authoritative Task 4.8 requirements
- implementation
- supported context routes
- guard order
- stable reason codes
- configuration/thresholds
- provenance checks
- injection handling
- scope-leak handling
- integration boundary
- test counts
- regression commands
- paid API calls during Task 4.8 = 0
- protected TEST usage = 0/3
- known limitations
- Git commit
- final Task 4.8 status
- exact next roadmap task from `PROJECT_EXECUTION.md`

Do not guess the next task.

Do not start it.

---

# Regression Gates

Before and after Task 4.8 verify:

- Task 4.1 normalization artifact unchanged
- Task 4.2 chunk artifact unchanged
- Task 4.3 embedding artifact unchanged
- Task 4.4 vector index unchanged
- Task 4.5 XBRL serving export unchanged
- Task 4.6 provider/generation semantics unchanged except explicit context
  boundary wiring
- Task 4.7 input-guard semantics unchanged
- frozen Phase 3 retrieval/routing decisions unchanged
- CRAG threshold remains `0.5531`
- no BM25/RRF reintroduced
- no reranker reintroduced
- no re-embedding
- no provider/model selection change
- no paid API call
- protected TEST remains unopened

Run:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Do not run `generation_api`.

If another optional external-service marker exists, exclude it when it can
make a network call or incur cost unless the task explicitly requires that
service.

Report skips/deselections accurately.

---

# Git Safety

Follow `project_plan/GIT_CONVENTIONS.md`.

Before committing:

```text
git status
git diff
git diff --staged
```

Verify:

- no `data/` content staged
- no `artifacts/` content staged
- no model weights staged
- no `.env` staged
- no API key staged
- no raw context dump staged
- no large generated outputs staged
- tracked results/docs/tests are small

Commit Task 4.8 as one coherent commit only after acceptance gates pass.

Suggested commit message:

`Add production context guardrails`

Do not push unless current user/repository policy explicitly authorizes it.

---

# Stop Conditions

STOP and report instead of guessing if:

1. Task 4.7 is not actually complete.
2. `PROJECT_EXECUTION.md` defines Task 4.8 materially differently.
3. A context limit/threshold is required but undefined.
4. The roadmap requires a policy choice between reject/filter/truncate/
   abstain and no approved choice exists.
5. Required provenance semantics are ambiguous.
6. A new external moderation/model service would be required.
7. A paid API call would be required.
8. A real generation call appears necessary for validation.
9. Context guarding would require prematurely implementing output guards.
10. Context guarding would require FastAPI/deployment work.
11. An upstream frozen artifact would need to be modified.
12. Protected TEST access would be required.
13. Regression tests fail for an unexplained reason.
14. Git safety cannot be established.

When stopping, report:

```text
TASK:
STEP:
EXPECTED:
OBSERVED:
WHY BLOCKING:
SAFE STATE:
DECISION NEEDED:
```

Do not mark Task 4.8 complete.

---

# Acceptance Criteria

Task 4.8 is COMPLETE only when the authoritative roadmap criteria pass and,
at minimum:

- context guardrail exists as a reusable production module
- guard executes after evidence acquisition and before generation
- malformed/rejected context cannot reach the generation provider
- allowed evidence retains required provenance
- no provenance is fabricated
- no unapproved evidence rewriting occurs
- every implemented rejection has a stable reason code
- thresholds come from an explicit frozen source, not an invented value
- context-injection handling is deterministic if required
- scope-leak validation is enforced if required
- behavior is deterministic
- no model/LLM/network dependency exists inside the context guard
- portable tests cover every implemented guard category
- integration tests prove provider invocation is zero on rejection
- regression suites pass with `generation_api` excluded
- paid API calls during Task 4.8 = 0
- Tasks 4.1–4.7 remain intact
- protected TEST remains unopened at 0/3
- documentation and result summary are written
- Progress.md is updated honestly
- one coherent Task 4.8 commit is created

Then record:

`Task 4.8 — Context Guardrails — COMPLETE`

and identify the exact next roadmap task from
`project_plan/PROJECT_EXECUTION.md`.

Do not start the next task.
