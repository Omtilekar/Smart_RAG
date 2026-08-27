You are working inside my **SEC RAG** repository.

We have completed data acquisition, validation, planning, and project-structure design. Before starting **Phase 0**, I want you to independently inspect the entire repository and create an accurate **current-state engineering snapshot** in:

```text
Progress.md
```

The purpose is to establish a trustworthy baseline of what exists **right now**, so future `Progress.md` updates can show the project evolving from this exact point.

This is an **inspection + documentation task only**.

Do NOT start Phase 0.

---

# PRIMARY OBJECTIVE

Inspect the repository as it actually exists on disk and answer:

> What has been completed, what files/artifacts exist, what has only been planned, what important decisions have already been made, what known issues have been discovered, and exactly where does implementation begin next?

Then update:

```text
Progress.md
```

with that information.

---

# IMPORTANT RULE

Do not treat planning documents as proof that something has been implemented.

For every important item distinguish between:

```text
IMPLEMENTED / VERIFIED
PLANNED
PARTIAL
NOT STARTED
```

For example:

If `PROJECT_EXECUTION.md` says:

```text
Create src/storage.py
```

but `src/storage.py` does not exist, report:

```text
PLANNED — not implemented
```

Do not report it as complete simply because it appears in the plan.

The repository filesystem and existing code are the source of truth for implementation state.

---

# 1 — INSPECT THE REPOSITORY

Start by understanding the complete repository structure.

Inspect recursively, but summarize intelligently.

Do not dump thousands of files.

Identify at least:

```text
root files
project_plan/
src/
tests/
configs/
scripts/
prompts/
results/
infra/
data/
logs/
artifacts/
```

if present.

Also identify:

- Python files
- Markdown documentation
- configuration files
- requirements/dependency files
- `.gitignore`
- `.env.example`
- notebooks
- tests
- generated reports
- logs
- derived artifacts
- unexpected files/directories

Produce a compact tree showing the meaningful repository structure.

Ignore noise such as:

```text
__pycache__
.venv
venv
.git internals
IDE caches
```

unless they reveal a configuration problem.

---

# 2 — READ THE IMPORTANT PROJECT DOCUMENTS

Find and read the project's important Markdown/documentation files.

Pay particular attention to files such as:

```text
PROJECT_SPEC.md
PROJECT_EXECUTION.md
DATA_READINESS_REPORT.md
REVIEW_RESOLUTIONS.md
GIT_CONVENTIONS.md
README.md
Progress.md
FAILURES.md
```

Some may now be inside:

```text
project_plan/
```

rather than repository root.

Use the actual repository locations.

Also inspect any other documentation that appears important.

---

# 3 — DETERMINE THE CURRENT PROJECT STATE

Build a status table using:

```text
COMPLETE
PARTIAL
NOT STARTED
STRETCH
```

The engineering roadmap should conceptually contain:

```text
Data Preparation
Phase 0 — Foundation
Phase 1 — Make It Work
Phase 2 — Make It Trustworthy
Phase 3 — Make It Good
Phase 4 — Make It Real
Phase 5 — Stretch
```

But use the current `PROJECT_EXECUTION.md` as the authoritative roadmap if wording differs.

For every phase determine whether there is actual implementation evidence in the repository.

Do not assume later phases are untouched without checking.

Example:

| Stage | Status | Evidence |
|---|---|---|
| Data Preparation | COMPLETE | acquisition scripts + readiness report + frozen metrics |
| Phase 0 | NOT STARTED | environment work not yet implemented |
| Phase 1 | NOT STARTED | no baseline retrieval pipeline |
| ... | ... | ... |

---

# 4 — SUMMARIZE COMPLETED DATA WORK

Read the current authoritative:

```text
DATA_READINESS_REPORT.md
```

and summarize the **final frozen dataset state**.

Do not use superseded historical metrics as headline numbers.

Capture the current authoritative values, including where present:

```text
MS MARCO passages
MS MARCO dev-small queries

EDGAR-CORPUS filings
EDGAR-CORPUS CIKs
year range

XBRL facts
XBRL submissions
XBRL CIKs
distinct tags

full-key duplicate rate

strict cross-filing value-revision rate

EDGAR ↔ XBRL 10-K coverage
2016–2020 aligned pairs

primary filings
table survival
inline-XBRL survival

raw source size
total data directory size
```

Also record:

```text
PHASE 1 COMPLETE — DATA FROZEN — PHASE 2 READY
```

or whatever the latest readiness report actually states.

In `Progress.md`, explain that the previous data-acquisition phase is now treated as:

```text
Data Preparation — COMPLETE
```

under the newer engineering roadmap if that is how `PROJECT_EXECUTION.md` defines it.

---

# 5 — SUMMARIZE THE MOST IMPORTANT DATA LESSONS

Do not simply list counts.

Capture the engineering lessons discovered during acquisition and validation.

