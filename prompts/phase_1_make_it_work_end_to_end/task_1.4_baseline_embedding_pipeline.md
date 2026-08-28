# Task 1.4 — Baseline Embedding Pipeline

You are working inside my SEC RAG repository.

Task file:

`task_1.4_baseline_embedding_pipeline.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.4 — Baseline Embedding Pipeline
```

Current status:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — CURRENT
```

Task 1.3 is the authoritative input.

Current recorded Task 1.3 output:

```text
chunk count: 162,357
documents with chunks: 1,493
documents with zero chunks: 7

chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

artifact:
artifacts/chunks/
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/
chunks.parquet

Parquet size:
190,631,710 bytes
```

The current Phase 1 baseline embedding model is:

```text
BAAI/bge-small-en-v1.5
```

Task 0.2 already verified this model can run CUDA embedding inference on the
RTX 5060 Laptop GPU and produces 384-dimensional vectors.

Task 1.4 must embed the Task 1.3 chunk corpus.

Do NOT begin Task 1.5.

---

# CRITICAL RULE — DO NOT ASSUME

If an implementation decision is not clearly resolved by:

1. the actual current repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. current specialized Phase 1 documentation,
4. current config/storage code,
5. direct inspection of the local cached model/configuration,

then:

**STOP AND ASK ME.**

Do not silently choose a reasonable default.

Do not choose behavior merely because SentenceTransformers or PyTorch has a
default.

Do not copy Task 0.10 benchmark behavior unless the Phase 1 repository
explicitly adopts it.

When asking me:

- state exactly what is ambiguous,
- state what you found,
- give the smallest useful set of options,
- explain what downstream behavior changes,
- wait for my answer before continuing.

Likely clarification points include:

```text
exact cached model revision
query convention / query instruction
passage convention
normalize_embeddings True/False
persisted vector dtype
GPU batch size
mixed-precision policy
embedding artifact location
embedding artifact format
metadata retention policy
artifact identity/versioning
overwrite/rebuild policy
```

Inspection first. Assumption never.

---

# AUTHORITATIVE TASK DEFINITION

Read Task 1.4 directly from:

```text
project_plan/PROJECT_EXECUTION.md
```

The current execution plan requires:

```text
- Load bge-small-en-v1.5.
- Apply the model's required query/passage conventions correctly.
- Batch embeddings on GPU.
- Record embedding throughput.
- Store the embeddings with chunk IDs and metadata.
```

Phase 1 remains deliberately simple:

```text
one embedding model
vector retrieval only later
no BM25
no hybrid search
no reranking
no CRAG
no router
no graph
```

---

# PURPOSE

Pipeline position:

```text
Task 1.3 chunks.parquet
        ↓
Task 1.4
BAAI/bge-small-en-v1.5
GPU passage embedding
        ↓
traceable embedding artifact
        ↓
Task 1.5 LanceDB vector-only index
```

Task 1.4 also establishes the query-encoding helper/convention Task 1.6 will
later use, but the full build embeds passages/chunks only.

No retrieval happens here.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. verify Task 1.3 is committed and its artifact matches provenance,
2. inspect and freeze the exact BGE model/revision,
3. establish correct query and passage conventions,
4. establish embedding normalization explicitly,
5. establish persisted vector dtype explicitly,
6. establish a safe GPU batch policy explicitly,
7. implement reusable passage/query embedding helpers,
8. embed all 162,357 chunks on CUDA,
9. preserve exact vector-to-chunk identity,
10. store embeddings with approved metadata,
11. record measured throughput, runtime, memory, and artifact size,
12. validate all output vectors,
13. add focused automated tests,
14. document the embedding contract,
15. update `Progress.md`,
16. create one Task 1.4 commit.

Do NOT start Task 1.5.

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
Task 1.3 committed
working tree clean except for intentional Task 1.4 prompt state
no Task 1.5 implementation already present
```

If unexplained changes exist:

**STOP AND ASK ME.**

Do not mix unrelated work into this commit.

---

# STEP 2 — VERIFY FOUNDATION AND GPU

