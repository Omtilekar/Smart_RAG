# Task 0.7 — Storage Abstraction

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.7 — Storage Abstraction
```

Current Phase 0 status:

```text
0.0 Git Safety Preflight       — COMPLETE
0.1 Python Environment         — COMPLETE
0.2 CUDA/GPU Validation        — COMPLETE
0.3 Repository Structure       — COMPLETE
0.4 Dependency Management      — COMPLETE
0.5 Configuration System       — COMPLETE
0.6 Logging                    — COMPLETE
0.7 Storage Abstraction        — CURRENT
```

Existing foundation:

```text
src/config.py
    centralized configuration
    repo_root
    STORAGE_ROOT
    environment overrides

src/logging_utils.py
    centralized application logging

data/
    frozen source/derived data from Data Preparation

artifacts/
    intended generated runtime artifacts
    Git-ignored

results/
    small public metrics/reports
    selected .csv/.json/.md files trackable
```

The purpose of this task is to establish **one authoritative storage/layout boundary** so future modules do not invent filesystem paths independently.

Future code should not contain scattered logic such as:

```python
Path("data/xbrl.duckdb")
Path("artifacts/chunks")
Path("index/foo")
Path("results/eval.json")
```

Instead, those locations should come from:

```text
src/storage.py
```

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. inspect the actual existing data/artifact layout,
2. define frozen-input vs generated-output boundaries,
3. create `src/storage.py`,
4. centralize known source-data paths,
5. centralize generated artifact paths,
6. support deterministic versioned artifact paths,
7. establish safe path-component handling,
8. provide explicit directory-creation helpers for generated outputs only,
9. avoid import-time filesystem mutation,
10. keep the design local-first but future-S3-compatible,
11. document the storage contract,
12. update `Progress.md`.

Do NOT begin:

```text
0.8 Basic Automated Tests
0.9 Developer Commands
0.10 Serving Feasibility Spike
```

Do NOT implement Phase 1 normalization/chunking/indexing.

---

# CORE STORAGE PRINCIPLES

The storage system must follow these rules:

```text
1. Frozen input data is read-only.
2. Generated artifacts never overwrite frozen input data.
3. No module invents its own project path.
4. Generated artifacts are versioned where reproducibility requires it.
5. Importing storage code has no filesystem side effects.
6. Directory creation is explicit.
7. Paths are portable across Windows/Linux.
8. No personal absolute path is committed.
9. Logical artifact identities should be backend-neutral.
10. Local filesystem works now.
11. Future S3 support remains possible.
12. Do not claim S3 support until it actually exists.
```

---

# STEP 1 — VERIFY ENVIRONMENT

Activate:

```text
.venv/
```

Verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

Expected:

```text
Python 3.11.9
interpreter inside .venv
```

Verify the current configuration:

```python
from src.config import get_settings

settings = get_settings()

print(settings.repo_root)
print(settings.storage_root)
```

Do not expose personal path components in tracked documentation.

---

# STEP 2 — INSPECT THE ACTUAL STORAGE LAYOUT

Inspect the repository and existing `data/` structure.

Do not recursively print millions of files.

Identify at minimum the actual locations of:

```text
MS MARCO
EDGAR-CORPUS
raw XBRL ZIPs
XBRL DuckDB
primary SEC HTML filings
interim audit metadata
validation report
```

Expected approximate current layout is conceptually:

```text
data/
├── .gitkeep
├── msmarco/
├── edgar_corpus/
├── raw/
│   ├── xbrl/
│   └── primary/
├── interim/
├── xbrl.duckdb
└── validation_report.md
```

Use the filesystem as truth.

Do not rename or move anything.

---

# STEP 3 — READ STORAGE-RELATED DOCUMENTATION

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/CONFIGURATION.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/GIT_CONVENTIONS.md
Progress.md
```

Pay particular attention to:

```text
frozen data policy
artifact versioning
chunk_config_hash
LanceDB storage
Parquet chunks
evaluation artifacts
small committed result files
future S3 serving assumptions
```

Do not redesign the project architecture during this task.

---

# STEP 4 — FREEZE THE READ/WRITE BOUNDARY

Explicitly define two storage classes of content.

## Frozen Inputs

Existing Data Preparation artifacts such as:

```text
data/msmarco/
data/edgar_corpus/
data/raw/xbrl/
data/raw/primary/
data/xbrl.duckdb
```

must be treated as:

```text
READ-ONLY INPUTS
```

`src/storage.py` must never automatically:

```text
delete
rename
move
truncate
overwrite
repartition
download into
```

these locations.

---

# STEP 5 — DEFINE GENERATED OUTPUTS

Generated engineering artifacts should live separately from frozen inputs.

Use:

```text
<repo>/artifacts/
```

as the local generated-artifact root unless the repository already defines another authoritative convention.

Expected conceptual layout:

```text
artifacts/
├── normalized/
├── chunks/
├── indexes/
├── eval/
└── cache/
```

Do not create all of these directories merely by importing the module.

They should appear only when explicitly requested by future workflows.

Do not place new generated pipeline artifacts inside frozen source-data directories.

---

# STEP 6 — DEFINE PUBLIC RESULTS

Keep:

```text
<repo>/results/
```

separate from large/generated artifacts.

Its purpose is:

```text
small evaluation summaries
small experiment comparisons
small JSON metadata
CSV metric tables
human-readable Markdown summaries
```

These may be committed when useful.

Do not use `results/` for:

```text
embeddings
LanceDB indexes
Parquet chunk corpora
model weights
large traces
large databases
```

Those belong under:

```text
artifacts/
```

---

# STEP 7 — CREATE `src/storage.py`

Create:

```text
src/storage.py
```

Keep it focused.

A reasonable design is a frozen dataclass such as:

```python
@dataclass(frozen=True)
class StoragePaths:
    repo_root: Path
    data_root: Path
    artifacts_root: Path
    results_root: Path
```

with a factory such as:

```python
StoragePaths.from_settings(...)
```

or:

```python
get_storage()
```

Use actual design names that remain simple and obvious.

---

# STEP 8 — PUBLIC API

Prefer a small public interface.

Conceptually something like:

```python
StoragePaths
get_storage()

# frozen inputs
storage.msmarco_root
storage.edgar_corpus_root
storage.xbrl_db
storage.raw_xbrl_root
storage.primary_docs_root

# generated outputs
storage.normalized_dir(version)
storage.chunks_dir(chunk_config_hash)
storage.index_dir(chunk_config_hash, embedding_model)
storage.eval_dir(eval_version)

# public summaries
storage.results_root
```

Adapt to actual project needs.

Do not add dozens of one-line properties for hypothetical future artifacts.

---

# STEP 9 — CENTRALIZE KNOWN FROZEN INPUT PATHS

At minimum expose stable access to the actual existing inputs:

```text
MS MARCO root
EDGAR-CORPUS root
raw XBRL root
primary filing root
XBRL DuckDB
```

Also expose the validation report/interim audit location only if current engineering code genuinely needs them.

Do not turn every file under `data/` into a property.

The goal is useful centralization, not mirroring the entire filesystem in Python.

---

# STEP 10 — DO NOT VALIDATE LARGE DATA AT IMPORT TIME

Constructing:

```python
storage = get_storage()
```

must not:

```text
scan 90M XBRL facts
open DuckDB
walk 990 filings
count Parquet rows
read ZIPs
```

Path construction must be cheap.

Existence validation, when needed, should be explicit.

---

# STEP 11 — PROVIDE LIGHTWEIGHT EXISTENCE CHECKS

A small helper is acceptable, conceptually:

```python
storage.require_file(storage.xbrl_db)
storage.require_dir(storage.primary_docs_root)
```

or equivalent.

It should:

```text
check existence/type
raise a clear StorageError if missing
```

It must not perform content validation.

Do not duplicate Data Preparation validation logic.

---

# STEP 12 — GENERATED ARTIFACT VERSIONING

The project has already frozen the principle that generated artifacts must carry reproducibility identity.

Support deterministic paths for versioned outputs.

At minimum:

```text
normalized documents
chunks
indexes
evaluation artifacts
```

should be able to receive stable version identifiers.

Examples:

```text
artifacts/normalized/<normalizer_version>/

artifacts/chunks/<chunk_config_hash>/

artifacts/indexes/<chunk_config_hash>/<embedding_model_key>/

artifacts/eval/<eval_version>/
```

These are conceptual examples.

Use the execution plan as the authority if it defines a stronger layout.

---

