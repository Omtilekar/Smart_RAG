# Task 1.7 — Minimal Generation Layer

You are working inside my SEC RAG repository.

Task file:

`task_1.7_minimal_generation_layer.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.7 — Minimal Generation Layer
```

Current status:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — COMPLETE
  1.6 Baseline Retriever           — COMPLETE
  1.7 Minimal Generation Layer     — CURRENT
```

Task 1.6 is the authoritative retrieval input to this task.

Current recorded Task 1.6 state:

```text
retriever:
BaselineRetriever.retrieve(question, k=5)

default k:
5

search:
exact cosine LanceDB

result fields:
rank
score
distance
chunk_id
document_id
text
cik
company
form_type
fiscal_year
source
source_filename
source_split
ordinal
token_count
chunk_config_hash
normalizer_version
normalization_build_sha256
development_manifest_sha256

vector returned:
NO
```

Current Phase 1 index/model provenance:

```text
chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

embedding model:
BAAI/bge-small-en-v1.5

embedding revision:
5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

index table:
chunks

index rows:
162,357

retrieval mode:
exact cosine

ANN indexes:
0
```

Do NOT begin Task 1.8.

---

# USER-APPROVED TASK 1.7 DECISIONS — FROZEN

The following decisions were explicitly approved before this prompt was drafted.

Do NOT ask again unless the actual repository materially contradicts them.

## Decision 1 — Generation Provider

Use:

```text
OpenRouter
```

for Phase 1 testing.

Important:

```text
OpenRouter is NOT a permanently frozen production provider.
The user explicitly intends to change the provider/model later.
```

Therefore:

- keep generation behind a small provider interface,
- do not couple retrieval/generation code to OpenRouter-specific concepts outside the provider adapter,
- do not scatter OpenRouter URLs, headers, or response parsing across the codebase,
- do not make OpenRouter the architectural definition of generation.

### Model selection is intentionally runtime-configurable

The user did NOT freeze one permanent model ID.

Use the existing configuration boundary:

```text
GENERATION_PROVIDER
GENERATION_MODEL
```

with:

```text
GENERATION_PROVIDER=openrouter
```

for this Phase 1 test.

Do NOT hardcode a repository-wide OpenRouter model default merely to make the smoke test run.

For the real API smoke test:

- if `GENERATION_MODEL` is already explicitly supplied by the user/process environment, use that exact value;
- record the exact model actually requested and the exact model/provider reported by the response if available;
- if no model is supplied, **STOP AND ASK ME** before making the live API call.

The implementation itself should support arbitrary OpenRouter model IDs through configuration.

## Decision 2 — Citation Format

Use inline chunk-ID citations in the answer:

```text
[chunk_id]
```

Example:

```text
Revenue increased during the year. [1158114_2016.htm::chunk106]
```

The public generation result must expose:

```text
answer: str
citations: list[str]
```

where `citations` is parsed from the inline markers in answer order, with duplicate handling defined explicitly by the implementation contract.

Do NOT invent human-readable filing citations yet.

Do NOT replace chunk IDs with company/year-only citations.

Task 1.8 will perform citation-integrity checking.

## Decision 3 — Unsupported-Answer Behavior

The model must answer only from the supplied retrieved chunks.

If the supplied context does not support an answer:

```text
ABSTAIN
```

using a concise natural-language statement that there is not enough information in the provided context.

Requirements:

- no invented answer,
- no outside knowledge,
- no invented citation,
- no forced citation on an abstention.

Do NOT tell the model to "make the best guess."

## Decision 4 — Generation Randomness

Use the lowest deterministic setting supported by the selected OpenRouter model/API.

Preferred:

```text
temperature = 0
```

when supported.

If the selected model/provider does not support `temperature=0`, use the closest supported deterministic mechanism allowed by the provider/model and record the actual request parameters.

Do NOT silently use normal/default sampling when a deterministic control is available.

---

# CRITICAL RULE — DO NOT ASSUME

If any implementation decision is not clearly resolved by:

1. the actual repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_RETRIEVER.md`,
4. current configuration documentation,
5. current generation-provider documentation/API behavior,
6. current installed dependencies,
7. current code/tests,

then:

**STOP AND ASK ME.**

Do not silently choose:

```text
a specific OpenRouter model
an OpenRouter endpoint from memory
an SDK vs raw-HTTP implementation if the choice requires a new dependency
a retry policy
a timeout
max output tokens
citation deduplication semantics
provider error translation semantics
provider response-field assumptions
structured-output mode
streaming behavior
```

When asking:

- state exactly what is ambiguous,
- state what repository/provider evidence you found,
- give the smallest useful options,
- explain downstream behavior,
- wait for my answer.

Inspection first.

Assumption never.

---

# AUTHORITATIVE TASK PURPOSE

