# Task 1.8 — Citation Integrity Smoke

You are working inside my SEC RAG repository.

Task file:

`task_1.8_citation_integrity_smoke.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.8 — Citation Integrity Smoke
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
  1.7 Minimal Generation Layer     — COMPLETE
  1.8 Citation Integrity Smoke     — CURRENT
```

Do NOT begin Task 1.9.

---

# AUTHORITATIVE TASK 1.8 DEFINITION

`project_plan/PROJECT_EXECUTION.md` defines Task 1.8 as:

```text
- Confirm every cited chunk ID exists.
- Confirm citations refer only to chunks supplied to the generator.
- Fail clearly when the generator emits an unknown citation.
- Store source metadata needed to inspect citations manually.
```

Task 1.8 is a mechanical citation-integrity check.

It is NOT an answer-quality evaluator.

It is NOT an entailment/support grader.

It is NOT the ~200-question Task 1.9 evaluation.

---

# CURRENT TASK 1.7 CONTRACT

Task 1.7 is the authoritative generation input to this task.

Recorded Task 1.7 state:

```text
provider for Phase 1 testing:
OpenRouter

provider permanence:
replaceable later; OpenRouter is NOT frozen production architecture

runtime model used in Task 1.7 live smoke:
openai/gpt-oss-20b

model configuration:
GENERATION_MODEL runtime-configurable; no permanent tracked model default

generation API:
src/generation/provider.py
src/generation/openrouter.py
src/generation/citations.py
src/generation/minimal.py

public result:
GenerationResult(
    answer: str,
    citations: list[str],
)

retrieval context:
Task 1.6 top-5 chunks

citation syntax requested from model:
[chunk_id]

citation parser:
strict
first-occurrence order
duplicate IDs removed

unsupported-answer policy:
explicit abstention
no forced citation

generation randomness:
temperature=0.0 for the Task 1.7 model
stream=false
```

Task 1.7 live smoke also exposed real citation-format failures that Task
1.8 is specifically expected to investigate rather than hide:

```text
fullwidth brackets:
【1158114_2016.htm::chunk106】

truncated ID:
[chunk63]

previous context-label imitation:
[chunk_id: 1158114_2016.htm::chunk106]
```

Task 1.7 deliberately rejected those malformed forms rather than silently
normalizing them.

Preserve that strictness.

---

# USER-APPROVED TASK 1.8 DECISIONS — FROZEN

These decisions were explicitly approved before this prompt was drafted.

Do NOT ask again unless the actual repository materially contradicts them.

## Decision 1 — Malformed Citation Attempts Fail

Task 1.8 must inspect the generated **answer text itself**, not merely trust:

```text
GenerationResult.citations
```

If the answer contains a citation-looking attempt that is not a valid
strict `[chunk_id]` citation, the case fails citation integrity.

Examples that must fail:

```text
【1158114_2016.htm::chunk106】
[chunk63]
[chunk_id: 1158114_2016.htm::chunk106]
```

Do NOT silently:

```text
convert fullwidth brackets to ASCII
expand truncated IDs
strip "chunk_id:"
guess the intended document ID
repair malformed citations
```

A malformed citation attempt is evidence of non-compliant output.

Record it truthfully.

## Decision 2 — Non-Abstaining Answer With Zero Valid Citations Fails

Mechanical policy:

```text
abstention + zero citations
    -> citation-integrity eligible to PASS

non-abstaining answer + >=1 valid citation
    -> eligible to PASS after existence/context checks

non-abstaining answer + zero valid citations
    -> FAIL
```

This does NOT mean Task 1.8 judges whether every factual claim is
semantically supported.

It only enforces the Phase 1 output contract that a substantive generated
answer uses supplied chunk-ID citations.

Do not invent citations on behalf of the model.

## Decision 3 — Live Smoke Size

Run exactly:

```text
10 deterministic live generation questions
```

Target composition:

```text
8 ordinary SEC-style answerable smoke questions
2 intentionally unsupported / abstention controls
```

This is deliberately small.

Do not expand it into Task 1.9's ~200-question evaluation.

Do not spend API credits on a large sample merely to make Task 1.8 look
statistically rigorous.

---

# CRITICAL RULE — DO NOT ASSUME

If an implementation decision is not clearly resolved by:

1. the actual current repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_GENERATION.md`,
4. `project_plan/PHASE1_RETRIEVER.md`,
5. current Task 1.7 code/tests/results,
6. current Task 1.5 index code/schema,
7. the three frozen decisions above,

then:

**STOP AND ASK ME.**

Do not silently choose:

```text
an abstention-classification heuristic
a new citation syntax
a citation-repair strategy
a semantic citation-support model
a fuzzy chunk-ID matcher
an unknown-ID fallback
a different generation model
a new live-question count
a new provider
a new retry policy
a new prompt format
```

When asking:

- state exactly what is ambiguous,
- state what repository evidence you found,
- present the smallest useful options,
- explain downstream behavior,
- wait for my answer.

Inspection first.

Assumption never.

---

# IMPORTANT ABSTENTION NOTE

Task 1.7's public result is:

```text
answer
citations
```

and may not expose a machine-readable:

```text
abstained: bool
```

Before implementing Task 1.8, inspect the actual Task 1.7 code.

If there is already a reliable machine-readable abstention signal:

use it.

If there is NOT one:

do NOT invent a broad phrase classifier such as:

```text
"if answer contains 'not enough' then abstained=True"
```

without approval.

For the two deliberately unsupported live control cases, it is acceptable
to record the expected mode as:

```text
expected_behavior = "abstain"
```

and manually inspect the generated answer as part of the smoke review.

However, if automated PASS/FAIL of the abstention language itself requires
a new heuristic or upstream `GenerationResult` contract change:

**STOP AND ASK ME.**

Task 1.8's citation checker should remain mechanical.

---

# PURPOSE

Pipeline position:

```text
question
   ↓
