# Phase 0 Checkup

You are working inside my SEC RAG repository.

This is a **post-Phase-0 verification/audit task**.

Task name:

```text
Phase 0 Checkup
```

Task file:

```text
task_0.11_phase_0_checkup.md
```

This is NOT another implementation subtask.

Its purpose is to independently inspect everything completed during Phase 0 and answer:

> Is Phase 0 genuinely complete, reproducible, internally consistent, safe to commit, and ready for Phase 1?

Do not trust `Progress.md` merely because it says something passed.

Re-run important checks against the repository as it exists now.

Do not begin Phase 1.

---

# EXPECTED PHASE 0 SCOPE

The completed Phase 0 should contain:

```text
0.0  Git Safety Preflight
0.1  Python Environment
0.2  CUDA / GPU Validation
0.3  Repository Structure
0.4  Dependency Management
0.5  Configuration System
0.6  Logging
0.7  Storage Abstraction
0.8  Basic Automated Tests
0.9  Developer Commands
0.10 Serving Feasibility Spike
```

Task 0.10 must already have been completed before this checkup.

If `Progress.md` still reports:

```text
0.10 Serving Feasibility Spike — NOT STARTED
```

or any other Phase 0 task as incomplete:

STOP.

Report:

```text
BLOCKED — Phase 0 implementation is not yet complete enough for final checkup
```

Do not perform Phase 1 work.

---

# AUTHORITATIVE SOURCES

Read these first where present:

```text
project_plan/PROJECT_EXECUTION.md
DATA_READINESS_REPORT.md
Progress.md

project_plan/GIT_CONVENTIONS.md
project_plan/ENVIRONMENT.md
project_plan/DEPENDENCIES.md
project_plan/REPOSITORY_STRUCTURE.md
project_plan/CONFIGURATION.md
project_plan/LOGGING.md
project_plan/STORAGE.md
project_plan/TESTING.md
project_plan/DEVELOPER_COMMANDS.md
project_plan/SERVING_FEASIBILITY.md
```

Also inspect:

```text
.gitignore
.python-version
.env.example

requirements-gpu.txt
requirements.txt
requirements-dev.txt

src/
tests/
scripts/
configs/
results/
```

Use the actual repository and executable behavior as the source of truth.

Planning documents describe intent.

Working code and reproducible checks prove completion.

---

# PRECEDENCE

When documents disagree:

```text
actual verified repository behavior
    >
PROJECT_EXECUTION.md for current execution scope
    >
current specialized Phase 0 documentation
    >
historical Progress.md entries
    >
stale PROJECT_SPEC.md statements
```

Do NOT silently rewrite historical `Progress.md` entries.

Historical entries may accurately describe what was believed at that time.

Instead document current authoritative conclusions in the new checkup entry.

---

# PRIMARY OBJECTIVES

Complete only these goals:

1. inspect all Phase 0 implementation,
2. independently verify every Phase 0 task,
3. re-run the foundation test suite,
4. verify the development commands,
5. verify CUDA/GPU health,
6. verify frozen data accessibility without mutation,
7. verify configuration and storage boundaries,
8. verify dependency reproducibility evidence,
9. verify serving-spike evidence and decision,
10. inspect documentation consistency,
11. inspect Git safety and repository hygiene,
12. confirm no Phase 1 implementation has accidentally begun,
13. identify unresolved blockers/warnings,
14. determine whether the official Phase 0 exit gate passes,
15. append a Phase 0 Checkup entry to `Progress.md`.

---

# IMPORTANT MODE

This is primarily an:

```text
AUDIT + VERIFICATION
```

task.

Do not opportunistically redesign Phase 0.

Do not expand scope.

Do not perform general cleanup merely because you notice something untidy.

---

# ALLOWED MODIFICATIONS

Prefer modifying only:

```text
Progress.md
```

If a **small, unambiguous Phase 0 defect** prevents an otherwise-complete
checkup, you may fix it only when all of these are true:

```text
the intended behavior is already clearly documented
the fix is small
the fix does not alter architecture
the fix stays inside Phase 0
the fix can be fully tested immediately
```

Examples:

```text
broken documentation cross-link
incorrect stale current-status line
small test regression in Phase 0 helper
missing Git-ignore exception
minor dev-command bug
```

If a fix would require a design decision, new subsystem, substantial
dependency change, or Phase 1 code:

do NOT fix it.

Report it as a blocker or warning.

Record every modified file explicitly.

