# Task 1.6 — Baseline Retriever

You are working inside my SEC RAG repository.

Task file: `task_1.6_baseline_retriever.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.6 — Baseline Retriever
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
  1.6 Baseline Retriever           — CURRENT
```

Task 1.5 produced the authoritative LanceDB index consumed by this task.

Current recorded Task 1.5 state:

```text
chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

embedding model:
BAAI/bge-small-en-v1.5

embedding revision:
5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

embedding dimension: 384
vector dtype: float32
embedding normalization: L2-normalized
LanceDB: 0.37.1
table: chunks
rows: 162,357
search mode: exact / flat
distance metric: cosine
ANN indexes: 0
```

Do NOT begin Task 1.7.

# USER-APPROVED TASK 1.6 DECISIONS — FROZEN

## 1. Default retrieval k

Use `k=5` by default, but keep `k` caller-configurable.

Conceptually:

```python
retrieve(question, k=5)
```

Requirements:

```text
k must be a positive integer
default k = 5
Task 1.7 may use the default
Task 1.10 may explicitly request k=10
```

Do not hardwire the retriever so only 5 works.

## 2. Return both distance and score

Expose both:

```text
distance = raw LanceDB cosine _distance
score = 1.0 - distance
```

Semantics:

```text
distance: lower is better
score: higher is better
```

Do not clamp floating-point residuals.
Do not rename raw LanceDB distance to score.
Do not discard distance.

## 3. Retrieval result contents

Return:

```text
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
```

Do NOT return the 384-dimensional vector.

# CRITICAL RULE — DO NOT ASSUME

If an implementation decision is not clearly resolved by the actual repository,
`PROJECT_EXECUTION.md`, current Phase 1 documentation, current configs/results,
`src/embeddings/`, `src/index/`, or installed package behavior:

**STOP AND ASK ME.**

Do not silently choose defaults for:

```text
public result type
retriever class/function shape
model lifetime/loading
index-handle lifetime
batch-query support
long-query truncation
timing fields in public result objects
k > table-row behavior
```

When asking:
- state exactly what is ambiguous,
- state what repo evidence you found,
- present the smallest useful options,
- explain downstream impact,
- wait for my answer.

# PURPOSE

Implement the first natural-language retrieval path:

```text
question
  ↓
Task 1.4 BGE query encoder
  ↓
384-d normalized query vector
  ↓
Task 1.5 exact cosine LanceDB search
  ↓
ranked chunk results
```

The retriever must work independently from generation.

Task 1.7 will consume top-5 results.
Task 1.10 will later call with `k=10`.

# PRIMARY OBJECTIVES

1. Verify Task 1.5 checkpoint and index.
2. Reuse Task 1.4's exact BGE query encoder.
3. Implement reusable natural-language retrieval.
4. Keep `k` configurable with default 5.
5. Preserve exact-cosine search semantics.
6. Return rank, raw distance, derived score, text, and provenance.
7. Omit vectors from public results.
8. Validate query and output invariants.
9. Add focused tests.
10. Run real-corpus smoke retrieval.
11. Record lightweight timing diagnostics.
12. Document the contract.
13. Update `Progress.md`.
14. Create one coherent Task 1.6 commit.

Do NOT begin Task 1.7.

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -7
git tag --list
```

Verify Task 1.5 is committed and the tree is clean except for intentional Task 1.6 prompt state.

If unexplained changes exist: **STOP AND ASK ME.**

# STEP 2 — VERIFY FOUNDATION

Activate `.venv`.

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py gpu
```

Required: zero failures and a real CUDA PASS.

Do not silently fall back to CPU if the configured Phase 1 query path expects CUDA.