Task 1.6 retrieval
   ↓
exact top-5 supplied chunks
   ↓
Task 1.7 generation
   ↓
answer text + parsed citations
   ↓
Task 1.8
citation-attempt detection
citation existence check
citation supplied-context check
source metadata capture
   ↓
PASS / FAIL per smoke case
```

The core invariant is:

```text
every valid citation emitted by the model
must resolve to a real stored chunk
AND
must have been among the exact chunks supplied to that generation call
```

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify Task 1.7 is committed,
2. verify Task 1.7 generation and Task 1.6 retrieval contracts,
3. implement strict citation-attempt inspection,
4. detect malformed citation attempts in answer text,
5. verify parsed citations exactly agree with strict answer parsing,
6. verify every valid citation exists in the real Task 1.5 `chunks` table,
7. verify every valid citation was in the exact top-5 context supplied to that generation call,
8. fail unknown citations clearly,
9. fail out-of-context-but-real citations clearly,
10. fail malformed citation attempts clearly,
11. fail non-abstaining substantive answers with zero valid citations,
12. allow legitimate abstention controls to have zero citations,
13. preserve source metadata needed for manual inspection,
14. run 10 deterministic live OpenRouter smoke cases,
15. record per-case PASS/FAIL reasons,
16. add focused automated tests with no network in portable mode,
17. document the citation-integrity contract,
18. update `Progress.md`,
19. create one coherent Task 1.8 commit.

Do NOT begin Task 1.9.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -8
git tag --list
```

Verify:

```text
Task 1.7 committed
commit message:
"Add minimal grounded generation layer"

working tree clean except for intentional Task 1.8 prompt state

no Task 1.9 evaluation implementation already present
```

Use actual Git state.

If unexplained changes exist:

**STOP AND ASK ME.**

Do not mix unrelated work into Task 1.8.

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

Do not make any live API call during portable tests.

Task 1.7 already established a `generation_api` marker.

Preserve that separation.

---

# STEP 3 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_GENERATION.md
project_plan/PHASE1_RETRIEVER.md
project_plan/PHASE1_VECTOR_INDEX.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/generation/provider.py
src/generation/openrouter.py
src/generation/citations.py
src/generation/minimal.py
src/retrieval/baseline.py
src/index/lancedb_index.py
scripts/smoke_generation.py
tests/test_minimal_generation.py
tests/test_openrouter_provider.py
tests/test_openrouter_live_smoke.py
results/phase_1_7_generation_summary.json
pytest.ini
scripts/dev.py
```

Do not reimplement behavior that already exists.

---

# STEP 4 — VERIFY TASK 1.7 CHECKPOINT

Verify from actual repo state:

```text
Task 1.7 commit exists
GenerationResult exists
answer is a string
citations is a list[str]
strict citation parser exists
OpenRouter adapter exists
MinimalGenerator retrieves top-5
temperature behavior matches recorded contract
```

Re-run current focused Task 1.7 unit tests if useful.

Do not modify Task 1.7 merely to make Task 1.8 easier unless necessary.

If a required observation cannot be obtained without changing the upstream
public contract:

**STOP AND ASK ME.**

---

# STEP 5 — VERIFY TASK 1.5 / 1.6 PROVENANCE

Expected current corpus/index identity:

```text
chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

LanceDB table:
chunks

rows:
162,357

search mode:
exact cosine

