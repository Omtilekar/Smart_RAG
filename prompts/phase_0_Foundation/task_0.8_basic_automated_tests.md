# Task 0.8 — Basic Automated Tests

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.8 — Basic Automated Tests
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
0.7 Storage Abstraction        — COMPLETE
0.8 Basic Automated Tests      — CURRENT
```

The project now has several foundation components worth protecting:

```text
src/config.py
src/logging_utils.py
src/storage.py
dependency installation
CUDA/PyTorch environment
DuckDB compatibility
LanceDB compatibility
sentence-transformers GPU inference
existing src/ingest modules
```

Task 0.8 turns the ad hoc verification performed in Tasks 0.1–0.7 into a **small, repeatable automated test suite**.

This is still Phase 0.

Do NOT begin:

```text
0.9 Developer Commands
0.10 Serving Feasibility Spike

Phase 1 normalization
Phase 1 chunking
Phase 1 embeddings pipeline
Phase 1 indexing
Phase 1 retrieval
```

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. establish the project's pytest structure,
2. test `src.config`,
3. test `src.logging_utils`,
4. test `src.storage`,
5. test critical dependency imports,
6. verify existing ingestion modules still import,
7. add a lightweight LanceDB smoke test,
8. add a read-only DuckDB/data smoke test,
9. add a CUDA smoke test,
10. add a cached-model embedding smoke test,
11. distinguish portable tests from machine-dependent smoke tests,
12. prevent network access and frozen-data mutation,
13. make the suite usable on a public clone,
14. document how tests are classified and run,
15. update `Progress.md`.

---

# TESTING PRINCIPLE

The test suite must distinguish:

```text
portable correctness tests
```

from:

```text
local capability / integration smoke tests
```

A developer cloning the public repository may not have:

```text
26 GB frozen datasets
RTX GPU
CUDA
cached Hugging Face model
```

That should not cause unrelated foundation tests to fail.

Therefore:

```text
missing optional local capability
    -> SKIP with a clear reason

capability exists but operation fails
    -> FAIL
```

Example:

```text
No NVIDIA GPU on a laptop
    -> GPU smoke test SKIP

CUDA is reported available but CUDA matmul crashes
    -> GPU smoke test FAIL
```

Do not use skips to conceal real failures on this development machine.

---

# STEP 1 — VERIFY THE ENVIRONMENT

Activate:

```text
.venv/
```

Verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pytest --version
```

Expected:

```text
Python 3.11.9
interpreter inside .venv
pytest 9.1.1
```

Run:

```bash
python -m pip check
```

before writing tests.

Expected:

```text
No broken requirements found.
```

If the environment is already broken, stop before blaming the tests.

---

# STEP 2 — INSPECT THE CURRENT FOUNDATION CODE

Read:

```text
src/config.py
src/logging_utils.py
src/storage.py
```

Also inspect:

```text
project_plan/CONFIGURATION.md
project_plan/LOGGING.md
project_plan/STORAGE.md
project_plan/PROJECT_EXECUTION.md
```

Tests must verify the code that actually exists.

Do not write tests against imagined APIs from earlier prompts if the implemented names differ.

---

# STEP 3 — INSPECT CURRENT TEST DIRECTORY

Task 0.3 created:

```text
tests/.gitkeep
```

Inspect `tests/`.

Expected:

```text
no real tests yet
```

Once real tests are added, `.gitkeep` is no longer necessary.

It may be removed.

Do not keep meaningless placeholder files merely for history.

Git history will show that the directory previously existed as a placeholder.

---

# STEP 4 — ESTABLISH TEST ORGANIZATION

Prefer a small structure such as:

```text
tests/
├── conftest.py
├── test_config.py
├── test_logging_utils.py
├── test_storage.py
├── test_dependencies.py
├── test_ingest_imports.py
├── test_lancedb_smoke.py
├── test_duckdb_smoke.py
├── test_gpu_smoke.py
└── test_embedding_smoke.py
```

Adapt if fewer files produce a cleaner suite.

Do not create dozens of files.

The goal is roughly:

```text
15–30 meaningful tests
```

not hundreds of trivial assertions.

---

