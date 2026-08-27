# Task 0.4 — Dependency Management

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.4 — Dependency Management
```

Previous Phase 0 status:

```text
0.0 Git Safety Preflight — COMPLETE
0.1 Python Environment   — COMPLETE
0.2 CUDA/GPU Validation  — COMPLETE
0.3 Repository Structure — COMPLETE
0.4 Dependency Management — CURRENT
```

Current tested environment:

```text
Python:                 3.11.9
Virtual environment:    .venv/
GPU:                    NVIDIA GeForce RTX 5060 Laptop GPU
PyTorch:                2.13.0+cu130
PyTorch CUDA runtime:   13.0
sentence-transformers:  6.0.0
bge-small GPU smoke:    PASS
```

The objective of this task is to turn the currently working but partially ad hoc `.venv` into a **documented, reproducible dependency definition** suitable for:

1. this development machine,
2. a fresh clone,
3. another developer following the public repository,
4. later Phase 0 and Phase 1 implementation.

This task manages dependencies only.

Do NOT begin:

```text
0.5 Configuration System
0.6 Logging
0.7 Storage Abstraction
0.8 Automated Tests
0.9 Developer Commands
0.10 Serving Feasibility Spike
```

---

# CORE PRINCIPLE

Do not create a dependency list by blindly running:

```bash
pip freeze > requirements.txt
```

The project should distinguish:

```text
direct project dependencies
vs
transitive dependencies
```

We want a readable, intentional dependency definition.

Pin important direct dependencies to versions that were actually installed and tested.

Do not manually pin every transitive dependency unless there is a demonstrated reproducibility reason.

---

# TARGET FILES

The preferred dependency layout for this project is:

```text
requirements-gpu.txt
requirements.txt
requirements-dev.txt
```

with responsibilities:

```text
requirements-gpu.txt
    tested CUDA-enabled PyTorch installation only

requirements.txt
    direct runtime/project dependencies

requirements-dev.txt
    development/testing dependencies
```

Also create:

```text
project_plan/DEPENDENCIES.md
```

to explain the installation order and why GPU dependencies are separated.

Do not create a second competing dependency system unless there is a strong technical reason.

In particular, do not add:

```text
environment.yml
Pipfile
poetry.lock
requirements.in
```

just for tooling variety.

A simple pip-based setup is preferred for this project.

---

# STEP 1 — VERIFY CURRENT ENVIRONMENT

Activate:

```text
.venv/
```

and verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pip --version
```

Expected:

```text
Python 3.11.9
interpreter inside .venv
```

If the active environment is not `.venv`, stop.

Never install dependencies into global Python.

---

# STEP 2 — INSPECT CURRENT INSTALLED PACKAGES

Run:

```bash
python -m pip list
python -m pip check
```

Record the current important versions.

Do not paste the entire package list into `Progress.md`.

Pay particular attention to:

```text
torch
sentence-transformers
transformers
huggingface-hub
tokenizers
numpy
```

already installed during Task 0.2.

Verify:

```bash
python -m pip check
```

passes before adding anything else.

If it already reports conflicts, investigate before continuing.

---

# STEP 3 — INVENTORY ACTUAL SOURCE IMPORTS

Inspect the current Python source tree recursively.

Determine which third-party packages are actually imported by:

```text
src/ingest/
```

and any other implemented code.

Do not infer dependencies solely from planning documents.

Build a compact table internally such as:

| Package | Imported by current code? | Needed Phase 0/1? | Dependency group |
|---|---|---|---|
| requests | yes | yes | runtime |
| duckdb | yes | yes | runtime |
| pyarrow | ... | ... | runtime |
| pytest | no current code | Phase 0.8 | dev |
| ... | ... | ... | ... |

This inventory should drive the dependency definition.

---

# STEP 4 — READ THE EXECUTION PLAN

Read:

```text
project_plan/PROJECT_EXECUTION.md
```

Identify dependencies explicitly required for the remainder of Phase 0 and the Phase 1 vertical slice.

At minimum consider the needs for:

```text
SEC ingestion utilities
DuckDB
Parquet / PyArrow
sentence-transformers
PyTorch
LanceDB
FastAPI
testing
environment/configuration
HTTP
HTML parsing
```

Do not include Phase 5 research dependencies merely because they may eventually be useful.

Examples of packages that should generally be deferred until their feature is actually scheduled:

```text
Docling
ColBERT stacks
graph libraries
large table-RAG frameworks
experimental rerank packages
```

unless the execution plan explicitly requires them earlier.

---

# STEP 5 — CLASSIFY DEPENDENCIES

Classify direct dependencies into:

## GPU

Packages with special installation behavior.

For this project the known one is:

```text
torch
```

## Runtime

Packages required to run implemented or near-term project code.

Likely categories include:

```text
database
Parquet/dataframe
HTTP
HTML/XML parsing
embedding/model interface
vector database
API serving
```

Use actual package names based on the code and execution plan.

## Development

Packages required only for:

```text
testing
linting/formatting, if actually adopted
development tooling
```

Do not adopt a formatter/linter merely because this task exists.

If no formatter/linter has been selected by the project, do not introduce one now.

---

# STEP 6 — HANDLE PYTORCH SEPARATELY

Task 0.2 established a working GPU stack:

```text
torch==2.13.0+cu130
```

installed from the official PyTorch CUDA 13.0 wheel index.

Preserve that known-working configuration.

Create:

```text
requirements-gpu.txt
```

containing the GPU-specific dependency and enough information to reproduce its official install source.

Prefer a form that makes the special index explicit and understandable.

For example, conceptually:

```text
--index-url https://download.pytorch.org/whl/cu130

torch==2.13.0+cu130
```

Verify the exact syntax works with pip before finalizing it.

Do NOT:

```text
silently replace the tested cu130 build
switch back to CPU torch
switch to a nightly build
install the full CUDA Toolkit
```

during this task.

---

# STEP 7 — DO NOT LET GENERIC INSTALLS REPLACE CUDA TORCH

This is important.

Packages such as:

```text
sentence-transformers
transformers
```

may declare PyTorch dependencies.

The installation procedure for a fresh clone must not accidentally replace:

```text
torch==2.13.0+cu130
```

with an unintended PyPI/CPU/default build.

The documented installation order should therefore be conceptually:

```text
1. install requirements-gpu.txt
2. install requirements.txt
3. install requirements-dev.txt
```

Verify that this order leaves the tested CUDA-enabled torch version intact.

After runtime dependency installation, explicitly check:

```python
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
```

Expected:

```text
torch == 2.13.0+cu130
torch.version.cuda == 13.0
CUDA available == True
```

If another dependency causes torch to be replaced or downgraded, treat that as a dependency conflict and resolve it before continuing.

---

# STEP 8 — CREATE `requirements.txt`

Create the direct runtime dependency file.

Do not blindly copy every package shown by `pip freeze`.

Include direct dependencies needed by current code and the accepted Phase 0/1 architecture.

Likely candidates should be verified rather than assumed.

Potential categories include:

```text
requests
duckdb
pyarrow
pandas
beautifulsoup4
lxml
sentence-transformers
lancedb
fastapi
uvicorn
```

and environment/config dependencies only if the current execution plan clearly commits to them.

Important:

```text
torch should NOT be duplicated here
```

if it is owned by:

```text
requirements-gpu.txt
```

Pin each direct dependency to the version that successfully resolves and works inside Python 3.11.9.

Prefer:

```text
package==X.Y.Z
```

for direct dependencies at this stage.

Do not pin platform-specific transitive packages manually unless necessary.

---

# STEP 9 — CREATE `requirements-dev.txt`

Create a small development dependency file.

At minimum Phase 0.8 will require:

```text
pytest
```

Add other development-only dependencies only if they are genuinely part of the established project workflow.

Do not automatically add:

```text
black
ruff
mypy
pre-commit
coverage
tox
```

unless the project has explicitly chosen them.

This task is dependency management, not tooling expansion.

If useful, `requirements-dev.txt` may document that runtime dependencies must be installed first, but do not create confusing recursive requirements that interfere with the special GPU installation sequence.

Keep installation order obvious.

---

# STEP 10 — INSTALL MISSING RUNTIME DEPENDENCIES

Install the newly selected direct runtime dependencies into:

```text
.venv/
```

using the dependency files.

Do not install them ad hoc one-by-one and then forget to reflect them in the requirements files.

The file should be the source of truth.

After installation run:

```bash
python -m pip check
```

Expected:

```text
No broken requirements found.
```

If dependency resolution produces conflicts:

- identify the packages involved,
- resolve intentionally,
- document the reason for any changed pin.

Do not simply use:

```text
--force
--no-deps
```

to suppress resolver problems.

---

# STEP 11 — INSTALL DEVELOPMENT DEPENDENCIES

Install:

```text
requirements-dev.txt
```

inside `.venv`.

Run:

```bash
python -m pip check
```

again.

Do not write tests yet.

Task 0.8 owns test implementation.

---

# STEP 12 — VERIFY CURRENT INGESTION MODULE IMPORTS

Task 0.3 found that existing ingestion modules could not fully import inside the clean environment because packages such as:

```text
requests
duckdb
```

had intentionally not yet been installed.

Now verify that the current implemented ingestion modules import successfully.

Test at minimum:

```text
src.ingest.common
src.ingest.fetch_msmarco
src.ingest.fetch_edgar_corpus
src.ingest.fetch_xbrl
src.ingest.fetch_primary_docs
src.ingest.validate
src.ingest.audit_data
```

Do not run downloads.

Do not run the full audit.

This is an import/dependency check only.

If one module imports an undeclared third-party dependency:

1. identify it,
2. decide whether it is a direct project dependency,
3. add it to the appropriate dependency file if justified,
4. reinstall,
5. retest.

Do not hide missing dependencies.

---

# STEP 13 — VERIFY PHASE 0 CORE IMPORTS

Verify that at least the following can import successfully where selected:

```python
import torch
import sentence_transformers
import duckdb
import pyarrow
import requests
import lancedb
import fastapi
import pytest
```

Only test packages actually included by the final dependency plan.

Do not write application code.

---

# STEP 14 — RECHECK CUDA AFTER DEPENDENCY RESOLUTION

Dependency installation must not break the working GPU environment.

Run a lightweight check:

```python
import torch

assert torch.cuda.is_available()
print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.get_device_name(0))
```

Also perform one small CUDA tensor operation.

This is not a repeat of Task 0.2's complete benchmark.

It is a regression check.

Expected configuration remains:

```text
torch 2.13.0+cu130
CUDA runtime 13.0
RTX 5060 Laptop GPU
```

If it changed, investigate immediately.

---

# STEP 15 — VERIFY `sentence-transformers` STILL USES CUDA

Do not redownload the model unnecessarily if it already exists in the Hugging Face cache.

Load:

```text
BAAI/bge-small-en-v1.5
```

and perform a tiny one- or two-text encoding with:

```text
device="cuda"
```

Confirm execution still succeeds.

No throughput benchmark is needed.

This is only a dependency-regression check.

---

# STEP 16 — VERIFY LANCEDB BASIC IMPORT/INITIALIZATION

Task 0.2 did not install LanceDB.

After installing the chosen version, perform a minimal dependency-level smoke test.

For example:

```text
import lancedb
```

and, if inexpensive, create/open a tiny temporary database under:

```text
.tmp/
```

Do not create the project's real index.

Do not add embeddings.

Do not implement retrieval.

Delete or leave the tiny temp DB inside `.tmp/`, which is ignored.

The goal is only to prove:

```text
LanceDB package works with selected Python/PyArrow versions
```

---

# STEP 17 — VERIFY DUCKDB CAN OPEN THE EXISTING DATABASE

Perform a read-only or non-mutating connectivity check against:

```text
data/xbrl.duckdb
```

For example:

```text
open connection
list tables
close connection
```

Do not modify the database.

Do not run expensive audit queries.

The goal is to prove the selected DuckDB package can read the project's existing database.

---

# STEP 18 — CHECK DEPENDENCY HEALTH

Run:

```bash
python -m pip check
```

This must pass.

Also inspect direct/top-level packages where practical.

Useful commands may include:

```bash
python -m pip list --not-required
```

Use this only diagnostically.

Do not assume everything reported as top-level belongs in `requirements.txt`; bootstrap packages such as pip/setuptools/wheel are not runtime project dependencies.

---

# STEP 19 — TEST A FRESH ENVIRONMENT INSTALL

This is the strongest reproducibility check in Task 0.4.

Do NOT destroy the working `.venv`.

Create a temporary validation environment under the already ignored:

```text
.tmp/
```

For example conceptually:

```text
.tmp/dependency_check_venv/
```

using Python 3.11.

Then reproduce the documented install sequence:

```text
1. requirements-gpu.txt
2. requirements.txt
3. requirements-dev.txt
```

Use normal pip caching where available; do not deliberately disable the cache and redownload multi-GB packages unnecessarily.

Inside the temporary environment verify at least:

```text
Python version
torch import
torch version
torch.version.cuda
torch.cuda.is_available()
sentence-transformers import
duckdb import
pyarrow import
lancedb import
fastapi import
pytest import
```

Run:

```bash
python -m pip check
```

Expected:

```text
PASS
```

If practical, run one tiny CUDA tensor operation in the temporary environment too.

This proves the requirements files can actually reconstruct the working environment rather than merely describing the already-mutated `.venv`.

After validation, the temporary environment may be removed.

If removal fails for a benign Windows file-lock reason, it remains under `.tmp/` and is safely ignored; document that instead of risking unrelated filesystem changes.

