# Task 4.10 — FastAPI Service

## Objective

Implement and validate the production FastAPI service boundary for the
Production RAG system.

Tasks 4.7–4.9 established the three safety boundaries:

```text
USER REQUEST
    ->
INPUT GUARD
    ->
routing / retrieval / SQL / navigation
    ->
CONTEXT GUARD
    ->
generation where applicable
    ->
OUTPUT GUARD
    ->
PUBLIC RESPONSE
```

Task 4.10 must expose the already-frozen production pipeline through a small,
typed, production-oriented HTTP API.

This task is an integration/serving task.

Do NOT reopen retrieval, chunking, embedding, routing, CRAG, citation, or
guardrail decisions.
Do NOT re-normalize, re-chunk, re-embed, or rebuild production artifacts.
Do NOT change the generation provider/model selection.
Do NOT deploy to AWS yet unless `PROJECT_EXECUTION.md` explicitly says
Task 4.10 includes deployment.
Do NOT make paid generation API calls during ordinary tests.
Do NOT open protected TEST.

The authoritative definition is the exact Task 4.10 section in:

`project_plan/PROJECT_EXECUTION.md`

Read that section before coding.

If the authoritative Task 4.10 checklist materially differs from this prompt,
follow `PROJECT_EXECUTION.md` and report the difference explicitly instead of
silently substituting this prompt's assumptions.

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
- `project_plan/SERVING_FEASIBILITY.md`
- `project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md`
- `project_plan/PHASE4_INPUT_GUARDRAILS.md`
- `project_plan/PHASE4_CONTEXT_GUARDRAILS.md`
- `project_plan/PHASE4_OUTPUT_GUARDRAILS.md`
- current `src/api/`
- current `src/cli/`
- current `src/router/`
- current `src/retrieval/`
- current `src/generation/`
- current `src/guards/`
- current structured SQL/XBRL route code
- current tree-navigation route code
- `src/config.py`
- `src/logging_utils.py`
- `src/storage.py`
- `scripts/dev.py`
- `pytest.ini`

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not rely only on Progress.md prose.

---

# Hard Precondition — Task 4.9

Task 4.10 may begin only if Task 4.9 is actually COMPLETE.

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
  4.8 Context guardrails                      — COMPLETE
  4.9 Output guardrails                       — COMPLETE

Next: 4.10 FastAPI service
```

Verify the real repository evidence before proceeding.

At minimum confirm:

- Task 4.9 output-guard module exists
- Task 4.9 is integrated after generation and before public release
- malformed/unknown citations are blocked according to the documented contract
- unsupported-advice output handling matches the documented contract
- legitimate zero-citation abstention remains allowed
- Task 4.9 made zero paid API calls
- protected TEST remains unopened

If Task 4.9 is not actually complete:

STOP.

Do not repair Task 4.9 inside Task 4.10 except for a tiny factual
documentation correction if needed.

---

# Frozen Production Stack

Treat the following as immutable unless the authoritative Task 4.10 roadmap
explicitly says otherwise.

## Full-corpus text path

```text
documents normalized:
  91,086 total source documents accounted for

full-corpus chunks:
  10,487,096

chunking:
  fixed 256 content tokens
  overlap 0
  stride 256

chunk_config_hash:
  ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06

embedding:
  Qwen/Qwen3-Embedding-0.6B

embedding revision:
  97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3

dimension:
  1024

dtype:
  float32

distance:
  cosine

retrieval:
  dense-only selected

index:
  exact / flat LanceDB

RRF hybrid:
  NOT selected

cross-encoder reranking:
  NOT selected

metadata prefilter:
  selected
```

## Routing / structured paths

```text
structured SQL/XBRL route:
  selected / frozen

tree-navigation route:
  selected / frozen

CRAG threshold:
  0.5531
```

Do not change routing semantics in the API layer.

## Generation

```text
provider interface:
  configurable

production configuration:
  GENERATION_PROVIDER=openrouter
  GENERATION_MODEL=openai/gpt-oss-20b

local/offline provider:
  Ollama
