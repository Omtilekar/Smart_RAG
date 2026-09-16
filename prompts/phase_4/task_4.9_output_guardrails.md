# Task 4.9 — Output Guardrails

## Objective

Implement and validate the production **output-guardrail boundary** for the
Production RAG system.

Tasks 4.7 and 4.8 established the two earlier safety boundaries:

```text
USER INPUT
    ->
INPUT GUARD
    ->
routing / retrieval / SQL / navigation
    ->
CONTEXT GUARD
    ->
generation
    ->
GENERATED OUTPUT
    ->
OUTPUT GUARD
    ->
RELEASE / SAFE REJECTION / ABSTENTION
```

Task 4.9 owns only the final boundary between a generated answer and what is
returned to the user.

Do NOT implement FastAPI.
Do NOT deploy infrastructure.
Do NOT reopen Phase 3 retrieval/routing/model decisions.
Do NOT change the generation provider/model selection.
Do NOT re-normalize, re-chunk, re-embed, or rebuild indexes.
Do NOT open protected TEST.
Do NOT make any paid/external generation API call during this task.

The authoritative definition is the exact Task 4.9 section in:

`project_plan/PROJECT_EXECUTION.md`

Before writing code, read that section directly.

If the authoritative Task 4.9 checklist materially differs from this prompt,
follow `PROJECT_EXECUTION.md` and report the difference explicitly instead of
silently implementing this prompt's broader suggestions.

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
- `project_plan/PHASE4_CONTEXT_GUARDRAILS.md`
- `project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md`
- current `src/guards/`
- `src/generation/minimal.py`
- `src/generation/provider.py`
- `src/generation/citations.py`
- current citation-validation / citation-integrity helpers
- current router / structured SQL / tree-navigation result contracts
- any existing abstention helpers
- `scripts/dev.py`
- `pytest.ini`

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not rely solely on Progress.md prose.

---

# Hard Precondition — Task 4.8

Task 4.9 may begin only if Task 4.8 is actually COMPLETE.

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

Next: 4.9 Output guardrails
```

Verify the real Task 4.8 implementation and tests before proceeding.

At minimum confirm:

- `src/guards/context.py` exists
- dense/XBRL/navigation context checks match their documented contracts
- `missing_provenance` is the only Task 4.8 runtime reason code unless the
  repository now explicitly says otherwise
- dense evidence is structurally delimited before generation
- retrieved instruction-shaped text cannot replace the frozen system prompt
- invalid dense context prevents `provider.generate()`
- Task 4.8 made zero paid API calls
- protected TEST remains unopened

If Task 4.8 is not actually complete:

STOP.

Do not repair Task 4.8 as part of Task 4.9 except for a tiny factual
documentation correction if required.

---

# Task 4.8 Handoff — Preserve the Narrow Roadmap Scope

Task 4.8 discovered that the authoritative roadmap was much narrower than
the draft prompt.

Its actual five-item contract was:

1. treat retrieved content as untrusted data,
2. clearly delimit retrieved evidence,
3. preserve raw evidence for provenance,
4. plant adversarial/instruction-shaped retrieved examples,
5. prove retrieved text cannot override system instructions.

Do not undo or broaden this design in Task 4.9.

Task 4.8 intentionally did NOT add:

- context-size budgets,
- context-injection rejection,
- scope-leak runtime filtering,
- context rewriting,
- large multi-reason policy frameworks.

Do not retroactively add those under the label "output guardrails."

---

# Frozen Task 4.7 Input-Guard Decisions

Do not reopen:

```text
max input length:
  2,000 characters

PII:
  regex-only for now

scope:
  loose deny-list / domain-signal approach

rate limiting:
  documented only; deferred to API/infrastructure

input guard reason/order:
  invalid_type
  empty_input
  input_too_long
  disallowed_control_character
  prompt_injection_detected
  advice_request_detected
  pii_detected
  out_of_scope
```

Output guardrails are not a second input-policy layer.

---

# Frozen Retrieval / Routing / Generation Decisions

Treat these as frozen unless the authoritative Task 4.9 section explicitly
says otherwise:

```text
chunking:
  fixed 256 content tokens, overlap 0

embedding:
  Qwen/Qwen3-Embedding-0.6B
  revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
  dimension 1024

retrieval:
  dense-only selected
  exact / flat cosine retained

RRF hybrid:
  NOT selected

cross-encoder reranking:
  NOT selected

metadata prefilter:
  selected

CRAG threshold:
  0.5531