Task 1.6 default retrieval k:
5
```

Verify the real table is readable.

Do not rebuild it.

Do not modify it.

Task 1.8 needs ID existence lookup, not a new index.

---

# STEP 6 — IMPLEMENTATION LOCATION

Task 1.8 is evaluation/integrity logic.

Prefer implementation under:

```text
src/eval/
```

For example:

```text
src/eval/citation_integrity.py
```

or another repository-consistent name.

Do NOT put the integrity checker inside:

```text
src/generation/openrouter.py
src/retrieval/baseline.py
src/index/lancedb_index.py
```

Generation emits citations.

Task 1.8 evaluates their structural integrity.

Keep the boundary clean.

---

# STEP 7 — CITATION-INTEGRITY RESULT MODEL

Implement a small typed mechanical result representation.

Conceptually, a per-case result should distinguish:

```text
PASS
FAIL
```

and include machine-readable failure reasons.

Useful reason codes may include:

```text
malformed_citation_attempt
parsed_citation_mismatch
unknown_chunk_id
citation_not_in_supplied_context
missing_required_citation
```

Do not use vague single strings if structured reason codes are easy.

Do not add semantic-support reason codes.

No:

```text
citation_not_entailing_claim
answer_incorrect
```

Those are out of scope.

---

# STEP 8 — STRICT VALID CITATION SYNTAX

Reuse Task 1.7's actual strict citation parser/grammar.

Do not create a second incompatible definition of a valid citation.

Current valid shape is conceptually:

```text
[<document_id>::chunk<ordinal>]
```

Example:

```text
[1158114_2016.htm::chunk106]
```

Use exact parser behavior from `src/generation/citations.py`.

If Task 1.7 parser behavior differs from this recorded description:

follow the actual committed Task 1.7 code and document the discrepancy.

Do not silently rewrite history.

---

# STEP 9 — DETECT CITATION ATTEMPTS IN ANSWER TEXT

Task 1.8 must inspect answer text independently of
`GenerationResult.citations`.

Implement a narrow deterministic citation-attempt detector.

It should detect at least:

## Valid strict citation markers

```text
[1158114_2016.htm::chunk106]
```

## Known malformed citation-like markers

```text
【1158114_2016.htm::chunk106】
[chunk63]
[chunk_id: 1158114_2016.htm::chunk106]
```

The detector should be narrow enough not to classify ordinary markdown
brackets as citations merely because square brackets exist.

A reasonable rule is to treat bracketed text as a citation attempt when it
contains a chunk-like token such as:

```text
::chunk<digits>
chunk<digits>
chunk_id
```

using ASCII `[]` or the observed fullwidth `【】` form.

Then classify the attempt as valid only if the exact strict parser accepts
it.

Do NOT normalize malformed attempts before classification.

Do NOT make them valid after detection.

If designing a reliable narrow detector is still ambiguous after inspecting
Task 1.7's parser/tests:

**STOP AND ASK ME.**

---

# STEP 10 — MALFORMED ATTEMPTS ARE HARD CASE FAILURES

If:

```text
citation_attempt_detected == True
```

and:

```text
strict_valid_citation == False
```

then:

```text
case citation integrity = FAIL
reason = malformed_citation_attempt
```

Record the raw malformed marker exactly as emitted.

Do not repair it.

Do not drop it from the report.

Do not allow a case to PASS merely because the malformed attempt did not
appear in `GenerationResult.citations`.

This is the main reason Task 1.8 cannot trust the parsed citations list
alone.

---

# STEP 11 — RE-PARSE ANSWER INDEPENDENTLY

For each generation result:

```text
reparsed = parse_citations(answer)
```

Verify:

```text
reparsed == GenerationResult.citations
```

under Task 1.7's documented:

```text
first-occurrence order
deduplicate repeated IDs
```

If they differ:

```text
FAIL
reason = parsed_citation_mismatch
```

This detects integration regressions where the public citation list no
longer reflects the actual answer.

Do not silently trust either side.

---

# STEP 12 — CAPTURE THE EXACT SUPPLIED TOP-5

The check:

```text
citation was among chunks supplied to generator
```

must use the **exact retrieval results used by that same generation call**.

Do NOT simply run retrieval a second time after generation and assume the
result set was identical.

Preferred implementation if current `MinimalGenerator` construction allows
it:

```text
wrap/decorate the real retriever with a recording retriever
```

that:

1. delegates to the real Task 1.6 retriever,
2. records the exact returned `RetrievalResult` objects,
3. gives those same objects back to `MinimalGenerator`.

Then Task 1.8 knows the exact top-5 supplied set without modifying Task
1.6/1.7 public contracts.

If the actual committed implementation prevents this cleanly:

**STOP AND ASK ME** before changing Task 1.7.

Do not infer supplied context from a fresh second retrieval unless explicitly
approved.

---

# STEP 13 — SUPPLIED CONTEXT INVARIANTS

For every live generation call verify the captured supplied context:

```text
exactly 5 chunks
5 unique chunk_ids
every chunk_id non-empty
every document_id non-empty
every text non-empty
```

The set:

```text
supplied_chunk_ids
```

is the authoritative allowed-citation set for that answer.

Do not expand it with:

```text
other chunks from the same filing
same document IDs
nearest neighbors not sent
all corpus IDs
```

A citation is allowed only if its exact `chunk_id` was supplied.

---

# STEP 14 — VERIFY EVERY VALID CITATION EXISTS

For every strict parsed citation:

```text
chunk_id
```

verify it exists in the authoritative Task 1.5 `chunks` table.

Do not infer existence from format alone.

Do not infer existence because the document ID exists.

Required:

```text
exact chunk_id match in LanceDB
```

If not found:

```text
FAIL
reason = unknown_chunk_id
```

This is a hard failure required explicitly by `PROJECT_EXECUTION.md`.

The smoke script must make the failure clear.

---

# STEP 15 — ID LOOKUP MUST NOT USE VECTOR SEARCH

Existence checking is an identity lookup.

Use:

```text
exact chunk_id filter / scan / lookup
```

through the actual LanceDB API or a small reusable helper.

Do not:

```text
embed the citation
vector-search for it
fuzzy-match it
search by document_id only
```

If adding a small exact-ID lookup helper to `src/index/lancedb_index.py`
would be useful but is not already present, first determine whether it can
be implemented as a narrow non-breaking helper.

If the required change would alter Task 1.5's contract materially:

**STOP AND ASK ME.**

---

# STEP 16 — VERIFY EVERY VALID CITATION WAS SUPPLIED

For each valid citation:

```text
citation_id in supplied_chunk_ids
```

must be true.

If the citation exists in the global index but was not one of the exact
top-5 chunks given to the model:

```text
FAIL
reason = citation_not_in_supplied_context
```

This is a distinct failure from:

```text
unknown_chunk_id
```

Record the distinction.

Example:

```text
known real chunk
+
not supplied to current answer
=
out-of-context citation
```

Do not treat it as valid merely because it exists.

---

# STEP 17 — SOURCE METADATA FOR MANUAL INSPECTION

For every valid citation, store enough source metadata to trace it manually.

Prefer metadata already captured from the exact supplied
`RetrievalResult` when the citation was supplied.

At minimum preserve:

```text
chunk_id
document_id
company
form_type
fiscal_year
source
source_filename
source_split
ordinal
token_count
retrieval_rank
retrieval_score
retrieval_distance
```

Also preserve existing provenance hashes where practical:

```text
chunk_config_hash
normalizer_version
normalization_build_sha256
development_manifest_sha256
```

Do not fabricate:

```text
accession
section_id
section_title
```

because the Phase 1 chunk schema does not contain them.

If a citation is real but out-of-context, record its source metadata from
the index if practical so the failure can be inspected.

If a citation is unknown, metadata should be absent/null rather than
invented.

---

# STEP 18 — DO NOT STORE LARGE CONTEXT DUMPS BY DEFAULT

The tracked Task 1.8 report should remain small.

Do not store all five 512-token chunk texts for all 10 cases unless current
project docs explicitly require that.

The requirement is source metadata needed for manual inspection.

A bounded text excerpt may be stored only if useful and deterministic.

If used, keep it small and clearly diagnostic.

Do not create a multi-megabyte tracked report.

Full chunk text already exists in the LanceDB table.

---

# STEP 19 — NON-ABSTAINING ZERO-CITATION FAILURE

For a substantive/non-abstaining answer:

```text
len(valid_citations) == 0
```

must produce:

```text
FAIL
reason = missing_required_citation
```

Do not allow a normal answer to PASS merely because it emitted no unknown
citation.

This is a user-frozen rule.

---

# STEP 20 — ABSTENTION CONTROL CASES

Exactly 2 of the 10 live smoke cases should be intentionally unsupported
controls.

Their expected mode is:

```text
abstain
```

For citation integrity:

```text
0 valid citations
0 malformed citation attempts
0 unknown citations
```

is acceptable.

Do not force a citation.

Do not mark an abstention as citation failure solely because citations are
empty.

Manual inspection must confirm the answer is actually an insufficiency /
abstention response unless the existing Task 1.7 code exposes a reliable
machine-readable abstention signal.

Do not invent a broad text classifier without asking.

---

# STEP 21 — ABSTENTION WITH A CITATION

If an abstention response unexpectedly includes a valid supplied citation,
do not automatically fail solely because it has a citation.

The integrity questions remain mechanical:

```text
is citation syntactically valid?
does it exist?
was it supplied?
```

However, record the behavior for manual inspection.

Do not add semantic policy beyond the frozen zero-citation allowance.

---

# STEP 22 — DUPLICATE VALID CITATIONS

Repeated valid citations in answer text are NOT themselves an integrity
failure.

Task 1.7's parser already uses:

```text
first occurrence order
deduplicate identical IDs
```

Task 1.8 should verify that behavior rather than classify repetition as
unknown/malformed.

Example:

```text
[A::chunk1] ... [A::chunk1]
```

may yield:

```text
citations = ["A::chunk1"]
```

and still pass structural integrity if that chunk exists and was supplied.

---

# STEP 23 — MULTIPLE CITATIONS

A case with multiple valid citations passes only if EVERY citation:

```text
is strict-format valid
exists in index
was supplied to this generation call
```

One bad citation fails the case.

Do not pass a case by majority vote.

---

# STEP 24 — TEST UNKNOWN CITATION HANDLING SYNTHETICALLY

Unit tests must explicitly prove:

```text
syntactically valid but nonexistent chunk ID
```

fails clearly.

Example synthetic form:

```text
[does-not-exist_2099.htm::chunk999999]
```

Use fake/synthetic data in unit tests.

Do not insert fake rows into the real index.

Expected reason:

```text
unknown_chunk_id
```

---

# STEP 25 — TEST OUT-OF-CONTEXT REAL CITATION

Unit tests must distinguish:

```text
exists globally
but not supplied to generator
```

from unknown.

Use a tiny fake index/existence resolver with:

```text
known_ids = {A, B, C}
supplied_ids = {A, B}
citation = C
```

Expected:

```text
citation_not_in_supplied_context
```

Do not collapse both failure modes into a generic `invalid_citation`.

---

# STEP 26 — TEST MALFORMED OBSERVED FORMS

Add regression tests for the actual Task 1.7 observed failures:

```text
【1158114_2016.htm::chunk106】
[chunk63]
[chunk_id: 1158114_2016.htm::chunk106]
```

All must be detected as citation attempts.

All must fail strict integrity.

Do not "fix" them in the test fixture.

These regression cases are valuable because they came from real provider
behavior.

---

# STEP 27 — TEST ORDINARY BRACKETS

Ensure the malformed-attempt detector does NOT treat unrelated text such
as:

```text
[see note]
[2024]
[revenue]
```

as citation attempts merely because square brackets exist.

The detector should be narrow.

Do not create false failures from ordinary markdown.

---

# STEP 28 — 10-QUESTION LIVE SMOKE SET

Create one deterministic Task 1.8 live smoke set.

Exactly:

```text
10 questions
```

Composition:

```text
8 ordinary SEC-style expected-answerable questions
2 intentionally unsupported controls
```

Prefer to reuse stable Task 1.7 smoke questions where appropriate and add
only enough to reach 10.

Do not generate these questions with an LLM.

Do not call this an evaluation dataset.

Store the exact list in a small tracked config/result so the run is
reproducible.

A reasonable config shape:

```json
{
  "schema_version": 1,
  "questions": [
    {
      "id": "citation-smoke-01",
      "expected_behavior": "answer"
    },
    {
      "id": "citation-smoke-09",
      "expected_behavior": "abstain"
    }
  ]
}
```

Include actual question text in the real config.

If current repo convention prefers embedding the list in the smoke script,
follow established style, but a tracked config is preferred for explicit
reproducibility.

---

# STEP 29 — LIVE MODEL / PROVIDER

Use the existing Task 1.7 runtime configuration.

Expected testing provider:

```text
GENERATION_PROVIDER=openrouter
```

Use the current explicitly configured:

```text
GENERATION_MODEL
```

Do not permanently hardcode:

```text
openai/gpt-oss-20b
```

even though that was the Task 1.7 smoke model.

If the local `.env` currently still configures it, record the exact model
used.

If the model has intentionally changed, use the configured model and record
that fact.

If:

```text
GENERATION_PROVIDER
GENERATION_MODEL
OPENROUTER_API_KEY
```

are missing for the required live run:

**STOP AND ASK ME.**

Do not choose a replacement model.

---

# STEP 30 — LIVE NETWORK BOUNDARY

The only external network traffic permitted by the real Task 1.8 smoke is:

```text
the same OpenRouter generation request path established in Task 1.7
```

Do not:

```text
browse the web
call SEC
download models
download datasets
query OpenRouter model listings
```

unless explicitly required because current provider configuration is
broken and I approve it.

Only:

```text
question
top-5 generation context
```

should leave the machine as already established in Task 1.7.

---

# STEP 31 — ONE GENERATION PER CASE

For each of the 10 questions:

```text
1 retrieval
1 generation request
1 integrity evaluation
```

Do not add:

```text
retry-until-valid
citation repair
second LLM judge
self-correction
regeneration
```

If the model emits malformed/unknown citations:

record the failure.

That is the point of the smoke check.

---

# STEP 32 — NO CITATION REPAIR LOOP

Task 1.8 must NOT turn:

```text
bad citation
```

into:

```text
another API call asking model to fix it
```

Do not automatically rewrite Task 1.7's prompt based on failures.

If the smoke exposes a simple upstream generation bug that you believe must
be fixed before Phase 1 can continue:

**STOP AND ASK ME** before changing Task 1.7.

Do not weaken the validator to obtain a green result.

---

# STEP 33 — PER-CASE REPORT

For each live case record:

```text
case_id
question
expected_behavior
answer
parsed_citations
citation_attempts
malformed_citation_attempts
supplied_chunk_ids
citation_checks
case_status
failure_reasons
requested_provider
requested_model
response_reported_model/provider if available
```

For each valid citation check record:

```text
chunk_id
exists_in_index
was_supplied
source_metadata
```

Do not store:

```text
API key
authorization header
retrieval vectors
entire provider raw response
full five-chunk context dump
```

---

# STEP 34 — SUMMARY METRICS

Record simple descriptive counts only.

At minimum:

```text
total_cases = 10
passed_cases
failed_cases
answer_expected_cases = 8
abstention_control_cases = 2