# STEP 13 — CHUNK CONFIG HASH SUPPORT

The frozen chunking design uses:

```text
chunk_config_hash
```

as part of artifact identity.

Provide a storage helper such as:

```python
storage.chunks_dir(chunk_config_hash)
```

which deterministically maps a config hash to one location.

Do NOT implement chunk hashing itself.

Task 0.7 only consumes the supplied hash.

Hash creation belongs to the chunk/config implementation later.

---

# STEP 14 — INDEX IDENTITY

The same chunk configuration may be embedded with several models during Phase 3.

Therefore an index path must not be identified only by:

```text
index/
```

or only by:

```text
embedding model
```

At minimum index identity should support:

```text
chunk configuration
+
embedding model
```

Conceptually:

```text
artifacts/indexes/
    <chunk_config_hash>/
        <embedding_model_key>/
```

Do not implement LanceDB itself.

Do not create a real index.

---

# STEP 15 — SAFE MODEL IDENTIFIERS

Embedding model names may contain:

```text
/
:
spaces
```

For example:

```text
BAAI/bge-small-en-v1.5
```

Do not insert arbitrary model names directly into OS paths without normalization.

Implement a deterministic safe-component helper.

For example, conceptually:

```text
BAAI/bge-small-en-v1.5
    ->
BAAI--bge-small-en-v1.5
```

The exact convention may differ.

Requirements:

```text
deterministic
portable
human-readable where possible
no path traversal
```

Document the convention.

---

# STEP 16 — PATH TRAVERSAL SAFETY

Helpers receiving user/config-provided identifiers must reject dangerous components such as:

```text
../
..\ 
absolute paths
drive-qualified paths
empty identifiers
.
..
```

For example:

```python
storage.chunks_dir("../escape")
```

must fail.

Generated artifact helpers must never escape:

```text
artifacts_root
```

through malicious or malformed path components.

Use a clear exception such as:

```text
StorageError
```

---

# STEP 17 — LOGICAL KEYS FOR FUTURE S3 COMPATIBILITY

This project is local-first now but may later store artifacts in S3.

Do NOT implement:

```text
boto3
s3fs
AWS credentials
S3 uploads
S3 downloads
```

during this task.

Instead, keep artifact identity conceptually backend-neutral.

Where useful, represent logical artifact keys with POSIX-style components, for example:

```text
chunks/<chunk_config_hash>
indexes/<chunk_config_hash>/<model_key>
```

Then local storage can resolve those keys beneath:

```text
artifacts_root
```

A future S3 backend could map the same logical key beneath an S3 prefix.

You may expose something like:

```python
artifact_key(...)
```

only if it makes the implementation clearer.

Do not create an elaborate cloud interface with no real consumer.

---

# STEP 18 — DO NOT CREATE A FAKE S3 BACKEND

Do not write classes like:

```text
S3Storage
CloudStorage
RemoteStorage
```

that are untested placeholders.

Document:

```text
S3 backend — future work
```

instead.

An abstraction that lies about supported functionality is worse than a small local implementation with a clean future boundary.

---

# STEP 19 — EXPLICIT DIRECTORY CREATION

Importing:

```python
import src.storage
```

must create nothing.

Calling:

```python
get_storage()
```

must create nothing.

Directory creation must require an explicit operation.

A helper such as:

```python
ensure_dir(path)
```

or:

```python
storage.ensure_artifact_dir(...)
```

is acceptable.

---

# STEP 20 — OUTPUT CREATION MUST BE RESTRICTED

If an explicit directory-creation helper exists, it must only create paths under approved generated roots such as:

```text
artifacts_root
results_root
```

It must refuse to create or mutate paths inside frozen inputs except when explicitly designed for harmless checks.

For example:

```python
ensure_output_dir(storage.xbrl_db.parent)
```

should not be the normal API.

The abstraction should make the safe behavior obvious.

---

# STEP 21 — EXISTING DATA MUST REMAIN UNCHANGED

Before and after the task, record lightweight metadata for important frozen inputs, such as:

```text
existence
file size for xbrl.duckdb
number of top-level source directories
```

Do not hash tens of gigabytes.

Verify Task 0.7 did not change:

```text
data/xbrl.duckdb
data/msmarco/
data/edgar_corpus/
data/raw/
```

No downloads.

No migrations.