---

# DO NOT

Do NOT:

```text
start Phase 1
select the 1,500-filing development corpus
implement normalization
implement chunking
implement production embeddings
build the Phase 1 LanceDB index
implement retrieval
implement generation
create the smoke evaluation set
implement XBRL truth contract
implement router/reranker/CRAG
deploy anything
```

---

# STEP 1 — INSPECT REPOSITORY STATE

From repository root inspect:

```bash
git status --short
git branch --show-current
git remote -v
git log --oneline --decorate -10
git tag --list
git count-objects -vH
```

Do not assume Git state from historical entries.

Record actual current state.

Do not commit, push, tag, reset, checkout, merge, or rebase.

---

# STEP 2 — INSPECT THE FINAL REPOSITORY TREE

Generate a compact tree excluding:

```text
.git/
.venv/
data contents
.tmp/
artifacts/
model caches
__pycache__/
.pytest_cache/
```

Verify the expected foundation structure exists.

At minimum inspect:

```text
src/config.py
src/logging_utils.py
src/storage.py

tests/
scripts/dev.py

configs/
results/
infra/

project_plan/
```

Confirm the Phase 1 feature packages may exist structurally but remain
unimplemented unless Phase 0 explicitly owns something inside them.

---

# STEP 3 — VERIFY PHASE STATUS FROM IMPLEMENTATION

Create an internal table:

| Task | Claimed status | Independent evidence | Checkup status |
|---|---|---|---|
| 0.0 Git safety | ... | ... | PASS/WARN/FAIL |
| 0.1 Python | ... | ... | ... |
| 0.2 CUDA | ... | ... | ... |
| 0.3 Structure | ... | ... | ... |
| 0.4 Dependencies | ... | ... | ... |
| 0.5 Config | ... | ... | ... |
| 0.6 Logging | ... | ... | ... |
| 0.7 Storage | ... | ... | ... |
| 0.8 Tests | ... | ... | ... |
| 0.9 Dev commands | ... | ... | ... |
| 0.10 Serving spike | ... | ... | ... |

Do not mark a task PASS based solely on its `Progress.md` claim.

---

# STEP 4 — VERIFY PYTHON ENVIRONMENT

Activate:

```text
.venv/
```

Verify:

```bash
python --version
python -c "import sys; print(sys.executable)"
python -m pip --version
python -m pip check
```

Verify:

```text
Python major/minor matches .python-version
interpreter is inside .venv
pip belongs to .venv
pip check passes
```

Inspect:

```text
.venv/pyvenv.cfg
```

Confirm:

```text
include-system-site-packages = false
```

Do not rely on global Python.

---

# STEP 5 — VERIFY DECLARED DEPENDENCY CONTRACT

Inspect:

```text
requirements-gpu.txt
requirements.txt
requirements-dev.txt
project_plan/DEPENDENCIES.md
```

Check for contradictions.

Verify the installation order remains explicit.

Confirm the known GPU PyTorch build remains intentionally separated from
generic runtime requirements if that is still the implementation.

Run:

```bash
python -m pip check
```

and import key dependencies.

At minimum:

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

Use actual dependency list as authority.

---

# STEP 6 — CHECK REQUIREMENT DRIFT

Compare installed direct package versions against the declared pinned direct
dependencies.

Do not require every transitive package to be pinned.

Flag:

```text
declared direct package missing
installed direct version differs from pinned version
working CUDA torch differs from requirements-gpu.txt
```

as WARN or FAIL depending on reproducibility impact.

Do not automatically regenerate requirements with `pip freeze`.

---

# STEP 7 — RECHECK CUDA

Run:

```bash
python scripts/dev.py gpu
```

Also independently inspect enough information to verify:

```text
torch version
torch.version.cuda
torch.cuda.is_available()
GPU model
compute capability
```

The current development machine is expected to have a working NVIDIA GPU,
but use actual results.

Perform a real CUDA operation if `dev.py gpu` does not already prove one.

Do not merely check device visibility.

---

# STEP 8 — RECHECK BASELINE EMBEDDING

Use the existing automated smoke test rather than recreating a new benchmark.

Run the relevant model test or:

```bash
python scripts/dev.py smoke
```

Verify:

```text
BAAI/bge-small-en-v1.5
cached/offline load
CUDA execution
384-dimensional embeddings
finite output
```

if those remain the frozen Task 0.8 semantics.

No model download should occur.

---

# STEP 9 — VERIFY CONFIGURATION