cases_with_valid_citations
cases_with_malformed_attempts
cases_with_unknown_ids
cases_with_out_of_context_ids
cases_missing_required_citation

total_valid_citations
valid_citations_existing
valid_citations_supplied
```

Do not call these:

```text
citation precision
citation recall
faithfulness
groundedness
answer accuracy
```

unless those metrics are formally defined later.

This is a smoke diagnostic.

---

# STEP 35 — OVERALL LIVE-SMOKE STATUS

The live smoke itself passes only if all required integrity rules pass.

Conceptually:

```text
10/10 case integrity PASS
    -> live smoke PASS

any malformed citation attempt
or unknown citation
or out-of-context citation
or non-abstaining zero-valid-citation case
    -> live smoke FAIL
```

The smoke script should exit non-zero on live integrity failure.

Do not hide the failure behind an informational log.

---

# STEP 36 — TASK RESULT SEMANTICS

Distinguish:

```text
integrity checker implementation correctness
```

from:

```text
generation model citation compliance
```

Use these Task 1.8 outcomes:

```text
PASS
— integrity checker is correct AND the 10-case live smoke passes

WARN
— integrity checker is correct, tests pass, but the live model emits one
  or more correctly-detected citation-compliance failures

BLOCKED
— the checker cannot reliably determine citation existence/supplied-context
  membership, required infrastructure is broken, or safety/provenance is
  unresolved