Activate `.venv`.

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py gpu
```

Required:

```text
doctor PASS
portable suite 0 failures
real CUDA operation PASS
```

If CUDA is unavailable or broken:

STOP.

Do not silently fall back to CPU for the real build.

---

# STEP 3 — READ CURRENT DOCUMENTATION

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_CHUNKING.md
project_plan/PHASE1_NORMALIZATION.md
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
src/config.py
src/storage.py
src/embeddings/
src/chunk/fixed_window.py
scripts/chunk_development_corpus.py
configs/chunk_development_corpus.json
results/phase_1_3_chunking_summary.json
requirements.txt
requirements-gpu.txt
```

Use the actual repository as source of truth.

---

# STEP 4 — VERIFY TASK 1.3 INPUT

Resolve the actual chunk artifact from Task 1.3 tracked provenance.

Expected:

```text
chunk_config_hash =
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

chunk rows = 162,357
```

Verify:

```text
chunks.parquet exists
row count == 162,357
chunk_id unique count == 162,357
all chunk_config_hash values match
text is non-empty for every chunk
```

Verify the current 16-column Phase 1 baseline schema.

Do not repair Task 1.3 here.

If current artifact/provenance disagree:

STOP and report the discrepancy.

---

# STEP 5 — VERIFY MODEL IDENTITY

Use exactly:

```text
BAAI/bge-small-en-v1.5
```

Inspect the local Hugging Face / SentenceTransformers cache.

Record:

```text
repository/model ID
resolved model revision/commit if available
sentence-transformers version
transformers version
torch version
torch.version.cuda
```

Task 1.3 recorded a cached tokenizer revision, but do not assume the model
revision is identical without checking.

If multiple cached model revisions exist and the intended revision is
ambiguous:

**STOP AND ASK ME.**

---

# STEP 6 — OFFLINE MODEL POLICY

The real build should use local cached assets only.

Do not unexpectedly download model files.

Verify required cached model assets before construction.

If assets are missing/incomplete:

**STOP AND ASK ME.**

Do not silently fetch them.

Do not substitute another model.

---

# STEP 7 — VERIFY EMBEDDING DIMENSION

Verify from the loaded model, not from memory:

```text
model.get_sentence_embedding_dimension()
```

Expected:

```text
384
```

If the actual dimension is not 384:

STOP.

Do not produce an artifact under an unexpected vector schema.

---

# STEP 8 — RESOLVE QUERY / PASSAGE CONVENTIONS

This is an explicit Task 1.4 requirement.

Inspect the exact locally cached model metadata/model card/configuration and
the current SentenceTransformers behavior.

Determine separately:

```text
passage/document convention
query convention
```

Do not assume from memory that a particular query instruction is required.

Do not assume passage text has no prefix.

Do not silently rely on generic `model.encode(...)`.

If the correct conventions cannot be established unambiguously:

**STOP AND ASK ME.**

When resolved, expose clearly separate APIs, conceptually:

```python
encode_passages(...)
encode_queries(...)
```

The full 162,357-row build must use the passage convention.

A tiny query smoke test must verify the future query path.

---

# STEP 9 — RESOLVE EMBEDDING NORMALIZATION

Determine whether stored vectors are:

```text
L2-normalized
```

or:

```text
raw embeddings
```

Do not silently accept the SentenceTransformer default.

Do not silently set `normalize_embeddings=True`.

Search current repo/model guidance.

If the intended Phase 1 behavior is not already explicit:

**STOP AND ASK ME.**

This decision must be compatible with Task 1.5/1.6 similarity semantics.

---

# STEP 10 — RESOLVE VECTOR DTYPE

Determine the persisted vector dtype.

Possible examples:

```text
float32
float16
```

Do not perform binary/product quantization here.

If current docs do not specify the persisted dtype:

**STOP AND ASK ME.**

Record the approved dtype in config/docs/summary and validate it after the
full build.

---

# STEP 11 — RESOLVE GPU BATCH SIZE AND PRECISION POLICY

Search current docs for a frozen Phase 1 embedding batch size.

If none exists:

**STOP AND ASK ME.**

Do not choose 16/32/64/128 merely by habit.