```

Do not hard-code credentials or provider-specific behavior into endpoint
logic.

## Serving direction

Task 0.10 selected:

```text
Fargate / continuously warm service preferred
```

Task 4.10 should produce an application suitable for a warm-service
deployment model.

Do not redesign it around ephemeral serverless assumptions unless the current
roadmap explicitly changed that decision.

---

# Frozen Guardrail Stack

The HTTP layer must compose, not replace, existing guardrails.

## Input guard

Frozen Task 4.7 behavior includes:

```text
INPUT_GUARD_MAX_LENGTH:
  default 2000 characters

reason order:
  invalid_type
  empty_input
  input_too_long
  disallowed_control_character
  prompt_injection_detected
  advice_request_detected
  pii_detected
  out_of_scope
```

## Context guard

Task 4.8 intentionally implemented a narrow roadmap contract:

```text
- treat retrieved content as untrusted data
- delimit retrieved evidence
- preserve provenance
- validate required provenance
- prove retrieved text cannot override system instructions
```

Only `missing_provenance` is currently a runtime context reason code unless
the repository now explicitly says otherwise.

## Output guard

Task 4.9 currently implements deterministic checks for:

```text
malformed_citation
unknown_citation
unsupported_advice

plus:
  structured route provenance validation through the reused
  missing_provenance contract
```

Do not add new guard behavior merely because an HTTP API now exists.

---

# Protected TEST

Protected TEST remains sealed.

Official usage before Task 4.10:

`0 / 3`

Rules:

- Do not open protected TEST.
- Do not inspect protected TEST questions.
- Do not run protected TEST.
- Do not use TEST to tune endpoint behavior.
- Do not consume an official TEST run.

At task completion explicitly report:

`official TEST usage: 0/3`

If any proposed validation requires TEST access:

STOP.

---

# Paid / External API Safety

Ordinary Task 4.10 tests must make zero paid generation calls.

The project has a known historical incident where a live OpenRouter test ran
because credentials were present.

Task 4.10 must not repeat that.

Requirements:

- endpoint tests use dependency injection / fakes,
- do not run `scripts/smoke_generation.py`,
- do not set `RUN_LIVE_GENERATION_API_TEST=1`,
- do not let mere presence of `OPENROUTER_API_KEY` trigger network usage,
- explicitly exclude `generation_api` from non-portable regression runs.

Preferred regression commands:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Record:

```text
Task 4.10 paid API calls: 0
```

Do not claim the entire historical project had zero live calls.

---

# First Implementation Step — Resolve the Exact API Contract

Before writing endpoint code, read the exact Task 4.10 checklist from
`PROJECT_EXECUTION.md`.

Write down internally:

```text
Task 4.10 exact title:
Required endpoints:
Request schemas:
Response schemas:
HTTP status mapping:
Guard-rejection mapping:
Health/readiness semantics:
Startup/lifespan behavior:
Dependency initialization:
Logging requirements:
Timeout/cancellation requirements:
CORS/auth/rate-limit scope:
Required tests:
Required docs:
Explicit non-goals:
```

Do not invent material API semantics.

If the roadmap says only one endpoint is required, do not build a broad API.

If required status-code behavior is missing and materially affects clients,
STOP AND ASK.

Examples of decisions that must not be guessed if the roadmap does not define
them:

- `/answer` vs `/query` vs `/v1/query`
- 400 vs 422 for guard rejection
- whether guard rejection is HTTP error or a successful typed refusal result
- readiness vs liveness behavior
- whether structured and dense routes share one endpoint
- whether route metadata is exposed publicly
- whether internal reason codes are included in public responses
- whether latency diagnostics are returned
- whether raw citations are strings or structured objects
- whether request IDs are client-supplied or server-generated

---

# Recommended Minimal Service Shape

Only use this shape if it matches the authoritative roadmap.

Prefer a small API such as:

```text
GET  /health
GET  /ready
POST /query
```

Avoid endpoint sprawl.

Do not add admin/debug/internal artifact endpoints unless explicitly required.

Do not expose filesystem paths, raw prompts, embeddings, provider responses,
or secrets.

---

# App Factory

Prefer an application factory rather than constructing heavyweight production
dependencies at import time.

Conceptually:

```python
def create_app(...) -> FastAPI:
    ...