Task 1.7 adds the first grounded answer-generation layer on top of the working Task 1.6 retriever.

Pipeline:

```text
question
   ↓
Task 1.6 BaselineRetriever
   ↓
top-5 ranked chunks
   ↓
minimal grounded prompt
   ↓
OpenRouter provider adapter
   ↓
answer with inline [chunk_id] citations
   ↓
GenerationResult(answer, citations)
```

This task establishes only the crude Phase 1 generation baseline.

Task 1.8 will check citation integrity.

No evaluation dataset is built here.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify Task 1.6 is committed and healthy,
2. verify the retriever's default top-5 contract,
3. implement a small provider-neutral generation interface,
4. implement an OpenRouter adapter for Phase 1 testing,
5. keep provider/model configuration external and swappable,
6. build a minimal grounded prompt from the question + top-5 retrieved chunks,
7. require inline `[chunk_id]` citations,
8. instruct explicit abstention when context is insufficient,
9. use the lowest deterministic setting supported by the selected model,
10. parse citations from generated text,
11. expose a small typed `GenerationResult`,
12. keep generation callable independently from FastAPI,
13. add focused unit tests using fake providers,
14. perform a small live OpenRouter smoke test only when credentials/model are explicitly available,
15. record provider/model/request provenance and light latency diagnostics,
16. document the generation contract,
17. update `Progress.md`,
18. create one coherent Task 1.7 commit.

Do NOT begin Task 1.8.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -7
git tag --list
```

Verify:

```text
Task 1.6 committed
working tree clean except for intentional Task 1.7 prompt state
no Task 1.8 citation-integrity implementation already present
```

If unexplained changes exist:

**STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv`.

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Required:

```text
doctor PASS
portable suite 0 failures
```

Generation itself does not require CUDA, but Task 1.6 retrieval may use the existing GPU query encoder in the real end-to-end smoke path.

Do not change that behavior in this task.

---

# STEP 3 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_RETRIEVER.md
project_plan/PHASE1_VECTOR_INDEX.md
project_plan/PHASE1_EMBEDDINGS.md
project_plan/CONFIGURATION.md
project_plan/DEPENDENCIES.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/config.py
src/retrieval/baseline.py
src/generation/
src/logging_utils.py
scripts/smoke_retrieval.py
results/phase_1_6_retriever_summary.json
requirements.txt
requirements-dev.txt
.env.example
```

Use the actual repository state.

---

# STEP 4 — VERIFY TASK 1.6 RETRIEVER

Before generation work, verify:

```text
BaselineRetriever exists
default k = 5
real index provenance matches recorded Task 1.6 state
public retrieval result omits vector
retrieval result contains chunk_id + text + provenance
```

Run the existing real retrieval smoke if appropriate.

Do not rewrite Task 1.6.

Do not change retrieval scoring.

---

# STEP 5 — VERIFY CONFIGURATION BOUNDARY

Task 0.5 intentionally established:

```text
GENERATION_PROVIDER
GENERATION_MODEL
```

without storing provider API keys in `Settings`.

Keep that security boundary.

For Task 1.7:

```text
GENERATION_PROVIDER=openrouter
```

must be supported.

The live model ID must come from:

```text
GENERATION_MODEL
```

or another already-approved config mechanism.

Do not hardcode the testing model into source code.

Do not put a real API key into:

```text
src/config.py
.env.example
tracked config JSON
tests
Progress.md
logs
```

---

# STEP 6 — OPENROUTER CREDENTIAL

Use:

```text
OPENROUTER_API_KEY
```

from the process environment at provider-call time.

Do NOT add the credential to `Settings`.

Do NOT include it in object reprs.

Do NOT log it.

Do NOT write it to tracked files.

If the current OpenRouter API requires a different credential variable or authentication mechanism, verify current provider documentation before implementation.

Do not guess.

---

# STEP 7 — VERIFY OPENROUTER API CONTRACT

Before implementing the adapter, verify the current OpenRouter API contract from authoritative provider documentation or an already-installed, repository-approved client library.

Establish:

```text
base endpoint
authentication header
request schema
model field
messages/input schema
temperature/determinism controls
max-token parameter if needed
response text location
usage fields if available
reported model/provider metadata if available
error response structure
```

Do not copy API syntax from memory.

Do not assume OpenAI-compatible details without verification.

Document what was verified and from where.

---

# STEP 8 — DEPENDENCY DECISION

Inspect current dependencies.

If the repo already has a suitable HTTP/client dependency that can implement the provider cleanly, prefer minimal reuse.

If implementing OpenRouter cleanly requires adding a new direct dependency (e.g. an SDK):

**STOP AND ASK ME** before modifying requirement files.

Present:

```text
existing requests-based implementation
vs
new SDK dependency
```

with actual tradeoffs.

Do not add a provider SDK merely for convenience without approval.

---

# STEP 9 — PROVIDER-NEUTRAL INTERFACE

Implement a small provider abstraction under:

```text
src/generation/
```

Conceptually:

```python
class GenerationProvider(Protocol):
    def generate(self, request: ...) -> ...:
        ...
