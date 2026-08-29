# Task 1.5 — Vector-Only Index

You are working inside my SEC RAG repository.

Task file:

`task_1.5_vector_only_index.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.5 — Vector-Only Index
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
  1.5 Vector-Only Index            — CURRENT
```

Task 1.4 produced the authoritative input embedding artifact for this task.

Current recorded Task 1.4 state:

```text
chunk count: 162,357
chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

embedding model:
BAAI/bge-small-en-v1.5

embedding model revision:
5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

embedding dimension: 384
embedding normalization: L2-normalized
vector dtype: float32

embedding artifact:
artifacts/embeddings/
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/
BAAI--bge-small-en-v1.5/
embeddings.parquet

embedding rows: 162,357
```

Task 1.4 verified full-corpus traceability between the embedding artifact
and Task 1.3 chunks.

Do NOT begin Task 1.6.

---

# USER-APPROVED TASK 1.5 DECISIONS — FROZEN

The following decisions were explicitly resolved before this prompt was
drafted.

Do NOT ask again unless the actual repository materially contradicts them.

## Decision 1 — Index Type

Use:

```text
plain LanceDB table
exact / flat vector search
NO ANN index
```

Do NOT create IVF_PQ, HNSW, IVF_FLAT, or any other approximate index.

Task 0.10 used IVF_PQ only for a serving-feasibility experiment. That does
not define the Phase 1 baseline.

## Decision 2 — Similarity Metric

Use exactly:

```text
cosine
```

Do not silently switch to L2 or dot product.

## Decision 3 — Table Contents

Retain all 17 Task 1.4 columns:

```text
chunk_id
document_id
cik
company
form_type
fiscal_year
source
source_filename
source_split
ordinal
text
token_count
chunk_config_hash
normalizer_version
normalization_build_sha256
development_manifest_sha256
vector
```

The Phase 1 table must be self-contained. Task 1.6 should not need to join
back to chunks.parquet simply to recover the retrieved text/metadata.

## Decision 4 — Table Name

Use exactly:

```text
chunks
```

---

# CRITICAL RULE — DO NOT ASSUME

For every other implementation decision, if it is not clearly established
by:

1. the actual repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_EMBEDDINGS.md`,
4. `project_plan/PHASE1_CHUNKING.md`,
5. `project_plan/STORAGE.md`,
6. current Task 1.4 config/summary,
7. the installed LanceDB 0.37.1 API behavior,
8. current tests/code,

then:

**STOP AND ASK ME.**

Do not choose a library default merely because it works.

Do not silently convert schema types.

Do not silently overwrite an existing index.

Do not invent a new durable index hash/version unless current project
contracts require one.

Do not silently interpret LanceDB `_distance` as a similarity score.

When asking:

- state exactly what is ambiguous,
- state what evidence you found,
- give the smallest useful set of options,
- explain what downstream behavior changes,
- wait for my answer.

Potential ambiguity points include:

```text
exact local LanceDB database-directory semantics
existing-index overwrite/reuse behavior
how LanceDB 0.37.1 explicitly requests cosine for exact search
returned cosine distance field and ranking direction
whether LanceDB preserves physical row order
whether a separate index-config identity is needed
```

Inspection first. Assumption never.

---

# AUTHORITATIVE TASK PURPOSE

Task 1.5 builds the first searchable vector store for the Phase 1 vertical
slice:

```text
Task 1.4
162,357 BGE embedding rows
        ↓
Task 1.5
LanceDB table: chunks
exact cosine vector search
        ↓
Task 1.6
baseline retriever
```

This is an integration-correctness baseline, not an indexing optimization
experiment.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify the Task 1.4 checkpoint and embedding artifact,
2. verify LanceDB 0.37.1 behavior for plain exact cosine search,
3. create the versioned LanceDB database through `src.storage`,
4. create exactly one application table named `chunks`,
5. load all 162,357 embedding rows,
6. preserve all approved 17 columns,
7. create no ANN index,
8. implement exact cosine vector search,
9. validate row count/schema/metadata/vector integrity,
10. verify stored vectors map exactly to source chunk IDs,
11. perform deterministic real-corpus self-retrieval checks,
12. record build size/time and small search diagnostics,
13. add reusable index-opening/search helpers for Task 1.6 where appropriate,
14. add focused automated tests,
15. document the Phase 1 vector-index contract,
16. update `Progress.md`,
17. commit Task 1.5 as one coherent Git commit.

Do NOT start Task 1.6.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -7
git tag --list
```