# STEP 5 — DEFINE TEST MARKERS

Create a root:

```text
pytest.ini
```

or another minimal pytest configuration if the repository already uses one.

Register markers such as:

```text
local_data
gpu
model
```

Optionally:

```text
integration
```

only if it genuinely improves organization.

Example semantics:

```text
local_data
    requires this project's frozen local datasets

gpu
    requires CUDA-capable GPU

model
    requires an already-cached model or another explicitly available model
```

Do not create marker names that are unused.

---

# STEP 6 — NO NETWORK ACCESS IN TESTS

This is a hard requirement.

The automated test suite must not:

```text
download from SEC
download from Hugging Face
call OpenAI
call Anthropic
call external APIs
download model weights
download datasets
```

Tests should be deterministic and offline.

Do not run:

```text
src.ingest.fetch_*
```

download entry points.

Importing their modules is allowed if imports have no network side effects.

---

# STEP 7 — PROTECT FROZEN DATA

Tests must never mutate:

```text
data/
```

Specifically, do not:

```text
write to data/
create tables in data/xbrl.duckdb
delete data files
rewrite Parquet
modify primary HTML
touch XBRL ZIPs
```

All temporary writes must use:

```text
pytest tmp_path
```

or another pytest-managed temporary directory.

LanceDB tests must use `tmp_path`.

Storage directory-creation tests must use a temporary configuration/root where possible.

---

# STEP 8 — CONFIGURATION TESTS

Create tests for the actual `src.config` API.

At minimum verify:

### Defaults

```text
APP_ENV default
LOG_LEVEL default
DEVICE default
EMBEDDING_MODEL default
repository-root detection
STORAGE_ROOT default
```

Do not assert a personal absolute path.

Assert relationships instead, such as:

```python
settings.storage_root == settings.repo_root / "data"
```

or the actual implemented invariant.

### Environment overrides

Using `monkeypatch`, verify safe temporary overrides such as:

```text
APP_ENV=test
LOG_LEVEL=DEBUG
DEVICE=cpu
EMBEDDING_MODEL=test-model
STORAGE_ROOT=<tmp_path>
```

### Invalid values

Verify invalid:

```text
APP_ENV
LOG_LEVEL
DEVICE
```

raise the actual configuration exception.

### Cache behavior

If `get_settings()` is cached, verify:

```text
cached value remains until cache_clear()
cache_clear() causes new environment value to be loaded
```

### No directory side effects

Set:

```text
STORAGE_ROOT=<nonexistent tmp child>
```

Load configuration.

Verify the path still does not exist.

---

# STEP 9 — ENVIRONMENT ISOLATION IN CONFIG TESTS

Tests that modify environment variables must restore state automatically.

Use:

```text
pytest monkeypatch
```

Do not manually mutate permanent environment variables.

Be especially careful with:

```text
.env
LOG_LEVEL
STORAGE_ROOT
DEVICE
APP_ENV
```

Tests should pass regardless of the developer's current shell overrides unless the test explicitly controls them.

---

# STEP 10 — LOGGING TESTS

Automate the important Task 0.6 invariants.

Test at minimum:

### Level filtering

At INFO:

```text
DEBUG hidden
INFO visible
```

At DEBUG:

```text
DEBUG visible
```

Use pytest logging/capture facilities or controlled streams.

### Idempotent configuration

Call:

```text
configure_logging()
```

multiple times.

Verify:

```text
one project handler
one emitted message
```

### Reconfiguration

Configure:

```text
INFO
```

then:

```text
DEBUG
```

Verify the level changes without adding another project handler.

### Structured fields

Verify representative fields render correctly.

### Secret redaction

Use a fake value such as:

```text
TEST_SECRET_VALUE_DO_NOT_EMIT
```

under fields:

```text
api_key
token
password
authorization
```

Assert that the fake value does not occur in captured output.

Assert:

```text
[REDACTED]
```

or the implementation's actual replacement does occur.

### Exception traceback

Use a harmless intentional exception.

Verify:

```text
exception message
exception type
traceback
```

survive formatting.

---

# STEP 11 — LOGGING TEST ISOLATION

