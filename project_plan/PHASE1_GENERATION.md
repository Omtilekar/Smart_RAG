# Phase 1 Minimal Generation Layer

**Phase 1 baseline generation contract.** Established in Task 1.7. The
first grounded answer-generation layer on top of the working Task 1.6
retriever: question → top-5 chunks → minimal grounded prompt → one
provider call → answer with inline `[chunk_id]` citations.

## Purpose

```text
question
  → Task 1.6 BaselineRetriever.retrieve(question, k=5)
  → minimal grounded prompt (question + 5 chunk blocks)
  → GenerationProvider.generate() — one call
  → inline [chunk_id] citations parsed from the answer
  → GenerationResult(answer, citations)
```

Task 1.8 checks citation integrity formally. Task 1.7 only asks for
citations, parses them, and returns them truthfully — it does not verify
that a citation actually supports its claim.

## Provider abstraction

**OpenRouter is the Phase 1 *testing* provider — not a frozen production
architecture.** The user explicitly intends to change provider/model
later. Accordingly:

- `src/generation/provider.py` defines a provider-neutral
  `GenerationProvider` protocol (`generate(GenerationRequest) ->
  ProviderResponse`), `GenerationRequest`/`ProviderResponse` dataclasses,
  and `GenerationError`.
- `src/generation/openrouter.py` implements `OpenRouterProvider` behind
  that interface — all OpenRouter-specific URLs, headers, request/response
  parsing, and error-code translation live only in this one file.
- `src/generation/minimal.py`'s `MinimalGenerator` (the orchestrator) and
  the prompt-construction logic know nothing OpenRouter-specific — they
  depend only on the `GenerationProvider` protocol, so swapping providers
  later means writing one new adapter file, not touching retrieval,
  prompt construction, or citation parsing.

## Runtime configuration

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=<user-selected OpenRouter model ID, e.g. "anthropic/claude-3-haiku">
OPENROUTER_API_KEY=<process environment / local .env only>
```

`Settings.generation_provider`/`Settings.generation_model` already existed
on `src/config.py` (Task 0.5) — reused unchanged, no new config field
added. **No model ID is a tracked project default** — `GENERATION_MODEL`
stays blank in `.env.example`, matching the user's explicit intent to
change it later, and `scripts/smoke_generation.py` refuses to run (never
guesses a model from a leaderboard) if it's unset.

**Security boundary preserved**: `OPENROUTER_API_KEY` is read directly
from `os.environ` at provider-call time inside `OpenRouterProvider.generate()`
only — never stored on `Settings`, never held on the provider instance
beyond the single call, never in `__repr__` (`OpenRouterProvider.__repr__`
shows only the model ID), never logged, never in a tracked file.

## OpenRouter API contract (verified from OpenRouter's own docs, not memory)

Verified directly against
`https://openrouter.ai/docs/api-reference/chat-completion` and
`https://openrouter.ai/docs/api-reference/authentication`:

```text
endpoint:        POST https://openrouter.ai/api/v1/chat/completions
auth header:        Authorization: Bearer <OPENROUTER_API_KEY>
content type:          Content-Type: application/json
request body:            {"model": str, "messages": [{"role","content"}, ...],
                        "temperature": float, "stream": false}
response text:              choices[0].message.content
response model (echo):        top-level "model" field
usage:                          top-level "usage": {prompt_tokens,
                              completion_tokens, total_tokens}
error codes:                      401 auth, 402 insufficient credits, 403
                                permissions/guardrail, 404 model not found,
                                429 rate limit, 500/502/503/524/529
                                server/upstream/timeout/overload
```

No `"provider"` field is documented in the base response schema — the
adapter reads `data.get("provider")` defensively and leaves
`response_provider = None` when it's actually absent, rather than
fabricating a value.

**Dependency decision**: implemented with `requests` (already a project
dependency, `requirements.txt`) via raw HTTP calls to the documented
endpoint — no OpenRouter SDK added. The request/response shape is simple
enough that a raw-HTTP implementation is the minimal-reuse option; adding
an SDK was not necessary and was not approved.