structured SQL/XBRL:
  selected / frozen

tree navigation:
  selected / frozen

generation provider:
  configurable provider interface

production generation configuration:
  GENERATION_PROVIDER=openrouter
  GENERATION_MODEL=openai/gpt-oss-20b

local/offline generation option:
  Ollama
```

Do not change any of these while implementing output validation.

---

# Protected TEST

Protected TEST remains sealed.

Official usage before Task 4.9:

`0 / 3`

Rules:

- Do not open protected TEST.
- Do not inspect TEST questions.
- Do not run TEST.
- Do not use TEST examples to tune output rules.
- Do not consume an official TEST run.

At completion explicitly report:

`official TEST usage: 0/3`

If any proposed validation requires TEST access:

STOP.

---

# Zero Paid / External Generation Calls

Task 4.9 must make **zero paid generation API calls**.

There was a documented earlier incident in which 3 unintended OpenRouter
calls occurred during Task 4.6/4.7 regression execution. That has already
been recorded accurately.

Do not repeat it.

Requirements:

- do not run the live OpenRouter integration test,
- do not run `scripts/smoke_generation.py`,
- do not set `RUN_LIVE_GENERATION_API_TEST=1`,
- do not make an Ollama call unless the authoritative roadmap specifically
  requires a local-provider integration test; prefer fakes even then,
- use fake/stub provider responses for output-guard testing,
- explicitly exclude `generation_api` from regression commands.

Preferred regression commands:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Record:

```text
Task 4.9 paid API calls: 0
```

Do not claim the whole historical project had zero live calls.

---

# Core Design Principle

The output guard answers:

```text
Can this generated answer be released to the user under the project's
frozen output contract?
```

It does NOT answer:

```text
Was the user input acceptable?
```

Task 4.7 owns that.

It does NOT answer:

```text
Was retrieved context structurally safe and provenance-complete?
```

Task 4.8 owns that.

It also must NOT become a new retrieval-quality experiment or an LLM judge.

The intended boundary is:

```text
provider.generate(...)
    ->
ProviderResponse / generated answer
    ->
OUTPUT GUARD
    ->