Also explicitly resolve whether the real build uses:

```text
full/default model precision
FP16 autocast
BF16 autocast
another approved policy
```

Do not silently enable mixed precision.

If a chosen batch size OOMs, do not silently alter provenance and continue.
Follow an already-approved fallback policy or ask me.

Never fall back to CPU silently.

---

# STEP 12 — VERIFY REAL CUDA EXECUTION

Load the exact model on:

```text
cuda
```

explicitly.

Confirm model/device state directly.

Record:

```text
GPU model
compute capability
model device
```

The full build must actually run on CUDA.

Timing alone is not evidence.

---

# STEP 13 — RESOLVE EMBEDDING ARTIFACT LOCATION

Inspect `src/storage.py`.

Task 0.7 originally provided helpers for normalized/chunks/index/eval paths;
an embedding-artifact path may or may not have been added since.

Do not assume embeddings belong under:

```text
artifacts/chunks/
artifacts/indexes/
results/
```

If no embedding artifact location is defined:

**STOP AND ASK ME.**

Present the smallest sensible options based on the actual storage
architecture.

Do not create a new storage convention before approval.

Large embedding artifacts must remain git-ignored.

---

# STEP 14 — RESOLVE EMBEDDING ARTIFACT FORMAT

`PROJECT_EXECUTION.md` requires vectors with chunk IDs and metadata but does
not itself specify the format.

Search the repository for a frozen Task 1.4 format.

Examples of materially different choices include:

```text
Parquet with vector column + metadata
vectors array + separate metadata Parquet
Arrow
another explicit format
```

If undefined:

**STOP AND ASK ME.**

Do not build LanceDB in Task 1.4 just to avoid deciding on an intermediate
artifact.

Task 1.5 must consume the Task 1.4 result cleanly.

---

# STEP 15 — RESOLVE METADATA RETENTION

Task 1.3 has 16 chunk columns.

Determine exactly which chunk fields are carried into the embedding artifact.

The rule must preserve exact vector-to-chunk traceability and metadata needed
by Task 1.5 and later citation checks.

Do not silently discard important metadata.

Do not silently duplicate large `text` if the approved artifact contract is
intended to reference the source chunk artifact instead.

If not defined:

**STOP AND ASK ME.**

---

# STEP 16 — CONFIGURATION

Create a small tracked Task 1.4 config under the existing `configs/`
convention.

Capture all resolved semantics that affect vector output, such as:

```text
schema_version
input_chunk_config_hash
input_chunk_artifact
model_repository
model_revision
embedding_dimension
passage_convention
query_convention
normalize_embeddings
vector_dtype
device
batch_size
precision_policy
artifact_format
metadata_policy
```

Use actual resolved values.

Do not put runtime timestamps into semantic config.

---

# STEP 17 — ARTIFACT IDENTITY / VERSIONING

Search for an existing Phase 1 embedding artifact identity convention.

Do not misuse:

```text
chunk_config_hash
```

as if it also identifies the embedding model/config.

Do not assume Task 0.7's `index_dir(chunk_config_hash, embedding_model)` is
an embedding artifact path.

If safe artifact reuse requires a new embedding identity and no rule exists:

**STOP AND ASK ME.**

Do not invent a permanent production hashing contract prematurely.

If a hash is approved, use deterministic canonical serialization and a
cryptographic hash, never Python `hash()`.

---

# STEP 18 — IMPLEMENTATION LOCATION

Task 1.4 makes:

```text
src/embeddings/
```

a real package.

Prefer a small reusable module such as:

```text
src/embeddings/bge.py
```

with separate functions for:

```text
load_model
encode_passages
encode_queries
validate_vectors
```

Use a thin orchestration script such as:

```text
scripts/embed_development_corpus.py
```

if consistent with current script conventions.

Do not put production logic in:

```text
scripts/serving_spike.py
src/chunk/
src/index/
```

---

# STEP 19 — USE FOUNDATION BOUNDARIES

Use:

```text
src.config
src.storage
src.logging_utils
```

where appropriate.

Do not add scattered:

```text
Path("artifacts/...")
os.getenv(...)
logging.basicConfig(...)
```

