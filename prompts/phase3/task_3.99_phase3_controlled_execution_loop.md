# Phase 3 — Controlled Execution Loop

## Task name

`task_3.99_phase3_controlled_execution_loop.md`

## Objective

Continue Phase 3 **one numbered roadmap task at a time** after Task 3.5,
using the repository's current `PROJECT_EXECUTION.md`, frozen evaluation
contracts, ablation-table discipline, Git conventions, and regression gates.

This is a **controlled engineering loop**, not a blind "finish everything"
instruction.

The controller may automatically continue from one Phase 3 task to the next
only when:

- the current task is formally complete;
- all required tests pass;
- all frozen identities/scope checks pass;
- the experiment's pre-frozen decision rule resolves the outcome
  unambiguously;
- no user decision is required;
- protected TEST remains untouched;
- the next roadmap task is explicitly defined in the current repository.

The controller must STOP immediately when a real ambiguity, trade-off,
failure, or protected-evaluation boundary appears.

Do not start Phase 4.

Do not use protected TEST for tuning.

Do not silently change the roadmap.

---

# Core operating principle

Use this loop:

```text
READ CURRENT REPOSITORY STATE
        ↓
VERIFY CURRENT TASK COMPLETE
        ↓
VERIFY TEST / HASH / GIT / SCOPE GATES
        ↓
READ EXACT NEXT PHASE 3 TASK
        ↓
FREEZE THAT TASK'S EXPERIMENT CONTRACT
        ↓
IMPLEMENT ONLY THAT TASK
        ↓
RUN DEV EVALUATION
        ↓
APPLY PRE-FROZEN DECISION RULE
        ↓
UPDATE RESULTS + ABLATION TABLE + DOCS
        ↓
RUN REGRESSION SUITES
        ↓
COMMIT TASK
        ↓
RE-READ ROADMAP
        ↓
CONTINUE IF UNAMBIGUOUS
        ↓
PHASE 3 EXIT AUDIT
        ↓
STOP
```

Never skip the re-read between tasks.

---

# Stage 0 — Do not interfere with a currently running Task 3.5

The user is currently running:

```text
Phase 3 — Task 3.5: RRF Hybrid Fusion
```

Before doing anything else:

1. inspect current running processes relevant to the repository;
2. inspect Git status;
3. inspect `Progress.md`;
4. inspect Task 3.5 result/config files if they exist;
5. inspect the current Task 3.5 runner/checkpoint/status if present.

If Task 3.5 is still actively running:

```text
CONTROLLER STATUS:
WAITING FOR TASK 3.5
```

Do not:

- start another modifying process;
- restart Task 3.5;
- rebuild dense/sparse artifacts;
- edit tracked files used by Task 3.5;
- create a competing Task 3.5 run;
- run the next numbered task.

Only read-only monitoring is allowed until Task 3.5 finishes.

If a repository-provided read-only status command exists, it may be used.

If there is no safe read-only status command, STOP and tell the user to
resume this controller after Task 3.5 finishes.

Do not poll aggressively.
Do not mutate checkpoints merely to inspect status.

---

# Authoritative source order

At the beginning of the controller and again **after every completed task**,
read in this order:

1. `project_plan/PROJECT_EXECUTION.md`
2. `Progress.md`
3. `project_plan/GIT_CONVENTIONS.md`
4. current Phase 3 task-specific planning documents
5. `results/phase_3_ablation_table.csv`
6. current Phase 3 tracked result/config artifacts
7. Task 2.10 canonical hashing/versioning implementation
8. Task 2.11 run-log implementation
9. current source/tests for components being modified

Repository truth always wins.

Do not continue based on remembered task numbering or this controller's
assumptions when the live roadmap differs.

---

# Global frozen Phase 3 state

At the time this controller is created, Phase 3 has already frozen:

## Evaluation scope

```text
split:
DEV

scope:
Task 3.1 frozen DEV/evaluable subset

question count:
89
```