```

or an equivalent repository-consistent interface.

The abstraction should isolate:

```text
provider-specific URL
auth headers
provider request schema
provider response schema
provider errors
```

from the generic grounded-generation logic.

Do not build a plugin framework.

Do not build multi-provider routing.

We only need enough abstraction to replace OpenRouter later without rewriting retrieval or prompt construction.

---

# STEP 10 — OPENROUTER ADAPTER

Implement one OpenRouter adapter behind the provider-neutral interface.

A reasonable conceptual location:

```text
src/generation/openrouter.py
```

or a repo-consistent equivalent.

It must accept:

```text
model ID from config/runtime
API key from environment
generation request
```

and return a small provider-neutral response.

Do not instantiate or invoke the retriever inside the provider adapter.

---

# STEP 11 — GENERATION ORCHESTRATOR

Implement a separate grounded-generation boundary that composes:

```text
question
retriever
provider
```

Conceptually:

```python
class MinimalGenerator:
    def answer(self, question: str) -> GenerationResult:
        ...
```

or an equivalent simple function-based API if that fits repo style better.

Its flow:

```text
validate question
→ retrieve(question, k=5)
→ build grounded prompt
→ call provider once
→ parse inline chunk citations
→ return GenerationResult
```

Do not implement retries or multi-turn repair unless separately approved.

---

# STEP 12 — RETRIEVE EXACTLY TOP 5

Task 1.7 generation context uses:

```text
top 5 chunks
```

Call Task 1.6 with:

```python
retrieve(question, k=5)
```

explicitly or rely on its documented default in a way that is unambiguous.

Do not use 10.

Do not dynamically vary k.

Do not rerank.

Do not deduplicate chunks unless current repo already requires that.

---

# STEP 13 — CONTEXT FORMAT

Construct a minimal deterministic context block.

Each chunk must clearly expose at least:

```text
chunk_id
text
```

Useful provenance may also be shown to the model if it improves grounding without materially bloating the prompt, e.g.:

```text
company
fiscal_year
document_id
```

Do not silently invent a complex citation schema.

The model must have the exact chunk ID available verbatim so it can cite:

```text
[chunk_id]
```

If the exact context formatting is not already frozen and materially different reasonable formats exist:

choose the smallest clear deterministic format.

If formatting affects citation parseability or downstream behavior in a nontrivial way:

**STOP AND ASK ME.**

---

# STEP 14 — MINIMAL GROUNDED SYSTEM/PROMPT CONTRACT

The prompt must clearly instruct the model:

```text
Use only the supplied context.
Do not use outside knowledge.
Answer the user's question directly.
Cite every factual claim that relies on supplied context with [chunk_id].
Use only chunk IDs that appear in the supplied context.
If the context is insufficient, say there is not enough information in the provided context and do not invent an answer.
Do not invent citations.
```

Keep it minimal.

Do not add chain-of-thought instructions.

Do not ask the model to explain its reasoning process.

Do not ask it to browse.

Do not give it tools.

---

# STEP 15 — CITATION FORMAT

Allowed inline citation syntax:

```text
[<chunk_id>]
```

where Task 1.6 chunk IDs currently follow:

```text
<document_id>::chunk<ordinal>
```

Example:

```text
[1158114_2016.htm::chunk106]
```

The model should use exact supplied IDs.

Do not convert chunk IDs to URLs.

Do not fabricate accessions.

Do not introduce section IDs that do not exist in the Phase 1 schema.

---

# STEP 16 — CITATION PARSER

Implement a small deterministic parser for inline chunk-ID markers.

Input:

```text
answer text
```

Output:

```text
citations: list[str]
```

The parser must not invoke an LLM.

It must not normalize or rewrite IDs.

Define duplicate behavior explicitly.

Recommended simple behavior:

```text
preserve first occurrence order
deduplicate repeated identical chunk IDs
```

If current project docs specify another rule, follow them.

If duplicate semantics remain genuinely unresolved and affect Task 1.8:

**STOP AND ASK ME.**

Do not silently sort citation IDs alphabetically.

---

# STEP 17 — GENERATION RESULT TYPE

Expose a small typed result:

```text
answer: str
citations: list[str]
```

Optional diagnostic/provider metadata may exist in an internal result or separate diagnostic object if useful, but do not bloat the public Phase 1 answer contract.

Do not return:

```text
raw provider HTTP response
API key
full prompt
384-d retrieval vectors
```

Task 1.8 needs answer + citations.

---

# STEP 18 — ABSTENTION

The prompt must instruct explicit abstention when evidence is insufficient.

The public result for an abstention should have:

```text
answer: natural-language insufficiency statement
citations: []
```

unless the model legitimately cites context explaining why the requested fact is unavailable, which should not be forced.

Do not add a synthetic citation just to satisfy a non-empty-citation rule.

Do not fabricate supporting evidence.

---

# STEP 19 — DO NOT IMPLEMENT FULL CITATION INTEGRITY YET

Task 1.7 should:

```text
ask for citations
parse citations
return citations
```

Task 1.8 will systematically verify integrity.

Do NOT turn Task 1.7 into Task 1.8 by implementing a full citation validator or relevance/support grader.

However, do not hide malformed provider output.

If citation syntax cannot be parsed, surface that truthfully in the result or as a clear error according to the current result/error contract.

If exact behavior is undefined:

**STOP AND ASK ME.**

---

# STEP 20 — DETERMINISTIC GENERATION SETTINGS

Use the lowest deterministic setting supported by the selected model.

Preferred:

```text
temperature = 0
```

when valid.

Inspect the exact chosen OpenRouter model/provider behavior.

If temperature is unsupported or rejected:

use the provider/model's closest deterministic setting allowed by the user-approved rule and record what was actually sent.

Do not silently omit this and accept default sampling if deterministic control exists.

---

# STEP 21 — MAX OUTPUT TOKENS

Do not invent a permanent max-output-token value.

Search current Phase 1 docs/config.

If none is defined and the provider requires/strongly benefits from an explicit limit:

**STOP AND ASK ME.**

If the provider safely permits omission and current repo policy accepts provider default output length, document that actual behavior rather than pretending a project limit was frozen.

---

# STEP 22 — TIMEOUT / RETRY POLICY

Do not invent a production retry strategy.

Task 1.7 is a minimal baseline.

If the current HTTP/client stack has a repo-wide timeout convention, use it.

If no timeout exists and the provider call requires choosing one:

**STOP AND ASK ME.**

Do not automatically add exponential backoff, retry storms, or circuit breakers.

Phase 4 owns production resilience.

---

# STEP 23 — NO STREAMING

Use a simple non-streaming request for Phase 1 unless current docs already require streaming.

Do not build token streaming, SSE, callbacks, or async streaming here.

If the provider API defaults to streaming, explicitly request non-streaming behavior if supported.

---

# STEP 24 — REQUEST COUNT

One answer call should make:

```text
1 retrieval operation
1 provider generation request
```

Do not implement:

```text
self-reflection
citation repair call
answer verification call
multiple candidate generations
majority voting
```

Those are beyond the crude baseline.

---

# STEP 25 — LOGGING

Use:

```text
src.logging_utils
```

Log safe operational metadata such as:

```text
provider
model ID
retrieved chunk count
generation elapsed_ms
citation count
abstained yes/no if detectable
```

Do not log:

```text
OPENROUTER_API_KEY
authorization header
full prompt by default
full filing text
raw provider response containing user/context data
```

Do not log secrets even at DEBUG.

---

# STEP 26 — PROVIDER ERRORS

Translate provider/network failures into a small clear application-facing error type or existing repository error convention.

Do not expose:

```text
Authorization: Bearer ...
raw secret-bearing headers
```

If the provider returns:

```text
401/403
rate limit
invalid model
timeout
malformed response
```

surface a concise safe error.

Do not silently return an empty answer as success.

Do not retry unless approved.

---

# STEP 27 — LIVE MODEL CONFIGURATION

Before any real OpenRouter smoke call, inspect:

```text
GENERATION_PROVIDER
GENERATION_MODEL
OPENROUTER_API_KEY
```

Required:

```text
GENERATION_PROVIDER resolves to openrouter
GENERATION_MODEL is explicitly non-empty
OPENROUTER_API_KEY is explicitly non-empty
```

If model or credential is missing:

do not make a live call.

For tests, use fake providers.

For the task's real live smoke requirement:

if `GENERATION_MODEL` is missing, **STOP AND ASK ME** for the exact model.

Do not choose one from an OpenRouter leaderboard.

---

# STEP 28 — LIVE PROVIDER PROVENANCE

For each real smoke run record safely:

```text
requested provider
requested model
response-reported model if available
response-reported provider if available
temperature/determinism setting
request count
latency
usage tokens if available
```

Do not record the API key.

Do not store raw responses containing large context unless necessary.

---

# STEP 29 — UNIT TESTS

Add focused tests, e.g.:

```text
tests/test_minimal_generation.py
```

Use fake retriever/provider objects.

Cover:

```text
retriever called with k=5
provider called exactly once
question included
all five chunk IDs available to prompt
all five chunk texts available to prompt
grounding instruction present
outside-knowledge prohibition present
citation instruction present
abstention instruction present
GenerationResult answer
citation parsing
duplicate citation behavior
citation first-occurrence order
no vector dependence
empty/invalid question behavior
provider error propagation/translation
```

No network in portable tests.

No real API key.

---

# STEP 30 — OPENROUTER ADAPTER TESTS

Test provider request construction without live network where practical.

Verify:

```text
Authorization value built from env-provided fake key
model comes from config/runtime
deterministic setting included when configured
messages/input serialized correctly
response text extraction
safe handling of malformed response
API key never appears in repr/logged error
```

Use fake keys such as:

```text
test-key-not-real
```

Never a real secret.

If request mocking requires a new dependency:

**STOP AND ASK ME** before adding it.

Prefer lightweight injection/stdlib/existing tools.

---

# STEP 31 — CITATION PARSER TESTS

Use examples such as:

```text
"Revenue rose. [doc.htm::chunk1]"
→ ["doc.htm::chunk1"]

