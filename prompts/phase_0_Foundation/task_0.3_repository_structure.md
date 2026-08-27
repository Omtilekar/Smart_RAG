# Task 0.3 — Repository Structure

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.3 — Repository Structure
```

Previous Phase 0 status:

```text
0.0 Git Safety Preflight — COMPLETE
0.1 Python Environment   — COMPLETE
0.2 CUDA/GPU Validation  — COMPLETE
0.3 Repository Structure — CURRENT
```

The goal of this task is to establish the **final high-level repository skeleton** before implementation begins to spread across the project.

This task creates structure and documents responsibilities.

It does **not** implement RAG functionality.

---

# OBJECTIVE

Create a clean, understandable repository layout that supports:

```text
data ingestion
normalization
chunking
embeddings
indexing
retrieval
generation
evaluation
routing
reranking
CRAG
guardrails
API
CLI
configuration
tests
scripts
results
infrastructure
documentation
```

The repository should be understandable to:

1. us while developing the project,
2. another developer cloning it later,
3. someone using the GitHub repo to learn how to build a production-style RAG system.

---

# IMPORTANT PRINCIPLE

Do not confuse:

```text
directory exists
```

with:

```text
feature implemented
```

Creating:

```text
src/retrieval/
```

does NOT mean retrieval exists.

At the end of this task, most new packages should contain only:

```text
__init__.py
```

and no functional implementation.

Do not add fake implementations or large TODO skeleton classes simply to fill folders.

---

# STEP 1 — VERIFY CURRENT STATE

Before modifying anything, inspect the repository from root.

Identify the current locations of:

```text
src/
src/ingest/
project_plan/
prompts/
data/
Progress.md
.gitignore
.python-version
.venv/
```

Also determine whether any of the target Phase 0.3 directories already exist.

Do not blindly recreate existing directories.

Preserve existing ingestion code exactly.

---

# STEP 2 — VERIFY PROJECT ENVIRONMENT

Activate:

```text
.venv/
```

and verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
```

Expected project interpreter:

```text
Python 3.11.9
```

inside `.venv`.

No package installation should be required for this task.

---

# STEP 3 — READ CURRENT PLANNING DOCUMENTS

Read the current:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/GIT_CONVENTIONS.md
```

and any repository-structure instructions already present.

Use the actual repository as the source of truth where planning documents and filesystem differ.

Do not update architecture decisions during this task.

---

# STEP 4 — CREATE THE `src/` PACKAGE STRUCTURE

Preserve:

```text
src/ingest/
```

exactly as it currently exists.

Create the following Python packages if they do not already exist:

```text
src/
├── ingest/          # existing — data acquisition / validation
├── normalize/       # source documents -> normalized representation
├── chunk/           # normalized documents -> chunks
├── embeddings/      # embedding model wrappers / batch embedding
├── index/           # vector / sparse index construction
├── retrieval/       # retrieval execution / fusion
├── generation/      # LLM generation/provider interface
├── eval/            # benchmarks, truth contract, metrics
├── router/          # query classification / path selection
├── rerank/          # cross-encoder reranking
├── crag/            # retrieval confidence / corrective decisions
├── guards/          # input/context/output protections
├── api/             # FastAPI-facing layer
└── cli/             # command-line entry points
```

Each new Python package should contain:

```text
__init__.py
```

Do NOT create implementation modules yet.

Examples of things that must NOT be implemented here:

```text
chunker.py
embedder.py
retriever.py
router.py
reranker.py
truth_contract.py
app.py
```

Those belong to later tasks/phases.

---

# STEP 5 — DO NOT CREATE `config.py` OR `storage.py` YET

The execution plan eventually requires:

```text
src/config.py
src/storage.py
```

but these belong to later Phase 0 tasks.

Do NOT create placeholder versions in Task 0.3.

They should remain:

```text
PLANNED — not implemented
```

until their dedicated tasks.

This avoids creating empty files that later appear to be completed features.

---

# STEP 6 — CREATE TOP-LEVEL ENGINEERING DIRECTORIES

Create the following if absent:

```text
configs/
tests/
scripts/
results/
infra/
```

Their intended responsibilities are:

```text
configs/
    versioned experiment/system configuration