public GenerationResult / safe fallback
```

---

# First Implementation Step — Resolve the Exact Task 4.9 Contract

Before coding, read the exact Task 4.9 checklist from
`PROJECT_EXECUTION.md`.

Write down internally:

```text
Task 4.9 exact title:
Required output checks:
Required citation checks:
Required grounding checks:
Required sensitive-data checks:
Required system-prompt / internal-data checks:
Required behavior on failure:
Required reason-code schema:
Required integration point:
Required logging:
Required tests:
Required configuration:
Explicit non-goals:
```

Do not infer policy from the phrase "output guardrails."

If the roadmap is narrower than this prompt, implement the narrower roadmap.

If a required policy choice is missing, STOP AND ASK rather than inventing
one.

Examples of choices that must not be guessed:

- reject vs. replace with abstention
- redact vs. reject
- whether every non-abstaining answer must contain a citation
- whether every sentence must be cited
- how malformed-but-recognizable citations are treated
- whether unsupported citations are removed or fail the entire answer
- whether uncited numerical claims are blocked
- whether PII/secret-looking output is rejected or redacted
- whether the raw provider response remains available to diagnostics after
  a blocked answer
- whether structured SQL/tree answers pass through the same guard

---

# Reuse Existing Citation Semantics

The project already has citation parsing and citation-integrity history.

Inspect and reuse the existing implementation instead of creating a second
citation grammar.

Relevant history includes:

- Task 1.7 inline `[chunk_id]` citations,
- Task 1.7a citation-format correction,
- strict rejection of malformed/fullwidth/truncated citation forms,
- existing citation parser(s),
- existing citation-integrity evaluation utilities.

Do NOT relax citation syntax merely to improve guard pass rate.

Do NOT silently "repair":

```text
【chunk-id】
[chunk63]
[chunk_id: ...]
```

into a valid citation unless the authoritative Task 4.9 contract explicitly
authorizes repair.

A guard should validate the frozen contract, not rewrite model output to make
it appear compliant.

---

# Citation-to-Context Integrity

If the Task 4.9 roadmap requires citation validation, every emitted citation
must be checked against the evidence actually supplied to that generation
request.

At minimum determine from the existing generation contract:

```text
allowed citation identities
actual citations parsed from answer
unknown / out-of-context citations
duplicates
malformed citation attempts
```

Never validate a citation merely because the referenced chunk exists
somewhere in the global corpus.

The relevant set is the evidence supplied to the answer.

Do not permit the model to cite a chunk that was not in its context.

Reuse existing provenance rather than re-querying LanceDB.

---

# Abstention Semantics

The generation layer already supports abstention when evidence is
insufficient.

If Task 4.9 validates abstentions:

- preserve the frozen abstention semantics,
- do not require a citation for a legitimate abstention unless the roadmap
  explicitly says otherwise,
- do not convert a valid abstention into an error,
- do not fabricate a citation merely to satisfy a generic "citation
  required" rule.

Test valid abstention separately from invalid uncited substantive answers if
the roadmap distinguishes them.

---

# Grounding / Unsupported-Claim Checks

Only implement deterministic grounding checks explicitly required by
`PROJECT_EXECUTION.md`.

Do NOT introduce an LLM judge.

Do NOT implement semantic entailment with a new embedding/cross-encoder model
unless explicitly required.

If the roadmap requires only structural grounding checks such as:

```text
substantive answer must cite supplied evidence
all citations must belong to supplied evidence
```

then implement only those.

Do not pretend these structural checks prove every natural-language claim is
factually entailed.

Document that limitation accurately.

---

# Internal Prompt / Secret Leakage

If Task 4.9 explicitly requires leak prevention, validate the output against
the project's actual internal boundary.

Potential categories may include:

- system prompt leakage,
- raw provider metadata leakage,
- API key / authorization value leakage,
- internal filesystem path leakage,
- hidden prompt/context delimiter leakage.

These are examples only.

Do not implement them unless required by the authoritative task.

Never log the sensitive value while testing for its presence.

Use fake secrets in portable tests.

---

# PII / Advice / Scope in Output

Do NOT automatically duplicate Task 4.7's input checks onto model output.

If the authoritative Task 4.9 checklist explicitly requires output-side:

- PII checks,
- investment-advice language checks,
- domain-scope checks,

reuse the existing deterministic helpers where semantically appropriate.

If it does not require them, do not invent them.

SEC filing evidence can legitimately contain:

- names,
- phone numbers,
- email addresses,
- addresses,
- legal language,

so broad output blocking can create serious false positives.

Follow the exact roadmap policy.

---

# Output Mutation Policy

Default principle:

**validate, do not silently rewrite.**

Unless the authoritative roadmap explicitly authorizes sanitization:

- do not paraphrase generated answers,
- do not add missing citations,
- do not normalize citation syntax,
- do not remove unsupported sentences,
- do not redact arbitrary content,
- do not change numeric values,
- do not reorder citations,
- do not replace the provider's answer with a "fixed" answer.

On guard failure, use the exact frozen behavior:

- reject,
- safe fallback,
- abstention,
- or other explicitly-defined outcome.

If that behavior is not specified:

STOP AND ASK.

---

# Recommended Output-Guard Result Contract

Only if the repository does not already define an appropriate guard result,
prefer a small deterministic object consistent with Tasks 4.7/4.8, e.g.:

```python
OutputGuardDecision(
    allowed: bool,
    reason_code: str | None,
    detail: str | None,
)
```

or, if the frozen contract requires a safe replacement:

```python
OutputGuardResult(
    allowed: bool,
    release_text: str | None,
    reason_code: str | None,
    detail: str | None,
)
```

These names are examples only.

Follow existing repository style.

Do not introduce a broad generic framework unless Task 4.9 actually needs
one.

---

# Stable Reason Codes

Every implemented blocking outcome must use a stable machine-readable reason
code.

Potential examples — NOT pre-approved:

```text
missing_citation
unknown_citation
malformed_citation
output_contract_violation
sensitive_output_detected
internal_prompt_leak
```

Use only categories explicitly required by Task 4.9.

Do not build a long reason-code taxonomy because it looks production-like.

Task 4.8 is evidence that the authoritative roadmap may intentionally be
narrower.

---

# Integration Boundary

Output guarding must happen **after provider output exists but before the
answer is returned publicly**.

For the dense generation path, inspect
`MinimalGenerator._answer_with_diagnostics()` and integrate at the narrowest
boundary that preserves existing semantics.

Conceptually:

```text
retrieve
  -> context guard
  -> build prompt
  -> provider.generate()
  -> parse candidate answer/citations
  -> output guard
  -> public GenerationResult
```

Prove by synthetic tests:

```text
valid provider output
  -> output guard allows
  -> public result returned unchanged