Inspect:

```text
src/config.py
project_plan/CONFIGURATION.md
.env.example
.gitignore
```

Confirm:

```text
typed settings
portable repo-root detection
STORAGE_ROOT portable default
environment overrides
process env > .env > defaults
DEVICE validation
LOG_LEVEL validation
embedding baseline centralized
no credential values stored in settings
no import-time heavy side effects
```

Verify:

```bash
git check-ignore -v .env
git check-ignore -v .env.example
```

Expected:

```text
.env ignored
.env.example trackable
```

---

# STEP 10 — VERIFY CONFIG IMPORT SIDE EFFECTS

In a fresh process import:

```python
import src.config
```

Confirm it does not unexpectedly:

```text
initialize CUDA
load torch/model
open DuckDB
open LanceDB
create directories
call network
```

Do not over-measure startup time.

This is a correctness check.

---

# STEP 11 — VERIFY LOGGING

Inspect:

```text
src/logging_utils.py
project_plan/LOGGING.md
```

Confirm:

```text
stdlib logging
central LOG_LEVEL integration
UTC timestamps
module logger names
structured context
secret-field redaction
console/stderr only
idempotent configuration
```

Rely primarily on automated tests where available.

Run targeted logging tests if necessary.

Verify no unexpected:

```text
logs/
*.log
```

files are created by the new application logging system.

Historical Data Preparation logs are separate.

---

# STEP 12 — VERIFY STORAGE BOUNDARY

Inspect:

```text
src/storage.py
project_plan/STORAGE.md
```

Confirm:

```text
frozen data root is read-only by convention/API
generated artifacts use artifacts/
small public results use results/
directory creation explicit
path traversal rejected
model identifiers sanitized
config drives storage
no fake S3 implementation
```

Verify S3 documentation remains truthful:

```text
Local filesystem: implemented
S3 backend: NOT IMPLEMENTED
```

Do not accept speculative S3 classes as completion evidence.

---

# STEP 13 — VERIFY FROZEN DATA PATHS

Run:

```bash
python scripts/dev.py data
```

Confirm canonical inputs.

At minimum:

```text
MS MARCO
EDGAR-CORPUS
raw XBRL
primary filings
XBRL DuckDB
```

Do not run the full audit.

Do not scan millions of rows unnecessarily.

---

# STEP 14 — VERIFY FROZEN DATA DID NOT MUTATE

Capture lightweight stable metadata before/after this checkup.

At minimum:

```text
data/xbrl.duckdb size
raw XBRL ZIP count
primary filing count
```

Optionally use other already-established cheap invariants.

Do not hash the full 26 GB dataset.

The checkup must not modify frozen data.

---

# STEP 15 — VERIFY DUCKDB

Use the existing automated read-only test.

Confirm:

```text
XBRL DuckDB opens read-only
expected key tables exist
```

Use the frozen fact count if the existing test already verifies it cheaply.

Do not perform writes.

---

# STEP 16 — VERIFY LANCEDB

Use the existing temporary smoke test.

Confirm:

```text
temporary database creation
tiny table write/read
search/read behavior
```

All writes must remain temporary.

Do not use/build the real Phase 1 index.

---

# STEP 17 — RUN DEVELOPER DOCTOR

Run:

```bash
python scripts/dev.py doctor
```

Record:

```text
exit code
required foundation result
optional local-data status
optional CUDA status
```

A failure here is significant because this is the intended routine
developer health command.

---

# STEP 18 — RUN PORTABLE TEST SUITE

Run:

```bash
python scripts/dev.py test --portable
```

Record:

```text
passed
failed
skipped
runtime
```

There must be:

```text
0 failures
```

for Phase 0 PASS.

Do not hardcode historical test counts.

Use current collected tests.

---

# STEP 19 — RUN LOCAL SMOKE TESTS

Run:

```bash
python scripts/dev.py smoke
```

On the primary development machine, expected capabilities likely include:

```text
local_data
gpu
model
```

Use actual environment.

Explain every skip.

A capability present but broken must fail rather than skip.

---

# STEP 20 — RUN FULL TEST SUITE

Run:

```bash
python scripts/dev.py test
```

Record:

```text
passed
failed
skipped
warnings
runtime
```

Phase 0 cannot receive final PASS with unresolved failing foundation tests.

---

# STEP 21 — INSPECT TEST QUALITY

Do not assess only test count.

Inspect enough tests to verify they actually protect:

```text
configuration
logging
storage
dependencies
ingest imports
LanceDB
DuckDB
CUDA
embedding
developer commands
serving-spike helpers where applicable
```

Look for weak patterns such as:

```text
assert True
tests permanently skipped
tests that only import without asserting behavior where behavior matters
tests that mutate frozen data
tests that download resources
```

Do not rewrite a healthy suite for style reasons.

---

# STEP 22 — VERIFY OFFLINE TEST CONTRACT

Search tests for obvious network operations.

Tests must not unexpectedly:

```text
download from Hugging Face
call SEC
call OpenAI
call Anthropic
call external APIs
```

Confirm the cached-model test remains offline.

Do not require credentials.

---

# STEP 23 — VERIFY DEVELOPER COMMANDS

Inspect:

```text
scripts/dev.py
project_plan/DEVELOPER_COMMANDS.md
```

Verify the expected interface exists:

```text
doctor
test
test --portable
data
gpu
smoke
```

or the actual documented equivalent.

Verify:

```text
repository root detection portable
subprocesses use sys.executable
exit codes preserved
no installation
no downloads
no secret output
```

---

# STEP 24 — VERIFY FROM OUTSIDE REPO ROOT

From another working directory, invoke at least:

```text
scripts/dev.py --help
scripts/dev.py doctor
```

using the correct script path.

Confirm it does not depend on the current working directory.

Do not put personal absolute paths into documentation.

---

# STEP 25 — AUDIT SERVING FEASIBILITY SPIKE

This is one of the most important checks.

Read:

```text
project_plan/SERVING_FEASIBILITY.md
configs/serving_spike.json
results/phase_0_10_serving_spike.json
```

plus any small CSV/result artifacts actually produced.

Confirm Task 0.10 measured rather than estimated.

---

# STEP 26 — VERIFY SPIKE CONFIG PROVENANCE

Confirm the serving result records enough information to reproduce/interpret:

```text
representative corpus size
chunk size
embedding model
vector store
retrieval top-k
reranker
reranker runtime
quantization
query count
warm-up count
CPU/resource/thread configuration
spike_config_hash or equivalent
```

If critical benchmark configuration is missing:

flag it.

---

# STEP 27 — VERIFY SERVING RESULTS ARE REAL

Inspect the machine-readable result.

Confirm it contains actual numeric measurements for:

```text
warm p50
warm p95
component timings
cold/process-cold samples
memory/RSS
index/model footprint
```

where required by the current execution plan.

Do not accept:

```text
estimated 400 ms
expected ~1 second
probably under 500 ms
```

as measured evidence.

---

# STEP 28 — VERIFY WARM VS COLD DISTINCTION

Confirm:

```text
warm measurements exclude warm-up
cold measurements use fresh processes or the actual documented mechanism
```

Ensure local cold measurements are described honestly.

If they are local process-cold proxies:

documentation must not call them actual AWS Lambda cold starts.

---

# STEP 29 — VERIFY SERVING DECISION THRESHOLDS

Re-read the exact threshold table from:

```text
project_plan/PROJECT_EXECUTION.md
```

Compare measured results against the frozen thresholds.

Confirm thresholds were not silently changed after measurement.

Create a small internal table:

| Metric | Threshold | Measured | Interpretation |
|---|---:|---:|---|
| Warm p95 | ... | ... | ... |
| Cold proxy | ... | ... | ... |

Use actual plan fields.

---

# STEP 30 — VERIFY SERVING TARGET DECISION

The report must state one clear architecture direction, such as:

```text
Lambda preferred
Fargate preferred
conditional / optimization required
```

Confirm the decision follows from measured evidence.

Do not judge whether Lambda or Fargate is aesthetically preferable.

Judge whether the recorded reasoning matches the plan's thresholds.

---

# STEP 31 — VERIFY SPIKE LIMITATIONS

The serving report should explicitly acknowledge relevant limitations such as:

```text
representative ~100k corpus, not full corpus
provisional components
local process-cold != real Lambda cold start
no LLM generation latency
no trusted retrieval-quality conclusions yet
Phase 3 re-check required
```

Flag overclaiming.

---

# STEP 32 — VERIFY GENERATED SPIKE ARTIFACTS ARE IGNORED

Inspect:

```text
artifacts/serving_spike/
```

if present.

Verify large items such as:

```text
chunks
embeddings
LanceDB index
ONNX weights
benchmark caches
```