```

A WARN is truthful completion of the smoke-check implementation.

Do NOT convert real model failures into PASS.

Do NOT call the task BLOCKED merely because the checker successfully found
a model citation failure.

If the current `PROJECT_EXECUTION.md` or repo conventions define different
task result semantics:

**STOP AND ASK ME.**

---

# STEP 37 — PHASE 1 STATUS AFTER WARN

If Task 1.8 ends WARN because the generator emits citation-integrity
failures:

do not silently claim the Phase 1 citation exit criteria are satisfied.

Record that:

```text
Task 1.8 implementation is complete
but Phase 1 citation compliance remains a documented warning
```

Then stop and wait for my decision before deciding whether Task 1.9 should
proceed unchanged or whether generation needs a targeted correction.

If Task 1.8 PASSes:

mark Task 1.9 as next normally.

---

# STEP 38 — TRACKED CONFIG

Create a small tracked Task 1.8 config if consistent with current project
conventions.

A reasonable name:

```text
configs/citation_integrity_smoke.json
```

Possible fields:

```text
schema_version
case_count = 10
answer_case_count = 8
abstention_case_count = 2
citation_format = "[chunk_id]"
malformed_attempt_policy = "fail"
unknown_id_policy = "fail"
out_of_context_policy = "fail"
non_abstaining_zero_citation_policy = "fail"
questions = [...]
```

Do not include:

```text
API key
hardcoded permanent generation model
```

Runtime provider/model provenance belongs in the result.

---

# STEP 39 — TRACKED RESULT

Create a small tracked result under the existing `results/` convention.

A reasonable filename:

```text
results/phase_1_8_citation_integrity_summary.json
```

It may contain:

```text
summary
+
10 small per-case records
```

as long as the file remains reasonably small.

If you prefer separate summary/detail files for clarity:

inspect current repository conventions first.

Do not create a large raw transcript archive.

---

# STEP 40 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_CITATION_INTEGRITY.md
```

unless current repository naming conventions clearly specify another file.

Document:

## Purpose

Mechanical structural citation integrity only.

## Valid Citation Syntax

Exact Task 1.7 strict `[chunk_id]` form.

## Integrity Rules

```text
malformed citation attempt -> fail
unknown chunk ID -> fail
real but unsupplied chunk -> fail
non-abstaining zero citation -> fail
legitimate abstention with zero citation -> allowed
```

## Existence Source

Task 1.5 LanceDB `chunks` table.

## Supplied-Context Source

Exact top-5 captured from the same Task 1.7 generation call.

## Malformed Attempt Detection

Document the narrow deterministic detector and the real observed regression
examples.

## Manual Inspection Metadata

List exactly what metadata is stored.

## Live Smoke

```text
10 cases
8 ordinary answer cases
2 abstention controls
provider/model actually used
```

## Result Meaning

Explain PASS/WARN/BLOCKED distinction.

## Known Limitations

At minimum:

```text
does not prove cited text supports the answer
does not prove answer correctness
does not require every factual clause to have its own citation
does not evaluate retrieval relevance
does not perform citation repair
only a 10-case smoke
generation provider/model can change later
```