```

Exact signature should follow repository style.

Goals:

- portable tests can inject fakes,
- import of `src.api` does not load Qwen or open LanceDB,
- endpoint behavior can be tested without the full 10.49M-row index,
- provider network clients are not constructed unnecessarily,
- lifecycle behavior remains explicit.

Do not create two competing app instances/APIs if the repository already has
a service factory pattern.

---

# Dependency Construction

The API layer should depend on existing production components.

Do not duplicate business logic inside route functions.

Preferred conceptual separation:

```text
FastAPI endpoint
    ->
typed request
    ->
existing request/pipeline service
    ->
input guard
    ->
router
    ->
selected route implementation
    ->
context/output guards where applicable
    ->
typed domain result
    ->
HTTP response mapper
```

If no single orchestration service exists yet, Task 4.10 may add a narrow
service/facade only if required to avoid embedding pipeline logic directly in
FastAPI routes.

Do not reimplement:

- routing heuristics
- retrieval
- SQL fact selection
- navigation
- generation
- citation parsing
- guardrail logic

inside `src/api/`.

---

# Startup / Lifespan

The full production model and index are expensive resources.

Use FastAPI's current lifespan/startup pattern according to the project's
installed FastAPI version and repository conventions.

Do not load the model/index once per request.

For production dependencies, initialize/reuse long-lived resources at app
startup or through another explicit singleton/service lifecycle already
established by the project.

However, portable tests must be able to construct the app with lightweight
fake dependencies.

Measure and report startup behavior if the roadmap requires it.

Do not hide multi-second initialization under the first user request if the
service is meant to be continuously warm.

---

# Health vs Readiness

If the authoritative roadmap requires both:

```text
liveness/health:
  process/app is running

readiness:
  required serving dependencies are initialized and usable
```

Keep them distinct.

A process can be alive but not ready.

Readiness should not perform an expensive 10.49M-row retrieval on every
probe.

Use lightweight checks against already-initialized dependency state.

Do not make readiness call OpenRouter.

Do not make readiness dependent on a paid external generation API unless the
roadmap explicitly requires external-provider reachability as readiness
semantics.

---

# Request Schema

Use Pydantic/FastAPI typed request models.

Do not rely on untyped `dict` payloads.

The request should preserve the exact user question string for Task 4.7's
input guard.

Do not silently strip or rewrite substantive user input before the existing
input guard sees it.

If the API contract includes optional metadata/filter fields, map them to the
already-frozen route/filter semantics.

Do not add new filtering dimensions.

---

# Response Schema

Use an explicit response model.

Expose only fields allowed by the authoritative roadmap and existing public
contracts.

Potential public fields may include:

```text
answer
citations
route
status
reason_code
request_id
```

These are examples only.

Do not expose:

- embeddings
- raw retrieval vectors
- provider raw response
- provider API key
- system prompt
- full retrieved context
- local filesystem paths
- internal stack traces
- raw LanceDB rows
- hidden diagnostic metadata not already approved

If citations are returned, preserve the frozen citation identity contract.

---

# Guardrail-to-HTTP Mapping

Task 4.10 must map existing guard decisions into stable HTTP/API behavior
without changing guard semantics.

For each existing input/context/output reason code, document:

```text
domain decision
    ->
HTTP status
    ->