are ignored and not stageable.

Small:

```text
results/*.json
results/*.csv
configs/*.json
```

may remain trackable.

---

# STEP 33 — VERIFY PHASE 0 DID NOT IMPLEMENT PHASE 1

Search:

```text
src/normalize/
src/chunk/
src/embeddings/
src/index/
src/retrieval/
src/generation/
```

Distinguish:

```text
empty structural packages
```

from:

```text
actual Phase 1 implementation
```

Benchmark-local code inside:

```text
scripts/serving_spike.py
```

does not count as Phase 1 if clearly scoped as disposable feasibility code.

But reusable production pipeline implementations inside `src/` would mean
scope leaked.

Report any leakage.

Do not delete it automatically.

---

# STEP 34 — DOCUMENTATION CONSISTENCY AUDIT

Inspect current documentation for contradictions affecting Phase 0.

Pay special attention to statements such as:

```text
Phase 0 NOT STARTED
tests do not exist
src/config.py planned
src/storage.py planned
lancedb not installed
serving latency unmeasured
Task 0.10 not started
```

Historical `Progress.md` entries may contain these statements and should
remain unchanged.

Current-state planning/docs should not.

---

# STEP 35 — PROJECT_SPEC STALENESS

The pre-Phase-0 audit already identified:

```text
project_plan/PROJECT_SPEC.md
```

as stale relative to corrected data-readiness metrics.

Do NOT rewrite `PROJECT_SPEC.md` during this checkup unless the task has
explicit authorization elsewhere.

Instead determine:

```text
Does this staleness affect Phase 0 correctness?
```

Likely classification:

```text
documentation warning / pre-publication cleanup
```

rather than a Phase 0 engineering blocker, unless it conflicts with current
implementation in a way that would mislead Phase 1.

Record the finding accurately.

---

# STEP 36 — CHECK DOCUMENT NAVIGATION

Inspect:

```text
project_plan/README.md
```

Verify important Phase 0 documents are discoverable.

Do not require every specialized engineering document to appear in an old
seven-item reading order unless the current documentation intentionally
works that way.

Flag broken links/missing referenced files.

---

# STEP 37 — GITIGNORE AUDIT

Review:

```text
.gitignore
```

and verify representative paths with:

```bash
git check-ignore -v <path>
```

At minimum test:

```text
data/xbrl.duckdb
.tmp/
.venv/
.env
artifacts/
model cache/model weight example
```

and trackability of:

```text
.env.example
requirements.txt
src/config.py
src/storage.py
tests/
scripts/dev.py
configs/serving_spike.json
results/phase_0_10_serving_spike.json
```

Do not create fake huge files.

---

# STEP 38 — GIT DRY RUN

Run:

```bash
git add -n .
```

Do not stage.

Inspect all files that would be staged.

There must be no:

```text
frozen datasets
DuckDB databases
Parquet corpora
ZIP archives
LanceDB indexes
model weights
.venv contents
.tmp contents
.env
secret-bearing files
large benchmark artifacts
```

If any appear:

Phase 0 checkup cannot PASS until Git safety is restored.

---

# STEP 39 — LARGE FILE AUDIT

Inspect stageable files for suspicious size.

Flag any stageable file:

```text
>10 MB
```

for manual review unless it is clearly intentional and Git-appropriate.

Do not automatically remove files.

Record:

```text
largest stageable file
total approximate stageable size
```

---

# STEP 40 — SECRET SAFETY AUDIT

Search tracked/stageable source/docs/config files for patterns associated with:

```text
API keys
passwords
tokens
authorization headers
AWS credentials
private keys
real .env values
```

Do not print secret values.

Also check for:

```text
personal absolute filesystem paths
real SEC contact address
```

where inappropriate in a public repository.

Generic placeholders are acceptable.

---

# STEP 41 — CHECK GIT HISTORY POLICY

Read:

```text
project_plan/GIT_CONVENTIONS.md
```

Compare actual Git state to the documented policy.

Important:

Do not create commits during this checkup.

Only report whether current repository history is aligned or whether
uncommitted Phase 0 work remains.

If the repository still has:

```text
0 commits
```

after all Phase 0 implementation, call that out clearly because the project
conventions may expect per-subtask history.

Do not silently "fix" it with one giant commit.

That would erase the intended engineering history.

---

# STEP 42 — CHECK ROOT LOG FILE POLICY

Historical root:

```text
stage*.log
phase1_data_audit.log
```