## Next Task

Task 1.9 ~200-question smoke evaluation.

---

# STEP 41 — UPDATE REPOSITORY STRUCTURE

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

only as needed to mark the Task 1.8 `src/eval/` implementation.

Do not claim the broader Phase 2 evaluation system is implemented.

Be precise:

```text
citation-integrity smoke helper implemented
full eval/truth-contract system not yet implemented
```

---

# STEP 42 — TESTS

Add focused tests, for example:

```text
tests/test_citation_integrity.py
```

Portable tests must require no:

```text
GPU
real LanceDB
OpenRouter
API key
network
```

Use small fake supplied-context and existence resolvers.

Test at minimum:

```text
valid citation exists + supplied -> PASS
valid citation unknown -> FAIL unknown_chunk_id
valid citation exists but not supplied -> FAIL citation_not_in_supplied_context

fullwidth citation attempt -> FAIL
truncated [chunk63] -> FAIL
[chunk_id: ...] -> FAIL
ordinary [note] brackets ignored

GenerationResult.citations matches reparse -> PASS
mismatch -> FAIL parsed_citation_mismatch

non-abstaining zero citation -> FAIL missing_required_citation
abstention-control zero citation -> allowed under approved/manual contract

multiple all-valid citations -> PASS
one valid + one bad -> FAIL
duplicate valid citation -> not itself a failure

source metadata retained for valid citation
unknown citation metadata absent rather than fabricated
```

---

# STEP 43 — REAL INDEX INTEGRATION TEST

Where appropriate, add a marked local-data test that opens the real Task
1.5 `chunks` table and verifies:

```text
a known real chunk ID exists
a fabricated valid-format chunk ID does not exist
```

Do not invoke the generator.

Do not call the network.

Use the existing `local_data` marker conventions.

If the index is absent:

skip only according to current capability policy.

If the index exists but is broken:

FAIL.

---

# STEP 44 — LIVE GENERATION TEST POLICY

Do NOT put all 10 paid/live smoke calls inside the ordinary full pytest
suite.

Use the dedicated smoke script for the 10-case run.

If one small `generation_api` integration test already exists from Task
1.7, preserve it.

Do not create a 10-call pytest test that unexpectedly spends API credits
every time someone runs:

```bash
python -m pytest
```

The dedicated Task 1.8 smoke is an explicit command.

---

# STEP 45 — SMOKE SCRIPT

Create a dedicated command such as:

```bash
python scripts/smoke_citation_integrity.py
```

or repository-consistent equivalent.

It must:

1. validate Task 1.7/1.6/1.5 provenance,
2. require configured OpenRouter provider/model/key,
3. load the real retriever,
4. wrap/capture the exact retrieval context used by generation,
5. run exactly 10 configured questions,
6. call generation once per question,
7. inspect answer text for citation attempts,
8. reparse strict citations,
9. verify existence,
10. verify supplied-context membership,
11. record source metadata,
12. classify each case,
13. write the tracked summary/result,
14. print concise per-case result lines,
15. exit non-zero if the live smoke contains any integrity failure.

Do not print the API key.

Do not print five full chunks per case.

---

# STEP 46 — LIVE FAILURE OUTPUT

When a case fails, print a concise reason such as:

```text
FAIL citation-smoke-03:
malformed_citation_attempt="【1158114_2016.htm::chunk106】"
```

or:

```text
FAIL citation-smoke-04:
unknown_chunk_id="999999_2099.htm::chunk77"
```

or:

```text
FAIL citation-smoke-05:
citation_not_in_supplied_context="12345_2019.htm::chunk8"
```

or:

```text
FAIL citation-smoke-06:
missing_required_citation
```

Do not dump the raw provider HTTP response.

Do not hide the exact offending marker/ID.

---

# STEP 47 — MANUAL INSPECTION

Manually inspect all:

```text
10 live cases
```

because this is a smoke set, not a large benchmark.

For each case inspect:

```text
question
expected behavior
answer
citation attempts
parsed citations
supplied chunk IDs
citation metadata
integrity result
```

For the 2 abstention controls, manually confirm that the answer actually
behaves as an abstention if no reliable machine-readable abstention flag
already exists.

Do not judge deep semantic correctness.

The manual review question is:

```text
Does the structural citation-integrity classification look correct?
```

---

# STEP 48 — NO SEMANTIC SUPPORT GRADING

Task 1.8 must NOT decide whether:

```text
the cited chunk actually entails the claim
the answer is factually correct
the retrieved chunk is relevant
the model omitted a citation on one particular factual clause
```

Those require stronger evaluation methodology.

Do not add:

```text
LLM-as-judge
NLI model
cross-encoder support grader
citation precision/recall
faithfulness score
```

Mechanical integrity only.

---

# STEP 49 — NO RETRIEVAL CHANGES

Do not change:

```text
embedding model
query prefix
default k
index metric
exact-search mode
score transform
result schema
```

Task 1.8 observes the working Phase 1 pipeline.

It does not optimize retrieval.

---

# STEP 50 — NO GENERATION MODEL ABLATION

Do not compare multiple OpenRouter models.

Use the currently configured model once.

Do not turn citation integrity into a model benchmark.

Provider/model comparison belongs later if explicitly planned.

---

# STEP 51 — NO PROMPT ABLATION

Do not run several prompt variants to maximize citation compliance.

Use the committed Task 1.7 prompt.

If the Task 1.8 smoke exposes a clear need for a prompt correction:

record the evidence and **STOP AND ASK ME** before changing it.

---

# STEP 52 — NO TASK 1.9 EVAL

Do not:

```text
generate ~200 questions
calculate doc_recall@10
build evaluation truth
report retrieval metrics
```

Task 1.9 and Task 1.10 own those.

Task 1.8 remains exactly 10 live cases.

---

# STEP 53 — UPSTREAM IMMUTABILITY