Logging tests can easily contaminate one another because Python logging is process-global.

Create fixtures/helpers that restore the relevant logging state after each test.

Do not leave:

```text
extra handlers
changed root level
changed project handler
```

for subsequent tests.

A test suite that passes only in one test order is unacceptable.

Verify:

```bash
python -m pytest tests/test_logging_utils.py
```

multiple times if useful.

---

# STEP 12 — STORAGE TESTS

Test the actual `src.storage` API.

At minimum verify:

### Determinism

Same input:

```text
same path
```

Different:

```text
chunk_config_hash
embedding_model
eval_version
```

produce different paths where expected.

### Safe component behavior

Verify examples such as:

```text
BAAI/bge-small-en-v1.5
model with spaces
ns:model
```

map deterministically.

### Traversal rejection

Verify dangerous values are rejected:

```text
../escape
..\escape
/path
C:\escape
.
..
empty string
```

Use platform-aware assertions where necessary.

### Explicit creation

Using a temporary storage object or safe disposable generated root:

```text
path absent
constructing path does not create
explicit ensure call creates
second ensure call remains successful
```

### Frozen root protection

Verify creation helpers reject attempts to create inside frozen data.

Do not mutate the actual frozen data directory to prove this.

Use the API's validation behavior and temporary roots.

---

# STEP 13 — STORAGE CONFIG OVERRIDE TEST

Using `monkeypatch` and `tmp_path`, override:

```text
STORAGE_ROOT
```

Clear config/storage caches where necessary.

Verify:

```text
data_root follows override
artifact/results roots behave according to implemented contract
no directory is created automatically
```

Restore cache/environment state after the test.

---

# STEP 14 — DEPENDENCY IMPORT TEST

Create a lightweight test confirming critical dependencies import.

At minimum, based on Task 0.4:

```text
requests
duckdb
pyarrow
bs4
lxml
sentence_transformers
lancedb
fastapi
pytest
```

Do not require:

```text
torch.cuda
```

in the generic dependency test.

A CPU-only public environment could still import torch successfully.

Also verify:

```text
import torch
```

succeeds.

This test checks installation consistency, not GPU capability.

---

# STEP 15 — EXISTING INGEST MODULE IMPORT TEST

Verify all implemented ingestion modules import without executing downloads.

At minimum:

```text
src.ingest.common
src.ingest.fetch_msmarco
src.ingest.fetch_edgar_corpus
src.ingest.fetch_xbrl
src.ingest.fetch_primary_docs
src.ingest.validate
src.ingest.audit_data
```

Do not call their `main()` functions.

Do not perform network requests.

The purpose is to catch future dependency/import regressions.

---

# STEP 16 — LANCEDB SMOKE TEST

Create:

```text
tests/test_lancedb_smoke.py
```

or equivalent.

Use:

```text
tmp_path
```

only.

Perform a tiny operation such as:

```text
create database
create tiny table
insert 2–3 rows
read/search basic data
close/reopen if useful
```

Do not create:

```text
artifacts/indexes/
```

Do not use the real project index.

Do not build embeddings.

This test verifies:

```text
selected LanceDB version
+
selected PyArrow version
+
Python 3.11
```

work together.

---

# STEP 17 — DUCKDB LOCAL-DATA SMOKE TEST

Create a test marked:

```text
@pytest.mark.local_data
```

Use the storage abstraction to locate:

```text
data/xbrl.duckdb
```

Behavior:

If the local XBRL DB is absent:

```text
pytest.skip("local frozen XBRL database not available")
```

If it exists:

open it in a mode that prevents accidental mutation where supported.

Prefer an explicit read-only DuckDB connection.

Verify something tiny, such as:

```text
facts table exists
submissions table exists
```

Optionally verify the known frozen fact count:

```text
90,685,753
```

only if doing so is cheap enough and clearly useful.

Avoid scanning the entire table merely for ceremony.

Do not write anything.

---

# STEP 18 — LOCAL DATA PATH SMOKE TEST

Optionally combine with the DuckDB test or create a small local-data test verifying that, when this repository's frozen data exists:

```text
MS MARCO root exists
EDGAR-CORPUS root exists
raw XBRL root exists
primary filings root exists
XBRL DB exists
```

