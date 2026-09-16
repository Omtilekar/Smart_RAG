# Task 4.7 — Input Guardrails

## Objective

Implement and validate the production input-guardrail boundary for the
Production RAG system.

This task is deliberately narrow:

USER INPUT
    ->
INPUT GUARDRAIL
    ->
ALLOW or REJECT
    ->
only allowed input may continue to routing / retrieval / generation

Do NOT implement context guardrails.
Do NOT implement output guardrails.
Do NOT build the FastAPI serving layer.
Do NOT reopen Phase 3 retrieval/model decisions.
Do NOT modify Tasks 4.1–4.6 production artifacts.
Do NOT open protected TEST.
Do NOT make paid LLM/API calls.

The authoritative Task 4.7 definition remains
`project_plan/PROJECT_EXECUTION.md`.

Before coding, read the exact Task 4.7 section there. If its scope or
acceptance criteria materially differ from this prompt, follow the
authoritative roadmap and report the difference explicitly rather than
silently reconciling it.

---

# Repository

Project root:

`C:\Om\Codes\RAG`

Before making changes, inspect at minimum:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PROJECT_SPEC.md`
- `project_plan/GIT_CONVENTIONS.md`
- `project_plan/TESTING.md`
- `project_plan/CONFIGURATION.md`
- `project_plan/LOGGING.md`
- `project_plan/REPOSITORY_STRUCTURE.md`
- `project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md`
- Phase 3 router / retrieval / CRAG documentation relevant to the request path
- current `src/guards/`
- current router / retrieval / generation public interfaces
- `scripts/dev.py`
- `pytest.ini`

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not assume current repository state from this prompt alone.

---

# Hard Precondition

Task 4.7 may begin only if Task 4.6 is actually complete.

Current Progress.md records:

```text
Phase 4 — Make It Real
  4.1 Full-corpus normalization       — COMPLETE
  4.2 Full-corpus chunking            — COMPLETE
  4.3 Full-corpus embedding           — COMPLETE
  4.4 Full-corpus vector index        — COMPLETE
  4.5 XBRL serving representation     — COMPLETE
  4.6 Generation production interface — COMPLETE

Next: 4.7 Input guardrails
```

Verify the real repository evidence for Task 4.6, including its code,
tests, documentation, and Git state.

If Task 4.6 is incomplete or inconsistent with Progress.md:

STOP.

Do not repair Task 4.6 inside Task 4.7.

---

# Frozen Upstream Decisions

Treat the following as frozen unless the authoritative repository contains
a newer explicit decision.

## Retrieval / indexing

- Full-corpus chunks: `10,487,096`
- Embedding model: `Qwen/Qwen3-Embedding-0.6B`
- Embedding revision:
  `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- Dimension: `1024`
- Persisted vector dtype: `float32`
- Dense retrieval selected
- Exact / flat cosine search retained
- RRF hybrid: NOT selected
- Cross-encoder reranking: NOT selected
- Metadata pre-filtering: selected where applicable
- CRAG threshold: `0.5531`

Task 4.7 must not change any of these.

## Generation