After the smoke verify unchanged:

```text
Task 1.5 LanceDB index
Task 1.4 embeddings.parquet
Task 1.3 chunks.parquet
Task 1.2 normalized Markdown
frozen data/
```

Task 1.8 is read-only with respect to upstream artifacts.

The only generated/tracked outputs should be Task 1.8 code/docs/config/
summary.

---

# STEP 54 — SECURITY

Re-verify the Task 1.7 key boundary.

The real key belongs only in the ignored local `.env` / process
environment.

Never put it into:

```text
Task 1.8 config
Task 1.8 result
Progress.md
logs
test fixtures
prompt file
```

Run a secret scan before commit.

Pay special attention because Task 1.7 already recorded a caught
`.env.example` near-miss.

Do not rely on memory that it was fixed.

Verify again.

---

# STEP 55 — TEST SUITES

After implementation run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required for code correctness:

```text
0 failures
```

The 10-case live smoke is a separate explicit command.

If the live smoke returns non-zero due correctly-detected model citation
failures, do not misreport the pytest suite as failed.

Distinguish:

```text
unit/integration implementation tests
vs
live citation-compliance smoke
```

Use actual test counts.

Do not hardcode the previous 256 total.

---

# STEP 56 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected trackable Task 1.8 files may include:

```text
src/eval/citation_integrity.py
scripts/smoke_citation_integrity.py
configs/citation_integrity_smoke.json
results/phase_1_8_citation_integrity_summary.json
tests/test_citation_integrity.py
project_plan/PHASE1_CITATION_INTEGRITY.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
prompt file if prompts are tracked
```

Use actual final filenames.

Do not stage:

```text
.env
API key
LanceDB artifacts
embeddings
chunks
raw full provider transcript dumps
```

Run the normal personal-path scan too.

---

# STEP 57 — UPDATE Progress.md

Preserve all existing history.

Append:

```markdown
## YYYY-MM-DD — Phase 1.8 Citation Integrity Smoke
```

Use the current local date when the task is executed.

Include:

## Objective

Explain that Task 1.8 mechanically validates Task 1.7 chunk-ID citations
against the real Task 1.5 chunk store and the exact context supplied to the
same generation call.

## Initial State

Record:

```text
Task 1.7 commit
generation provider/model configuration
Task 1.6 retriever
Task 1.5 index/table
test baseline
```

## Frozen User Decisions

Record:

```text
malformed citation attempts fail
non-abstaining zero valid citations fail
live smoke = exactly 10 questions
8 ordinary + 2 abstention controls
```

## Integrity Contract

Record exact rules for:

```text
valid syntax
malformed attempts
unknown IDs
out-of-context IDs
zero citations
abstention controls
duplicate citations
```

## Implementation

Record:

```text
citation-integrity module
exact supplied-context capture method
index existence lookup method
```

## Live Smoke

Record:

```text
provider
requested model
response-reported model if available
10 cases
8 answer cases
2 abstention controls
passed/failed counts
```

List concise failure reasons.

Do not paste large answers/context.

## Citation Diagnostics

Record:

```text
cases with valid citations
malformed attempts
unknown IDs
out-of-context IDs
missing required citations
total valid citations
```

Do not call these scientific quality metrics.

## Manual Inspection

Record that all 10 cases were inspected structurally.

## Tests

Record:

```text
new Task 1.8 tests
doctor
portable suite
full suite
live smoke exit/result
```

## Safety

Confirm:

```text
API key absent from tracked files
index unchanged
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
data unchanged
no prompt/model ablation
no Task 1.9 work
```

## Files Created / Modified

List actual tracked files only.

## Git

Record Task 1.8 commit.

## Result

Use exactly one:

```text
PASS — citation-integrity checker implemented and 10-case live smoke passed

WARN — citation-integrity checker implemented; live generator produced one
or more correctly-detected citation-compliance failures

BLOCKED — citation integrity could not be determined safely
```

## Phase Status

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
  1.8 Citation Integrity Smoke     — COMPLETE
  1.9 200-Question Smoke Eval      — NEXT
```

If WARN because the live generator violated citation integrity:

record:

```text
1.8 implementation COMPLETE WITH WARN
Phase 1 citation compliance remains unresolved
```

and stop for my decision before silently proceeding.

---

# STEP 58 — COMMIT TASK 1.8

After:

```text
integrity checker implemented
focused tests pass
real 10-case smoke executed
results recorded truthfully
manual structural inspection completed
secret scan clean
upstream artifacts unchanged
Progress.md updated
```

create one coherent Task 1.8 commit.

Preferred message:

```text
Add citation integrity smoke check
```

or concise equivalent consistent with `GIT_CONVENTIONS.md`.

A live-smoke WARN due model citation output does NOT mean the checker code
should remain uncommitted.

Commit the truthful checker/results/docs if the implementation itself is
correct.

Do not include Task 1.9 work.

Do not tag Phase 1 yet.

---

# STEP 59 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

Do not invent one.

If push authorization is ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.8 implementation is complete only if:

```text
[ ] Task 1.7 commit verified
[ ] Task 1.7 strict parser reused
[ ] Task 1.6 top-5 retrieval contract verified
[ ] Task 1.5 chunks table verified

[ ] citation integrity helper implemented under appropriate eval boundary
[ ] answer text inspected independently of GenerationResult.citations
[ ] strict valid citation syntax reused from Task 1.7

[ ] valid citations reparsed from answer
[ ] public citations list checked against reparse
[ ] parsed-citation mismatch fails clearly

[ ] malformed citation-attempt detector implemented
[ ] fullwidth 【...】 observed form fails
[ ] [chunk63] observed form fails
[ ] [chunk_id: ...] observed form fails
[ ] ordinary unrelated brackets do not false-positive

[ ] exact top-5 supplied context captured from the same generation call
[ ] no second retrieval assumed to equal the first
[ ] supplied chunk IDs unique and validated