No deletions.

---

# STEP 22 — SMOKE-VERIFY FROZEN PATHS

Using the new abstraction, verify:

```text
MS MARCO path exists
EDGAR-CORPUS path exists
XBRL DuckDB exists
raw XBRL directory exists
primary filings directory exists
```

Do not execute heavy queries.

This verifies the abstraction matches reality.

---

# STEP 23 — SMOKE-VERIFY GENERATED PATHS

Ask the storage abstraction for representative paths such as:

```text
normalized version
chunk config hash
index path
eval version
```

Verify:

```text
paths are deterministic
paths remain under artifacts/
same input => same path
different config/model => different path
```

Do not build the artifacts themselves.

---

# STEP 24 — TEST SAFE COMPONENT NORMALIZATION

Verify at minimum:

```text
BAAI/bge-small-en-v1.5
simple-model
model with spaces
```

produce deterministic safe path components.

Also verify dangerous values such as:

```text
../escape
..\escape
/path
C:\escape
..
```

are rejected where applicable.

---

# STEP 25 — TEST EXPLICIT DIRECTORY CREATION

Use a temporary generated path under:

```text
.tmp/
```

or a deliberately disposable child under `artifacts/`.

Prefer `.tmp/` if the production helper allows test injection of a temporary root.

Verify:

```text
directory absent before explicit call
constructing storage does not create it
explicit creation creates it
repeat creation is idempotent
cleanup succeeds
```

Do not leave test artifacts behind unnecessarily.

If using `artifacts/`, remove the smoke-test directory afterward.

---

# STEP 26 — DO NOT IMPLEMENT FILE I/O FRAMEWORKS

Do not create abstractions for every possible operation such as:

```text
read_json()
write_json()
read_parquet()
write_parquet()
open_duckdb()
open_lancedb()
read_markdown()
```

Those belong close to the components that actually use those formats.

Task 0.7 centralizes:

```text
location
identity
safe output creation
```

not every serialization format.

---

# STEP 27 — DO NOT IMPLEMENT STORAGE FOR LOGGING

Task 0.6 deliberately chose:

```text
console/stderr logging
```

Do not introduce:

```text
logs_root file logging
rotating log files
```

during this task.

`logs/` may remain a Git-ignored conceptual runtime directory.

---

# STEP 28 — DO NOT IMPLEMENT CACHE POLICY

A future cache directory may be represented if genuinely needed, but do not implement:

```text
cache eviction
TTL
LRU
model cache management
Hugging Face cache relocation
```

in Task 0.7.

---

# STEP 29 — DO NOT MODIFY FROZEN INGESTION PATHS

Existing acquisition code may still contain historical path logic.

Do not broadly refactor:

```text
src/ingest/
```

to use `src.storage`.

Data Preparation is complete.

New application code should use the abstraction going forward.

If a tiny future-facing compatibility change is essential, explain it first and preserve existing behavior.

Preferred outcome:

```text
src/ingest/ unchanged
```

---

# STEP 30 — INTEGRATE WITH CONFIGURATION

`src/storage.py` should consume:

```text
src.config.Settings
```

rather than independently reading:

```text
STORAGE_ROOT
os.environ
.env
```

Desired dependency direction:

```text
src.config
   ↓
src.storage
   ↓
future pipeline modules
```

Do not duplicate environment loading logic.

---

# STEP 31 — LOGGING INTEGRATION

Storage code may use:

```python
get_logger(__name__)
```

from:

```text
src.logging_utils
```

if there is a useful event to log.

However, simple path construction should not spam logs.

Reasonable events might occur when an explicit directory is created.

Do not make logging required for basic path resolution if that complicates the design.

---

# STEP 32 — NO NEW DEPENDENCIES

Expected new dependency count:

```text
0
```

Use:

```text
pathlib
dataclasses
functools
typing
```

and other standard-library facilities.

Do not add:

```text
fsspec
s3fs
boto3
cloudpathlib
```

during this task.

If you believe one is required, stop and explain why before changing dependency files.

---

# STEP 33 — CREATE STORAGE DOCUMENTATION

Create:

```text
project_plan/STORAGE.md
```

Explain:

```text
storage goals
frozen vs generated boundary
local directory layout
public results vs large artifacts
src/storage.py API
artifact versioning
chunk_config_hash role
embedding-model path normalization
directory-creation policy
path traversal protection
future S3 compatibility boundary
```