"A. [doc.htm::chunk1] B. [doc.htm::chunk2]"
→ ["doc.htm::chunk1", "doc.htm::chunk2"]

"A. [doc.htm::chunk1] B. [doc.htm::chunk1]"
→ first-occurrence deduplicated result if that policy is adopted
```

Verify unrelated square brackets are not accidentally parsed as chunk IDs.

Do not parse arbitrary markdown links as citations.

---

# STEP 32 — ABSTENTION TEST

Fake-provider response:

```text
"The provided context does not contain enough information to answer."
```

Expected:

```text
citations = []
```

Do not fail merely because an abstention has no citation.

---

# STEP 33 — REAL END-TO-END SMOKE

When:

```text
OPENROUTER_API_KEY present
GENERATION_MODEL explicitly supplied
```

run a small real smoke through:

```text
real Task 1.6 retriever
+
real OpenRouter provider
```

Use a small number of SEC-style questions, e.g. 3–5.

At least one should plausibly be answerable from retrieved context.

If practical, include one intentionally unsupported question to exercise abstention, but do not claim success solely from a subjective expectation.

Inspect:

```text
answer non-empty
citations parsed
citation syntax uses chunk IDs
no vector leaked
provider/model provenance recorded
```

Task 1.8 will determine citation integrity formally.

---

# STEP 34 — LIVE-SMOKE NETWORK POLICY

Unlike Tasks 1.3–1.6, the real generation smoke necessarily calls an external API.

This is allowed only for:

```text
OpenRouter generation requests
```

Do NOT:

```text
download data
download models
call SEC
browse the web
send raw frozen datasets elsewhere wholesale
```

Only the user's question and the top-5 retrieved chunk context needed for the test should be sent to the generation provider.

Document this boundary.

---

# STEP 35 — DATA-SENDING AWARENESS

The live provider call sends retrieved filing text to OpenRouter / the selected downstream model provider.

Do not send more context than the approved top 5 chunks.

Do not send:

```text
entire filing
embeddings
local filesystem paths
API secrets
unrelated data
```

Record that provider-bound context consists only of:

```text
question
top-5 chunk IDs/text/provenance needed by the prompt
```

---

# STEP 36 — PERFORMANCE DIAGNOSTICS

Measure lightweight real generation diagnostics.

Where practical:

```text
retrieval latency
generation API latency
total answer latency
```

For a tiny smoke set record:

```text
count
p50
p95
```

if the sample size is sufficient to make those labels meaningful.

Otherwise report individual/min/median/max values honestly.

Do not call this a production benchmark.

Provider latency is external and model-dependent.

Label:

```text
Phase 1 generation smoke diagnostic — NOT a production benchmark
```

---

# STEP 37 — COST / TOKEN USAGE

If OpenRouter returns token usage safely:

record:

```text
prompt/input tokens
completion/output tokens
total tokens
```

for the small smoke summary.

If the response includes cost directly and it is reliable, it may be recorded as informational.

Do not invent cost from a stale price table.

Do not web-scrape pricing in this task unless explicitly asked.

---

# STEP 38 — TRACKED SUMMARY

Create a small tracked summary under `results/`, likely:

```text
results/phase_1_7_generation_summary.json
```

subject to actual repository naming conventions.

Include:

```text
schema_version
provider
requested_model
response_reported_model if available
retriever_k
citation_format
abstention_policy
determinism/request parameters
live_smoke_performed
live_smoke_count
citation_parse counts
latency diagnostics
token usage if available
created_at_utc
```

Do not store:

```text
API key
authorization headers
large raw prompts
large full provider responses
```

If no live smoke was possible because the user had not supplied model/key, Task 1.7 should not falsely PASS its live integration criterion.

Follow the stop/ask rule.

---

# STEP 39 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_GENERATION.md
```

