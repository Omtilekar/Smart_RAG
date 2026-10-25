# Task 4.A1 — Group 2 Archify Sync, Validation, Commit, and Push

## Objective

Finalize the completed Group 2 / Gate A production-dense-retriever work before any Group 3 implementation begins.

This task has four goals:

1. verify the repository state after Task 4.A;
2. update the project's Archify architecture artifact so it reflects the **actual current live architecture**;
3. run the required regressions and truthfulness checks;
4. create one clean Git commit for the completed Group 2 work and push it to the existing remote branch.

**Do not start Group 3.**
**Do not modify the router/classifier experiment worktree.**
**Do not wire metadata filters or CRAG in this task.**

---

# 0. Important Parallel-Work Boundary

There are two worktrees:

```text
C:\Om\Codes\RAG
→ main project worktree
→ Group 2 / Task 4.A changes live here
→ THIS task runs here

C:\Om\Codes\RAG-router
→ separate worktree
→ experiment/group3-router-bakeoff
→ Group 3 work is STOPPED
```

Do not switch the main worktree to the Group 3 branch.
Do not merge, cherry-pick, rebase, or delete the Group 3 worktree/branch.
Do not edit files under `C:\Om\Codes\RAG-router`.

Before doing anything, record:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short
git log --oneline --decorate -8
git remote -v
git worktree list
```

If the current directory is not `C:\Om\Codes\RAG`, stop.

---

# 1. Read Current Source of Truth

Read:

```text
Progress.md
PROJECT_OVERVIEW.md if present
project_plan/PROJECT_EXECUTION.md
project_plan/TASK_4A_PRODUCTION_DENSE_RETRIEVER.md
project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md
project_plan/PHASE4_FASTAPI_SERVICE.md
project_plan/DEVELOPER_COMMANDS.md
```

Inspect the current code rather than trusting documentation:

```text
src/retrieval/production.py
src/api/dependencies.py
src/api/app.py
src/api/schemas.py
src/config.py
src/retrieval/cache.py
retrieval-security / context-guard modules
src/api/static/
```

Confirm the actual current runtime architecture.

Expected Task 4.A state:

```text
LIVE DENSE RETRIEVER
Qwen/Qwen3-Embedding-0.6B
revision 97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
1024 dimensions
10,487,096 production rows
ProductionDenseRetriever
production mode default
no silent fallback to BGE
```

Verify these facts from code/config/artifacts/runtime before putting them into Archify.

---

# 2. Preserve the Current Known Limitations

The architecture update MUST show these limitations clearly.

## Current performance limitation

Current live dense routing does **not yet pass company/year filters** into the production retriever.

Therefore:

```text
unscoped production exact search
≈ 33 seconds

company + year scoped search
≈ 61–77 ms in the Task 4.A local smoke

company-only scoped search
≈ 82 ms
```

These are local smoke measurements, not final system-wide SLA claims.

Do not imply that the current `/query` dense path runs at ~70 ms.
It still pays the unscoped scan for dense questions until Gate B is completed.

## CRAG limitation

CRAG remains disabled in the production live path.

The existing `0.5531` threshold was calibrated on the smaller development corpus and has NOT been validated on the 10.49M-row production index.

Do not show CRAG as live.

## Router limitation

The current live router still does not pass CIK/year metadata filters to the production dense retriever.

Do not claim the full evaluated router is production-live.

## Reranker status

No reranker is selected for the current retrieval stack.

Phase 3 reranking was a negative result.

Do not add a reranker to the diagram.

---

# 3. Use Archify — Do Not Manually Fake the Diagram

Use the installed **Archify** agent skill.

First inspect how Archify is installed in this Claude Code environment.

Do not invent an invocation.

If the Archify skill is unavailable, stop and report that clearly rather than manually pretending to have used it.

Use Archify to inspect the repository and create/update a **source-backed high-level runtime architecture diagram**.

Prefer updating the existing Archify artifact if one already exists.

Search the repository for existing Archify inputs/outputs, for example:

```text
*.architecture.json
*.workflow.json
*archify*
*.html architecture artifacts
docs/architecture/
project_plan/architecture/
```

If an existing Archify artifact exists:
- update it in place following existing repository conventions.

If none exists:
- create the smallest sensible tracked architecture source + generated HTML location consistent with the repository's existing documentation/layout;
- do not create a new arbitrary top-level folder if an existing docs/project_plan structure is appropriate.

---

# 4. Required Archify Architecture Content

The diagram should answer:

> "How does the SEC RAG system currently process a request, what is genuinely live, and what remains the next production gate?"

Keep the main visual readable.

Aim for approximately 8–12 primary runtime components.
Put supporting metrics/details into cards/annotations rather than creating excessive edges.

Required runtime path:

```text
User
  ↓