may still be stageable.

Evaluate them against current `GIT_CONVENTIONS.md`.

Do not assume they should be committed just because Task 0.0 allowed them.

If Git conventions now say runtime logs should not be committed, flag this
before the first commit.

Do not delete them automatically.

---

# STEP 43 — CHECK ORPHANED `.tmp/`

Inspect the previously known:

```text
.tmp/
```

state.

Confirm it remains ignored.

Record current approximate size.

Do NOT delete the historical 2.6 GB spill files unless explicitly authorized.

Disk housekeeping is separate from Phase 0 correctness as long as:

```text
it is ignored
it does not affect tests/benchmarks
```

---

# STEP 44 — RECHECK SOURCE IMPORTS

Verify:

```text
src.config
src.logging_utils
src.storage
```

and all implemented:

```text
src.ingest.*
```

modules import.

Also verify structural future packages import if that remains part of the
repository contract.

Do not execute network-download entry points.

---

# STEP 45 — CHECK FOUNDATION IMPORT WEIGHT

Confirm importing:

```text
src.config
src.logging_utils
src.storage
```

does not unexpectedly load:

```text
torch
sentence_transformers
duckdb
lancedb
```

unless the actual implementation intentionally documents otherwise.

The foundation modules should remain lightweight.

---

# STEP 46 — CHECK PHASE 0 ARTIFACT PROVENANCE

Verify every important Phase 0 generated result has enough provenance.

Examples:

```text
CUDA environment -> ENVIRONMENT.md
dependency contract -> requirements*.txt + DEPENDENCIES.md
test strategy -> pytest.ini + TESTING.md
serving benchmark -> config + results + SERVING_FEASIBILITY.md
```

A benchmark result without its producing config is a warning/blocker
depending on reproducibility impact.

---

# STEP 47 — OFFICIAL PHASE 0 EXIT GATE

Re-read the Phase 0 exit criteria directly from:

```text
project_plan/PROJECT_EXECUTION.md
```

Copy each criterion exactly enough to identify it.

For every criterion assign:

```text
PASS
WARN
FAIL
```

with concrete evidence.

Do not use an old prompt's shortened checklist.

The current `PROJECT_EXECUTION.md` is authoritative.

---

# STEP 48 — DETERMINE FINAL STATUS

Use:

```text
PASS
```

only if:

```text
all Phase 0 implementation tasks are complete
all mandatory exit criteria pass
foundation tests have zero failures
serving feasibility is measured
serving target is recorded
Git safety is sound
no critical reproducibility blocker exists
no Phase 1 implementation has improperly started
```

Use:

```text
WARN
```

when Phase 0 is functionally complete but one or more genuinely
non-blocking issues remain.

Examples might include:

```text
stale PROJECT_SPEC wording
ignored .tmp disk waste
optional documentation polish
```

Use:

```text
BLOCKED
```

when any mandatory Phase 0 exit criterion remains unresolved.

---

# STEP 49 — DO NOT CONFUSE WARNINGS WITH BLOCKERS

Potential non-blocking items may include:

```text
PROJECT_SPEC historical/stale metrics
.tmp disk cleanup
missing public README polish
future S3 backend not implemented
actual cloud deployment not performed
```

Those should not fail Phase 0 unless `PROJECT_EXECUTION.md` explicitly makes
them Phase 0 requirements.

Conversely, do not downgrade actual blockers merely to obtain a clean phase
exit.

---

# STEP 50 — UPDATE `Progress.md`

Preserve all previous history exactly.

Append:

```markdown
## YYYY-MM-DD — Phase 0 Checkup
```

Use the current local date.

Do NOT name the heading:

```text
Phase 0.11
```

The human-facing audit is:

```text
Phase 0 Checkup
```

The file/prompt identifier may remain:

```text
task_0.11_phase_0_checkup.md
```

---

# REQUIRED PROGRESS ENTRY

Include these sections.

## Objective

Explain that this was an independent post-implementation verification of the
entire Phase 0 foundation before starting Phase 1.

## Repository State

Record:

```text
branch
commit count/history state
remote status
tag status
working-tree status
```

Do not expose irrelevant personal paths.

## Phase 0 Task Audit

Include:

| Task | Result | Evidence |
|---|---|---|
| 0.0 Git Safety | PASS/WARN/FAIL | ... |
| 0.1 Python Environment | ... | ... |
| 0.2 CUDA/GPU | ... | ... |
| 0.3 Repository Structure | ... | ... |
| 0.4 Dependencies | ... | ... |
| 0.5 Configuration | ... | ... |
| 0.6 Logging | ... | ... |
| 0.7 Storage | ... | ... |
| 0.8 Tests | ... | ... |
| 0.9 Developer Commands | ... | ... |
| 0.10 Serving Spike | ... | ... |

## Foundation Verification

Record actual results for:

```text
doctor
pip check
portable tests
smoke tests
full tests
data paths
GPU kernel
cached embedding inference
DuckDB
LanceDB
```

## Serving Check

Record:

```text
warm p50/p95
cold/process-cold result
memory
serving decision
decision threshold interpretation
```

Use the actual Task 0.10 result.

## Reproducibility

Record:

```text
Python version contract
requirements state
config provenance
serving benchmark provenance
```

## Git Safety

Record:

```text
dry-run staging result
largest stageable file
approximate total stageable size
ignored large/generated categories
secret scan result
```

## Scope Check

State:

```text
Phase 1 implementation detected: YES / NO
```

Explain any finding.

## Documentation Warnings

Record real current inconsistencies only.

Do not repeat every historical issue merely because it once existed.

## Official Exit Gate

List every current official Phase 0 exit criterion and its:

```text
PASS / WARN / FAIL
```

status.

## Remaining Issues

Separate:

```text
BLOCKERS
WARNINGS
DEFERRED / LATER-PHASE ITEMS
```

Do not mix them.

## Final Result

Use exactly one:

```text
PASS — Phase 0 independently verified and ready for Phase 1
```

or:

```text
WARN — Phase 0 complete with documented non-blocking issues
```

or:

```text
BLOCKED — Phase 0 checkup found unresolved mandatory issues
```

## Phase Status

If full PASS:

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
  0.10 Serving Feasibility Spike  — COMPLETE
  Phase 0 Checkup                 — PASS

Phase 1 — Make It Work End to End — READY
```

If WARN but mandatory exit criteria all pass:

```text
Phase 0 — COMPLETE WITH WARNINGS
Phase 1 — READY
```

If blocked:

```text
Phase 0 — NOT COMPLETE
Phase 1 — NOT READY
```

and identify the exact blockers.

---

# STEP 51 — DO NOT CHANGE STATUS TO PASS MERELY BECAUSE PROGRESS CLAIMS PASS

This checkup is supposed to be independent.

If implementation contradicts historical claims:

record the contradiction.

Examples:

```text
Progress says test suite passes but pytest fails
Progress says serving target selected but result file missing
Progress says .env ignored but git add dry-run stages it
Progress says data unchanged but benchmark wrote into data/
```

Actual current evidence wins.

---

# STEP 52 — FINAL RE-RUN AFTER ANY ALLOWED SMALL FIX

If you made an allowed small Phase 0 correction:

re-run all checks affected by that change.

At minimum after code/config/test changes:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Do not claim PASS on stale pre-fix results.

---

# STEP 53 — FINAL GIT SAFETY CHECK

After `Progress.md` is updated run again:

```bash
git status --short
git add -n .
git count-objects -vH
```

Confirm the checkup itself did not introduce unsafe files.

Do not actually stage.

---

# ACCEPTANCE CRITERIA

The Phase 0 Checkup is complete only if:

```text
[ ] current PROJECT_EXECUTION.md read
[ ] current official Phase 0 exit criteria read

[ ] every Phase 0 task 0.0–0.10 independently reviewed
[ ] no task accepted solely from Progress.md claims

[ ] .venv verified
[ ] Python contract verified
[ ] pip check passes
[ ] direct dependency drift checked

[ ] CUDA real kernel verified
[ ] cached/offline baseline embedding verified

[ ] configuration contract verified
[ ] .env ignored
[ ] .env.example trackable
[ ] config imports lightweight

[ ] logging contract verified
[ ] logging idempotency/redaction covered by passing tests

[ ] storage boundary verified
[ ] frozen vs generated separation verified
[ ] S3 status represented truthfully
[ ] path-safety tests pass

[ ] canonical data paths available on primary machine
[ ] frozen data unchanged

[ ] DuckDB read-only smoke passes
[ ] LanceDB temp smoke passes

[ ] doctor passes
[ ] portable tests have zero failures
[ ] smoke tests have zero failures for available capabilities
[ ] full tests have zero failures
[ ] test skips explained

[ ] developer commands verified
[ ] outside-working-directory behavior verified