invalid provider output
  -> output guard blocks
  -> invalid candidate text is not released through the public result
```

Do not call a real provider.

---

# Preserve Diagnostic Separation

If the code has an internal diagnostics method that retains provider
metadata, carefully distinguish:

```text
internal diagnostics
vs.
public answer contract
```

Do not leak a blocked raw answer through the public `GenerationResult`.

Do not destroy debugging provenance unless the frozen contract requires it.

If the roadmap does not specify whether blocked raw output remains in
internal diagnostics, inspect existing architecture and choose the least
invasive behavior; if this choice materially affects security or public API
semantics, STOP AND ASK.

---

# Structured SQL / Navigation Routes

Inspect whether XBRL and tree-navigation routes currently invoke a generation
provider.

Task 4.8 recorded that they currently answer deterministically and do not
have a generation-prompt orchestrator.

Therefore:

- do not force generated-output guard wiring into routes that produce no LLM
  output,
- do not invent a generation layer for XBRL/navigation merely so Task 4.9
  can "cover every route,"
- if deterministic route outputs are explicitly in Task 4.9 scope, validate
  them according to the roadmap's actual contract,
- otherwise document that output guard integration currently applies only to
  the generated dense path.

Do not overclaim coverage.

---

# Logging

Use `src.logging_utils`.

Prefer fields such as:

```text
event=output_guard_decision
allowed=true/false
reason_code=...
citation_count=...
unknown_citation_count=...
```

Do not log:

- full generated answer,
- full prompt,
- full retrieved context,
- API keys,
- authorization headers,
- raw provider response,
- secret-like values detected in output.

If a blocked answer contains sensitive material, logging the entire answer
would defeat the guard.

---

# Configuration

Only add Task 4.9 configuration if the authoritative roadmap requires it.

If configuration is needed:

- use `src.config`,
- do not scatter environment reads,
- do not invent threshold defaults,
- validate at load time,
- update `project_plan/CONFIGURATION.md`,
- update `.env.example` only with non-secret values and only if repository
  permissions permit.

If no runtime threshold is required, prefer no new config file merely for
symmetry.

---

# Error Policy

Separate:

```text
expected output guard failure
  -> normal safe result / decision

invalid guard configuration
  -> clear early configuration error

malformed provider response
  -> existing provider/generation contract error unless Task 4.9 explicitly
     assigns it to the output guard

unexpected internal bug
  -> must not silently become "output rejected"