Every comparable Phase 3 retrieval/ranking experiment must use the exact same
question IDs and scope hash unless the authoritative roadmap explicitly
introduces a new, separately named evaluation contract.

Do not regenerate the scope.

Do not score out-of-scope DEV questions as misses.

Do not use FinanceBench as the routine tuning set.

## Chunking

Task 3.2 selected:

```text
split_mode:
fixed

window_size_tokens:
256

overlap_tokens:
0

stride_tokens:
256

chunk_config_hash:
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
```

Verify this against repository truth before every later task.

## Dense embedding

Task 3.3 selected:

```text
model:
Qwen/Qwen3-Embedding-0.6B

revision:
97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3

dimension:
1024
```

Verify this against repository truth before every later task.

## Sparse retrieval

Task 3.4 established:

```text
LanceDB-native FTS / BM25-style sparse retrieval
```

Use the exact frozen Task 3.4 config/artifact identity.

## Protected TEST

At controller start the expected status is:

```text
protected SEC TEST opened:
NO

official TEST runs consumed:
0/3
```

Verify this after every task.

---

# Hard global rules

These apply to every automatic loop iteration.

## Evaluation discipline

- DEV only for routine Phase 3 optimization.
- Never open protected TEST unless the current authoritative roadmap
  explicitly authorizes a Phase 3 exit TEST run.
- Never consume a TEST run silently.
- Never use TEST failures to tune.
- Never convert N/A metrics to 0.
- Never invent chunk-level gold.
- Never use same-document proxy relevance as chunk gold.

## Experiment discipline

- One numbered task at a time.
- Change only the component the task is supposed to study.
- Freeze the experiment plan before formal evaluation.
- Never alter winner rules after observing results.
- Preserve negative results.
- Never force a new component to win.
- Do not rerun expensive completed artifacts without a concrete integrity
  reason.
- Resume valid checkpoints rather than restart.
- Do not mix results across incompatible config hashes.

## Ablation discipline

- Row 0 remains immutable.
- Earlier Task 3.x rows remain immutable.
- Append later task rows.
- Never rewrite historical metrics to fit a later interpretation.
- Preserve run ID, Git SHA, config hash, scope hash, component identities,
  raw hit counts, and N/A state.

## Git discipline

- Follow current `GIT_CONVENTIONS.md`.
- Use the appropriate Phase 3 ablation branch for each scientific experiment.
- Commit each successful numbered task separately.
- Do not fabricate granular history after the fact.
- Do not commit generated model/index/data artifacts.
- Do not commit `.env`, credentials, API keys, model weights, LanceDB data,
  embeddings, Parquet corpora, checkpoints, or large logs.
- Push only if a remote is configured.
- Do not invent a remote.
- Do not create a Phase 3 exit tag until the Phase 3 exit gate actually
  passes.

## Long-running process discipline

- Formal long operations run in the foreground with visible progress.
- Use unbuffered output.
- Do not hide all useful output in background logs.
- Read-only monitoring/status must make zero model calls and perform zero
  artifact mutations.
- Do not launch two processes that can modify the same experiment state.

---

# Loop entry gate after Task 3.5

Once Task 3.5 finishes, verify it formally before continuing.

At minimum require:

```text
Task 3.5 status:
COMPLETE

doctor:
PASS

portable suite:
PASS

full suite:
PASS

protected TEST:
unopened

official TEST:
0/3

Task 3.5 result artifact:
present

Task 3.5 ablation row:
present

selection:
resolved under the pre-frozen Task 3.5 rule

Git:
task committed according to repository convention
```

If Task 3.5 produced an unresolved dense-vs-hybrid trade-off, STOP.

Do not guess which retrieval path should be inherited by the next task.

If Task 3.5 is complete but closure/docs/commit are incomplete, finish Task
3.5 closure before reading the next task.

---

# Generic loop for every remaining numbered Phase 3 task

For every next task discovered from `PROJECT_EXECUTION.md`, execute the
following 12-step procedure.

---

## LOOP STEP 1 — Read exact task contract

Print:

```text
[PHASE3 LOOP] Reading next roadmap task
```

Read the exact task number/title and all task-specific bullets in the current
`PROJECT_EXECUTION.md`.

Also read any already-existing task-specific planning document.

Do not infer the task from memory.

Print:

```text
CURRENT TASK:
  <number> — <exact title>

ALLOWED VARIABLE:
  ...

FROZEN COMPONENTS:
  ...

REQUIRED OUTPUTS:
  ...

EXIT CONDITION:
  ...
```

If the task contract is materially ambiguous, STOP for the user.

---

## LOOP STEP 2 — Verify inherited winners

Every task must explicitly identify which prior winning components it
inherits.

Verify their exact artifact/config hashes and revisions.

Examples include:

```text
chunk_config_hash
embedding model revision
dense index identity
sparse index/config identity
hybrid config identity
reranker identity
router config identity
metadata-filter config
```

Never rely on a component name alone when the repository stores a stronger
identity.

If an inherited winner cannot be reproduced, STOP.

---

## LOOP STEP 3 — Freeze experiment plan before formal run

Create/update the task-specific tracked config under:

```text
configs/
```

Use Task 2.10 canonical hashing/versioning.

The task config must include:

```text
task number/title
experiment version
DEV scope identity
question count
inherited component identities
candidate grid
candidate depths
metric contract
winner-selection rule
bootstrap convention if applicable
latency/resource measurements required
```

Do not change the formal grid or winner rule after results are seen.

If a new version is needed, preserve the old one and create a new experiment
identity.

---

## LOOP STEP 4 — Implement only the allowed component

The task may modify only its intended layer.

Examples:

```text
retrieval fusion task:
  do not modify embeddings/chunking

reranker task:
  do not modify base candidate generation

metadata filtering task:
  do not change embedding model

router task:
  do not rewrite retrieval stack

CRAG task:
  do not silently retune prior retrieval winners
```

If implementation requires changing a previously frozen component, STOP
unless the roadmap explicitly says that component is being reopened.

---

## LOOP STEP 5 — Add portable tests first

Before expensive formal runs:

- add deterministic unit tests;
- use tiny synthetic fixtures;
- make no paid API calls;
- make no real TEST access;
- avoid full model/index builds inside pytest;
- mark local GPU/model/data integration tests according to repository policy.

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

If either fails, fix the current task or STOP.

Do not proceed to expensive evaluation with a broken portable suite.

---

## LOOP STEP 6 — Pilot before expensive execution

For any new expensive model/index/component:

- run a deterministic small pilot;
- verify schema/dimension/ranking contract;
- verify resource feasibility;
- verify no silent CPU fallback when GPU is required;
- verify checkpoint/resume behavior where relevant;
- estimate full runtime.

If projected runtime/resource use is unexpectedly extreme or likely to
exceed local limits, STOP and report before launching the full run.

Do not silently replace the candidate with another component.

---

## LOOP STEP 7 — Formal DEV evaluation

Run exactly the frozen DEV scope unless the roadmap explicitly defines a
different named contract.

Use the already-established Phase 3 metric implementations.

At minimum preserve:

```text
doc_recall@10
doc_recall@50
doc_mrr
doc_ndcg@10
```

plus whatever task-specific metrics the roadmap requires.

Always record raw numerators/denominators where applicable.

For the frozen 89-question scope:

```text
R@10 -> hits / 89
R@50 -> hits / 89
```

Do not report only percentages.

Generation-based metrics remain N/A when generation is disabled.

Chunk metrics remain N/A without chunk gold.

---

## LOOP STEP 8 — Paired analysis

When comparing two configurations on the same 89 questions, use paired
question-level analysis.

Unless the task/roadmap specifies otherwise, retain the established Phase 3
bootstrap convention:

```text
seed:
42

iterations:
10000

unit:
question_id
```

Report:

```text
metric deltas
raw gain/loss counts
first-hit rank movement where relevant
95% paired bootstrap intervals
```

Do not overstate small-N evidence.

---