Task 4.6 froze:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
```

and added a local/offline Ollama provider for experiments.

Input guardrails must be provider-neutral.

Do not place OpenRouter-specific logic inside the guardrail layer.

## Serving direction

Fargate / continuously warm compute remains the preferred serving direction.

Task 4.7 does not deploy anything.

---

# Protected TEST

Protected TEST remains sealed.

Official usage before Task 4.7:

`0 / 3`

Rules:

- Do not open protected TEST.
- Do not inspect TEST questions.
- Do not run TEST.
- Do not use TEST examples to tune guardrails.
- Do not consume an official TEST run.

At task completion explicitly report:

`official TEST usage: 0/3`

If any proposed validation requires TEST access:

STOP.

---

# No Paid Calls

Task 4.7 should be deterministic and local.

Do not make:

- OpenRouter calls
- OpenAI calls
- Anthropic calls
- paid moderation calls
- remote LLM calls

Do not use an LLM as the input guardrail unless
`PROJECT_EXECUTION.md` explicitly requires one.

If the roadmap unexpectedly requires a paid/external moderation service,
STOP and report the dependency instead of spending money.

---

# Design Principle

Input guardrails are a request-boundary safety and validity layer.

They must answer, deterministically:

```text
Can this user input enter the RAG pipeline?
```

They must NOT answer:

```text
Is the retrieved context safe?
Is the model answer grounded?
Is the generated answer safe?
```

Those belong to later context/output guardrail tasks.

Keep Task 4.7 separated from those responsibilities.

---

# First Implementation Step — Resolve Exact Guard Contract

Before writing guard code, extract the exact Task 4.7 requirements from
`PROJECT_EXECUTION.md`.

Create an internal checklist containing:

```text
Task 4.7 exact title:
Required guard categories:
Required thresholds:
Required result schema:
Required integration point:
Required logging behavior:
Required tests:
Required artifacts/results:
Explicit non-goals:
```

Do not invent thresholds.

Examples of threshold-like decisions that MUST come from the roadmap,
existing config, or an explicit user decision include:

- maximum input characters
- maximum input tokens
- maximum number of lines
- whether leading/trailing whitespace is normalized
- whether control characters are rejected
- whether prompt-injection heuristics are required
- which patterns count as an input-policy violation

If a material semantic value is not defined anywhere:

STOP AND ASK.

Do not silently choose a “reasonable” number.

---

# Recommended Architecture

If no existing guard interface already exists, implement a small,
deterministic API under `src/guards/`.

Prefer an interface conceptually similar to:

```python
GuardDecision(
    allowed: bool,
    reason_code: str | None,
    detail: str | None,
)
```

and a function / class conceptually similar to:

```python
check_input(question: str) -> GuardDecision
```

The exact names should follow repository style after inspection.

If the roadmap already defines an interface, use it instead.

Do not create two competing guardrail APIs.

---

# Stable Reason Codes

Rejected inputs should have machine-readable, stable reason codes.

Examples only — use the roadmap's actual categories:

```text
empty_input
input_too_long
invalid_type
disallowed_control_character
prompt_injection_detected
```

Do NOT add a reason merely because it sounds useful.

Every implemented reason code must correspond to an explicit guard
requirement.

Reason codes should be stable enough for the later API layer to translate
them into HTTP responses without parsing human-readable text.

Human-readable detail may accompany the code, but application behavior
must not depend on wording.

---

# Input Preservation

Do not silently rewrite the user's substantive question.

Unless the authoritative task explicitly defines normalization:

- it is acceptable to use `strip()` or equivalent internally to determine
  whether input is empty,
- but preserve the original accepted question for downstream processing,
- do not paraphrase it,
- do not summarize it,
- do not remove phrases,
- do not “repair” prompt injection,
- do not convert rejected input into a safer question.

The guard either allows or rejects.

It does not rewrite user intent.

---

# Prompt-Injection Handling

Only implement prompt-injection detection if Task 4.7 / existing planning
documents explicitly require it.

If required, the detector must be deterministic and testable.

Do not use an LLM classifier.

Do not claim a heuristic detector is a comprehensive security boundary.

If heuristic rules are required:

- store rules in one clearly-defined place,
- make matching deterministic,
- document known false-positive/false-negative limitations,
- test obvious malicious examples,
- test legitimate SEC/financial questions that contain similar vocabulary,
- avoid overly broad patterns such as rejecting every query containing
  the word `ignore`,
- never execute or follow instruction-shaped content during detection.

The detector examines strings as data only.

---

# Structural Input Validation

Implement the structural validation required by the authoritative task.

Potential categories may include:

- type validation
- empty / whitespace-only input
- configured size limit
- malformed Unicode handling
- NUL / control characters
- request-shape validation

Only implement categories actually required by Task 4.7.

Malformed input must fail predictably.

Do not crash deep inside retrieval/generation because an invalid request
was allowed through.

---

# Integration Boundary

Input guardrails must sit before expensive or stateful downstream work.

Prove by test that rejected input does NOT invoke:

- router
- query embedding
- LanceDB search
- XBRL lookup
- tree navigation
- generation provider
- Ollama
- OpenRouter

Do this with injected/mocked callables or the repository's existing
dependency-injection style.

Do not call real external services to prove a rejected request is blocked.

For accepted input, prove the downstream callable is invoked exactly once
and receives the unchanged accepted question unless the frozen contract
explicitly defines a normalization.

---

# Do Not Couple to Full-Corpus Latency

Task 4.4 established that a local exact-flat query over the complete
10,487,096-row index can take roughly 31–35 seconds on this development
machine.

Input-guardrail unit tests must NOT trigger full-corpus vector queries.

Portable tests should use synthetic/stubbed downstream functions.

A narrow local-data integration test may verify the wiring if the roadmap
requires it, but do not repeatedly run 30+ second queries just to test
input validation.

---

# Logging

Use the existing `src.logging_utils` convention.

Input guardrails should emit useful structured events without leaking
unnecessary user content.

Prefer fields such as:

```text
event=input_guard_decision
allowed=true/false
reason_code=...
input_length=...
```

Do not log:

- API keys
- authorization headers
- embedding vectors
- retrieved context
- full prompts
- full generation responses

Unless the repository explicitly requires raw input logging, do not log
the entire rejected input string.

A malicious prompt may itself contain sensitive or instruction-shaped
content; logging it verbatim is unnecessary for the guardrail decision.

---

# Configuration

Do not scatter hardcoded limits across source files.

If Task 4.7 introduces a configurable input limit, integrate it through the
existing config boundary (`src.config`) in the same typed/environment-aware
style already used by the project.

Requirements:

- safe default only if the roadmap defines one,
- environment override only if the project convention requires it,
- validation at config load,
- documented in `project_plan/CONFIGURATION.md`,
- `.env.example` updated only if permitted by the current environment and
  only with non-secret placeholder/default values.

If the sandbox denies `.env.example`, report it; do not work around
permissions by writing secrets elsewhere.

---

# Error / Exception Policy

Expected user rejection is not an application crash.

Separate:

1. valid guard rejection,
2. guard configuration error,
3. unexpected internal execution failure.

A normal rejected question should produce a normal `GuardDecision` or
equivalent result, not a traceback.

Invalid guard configuration should fail clearly and early.

Unexpected internal bugs should propagate or be wrapped in the project's
normal error hierarchy; do not silently convert them into “input rejected.”

---

# Determinism

For the same input and same config, guard decisions must be identical.

No random sampling.
No temperature.
No time-dependent policy.
No network call.
No model inference.

Add a determinism test covering every implemented guard category.

---

# Portable Test Requirements

Add focused portable tests for all actual Task 4.7 semantics.

At minimum cover, where applicable:

- ordinary valid SEC/financial question allowed
- valid Unicode question allowed
- empty string rejected
- whitespace-only string rejected
- invalid type rejected
- exact boundary immediately below / at / above configured size limit
- deterministic repeated decisions
- stable reason codes
- original valid input preserved
- rejected input never reaches downstream work
- allowed input reaches downstream exactly once
- no network/LLM call exists in guard code
- logging does not expose disallowed raw content
- config validation
- malformed configuration rejected
- prompt-injection positive fixtures if that guard exists
- prompt-injection negative / false-positive fixtures if that guard exists

If prompt-injection detection is implemented, include adversarial fixtures
such as instruction-shaped content while proving legitimate financial
questions are not broadly rejected.

Do not use protected TEST examples.

---

# Static Safety Tests

Where useful, add source-inspection / AST guards proving the input-guard
module does not import or call forbidden dependencies such as:

- OpenRouter provider
- Ollama provider
- `requests.post`
- LanceDB
- sentence-transformers
- torch
- protected TEST loaders

Do not rely only on comments claiming the module is local/deterministic.

---

# Local Integration Validation

After portable tests pass, run the smallest meaningful real integration
check supported by the authoritative roadmap.

Examples:

```text
valid question
  -> guard allows
  -> downstream stub / existing orchestrator receives same question

