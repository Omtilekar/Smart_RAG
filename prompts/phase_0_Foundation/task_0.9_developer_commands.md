# Task 0.9 — Developer Commands

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.9 — Developer Commands
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
0.8 Basic Automated Tests      — COMPLETE
0.9 Developer Commands         — CURRENT
```

Task 0.8 currently has:

```text
60 total tests
56 portable tests
60/60 passing locally
0 failures
0 skips
0 warnings
```

The current `PROJECT_EXECUTION.md` defines Task 0.9 as simple documented commands/scripts for:

```text
setup / environment check
tests
data path check
GPU check
```

This is the **final numbered Phase 0 subtask in the current execution plan**.

Do NOT invent a `task_0.10` during this task.

Do NOT begin Phase 1.

---

# OBJECTIVE

Create one small, cross-platform developer command interface so routine project checks no longer require remembering long commands.

The interface should cover:

```text
environment/setup health
tests
portable tests
data paths
GPU execution
local smoke tests
```

It should reuse the foundation already built rather than duplicate it.

The preferred implementation is:

```text
scripts/dev.py
```

using Python standard library only.

Preferred developer interface:

```bash
python scripts/dev.py doctor
python scripts/dev.py test
python scripts/dev.py test --portable
python scripts/dev.py data
python scripts/dev.py gpu
python scripts/dev.py smoke
```

Adapt names only if the actual repository gives a strong reason.

---

# DESIGN PRINCIPLE

Developer commands should be:

```text
thin wrappers around tested project behavior
```

not a second implementation of config, storage, testing, or GPU logic.

Use:

```text
src.config
src.storage
pytest
torch
```

where appropriate.

Do not create a new framework.

---

# STEP 1 — INSPECT CURRENT STATE

Before modifying anything, read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/ENVIRONMENT.md
project_plan/DEPENDENCIES.md
project_plan/CONFIGURATION.md
project_plan/STORAGE.md
project_plan/TESTING.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
scripts/
tests/
src/config.py
src/storage.py
requirements*.txt
pytest.ini
.python-version
```

Use actual implemented APIs.

Do not implement from old prompt examples if names differ.

---

# STEP 2 — VERIFY FOUNDATION FIRST

Activate `.venv`.

Run:

```bash
python --version
python -m pip check
python -m pytest
```

Task 0.9 should not start from a broken Task 0.8 state.

Expected baseline before changes:

```text
Python 3.11.9
pip check PASS
60 tests PASS
```

If the existing test suite fails before Task 0.9 changes:

stop and report the regression.

---

# STEP 3 — USE ONE CROSS-PLATFORM PYTHON ENTRY POINT

Prefer creating:

```text
scripts/dev.py
```

rather than separate:

```text
dev.ps1
dev.bat
Makefile
shell-only scripts
```

The public repository should have one interface usable on:

```text
Windows
Linux
macOS
```

through the project Python interpreter.

Do not introduce a CLI framework dependency.

Use:

```text
argparse
subprocess
pathlib
sys
importlib
```

or other standard-library modules.

---

# STEP 4 — MAKE REPOSITORY ROOT DETECTION PORTABLE

`scripts/dev.py` must not depend on the current working directory.

Resolve repository root from the script location.