If an embedding storage helper is approved, add it narrowly and test it.

---

# STEP 20 — PROCESS CHUNKS EFFICIENTLY

Embed in batches.

Avoid loading multiple unnecessary full copies of:

```text
all chunk texts
all vectors
all metadata
```

Use existing PyArrow/Parquet batching where practical.

Do not introduce distributed processing.

This is a single-GPU Phase 1 baseline.

Preserve a deterministic row order.

---

# STEP 21 — VECTOR ↔ CHUNK ALIGNMENT

Every output vector must map mechanically to exactly one Task 1.3 `chunk_id`.

Do not rely on asynchronous completion ordering.

Required invariant:

```text
vector i ↔ chunk_id i
```

or an equivalently explicit approved mapping.

The full output must preserve this contract across writes and reloads.

---

# STEP 22 — PRE-FULL-BUILD PASSAGE SMOKE

Before embedding all chunks, encode a small deterministic subset.

Verify:

```text
CUDA execution
dimension == 384
all finite
approved dtype
approved normalization behavior
correct chunk IDs/order
```

Do not proceed to the full build if this fails.

---

# STEP 23 — QUERY SMOKE

Encode a few SEC-style queries with the approved query path.

Verify:

```text
shape = (N, 384)
all finite
approved dtype
approved normalization semantics
query convention applied exactly once
```

No vector search.

No retrieval quality claims.

---

# STEP 24 — NUMERIC VALIDATION

For every produced passage vector:

```text
dimension == 384
no NaN
no +Inf
no -Inf
dtype matches contract
```

If normalization is enabled:

verify vector norms within a documented floating-point tolerance.

If normalization is disabled:

do not impose unit-norm checks.

---

# STEP 25 — FULL BUILD

Embed all:

```text
162,357
```

Task 1.3 chunks using the approved passage convention.

Task 1.4 cannot PASS from a subset-only run.

Record actual:

```text
vector count
batch size
model revision
dimension
dtype
normalization
GPU device
```

No estimates.

---

# STEP 26 — MEASURE THROUGHPUT

Task 1.4 explicitly requires throughput measurement.

Measure the real build.

Record at minimum:

```text
chunks embedded
embedding inference seconds
chunks/second
```

Also record:

```text
tokens/second
```

if practical using Task 1.3 token counts.

Where practical separate:

```text
model load
input read/preparation
embedding inference
artifact write
total wall time
```

Do not reuse Task 0.2's tiny smoke throughput as the corpus result.

---

# STEP 27 — RECORD GPU MEMORY

Record during the real build:

```text
peak torch CUDA allocated memory
peak torch CUDA reserved memory
```

Do not treat this as a full hardware capacity benchmark.

It is Task 1.4 build evidence.

---

# STEP 28 — SAFE ARTIFACT WRITING

Do not leave partial output looking complete after failure.

Use the repository's existing safe generated-artifact convention.

Prefer temporary output then finalization/rename when appropriate.

If an existing artifact is found:

- inspect its config/provenance,
- reuse only if current policy says it is compatible,
- do not overwrite a conflicting artifact silently.

If overwrite behavior is undefined:

**STOP AND ASK ME.**

---

# STEP 29 — FULL OUTPUT VALIDATION

Required:

```text
input chunks  = 162,357
output vectors = 162,357
```

Verify:

```text
unique output chunk IDs = 162,357
no missing IDs
no duplicate IDs
no extra IDs
all vectors dimension 384
all vectors finite
```

The 7 empty-source filings already generated zero chunks in Task 1.3, so
Task 1.4 creates no separate empty-document vectors.

---

# STEP 30 — METADATA VALIDATION

If metadata is stored alongside vectors, verify it against Task 1.3.

At minimum completely verify:

```text
chunk_id
document_id
cik
fiscal_year
chunk_config_hash
```

and every additional field required by the approved Task 1.4 schema.

Do not rely only on manual sampling for identity invariants.

---

# STEP 31 — MANUAL TRACEABILITY

Inspect at least 10 output rows.

Trace:

```text
Task 1.3 chunk
→ Task 1.4 embedding row/vector
```