If none of the local data is present in a public clone:

skip.

Do not count millions of records.

---

# STEP 19 — CUDA SMOKE TEST

Create a test marked:

```text
@pytest.mark.gpu
```

Behavior:

```python
if not torch.cuda.is_available():
    pytest.skip(...)
```

If CUDA is available:

1. inspect device,
2. allocate small CUDA tensors,
3. execute real CUDA matrix multiplication,
4. synchronize,
5. verify result is finite.

Use modest shapes.

For example:

```text
256x256
or
512x512
```

Do not use the Task 0.2 2048x2048 size unless necessary.

This should be a quick smoke test.

---

# STEP 20 — GPU CAPABILITY SEMANTICS

Do not skip because the GPU is a different model than the development machine.

The portable test should mean:

```text
If CUDA is available, real CUDA execution works.
```

Do not assert every developer owns:

```text
RTX 5060
sm_120
```

However, on this development machine, record the observed GPU in the Task 0.8 verification/Progress entry.

If this machine reports CUDA available but the kernel fails:

```text
FAIL
```

not skip.

---

# STEP 21 — EMBEDDING MODEL SMOKE TEST

Create a test marked:

```text
@pytest.mark.model
@pytest.mark.gpu
```

or equivalent.

The goal is to verify the exact Phase 1 baseline model:

```text
BAAI/bge-small-en-v1.5
```

can still execute through sentence-transformers.

Hard requirement:

```text
THE TEST MUST NOT DOWNLOAD THE MODEL
```

Use an offline/local-only approach supported by the installed sentence-transformers / Hugging Face stack.

Inspect the actual installed API before choosing the implementation.

Possible approaches include:

```text
local_files_only=True
HF_HUB_OFFLINE=1
cached snapshot resolution
```

Use whichever is robust with the installed versions.

Do not assume an argument exists without checking.

---

# STEP 22 — MODEL TEST SKIP RULES

If the model is not already cached locally:

```text
SKIP
```

with an explicit message such as:

```text
BAAI/bge-small-en-v1.5 not available in local cache; network downloads are disabled in tests
```

If the model is cached but fails to load:

```text
FAIL
```

If CUDA is unavailable:

```text
SKIP
```

If CUDA is available and model is cached but inference fails:

```text
FAIL
```

This distinction matters.

---

# STEP 23 — EMBEDDING ASSERTIONS

Encode only a tiny sample such as:

```text
"The company reported revenue for fiscal 2024."
"Item 1A describes material risk factors."
```

Explicitly use CUDA.

Verify:

```text
2 embeddings produced
embedding dimension == 384
all values finite
model/inference device is CUDA
```

Do not benchmark throughput here.

Do not download anything.

---

# STEP 24 — TEST NETWORK INDEPENDENCE

Review every test.

There should be no direct calls to:

```text
requests.get
requests.Session.get
huggingface online download
SEC
OpenAI
Anthropic
```

If useful, use monkeypatching to make unexpected network requests fail during specific tests.

Do not build a complex global socket-blocking plugin.

No new dependency should be required just to prevent network use.

---

# STEP 25 — NO REAL API KEYS REQUIRED

Running:

```bash
python -m pytest
```