[ ] serving spike config exists
[ ] serving spike result exists
[ ] serving spike report exists
[ ] serving latency is measured, not estimated
[ ] warm p95 verified
[ ] process-cold methodology verified
[ ] memory/footprint evidence verified
[ ] serving target decision recorded
[ ] decision matches frozen threshold logic
[ ] serving-spike limitations documented

[ ] no accidental Phase 1 implementation detected

[ ] documentation consistency reviewed
[ ] stale historical entries left intact
[ ] current contradictions identified

[ ] .gitignore verified
[ ] git dry run safe
[ ] no data staged
[ ] no model weights staged
[ ] no benchmark index staged
[ ] no .env staged
[ ] no .venv staged
[ ] no .tmp staged
[ ] stageable large files reviewed
[ ] secret scan clean

[ ] actual Git history compared with GIT_CONVENTIONS.md

[ ] every official Phase 0 exit criterion classified
[ ] blockers/warnings/deferred items separated

[ ] Progress.md appended
[ ] no Phase 1 work started
[ ] no Git commit created
[ ] no Git push performed
```

---

# STOP CONDITIONS

Stop and return `BLOCKED` rather than forcing Phase 0 closure if:

```text
Task 0.10 has not actually completed

mandatory Phase 0 exit criterion fails

portable tests fail

full foundation tests fail because of a Phase 0 regression

CUDA is available but the real GPU path is broken

frozen data was unexpectedly mutated

dependency contract cannot reproduce/describe the current working environment

serving latency remains estimated rather than measured

serving target has not been selected

serving result cannot be tied to its configuration

Git dry run includes frozen data/models/secrets/large generated artifacts

a serious credential leak exists

Phase 1 code was required to make Phase 0 pass
```

Do not change thresholds or weaken tests to get a PASS.

---

# IMPORTANT NON-GOALS

The Phase 0 Checkup does NOT:

```text
improve retrieval
change the serving architecture beyond recording the already-measured decision
run Phase 1
reconcile every historical document
clean all disk waste
build CI
create deployment infrastructure
create a public README
commit the repository
push to GitHub
tag the phase
```

Those are separate actions.

---

# FINAL RESPONSE TO ME

Return:

## Task

```text
task_0.11_phase_0_checkup.md
```

## Human Name

```text
Phase 0 Checkup
```

## Result

```text
PASS / WARN / BLOCKED
```

## Phase Audit

Return a compact table:

| Task | Result |
|---|---|
| 0.0 | PASS/WARN/FAIL |
| 0.1 | ... |
| 0.2 | ... |
| 0.3 | ... |
| 0.4 | ... |
| 0.5 | ... |
| 0.6 | ... |
| 0.7 | ... |
| 0.8 | ... |
| 0.9 | ... |
| 0.10 | ... |

## Verification

Report actual results for:

```text
doctor
pip check
portable tests
smoke tests
full tests
data paths
GPU
embedding
DuckDB
LanceDB
```

## Serving

Report:

```text
warm p50
warm p95
process-cold p50/p95
peak memory
serving target decision
threshold interpretation
```

## Git

Report:

```text
branch
commit count
remote
tags
dry-run stage count
approximate stage size
largest stageable file
unsafe files found: yes/no
```

## Documentation

List only current meaningful inconsistencies.

## Scope

Report:

```text
Phase 1 implementation detected: YES / NO
```

## Exit Gate

List every official Phase 0 exit criterion from the current
`PROJECT_EXECUTION.md` and give:

```text
PASS / WARN / FAIL
```

for each.

## Outstanding Items

Separate into:

```text
Blockers
Warnings
Deferred
```

## Progress.md

Confirm:

```text
## YYYY-MM-DD — Phase 0 Checkup
```

was appended without rewriting historical entries.

## Final Phase Decision

State exactly one:

```text
PHASE 0 VERIFIED — PHASE 1 READY
```

or:

```text
PHASE 0 VERIFIED WITH WARNINGS — PHASE 1 READY
```

or:

```text
PHASE 0 NOT VERIFIED — PHASE 1 NOT READY
```

## Next Task

Only if Phase 1 is ready, identify the **actual first Phase 1 task from the
current `PROJECT_EXECUTION.md`** using the project's filename convention.

Do not invent the number from memory.

Do not execute it.

Finally state:

```text
No Git commit created.
No Git push performed.
No Phase 1 work started.
```

Stop and wait for my approval.