Conceptually:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
```

When launching subprocesses, use:

```text
cwd=REPO_ROOT
```

where appropriate.

If importing `src` requires making the repository root importable, do so minimally and explicitly.

Do not hardcode a personal absolute path.

---

# STEP 5 — ALWAYS USE THE CURRENT PYTHON INTERPRETER

Subprocesses must use:

```python
sys.executable
```

not bare:

```text
python
python3
py
```

For example:

```python
[
    sys.executable,
    "-m",
    "pytest",
]
```

This ensures:

```text
scripts/dev.py
```

uses the same `.venv` from which it was invoked.

---

# STEP 6 — IMPLEMENT `doctor`

Command:

```bash
python scripts/dev.py doctor
```

Purpose:

```text
setup / environment check
```

It must be read-only and offline.

Check at minimum:

```text
Python version
virtual-environment status
expected .python-version relationship
core dependency imports
pip dependency health
src.config import/load
src.storage import/load
repository root detection
```

Reasonable core imports include the direct foundation dependencies already defined by the repository.

Do not manually maintain a second giant dependency manifest if `requirements.txt` already represents it.

---

# STEP 7 — DOCTOR VENV CHECK

Detect whether the command is running inside a virtual environment.

A typical check is based on:

```python
sys.prefix != sys.base_prefix
```

Also verify the interpreter is consistent with the repository's `.venv` convention where practical.

If the developer runs the command outside the project environment:

return non-zero and provide a short actionable message pointing to:

```text
project_plan/ENVIRONMENT.md
```

Do not create or activate a virtual environment automatically.

---

# STEP 8 — DOCTOR PYTHON VERSION

Read:

```text
.python-version
```

rather than duplicating the version in several places.

The project currently uses:

```text
3.11
```

Verify the running interpreter's major/minor matches.

Do not require the exact patch number unless the repository explicitly pins it.

For example:

```text
3.11.9
```

should satisfy:

```text
3.11
```

---

# STEP 9 — DOCTOR DEPENDENCY HEALTH

Run the equivalent of:

```bash
python -m pip check
```

using:

```python
sys.executable
```

Propagate failure correctly.

Also verify critical imports.

Do not:

```text
pip install
pip upgrade
repair packages
```

inside `doctor`.

`doctor` diagnoses.

It does not mutate the environment.

---

# STEP 10 — DOCTOR OPTIONAL CAPABILITIES

`doctor` may report whether:

```text
local frozen data appears present
CUDA appears available
```

but these should be informational.

A public clone without the 26 GB dataset or NVIDIA GPU should still be able to pass the **portable environment** portion of `doctor`.

Explicit commands:

```text
data
gpu
```

own strict capability checks.

Clearly distinguish output such as:

```text
Required foundation: PASS
Local data: AVAILABLE / NOT AVAILABLE
CUDA: AVAILABLE / NOT AVAILABLE
```

Do not turn optional hardware/data absence into a generic environment failure.

---

# STEP 11 — IMPLEMENT `test`

Command:

```bash
python scripts/dev.py test
```

It should delegate to:

```bash
python -m pytest
```

using `sys.executable`.

Do not reimplement pytest behavior.

Preserve pytest's exit code.

---

# STEP 12 — IMPLEMENT PORTABLE TEST MODE

Support:

```bash
python scripts/dev.py test --portable
```

which must run the exact portable subset established in Task 0.8:

```bash
python -m pytest -m "not local_data and not gpu and not model"
```

Do not duplicate marker definitions.

`pytest.ini` remains the source of truth for markers.

---

# STEP 13 — IMPLEMENT `data`

Command:

```bash
python scripts/dev.py data
```

Purpose:

```text
data path check
```

Use:

```text
src.storage
```

as the source of truth.

Do not independently hardcode:

```text
data/xbrl.duckdb
data/msmarco
...
```

if `StoragePaths` already exposes them.

Check the major frozen inputs:

```text
MS MARCO root
EDGAR-CORPUS root
raw XBRL root
primary filings root
XBRL DuckDB
```

For each print a concise status:

```text
PASS
MISSING
```

Use repository-relative paths in output where practical.

---

# STEP 14 — DATA COMMAND MUST BE LIGHTWEIGHT

Do NOT:

```text
count 90M facts
scan 8.8M passages
walk every filing
hash large files
run the data audit
```

This is a path/availability check.

A simple:

```text
is_file()
is_dir()
```

plus perhaps XBRL DB file size is enough.

If required frozen data is missing:

```text
data command exits non-zero
```

and clearly identifies what is missing.

Do not download it.

---

# STEP 15 — IMPLEMENT `gpu`

Command:

```bash
python scripts/dev.py gpu
```

Purpose:

```text
explicit GPU check
```

Use PyTorch.

Report:

```text
torch version
torch.version.cuda
CUDA available
GPU name
compute capability
```

If CUDA is available, perform one small real CUDA operation.

For example:

```text
256x256 or 512x512 matrix multiplication
```

Synchronize and verify finite output.

---

# STEP 16 — GPU FAILURE SEMANTICS

Because the developer explicitly invoked:

```text
gpu
```

missing CUDA is a failure for this command.

Therefore:

```text
CUDA unavailable
    -> non-zero exit