---

# STEP 20 — IF FRESH INSTALL IS TOO EXPENSIVE

Do not silently skip Step 19.

If reproducing the GPU environment would require an unreasonable second multi-gigabyte network download because pip has no cached wheel, first determine whether the required wheels are already cached.

If they are not cached and re-downloading is genuinely expensive, use the strongest available alternative:

```text
pip dependency resolution/dry-run
current .venv pip check
all direct imports
CUDA regression check
documented exact install source
```

Then record:

```text
Fresh-venv reconstruction: NOT FULLY VERIFIED
Reason: ...
```

and classify Task 0.4 as:

```text
WARN
```

rather than falsely claiming full reproducibility.

A complete successful fresh install earns PASS.

---

# STEP 21 — CREATE `project_plan/DEPENDENCIES.md`

Create a concise educational dependency document.

Recommended structure:

```markdown
# Dependency Management

## Python

Python 3.11

## Why dependencies are split

requirements-gpu.txt
requirements.txt
requirements-dev.txt

## Installation

### 1. Create / activate .venv

...

### 2. Install GPU runtime

python -m pip install -r requirements-gpu.txt

### 3. Install project dependencies

python -m pip install -r requirements.txt

### 4. Install development dependencies

python -m pip install -r requirements-dev.txt

## Verify

python -m pip check

python -c "import torch; ..."

## Why PyTorch is separate

Explain that the project validated a CUDA 13.0 PyTorch wheel on an RTX 5060
and wants to avoid a generic dependency install replacing it with an
unintended build.

## Dependency policy

- direct packages pinned
- transitive packages resolved by pip
- special GPU source explicit
- experimental/stretch dependencies added only when needed
```

Keep it understandable to someone building their own RAG.

---

# STEP 22 — UPDATE `project_plan/ENVIRONMENT.md`

Update the existing environment document only where necessary.

Add or refine the dependency installation commands so:

```text
ENVIRONMENT.md
```

and:

```text
DEPENDENCIES.md
```

do not contradict each other.

Avoid duplicating pages of package lists.

Suggested separation:

```text
ENVIRONMENT.md
    machine/Python/GPU setup and validation

DEPENDENCIES.md
    package management and install sequence
```

---

# STEP 23 — DO NOT CREATE CONFIGURATION CODE

Do not create:

```text
src/config.py
.env.example
.env
```

during this task.

Those belong to:

```text
task_0.5_configuration_system.md
```

Installing a configuration-related package, if clearly justified by the execution plan, does not mean configuration has been implemented.

---

# STEP 24 — DO NOT WRITE TESTS

Although:

```text
pytest
```

should now be available, do not create real tests.

`tests/` remains a placeholder until:

```text
task_0.8_basic_automated_tests.md
```

---

# STEP 25 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not actually stage anything.

Verify:

```text
requirements*.txt trackable
DEPENDENCIES.md trackable
ENVIRONMENT.md trackable
Progress.md trackable

.venv ignored
.tmp ignored
Hugging Face model cache ignored/outside repo
no wheel files tracked
no CUDA binaries tracked
no model weights tracked
no datasets tracked
```

If pip created unexpected files in the repository, clean or ignore them appropriately.

---

# STEP 26 — UPDATE `Progress.md`

Preserve all previous history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.4 Dependency Management
```

using the current local date.

Include:

## Objective

Explain that this task converted the working environment into a reproducible dependency specification.

## Initial State

Record:

```text
Python 3.11.9
working .venv
torch 2.13.0+cu130 already validated
sentence-transformers already validated
no requirements files
several ingestion dependencies absent
LanceDB absent
```

Use actual observed state.

## Dependency Strategy

Explain the three-file split:

```text
requirements-gpu.txt
requirements.txt
requirements-dev.txt
```

and why GPU PyTorch is separate.

## Direct Dependencies

Record a concise table of the final direct packages and versions.

Do not paste all transitive packages.

Suggested columns:

| Group | Package | Version | Why |
|---|---|---:|---|

## Installation Order

Record the tested order.

## Verification

Include:

```text
pip check
ingestion imports
core Phase 0 imports
CUDA regression
bge-small CUDA regression
LanceDB tiny smoke
DuckDB read-only open
fresh temporary environment reconstruction
```

Record PASS/FAIL for each.

## Fresh Environment Reproduction

State explicitly:

```text
PASS
```

only if the requirements files actually reconstructed a clean temporary environment successfully.

Otherwise state what was not verified.

## Files Created / Modified

Likely:

```text
requirements-gpu.txt
requirements.txt
requirements-dev.txt
project_plan/DEPENDENCIES.md
project_plan/ENVIRONMENT.md
Progress.md
```

List only files actually changed.

## Result

Use exactly one:

```text
PASS — dependency environment is reproducible from declared requirements