Look for documented issues such as:

```text
CIK string vs integer mismatch
coreg / segments handling
XBRL version semantics
tuple truncation bugs
coverage denominator mistakes
structured tables missing from EDGAR-CORPUS
primary HTML retaining tables
inline XBRL survival
cross-filing value-revision methodology
year-alignment decisions
invalid ddate outliers
```

Only include issues actually supported by repository documentation/logs.

For each important one, briefly record:

```text
Problem
Why it mattered
Resolution
```

These lessons are important because `Progress.md` should preserve engineering reasoning rather than just say "data downloaded."

---

# 6 — INSPECT EXISTING CODE

Inspect:

```text
src/
```

and summarize what code currently exists.

For each meaningful module classify it:

```text
implemented
working/validated
partial
legacy/acquisition-only
planned placeholder
```

Pay particular attention to existing acquisition code such as:

```text
src/ingest/
```

and identify scripts for:

```text
MS MARCO
EDGAR-CORPUS
XBRL
primary SEC filings
validation
auditing
final Phase 1 checks
```

Do not deeply document every function.

Summarize the responsibility of each important module.

Also determine whether any code already exists for:

```text
normalization
chunking
embedding
indexing
retrieval
generation
evaluation
routing
reranking
CRAG
guardrails
API
deployment
```

This determines where engineering actually resumes.

---

# 7 — INSPECT TESTS

Inspect:

```text
tests/
```

if present.

Report:

- number of test files,
- broad test categories,
- whether tests currently focus only on ingestion/validation,
- whether Phase 0+ tests already exist,
- whether the test suite appears runnable.

If practical and inexpensive, you may run the existing test suite.

Do NOT:

- install packages,
- change environments,
- modify code to make tests pass,
- begin fixing failures.

If tests cannot run because Phase 0 environment setup has not happened, simply document that.

---

# 8 — INSPECT CONFIGURATION / ENVIRONMENT STATE

Determine whether the repository currently has:

```text
requirements.txt
pyproject.toml
environment.yml
.env.example
.gitignore
Makefile
Dockerfile
docker-compose.yml
```

or alternatives.

Report what already exists and what Phase 0 still needs to create.

Do not install anything.

Do not create the virtual environment yet.

Do not modify dependency files.

This section is specifically meant to tell us what Phase 0 needs to start from.

---

# 9 — INSPECT GIT STATE

This repository is intended to be both a project and an educational engineering artifact.

Read:

```text
GIT_CONVENTIONS.md
```

and inspect the current Git repository.

Run safe read-only commands such as:

```bash
git status
git branch --show-current
git log --oneline --decorate -n 15
git remote -v
git count-objects -vH
git tag
```

Do NOT:

```text
commit
push
pull
merge
rebase
reset
checkout another branch
delete branches
create tags
```

Report:

```text
current branch
whether working tree is clean
tracked/untracked changes
recent commits
existing tags
configured remote
approximate repo object size
```

Check whether obvious Git safety rules appear satisfied:

- `data/` contents are not tracked
- `.env` is not tracked
- large DuckDB/Lance/Parquet/model artifacts are not tracked
- planning documents are tracked or ready to be tracked
- `.gitignore` is present

If something looks risky, record it as a Git warning.

Do not fix it automatically.

---

# 10 — CHECK `.gitignore`

Inspect the actual `.gitignore`.

Verify whether it protects at least:

```text
data contents
*.duckdb
*.parquet
*.lance
*.zip
model files
.env
credentials
logs
artifacts
Python caches
virtual environments
```

Also check whether:

```text
data/.gitkeep
```

can be tracked if that is the intended structure.

Do not rewrite `.gitignore` unless explicitly instructed.

Just record its current state.

---

# 11 — INSPECT `project_plan/`

The `project_plan/` folder exists so someone discovering the repository on GitHub can learn how the system was designed and build their own RAG.

Summarize:

- which planning files exist,
- what each document contributes,
- whether the folder has its own README/index,
- whether there is an obvious reading order.

If no navigation file exists yet, record that as:

```text
Documentation improvement — not a Phase 0 blocker
```

Do not create it during this task.

---

# 12 — IDENTIFY IMPLEMENTATION VS DESIGN

Create a clear distinction in `Progress.md` between:

## Already implemented

For example:

```text
data acquisition
data validation
XBRL DuckDB construction
audit utilities
final data readiness analysis
```

if actually present.

## Designed but not implemented

For example:

```text
storage abstraction
normalizer
chunker
embedding pipeline
LanceDB retrieval
generation interface
truth contract
BM25
reranker
CRAG
router
guardrails
FastAPI
deployment
```

if those exist only in planning documents.

This distinction is extremely important.

---

# 13 — IDENTIFY KNOWN TECHNICAL RISKS

From the project documentation and actual repository state, summarize unresolved risks that matter going into Phase 0/1.