CUDA available but kernel fails
    -> non-zero exit

CUDA kernel succeeds
    -> zero exit
```

This differs intentionally from the portable test suite, where a machine without CUDA may legitimately skip GPU tests.

Do not silently fall back to CPU.

---

# STEP 17 — DO NOT LOAD THE EMBEDDING MODEL IN `gpu`

The `gpu` command checks GPU/PyTorch health.

Do not make every GPU check load:

```text
BAAI/bge-small-en-v1.5
```

That would make a simple hardware check unnecessarily slow.

The model-level smoke check already exists in pytest.

Use:

```text
smoke
```

for the broader local stack.

---

# STEP 18 — IMPLEMENT `smoke`

Command:

```bash
python scripts/dev.py smoke
```

This also closes the intent behind Phase 0.8's requested smoke-test command.

It should delegate to the existing marked tests rather than reimplementing them.

Use the marker expression matching the current suite, conceptually:

```bash
python -m pytest -m "local_data or gpu or model"
```

Verify the expression selects the intended local-capability tests.

Current Task 0.8 smoke areas are:

```text
DuckDB/local data
CUDA
BGE model
```

LanceDB is currently portable and already exercised in both the portable/full suites.

Do not invent a second smoke-test implementation.

---

# STEP 19 — PRESERVE PYTEST EXIT CODES

Commands wrapping pytest must return meaningful exit status.

Examples:

```text
pytest success -> command returns 0
pytest failure -> command returns non-zero
```

Do not catch a failed subprocess and then return success.

This is important for future CI or scripted use.

---

# STEP 20 — OUTPUT SHOULD BE CONCISE

Use clear terminal output.

For example:

```text
Environment
  Python............. PASS 3.11.9
  Virtual env........ PASS
  pip check.......... PASS
  config............. PASS
  storage............ PASS

Optional capabilities
  Local data......... AVAILABLE
  CUDA............... AVAILABLE