Local Web UI
  ↓
FastAPI
  ↓
Input Guardrails
  ↓
Current Rules-First Routing Layer
  ├──────────────────────────────┐
  ↓                              ↓
Structured XBRL Path          Dense Narrative Path
  ↓                              ↓
DuckDB / XBRL                Exact Retrieval Cache
  ↓                              ↓
Deterministic answer         Qwen3 Query Encoder
                                 ↓
                         ProductionDenseRetriever
                                 ↓
                     10,487,096-row LanceDB
                                 ↓
                         Retrieval Security
                                 ↓
                           Context Guard
                                 ↓
                          Generation Provider
                                 ↓
                           Output Guard
                                 ↓
                        Answer + Citations
```

Important truthfulness annotations:

```text
LIVE DENSE:
Qwen/Qwen3-Embedding-0.6B
1024-d
10,487,096 rows

LEGACY/HISTORICAL:
BAAI/bge-small-en-v1.5
384-d
162,357-row dev index
not production default

NEXT GATE:
route company/year filters into production retrieval

CURRENT DENSE COST:
unscoped exact scan ≈ 33 s local smoke

SCOPED RETRIEVAL:
CIK+year ≈ 61–77 ms local smoke

CRAG:
selected/evaluated historically
NOT live on production index yet

RERANKING:
negative experiment
not used

TREE NAVIGATION:
implemented/evaluated historically but not currently live-routed
```

Also show the offline production-build plane separately:

```text
91,086 SEC filings
      ↓
full-corpus normalization
      ↓
256-token chunks
0 overlap
      ↓
10,487,096 chunks
      ↓
Qwen3-Embedding-0.6B
1024-d normalized vectors
      ↓
10,487,096-row LanceDB production index
```

Keep live runtime and offline build visually distinct.

---

# 5. Trust / Security Boundaries

The Archify diagram should visibly communicate:

```text
retrieved text is untrusted evidence
```

Show the major trust boundaries without overcrowding the diagram:

```text
Input Guardrails

Retrieval Security
- provenance validation
- poison / indirect-injection checks
- exact duplicate defense

Context Guard
- instruction/data isolation

Output Guard
- citation/provenance validation
```

Do not expose secret values, API keys, local absolute paths, raw vectors, internal prompts, or user data in the architecture artifact.

---

# 6. Evidence / Source Backing

Every major architecture claim should be traceable to repository evidence.

Archify cards/source links should reference real files when supported, such as:

```text
src/api/app.py
src/api/dependencies.py
src/retrieval/production.py
src/retrieval/cache.py
src/config.py
relevant guard/security modules
project_plan/TASK_4A_PRODUCTION_DENSE_RETRIEVER.md
results/phase_4a_production_dense_smoke.json
Progress.md
```

Do not use `PROJECT_SPEC.md` as the primary source for current runtime architecture where it conflicts with the implemented system.

---

# 7. Validate Archify Output

Use Archify's own validation/delivery workflow.

Do not hand over an unvalidated diagram if the skill provides validation.

Verify:

```text
no overlapping/unreadable nodes
no hidden edges
no duplicated IDs
source references valid
labels legible
live vs historical clearly distinguished
offline vs online clearly distinguished
current limitations visible
```

Open the generated HTML locally if practical and inspect it.

Do not make aesthetic changes that reduce technical truthfulness.

---

# 8. Sync Existing Project Showcase

The existing project UI under:

```text
src/api/static/
```

already reports the production Qwen index as live.

Perform a truthfulness audit only.

Confirm it agrees with the new Archify artifact on:

```text
live model
model revision if displayed
embedding dimension
row count
production/default status
legacy BGE status
CRAG status
reranker status
current filter-routing limitation
```

Do not redesign the UI in this task.

Only fix factual inconsistencies introduced by or revealed after Task 4.A.

---

# 9. Small Group 2 Cleanup

Resolve the documented low-risk Task 4.A follow-ups where safe and directly related.

Inspect and correct if still applicable:

```text
.env.example
→ document DENSE_RETRIEVER_MODE

Dockerfile / .dockerignore
→ if they still explicitly describe/package only the old dev index,
   update documentation/configuration references so they no longer make
   false claims about the live local architecture
```

Important:

AWS/cloud deployment remains deferred.

Do NOT attempt to package/copy the 47+ GiB production index into a Docker image.

Do NOT redesign deployment architecture.

If Docker production-artifact mounting needs a larger design decision, document it instead of forcing a solution here.

The production artifact currently has NULL `company` for some rows and may display `CIK <n>`.

Do not fabricate company names to hide that limitation.

---

# 10. Regression / Verification Before Commit

Run:

```powershell
.\.venv\Scripts\python.exe scripts/dev.py doctor
.\.venv\Scripts\python.exe scripts/dev.py test --portable
.\.venv\Scripts\python.exe -m pytest tests/test_production_retriever.py
```

Also run:

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not generation_api"
```