Include:

```text
a first chunk
a final partial chunk
a very short chunk
a chunk from a long document
multiple fiscal years
```

Verify metadata and vector shape/finite values.

---

# STEP 32 — REPEAT / NUMERIC STABILITY CHECK

GPU embeddings do not need to be assumed byte-identical unless the project
explicitly requires that.

Run a second fresh-process encoding check on a deterministic small subset.

Verify:

```text
same model revision
same config
same chunk IDs/order
same shape/dtype
numerically close vectors
```

Use and document a justified tolerance.

If current project docs require a stronger determinism contract, follow it.

---

# STEP 33 — TRACKED SUMMARY

Create a small tracked summary under `results/`.

A likely repository-consistent name is:

```text
results/phase_1_4_embedding_summary.json
```

but inspect naming conventions first.

Include the actual resolved:

```text
input chunk_config_hash
input row count
model/revision
dimension
query convention
passage convention
normalization
dtype
batch size
precision policy
device
artifact path/format
vector count
throughput
runtime components
peak VRAM
artifact size
created_at_utc
```

If an approved embedding artifact/config identity exists, include it.

Do not put vectors into tracked JSON.

---

# STEP 34 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_EMBEDDINGS.md
```

unless current conventions clearly specify another name.

Document:

```text
purpose
Task 1.3 input provenance
model identity/revision
query convention
passage convention
normalization
dtype
dimension
GPU/device/batch/precision policy
offline policy
artifact location/format
metadata mapping
measured throughput
measured GPU memory
validation
known limitations
next consumer: Task 1.5
```

Known limitations should explicitly include:

```text
Phase 1 baseline only
one embedding model only
no embedding-model ablation
no retrieval-quality claim
no quantization experiment
no LanceDB index yet
```

Update `project_plan/REPOSITORY_STRUCTURE.md` only as needed to mark
`src/embeddings/` implemented.

---

# STEP 35 — TESTS

Add focused tests, for example:

```text
tests/test_baseline_embeddings.py
```

Cover the approved behavior for:

```text
query convention
passage convention
query/passages remain separate
dimension validation
finite-value validation
dtype validation
normalization validation if enabled
metadata alignment
config validation
artifact identity helper if implemented
```

Use tiny fixtures.

Do not run the full 162,357-vector build in pytest.

---

# STEP 36 — OFFLINE GPU/MODEL INTEGRATION TEST

Where appropriate, add a marked test using existing project marker policy.

It should:

```text
pre-check local model cache
load BGE offline
verify CUDA
encode tiny passage batch
encode tiny query batch
verify (N, 384)
verify finite values
```

Do not download during tests.

Missing capability may skip only under the project's existing policy.

Present-but-broken cache/GPU must fail.

---

# STEP 37 — NO INDEX OR RETRIEVAL

Do NOT:

```text
create LanceDB table
create ANN index
perform nearest-neighbor search
measure recall
implement retriever
build BM25
rerank
```

Those begin in later tasks.

Task 1.4 ends with a validated embedding artifact.

---

# STEP 38 — NO MODEL ABLATION

Do not run:

```text
bge-base
nomic
Qwen3
Titan
```

Phase 3 owns embedding comparisons.

Task 1.4 uses only the frozen Phase 1 baseline.

---

# STEP 39 — NO INDEX QUANTIZATION

Do not perform binary/product quantization experiments.

Do not conflate Task 0.10's serving-spike IVF_PQ experiment with Task 1.4.

Persist only the explicitly approved Task 1.4 vector dtype.

---

# STEP 40 — INPUT SAFETY

After the build confirm:

```text
Task 1.3 chunks.parquet unchanged
Task 1.2 normalized Markdown unchanged
frozen data/ unchanged
```

The embedder is a consumer.

It must not rewrite its inputs.

---

# STEP 41 — RUN ALL TESTS

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

Do not hardcode the previous 144-test total.

---

# STEP 42 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Verify large vectors/model caches remain ignored.

Expected trackable files may include:

```text
src/embeddings/...
scripts/embed_development_corpus.py
configs/<Task 1.4 config>.json
results/phase_1_4_embedding_summary.json
tests/test_baseline_embeddings.py
project_plan/PHASE1_EMBEDDINGS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
prompt file if prompts are tracked
```

No vector files or model weights should be staged.

Run the normal secret/personal-path scan.

---

# STEP 43 — UPDATE Progress.md

Append:

```markdown
## YYYY-MM-DD — Phase 1.4 Baseline Embedding Pipeline
```

Preserve all prior history.

Include:

### Objective

Task 1.4 converts the Task 1.3 fixed-window corpus to BGE dense vectors for
Task 1.5.

### Initial State

Record:

```text
Task 1.3 commit
chunk_config_hash
chunk artifact
input row count
```

### User Decisions / Clarifications

Record every question asked and approved answer.

### Model Contract

```text
model repository
resolved revision
dimension
sentence-transformers version
torch/CUDA versions
GPU
```

### Query / Passage Contract

Record exact behavior.

### Vector Contract

```text
normalization
dtype
dimension
```

### Build Configuration

```text
device
batch size
precision policy
offline/cache policy
```

### Output

```text
artifact location
format
metadata policy
vector count
artifact size
artifact identity if approved
```

### Performance

```text
model load time
embedding inference time
artifact write time
total wall time
chunks/sec
tokens/sec if measured
peak VRAM allocated/reserved
```

### Validation

```text
row count
unique chunk IDs
dimensions
finite values
dtype
normalization if applicable
metadata traceability
manual inspection
repeat numeric-stability check
```

### Tests

Record:

```text
new Task 1.4 tests
doctor
portable suite
full suite
```

### Safety

Confirm:

```text
chunks unchanged
normalized files unchanged
data unchanged
no network download
embedding artifact ignored
no index/retrieval created
```

### Files Created / Modified

List actual tracked files only.

### Git

Record Task 1.4 commit details.

### Result

Use exactly one:

```text
PASS — baseline BGE embeddings generated for all Phase 1 chunks