Verify Task 1.4 is committed and there are no unexplained changes.

If unexplained changes exist:

**STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv` and run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -c "import lancedb; print(lancedb.__version__)"
```

Expected LanceDB version from the pinned environment:

```text
0.37.1
```

If the installed version differs materially from the pin, STOP.

---

# STEP 3 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_EMBEDDINGS.md
project_plan/PHASE1_CHUNKING.md
project_plan/STORAGE.md
project_plan/CONFIGURATION.md
project_plan/DEPENDENCIES.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/storage.py
src/index/
src/embeddings/bge.py
scripts/embed_development_corpus.py
configs/embed_development_corpus.json
results/phase_1_4_embedding_summary.json
tests/test_lancedb_smoke.py
tests/test_baseline_embeddings.py
```

Use actual current interfaces, not old prompt examples.

---

# STEP 4 — VERIFY TASK 1.4 INPUT

Resolve the embedding artifact from tracked Task 1.4 provenance.

Expected values:

```text
chunk_config_hash = f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
model = BAAI/bge-small-en-v1.5
model revision = 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
row count = 162,357
dimension = 384
dtype = float32
normalize_embeddings = true
```

Independently verify:

```text
embedding artifact exists
row count == 162,357
unique chunk_id == 162,357
vector dimension == 384
vector dtype == float32
all vectors finite
chunk_config_hash is single-valued and expected
```

Do not rebuild embeddings.

If current artifact/provenance disagree, STOP.

---

# STEP 5 — VERIFY INPUT SCHEMA

Inspect the actual PyArrow schema and verify all 17 logical fields exist.

Preserve the established type contract, especially:

```text
cik -> int64
fiscal_year -> int32
ordinal -> int32
token_count -> int32
vector -> fixed-size 384 float32 values
```

If LanceDB cannot preserve one of these safely:

**STOP AND ASK ME.**

Explain the source type, required target type, and whether values/downstream
behavior change.

---

# STEP 6 — USE THE EXISTING STORAGE CONTRACT

Use:

```python
storage.index_dir(chunk_config_hash, embedding_model)
```

Expected conceptual root:

```text
artifacts/indexes/
<chunk_config_hash>/
BAAI--bge-small-en-v1.5/
```

Do not hardcode a new index root.

Do not create a second indexing path convention.

---

# STEP 7 — VERIFY LOCAL DATABASE DIRECTORY SEMANTICS

Inspect how LanceDB 0.37.1 expects a local database directory to be opened.

Prefer the approved `index_dir(...)` itself as the database root unless the
current storage/documentation contract says otherwise.

Do not silently add nested names such as:

```text
index.lancedb/
db/
store/
```

If an additional directory layer is required and not already defined:

**STOP AND ASK ME.**

---

# STEP 8 — CREATE EXACTLY ONE TABLE

Create exactly one application table named:

```text
chunks
```

After build, verify the application's table listing contains only this
expected table.

Do not create auxiliary application tables for metadata/documents.

---

# STEP 9 — NO ANN INDEX

Do not call APIs that create:

```text
IVF_PQ
IVF_FLAT
HNSW
```

or any equivalent approximate vector index.

If LanceDB exposes index metadata, verify:

```text
ANN/vector indexes created = 0
```

If LanceDB 0.37.1 automatically creates an ANN index that cannot be disabled:

**STOP AND ASK ME.**

---

# STEP 10 — COSINE SEARCH MUST BE EXPLICIT

Use exact cosine search.

Do not rely on LanceDB's default distance metric.

Inspect the installed 0.37.1 API and use the actual supported method for
explicit cosine distance.

Do not copy syntax from an older/newer version blindly.

---

# STEP 11 — VERIFY DISTANCE SEMANTICS

Determine exactly what LanceDB returns for exact cosine search.

Document:

```text
result distance field name
metric = cosine
whether lower or higher is better
expected self-match behavior
```

If results expose `_distance`, do not rename it to `score` without a clear
semantic conversion.

If the behavior is unclear from installed API/docs/source:

**STOP AND ASK ME.**

---

# STEP 12 — TINY SYNTHETIC COSINE TEST FIRST

Before the real build, create a temporary tiny LanceDB database with known
normalized vectors.

Verify:

```text
identical vector ranks first
orthogonal vector ranks worse
opposite vector ranks worse if supported by the distance semantics
```

This validates the exact API behavior.

Delete the temporary DB afterward.

---

# STEP 13 — TASK 1.5 CONFIG

Create a small tracked config under the existing `configs/` convention.

It should capture at least:

```text
schema_version
input_embedding_artifact
input_chunk_config_hash
embedding_model
embedding_model_revision
embedding_dimension
vector_dtype
normalize_embeddings
database_backend
search_mode
distance_metric
table_name
column_policy
```

Freeze these approved values:

```text
database_backend = lancedb
search_mode = exact
distance_metric = cosine
table_name = chunks
column_policy = all_17_columns
```

Do not add ANN tuning parameters.

---

# STEP 14 — DO NOT INVENT A NEW INDEX HASH WITHOUT NEED

The storage path already keys the index by:

```text
chunk_config_hash + embedding_model
```

Inspect whether the current project requires a separate index-config hash.

If not required, keep Phase 1 simple.

If safe reuse genuinely requires one and no contract exists:

**STOP AND ASK ME.**

Never use Python's built-in `hash()` for durable identity.

---

# STEP 15 — IMPLEMENTATION LOCATION

Task 1.5 makes `src/index/` a real implemented package.

Prefer a small reusable module such as:

```text
src/index/lancedb_index.py
```

with functions conceptually like:

```text
open_database
create_chunk_table
open_chunk_table
validate_chunk_table
exact_cosine_search
```

Use a thin orchestration script such as:

```text
scripts/build_vector_index.py
```

if consistent with current repository conventions.

Do not put production index logic in `scripts/serving_spike.py`.

---

# STEP 16 — USE FOUNDATION BOUNDARIES

Use:

```text
src.storage
src.logging_utils
```

where appropriate.

Do not scatter `Path("artifacts/indexes")`, direct environment reads, or
`logging.basicConfig(...)` through the new implementation.

---

# STEP 17 — DO NOT LOAD THE EMBEDDING MODEL

Task 1.5 consumes stored vectors.

Do not load:

```text
SentenceTransformer
BGE weights
CUDA
```

Do not re-embed chunks.

Do not generate natural-language query embeddings.

Task 1.6 owns the query encoding path.

---

# STEP 18 — INGEST EFFICIENTLY

Prefer PyArrow-native ingestion into LanceDB where supported.

Avoid needless conversion of the whole artifact into nested Python lists or
large dict lists.

Keep implementation single-machine and simple.

---

# STEP 19 — LOAD ALL 162,357 ROWS

Required:

```text
input rows = 162,357
LanceDB chunks rows = 162,357
```

No filtering.

No replacement.

No deduplication beyond validation.

---

# STEP 20 — SAFE CREATE / REUSE POLICY

If the target database/table is absent, create it.

If it exists, inspect its provenance/schema/count before doing anything.

Do not silently overwrite with `mode="overwrite"` or equivalent.

If the existing table is identical and current repo policy explicitly
allows reuse, verify/reuse it.

If it conflicts and no policy resolves the conflict:

**STOP AND ASK ME.**

Never delete the whole `artifacts/indexes/` root.

---

# STEP 21 — RETAIN ALL 17 COLUMNS

After creation, inspect the LanceDB table schema.

Verify all 17 approved persisted columns exist.

System/query fields such as `_distance` are not persisted source columns.

Do not drop `text`.

---

# STEP 22 — FULL METADATA INTEGRITY

Compare LanceDB content against the Task 1.4 embedding artifact.

At minimum completely verify:

```text
row count
chunk_id uniqueness and set equality
document_id
cik
fiscal_year
ordinal
chunk_config_hash
normalizer_version
normalization_build_sha256
development_manifest_sha256
```

Because all 17 columns are retained, preferably verify every non-vector
column full-corpus.

Do not rely only on a small sample for identity invariants.

---

# STEP 23 — VECTOR INTEGRITY

Verify stored vectors remain:

```text
384-dimensional
float32 semantics
finite
```

For a deterministic subset, compare stored vectors against source vectors.

Prefer exact equality if LanceDB preserves the float32 representation.

If not exact, quantify the difference.

Do not silently accept material numeric changes.

---

# STEP 24 — DO NOT RELY ON PHYSICAL ROW ORDER

Chunk identity is `chunk_id`, not physical row position.

Do not make Task 1.6 depend on LanceDB preserving insertion order unless the
actual database contract explicitly guarantees it.

---

# STEP 25 — IMPLEMENT AN EXACT COSINE SEARCH HELPER

Implement a reusable vector-only helper, conceptually:

```python
exact_cosine_search(table, query_vector, limit)
```

It should:

```text
validate a 384-d numeric vector
request cosine explicitly
perform exact search
return top-k rows with text/metadata
preserve LanceDB distance semantics honestly
```

Do not accept a natural-language question here.

Do not load BGE here.

---

# STEP 26 — QUERY VECTOR VALIDATION

Reject clearly:

```text
wrong dimension
empty vector
NaN
Inf
```

Do not truncate/pad malformed vectors.

---

# STEP 27 — REAL-CORPUS SELF-RETRIEVAL

Use a deterministic subset of actual Task 1.4 vectors.

For each tested chunk:

```text
source vector -> exact cosine search -> expected same chunk_id at rank 1
```

Use enough cases to detect mapping errors, e.g. 20–50 deterministic chunks
across documents/years.

If any self-vector does not retrieve itself at rank 1, investigate before
passing.

If a genuine vector tie occurs, document it rather than silently weakening
the test.

---

# STEP 28 — SEARCH RESULT TRACEABILITY

For every smoke search verify returned rows contain at least:

```text
chunk_id
text
document_id
cik
fiscal_year
distance
```

The stored table must provide enough evidence for Task 1.6 without an
external metadata join.

---

# STEP 29 — COSINE SELF-DISTANCE SANITY

For identical vectors, cosine distance should be approximately zero under
normal LanceDB cosine-distance semantics.

Measure actual behavior and use a reasonable floating-point tolerance.

Document whether lower or higher is better based on the real API behavior.

---

# STEP 30 — SMALL SEARCH LATENCY DIAGNOSTIC

Task 1.5 is not a performance benchmark, but record a small honest exact-
search diagnostic if the current execution plan supports it.

Use warm-up queries, then a deterministic set of real vectors.

If top-k for the diagnostic is not already defined by the current plan and
choosing it would create a project contract:

**STOP AND ASK ME.**

If performed, record:

```text
query count
top-k
p50
p95
```

Label clearly:

```text
Phase 1 smoke diagnostic — not a production benchmark
```

Do not compare against IVF_PQ.

---

# STEP 31 — BUILD METRICS

Record actual:

```text
build elapsed time
database size on disk
table row count
table schema
ANN index count
```

Do not call the 162k-row database size a full-corpus production estimate.

---

# STEP 32 — TRACKED SUMMARY

Create a small tracked result under `results/`, following current naming
conventions.

A likely filename is:

```text
results/phase_1_5_vector_index_summary.json
```

Include actual resolved values such as:

```text
schema_version
input_embedding_artifact
input_chunk_config_hash
embedding_model
embedding_model_revision
vector_count
vector_dimension
vector_dtype
normalize_embeddings
backend
search_mode
distance_metric
table_name
column_count
database relative path
database size
build runtime
ANN indexes created
self-retrieval results
search diagnostic if performed
created_at_utc
```

Do not track generated LanceDB fragments.

---

# STEP 33 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_VECTOR_INDEX.md
```

