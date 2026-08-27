You are working inside my SEC RAG repository.

We are beginning:

```text
Phase 0 — Build the System Foundation
Task 0.0 — Git Safety Preflight
```

This task exists because the repository currently has:

```text
0 commits
no .gitignore
no remote
all files untracked

data/      ~26.28 GB
.tmp/      ~2.6 GB
```

A careless:

```bash
git add .
```

could attempt to stage roughly 29 GB of data/temp files.

The goal of this task is to make the repository safe for its **first Git commit**.

Do NOT start Phase 0.1 or any RAG implementation.

---

# OBJECTIVES

Complete only these goals:

1. create/fix `.gitignore`,
2. verify that large data, temp files, models, secrets, generated artifacts, and local tooling state cannot be committed accidentally,
3. preserve small reproducibility artifacts that should be public,
4. inspect Git state after the changes,
5. update `Progress.md`,
6. do **not** commit or push anything yet.

---

# STEP 1 — INSPECT CURRENT REPOSITORY STATE

Before modifying anything, inspect:

```bash
git status --short
git branch --show-current
git remote -v
git count-objects -vH
```

Also inspect the root directory and identify:

```text
data/
.tmp/
.claude/
logs/
artifacts/
models/
results/
.env*
*.duckdb
*.parquet
*.zip
*.lance/
*.onnx
*.safetensors
```

where present.

Do not recursively print millions of data files.

Summarize directory sizes instead.

---

# STEP 2 — READ THE GIT CONVENTIONS

Locate and read:

```text
GIT_CONVENTIONS.md
```

wherever it currently exists.

Treat it as the source of truth for repository Git behavior.

Important principles include:

```text
Commit per subtask
Push at end of session
Tag phase exits
Never commit data
Never commit secrets
Never force-push pushed branches
Keep Progress.md history
Commit small eval result files/configs
```

Do not change those conventions during this task unless a small technical correction is required for `.gitignore` compatibility.

---

# STEP 3 — CREATE OR FIX `.gitignore`

Create a root:

```text
.gitignore
```

if it does not exist.

It must protect at minimum:

```gitignore
# Raw / derived data
data/*
!data/.gitkeep

# Temporary files
.tmp/
tmp/
temp/

# Large generated artifacts
artifacts/
logs/

*.duckdb
*.duckdb.wal
*.parquet
*.zip
*.idx
*.part
*.lance/

# Models / model caches
models/
.cache/
**/.huggingface/
*.onnx
*.safetensors
*.bin

# Secrets
.env
.env.local
.env.*
!.env.example
*.pem
credentials*
secrets*

# Python
__pycache__/
*.py[cod]
.venv/
venv/
env/
*.egg-info/
.pytest_cache/
.ipynb_checkpoints/

# IDE / OS
.DS_Store
.idea/
.vscode/
*.swp

# Local tooling state
.claude/
```

Preserve small experiment-result files that are meant to be public.

If the repository uses:

```text
results/
```

do NOT ignore the entire directory.

Allow files such as:

```text
results/*.csv
results/*.json
results/*.md
```

to remain trackable.

Do not invent unnecessary patterns.

---

# STEP 4 — ENSURE `data/.gitkeep` CAN BE TRACKED

Because we want the repository to communicate where data belongs without committing the datasets:

```text
data/
```

should exist in Git with a placeholder.

Make sure the ignore rule is:

```gitignore
data/*
!data/.gitkeep
```

not simply:

```gitignore
data/
```

because ignoring the parent directory entirely can prevent the exception from working as intended.

If:

```text
data/.gitkeep
```

does not exist, create it.

The actual contents of `data/` must stay ignored.

---

# STEP 5 — HANDLE `.tmp/`

The current baseline identified approximately:

```text
.tmp/ ≈ 2.6 GB
```

of orphaned DuckDB temporary files.

For this task:

- ensure `.tmp/` is ignored,
- verify Git cannot stage it accidentally.

Do NOT delete it unless there is already explicit repository policy authorizing cleanup.

This task is Git safety, not disk cleanup.

Record the disk-cleanup issue in `Progress.md` if it remains.

---

# STEP 6 — PROTECT SECRETS

Search carefully for common secret-bearing files/names:

```text
.env
.env.local
credentials
aws credentials
API keys
SEC_USER_AGENT
private keys
*.pem
```

Do NOT print secret values into the terminal output, report, or `Progress.md`.

Only report:

```text
found / not found
tracked / untracked
protected / not protected
```

If a file contains real credentials, ensure it is ignored.

Create:

```text
.env.example
```

ONLY if one already belongs to this task according to the project plan.

Otherwise leave `.env.example` for Phase 0.5 and just ensure it would be trackable later.

Do not add real values.

---

# STEP 7 — VERIFY LARGE FILE SAFETY

Run safe checks to ensure large files are not being staged or tracked.

Useful commands may include:

```bash
git status --short --ignored
git ls-files
git check-ignore -v data/xbrl.duckdb
git check-ignore -v .tmp/
```

Also test representative files such as:

```text
data/xbrl.duckdb
data/raw/xbrl/<sample>.zip
data/edgar_corpus/<sample>.parquet
.tmp/<sample-temp-file>
```

Do not use `git add .`.

Do not stage the actual data files.

---

# STEP 8 — CHECK FOR FILES THAT SHOULD REMAIN TRACKABLE