## LOOP STEP 9 — Apply frozen selection rule

Apply the selection rule that was written before the formal results.

Never choose based on post-hoc preference.

If the rule yields one unambiguous winner:

```text
SELECTION:
RESOLVED
```

Continue.

If quality/resource metrics create a trade-off outside the frozen rule:

```text
SELECTION:
USER DECISION REQUIRED
```

STOP and present the evidence.

Do not continue until the user resolves it.

---

## LOOP STEP 10 — Record results

For each completed task:

- write/update the task-specific result JSON;
- append the ablation table row(s);
- preserve all prior rows;
- create a normal Task 2.11 run record where applicable;
- update the task-specific planning document;
- update `Progress.md`.

Record:

```text
experiment config hash
run_id
git_sha
scope hash
question count
component identities
metrics
raw hit counts
paired deltas
bootstrap intervals
latency/resource measurements
winner
limitations
negative results
TEST status
```

---

## LOOP STEP 11 — Regression gate

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Require zero unexpected failures.

Verify:

```text
protected TEST opened:
NO

official TEST runs:
0/3
```

Verify all prior frozen result/config identities remain unchanged.

If any earlier task's artifact changes unexpectedly, STOP.

---

## LOOP STEP 12 — Commit and re-read

Follow `GIT_CONVENTIONS.md`.

Before commit:

```powershell
git status
git diff --stat
git add -n <specific files>
```

Run secret and large-file checks.

Commit the completed numbered task.

Then re-read:

```text
PROJECT_EXECUTION.md
Progress.md
phase_3_ablation_table.csv
```

Determine the exact next Phase 3 task.

If the next task is unambiguous and no stop condition applies, loop.

---

# Automatic continuation policy

The controller MAY automatically continue when all of these are true:

```text
current task COMPLETE
tests PASS
Git state clean/committed
DEV scope unchanged
TEST untouched
winner resolved by frozen rule
next Phase 3 task explicit
next task does not require user-supplied credentials
next task does not require paid API spend
next task does not create an unresolved architecture/business choice
```

The controller MUST STOP when any of these are false.

---

# Mandatory stop conditions

STOP immediately and report if any of the following occurs:

## Repository / provenance

1. `PROJECT_EXECUTION.md` and `Progress.md` materially disagree.
2. the next task number/title is ambiguous.
3. working tree contains unexplained changes.
4. an inherited artifact/config hash changed unexpectedly.
5. a prior ablation row changed.
6. row 0 changed.
7. run provenance is missing or internally inconsistent.
8. a checkpoint/config identity does not match the run being resumed.

## Evaluation

9. frozen 89-question DEV scope cannot be reproduced.
10. candidate runs use different question IDs.
11. TEST would need to be opened for tuning.
12. an official TEST run would be consumed unexpectedly.
13. FinanceBench is proposed as routine tuning data.
14. invalid proxy relevance is proposed.
15. N/A would be converted to 0.
16. a metric definition would need to be changed after seeing results.

## Scientific integrity

17. experiment grid changes after formal results without a new version.
18. winner rule is changed after seeing results.
19. a component is tuned against individual observed failures after the
    formal run without a new declared experiment.
20. a task changes more than its allowed variable.
21. an old negative result is being deleted or rewritten.
22. a new component is being forced to win despite no evidence.
23. a task's result creates an unresolved quality-vs-latency/resource
    trade-off outside the frozen rule.

## Resource / execution

24. full run is likely to exceed available disk/VRAM/RAM materially.
25. required model cannot run reliably on the local GPU.
26. unexpected repeated CUDA OOM persists after approved batch-size fallback.
27. long-running resume state appears corrupted.
28. an existing completed candidate would need to be recomputed for no
    integrity reason.
29. two modifying experiment processes are active at once.

## External services / money

30. a task requires a paid API not already explicitly approved.
31. a task would expose a secret/API key.
32. a task requires an unapproved external service.
33. `trust_remote_code=True` is newly required and not already approved.

## Tests / regression