unless current repo conventions clearly specify another name.

Document:

```text
purpose
Task 1.4 input provenance
LanceDB version
database path
table name = chunks
row count
all-17-column policy
search mode = exact
metric = cosine
ANN index = none
distance field/semantics
vector/chunk traceability
validation
small build/search diagnostics
known limitations
next consumer = Task 1.6
```

Known limitations must include:

```text
exact scan only
no ANN optimization
no BM25/FTS
no hybrid retrieval
no reranking
no retrieval evaluation yet
```

Update `project_plan/REPOSITORY_STRUCTURE.md` only as needed to mark
`src/index/` implemented.

---

# STEP 34 — TESTS

Add focused tests, e.g.:

```text
tests/test_vector_index.py
```

Use temporary LanceDB directories and tiny synthetic data.

Test actual approved behavior:

```text
table name == chunks
17-column schema retained
row count retained
chunk_id uniqueness
384-d vector validation
non-finite vector rejection
exact cosine search
self-vector ranks first
cosine distance ordering
returned text + metadata
no ANN index creation
storage/index path behavior
existing-table conflict behavior
```

Do not require the full real embedding artifact for portable unit tests.

---

# STEP 35 — OPTIONAL REAL-INDEX INTEGRATION TEST

If consistent with the existing marker policy, add a small local-data test
that opens the already-built real Task 1.5 index and performs a tiny smoke
query.