[ ] every valid citation checked for exact existence in LanceDB
[ ] unknown chunk ID fails clearly
[ ] no fuzzy matching
[ ] no ID repair

[ ] every valid citation checked against exact supplied top-5 IDs
[ ] real-but-unsupplied citation fails clearly
[ ] unknown and out-of-context are distinct failure modes

[ ] valid citation source metadata stored
[ ] no fabricated accession/section metadata
[ ] tracked report remains small

[ ] non-abstaining zero-valid-citation answer fails
[ ] abstention control may have zero citations
[ ] no forced citation on abstention
[ ] no unapproved abstention phrase classifier

[ ] exactly 10 live cases executed
[ ] exactly 8 ordinary answer cases
[ ] exactly 2 unsupported/abstention controls
[ ] one generation request per case
[ ] no citation repair/regeneration

[ ] per-case PASS/FAIL recorded
[ ] malformed/unknown/out-of-context/missing-citation counts recorded
[ ] all 10 cases manually inspected structurally

[ ] focused portable tests added
[ ] observed Task 1.7 malformed citation regressions covered
[ ] real-index existence integration test added where appropriate
[ ] no paid 10-call smoke hidden inside ordinary pytest
[ ] doctor passes
[ ] portable suite 0 failures
[ ] full suite 0 failures

[ ] live smoke exits non-zero if any integrity case fails
[ ] overall PASS only if 10/10 live cases comply
[ ] WARN used truthfully if checker works but generator fails citation rules
[ ] validator not weakened to manufacture PASS

[ ] no semantic entailment/support grader
[ ] no answer correctness scoring
[ ] no LLM judge
[ ] no retrieval changes
[ ] no prompt/model ablation
[ ] no Task 1.9 evaluation work

[ ] API key not logged/committed
[ ] only existing Task 1.7 provider boundary used
[ ] upstream index/embeddings/chunks/normalized/data unchanged

[ ] PHASE1_CITATION_INTEGRITY.md created
[ ] REPOSITORY_STRUCTURE.md updated narrowly
[ ] Progress.md updated

[ ] staged content reviewed
[ ] one coherent Task 1.8 commit created
[ ] no Task 1.9 work included
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.7 current code contradicts its recorded citation parser contract

the exact top-5 supplied to a generation call cannot be observed safely
without modifying Task 1.7's public contract

a machine-readable abstention decision requires inventing a text heuristic

the current configured generation model/provider is missing for the required
live smoke

citation syntax needs changing to make the model comply

a citation-repair/regeneration strategy seems necessary

LanceDB exact chunk-ID lookup requires a material Task 1.5 contract change

unknown citation handling is ambiguous

a real-but-unsupplied citation cannot be distinguished mechanically

a new dependency appears necessary

a prompt modification seems necessary to get the smoke to pass

the 10-case smoke emits failures and you are considering weakening the
validator or changing the model

repository documentation materially conflicts

Git push authorization is unclear

any other durable implementation decision would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.8 does NOT:

```text
prove citation semantic support
prove answer correctness
prove retrieval relevance
calculate faithfulness
calculate citation precision/recall
use an LLM judge
repair citations
normalize malformed citations
rerun generation until citations pass
change the generation model
compare generation models
tune the prompt
change retrieval
change embeddings
change the index
build the 200-question evaluation
calculate doc_recall@10
implement FastAPI
implement production guardrails
```

The desired result is only:

```text
Task 1.7 generated answer
        ↓
strict answer-text citation inspection
        ↓
does every citation exist?
        ↓
was every citation actually supplied?
        ↓
are there malformed citation attempts?
        ↓
does a substantive answer contain at least one valid citation?
        ↓
small traceable PASS/FAIL smoke report
```

---

# FINAL RESPONSE TO ME

After completing Task 1.8, return:

## Task

```text
task_1.8_citation_integrity_smoke.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input / Provenance

Report:

```text
Task 1.7 commit
generation provider
requested model
response-reported model if available
Task 1.6 retriever
Task 1.5 index/table/row count
chunk_config_hash
```

## Frozen Decisions

Confirm:

```text
malformed attempts fail = YES
non-abstaining zero citation fails = YES
live smoke count = 10
ordinary cases = 8
abstention controls = 2
```

## Integrity API

Report actual:

```text
module
public function/class
result/reason-code types
```

## Citation Syntax

Report exact strict valid syntax.

## Supplied-Context Capture

Explain exactly how the same generation call's top-5 chunk IDs were
captured.

## Existence Check

Explain exactly how chunk IDs were checked against the real LanceDB table.

## Live Smoke

Report:

```text
total cases
passed
failed
answer cases
abstention controls

cases with valid citations
cases with malformed citation attempts
cases with unknown IDs
cases with out-of-context IDs
cases with missing required citations
```

List concise failing case IDs/reasons if any.

Do not paste long answers.

## Manual Inspection

Confirm:

```text
10/10 cases structurally inspected
```

and note any abstention cases manually classified because no
machine-readable abstention signal existed.

## Source Metadata

List the metadata stored for citation inspection.

## Tests

Report:

```text
new Task 1.8 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
real index check PASS/FAIL
live smoke PASS/FAIL
```

## Safety

Confirm:

```text
API key not logged/committed
no citation repair
no prompt/model ablation
index unchanged
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
data unchanged
no Task 1.9 work
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
## YYYY-MM-DD — Phase 1.8 Citation Integrity Smoke
```

was appended.

## Next Task

If PASS:

```text
task_1.9_200_question_smoke_evaluation.md
```

Do not start it.

If WARN because live citation compliance failed:

state:

```text
Task 1.8 implementation is complete with WARN.
Phase 1 citation compliance remains unresolved.
No Task 1.9 work started pending user decision.
```

Finally state:

```text
No Task 1.9 work started.
```

Stop and wait for my approval.