WARN — baseline embeddings generated with one documented non-blocking issue

BLOCKED — baseline embedding artifact could not be established safely
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
  1.5 Vector-Only Index            — NEXT
```

---

# STEP 44 — COMMIT TASK 1.4

After:

```text
full real build passes
artifact validation passes
tests pass
large vector artifact confirmed ignored
tracked changes reviewed
Progress.md updated
```

create one coherent Task 1.4 commit.

Preferred message:

```text
Add baseline BGE embedding pipeline
```

Do not include Task 1.5 work.

Do not tag Phase 1 yet.

---

# STEP 45 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote is configured:

```text
push deferred — no remote configured
```

Do not invent one.

If a remote exists and push authorization is clearly established by the
repository policy, follow it.

If ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.4 is complete only if:

```text
[ ] Task 1.3 committed
[ ] Task 1.3 artifact/provenance verified
[ ] exactly 162,357 input chunks
[ ] all input chunk IDs unique

[ ] exact BAAI/bge-small-en-v1.5 model used
[ ] local model revision verified
[ ] dimension verified as 384
[ ] model loads offline
[ ] no silent model download/substitution

[ ] query convention explicitly resolved
[ ] passage convention explicitly resolved
[ ] full corpus embedded with passage convention
[ ] query helper smoke passes

[ ] normalize_embeddings explicitly resolved
[ ] persisted dtype explicitly resolved
[ ] GPU batch size explicitly resolved
[ ] precision policy explicitly resolved

[ ] full build runs on CUDA
[ ] no CPU fallback
[ ] all vectors finite
[ ] every vector has dimension 384
[ ] dtype matches contract
[ ] norm checks pass if normalization enabled

[ ] embedding artifact location explicitly resolved
[ ] artifact format explicitly resolved
[ ] metadata policy explicitly resolved
[ ] artifact identity/versioning explicitly resolved if needed
[ ] no unapproved storage convention invented

[ ] exactly 162,357 output vectors
[ ] all output chunk IDs unique
[ ] vector-to-chunk mapping verified
[ ] approved metadata preserved