public response shape
```

Do not make downstream clients parse human-readable error strings.

If the authoritative roadmap does not specify whether guard rejection should
be a 4xx error vs. a normal typed refusal response and that choice affects the
public API contract:

STOP AND ASK.

Do not guess.

---

# Exception Mapping

Do not return raw tracebacks.

Separate at minimum:

```text
expected client/request rejection
expected domain abstention
expected provider/service unavailability
unexpected internal error
```

Use FastAPI exception handlers or a narrow equivalent.

Do not convert every exception into HTTP 200.

Do not convert every exception into HTTP 500.

Do not leak:

- exception internals
- local paths
- environment variables
- secrets
- raw provider bodies

Public messages should be stable and bounded.

Internal logs may retain safe structured diagnostics without raw sensitive
payloads.

---

# Provider Failures

Reuse Task 4.6's provider-neutral error contract.

Do not special-case OpenRouter deep inside endpoint code.

Map provider failures at the orchestration/API boundary according to the
authoritative API contract.

Examples may distinguish:

```text
upstream timeout
upstream unavailable
configuration error
unexpected provider response
```

Only implement distinctions already represented in the project's provider
error contract or explicitly required by Task 4.10.

---

# Timeouts / Cancellation

If the authoritative roadmap requires request timeouts, use an explicit
service-level policy.

Do not invent a timeout value.

If no timeout is specified and introducing one would change behavior:

STOP AND ASK.

Be aware that local full-corpus exact retrieval has historically been measured
in the tens-of-seconds range on the development machine.

Do not set a small arbitrary timeout that makes the frozen exact-search path
unusable.

---

# Concurrency

Do not assume that model/index/provider components are automatically safe
under concurrent requests.

Inspect the actual implementation.

Task 4.10 should test at least the HTTP/service layer for basic concurrent
request behavior using fakes if the roadmap requires concurrency.

Do not claim production throughput from synthetic TestClient concurrency.

Do not add worker/process counts in code unless they belong to deployment
configuration.

---

# Structured Route Behavior

The API must preserve the existing router contract.

A single user-facing query endpoint may route to:

```text
dense retrieval/generation
structured SQL/XBRL
tree navigation
```

if that is how the current production pipeline is defined.

Do not expose separate public routes merely to bypass the router unless the
roadmap explicitly requires them.

If structured/navigation routes currently return deterministic answers
without an LLM, preserve that.

Do not insert generation merely to make all routes look uniform.

---

# Observability

Use `src.logging_utils`.

Add structured request lifecycle events without logging raw sensitive data.

Potential fields:

```text
event=request_started
request_id=...
route=...
status=...
reason_code=...
elapsed_ms=...
```

Do not log:

- API keys
- authorization headers
- full user question unless explicitly allowed
- full retrieved context
- full provider prompt
- full generated answer
- embeddings
- raw provider response

Prefer input length / citation count / route / elapsed time over raw content.

If a request ID is required, use a deterministic/testable generation method
or injectable factory.

Do not expose hidden chain-of-thought or internal reasoning.

---

# CORS / Authentication / Rate Limiting

Do NOT implement these unless the authoritative Task 4.10 checklist requires
them.

Task 4.7 explicitly deferred rate limiting to the API/infrastructure layer,
so Task 4.10 must now read the roadmap carefully.

If rate limiting is in Task 4.10 scope:

- follow the exact approved strategy,
- do not invent limits,
- make behavior testable,
- avoid external paid dependencies unless explicitly approved.

If auth is not yet in scope, do not add a home-grown API-key system.

If CORS is required, do not default to wildcard production origins unless
explicitly approved.

---

# OpenAPI

FastAPI should produce a clean OpenAPI contract from typed models.

If the roadmap requires API docs:

- verify endpoint names,
- request/response schemas,
- status codes,
- descriptions,
- no internal-only fields exposed.

Do not manually maintain a second hand-written schema that can drift from the
actual app unless the repository already uses one.

A portable test should inspect the generated OpenAPI JSON for critical
contract fields.

---

# No Heavy Real Pipeline in Portable Tests

Portable tests must not:

- load Qwen3-Embedding-0.6B,
- query the 10.49M-row production index,
- open the large XBRL serving corpus,
- call OpenRouter,
- call Ollama,
- require GPU.

Use injected fakes/stubs.

Real-pipeline checks, if required, should be separately marked
`local_data`/`model`/`gpu` and still exclude paid generation.

Do not turn every API test into a 30+ second retrieval test.

---

# Required Portable Tests

Add focused tests for the exact Task 4.10 contract.

At minimum, where applicable:

- app constructs with fake dependencies
- app import has no heavy model/index side effects
- health endpoint
- readiness endpoint
- valid query request
- invalid request schema
- Task 4.7 rejection mapped correctly
- Task 4.8 context rejection mapped correctly
- Task 4.9 output rejection mapped correctly
- legitimate abstention mapped correctly
- dense route success
- structured route success
- navigation route success
- provider error mapping
- unexpected exception does not leak traceback
- citations preserved
- no vectors/internal prompt/provider raw response in public response
- request ID behavior
- structured logging does not expose raw sensitive content
- OpenAPI contract
- provider fake invoked only when route requires generation
- rejected input never initializes/calls expensive downstream work where
  architecture allows deferred construction
- deterministic behavior of pure response mapping

Only test route categories actually wired by the authoritative implementation.

---

# Static Safety Tests

Where useful, add source/AST tests confirming endpoint modules do not directly
implement or import forbidden lower-level behavior unnecessarily.

Examples:

- no OpenRouter HTTP construction inside route function
- no embedding-model inference inside route function
- no raw LanceDB query code inside route function
- no protected TEST loaders
- no credential logging
- no hardcoded API key

The API may import orchestration/service components; it should not duplicate
their internals.

---

# Optional Local Integration Test

If the authoritative roadmap requires a local real-pipeline check, keep it
small.

Recommended shape:

```text
FastAPI app with real local retrieval/router dependencies
generation provider replaced by a deterministic fake
one or a few SEC-style questions
```

This proves HTTP-to-pipeline wiring without spending API credits.

Do not use protected TEST.

Do not claim this as production load testing.

---

# Performance Diagnostic

If Task 4.10 requires endpoint-level latency, separate:

```text
API framework overhead
dependency startup/open time
warm request time
route/component timings
```

Do not compare a fake-provider endpoint benchmark to a real production
generation latency as if they were equivalent.

Do not include TestClient startup in every warm-request measurement unless
explicitly labeled.

Task 0.10 already selected continuously warm compute.

Task 4.10 should verify the service boundary, not rerun the Phase 0 serving
architecture decision unless `PROJECT_EXECUTION.md` explicitly requests a
re-check.

---

# CLI Compatibility

Do not break existing CLI behavior merely because an HTTP API now exists.

Where possible, CLI and FastAPI should share the same orchestration/service
layer.

Do not make the CLI call the local HTTP service unless the roadmap explicitly
requires that architecture.

Preserve existing deterministic CLI tests.

---

# Configuration

Use `src.config`.

Do not read environment variables ad hoc throughout the API.

If Task 4.10 introduces API-specific settings, examples may include:

```text
API_HOST
API_PORT
```

but only add settings actually required by the authoritative roadmap.

Do not add configuration purely for symmetry.

Validate any new settings at config load.

Update:

- `project_plan/CONFIGURATION.md`
- `.env.example` when allowed and appropriate

Never put real secrets into `.env.example`.

---

# Entry Point

If required, provide one clear local run command, for example:

```text
python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