Include a compact tree.

Example:

```text
data/                         # frozen/local project inputs
├── msmarco/
├── edgar_corpus/
├── raw/
│   ├── xbrl/
│   └── primary/
└── xbrl.duckdb

artifacts/                    # generated, ignored
├── normalized/<version>/
├── chunks/<chunk_config_hash>/
├── indexes/<chunk_hash>/<model_key>/
└── eval/<eval_version>/

results/                      # small shareable summaries
```

Adapt to the actual implementation.

---

# STEP 34 — DOCUMENT S3 STATUS ACCURATELY

`STORAGE.md` must explicitly say:

```text
Current backend: local filesystem
S3 backend: not implemented
```

Then explain that logical artifact identities/layout are designed so a later backend can map the same keys into S3.

Do not write:

```text
S3 supported
```

or:

```text
cloud-ready
```

without qualification.

---

# STEP 35 — UPDATE REPOSITORY DOCUMENTATION

Review:

```text
project_plan/REPOSITORY_STRUCTURE.md
project_plan/CONFIGURATION.md
```

Make only small cross-link/status updates where appropriate.

For example:

```text
src/storage.py — implemented in Phase 0.7
```

and link to:

```text
STORAGE.md
```

Do not duplicate the entire storage design across documents.

---

# STEP 36 — LIGHTWEIGHT IMPORT VERIFICATION

In a fresh process:

```python
import src.storage
```

Verify it does not import/load:

```text
torch
sentence_transformers
duckdb
lancedb
pyarrow
```

unless strictly necessary.

Expected:

```text
storage import is lightweight
```

It should also create no directories.

---

# STEP 37 — CONFIG OVERRIDE VERIFICATION

Use a temporary process environment with an alternate:

```text
STORAGE_ROOT
```

pointing to a safe temporary location.

Clear the cached configuration where necessary.

Verify:

```text
new StoragePaths uses overridden data root
repo artifacts/results behavior remains deterministic
no directories created merely by loading configuration/storage
```

Do not modify the developer's permanent environment.

---

# STEP 38 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not actually stage.

Verify:

```text
src/storage.py                trackable
project_plan/STORAGE.md       trackable
Progress.md                   trackable

data contents                 ignored
artifacts/                    ignored
.venv                         ignored
.tmp                          ignored
.env                          ignored
model caches                  ignored
```

Ensure no new generated storage artifact is stageable.

---

# STEP 39 — SECRET / PERSONAL PATH SCAN

Inspect all files created or modified during this task for:

```text
API keys
tokens
passwords
credentials
real email addresses
personal absolute paths
AWS access keys
S3 credentials
```

No secret should appear.

No local username should be embedded in tracked documentation.

---

# STEP 40 — UPDATE `Progress.md`

Preserve all existing history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.7 Storage Abstraction
```

using the current local date.

Include:

## Objective

Explain that storage semantics were centralized before Phase 1 starts producing artifacts.

## Initial State

Summarize:

```text
frozen data layout existed
artifacts/results directories conceptually existed
future modules had no centralized path API
STORAGE_ROOT already came from src.config
```

## Storage Design

Record:

```text
module/API
frozen-input root
generated-artifact root
results root
read/write boundary
directory-creation behavior
```

## Frozen Inputs

List the major canonical paths exposed by the abstraction.

## Generated Layout

Show the artifact layout.

## Versioning

Explain:

```text
normalizer version
chunk_config_hash
embedding model identity
eval version
```

only to the extent actually implemented by path helpers.

Do not imply those downstream systems exist yet.

## S3 Boundary

State explicitly:

```text
local filesystem implemented
S3 not implemented
logical artifact layout designed for later backend mapping
```

## Verification

Report PASS/FAIL for:

```text
frozen input paths resolve
generated paths deterministic
different versions produce different locations
safe model-key conversion
path traversal rejection
explicit directory creation
no import-time directory creation
STORAGE_ROOT override
lightweight import
frozen data unchanged
Git safety
```

## Existing Ingestion

State whether `src/ingest/` changed.

Preferred:

```text
unchanged — frozen Data Preparation code retained
```

## Files Created / Modified

Likely:

```text
src/storage.py
project_plan/STORAGE.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/CONFIGURATION.md
Progress.md
```

List only actual changes.

## Result

Use exactly one:

```text
PASS — centralized storage abstraction established