Do not rebuild the full index inside pytest.

If the real index is absent on another machine, follow the project's
existing missing-capability skip policy.

If it exists but is broken, FAIL.

---

# STEP 36 — BUILD COMMAND

Provide one documented command, conceptually:

```bash
python scripts/build_vector_index.py
```

Use actual final naming.

It must:

1. validate Task 1.4 provenance,
2. load Task 1.5 config,
3. resolve the index path via `src.storage`,
4. inspect existing index safety,
5. create/open LanceDB,
6. create exactly one `chunks` table,
7. ingest all 162,357 rows,
8. create NO ANN index,
9. validate schema/count,
10. validate metadata/vector integrity,
11. run exact cosine self-retrieval checks,
12. write the small tracked summary,
13. exit non-zero on invariant failure.

Do not load BGE.

Do not implement question retrieval.

---

# STEP 37 — RUN THE REAL FULL BUILD

Task 1.5 cannot PASS based only on a tiny synthetic table.

Build the real LanceDB table from all 162,357 Task 1.4 embedding rows.

Record actual path, size, time, schema, and ANN-index count.

---

# STEP 38 — RUN REAL SELF-RETRIEVAL CHECKS

Use deterministic real vectors and verify their own `chunk_id` comes back at
rank 1 under exact cosine search.