```

Exact presentation may differ.

Avoid decorative frameworks or giant banners.

No third-party rich-output package is needed.

---

# STEP 21 — SECRET SAFETY

Developer commands must never print:

```text
API keys
tokens
passwords
authorization headers
real credentials
.env contents
```

Do not dump the full environment.

Do not print `Settings.__dict__` indiscriminately.

Only print explicit safe fields.

---

# STEP 22 — NO NETWORK ACCESS

All Task 0.9 commands must work offline.

They must not:

```text
download models
download datasets
call SEC
call Hugging Face network endpoints
call OpenAI
call Anthropic
install packages
```

The `smoke` command inherits Task 0.8's offline model behavior.

---

# STEP 23 — NO DATA MUTATION

Commands must not mutate:

```text
data/
```

`data` is inspection only.

`gpu` operates in GPU memory.

`doctor` is read-only.

`test`/`smoke` retain the Task 0.8 temporary-write guarantees.

---

# STEP 24 — DO NOT CREATE A SETUP INSTALLER

Do not create a command that automatically:

```text
installs Python
creates system CUDA
installs GPU drivers
installs packages globally
rewrites .venv
```

Environment creation/install order is already documented in:

```text
project_plan/ENVIRONMENT.md
project_plan/DEPENDENCIES.md
```

Task 0.9 provides verification commands, not a bootstrap installer.

This avoids hiding the special CUDA PyTorch installation requirements.

---

# STEP 25 — HANDLE INTERRUPTS CLEANLY

If a subprocess such as pytest is interrupted with Ctrl+C:

propagate an appropriate non-zero exit code.

Do not swallow interrupts and print PASS.

---

# STEP 26 — KEEP `scripts/dev.py` SMALL

Do not turn the file into a generic task runner.

Do not add commands for:

```text
normalization
chunking
embedding corpus
index build
retrieval
generation
deployment
cleaning data
deleting artifacts
Git
```

Those do not exist yet or belong to later phases.

Task 0.9 only provides Phase 0 developer checks.

---

# STEP 27 — REMOVE `scripts/.gitkeep`

Task 0.3 created:

```text
scripts/.gitkeep
```

because the directory was empty.

Once:

```text
scripts/dev.py
```

exists, remove the placeholder.

Do not keep meaningless `.gitkeep` files in non-empty directories.

---

# STEP 28 — ADD SMALL AUTOMATED TESTS FOR THE COMMAND INTERFACE

Because Task 0.8 established the test suite, new foundation code added in 0.9 should receive targeted tests.

Create something like:

```text
tests/test_dev_commands.py
```

Keep this small.

Test at minimum:

### Help

Running:

```bash
python scripts/dev.py --help
```

returns zero and exposes the expected commands.

### Doctor

Within the project's valid `.venv`, `doctor` should complete successfully.

Do not require GPU or local data merely for `doctor`.

### Missing-data behavior

Where practical, run `data` in a subprocess with:

```text
STORAGE_ROOT=<empty tmp_path>
```

and verify it:

```text
returns non-zero
reports missing inputs clearly
does not crash
does not create data
```

Do not test `test` by launching pytest from inside pytest, which could recursively start the test suite.

Do not run `smoke` recursively from a test.

---

# STEP 29 — VERIFY FROM REPOSITORY ROOT

Run:

```bash
python scripts/dev.py --help
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py data
python scripts/dev.py gpu
python scripts/dev.py smoke
python scripts/dev.py test
```

On this development machine, expected capability state is:

```text
local data present
CUDA present
cached BGE model present
```

Therefore explicit local checks should execute successfully.

---

# STEP 30 — VERIFY FROM A DIFFERENT WORKING DIRECTORY

Because the command is intended as developer tooling, test at least one safe invocation from outside the repository working directory.

For example, invoke the script by path from a temporary or parent directory.

At minimum verify:

```text
--help
doctor
```

still resolve the repository correctly.

Do not encode the absolute test path into documentation.

---

# STEP 31 — VERIFY CURRENT TEST SUITE AFTER CHANGES

Run:

```bash
python -m pytest -m "not local_data and not gpu and not model"
python -m pytest
```

Expected:

```text
0 failures
```

The exact test count will likely exceed the Task 0.8 baseline because `test_dev_commands.py` is new.

Do not hardcode `60` as the new expected count.

---

# STEP 32 — VERIFY COMMAND RESULTS

Task 0.9 cannot PASS unless the following work on this development machine:

```text
doctor             PASS
test --portable    PASS
data               PASS
gpu                PASS
smoke              PASS
test                PASS
```

If any explicit command fails:

investigate rather than weakening its definition.

---

# STEP 33 — PHASE 0 EXIT GATE

The current execution plan ends Phase 0 after Task 0.9.

After developer commands pass, verify the official Phase 0 exit criteria.

Confirm:

```text
[ ] fresh terminal can activate project environment
[ ] core dependencies import
[ ] PyTorch sees GPU
[ ] real GPU computation succeeds
[ ] sentence-transformer embeds sample text
[ ] DuckDB opens local XBRL database
[ ] LanceDB creates/reads tiny test table
[ ] config/storage roots are portable
[ ] core smoke tests pass
```

Most of these already have automated evidence from Task 0.8.

Do not unnecessarily rerun expensive operations outside the established tests.

---

# STEP 34 — DO NOT START PHASE 1

Even if the Phase 0 exit gate passes, do NOT implement:

```text
1.1 development corpus selection
normalization
chunking
embedding pipeline
LanceDB project index
retrieval
generation
```

Task 0.9 stops at:

```text
PHASE 0 COMPLETE
```

and waits for approval.

---

# STEP 35 — DOCUMENT DEVELOPER COMMANDS

Create:

```text
project_plan/DEVELOPER_COMMANDS.md
```

Recommended content:

```markdown
# Developer Commands

## Overview

All routine foundation checks use:

python scripts/dev.py <command>

## Commands

| Command | Purpose |
|---|---|
| doctor | environment/setup health |
| test | full pytest suite |
| test --portable | public-clone portable suite |
| data | frozen data-path validation |
| gpu | PyTorch/CUDA kernel validation |
| smoke | local capability smoke tests |

## Typical workflow

After activating .venv:

python scripts/dev.py doctor
python scripts/dev.py test --portable

Before Phase 1 work on the primary machine:

python scripts/dev.py data
python scripts/dev.py gpu
python scripts/dev.py smoke