WARN — storage abstraction works but one non-blocking issue remains

BLOCKED — storage abstraction cannot be established safely
```

## Phase Status

If PASS:

```text
Data Preparation                  — COMPLETE
Phase 0                           — IN PROGRESS
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.7 is complete only if:

```text
[ ] actual data layout inspected

[ ] frozen-input vs generated-output boundary documented

[ ] src/storage.py exists
[ ] storage consumes src.config
[ ] storage does not independently read environment variables

[ ] major frozen source paths centralized
[ ] xbrl.duckdb path centralized
[ ] primary-doc path centralized

[ ] artifacts root centralized
[ ] results root centralized
[ ] frozen data and generated artifacts remain separate

[ ] normalized artifact path supported
[ ] chunks path supports chunk_config_hash
[ ] index path supports chunk config + embedding model
[ ] eval artifact path supports version identity

[ ] model names converted safely/deterministically for path use
[ ] dangerous path components rejected
[ ] artifact helpers cannot escape generated root

[ ] importing src.storage creates no directories
[ ] get_storage()/equivalent creates no directories
[ ] output directory creation is explicit
[ ] repeated explicit creation is safe/idempotent

[ ] frozen inputs remain unchanged
[ ] no downloads performed
[ ] no database migration performed
[ ] no large data copied

[ ] local filesystem is the only implemented backend
[ ] S3 is explicitly documented as NOT IMPLEMENTED
[ ] logical layout remains suitable for future S3 mapping
[ ] no fake S3 backend created
[ ] no AWS dependency added

[ ] storage import is lightweight
[ ] no model/database/vector initialization at import

[ ] project_plan/STORAGE.md exists
[ ] repository/config documentation remains consistent

[ ] no Phase 1 feature implementation added
[ ] no LanceDB index built
[ ] no chunks generated
[ ] no normalized docs generated
[ ] no eval dataset generated

[ ] Git dry-run safe
[ ] Progress.md updated

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.8 work not started
```

---

# STOP CONDITIONS

Stop and report instead of forcing the design if:

```text
existing configuration semantics make frozen inputs and generated outputs impossible to separate cleanly

an existing functional storage module already defines a materially different contract

a proposed change would require moving or renaming frozen data

the abstraction would require mutating data/xbrl.duckdb

S3 support would require adding cloud dependencies now

path helpers could escape their intended roots
```

Prefer a smaller truthful local abstraction over speculative cloud complexity.

---

# IMPORTANT NON-GOALS

Task 0.7 does NOT implement:

```text
S3
boto3
s3fs
remote DuckDB
LanceDB indexes
Parquet writers
normalization
chunking
embeddings
retrieval
generation
evaluation
cache eviction
file logging
deployment
```

The desired result is:

```text
one authoritative map of where things live
```

plus safe generated-artifact identity.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.7_storage_abstraction.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Storage API

Report the actual public API, for example:

```text
StoragePaths
get_storage()
```

plus the key helpers actually implemented.

## Frozen Inputs

Report canonical locations for:

```text
MS MARCO
EDGAR-CORPUS
XBRL DuckDB
raw XBRL
primary filings
```

using repository-relative descriptions.

## Generated Layout

Show the compact artifact layout.

## Versioning

Confirm how the abstraction distinguishes:

```text
normalized versions
chunk_config_hash
embedding model
eval version
```

## Safety

Report PASS/FAIL for:

```text
path traversal rejection
no import-time directory creation
explicit output creation
frozen data unchanged
```

## S3 Status

State explicitly:

```text
Local filesystem: implemented
S3 backend: NOT IMPLEMENTED
Future logical-key compatibility: yes/no
```

## Existing Ingestion

State whether `src/ingest/` was modified.

## Documentation

Confirm:

```text
project_plan/STORAGE.md
```

exists.

## Files Modified

List tracked/project files only.

## Git Safety

Confirm:

```text
data not staged
artifacts not staged
.env not staged
.tmp not staged
no large generated files staged
```

## Progress.md

Confirm the Phase 0.7 entry was appended.

## Next Task

If PASS:

```text
task_0.8_basic_automated_tests.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.8 work started.
```

Stop and wait for my approval.