unless current naming conventions clearly specify another file.

Document:

## Purpose

First grounded API-generation baseline.

## Provider Abstraction

Explain that:

```text
OpenRouter is the Phase 1 testing provider
provider/model are intentionally replaceable
OpenRouter is not frozen as production architecture
```

## Runtime Configuration

Document:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=<user-selected OpenRouter model ID>
OPENROUTER_API_KEY=<process environment only>
```

Do not put a real key/model default where none was approved.

## Retrieval Context

```text
top 5 Task 1.6 chunks
```

## Prompt Contract

Document the grounding, citation, and abstention instructions.

## Citation Contract

```text
inline [chunk_id]
GenerationResult.citations parsed from inline markers
```

## Abstention

Explain unsupported answers must abstain.

## Determinism

Record actual provider/model parameter used.

## Public Result

```text
answer
citations
```

## Validation

Record unit tests + real smoke.

## Known Limitations

At minimum:

```text
single API request
OpenRouter testing provider only
model may change
no citation-integrity verification yet
no answer-quality evaluation yet
no retries
no streaming
no guardrails
no production resilience
```

## Next Task

Task 1.8 citation integrity smoke check.

---

# STEP 40 — UPDATE REPOSITORY STRUCTURE

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

only as needed to mark:

```text
src/generation/
```

implemented for the Phase 1 minimal baseline.

Do not rewrite unrelated architecture.

---

# STEP 41 — OPTIONAL SMOKE SCRIPT

Provide a thin real-smoke command, conceptually:

```bash
python scripts/smoke_generation.py
```

or repository-consistent equivalent.

It should:

1. load settings,
2. require provider=openrouter,
3. require explicit `GENERATION_MODEL`,
4. require `OPENROUTER_API_KEY`,
5. construct Task 1.6 retriever,
6. construct OpenRouter provider,
7. run a small fixed smoke set,
8. print concise answer/citations/provider/model/latency,
9. avoid printing full retrieved context unless explicitly in debug-safe mode,
10. exit non-zero on provider/parse/invariant failures.

Do not expose the key.

---

# STEP 42 — NO FASTAPI

Do not implement:

```text
HTTP endpoint
FastAPI route
streaming endpoint
request schema for production API
```

Task 4 owns serving.

Task 1.7 is library + smoke integration only.

---

# STEP 43 — NO GUARDRAILS

Do not implement full:

```text
input guardrails
context guardrails
output guardrails
PII policies
prompt-injection classifier
```

Phase 4 owns production guardrails.

The grounding prompt itself is part of minimal generation, not a full guardrail system.

---

# STEP 44 — NO CITATION GRADER

Do not implement:

```text
citation support scoring
entailment
chunk verification
citation precision/recall
```

Task 1.8 owns citation integrity smoke checking.

---

# STEP 45 — NO RETRIEVAL CHANGES

Do not change:

```text
k default in Task 1.6
embedding model
index metric
index structure
retrieval score
chunk schema
```

Generation consumes Task 1.6.

It does not redesign it.

---

# STEP 46 — NO EVAL SET

Do not build:

```text
~200 smoke questions
~3,000 evaluation set
DEV/TEST split
doc_recall@10
answer correctness metric
```

Those are later tasks.

---

# STEP 47 — SAFETY / UPSTREAM IMMUTABILITY

After Task 1.7 verify unchanged:

```text
Task 1.5 LanceDB index
Task 1.4 embeddings
Task 1.3 chunks
Task 1.2 normalized Markdown
frozen data/
```

Task 1.7 is read-only with respect to upstream local artifacts.

---

# STEP 48 — TEST SUITES

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required:

```text
0 failures
```

Use actual current test counts.

Do not hardcode 209 as the final total.

A live OpenRouter call should NOT be part of the default portable pytest suite.

If you add a live-provider test marker, it must require explicit capability and must not silently make network calls during ordinary tests.

---

# STEP 49 — LIVE TEST MARKER POLICY

If the existing testing conventions support a network/provider marker, use it.

If no marker exists and adding one is needed:

add the smallest explicit marker, such as conceptually:

```text
generation_api
```

but first inspect `pytest.ini` conventions.

The live test must:

- skip cleanly if the API key/model is absent,
- fail if credentials/model are present but the provider call is broken,
- never download anything,
- never print the key.

However, task completion itself still requires the explicit real smoke described above once model/key are supplied.

---

# STEP 50 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected trackable files may include:

```text
src/generation/...
scripts/smoke_generation.py
results/phase_1_7_generation_summary.json
tests/test_minimal_generation.py
project_plan/PHASE1_GENERATION.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
.env.example if only placeholder variable names are added
requirements files only if a dependency change was explicitly approved
prompt file if prompts are tracked
```

Do not stage:

```text
.env
API keys
raw provider transcripts with sensitive context
large result dumps
model cache
artifacts/
```

Run the normal secret/personal-path scan.

---

# STEP 51 — UPDATE .env.example

If not already present, document variable names only:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=
OPENROUTER_API_KEY=
```