## Exit codes

0 = success
non-zero = failure

## Safety

Commands do not install packages, download data/models, require API keys,
or modify frozen data.

## Setup

See ENVIRONMENT.md and DEPENDENCIES.md.
```

Use actual final command behavior.

---

# STEP 36 — UPDATE EXISTING DOCUMENTATION

Review:

```text
project_plan/ENVIRONMENT.md
project_plan/TESTING.md
project_plan/REPOSITORY_STRUCTURE.md
```

Make small cross-link/status changes only.

Recommended:

`ENVIRONMENT.md`

```text
After activation:
python scripts/dev.py doctor
```

`TESTING.md`

document:

```text
python scripts/dev.py test
python scripts/dev.py test --portable
python scripts/dev.py smoke
```

while retaining the underlying raw pytest commands for transparency.

`REPOSITORY_STRUCTURE.md`

mark:

```text
scripts/dev.py — implemented Phase 0 developer command interface
```

Do not duplicate `DEVELOPER_COMMANDS.md` everywhere.

---

# STEP 37 — DO NOT ADD DEPENDENCIES

Expected requirement-file changes:

```text
none
```

Use standard library plus existing project dependencies.

Do not add:

```text
click
typer
rich
invoke
fabric
```

for a six-command foundation CLI.

If such a dependency appears necessary, stop and explain why first.

---

# STEP 38 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not actually stage anything.

Expected new/modified trackable files may include:

```text
scripts/dev.py
tests/test_dev_commands.py
project_plan/DEVELOPER_COMMANDS.md
project_plan/ENVIRONMENT.md
project_plan/TESTING.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

and removal of:

```text
scripts/.gitkeep
```

Verify no generated:

```text
data
artifacts
.tmp
.pytest_cache
__pycache__
.env
model weights
```

is stageable.

---

# STEP 39 — UPDATE `Progress.md`

Preserve all prior history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.9 Developer Commands
```

Use the current local date.

Include:

## Objective

Explain that the final Phase 0 subtask consolidated routine foundation checks behind one documented cross-platform developer interface.

## Initial State

Record:

```text
scripts/ contained only placeholder
foundation tests existed
checks required several raw commands
```

Use actual observed state.

## Developer Interface

Document the implemented commands:

```text
doctor
test
test --portable
data
gpu
smoke
```

Use actual names.

## Command Behavior

Briefly describe what each command verifies and whether it is strict or capability-optional.

Especially distinguish:

```text
doctor: GPU/data informational
data: missing data is failure
gpu: missing CUDA is failure
```

## Verification

Record PASS/FAIL and runtime where useful for:

```text
doctor
test --portable
data
gpu
smoke
test
```

## Automated Tests

Record:

```text
new total test count
portable result
full result
failures
skips
```

Explain skips if any.

## Safety

Record:

```text
no network access
no downloads
no frozen-data mutation
no credentials required
no package installation
```

## Phase 0 Exit Gate

Record PASS/FAIL for every official Phase 0 exit criterion.

## Files Created / Modified

List actual project files.

## Result

Use exactly one:

```text
PASS — developer commands established and Phase 0 exit gate passed

WARN — developer commands work but a non-blocking Phase 0 item remains

BLOCKED — developer commands or Phase 0 exit criteria remain unresolved
```

## Phase Status

If and only if every required Task 0.9 command and Phase 0 exit criterion passes:

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE

Phase 1 — Make It Work End to End — NEXT
```

Do NOT add a fictional Phase 0.10 if it is not present in the current `PROJECT_EXECUTION.md`.

---

# ACCEPTANCE CRITERIA

Task 0.9 is complete only if:

```text
[ ] scripts/dev.py exists
[ ] scripts/.gitkeep removed

[ ] command interface is cross-platform Python
[ ] no new CLI dependency added
[ ] repo root detection does not depend on current working directory
[ ] subprocesses use sys.executable

[ ] doctor command exists
[ ] doctor verifies Python version
[ ] doctor verifies venv
[ ] doctor verifies dependency health
[ ] doctor verifies config/storage imports
[ ] doctor does not require local data
[ ] doctor does not require GPU
[ ] doctor performs no installation

[ ] test command exists
[ ] test delegates to pytest
[ ] test preserves pytest exit status

[ ] test --portable exists
[ ] portable marker expression matches Task 0.8

[ ] data command exists
[ ] data uses src.storage
[ ] data checks canonical frozen paths
[ ] data does not scan large datasets
[ ] missing data produces non-zero exit
[ ] data never downloads or mutates data

[ ] gpu command exists
[ ] gpu reports PyTorch/CUDA/device
[ ] gpu executes a real CUDA kernel
[ ] gpu does not silently use CPU
[ ] missing/broken CUDA produces non-zero exit
[ ] gpu does not unnecessarily load BGE model

[ ] smoke command exists
[ ] smoke delegates to existing pytest markers
[ ] smoke remains offline
[ ] smoke preserves pytest exit status

[ ] command help is clear
[ ] commands print no secrets
[ ] commands work without network
[ ] commands do not install dependencies

[ ] targeted developer-command tests added
[ ] no recursive pytest test added
[ ] portable suite has zero failures
[ ] full suite has zero failures

[ ] project_plan/DEVELOPER_COMMANDS.md exists
[ ] ENVIRONMENT.md cross-linked
[ ] TESTING.md cross-linked
[ ] REPOSITORY_STRUCTURE.md updated

[ ] Git dry-run safe
[ ] Progress.md updated

[ ] official Phase 0 exit criteria verified
[ ] Phase 0 marked COMPLETE only if exit gate passes

[ ] no Phase 1 implementation started
[ ] no Git commit created
[ ] no Git push performed
```

---

# STOP CONDITIONS

Stop and report instead of forcing success if:

```text
doctor fails in the valid project .venv

data command cannot resolve paths through src.storage

GPU command sees CUDA but real kernel execution fails

developer commands require network access

developer commands mutate frozen data

portable tests regress

full tests regress

command exit codes hide failures

Phase 0 exit gate has any unresolved required item
```

Do not make a broken check pass by:

```text
ignoring its exit status
silently falling back to CPU
automatically downloading data
automatically downloading models
automatically installing dependencies
marking failures as warnings
```

---

# IMPORTANT NON-GOALS

Task 0.9 does NOT:

```text
implement Phase 1
build the 1,500-filing corpus
normalize filings
chunk documents
embed the corpus
build a LanceDB project index
implement retrieval
call an LLM
deploy anything
build CI/CD
add GitHub Actions
add Makefile complexity
install packages
download anything
```

The result should simply be:

```text
one memorable developer interface
+
a verified Phase 0 exit gate
```

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.9_developer_commands.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Developer Commands

List the actual commands and one-line purpose for each.

## Verification

Report:

```text
doctor              PASS/FAIL
test --portable     PASS/FAIL
data                PASS/FAIL
gpu                 PASS/FAIL
smoke               PASS/FAIL
test                 PASS/FAIL
```

## Test Suite

Report:

```text
total tests
portable passed/failed/skipped
full passed/failed/skipped
```

## Environment

Confirm:

```text
Python
virtual environment
pip check
```

## Data

Report PASS/FAIL for the canonical frozen input paths.

Do not print personal absolute paths.

## GPU

Report:

```text
PyTorch version
torch.version.cuda
GPU name
compute capability
real CUDA kernel PASS/FAIL
```

## Smoke

Report:

```text
DuckDB/local-data
CUDA
cached/offline BGE inference
```

## Phase 0 Exit Gate

Report each official criterion as PASS/FAIL.

Then state one of:

```text
PHASE 0 COMPLETE
```

or:

```text
PHASE 0 NOT COMPLETE
```

## Documentation

Confirm:

```text
project_plan/DEVELOPER_COMMANDS.md
```

and the relevant cross-links.

## Files Modified

List tracked/project files only.

## Git Safety

Confirm:

```text
data not staged
artifacts not staged
.env not staged
.tmp not staged
test caches not staged
no large generated files staged
```

## Progress.md

Confirm the Phase 0.9 entry was appended.

## Next Step

If Task 0.9 and the Phase 0 exit gate PASS, report:

```text
Phase 1 — Make It Work End to End
task_1.1_select_development_corpus.md — NEXT
```

Do not start it.

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 1 work started.
```

Stop and wait for my approval.