34. doctor fails.
35. portable tests fail.
36. full suite has an unexplained regression.
37. an earlier Phase 1/2/3 frozen result changes unexpectedly.

## Git

38. generated data/model/index/checkpoint artifact is about to be staged.
39. secret scan fails.
40. large-file scan identifies an unintended artifact.
41. branch/commit history would need to be fabricated.

---

# Phase 3 exit audit

When the roadmap reports no remaining Phase 3 numbered implementation tasks,
do **not** immediately declare Phase 3 complete.

Run a dedicated Phase 3 exit audit.

Print:

```text
[PHASE3 EXIT] Audit
```

Re-read the CURRENT Phase 3 exit criteria from `PROJECT_EXECUTION.md`.

Build an audit table:

```text
| Exit criterion | Evidence | Status | Notes |
```

Verify at minimum:

```text
all numbered Phase 3 tasks complete or explicitly documented as deferred
row 0 preserved
all ablation rows present
all selected winners frozen
all negative results retained
all required DEV metrics present
all config hashes/run IDs/Git SHAs present
all regression tests pass
protected TEST discipline intact
no Phase 4 work started
```

Do not infer exit criteria from this prompt if the roadmap defines them
differently.

---

# Protected TEST at Phase 3 exit

Do not automatically consume protected TEST merely because implementation
tasks are complete.

At the exit audit:

- read the exact roadmap rule for Phase 3 TEST usage;
- verify the maximum budget remains 3;
- verify current usage count;
- if the roadmap says a final official TEST run is required and now
  authorized, STOP before opening TEST and present:

```text
PHASE 3 IMPLEMENTATION COMPLETE
OFFICIAL TEST AUTHORIZATION REQUIRED
CURRENT BUDGET: 0/3
PROPOSED RUN: 1/3
```

Wait for explicit user approval unless repository policy already contains
an explicit, previously approved authorization for that exact run.

Do not use TEST automatically.

---

# Phase 3 completion status

Only after the exit audit passes may the controller set:

```text
Phase 3 — COMPLETE
```

or the exact repository-approved equivalent such as:

```text
COMPLETE WITH NOTE
```

if documented limitations remain.

Do not create a Phase 3 completion tag until all required exit criteria pass.

Do not start Phase 4.

---

# Final controller output

When the controller stops—whether for a user decision, failure, TEST
authorization, or successful Phase 3 exit—print:

```text
PHASE 3 CONTROLLED EXECUTION LOOP
=================================

Controller status:
  <CONTINUING / STOPPED / PHASE 3 EXIT REACHED>

Last completed task:
  ...

Current task:
  ...

Reason for stop:
  ...

Frozen DEV scope:
  questions: 89
  scope_sha256: ...

Selected stack so far:
  chunking: ...
  embedding: ...
  retrieval: ...
  reranker: ...
  router: ...
  other Phase 3 components: ...

Latest trusted metrics:
  R@10: ...
  R@50: ...
  MRR: ...
  nDCG@10: ...

Protected TEST:
  opened: NO
  official runs used: 0/3

Tests:
  doctor: ...
  portable: ...
  full: ...

Git:
  current branch: ...
  latest commit: ...
  working tree: ...

Ablation table:
  rows: ...
  row 0 intact: YES

NEXT ACTION:
  <exact user decision / authorization / next task / Phase 3 exit audit>

PHASE 4:
  NOT STARTED
```

Then STOP whenever a stop condition applies.

---

# Success definition

This controller is successful if it:

- never overlaps with the currently running Task 3.5;
- finishes each remaining Phase 3 task independently;
- re-reads repository truth after every task;
- preserves the frozen 89-question DEV scope;
- preserves historical ablation rows;
- uses pre-frozen experiment/selection rules;
- keeps TEST untouched during routine optimization;
- keeps paid APIs out unless explicitly approved;
- resumes rather than restarts valid expensive work;
- runs regression gates before advancement;
- commits each successful task;
- stops for genuine user decisions;
- performs a separate Phase 3 exit audit;
- never starts Phase 4 automatically.