But first inspect current `.env.example`.

Do not overwrite unrelated values.

Do not put a real model ID into `GENERATION_MODEL` unless explicitly approved as a tracked default.

Do not put a real key into the file.

If existing repo policy intentionally excludes secret variable names from `.env.example`, follow that policy instead.

---

# STEP 52 — UPDATE Progress.md

Preserve all history.

Append:

```markdown
## YYYY-MM-DD — Phase 1.7 Minimal Generation Layer
```

Use the current local date.

Include:

### Objective

Explain Task 1.7 composes Task 1.6 top-5 retrieval with a replaceable API generation provider.

### Initial State

Record:

```text
Task 1.6 commit
retriever module/API
index/model provenance
test baseline
```

### Frozen User Decisions

Record:

```text
provider: OpenRouter for testing, replaceable later
model: runtime-configurable, no permanent hardcoded model
citation format: inline [chunk_id]
public citations list: parsed from inline markers
unsupported answer: abstain
randomness: lowest deterministic supported; temperature=0 when supported
```

### Provider Contract

Record:

```text
provider adapter module
auth env var name
requested model
response-reported model/provider if available
request endpoint/interface actually used
```

Never record key value.

### Prompt Contract

Record exact grounding/citation/abstention behavior.

### Result Contract

Record:

```text
answer
citations
```

and citation parser duplicate semantics.

### Live Smoke

Record:

```text
model
question count
answers returned
citation parse status
abstention behavior if exercised
```

Do not paste large context.

### Performance

Record:

```text
retrieval latency
provider latency
total latency
token usage if available
```

Label:

```text
Phase 1 smoke diagnostic — not production benchmark
```

### Tests

Record:

```text
new Task 1.7 tests
doctor
portable suite
full suite
live provider smoke
```

### Safety

Confirm:

```text
no secret committed/logged
upstream artifacts unchanged
only top-5 chunk context sent to provider
no FastAPI
no citation grader
no eval set
```

### Files Created / Modified

List actual tracked files only.

### Git

Record Task 1.7 commit details.

### Result

Use exactly one:

```text
PASS — minimal grounded API generation layer implemented and live-smoked

WARN — generation layer implemented with one documented non-blocking issue

BLOCKED — generation layer could not be established safely
```

### Phase Status

If PASS:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — COMPLETE
  1.6 Baseline Retriever           — COMPLETE
  1.7 Minimal Generation Layer     — COMPLETE
  1.8 Citation Integrity Smoke     — NEXT
```

---

# STEP 53 — COMMIT TASK 1.7

After:

```text
provider abstraction works
OpenRouter adapter works
real OpenRouter smoke succeeds with explicit model/key
citation parsing works
abstention contract is tested
portable/full tests pass
secret scan passes
Progress.md updated
```

create one coherent Task 1.7 commit.

Preferred message:

```text
Add minimal grounded generation layer
```

or concise equivalent consistent with `GIT_CONVENTIONS.md`.

Do not include Task 1.8 work.

Do not tag Phase 1 yet.

---

# STEP 54 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

Do not invent one.

If authorization is ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.7 is complete only if:

```text
[ ] Task 1.6 commit verified
[ ] Task 1.6 real retriever verified
[ ] top-5 retrieval contract preserved

[ ] provider-neutral generation interface implemented
[ ] OpenRouter adapter implemented
[ ] OpenRouter-specific details isolated to provider adapter
[ ] provider can be changed later without rewriting retriever/orchestrator

[ ] GENERATION_PROVIDER=openrouter supported
[ ] GENERATION_MODEL runtime-configurable
[ ] no permanent model ID silently hardcoded
[ ] OPENROUTER_API_KEY read from environment only
[ ] API key absent from Settings/repr/logs/tracked files

[ ] current OpenRouter API contract verified from authoritative behavior/docs
[ ] no provider endpoint/request schema guessed from memory
[ ] no unapproved new dependency

[ ] minimal generator composes question + Task 1.6 top-5 chunks
[ ] one retrieval call per answer
[ ] one provider call per answer
[ ] no reranking/routing/retrieval redesign

[ ] prompt says use only supplied context
[ ] prompt prohibits outside knowledge
[ ] prompt requires exact inline [chunk_id] citations
[ ] prompt prohibits invented citations
[ ] prompt requires abstention when unsupported

[ ] public result exposes answer
[ ] public result exposes citations
[ ] citations parsed deterministically
[ ] vector not exposed
[ ] raw provider response not exposed as public result

[ ] deterministic generation setting resolved
[ ] temperature=0 used when selected model supports it
[ ] actual generation parameters recorded

[ ] abstention tested
[ ] abstention may return zero citations
[ ] no synthetic citation forced