This is only an example.

Use the actual module/factory chosen by the repository.

Document the command.

Do not silently enable reload in the production command.

If a developer reload command is useful, document it separately as
development-only.

---

# Results Artifact

Write a small tracked result summary following repository conventions,
likely:

`results/phase_4_10_fastapi_service_summary.json`

Use the repository's actual naming convention if different.

Record at minimum:

```text
task
status
endpoints
request/response contract
guard-to-HTTP mappings
route coverage
startup/lifespan design
portable test result
non-generation regression result
local integration result if run
paid API calls during Task 4.10 = 0
protected TEST usage = 0/3
files modified
known limitations
```

Do not include raw user questions, context, provider responses, or secrets.

---

# Documentation

Create/update a Phase 4 service document consistent with repository style,
likely:

`project_plan/PHASE4_FASTAPI_SERVICE.md`

Document:

- exact Task 4.10 roadmap checklist
- endpoint contract
- request model
- response model
- status/error mappings
- guardrail integration
- routing integration
- dependency lifecycle
- health/readiness
- logging
- local run command
- test strategy
- known limitations
- explicit non-goals
- separation from deployment/infrastructure

Update `project_plan/REPOSITORY_STRUCTURE.md`,
`project_plan/CONFIGURATION.md`,
`project_plan/DEVELOPER_COMMANDS.md`,
and other docs only if the real implementation changes them.