Record:

```text
number checked
number passed
any ties/anomalies
self-distance range
```

This is mapping validation, not retrieval relevance evaluation.

---

# STEP 39 — NO QUERY EMBEDDING YET

Do not implement:

```text
question -> BGE query vector
```

in Task 1.5.

Task 1.6 owns that pipeline.

---

# STEP 40 — NO BM25 / FTS / HYBRID

Do not create:

```text
LanceDB FTS
Tantivy
BM25
hybrid search
```

This task is vector-only.

---

# STEP 41 — NO RERANKER / CRAG / ROUTER / LLM

Do not load MiniLM.

Do not rerank.

Do not implement CRAG.

Do not route.

Do not call an LLM.

---

# STEP 42 — VERIFY UPSTREAM INPUTS REMAIN UNCHANGED

After the build confirm:

```text
Task 1.4 embeddings.parquet unchanged
Task 1.3 chunks.parquet unchanged
Task 1.2 normalized Markdown unchanged
frozen data/ unchanged
```

The index builder is a consumer only.

---

# STEP 43 — RUN TEST SUITES

After implementation:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required:

```text
0 failures
```

Record actual current counts.

Do not hardcode the prior 160-test total.

---

# STEP 44 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Verify generated LanceDB files under `artifacts/indexes/` are ignored.

