# Git conventions

Rules for this repository. Written down because the repo is a portfolio
artifact — someone will read the history, not just the final state.

---

## The core rule

**Commit when something works. Push at the end of every session.**

A commit is your undo. A push is your backup. Not every commit needs a push,
but never end a working session with unpushed work.

---

## Commit granularity

**Commit per subtask, not per phase.** Phases in `PROJECT_EXECUTION.md` are
20–50 hours each. A commit that size is unreviewable, unrevertable, and loses
a day's work if something goes wrong.

| Unit | Action |
|---|---|
| Subtask (e.g. 1.3 chunker) | One commit, sometimes several |
| Anything over ~2 hours of work | Break into multiple commits |
| End of session | Push |
| Phase exit gate | Tag |

A good commit is one coherent change that leaves the repo in a working state.

---

## DO

### Content

- **Commit `Progress.md` frequently.** Its git history shows the debugging as
  it happened rather than as a tidy retrospective. That history is evidence.
- **Commit eval results as small files.** Export metrics to CSV or JSON and
  commit those. The database file itself stays ignored.
- **Commit configs.** `configs/*.yaml`, `configs/eval_tags.yaml`, chunk
  configs. These are how experiments are reproduced.
- **Commit `.env.example`** with variable names and no values.
- **Commit the planning documents.** `PROJECT_SPEC.md`,
  `PROJECT_EXECUTION.md`, `REVIEW_RESOLUTIONS.md`, `FAILURES.md`.
- **Commit tests**, including the injection-resistance test and the
  hand-constructed metric unit tests.

### Process

- **Push before stopping for the day**, even mid-subtask. Use a WIP message
  if needed.
- **Tag phase exits**: `git tag phase-2-complete`. Eval runs record a git SHA;
  tags make those SHAs meaningful later.
- **Make an initial commit now**, before Phase 0, containing the planning
  documents. It timestamps work that is otherwise invisible in a history that
  starts at "add chunker".
- **Branch for Phase 3 ablations only.** One branch per experiment, because
  components that fail to earn their place get reverted, and reverting a
  branch is cleaner than untangling a merge.
- **Work on `main` otherwise.** Solo project; branch ceremony adds nothing.

### Messages

Write what changed and why. This history will be read.

```
Good:
  Fix silent CIK type mismatch causing 0% join rate
  Add coreg/segments to facts table — false 56.5% dup rate without them
  Freeze chunk schema before indexing (int64 cik everywhere)
  Add section-aware chunker, recall@10 0.61 -> 0.68 on dev

Bad:
  update
  fix bug
  wip
  changes
```

A reader scrolling the history should be able to follow the reasoning. "Fix
silent CIK type mismatch causing 0% join rate" is worth more than the code it
describes.

---

## DON'T

### Never commit

- **Data.** `data/` in any form.
- **`*.duckdb` files.** `xbrl.duckdb` alone is 6.6 GB.
- **`*.lance/` directories, `*.parquet`, `*.zip`, embeddings, indexes.**
- **Model weights or Hugging Face cache.**
- **`.env`, API keys, AWS credentials, `SEC_USER_AGENT` with a real address.**
- **`logs/`, `artifacts/`, `__pycache__/`, `.ipynb_checkpoints/`.**

**Why this matters more than usual here**: git history keeps large files
permanently, even after deletion. Committing a 6.6 GB database once means
every future clone downloads it forever. The fix requires history rewriting,
which is painful and breaks anything already pushed.

### Never do

- **Never `git push --force` to a pushed branch.** Rewriting shared history
  breaks clones and is the standard way to lose work.
- **Never commit secrets "temporarily".** Once pushed, treat the key as
  compromised and rotate it. Removing the commit does not remove it from
  history or from anyone's clone.
- **Never leave large uncommitted work overnight.** An unpushed day is an
  unbacked-up day.
- **Never commit broken code to `main`** without saying so in the message.
  If it must go in, say `WIP: chunker mid-refactor, tests failing`.
- **Never squash the bug-fix history.** The commits documenting the five
  silent validation bugs are among the repository's more valuable content.
  Clean history is worth less than honest history here.

---

## `.gitignore`

Put this in place **before** the first commit.

```gitignore
# Data — never commit
data/
artifacts/
logs/
*.duckdb
*.duckdb.wal
*.lance/
*.parquet
*.zip
*.idx
*.part

# Models and caches
models/
.cache/
**/.huggingface/
*.onnx
*.safetensors
*.bin

# Secrets
.env
.env.local
*.pem
credentials*

# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.ipynb_checkpoints/

# OS / editor
.DS_Store
.idea/
*.swp

# Exceptions — small artifacts worth keeping
!data/.gitkeep
!results/*.csv
!results/*.json
```

Note the exceptions at the bottom: exported eval metrics belong in the repo
even though the databases that produced them do not.

---

## Suggested workflow

### Daily

```bash
git status                  # confirm nothing large is staged
git add <specific files>    # not `git add .` early on
git commit -m "..."
git push
```

Prefer naming files explicitly until `.gitignore` is proven. `git add .` with
an incomplete ignore file is how 6 GB gets committed.

### At a phase gate

```bash
git tag phase-2-complete
git push --tags
```

### Phase 3 ablations

```bash
git checkout -b ablation/reranker
# build, measure, record result in Progress.md
# if it earns its place:
git checkout main && git merge ablation/reranker
# if it does not:
git checkout main && git branch -D ablation/reranker
# either way, record the measurement — a negative result is a result
```

---

## Before the first commit — checklist

- [ ] `.gitignore` in place with the contents above
- [ ] `git status` shows no files inside `data/`
- [ ] `.env` is ignored; `.env.example` is tracked
- [ ] No real email or API key in any tracked file
- [ ] Planning documents committed
- [ ] `git count-objects -vH` shows a small repository

If the repository is already larger than a few MB before any code exists,
something is being tracked that should not be. Fix it now — it is far cheaper
than rewriting history later.

---

## Recovery

**Committed a large file but have not pushed:**

```bash
git rm --cached path/to/large.file
echo "path/to/large.file" >> .gitignore
git commit --amend
```

**Already pushed a large file**: history rewriting is required
(`git filter-repo` or BFG). Painful. This is why the `.gitignore` goes in
first.

**Pushed a secret**: rotate the credential immediately. Removing the commit
does not un-expose it.