---

# Progress.md

Only after implementation and validation pass, append a detailed Task 4.10
entry matching existing style.

Record:

```text
objective
authoritative roadmap requirements
any scope differences from this prompt
endpoint list
request/response contracts
HTTP status mapping
guardrail integration
route coverage
startup/lifespan strategy
health/readiness behavior
config changes
tests
local integration result
performance diagnostic if required
paid API calls during Task 4.10 = 0
protected TEST usage = 0/3
known limitations
Git commit
final Task 4.10 status
exact next roadmap task from PROJECT_EXECUTION.md
```

Do not guess the next task.

Do not start it.

---

# Regression Gates

Before and after Task 4.10 verify:

- Task 4.1 normalization artifact unchanged
- Task 4.2 chunk artifact unchanged
- Task 4.3 embedding artifact unchanged
- Task 4.4 vector index unchanged
- Task 4.5 XBRL serving export unchanged
- Task 4.6 provider/model semantics unchanged
- Task 4.7 input guard semantics unchanged
- Task 4.8 context guard semantics unchanged
- Task 4.9 output guard semantics unchanged
- frozen Phase 3 routing/retrieval decisions unchanged
- CRAG threshold remains `0.5531`
- no BM25/RRF reintroduced
- no reranker reintroduced
- no re-embedding
- no provider/model change
- no paid API call
- protected TEST remains unopened

Run:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Do not run the live generation marker.

If another marker can perform a network call or incur cost, exclude it unless
the authoritative task explicitly requires that external dependency.

Report skips and deselections accurately.

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
- no API keys staged
- no raw prompts/context/provider responses staged
- no large generated outputs staged
- tracked docs/results/tests are small

Commit Task 4.10 as one coherent commit only after all gates pass.

Suggested commit message:

`Add production FastAPI service`

Do not push unless current user/repository policy explicitly authorizes it.

---

# Stop Conditions

STOP and report rather than guessing if:

1. Task 4.9 is not actually complete.
2. `PROJECT_EXECUTION.md` defines Task 4.10 materially differently.
3. Required endpoint names/contracts are ambiguous.
4. Guard rejection HTTP semantics are unspecified where a public contract
   decision is required.
5. Required timeout/concurrency/rate-limit values are undefined.
6. FastAPI integration would require changing frozen routing/retrieval
   semantics.
7. A paid generation call would be required.
8. A real provider call appears necessary for validation.
9. Task 4.10 unexpectedly includes cloud deployment but required
   infrastructure/account details are unavailable.
10. An upstream frozen artifact would need to be modified.
11. Protected TEST access would be required.
12. Regression tests fail for an unexplained reason.
13. Git safety cannot be established.

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

Do not mark Task 4.10 complete.

---

# Acceptance Criteria

Task 4.10 is COMPLETE only when the authoritative roadmap criteria pass and,
at minimum:

- FastAPI service exists as a reusable production application
- public endpoint contract is typed and documented
- endpoint code composes existing pipeline/guard components rather than
  reimplementing them
- input guard executes before expensive downstream work
- context guard executes before generation where applicable
- output guard executes after generation and before release
- dense / structured / navigation behavior matches the frozen router contract
  for whichever routes the roadmap requires
- health/readiness behavior is explicit
- production heavyweight dependencies are not recreated per request
- portable tests require no GPU/model/full corpus/network
- provider calls are replaced by fakes in API tests
- HTTP error handling does not leak stack traces/secrets/internal prompts
- OpenAPI schema matches the intended public contract
- existing CLI behavior remains intact
- regression suites pass with `generation_api` excluded
- paid API calls during Task 4.10 = 0
- Tasks 4.1–4.9 remain intact
- protected TEST remains unopened at 0/3
- documentation/result summary are written
- Progress.md is updated honestly
- one coherent Task 4.10 commit is created

Then record:

`Task 4.10 — FastAPI Service — COMPLETE`

and identify the exact next roadmap task from
`project_plan/PROJECT_EXECUTION.md`.

Do not start the next task.