must not require:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
SEC_USER_AGENT
AWS credentials
```

No test should use a real credential.

---

# STEP 26 — NO ORDER DEPENDENCE

Tests must pass regardless of reasonable execution order.

Run:

```bash
python -m pytest
```

at least twice if practical.

Pay particular attention to:

```text
config cache
storage cache
environment monkeypatches
logging handlers
```

Restore/reset them correctly.

---

# STEP 27 — RUN PORTABLE TEST SUBSET

Run a subset excluding machine-specific capabilities.

For example, depending on the final marker names:

```bash
python -m pytest -m "not local_data and not gpu and not model"
```

Expected:

```text
PASS
```

This is the subset that should remain meaningful on a clean public clone after dependencies are installed.

Record:

```text
passed
failed
skipped
runtime
```

---

# STEP 28 — RUN FULL LOCAL SUITE

On this development machine run:

```bash
python -m pytest
```

Because this machine currently has:

```text
frozen local data
CUDA
RTX 5060
cached BGE model
```

the relevant smoke tests should execute, not skip, unless the actual environment has changed.

Record:

```text
passed
failed
skipped
runtime
```

Explain every skip.

A full result with unexplained skips is not sufficient.

---

# STEP 29 — REQUIRE ZERO FAILURES

Task 0.8 cannot PASS with failing tests.

For PASS:

```text
failed == 0
```

Warnings may exist, but inspect them.

Do not simply suppress warnings globally.

If a warning is known and harmless, document it.

If it indicates a deprecated API in code you just wrote, fix it.

---

# STEP 30 — KEEP THE SUITE FAST

This is the Phase 0 foundation suite.

Target roughly:

```text
portable suite: a few seconds
full local suite: preferably <30 seconds
```

Model startup may make the full suite somewhat slower.

Do not scan:

```text
90M XBRL rows
91K filings
8.8M MS MARCO passages
```

during ordinary tests.

Do not run the full data audit.

---

# STEP 31 — DO NOT CREATE PHASE 2 METRIC TESTS

Phase 2 will require deterministic unit tests for:

```text
recall@k
MRR
nDCG
citation metrics
answer exactness
truth-contract behavior
```

Do not implement those now.

Task 0.8 tests the Phase 0 foundation.

Do not start the evaluation system early.

---

# STEP 32 — DO NOT TEST NONEXISTENT FEATURES

Do not create tests for:

```text
normalizer
chunker
embedder pipeline
retriever
router
reranker
CRAG
FastAPI app
guardrails
```

because those features do not exist yet.

Tests should describe implemented behavior, not speculative APIs.

---

# STEP 33 — NO MOCK IMPLEMENTATIONS TO SATISFY TESTS

If a feature does not exist:

```text
do not create it just so a test can pass
```

Task 0.8 should only test existing Phase 0 foundation components and dependency/capability smoke behavior.

---

# STEP 34 — DOCUMENT THE TEST STRATEGY

Create:

```text
project_plan/TESTING.md
```

Keep it concise and educational.

Recommended contents:

```markdown
# Testing

## Test philosophy

Portable correctness tests vs local capability smoke tests.

## Test categories

### Portable
- config
- logging
- storage
- dependency imports
- ingest imports
- temporary LanceDB

### local_data
- frozen SEC/XBRL presence
- read-only DuckDB smoke

### gpu
- CUDA kernel smoke

### model
- cached bge-small GPU inference

## Offline policy

Tests never download datasets/models or call external APIs.

## Running tests

python -m pytest

python -m pytest -m "not local_data and not gpu and not model"

## Skip semantics

Missing optional machine capability -> skip.
Present capability that fails -> fail.

## Frozen-data policy

Tests never modify data/.

## Future expansion