Confirm that important project files are **not accidentally ignored**.

Examples:

```text
README.md
Progress.md
project_plan/
src/
tests/
configs/
scripts/
results/*.json
results/*.csv
.env.example
.gitignore
```

Use:

```bash
git check-ignore -v <file>
```

where useful.

If a rule is too broad and accidentally ignores important source/documentation files, correct `.gitignore`.

---

# STEP 9 — SAFE STAGING DRY RUN

Do NOT actually create a commit.

Use one of these approaches:

```bash
git add -n .
```

or:

```bash
git status --short
```

to inspect what Git *would* stage.

The expected stageable set should contain only lightweight project files such as:

```text
source code
Markdown documentation
prompts
.gitignore
small config files
Progress.md
```

It should NOT contain:

```text
data files
DuckDB
Parquet
ZIPs
Lance indexes
model weights
logs
temporary files
secrets
virtual environments
```

If anything large or unsafe appears, fix `.gitignore` and re-check.

---

# STEP 10 — CHECK REPOSITORY SIZE

Run:

```bash
git count-objects -vH
```

Because there are currently zero commits, repository object storage should still be tiny.

If Git objects are unexpectedly large, investigate before proceeding.

Do not rewrite history because there should not yet be any pushed history.

---

# STEP 11 — OPTIONAL SAFE LARGE-FILE CHECK

If practical, inspect all currently stageable files and flag anything unexpectedly large.

A reasonable warning threshold:

```text
> 10 MB
```

Do not automatically delete anything.

Just verify that no unintended large binary is about to enter the first commit.

---

# STEP 12 — DO NOT COMMIT OR PUSH

This task must NOT run:

```bash
git commit
git push
git tag
git checkout
git reset
git rebase
git merge
git push --force
```

We want to inspect the result first.

The first commit will be a separate task.

---

# STEP 13 — UPDATE `Progress.md`

After Git safety is verified, update:

```text
Progress.md
```

Preserve all existing content.

Append a new dated entry under the existing pre-Phase-0 baseline.

Use a heading similar to:

```markdown
## 2026-08-26 — Phase 0.0 Git Safety Preflight
```

Use the current local date if different.

Include:

### Objective

Explain why Git safety had to happen before the first commit.

### Initial State

Record:

```text
0 commits
no / previous .gitignore state
data size
.tmp size
everything previously untracked
```

Use measured values from this task.

### Changes Made

Document:

```text
.gitignore created/updated
data contents ignored
data/.gitkeep behavior
.tmp ignored
.claude ignored
models/caches ignored
DuckDB/Parquet/ZIP/Lance ignored
secrets ignored
venv/cache ignored
logs/artifacts ignored
small results remain trackable
```

### Verification

Include results of checks such as:

```text
git status
git check-ignore
git add -n .
git count-objects -vH
```

Do not paste hundreds of lines.

Summarize the important findings.

### Safety Result

Use one of:

```text
PASS — repository is safe for the first commit

WARN — repository mostly safe but remaining issue requires review

BLOCKED — unsafe files would still be committed
```

### Files Modified

List only files actually changed.

Likely:

```text
.gitignore
data/.gitkeep
Progress.md
```

Possibly fewer.

### Remaining Git Notes

Examples:

```text
first commit not yet created
remote not yet configured
.tmp still consumes disk but is safely ignored
```

### Phase Status

Keep:

```text
Data Preparation — COMPLETE
Phase 0 — IN PROGRESS
```

and mark:

```text
0.0 Git Safety Preflight — COMPLETE
0.1 Python environment — NEXT
```

only if Task 0.0 passed.

---

# STEP 14 — FINAL SAFETY CHECK

Before finishing, verify again:

```bash
git status --short
git status --ignored --short
git count-objects -vH
```

Ensure no large data or secrets are stageable.

---

# ACCEPTANCE CRITERIA

Task 0.0 is complete only if:

```text
[ ] root .gitignore exists
[ ] data contents are ignored
[ ] data/.gitkeep can be tracked
[ ] .tmp/ is ignored
[ ] .claude/ is ignored
[ ] *.duckdb is ignored
[ ] *.parquet is ignored
[ ] *.zip is ignored
[ ] *.lance/ is ignored
[ ] model weights/caches are ignored
[ ] .env and credentials are ignored
[ ] venv/cache files are ignored
[ ] logs/artifacts are ignored
[ ] source/docs/configs remain trackable
[ ] small results files remain trackable
[ ] dry-run staging contains no unintended large files
[ ] Git object storage remains small
[ ] Progress.md is updated
[ ] no commit was created
[ ] nothing was pushed
```

---

# FINAL RESPONSE TO ME

When finished, respond with:

## Phase 0.0 Result

```text
PASS / WARN / BLOCKED
```

## Files modified

List each file.

## Protected paths

Summarize the important ignore categories.

## Dry-run result

State whether any data, database, Parquet, ZIP, model, temp, secret, or large generated artifact would be staged.

## Repository object size

Report the output summary from:

```bash
git count-objects -vH
```

## Remaining warnings

List any remaining Git hygiene issues.

## Progress.md

Confirm that the Phase 0.0 entry was appended.

## Next task

If PASS:

```text
Phase 0.1 — Python Environment
```

Finally confirm explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 0.1 work started.
```

Stop after this task and wait for my approval.