Examples may include:

```text
RTX 50-series / PyTorch CUDA compatibility
serverless LanceDB/S3 latency
future large full-corpus index size
XBRL serving format
EDGAR table limitations
primary-doc parsing cost
evaluation truth-contract correctness
```

Only include risks actually supported by repository documentation.

Classify them:

```text
OPEN
DEFERRED
RESOLVED
STRETCH
```

---

# 14 — DETERMINE THE EXACT NEXT STARTING POINT

Read the latest:

```text
PROJECT_EXECUTION.md
```

and determine the first incomplete subtask.

The expected next stage is likely:

```text
Phase 0 — Build the System Foundation
```

but verify rather than assume.

List the next phase's objective and its first few subtasks.

Do NOT execute them.

The report should end with a clear statement such as:

```text
NEXT: Phase 0 — Foundation
No Phase 0 implementation has started.
The repository baseline is now documented.
```

Only say that if supported by inspection.

---

# 15 — UPDATE `Progress.md`

Now update:

```text
Progress.md
```

## Preserve history

If `Progress.md` already contains useful content:

- do not delete it,
- do not rewrite historical entries,
- do not turn it into a polished retrospective.

Append a new clearly dated section.

Use the current local date.

Suggested structure:

```markdown
# Progress

[existing content remains untouched]

---

## YYYY-MM-DD — Pre-Phase-0 Repository Baseline

### Status

**Data Preparation: COMPLETE**
**Engineering roadmap: READY TO START**
**Next: Phase 0 — Foundation**

### Repository Snapshot

...

### Current Project Structure

```text
...
```

### Completed Work

...

### Frozen Dataset State

| Metric | Value |
|---|---:|
| ... | ... |

### Important Findings From Data Preparation

#### 1. ...
Problem:
Resolution:
Why it matters:

### Existing Code

...

### Existing Tests

...

### Environment / Dependency State

...

### Git State

...

### Documentation State

...

### Implemented vs Planned

#### Implemented
- ...

#### Planned / Not Started
- ...

### Known Risks Going Into Engineering

| Risk | Status | Note |
|---|---|---|
| ... | ... | ... |

### Phase Status

| Stage | Status |
|---|---|
| Data Preparation | COMPLETE |
| Phase 0 | NOT STARTED |
| Phase 1 | NOT STARTED |
| Phase 2 | NOT STARTED |
| Phase 3 | NOT STARTED |
| Phase 4 | NOT STARTED |
| Phase 5 | STRETCH |

### Next Step

Phase 0 — ...

First incomplete subtask:
...

### Baseline Declaration

This entry records the repository state immediately before Phase 0 implementation begins.
```

Adapt this structure based on what you actually discover.

---

# 16 — KEEP `Progress.md` EDUCATIONAL

This repository will be public.

Write for someone trying to understand:

> How was this production-style RAG project built?

Therefore explain important engineering decisions briefly.

Avoid vague entries such as:

```text
worked on data
fixed bugs
updated files
```

Prefer:

```text
Normalized CIK types explicitly after discovering that EDGAR stored CIK as VARCHAR while XBRL stored BIGINT; implicit comparison had previously produced a believable 0% overlap.
```

The goal is that a reader can understand the project's evolution through Git history + `Progress.md`.

---

# 17 — DO NOT OVERSTATE

If you cannot verify something, write:

```text
Not verified
```

or:

```text
Planned but not implemented
```

Do not infer:

```text
production-ready
tested
working
complete
```

from planning text alone.

Likewise, do not say a dependency is installed unless the environment proves it.

---

# 18 — FILE MODIFICATION LIMIT

This task should modify:

```text
Progress.md
```

only.

Do not modify:

```text
source code
configuration
requirements
planning documents
.gitignore
data
tests
Git history
```

If `Progress.md` does not exist, create it.

Do not make a Git commit.

We will review `Progress.md` first and commit separately.

---

# 19 — FINAL CONSISTENCY CHECK

Before finishing:

- reread the new `Progress.md` section,
- verify all major numbers against the authoritative readiness report,
- verify phase names against the latest execution plan,
- verify implementation claims against actual files,
- ensure no secret values were copied into the document,
- ensure no absolute personal filesystem paths were unnecessarily exposed,
- ensure historical/superseded metrics are not presented as final numbers.

---

# FINAL RESPONSE TO ME

After completing the inspection and updating `Progress.md`, respond with:

1. **Repository status:** concise summary
2. **Current phase:** where the project actually stands
3. **Next phase:** what is next
4. **Top 5 things already completed**
5. **Top 5 things not yet implemented**
6. **Any Git warnings**
7. **Any documentation warnings**
8. **Exact file modified**
9. **Confirmation that no Phase 0 work was started**
10. **Confirmation that no Git commit/push was performed**

Do not begin Phase 0.

Stop and wait for my approval.