[ ] focused Task 1.7 unit tests added
[ ] OpenRouter adapter request/response tests added
[ ] citation parser tests added
[ ] no live network in portable tests
[ ] doctor passes
[ ] portable suite has zero failures
[ ] full suite has zero failures

[ ] real OpenRouter smoke performed with explicit model
[ ] exact requested model recorded
[ ] response model/provider metadata recorded if available
[ ] smoke answers non-empty
[ ] citations parse where supplied
[ ] provider latency measured
[ ] no citation-integrity quality claim yet

[ ] only question + top-5 required context sent externally
[ ] index unchanged
[ ] embeddings unchanged
[ ] chunks unchanged
[ ] normalized Markdown unchanged
[ ] frozen data unchanged

[ ] no FastAPI
[ ] no streaming
[ ] no retries unless separately approved
[ ] no citation grader
[ ] no eval set
[ ] no guardrail system

[ ] PHASE1_GENERATION.md created
[ ] REPOSITORY_STRUCTURE.md updated where needed
[ ] Progress.md updated

[ ] secret scan clean
[ ] staged content reviewed
[ ] one coherent Task 1.7 commit created
[ ] no Task 1.8 work included
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.6 retriever differs from recorded provenance

GENERATION_MODEL is missing before the required live smoke

OpenRouter current endpoint/auth/request/response contract is unclear

a new provider SDK/dependency appears necessary

max output token policy requires a project decision

timeout requires a new project-wide decision

retry behavior would otherwise be invented

citation duplicate semantics materially affect Task 1.8 and are not resolved

provider returns malformed/unexpected citation behavior requiring a repair loop

selected model does not support the requested deterministic setting and the closest alternative is ambiguous

OpenRouter/provider terms require sending more information than the approved question + top-5 context

repo documentation materially conflicts

Git push authorization is unclear

any other durable implementation decision would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.7 does NOT:

```text
change retrieval
change embedding model
change index
change chunking
change normalized documents
add BM25
add metadata filters
add reranking
add CRAG
add routing
add SQL/XBRL answering
add tree navigation
add graph retrieval
verify citation integrity formally
score citation support
build eval questions
measure answer accuracy
build FastAPI
build streaming
build production retries
build production guardrails
freeze OpenRouter as the permanent provider
freeze one permanent generation model
```

The desired result is only:

```text
question
   ↓
Task 1.6 top-5 retrieval
   ↓
minimal grounded context
   ↓
replaceable generation provider
(OpenRouter for current testing)
   ↓
answer with inline [chunk_id]
   ↓
GenerationResult(answer, citations)
   ↓
Task 1.8
```

---

# FINAL RESPONSE TO ME

After completing Task 1.7, return:

## Task

```text
task_1.7_minimal_generation_layer.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input / Provenance

Report:

```text
Task 1.6 commit
retriever module/API
chunk_config_hash
embedding model/revision
index path/table
```

## Frozen Decisions

Confirm:

```text
provider = OpenRouter for testing
provider replaceable later = YES
model hardcoded = NO
citation format = inline [chunk_id]
unsupported answer = abstain
determinism = lowest supported
```

## Provider

Report:

```text
provider adapter module
API interface/endpoint verified
auth env-var name
requested model
response-reported model if available
response-reported provider if available
```

Never report the API key value.

## Generation API

Report actual:

```text
module
class/function
signature
```

## Prompt Contract

Summarize exact:

```text
grounding rule
citation rule
abstention rule
```

## Result Contract

Report:

```text
answer type
citations type
citation duplicate/order semantics
```

## Live Smoke

Report:

```text
questions tested
requested model
answers returned
citation parsing success
abstention case if tested
```

Do not paste long chunk text.

## Determinism Parameters

Report:

```text
temperature
other relevant generation parameters
reason if temperature=0 was unsupported
```

## Performance

Report:

```text
retrieval latency
provider latency
total latency
token usage if available
```

Label:

```text
Phase 1 generation smoke diagnostic — not production benchmark
```

## Tests

Report:

```text
new Task 1.7 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
live OpenRouter smoke PASS/FAIL
```

## Safety

Confirm:

```text
API key not logged/committed
only question + top-5 context sent to provider
index unchanged
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
data unchanged
no FastAPI
no citation grader
no eval set
```

## Files Modified

List actual tracked/project files only.

## Git

Report:

```text
commit created: YES/NO
commit hash
commit message
remote status
push performed: YES/NO
```

## Progress.md

Confirm:

```text
## YYYY-MM-DD — Phase 1.7 Minimal Generation Layer
```

was appended.

## Next Task

If PASS:

```text
task_1.8_citation_integrity_smoke.md
```

Do not start it.

Finally state:

```text
No Task 1.8 work started.
```

Stop and wait for my approval.