tests/
    automated unit/integration/smoke tests

scripts/
    developer/build/maintenance commands

results/
    small committed metrics and experiment summaries

infra/
    deployment/infrastructure definitions
```

Do not populate these with real functionality yet.

---

# STEP 7 — HANDLE EMPTY DIRECTORIES INTENTIONALLY

Git does not track empty directories.

For directories that should appear immediately in the public repository, create a minimal:

```text
.gitkeep
```

where appropriate.

Recommended candidates:

```text
configs/.gitkeep
tests/.gitkeep
scripts/.gitkeep
infra/.gitkeep
```

For:

```text
results/
```

first inspect the existing `.gitignore`.

Task 0.0 configured `results/` so small:

```text
*.csv
*.json
*.md
```

files remain commit-worthy.

If you decide to use:

```text
results/.gitkeep
```

make the smallest necessary `.gitignore` correction so that the placeholder is trackable.

Do not weaken the protection around large/generated result artifacts.

---

# STEP 8 — HANDLE `logs/` AND `artifacts/`

The conceptual architecture includes:

```text
logs/
artifacts/
```

but these are generated runtime directories and are intentionally Git-ignored.

You may create them locally if useful, but they do not need tracked placeholder files.

Do not change them into committed directories merely to make the GitHub tree look full.

Document them as runtime-generated locations.

---

# STEP 9 — PRESERVE `data/`

Do not modify the frozen datasets.

The existing arrangement should remain conceptually:

```text
data/
├── .gitkeep          # tracked
└── everything else  # ignored / local only
```

Do not:

```text
move data
rename data directories
repartition data
delete data
copy data
```

during this task.

Data layout changes belong to later pipeline work.

---

# STEP 10 — PRESERVE `project_plan/`

Do not reorganize the planning folder during this task.

Keep its existing documents in place.

The folder exists as the educational/design history of the project.

Do not move:

```text
PROJECT_EXECUTION.md
PROJECT_SPEC.md
GIT_CONVENTIONS.md
ENVIRONMENT.md
```

unless the filesystem already has a different authoritative arrangement that must be preserved.

---

# STEP 11 — PRESERVE `prompts/`

Keep the prompt/task history.

The project is intentionally preserving execution prompts as part of its educational value.

If the current structure contains a Phase 0 prompt folder, keep using it.

Do not rename older prompts unless necessary.

Future task prompts should follow the naming convention:

```text
task_<phase>.<subtask>_<descriptive_name>.md
```

For example:

```text
task_0.3_repository_structure.md
task_0.4_dependency_management.md
```

---

# STEP 12 — CREATE A REPOSITORY STRUCTURE DOCUMENT

Create:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

This should be concise and educational.

It should explain:

```text
what each top-level directory is for
what each src/ package will eventually contain
which directories contain source-of-truth code
which directories contain generated artifacts
which directories are intentionally Git-ignored
```

Use a tree similar to:

```text
SEC-RAG/
├── src/
│   ├── ingest/
│   ├── normalize/
│   ├── chunk/
│   ├── embeddings/
│   ├── index/
│   ├── retrieval/
│   ├── generation/
│   ├── eval/
│   ├── router/
│   ├── rerank/
│   ├── crag/
│   ├── guards/
│   ├── api/
│   └── cli/
│
├── configs/
├── tests/
├── scripts/
├── results/
├── infra/
├── prompts/
├── project_plan/
├── data/
├── artifacts/      # generated / ignored
├── logs/           # generated / ignored
│
├── Progress.md
├── .python-version
└── .gitignore
```

Adapt it to what actually exists.

Do not claim future files are already implemented.

Use wording such as:

```text
planned responsibility
```

for packages that currently contain only `__init__.py`.

---

# STEP 13 — DISTINGUISH TRACKED VS GENERATED CONTENT

In `REPOSITORY_STRUCTURE.md`, explicitly distinguish:

## Tracked

Examples:

```text
src/
configs/
tests/
scripts/
project_plan/
prompts/
small results/*.json
small results/*.csv
Progress.md
```

## Local/generated and ignored

Examples:

```text
data contents
.venv/
artifacts/
logs/
.tmp/
model caches
DuckDB
Parquet
Lance indexes
model weights
```

This is important for people cloning the public repository.

---

# STEP 14 — DO NOT CREATE A ROOT README YET

If a root:

```text
README.md
```

does not exist, do not create one as part of Task 0.3.

Final public-facing README work is separate.

The structure documentation in:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

is sufficient for this task.

---

# STEP 15 — DO NOT IMPLEMENT TESTS YET

Create:

```text
tests/
```

but do not write actual test cases.

Task:

```text
0.8 Basic Automated Tests
```

owns test implementation.

A placeholder only is appropriate here.

---

# STEP 16 — DO NOT INSTALL PACKAGES

Do not install:

```text
duckdb
lancedb
fastapi
pytest
pydantic
python-dotenv
docling
```

or anything else during Task 0.3.

Dependency management is:

```text
task_0.4_dependency_management.md
```

The packages installed during Task 0.2 remain as-is.

---

# STEP 17 — VALIDATE PYTHON PACKAGE IMPORTS

With `.venv` active, verify each new Python package can be imported.

Conceptually test:

```python
import src
import src.ingest
import src.normalize
import src.chunk
import src.embeddings
import src.index
import src.retrieval
import src.generation
import src.eval
import src.router
import src.rerank
import src.crag
import src.guards
import src.api
import src.cli
```

This should not require application dependencies because the new packages should be empty.

If imports fail because of package structure, fix the structure.

Do not add functional code merely to make imports pass.

---

# STEP 18 — VERIFY NO EXISTING CODE WAS BROKEN

Perform lightweight checks on existing ingestion modules.

At minimum confirm Python can resolve modules such as:

```text
src.ingest.common
src.ingest.fetch_msmarco
src.ingest.fetch_edgar_corpus
src.ingest.fetch_xbrl
src.ingest.fetch_primary_docs
src.ingest.validate
src.ingest.audit_data
```

Do not run expensive ingestion or audit jobs.

A syntax/import check is sufficient.

If existing modules import packages that have not yet been installed into the fresh `.venv`, do not automatically install them during this task.

Instead distinguish:

```text
package structure problem
```

from:

```text
dependency not yet installed because Task 0.4 has not happened
```

The latter is expected and should not cause Task 0.3 to fail.

---

# STEP 19 — INSPECT THE FINAL TREE

Generate a compact repository tree after the changes.

Exclude:

```text
.git/
.venv/
data contents
.tmp/
__pycache__/
model caches
```

The output should make the project's architecture understandable without flooding the terminal.

Use the appropriate command/tool for the actual OS.

---

# STEP 20 — GIT SAFETY VERIFICATION

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
new package __init__.py files are trackable
REPOSITORY_STRUCTURE.md is trackable
.gitkeep placeholders are trackable
data remains ignored
.venv remains ignored
.tmp remains ignored
model cache remains ignored
```

The dry run must not contain large binaries or frozen datasets.

---

# STEP 21 — CHECK FOR ACCIDENTAL PLACEHOLDER BLOAT

Review all files created during Task 0.3.

The new source packages should not contain unnecessary:

```text
abstract base classes
interfaces
schemas
dataclasses
configuration code
TODO implementations
mock business logic
```

The task is successful if the structure is **small and obvious**.

Delete unnecessary scaffolding created during this task before finishing.

---

# STEP 22 — UPDATE `Progress.md`

Preserve all previous entries.

Append:

```markdown
## YYYY-MM-DD — Phase 0.3 Repository Structure
```

using the current local date.

Include:

## Objective

Explain that this task established the repository architecture before feature development begins.

## Initial State

Summarize what existed before the task.

For example:

```text
src/ contained only ingestion code
tests/ absent
configs/ absent
scripts/ absent
results/ absent
infra/ absent
```

Use actual observed state.

## Structure Created

Include the compact final tree.

## Package Responsibilities

Briefly describe the purpose of each new `src/` package.

Make clear that they are currently:

```text
STRUCTURE ONLY — functionality not implemented
```

## Top-Level Directories

Explain:

```text
configs
tests
scripts
results
infra
artifacts/logs behavior
```

## Documentation Added

Record:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

and its purpose.

## Verification

Record:

```text
new package imports: PASS/FAIL
existing src/ingest preserved: YES/NO
Git dry-run safety: PASS/FAIL
```

If ingestion imports could not run due to Task 0.4 dependencies not yet being installed, state that accurately rather than reporting a false failure.

## Files Created / Modified

List tracked/project files.

It is acceptable to summarize a group such as:

```text
src/{normalize,chunk,embeddings,...}/__init__.py
```

instead of writing fifteen repetitive lines.

## Result

Use exactly one:

```text
PASS — repository structure established

WARN — structure established with a non-blocking issue

BLOCKED — repository structure cannot be finalized safely
```

## Phase Status

If PASS:

```text
Data Preparation               — COMPLETE
Phase 0                        — IN PROGRESS
  0.0 Git Safety Preflight     — COMPLETE
  0.1 Python Environment       — COMPLETE
  0.2 CUDA/GPU Validation      — COMPLETE
  0.3 Repository Structure     — COMPLETE
  0.4 Dependency Management    — NEXT
```

---

# ACCEPTANCE CRITERIA

Task 0.3 is complete only if:

```text
[ ] existing src/ingest preserved
[ ] src/normalize package exists
[ ] src/chunk package exists
[ ] src/embeddings package exists
[ ] src/index package exists
[ ] src/retrieval package exists
[ ] src/generation package exists
[ ] src/eval package exists
[ ] src/router package exists
[ ] src/rerank package exists
[ ] src/crag package exists
[ ] src/guards package exists
[ ] src/api package exists
[ ] src/cli package exists

[ ] each new Python package has __init__.py

[ ] configs/ exists
[ ] tests/ exists
[ ] scripts/ exists
[ ] results/ exists
[ ] infra/ exists

[ ] empty tracked directories have appropriate placeholders
[ ] generated logs/artifacts remain ignored
[ ] data remains untouched and ignored
[ ] .venv remains ignored

[ ] project_plan/REPOSITORY_STRUCTURE.md exists
[ ] tracked-vs-generated distinction is documented

[ ] all new src packages import successfully
[ ] no functional RAG implementation was added
[ ] no project dependencies installed
[ ] src/config.py not implemented
[ ] src/storage.py not implemented
[ ] tests not implemented

[ ] Git dry-run contains no data/models/temp binaries
[ ] Progress.md updated

[ ] no Git commit created
[ ] no Git push performed
[ ] Phase 0.4 work not started
```

---

# STOP CONDITIONS

Stop and report instead of restructuring aggressively if:

```text
existing code already uses a materially different architecture
moving files would break ingestion code
directory naming conflicts with existing functional modules
Git ignore rules would expose frozen data or model artifacts
```

Do not rename working ingestion code merely to make the planned tree prettier.

Working code takes precedence over an idealized folder diagram.

---

# IMPORTANT NON-GOALS

This task does NOT:

```text
implement config
implement storage
install dependencies
write tests
build normalization
build chunking
build embeddings
build indexes
build retrieval
build generation
build evaluation
build router
build reranker
build CRAG
build guardrails
build FastAPI
deploy anything
```

The output of Task 0.3 should mostly be:

```text
directories
__init__.py
.gitkeep
one structure document
Progress.md update
```

Nothing more sophisticated is necessary.

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.3_repository_structure.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Structure

Show the compact final repository tree.

## Python Packages

Confirm all newly created `src/` packages import successfully.

## Existing Code

Confirm:

```text
src/ingest preserved
no existing acquisition/validation implementation moved
```

## Documentation

Confirm:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

was created.

## Git Safety

Confirm:

```text
data ignored
.venv ignored
.tmp ignored
model caches ignored
dry-run staging safe
```

## Files Modified

List or compactly summarize all tracked/project files created or modified.

## Progress.md

Confirm the Phase 0.3 entry was appended.

## Next Task

If PASS:

```text
task_0.4_dependency_management.md
```

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.4 work started.
```

Stop and wait for my approval.