The prior Task 4.A report had 2 environment-related failures caused by Windows Application Control blocking a pandas DLL.

Do not hide them.

If they still occur:
- verify they are the same environment/Application-Control failures;
- record them exactly;
- do not claim a fully green suite.

If they disappear, report the clean result.

Do not run paid generation tests.

Do not run protected TEST.

Do not access AWS.

---

# 11. Runtime Truth Check

Run the local service in production dense mode and verify `/status`.

Expected concepts:

```text
dense_retriever_mode = production
embedding_model = Qwen/Qwen3-Embedding-0.6B
embedding_dimension = 1024
dense_index_row_count = 10487096
artifact_status = production
```

Do not use a real `/query` call that could invoke OpenRouter.

Use a fake/local provider or status-only smoke where possible.

Confirm `/health`, `/status`, `/docs`, and the static UI still work.

---

# 12. Update Progress / Architecture Docs

Append a concise Task 4.A1 entry to `Progress.md`.

Record:

```text
Archify architecture updated/validated
source-backed files used
Group 2 status remains COMPLETE
known Gate B limitation
CRAG still not live
Group 3 explicitly not started by this task
regression results
Git commit hash
push result
```

Update an architecture/readme document only if one already owns the current architecture.

Do not rewrite frozen Phase 3 historical decisions.

---

# 13. Git Review Before Commit

Before staging:

```powershell
git status --short
git diff --stat
git diff
```

Confirm:

- no production index/vector/chunk/model files are stageable;
- no `.env`;
- no credentials;
- no AWS secrets;
- no files from `RAG-router`;
- no unrelated Group 3 classifier work;
- no generated multi-GB artifact;
- only Group 2 / Archify / directly-related docs/config/tests are included.

Also inspect:

```powershell
git status --ignored --short
```

to make sure large artifacts remain ignored.

---

# 14. Commit

If verification is acceptable, create ONE coherent commit.

Recommended commit message:

```text
Finalize production dense retrieval integration
```

Before committing, show the exact staged file list:

```powershell
git diff --cached --name-status
git diff --cached --stat
```

Then commit.

Do not squash/rewrite prior history.

Do not amend an unrelated previous commit.

---

# 15. Push

Inspect the existing remote and upstream first:

```powershell
git remote -v
git branch -vv
```

Use the repository's existing remote.

Do not invent or replace the remote URL.

Push the current Group 2 branch.

If the branch already has an upstream:

```powershell
git push
```

If it does not, use the existing remote and set upstream explicitly:

```powershell
git push -u <existing-remote-name> <current-branch>
```

Do NOT use:

```text
--force
--force-with-lease
```

unless the user explicitly instructs it later.

Do not push the Group 3 experimental branch in this task.

---

# 16. Post-Push Verification

After push:

```powershell
git status
git log --oneline --decorate -5
git branch -vv
git worktree list
```

Confirm:

```text
working tree clean
commit exists locally
current branch tracks remote
push succeeded
RAG-router worktree still exists
experiment/group3-router-bakeoff untouched
```

---

# 17. Safety Constraints

Absolutely do not:

```text
start Group 3
train router classifier
modify router taxonomy
wire CIK/year filters
enable CRAG
add reranker
run protected TEST
make OpenRouter calls
access AWS
rebuild chunks
rebuild embeddings
rebuild production LanceDB
delete the dev index
delete the Group 3 worktree
force-push
```

Protected TEST must remain:

```text
0/3
```

---

# 18. Final Report

Return exactly these sections:

```text
ARCHIFY
- skill invocation used
- artifact/source files updated
- validation result
- architecture claims verified

GROUP 2 RUNTIME
- live embedding model
- model revision
- dimension
- production row count
- retriever implementation
- /status verification

KNOWN LIMITATIONS
- unscoped search latency
- scoped local-smoke latency
- metadata filters not live-routed yet
- CRAG not live
- company NULL/CIK display issue if still present
- Docker/deployment note if still applicable

REGRESSION
- doctor
- portable
- production retriever tests
- non-generation suite
- exact explanation of any remaining failures

SAFETY
- OpenRouter calls: 0
- AWS access: 0
- protected TEST: 0/3
- production artifacts rebuilt: NO
- Group 3 modified: NO

GIT
- branch
- commit hash
- commit message
- remote
- push result
- final git status
- group3 worktree status
```

After the push succeeds, STOP.

Do not begin Group 3.