**Timeout**: 60 seconds, reusing the existing convention already
established in `src/ingest/common.py`'s `get()` for API-style requests
(distinct from that module's 300s file-download timeout) — not a newly
invented value.

**No retries, no streaming**: `stream: false` is sent explicitly (never
relies on the provider's implicit default). One provider call per
`answer()`, matching the Phase 1 baseline's "no self-repair, no multi-call
resilience" scope — Phase 4 owns production retry/resilience policy.

## Retrieval context

Exactly the Task 1.6 default: `retriever.retrieve(question, k=5)` — never
10, never dynamically varied, no reranking, no deduplication beyond what
Task 1.6 itself already guarantees (unique `chunk_id`s).

## Context format

One block per retrieved chunk, in retrieval rank order:

```text
[chunk_id: 1158114_2016.htm::chunk106]
Company: APPLIED OPTOELECTRONICS, INC. | Fiscal Year: 2016 | Document: 1158114_2016.htm
<chunk text>
```

`chunk_id` is shown verbatim so the model can cite it exactly;
company/fiscal_year/document_id are included as light grounding context
without materially bloating the prompt (no invented complex citation
schema).

## Prompt contract

```text
Use only the supplied context to answer the question. Do not use outside knowledge.
Answer the user's question directly.
Cite every factual claim that relies on the supplied context using the format
[chunk_id], using only chunk IDs that appear in the supplied context.
If the supplied context does not contain enough information to answer, say so
directly in one or two sentences and do not invent an answer or a citation.
```

Deliberately minimal — no chain-of-thought instruction, no reasoning
request, no tools, no browsing.

### Task 1.7a citation-format correction

Task 1.8 found citation-format compliance failures: `openai/gpt-oss-20b`
predominantly emitted fullwidth `【】` brackets (6/7 failures) instead of the
instructed ASCII `[]`, plus one truncated ID (`[chunk63]`). No
unknown-chunk-ID or out-of-context-citation failures were observed — the
retrieval → prompt → model grounding pipeline itself was already correct;
the defect was narrowly citation-output formatting.

Task 1.7a changed only the citation-format instructions in `SYSTEM_PROMPT`
(`src/generation/minimal.py`). Parser (`src/generation/citations.py`),
validator (`src/eval/citation_integrity.py`), provider, model, generation
settings, and retrieval stayed unchanged.

The corrected prompt explicitly requires:
- ASCII `[` `]` only,
- fullwidth `【` `】` explicitly forbidden,
- the complete Chunk ID copied exactly as supplied (no truncation),
- nothing else inside the brackets (no `chunk_id:` prefix or similar),
- one valid format example and three invalid examples (fullwidth, truncated,
  extra-text-in-brackets), explicitly labeled as formatting-only.

Rerunning the unchanged 10-case Task 1.8 smoke after this prompt-only
change: **8/10 passed** (up from the historical 3/10), 2 residual
`malformed_citation_attempt` failures (both still fullwidth `【】`), 0
unknown/out-of-context failures. Below the 10/10 threshold required to
unblock Task 1.9 — see `results/phase_1_7a_citation_format_correction_summary.json`
and `Progress.md`'s Task 1.7a entry for the full record and the pending
user decision.

## Citation contract

```text
format:      inline [chunk_id], e.g. [1158114_2016.htm::chunk106]
parser:         src/generation/citations.py: parse_citations(answer_text) -> list[str]
                regex requires the literal "::chunk<digits>" shape inside
                brackets (matching Task 1.6's exact chunk_id format), so
                arbitrary markdown links or unrelated bracketed text are
                never mistaken for citations - never invokes an LLM, never
                normalizes/rewrites an ID
duplicate policy:  first-occurrence order preserved, repeated identical
                chunk IDs deduplicated (the user-approved recommended
                default - no other project rule existed to override it)
```

## Abstention

```text
The model must answer only from supplied context.
If context is insufficient: a concise natural-language insufficiency
statement, citations = [] — never a forced/synthetic citation, never
invented supporting evidence.
```

## Public result

```python
@dataclass(frozen=True)
class GenerationResult:
    answer: str
    citations: list[str]
```

Never exposes: the raw provider HTTP response, the API key, the full
prompt, or retrieval vectors. Provider/timing metadata needed for
smoke-diagnostic reporting is available via
`MinimalGenerator._answer_with_diagnostics()` (documented as
diagnostic-only, not part of the public Phase 1 answer contract) rather
than bloating `GenerationResult` itself.

## Determinism

```text
temperature = 0.0, sent explicitly on every request (OpenRouter's
  documented request schema accepts temperature 0-2; 0 is the lowest/most
  deterministic value in that range and is honored uniformly through
  OpenRouter's normalization layer - not silently defaulted to unspecified
  sampling)
stream = false, sent explicitly (never relies on the implicit default)
```

## Validation

```text
unit tests (fake retriever/provider, no network):    46 tests across
  tests/test_minimal_generation.py (26) and
  tests/test_openrouter_provider.py (20 request/response/error-path
  tests using a monkeypatched requests.post and a fake, clearly-labeled
  key) - covers k=5 retrieval, exactly-one provider call, prompt content
  (question + all 5 chunk IDs/texts + grounding/citation/abstention
  instructions present), GenerationResult shape, citation parsing
  (ordering, dedup, non-citation brackets rejected), abstention (empty
  citations, non-empty answer), input validation, provider-error
  propagation, and API-key never appearing in repr/error messages
live integration test (tests/test_openrouter_live_smoke.py,
  generation_api-marked):                                 skips cleanly
  when OPENROUTER_API_KEY/GENERATION_MODEL are absent (confirmed - both
  were unset during this task, so it skipped); would fail (not skip) if
  both are present but the call is broken
```

## Known limitations

- Single API request per answer — no retries, no self-repair, no
  multi-candidate generation or voting.
- OpenRouter is a *testing* provider only — the user has stated intent to
  change it; no permanent generation model is frozen.
- No citation-integrity verification yet — Task 1.7 asks for and parses
  citations but does not check they actually support their claims. Task
  1.8 owns that.
- No answer-quality evaluation of any kind.
- No streaming, no FastAPI endpoint — library + smoke-script only.
- No production guardrails (PII policy, prompt-injection classification,
  full input/context/output guardrail stack) — the grounding prompt itself
  is part of minimal generation, not a guardrail system. Phase 4 owns
  production guardrails.

## Next task

Task 1.8 — Citation Integrity Smoke Check.