Expected trackable files may include:

```text
src/index/...
scripts/build_vector_index.py
configs/<Task 1.5 config>.json
results/phase_1_5_vector_index_summary.json
tests/test_vector_index.py
project_plan/PHASE1_VECTOR_INDEX.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
prompt file if prompts are tracked
```

Do not stage Lance fragments/vector data/model weights.

Run the normal secret/personal-path scan.

---

# STEP 45 — UPDATE Progress.md

Append:

```markdown
## YYYY-MM-DD — Phase 1.5 Vector-Only Index
```

Preserve all prior history.

Include:

### Objective

Task 1.5 creates the first exact LanceDB cosine-search table over all Task
1.4 embeddings.

### Initial State

Record:

```text
Task 1.4 commit
embedding artifact
chunk_config_hash
embedding model/revision
embedding row count
```

### Frozen User Decisions

Record:

```text
index type: plain table / exact search
metric: cosine
table columns: all 17
table name: chunks
```

### Backend / Storage

Record:

```text
LanceDB version
database path
table name
```

### Search Contract

Record:

```text
exact vs approximate
cosine API used
distance field
distance ranking direction
ANN index count
```

### Table Schema

List exact persisted columns/types.

### Build

Record:

```text
input rows
table rows
build runtime
database size
```

### Validation

Record:

```text
metadata equality
vector checks
chunk-ID uniqueness
self-retrieval checks
```

### Search Diagnostics

If performed, record p50/p95 and clearly label them as Phase 1 smoke
numbers, not production benchmarks.

### Tests

Record:

```text
new Task 1.5 tests
doctor
portable suite
full suite
```

### Safety

Confirm:

```text
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
data unchanged
index artifact ignored
no ANN
no BM25/FTS
no retriever pipeline
```

### Files Created / Modified

List actual tracked files only.

### Git

Record Task 1.5 commit details.

### Result

Use exactly one:

```text
PASS — exact cosine LanceDB index built for all Phase 1 embeddings

WARN — vector index built with one documented non-blocking issue

BLOCKED — Phase 1 vector index could not be established safely
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
  1.6 Baseline Retriever           — NEXT
```

---

# STEP 46 — COMMIT TASK 1.5

After the real build, integrity checks, self-retrieval checks, tests, and
Git-safety review all pass, create one coherent Task 1.5 commit.

Preferred message:

```text
Add exact LanceDB vector index
```

Do not include Task 1.6 work.

Do not tag Phase 1 yet.

---

# STEP 47 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote is configured:

```text
push deferred — no remote configured
```

Do not invent one.

If push authorization is ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.5 is complete only if:

```text
[ ] Task 1.4 commit verified
[ ] Task 1.4 artifact/provenance verified
[ ] exactly 162,357 input embedding rows
[ ] all input chunk IDs unique
[ ] vectors dimension 384
[ ] vectors float32
[ ] vectors finite

[ ] LanceDB version verified
[ ] src.storage.index_dir() used
[ ] database path semantics verified

[ ] table name exactly chunks
[ ] exactly one application table
[ ] all 17 columns retained
[ ] table row count exactly 162,357

[ ] exact/flat search only
[ ] cosine explicitly requested
[ ] no ANN index created
[ ] no IVF_PQ/HNSW/etc.

[ ] LanceDB distance semantics verified
[ ] ranking direction documented
[ ] distance field documented

[ ] chunk IDs unique after indexing
[ ] metadata integrity verified
[ ] stored vectors verified against source
[ ] no material vector corruption/conversion

[ ] exact cosine search helper implemented
[ ] helper accepts numeric vectors, not question strings
[ ] malformed query vectors rejected

[ ] real-corpus self-retrieval performed
[ ] own vector retrieves same chunk at rank 1
[ ] returned rows contain text and metadata
[ ] no external join required for evidence

[ ] build runtime recorded
[ ] database size recorded
[ ] small search diagnostic recorded if applicable
[ ] no production benchmark claim made

[ ] focused Task 1.5 tests added
[ ] doctor passes
[ ] portable suite has zero failures
[ ] full suite has zero failures

[ ] embeddings.parquet unchanged
[ ] chunks.parquet unchanged
[ ] normalized Markdown unchanged
[ ] frozen data unchanged

[ ] no embedding model loaded for build
[ ] no query embedding implemented
[ ] no BM25/FTS
[ ] no reranker
[ ] no CRAG
[ ] no router
[ ] no LLM
[ ] no ANN

[ ] PHASE1_VECTOR_INDEX.md created
[ ] REPOSITORY_STRUCTURE.md updated where needed
[ ] Progress.md updated

[ ] LanceDB artifact ignored
[ ] staged content reviewed
[ ] one Task 1.5 commit created
[ ] no Task 1.6 work included
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.4 artifact does not match provenance
LanceDB cannot preserve an approved field safely
database directory semantics are unclear
exact search cannot be guaranteed
explicit cosine-search API is unclear
returned cosine-distance semantics are unclear
existing target database/table conflicts
overwrite/reuse policy is undefined
a separate durable index identity becomes necessary but undefined
a new dependency appears necessary
stored vectors materially differ from Task 1.4 source vectors
LanceDB creates an ANN index automatically and it cannot be disabled
repository documentation materially conflicts
Git push authorization is unclear
any other durable implementation decision would require guessing
```

Do not use "LanceDB default" as a substitute for a project decision when
that default affects the retrieval contract.

---

# IMPORTANT NON-GOALS

Task 1.5 does NOT:

```text
re-embed chunks
modify Task 1.4 vectors
change chunking
change normalized documents
create ANN indexes
tune IVF_PQ
build HNSW
build BM25
build FTS
build hybrid retrieval
encode natural-language queries
implement Task 1.6 retriever
measure doc_recall@10
rerank
implement CRAG
implement routing
call an LLM
generate smoke questions
```

The desired result is only:

```text
162,357 Task 1.4 embedding rows
        ↓
LanceDB
plain table = chunks
exact cosine search
all 17 columns retained
        ↓
Task 1.6
```

---

# FINAL RESPONSE TO ME

After completing Task 1.5, return:

## Task

```text
task_1.5_vector_only_index.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input

Report:

```text
embedding artifact
chunk_config_hash
embedding model/revision
input rows
unique chunk IDs
vector dimension/dtype
```

## Frozen Decisions

Confirm:

```text
index type: exact/plain LanceDB table
metric: cosine
table columns: all 17
table name: chunks
```

## Backend

Report:

```text
LanceDB version
database path
table name
table row count
ANN indexes created
```

## Table Schema

List exact columns/types.

## Search Contract

Report:

```text
search mode
metric
LanceDB API used to request cosine
returned distance field
lower/higher is better
```

## Integrity

Report:

```text
row-count match
chunk-ID uniqueness
metadata equality
vector dimension/dtype
finite vectors
stored-vs-source vector comparison
```

## Self-Retrieval

Report:

```text
real vectors tested
same chunk at rank 1: X/Y
ties/anomalies
self-distance range
```

## Performance

Report:

```text
build runtime
database size
search diagnostic query count/top-k
p50
p95
```

Clearly label search timing as a smoke diagnostic rather than a production
benchmark.

## Tests

Report:

```text
new Task 1.5 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
```

## Safety

Confirm:

```text
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
data unchanged
index artifact ignored by Git
no ANN index
no BM25/FTS
no retrieval pipeline
```

## Files Modified

List actual tracked/project files only.

Do not list LanceDB fragment files individually.

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
## YYYY-MM-DD — Phase 1.5 Vector-Only Index
```

was appended.

## Next Task

If PASS:

```text
task_1.6_baseline_retriever.md
```

Do not start it.

Finally state:

```text
No Task 1.6 work started.
```

Stop and wait for my approval.