[ ] real-build throughput measured
[ ] chunks/sec recorded
[ ] runtime recorded
[ ] batch size recorded
[ ] peak VRAM recorded
[ ] artifact size recorded

[ ] manual traceability inspection passes
[ ] fresh-process sample stability check passes

[ ] focused Task 1.4 tests added
[ ] doctor passes
[ ] portable suite has zero failures
[ ] full suite has zero failures

[ ] chunks.parquet unchanged
[ ] normalized Markdown unchanged
[ ] frozen data unchanged

[ ] no LanceDB index built
[ ] no retrieval implemented
[ ] no model ablation
[ ] no network download

[ ] PHASE1_EMBEDDINGS.md created
[ ] repository structure docs updated where needed
[ ] Progress.md updated

[ ] generated vectors git-ignored
[ ] staged content reviewed
[ ] one Task 1.4 commit created
[ ] no Task 1.5 work included
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.3 artifact does not match provenance

exact BGE model revision is ambiguous

required model assets are missing from local cache

query convention is unclear

passage convention is unclear

normalize_embeddings is not defined

vector dtype is not defined

batch-size policy is not defined

precision/autocast policy is not defined

embedding artifact location is not defined

embedding artifact format is not defined

metadata retention policy is not defined

artifact identity/versioning is needed but undefined

existing embedding artifact conflicts with current config

a new dependency appears necessary

CUDA fails or model falls back to CPU

OOM requires an unapproved batch-size change

documentation materially conflicts

Git push authorization is unclear

any other durable implementation choice would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.4 does NOT:

```text
change Task 1.3 chunking
re-chunk documents
modify the development manifest
modify normalized Markdown
build LanceDB
create ANN indexes
perform vector search
implement retrieval
measure recall
build BM25
build hybrid retrieval
rerank
implement CRAG
implement routing
call an LLM
generate evaluation questions
compare embedding models
run Phase 3 ablations
```

The desired result is only:

```text
162,357 Phase 1 chunks
        ↓
BAAI/bge-small-en-v1.5
approved passage convention
GPU batch inference
        ↓
162,357 traceable dense vectors
        ↓
Task 1.5
```

---

# FINAL RESPONSE TO ME

Return:

## Task

```text
task_1.4_baseline_embedding_pipeline.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input

```text
chunk_config_hash
chunk artifact path
input row count
unique chunk IDs
```

## User Decisions

List every clarification asked and approved answer.

## Model

```text
model repository
model revision
embedding dimension
sentence-transformers version
torch version
CUDA runtime
GPU model
```

## Query / Passage Contract

Report exact query and passage conventions.

## Vector Contract

```text
normalize_embeddings
vector dtype
dimension
```

## Build Configuration

```text
device
batch size
precision policy
offline/local-only status
```

## Output

```text
artifact path
artifact format
vector count
metadata policy
artifact size
artifact/config identity if implemented
```

## Performance

```text
model load time
embedding inference time
artifact write time
total wall time
chunks/sec
tokens/sec if measured
peak GPU allocated memory
peak GPU reserved memory
```

## Validation

```text
finite vectors: PASS/FAIL
dimension: PASS/FAIL
dtype: PASS/FAIL
normalization: PASS/FAIL/N/A
vector-to-chunk traceability: PASS/FAIL
manual rows inspected
```

## Repeat Check

```text
fresh-process sample size
same model/config: YES/NO
same IDs/order: YES/NO
numerically close: YES/NO
tolerance used
```

## Tests

```text
new Task 1.4 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
GPU smoke PASS/FAIL
```

## Safety

Confirm:

```text
chunks.parquet unchanged
normalized Markdown unchanged
data/ unchanged
no network download
embedding artifact ignored by Git
no LanceDB index created
no retrieval implemented
```

## Files Modified

List actual tracked/project files only.

## Git

```text
commit created: YES/NO
commit hash
commit message
remote status
push performed: YES/NO
```

## Progress.md

Confirm the Phase 1.4 entry was appended.

## Next Task

If PASS:

```text
task_1.5_vector_only_index.md
```

Do not start it.

Finally state:

```text
No Task 1.5 work started.
```

Stop and wait for my approval.