rejected question
  -> guard rejects
  -> downstream invocation count remains zero
```

Do not make a paid generation call.

If an actual local Ollama call is not required by Task 4.7, do not make one.

This task validates the guard boundary, not the generator.

---

# Results Artifact

Write a small tracked summary, following repository conventions, likely:

`results/phase_4_7_input_guardrails_summary.json`

The exact name may follow current naming style if different.

Include at minimum:

- task
- status
- guard categories implemented
- configured thresholds / values
- deterministic config identity/hash if the project convention uses one
- portable test results
- full test results
- integration check result
- paid API calls
- protected TEST usage
- files modified
- known limitations

Do not include raw malicious prompt text if not needed.

Do not include secrets.

---

# Documentation

Create a task document consistent with existing Phase 4 docs, likely:

`project_plan/PHASE4_INPUT_GUARDRAILS.md`

Document:

- exact roadmap requirement
- implemented contract
- guard order
- reason codes
- configuration
- integration boundary
- logging behavior
- test matrix
- known limitations
- explicit separation from context/output guardrails

Update `project_plan/REPOSITORY_STRUCTURE.md` only if new tracked modules
need to be reflected there.

Update other docs only when the task genuinely changes them.

---

# Progress.md

Only after implementation and validation pass, append a detailed Task 4.7
entry matching the established Progress.md style.

Record:

- objective
- authoritative guard requirements
- implementation
- reason codes
- thresholds/config
- integration point
- deterministic behavior
- prompt-injection handling if implemented
- logging policy
- test counts
- real integration result
- known limitations
- no-paid-call status
- protected TEST usage `0/3`
- Git commit
- final Task 4.7 status
- exact next roadmap task from `PROJECT_EXECUTION.md`

Do not guess that the next task is context guardrails even if it seems
likely.

Read the roadmap and record its exact title.

Do not start the next task.

---

# Regression Gates

Before and after Task 4.7 verify:

- Task 4.1 normalization artifact unchanged
- Task 4.2 chunk artifact unchanged
- Task 4.3 embedding artifact unchanged
- Task 4.4 full-corpus vector index unchanged
- Task 4.5 XBRL serving export unchanged
- Task 4.6 generation semantics unchanged except any explicitly-approved
  input-boundary wiring
- frozen Phase 3 retrieval decisions unchanged
- CRAG threshold unchanged
- no BM25/RRF reintroduced
- no reranker reintroduced
- no re-embedding
- no generation-provider model change
- no paid API call
- protected TEST unopened

Run:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

If the full test suite contains optional external-service tests that skip
because credentials/services are absent, report that honestly.

Do not turn a missing capability into a fake PASS.

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

- no `data/` contents staged
- no `artifacts/` contents staged
- no model weights staged
- no `.env` staged
- no API keys staged
- no user-sensitive raw logs staged
- only small tracked task deliverables are included

Commit Task 4.7 as one coherent commit after all gates pass.

Suggested commit message:

`Add production input guardrails`

Do not push unless current user/repository policy explicitly authorizes it.

---

# Stop Conditions

STOP and report instead of guessing if:

1. Task 4.6 is not actually complete.
2. `PROJECT_EXECUTION.md` defines Task 4.7 materially differently from this
   prompt.
3. A required input-length or token threshold is not defined.
4. Prompt-injection policy is required but its matching/response contract is
   unspecified.
5. A new external moderation/LLM service would be required.
6. A paid API call would be required.
7. Guard integration would require prematurely building the FastAPI layer.
8. Context/output guardrails would have to be implemented to satisfy this
   task.
9. Any upstream frozen Phase 3/4 artifact would need to be modified.
10. Protected TEST access would be required.
11. Regression tests fail for an unexplained reason.
12. Git safety cannot be established.

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

Do not mark Task 4.7 complete.

---

# Acceptance Criteria

Task 4.7 is COMPLETE only when all authoritative Task 4.7 criteria pass and,
at minimum:

- input guardrail exists as a reusable production module
- guard runs before downstream routing/retrieval/generation
- invalid/rejected input cannot reach downstream work
- accepted input preserves the user's substantive question
- every implemented rejection has a stable machine-readable reason code
- thresholds come from an explicit frozen source, not an invented value
- behavior is deterministic
- no LLM is required for the guard unless explicitly mandated
- no paid API call is made
- portable tests cover every guard category
- regression suites pass
- structured logging avoids secrets/unnecessary raw input
- Tasks 4.1–4.6 remain intact
- protected TEST remains unopened at `0/3`
- documentation/result summary are written
- Progress.md is updated honestly
- one coherent Task 4.7 commit is created

Then record:

`Task 4.7 — Input Guardrails — COMPLETE`

and identify the exact next roadmap task from
`project_plan/PROJECT_EXECUTION.md`.

Do not start that next task.