```

Do not hide generation bugs behind a generic safety message.

---

# Determinism

The same candidate output + same supplied evidence + same configuration must
produce the same guard decision.

No random sampling.
No network calls.
No LLM judge.
No model inference.
No clock-dependent behavior.

Add deterministic repeated-decision tests for every implemented rule.

---

# Portable Test Requirements

Add focused portable tests for every actual Task 4.9 rule.

Where applicable, cover:

- valid cited answer allowed
- citations all belong to supplied context
- unknown/out-of-context citation blocked
- malformed citation behavior
- duplicate citation behavior
- valid abstention with zero citations
- substantive uncited answer behavior
- empty provider output behavior
- stable reason codes
- deterministic repeated decisions
- accepted answer preserved byte-for-byte
- blocked candidate answer not released publicly
- provider called exactly once before output validation
- output guard itself performs zero network/model calls
- fake secret/internal-prompt leak fixtures if required
- legitimate SEC language negative controls
- logging does not include raw blocked output
- route-specific behavior if multiple output types are in scope

Only implement tests for rules actually required by the authoritative
Task 4.9 contract.

---

# Static Safety Tests

Where useful, add source/AST checks proving the output guard module does not
import/call:

- OpenRouter
- Ollama
- `requests`
- `httpx`
- sentence-transformers
- torch
- LanceDB retrieval APIs
- protected TEST loaders

The guard consumes the candidate answer and evidence metadata already in
memory.

It must not independently retrieve or generate anything.

---

# Existing Citation Regression

Do not break the frozen citation contract.

Re-run all existing citation-format and citation-integrity tests.

Pay particular attention to historical failure forms already documented by
the project:

```text
fullwidth brackets
truncated chunk IDs
context-label imitation
unknown/out-of-context citations
```

The output guard should reinforce the selected contract, not alter the
parser to accept these forms unless the roadmap explicitly says otherwise.

---

# Results Artifact

Write a small tracked result summary following repository conventions,
likely:

`results/phase_4_9_output_guardrails_summary.json`

Use the repository's actual naming pattern if it differs.

Record at minimum:

- task
- status
- authoritative Task 4.9 checklist
- implemented checks
- reason codes
- failure behavior
- routes integrated
- citation contract reused
- deterministic behavior
- portable test results
- non-generation regression results
- paid API calls during Task 4.9 = 0
- protected TEST usage = 0/3
- files modified
- known limitations

Do not include:

- raw provider answers
- raw prompts
- retrieved context dumps
- API keys
- secret test values

---

# Documentation

Create/update task documentation consistent with current Phase 4 docs,
likely:

`project_plan/PHASE4_OUTPUT_GUARDRAILS.md`

Document:

- exact Task 4.9 roadmap checklist
- output-guard boundary
- implemented checks
- citation semantics
- reason codes
- failure/release behavior
- abstention handling
- integration location
- logging
- tests
- known limitations
- separation from Task 4.7 input guardrails
- separation from Task 4.8 context guardrails
- separation from the later API/deployment layer

Update `project_plan/REPOSITORY_STRUCTURE.md`,
`project_plan/CONFIGURATION.md`, or other docs only if implementation
actually changes those contracts.

---

# Progress.md

Only after implementation and validation pass, append a detailed Task 4.9
entry matching the existing style.

Record:

- objective
- authoritative Task 4.9 requirements
- any scope difference between this prompt and the roadmap
- implementation
- output checks
- reason codes
- citation validation
- abstention behavior
- failure/release semantics
- integration point
- routes covered
- tests
- regression commands
- paid API calls during Task 4.9 = 0
- protected TEST usage = 0/3
- known limitations
- Git commit
- final status
- exact next roadmap task from `PROJECT_EXECUTION.md`

Do not guess the next task.

Do not start it.

---

# Regression Gates

Before and after Task 4.9 verify:

- Task 4.1 normalization artifact unchanged
- Task 4.2 chunk artifact unchanged
- Task 4.3 embedding artifact unchanged
- Task 4.4 vector index unchanged
- Task 4.5 XBRL serving export unchanged
- Task 4.6 provider/model contract unchanged except explicit output-boundary
  wiring
- Task 4.7 input guard semantics unchanged
- Task 4.8 context guard semantics unchanged
- frozen Phase 3 retrieval/routing decisions unchanged
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

If another external-service marker can perform a network call or incur cost,
exclude it unless the authoritative task explicitly requires it.

Report deselections/skips honestly.

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
- result/docs/tests are small and trackable

Commit Task 4.9 as one coherent commit only after all gates pass.

Suggested commit message:

`Add production output guardrails`

Do not push unless current user/repository policy explicitly authorizes it.

---

# Stop Conditions

STOP and report rather than guessing if:

1. Task 4.8 is not actually complete.
2. `PROJECT_EXECUTION.md` defines Task 4.9 materially differently.
3. Required output policy is ambiguous.
4. Citation failure behavior is unspecified where a decision is required.
5. Reject vs. redact vs. abstain behavior is unspecified.
6. A new LLM judge/model/moderation service would be required.
7. A paid or external generation call would be required.
8. A real provider call appears necessary for validation.
9. Task 4.9 would require FastAPI/deployment work.
10. Output guarding would require reopening retrieval/routing decisions.
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

Do not mark Task 4.9 complete.

---

# Acceptance Criteria

Task 4.9 is COMPLETE only when the authoritative roadmap criteria pass and,
at minimum:

- output guardrail exists as a reusable production component
- guard executes after generation and before public release
- invalid output cannot be returned through the normal public answer path
- allowed output remains unchanged unless the frozen contract explicitly
  authorizes sanitization
- every implemented block has a stable machine-readable reason code
- citation validation reuses the frozen citation contract if required
- unknown/out-of-context citations are handled exactly as the roadmap
  specifies
- valid abstention semantics are preserved
- no citation repair is silently introduced
- no new LLM judge/model/network dependency is used
- behavior is deterministic
- portable tests cover every implemented output rule
- existing citation tests remain passing
- regression suites pass with `generation_api` excluded
- paid API calls during Task 4.9 = 0
- Tasks 4.1–4.8 remain intact
- protected TEST remains unopened at 0/3
- documentation and result summary are written
- Progress.md is updated honestly
- one coherent Task 4.9 commit is created

Then record:

`Task 4.9 — Output Guardrails — COMPLETE`

and identify the exact next roadmap task from
`project_plan/PROJECT_EXECUTION.md`.

Do not start the next task.