Phase 1 adds component tests.
Phase 2 adds deterministic metric/truth-contract tests.
```

Use the actual marker names and commands implemented.

---

# STEP 35 — UPDATE REPOSITORY DOCUMENTATION

Review:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

Make a small update indicating:

```text
tests/ — now implemented Phase 0 foundation tests
```

Cross-link:

```text
TESTING.md
```

Do not duplicate the whole testing document.

If any existing documentation still says:

```text
tests/ is empty
```

update that current-state statement where appropriate.

Do not rewrite historical `Progress.md` entries that accurately described the past.

---

# STEP 36 — DO NOT MODIFY REQUIREMENTS UNLESS REQUIRED

`pytest==9.1.1` is already in:

```text
requirements-dev.txt
```

Expected dependency changes:

```text
none
```

Use pytest built-ins:

```text
tmp_path
monkeypatch
caplog
capsys
```

where suitable.

Do not add:

```text
pytest-cov
pytest-xdist
pytest-mock
requests-mock
responses
```

unless there is a demonstrated necessity.

If a new dependency seems required, stop and justify it first.

---

# STEP 37 — OPTIONAL COVERAGE IS NOT REQUIRED

Do not chase a coverage percentage.

Task 0.8 is about protecting important invariants.

A meaningful:

```text
20 tests
```

is better than:

```text
100 superficial tests
```

Do not add coverage tooling solely to produce a number.

---

# STEP 38 — INSPECT WARNINGS

Run:

```bash
python -m pytest
```

and inspect warnings.

Classify them:

```text
project-code warning
third-party warning
platform warning
```

Do not hide unexpected project warnings with blanket filters.

Known harmless external warnings may remain if clearly understood.

---

# STEP 39 — VERIFY FROZEN DATA DID NOT CHANGE

Before and after full local tests, record lightweight metadata for:

```text
data/xbrl.duckdb size
```

and perhaps another small stable filesystem indicator already used in Task 0.7.

Do not hash 26 GB.

Verify the suite did not mutate frozen data.

---

# STEP 40 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not actually stage anything.

Expected new trackable files may include:

```text
pytest.ini
tests/*.py
project_plan/TESTING.md
Progress.md
project_plan/REPOSITORY_STRUCTURE.md
```

Verify these remain ignored:

```text
.pytest_cache/
__pycache__/
.tmp/
data contents
artifacts/
.venv/
.env
model caches
```

No test-generated database or model file should be stageable.

---

# STEP 41 — CLEAN TEMPORARY TEST ARTIFACTS

Pytest's own temporary directories normally live outside the repository.

If any manual temporary artifact was created under:

```text
.tmp/
artifacts/
```

remove it when safe.

Do not delete the historical 2.6 GB `.tmp/` spill directory as part of this task.

That unrelated cleanup remains out of scope.

---

# STEP 42 — SECRET / PATH SCAN

Inspect all new/modified tracked files for:

```text
real API keys
tokens
passwords
credentials
real SEC email
personal absolute paths
```

Tests may contain fake secret markers, but they must be obviously fake and must never resemble live credentials.

Prefer generated strings inside the test rather than embedding realistic key formats.

---

# STEP 43 — UPDATE `Progress.md`

Preserve all existing history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.8 Basic Automated Tests
```

using the current local date.

Include:

## Objective

Explain that Tasks 0.1–0.7 previously relied mostly on manual verification and Task 0.8 converted critical foundation behavior into a repeatable pytest suite.

## Initial State

Record:

```text
pytest installed
tests/ existed only as placeholder
zero automated tests
foundation modules implemented
```

Use actual observed state.

## Test Strategy

Explain:

```text
portable tests
local_data tests
gpu tests
model tests
offline-only policy
```

## Test Inventory

Include a compact table like:

| Test area | Tests | Category |
|---|---:|---|
| Configuration | N | portable |
| Logging | N | portable |
| Storage | N | portable |
| Dependencies/imports | N | portable |
| LanceDB | N | portable |
| DuckDB/local data | N | local_data |
| CUDA | N | gpu |
| Embedding | N | gpu/model |

Use actual counts.

## Portable Test Result

Record:

```text
command
passed
failed
skipped
runtime
```

## Full Local Test Result

Record:

```text
command
passed
failed
skipped
runtime
```

Explain any skips.

## Machine Smoke Results

Record factual outcomes for:

```text
DuckDB read-only
LanceDB temp DB
CUDA kernel
bge-small offline/cached GPU inference
```

Do not repeat Task 0.2's throughput benchmark.

## Offline / Safety Verification

Record:

```text
no network downloads
no API credentials required
no frozen data mutation
temporary writes isolated
```

## Files Created / Modified

Likely:

```text
pytest.ini
tests/conftest.py
tests/test_*.py
project_plan/TESTING.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

List actual files.

## Result

Use exactly one:

```text
PASS — Phase 0 foundation test suite established with zero failures

WARN — portable suite passes but one optional local capability remains unverified

BLOCKED — foundation tests expose an unresolved failure
```

For this machine, because GPU/data/model are already present, unexplained skipped smoke tests should be investigated before using PASS.

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
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.8 is complete only if:

```text
[ ] pytest configuration exists
[ ] useful test markers registered

[ ] tests/.gitkeep removed if no longer needed

[ ] configuration defaults tested
[ ] configuration overrides tested
[ ] configuration validation tested
[ ] configuration caching tested
[ ] configuration no-directory-side-effect tested

[ ] logging level filtering tested
[ ] logging idempotency tested
[ ] logging reconfiguration tested
[ ] structured logging tested
[ ] secret redaction tested
[ ] exception traceback tested
[ ] logging test state isolated

[ ] storage deterministic paths tested
[ ] storage safe-component behavior tested
[ ] storage traversal protection tested
[ ] storage explicit creation tested
[ ] frozen-root creation protection tested
[ ] storage override behavior tested
[ ] storage tests do not modify real data

[ ] critical dependency imports tested
[ ] all implemented src.ingest modules import

[ ] LanceDB temporary smoke test passes

[ ] local XBRL DuckDB smoke test exists
[ ] XBRL DB test uses read-only access
[ ] missing local data causes a clear skip, not unrelated failure

[ ] CUDA smoke test exists
[ ] CUDA test executes real kernel when CUDA is available
[ ] missing CUDA causes skip
[ ] present-but-broken CUDA causes failure

[ ] bge-small embedding smoke test exists
[ ] model test cannot download from network
[ ] missing cache causes skip
[ ] cached model failure causes failure
[ ] GPU inference explicitly verified
[ ] embedding dimension validated

[ ] no tests call SEC/OpenAI/Anthropic/external APIs
[ ] no tests require real credentials
[ ] no tests mutate frozen data
[ ] all writes use temporary/generated locations

[ ] portable test subset passes
[ ] full local suite has zero failures
[ ] all skips explained
[ ] test suite runtime reasonable

[ ] no Phase 1 feature implemented
[ ] no Phase 2 metric tests implemented
[ ] no new testing dependency added without justification

[ ] project_plan/TESTING.md exists
[ ] repository documentation updated

[ ] Git dry-run safe
[ ] no test-generated binaries/data staged
[ ] Progress.md updated

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.9 work not started
```

---

# STOP CONDITIONS

Stop and report rather than weakening tests if:

```text
a portable foundation test fails

config/logging/storage behavior contradicts its documentation

CUDA is available but a CUDA kernel fails

the cached BGE model is present but GPU inference fails

DuckDB cannot open the existing XBRL database read-only

LanceDB cannot perform a tiny temporary operation

tests require network downloads to pass

tests mutate frozen data

test isolation is unreliable because global config/logging state leaks between tests
```

Do not solve failing tests by:

```text
marking them all skip
loosening assertions without evidence
disabling CUDA
falling back silently to CPU
downloading alternate models
modifying frozen datasets
```

Find the actual cause.

---

# IMPORTANT NON-GOALS

Task 0.8 does NOT:

```text
build CI/CD
build GitHub Actions
measure code coverage
add linting
add formatting
implement Phase 1 code
implement retrieval metrics
implement truth-contract tests
benchmark models
benchmark retrieval latency
build an index
download models
download datasets
```

Task 0.8 establishes:

```text
a trustworthy automated safety net for the Phase 0 foundation
```

nothing more.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.8_basic_automated_tests.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Test Inventory

Report:

```text
total tests
portable tests
local_data tests
gpu tests
model tests
```

Use actual collected counts.

## Portable Suite

Report:

```text
command
passed
failed
skipped
runtime
```

## Full Local Suite

Report:

```text
command
passed
failed
skipped
runtime
```

Explain every skip.

## Smoke Tests

Report PASS/FAIL/SKIP for:

```text
DuckDB read-only
LanceDB temporary DB
CUDA kernel
BAAI/bge-small-en-v1.5 cached/offline GPU inference
```

## Safety

Confirm:

```text
no network calls
no model downloads
no dataset downloads
no credentials required
no frozen data modified
```

## Test Files

List the created test/configuration files.

## Documentation

Confirm:

```text
project_plan/TESTING.md
```

exists.

## Git Safety

Confirm:

```text
.pytest_cache ignored
__pycache__ ignored
temporary databases not staged
data not staged
artifacts not staged
.env not staged
```

## Progress.md

Confirm that the Phase 0.8 entry was appended.

## Next Task

If PASS:

```text
task_0.9_developer_commands.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.9 work started.
```

Stop and wait for my approval.