# STEP 3 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_EMBEDDINGS.md
project_plan/PHASE1_VECTOR_INDEX.md
project_plan/PHASE1_CHUNKING.md
project_plan/STORAGE.md
project_plan/CONFIGURATION.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/embeddings/bge.py
src/index/lancedb_index.py
src/storage.py
src/config.py
src/retrieval/
configs/embed_development_corpus.json
configs/build_vector_index.json
results/phase_1_4_embedding_summary.json
results/phase_1_5_vector_index_summary.json
tests/test_baseline_embeddings.py
tests/test_vector_index.py
```

Reuse actual existing interfaces.

# STEP 4 — VERIFY TASK 1.5 INDEX

Expected:

```text
table = chunks
rows = 162,357
metric = cosine
mode = exact
ANN indexes = 0
```

Verify the DB exists, table exists, count matches, required columns exist, and `list_indices()` is empty.

Do not rebuild or repair Task 1.5 here.

# STEP 5 — VERIFY TASK 1.4 QUERY CONTRACT

Use the existing query helper, not a new ad hoc prefix implementation.

Expected query convention:

```text
"Represent this sentence for searching relevant passages: "
```

Expected vector contract:

```text
dimension = 384
dtype = float32
normalize_embeddings = True
model = BAAI/bge-small-en-v1.5
revision = 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
```

Use offline/local-only loading.

If cached revision is ambiguous: **STOP AND ASK ME.**

# STEP 6 — PUBLIC RETRIEVER API

Implement one small public retrieval boundary under `src/retrieval/`.

A reasonable shape is:

```python
class BaselineRetriever:
    def retrieve(self, question: str, k: int = 5) -> list[RetrievalResult]:
        ...