WARN — working dependency set declared but fresh reconstruction remains partially unverified

BLOCKED — dependency conflicts prevent a reliable environment
```

## Phase Status

If PASS:

```text
Data Preparation                 — COMPLETE
Phase 0                          — IN PROGRESS
  0.0 Git Safety Preflight       — COMPLETE
  0.1 Python Environment         — COMPLETE
  0.2 CUDA/GPU Validation        — COMPLETE
  0.3 Repository Structure       — COMPLETE
  0.4 Dependency Management      — COMPLETE
  0.5 Configuration System       — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.4 is complete only if:

```text
[ ] project .venv active
[ ] Python 3.11.9 retained

[ ] current source imports inventoried
[ ] Phase 0/1 direct dependency needs identified
[ ] dependencies classified into GPU/runtime/dev

[ ] requirements-gpu.txt exists
[ ] tested CUDA PyTorch version/source preserved
[ ] requirements.txt exists
[ ] requirements-dev.txt exists

[ ] direct dependencies intentionally pinned
[ ] full pip-freeze dump NOT used as requirements.txt

[ ] runtime requirements installed successfully
[ ] dev requirements installed successfully
[ ] pip check passes

[ ] existing ingestion modules import successfully
[ ] required Phase 0 package imports succeed
[ ] LanceDB imports/initializes successfully
[ ] existing XBRL DuckDB opens successfully

[ ] torch remains 2.13.0+cu130 unless a documented blocker forced a change
[ ] torch.version.cuda remains 13.0 unless a documented blocker forced a change
[ ] CUDA remains available
[ ] small CUDA operation succeeds
[ ] bge-small still encodes explicitly on CUDA

[ ] documented install order prevents accidental torch replacement

[ ] fresh temporary environment reconstruction attempted
[ ] fresh reconstruction passes for full PASS status
[ ] fresh environment pip check passes for full PASS status

[ ] project_plan/DEPENDENCIES.md exists
[ ] project_plan/ENVIRONMENT.md remains consistent

[ ] no configuration implementation added
[ ] no tests implemented
[ ] no retrieval/RAG code implemented

[ ] no model weights/data/wheels staged
[ ] Progress.md updated

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.5 work not started
```

---

# STOP CONDITIONS

Stop rather than forcing dependency resolution if:

```text
the requirements install replaces the working CUDA torch unexpectedly
PyTorch CUDA becomes unavailable
a package requires an incompatible Python version
LanceDB/PyArrow create an unresolved binary/version conflict
pip check reports unresolved requirements
current ingestion modules require mutually incompatible packages
fresh environment cannot reproduce the declared environment
```

If a conflict occurs:

1. preserve the exact resolver/import error,
2. identify the conflicting direct packages,
3. explain candidate resolutions,
4. choose the smallest compatible adjustment if unambiguous,
5. otherwise stop and report BLOCKED.

Do not use `--force` or random downgrades until something happens to import.

---

# IMPORTANT NON-GOALS

This task does NOT:

```text
implement configuration
create .env.example
implement logging
implement storage
write automated tests
build the chunker
build embeddings pipeline code
build LanceDB project indexes
implement retrieval
build FastAPI endpoints
configure deployment
install Docling
install graph tooling
install ColBERT
```

The main artifact of this task is:

```text
a reproducible dependency contract
```

not application functionality.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.4_dependency_management.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Dependency Files

Report:

```text
requirements-gpu.txt
requirements.txt
requirements-dev.txt
```

and their purpose.

## GPU Environment

Confirm:

```text
torch version
torch.version.cuda
CUDA available
GPU name
```

after all dependency installation.

## Core Dependency Verification

Report PASS/FAIL for:

```text
pip check
ingestion imports
DuckDB open
LanceDB smoke
sentence-transformers CUDA smoke
```

## Fresh Environment Reproduction

Report:

```text
PASS / NOT FULLY VERIFIED / FAIL
```

and why.

## Documentation

Confirm:

```text
project_plan/DEPENDENCIES.md
project_plan/ENVIRONMENT.md
```

status.

## Files Modified

List tracked/project files only.

## Git Safety

Confirm:

```text
.venv ignored
.tmp ignored
model cache not staged
no wheels/binaries/data staged
```

## Progress.md

Confirm the Phase 0.4 entry was appended.

## Next Task

If PASS:

```text
task_0.5_configuration_system.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.5 work started.
```

Stop and wait for my approval.