```

A function-based equivalent is acceptable if clearly more consistent with current repo style.

Do not overengineer.

# STEP 7 — INPUT VALIDATION

Reject:

```text
non-string question
empty string
whitespace-only question
non-integer k
k <= 0
```

Do not silently coerce.

# STEP 8 — QUERY ENCODING

For one question, verify:

```text
shape = (1, 384)
float32
finite
normalized per Task 1.4
```

Use the query path exactly once.

Do not use passage encoding.

# STEP 9 — SEARCH

Reuse Task 1.5's exact-cosine search helper if possible.

Search:

```text
table = chunks
metric = cosine
mode = exact
limit = k
```

Do not add ANN, BM25, FTS, reranking, or metadata filtering.

# STEP 10 — RANK

Preserve LanceDB result order.

Expose:

```text
rank = 1, 2, ..., k
```

If current repo already freezes another rank convention, stop and ask.

# STEP 11 — DISTANCE / SCORE

For every row:

```python
distance = float(raw_distance)
score = 1.0 - distance
```

No rounding for internal representation.
No clamping.
No normalization across returned rows.

# STEP 12 — PUBLIC RESULT SCHEMA

Expose exactly:

```text
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
```

Do not expose `vector`.
Do not expose raw internal `_distance` in addition to `distance`.

# STEP 13 — RESULT TYPE

Use a small typed result representation consistent with repo style.

Prefer standard-library typing/dataclass unless current architecture clearly calls for something else.

Do not add a dependency solely for this result object.

# STEP 14 — RESULT INVARIANTS

For every result verify:

```text
rank >= 1
score finite
distance finite
chunk_id non-empty
document_id non-empty
text non-empty
form_type == "10-K"
chunk_config_hash matches current Phase 1
normalizer_version == "phase1-minimal-v1"
```

Do not fabricate accession or section fields.

# STEP 15 — k BEHAVIOR

Verify:

```text
retrieve(question) -> exactly 5 results
retrieve(question, k=10) -> exactly 10 results
```

If `k > table row count` behavior matters and is undefined, **STOP AND ASK ME.**

# STEP 16 — OBJECT LIFETIME

Do not reload BGE or reopen the DB unnecessarily for every call.

A retriever instance should normally reuse:
- query encoder/model
- LanceDB table handle

Reuse any existing project cache/lifetime mechanism rather than creating a conflicting one.

# STEP 17 — TESTABILITY

Keep the design easy to unit-test with small injected/fake encoder/search components.

Do not build a DI framework.

# STEP 18 — NO GENERATION COUPLING

Task 1.6 must not:
- format an LLM prompt,
- concatenate context for generation,
- call an LLM,
- require generation credentials.

Task 1.7 owns generation.

# STEP 19 — NO CITATION FORMAT YET

Preserve citation-relevant metadata, but do not invent final citation formatting.

Task 1.8 owns citation-integrity smoke checking.

# STEP 20 — NO ROUTING / FILTERING / RERANKING

Do not add:
- metadata filters,
- SQL/XBRL routing,
- tree routing,
- graph routing,
- BM25,
- FTS,
- reranking,
- CRAG.

Every Task 1.6 question uses the vector path only.

# STEP 21 — REAL-CORPUS SMOKE QUERIES

Use a small deterministic set of SEC-style smoke questions covering themes like:

```text
revenue
risk factors
net income
R&D
debt
dividends
```

These are smoke questions, not trusted eval questions.

For each, record only concise top-result metadata:
- chunk_id
- document_id
- company
- fiscal_year
- score
- distance

Do not claim relevance quality from subjective inspection.

# STEP 22 — TIMING DIAGNOSTICS

Measure lightweight real retrieval diagnostics.

Where practical separate:
- query embedding time
- exact search time
- total retrieve time

Record:
- query count
- k
- p50
- p95

Label explicitly:

```text
Phase 1 smoke diagnostic — NOT a production benchmark
```

# STEP 23 — DETERMINISM

Repeat the same question with the same `k`.

Verify:
- same chunk IDs,
- same order,
- same scores/distances within sensible float tolerance.

Do not claim cross-hardware bitwise determinism unless demonstrated.

# STEP 24 — UNICODE / LONG QUERY

Verify at least one Unicode query works.

Inspect current long-query behavior. If `src/embeddings/bge.py` already defines truncation, reuse it.

If long-query truncation would otherwise become an undocumented durable contract: **STOP AND ASK ME.**

# STEP 25 — IMPLEMENTATION LOCATION

Implement Task 1.6 under:

```text
src/retrieval/
```

Prefer a focused module such as:

```text
src/retrieval/baseline.py
```

Use a thin real-smoke script such as:

```text
scripts/smoke_retrieval.py
```

or a repo-consistent equivalent.

Do not add a FastAPI endpoint yet.

# STEP 26 — CONFIG

Create a Task 1.6 config only if current repo conventions require one.

If used, capture semantics such as:

```text
embedding_model
embedding_revision
chunk_config_hash
index_backend = lancedb
table_name = chunks
search_mode = exact
distance_metric = cosine
default_k = 5
score_transform = 1-distance
return_vector = false
```

Do not create a config merely for symmetry if no new runtime semantics need one.

# STEP 27 — TESTS

Add focused tests, e.g.:

```text
tests/test_baseline_retriever.py
```

Cover at minimum:

```text
default k=5
custom k=10
invalid k
empty query
query encoder called once
query path used, not passage path
search vector is 384-d
rank numbering
result order preserved
raw distance preserved
score = 1-distance
no clamping
vector omitted
approved metadata returned
Unicode query
```

Use small fake/injected components for portable tests where practical.

# STEP 28 — REAL MODEL/INDEX INTEGRATION TEST

Where appropriate, add a marked integration test requiring the actual:
- cached BGE model,
- GPU if current config requires it,
- Task 1.5 index.

It should retrieve one simple SEC query at `k=5`, verify 5 rows and public schema, and confirm vector omission.

Do not rebuild the index inside pytest.

Missing capability may skip only under the existing testing policy.
Present-but-broken capability must fail.

# STEP 29 — SCORE REGRESSION TEST

Use deterministic examples:

```text
distance 0.0    -> score 1.0
distance 0.25   -> score 0.75
distance 1.0    -> score 0.0
distance -1e-7  -> score 1.0000001
```

This protects the no-clamping rule.

# STEP 30 — SMALL TRACKED SUMMARY

Create a small tracked summary if consistent with current conventions, likely:

```text
results/phase_1_6_retriever_summary.json
```

Include:
- chunk_config_hash
- model/revision
- index path
- table
- search mode
- metric
- default_k
- score transform
- vector omitted
- smoke query count
- k values tested
- p50/p95 diagnostics
- determinism result
- created_at_utc

Do not store large retrieval dumps.

# STEP 31 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_RETRIEVER.md
```

Document:

## Purpose
Natural-language vector retrieval baseline.

## Query Pipeline

```text
question
→ BGE query convention
→ normalized 384-d float32 vector
→ exact cosine LanceDB search
→ ranked results
```

## Default k
`5`, caller-configurable; `k=10` supported.

## Distance / Score

```text
distance = raw LanceDB cosine distance, lower better
score = 1 - distance, higher better
```

No clamping.

## Result Schema
List every public field and state `vector` is omitted.

## Provenance
Record exact model, revision, chunk_config_hash, index path/table.

## Validation
Record default-k, k=10, input validation, determinism, real smoke, vector omission.

## Performance
Record p50/p95 as smoke diagnostics, not production benchmark.

## Known Limitations
- vector-only
- exact scan
- no BM25
- no hybrid
- no reranker
- no metadata prefilter
- no CRAG
- no router
- no generation
- no relevance evaluation yet

## Next Consumer
Task 1.7 minimal generation layer.

# STEP 32 — UPDATE REPOSITORY STRUCTURE

Update `project_plan/REPOSITORY_STRUCTURE.md` only as needed to mark `src/retrieval/` implemented.

# STEP 33 — REAL SMOKE COMMAND

Provide a documented command such as:

```bash
python scripts/smoke_retrieval.py
```

It should:
1. validate Task 1.5 provenance,
2. load BGE offline,
3. construct the retriever,
4. run deterministic smoke questions,
5. print concise result metadata and score/distance,
6. omit vectors,
7. record timing,
8. exit non-zero on invariant failure.

# STEP 34 — READ-ONLY SAFETY

Confirm unchanged:
- Task 1.5 index,
- Task 1.4 embeddings,
- Task 1.3 chunks,
- Task 1.2 normalized Markdown,
- frozen `data/`.

Retrieval is read-only.

# STEP 35 — NO NETWORK

No downloads.
No web.
No SEC calls.
No LLM calls.

# STEP 36 — RUN TEST SUITES

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required: zero failures.

Use actual current counts, not the previous 180.

# STEP 37 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected trackable files may include:

```text
src/retrieval/...
scripts/smoke_retrieval.py
configs/<Task 1.6 config>.json if needed
results/phase_1_6_retriever_summary.json
tests/test_baseline_retriever.py
project_plan/PHASE1_RETRIEVER.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
prompt file if tracked
```

Do not stage:
- model cache,
- LanceDB fragments,
- embeddings,
- large retrieval dumps.

Run secret/personal-path scan.

# STEP 38 — UPDATE Progress.md

Append:

```markdown
## YYYY-MM-DD — Phase 1.6 Baseline Retriever
```

Preserve prior history.

Include:

### Objective
Task 1.6 composes the Task 1.4 BGE query encoder with Task 1.5 exact cosine search.

### Initial State
Record Task 1.5 commit, index path, table, rows, model/revision, chunk_config_hash.

### Frozen User Decisions

```text
default k = 5, configurable
distance returned
score returned
score = 1-distance
vector omitted
```

### Retriever Contract
Record input, query encoding, search, and rank semantics.

### Result Schema
List exact public fields.

### Validation
Record default k, k=10, invalid inputs, score/distance, ordering, vector omission, smoke, determinism.

### Performance
Record p50/p95 and label as smoke diagnostic only.

### Tests
Record new tests, doctor, portable, full.

### Safety
Confirm index/embeddings/chunks/normalized/data unchanged; no network; no generation; no BM25; no reranker.

### Files Created / Modified
List actual tracked files only.

### Git
Record Task 1.6 commit.

### Result
Use exactly one:

```text
PASS — baseline natural-language vector retriever implemented
WARN — baseline retriever implemented with one documented non-blocking issue
BLOCKED — baseline retriever could not be established safely
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
  1.7 Minimal Generation Layer     — NEXT
```

# STEP 39 — COMMIT TASK 1.6

After real smoke passes, tests pass, safety checks pass, and docs are updated, create one coherent Task 1.6 commit.

Preferred message:

```text
Add baseline vector retriever
```

Do not include Task 1.7.

Do not tag Phase 1 yet.

# STEP 40 — PUSH POLICY

Inspect `git remote -v`.

If no remote exists:

```text
push deferred — no remote configured
```

If authorization is unclear: **STOP AND ASK ME.**

Never force-push.

# ACCEPTANCE CRITERIA

Task 1.6 is complete only if:

```text
[ ] Task 1.5 commit/index verified
[ ] chunks table exists with 162,357 rows
[ ] exact cosine contract preserved
[ ] ANN index count remains 0

[ ] Task 1.4 query encoder reused
[ ] exact BGE model/revision verified
[ ] query convention preserved
[ ] query vectors 384-d float32, finite, normalized
[ ] no passage encoder used for questions
[ ] no network download

[ ] natural-language retriever implemented
[ ] default k=5
[ ] configurable positive k
[ ] k=10 tested
[ ] invalid k rejected
[ ] empty query rejected

[ ] rank exposed
[ ] distance exposed
[ ] score exposed
[ ] score = 1-distance
[ ] no score clamping
[ ] result order preserved

[ ] required text/provenance returned
[ ] vector omitted
[ ] internal _distance not leaked as undocumented public field

[ ] default retrieval returns 5
[ ] k=10 returns 10
[ ] real smoke queries run
[ ] repeated query ordering stable

[ ] focused Task 1.6 tests added
[ ] real model/index integration test added where appropriate
[ ] doctor passes
[ ] portable suite 0 failures
[ ] full suite 0 failures

[ ] index unchanged
[ ] embeddings unchanged
[ ] chunks unchanged
[ ] normalized Markdown unchanged
[ ] frozen data unchanged

[ ] no metadata filters
[ ] no BM25/FTS
[ ] no reranker
[ ] no CRAG
[ ] no router
[ ] no generation
[ ] no eval metric

[ ] PHASE1_RETRIEVER.md created
[ ] REPOSITORY_STRUCTURE.md updated as needed
[ ] Progress.md updated
[ ] staged content reviewed
[ ] one coherent Task 1.6 commit created
[ ] no Task 1.7 work included
[ ] no force-push
```

# STOP CONDITIONS

STOP AND ASK ME if:

```text
Task 1.5 index differs from provenance
Task 1.4 model/revision is ambiguous
model cache is missing
query encoding differs from approved Task 1.4 behavior
long-query truncation becomes an undefined durable contract
result-type choice has material downstream consequences not resolved by current repo
k > table-row behavior becomes relevant and undefined
LanceDB exact cosine behavior differs from Task 1.5
distance semantics differ from Task 1.5
a new dependency appears necessary
repo docs materially conflict
Git push authorization is unclear
any other durable choice would require guessing
```

# IMPORTANT NON-GOALS

Task 1.6 does NOT:
- rebuild the index,
- re-embed passages,
- change chunking,
- change normalized docs,
- build BM25/FTS,
- build hybrid search,
- add metadata prefilters,
- rerank,
- implement CRAG,
- route to SQL/tree/graph,
- format final citations,
- call an LLM,
- generate an answer,
- build the ~200-question smoke eval,
- calculate doc_recall@10,
- implement FastAPI.

# FINAL RESPONSE TO ME

Return:

## Task

```text
task_1.6_baseline_retriever.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input / Provenance
Report Task 1.5 commit, index path, table, row count, chunk_config_hash, model, revision.

## Frozen Decisions

```text
default k = 5
k configurable = YES
distance returned = YES
score returned = YES
score transform = 1-distance
vector returned = NO
```

## Retriever API
Report module, class/function, signature.

## Query Contract
Report query convention, model revision, dimension, dtype, normalization, device, offline status.

## Search Contract
Report backend, table, exact mode, cosine metric, distance semantics, rank semantics.

## Result Schema
List exact public fields.

## Smoke Retrieval
Report real query count, default-k behavior, k=10 behavior, concise sample top-result IDs/metadata.

## Determinism
Report whether repeated identical query returns same chunk IDs/order and stable score/distance.

## Performance
Report query count, k, embedding/search/total p50/p95 where measured.

Label as:

```text
Phase 1 smoke diagnostic, not production benchmark
```

## Tests
Report new tests, portable/full counts, doctor, GPU smoke.

## Safety
Confirm index/embeddings/chunks/normalized/data unchanged, no network, no BM25, no reranker, no generation.

## Files Modified
List actual tracked/project files only.

## Git
Report commit created, hash, message, remote, push status.

## Progress.md
Confirm Phase 1.6 entry appended.

## Next Task

If PASS:

```text
task_1.7_minimal_generation_layer.md
```

Do not start it.

Finally state:

```text
No Task 1.7 work started.
```

Stop and wait for my approval.
