# Task 1.11 — End-to-End Command

You are working inside my SEC RAG repository.

Task file:

`task_1.11_end_to_end_command.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.11 — End-to-End Command
```

Current status:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — IN PROGRESS
  1.1 Select Development Corpus               — COMPLETE
  1.2 Minimal Normalization                   — COMPLETE
  1.3 Minimal Fixed-Window Chunker            — COMPLETE
  1.4 Baseline Embedding Pipeline             — COMPLETE
  1.5 Vector-Only Index                       — COMPLETE
  1.6 Baseline Retriever                      — COMPLETE
  1.7 Minimal Generation Layer                — COMPLETE
  1.8 Citation Integrity Smoke                — COMPLETE WITH HISTORICAL WARN
  1.7a Citation Format Compliance Correction  — COMPLETE WITH WARN
  1.9 200-Question Smoke Evaluation           — COMPLETE
  1.10 Baseline Metric Runner                 — COMPLETE
  1.11 End-to-End Command                     — CURRENT
```

Task 1.11 is the final numbered Phase 1 task.

Do NOT begin Phase 2.

Do NOT silently declare Phase 1 cleanly complete if the official exit
criteria are not actually demonstrated.

---

# AUTHORITATIVE TASK DEFINITION

`project_plan/PROJECT_EXECUTION.md` defines Task 1.11:

```text
### 1.11 End-to-end command

Provide one documented command that can:

1. accept a question,
2. retrieve chunks,
3. generate an answer,
4. print citations.

Also provide one command that runs the 200-question smoke evaluation.
```

The same document defines the Phase 1 exit criteria:

```text
- One command accepts a question and returns an answer.
- The answer contains valid source citations.
- Every citation resolves back to a stored source chunk.
- A 200-question evaluation runs end to end.
- doc_recall@10 is printed and saved.
- Integration bugs found during the vertical slice are documented.
- No advanced retrieval component has been added prematurely.
```

Task 1.11 is therefore an INTEGRATION / ORCHESTRATION task.

It is not an architecture-upgrade task.

---

# VERIFIED TASK 1.10 INPUT

Task 1.10 is complete and recorded as PASS.

Current baseline:

```text
dataset:
results/phase_1_9_smoke_evaluation.json

question_count:
200

smoke_eval_sha256:
0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27

metric:
doc_recall@10

hit_count:
194

doc_recall@10:
0.970000

metric_run_config_hash:
d429b0b971d1fdf68eeb93cd526208754842181ee373b7b8fdec5ef085437e5d

metric_result_sha256:
64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

Category results:

```text
business:             38 / 40 = 0.950000
risk_factors:         37 / 40 = 0.925000
mdna:                 39 / 40 = 0.975000
market_risk:          40 / 40 = 1.000000
financial_statements: 40 / 40 = 1.000000
```

Task 1.10 determinism:

```text
two independent fresh-process 200-question runs
same hit count
same recall
same per-question hit/first_hit_rank
same retrieved chunk-ID order
same retrieved document-ID order
same metric_result_sha256
```

Manual checks:

```text
10 / 10 PASS
```

Independent arithmetic:

```text
194 hits / 200 = 0.97
```

Task 1.10 tests:

```text
portable: 330 passed, 10 deselected, 0 failed
full:     340 passed, 0 failed
doctor:   PASS
```

Task 1.10 commit message:

```text
Add baseline retrieval metric runner
```

Use the actual Git hash from the repository.

Do not invent it.

---

# ACCEPTED EXISTING GENERATION WARNING

Task 1.7a remains truthfully:

```text
COMPLETE WITH WARN
```

Historical citation-format compliance:

```text
Task 1.8 baseline:
3 / 10 PASS

Task 1.7a prompt-only rerun:
8 / 10 PASS
```

Residual Task 1.7a failures:

```text
citation-smoke-01
citation-smoke-07
```

Both remained malformed fullwidth-bracket attempts:

```text
【...】
```

Important evidence that remained good:

```text
unknown_chunk_id cases:              0
citation_not_in_supplied_context:    0
```

The user explicitly approved proceeding through Tasks 1.9 and 1.10 with
this limitation documented.

Task 1.11 must continue to preserve that history.

Do NOT say citation-format compliance is 10/10.

Do NOT normalize `【】` into `[]`.

Do NOT repair citations.

Do NOT silently switch models.

---

# TASK 1.11 COMMAND DESIGN — FROZEN

Use one small Phase 1 CLI module:

```text
src/cli/phase1.py
```

Document these two commands:

```bash
python -m src.cli.phase1 answer --question "..."
```

and:

```bash
python -m src.cli.phase1 evaluate
```

This finally gives the existing `src/cli/` package a real Phase 1 purpose
without introducing FastAPI or a production service.

If the actual repository contains a materially different, already-frozen
CLI convention that conflicts with this location:

**STOP AND ASK ME.**

Do not create several competing Phase 1 CLI entry points.

---

# COMMAND 1 — ANSWER

The command:

```bash
python -m src.cli.phase1 answer --question "<question>"
```

must compose the existing Phase 1 stack:

```text
question
   ↓
Task 1.6 BaselineRetriever
   ↓
top 5 chunks
   ↓
Task 1.7 / 1.7a MinimalGenerator
   ↓
OpenRouterProvider
   ↓
answer
   ↓
parsed [chunk_id] citations
   ↓
console output
```

Do not reimplement retrieval or generation inside the CLI.

---

# COMMAND 2 — EVALUATE

The command:

```bash
python -m src.cli.phase1 evaluate
```

must run the existing frozen Task 1.9 / Task 1.10 200-question retrieval
smoke evaluation.

Expected logical result:

```text
question_count = 200
hit_count = 194
doc_recall@10 = 0.970000
metric_result_sha256 =
64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

Do not duplicate the metric implementation.

Reuse Task 1.10's runner.

---

# CRITICAL RULE — DO NOT ASSUME

If any implementation decision is not clearly resolved by:

1. the actual repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_RETRIEVER.md`,
4. `project_plan/PHASE1_GENERATION.md`,
5. `project_plan/PHASE1_CITATION_INTEGRITY.md`,
6. `project_plan/PHASE1_SMOKE_EVALUATION.md`,
7. `project_plan/PHASE1_BASELINE_METRICS.md`,
8. current code/tests/results,

then:

**STOP AND ASK ME.**

Do not silently choose:

```text
a different generation provider
a different generation model
a different embedding model
a different k
a new metric
a new eval subset
a citation normalization rule
a citation repair loop
a retry-until-valid strategy
a new structured-output format
a new CLI framework
a FastAPI route
a new dependency
a new retrieval component
a new prompt revision
a new Task 1.7b
a Phase 2 implementation
```

When asking:

- state exactly what is ambiguous,
- state the repository evidence,
- provide the smallest useful options,
- explain downstream effect,
- wait for my answer.

Inspection first.

Assumption never.

---

# PRIMARY OBJECTIVES

Complete only:

1. verify Task 1.10 is committed and healthy,
2. verify the official Task 1.11 / Phase 1 exit contract,
3. implement one thin `src.cli.phase1` CLI,
4. expose `answer --question`,
5. expose `evaluate`,
6. reuse existing Task 1.6 retrieval,
7. reuse existing Task 1.7/1.7a generation,
8. reuse existing Task 1.10 metric runner,
9. print answer and citations clearly,
10. print the 200-question metric clearly,
11. perform one real live answer-command integration smoke,
12. mechanically verify that live demo's citations,
13. perform one real `evaluate` command run,
14. verify it reproduces the Task 1.10 logical result,
15. add portable CLI tests using fakes/mocks,
16. run the complete test suite,
17. document all integration findings,
18. evaluate every official Phase 1 exit criterion,
19. commit Task 1.11,
20. stop before Phase 2.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -12
git tag --list
```

Verify:

```text
Task 1.10 committed
working tree clean except intentional Task 1.11 prompt state
no Phase 2 implementation started
```

Verify actual Task 1.10 commit hash/message.

If unexplained changes exist:

**STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Required:

```text
doctor PASS
portable suite 0 failures
```

Do not make an OpenRouter call during portable tests.

---

# STEP 3 — READ CURRENT IMPLEMENTATION

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_RETRIEVER.md
project_plan/PHASE1_GENERATION.md
project_plan/PHASE1_CITATION_INTEGRITY.md
project_plan/PHASE1_SMOKE_EVALUATION.md
project_plan/PHASE1_BASELINE_METRICS.md
project_plan/TESTING.md
project_plan/DEVELOPER_COMMANDS.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/retrieval/baseline.py
src/generation/provider.py
src/generation/openrouter.py
src/generation/citations.py
src/generation/minimal.py
src/eval/citation_integrity.py
src/eval/baseline_metrics.py
src/cli/

scripts/smoke_generation.py
scripts/smoke_citation_integrity.py
scripts/run_baseline_metric.py

configs/citation_integrity_smoke.json
configs/phase_1_10_baseline_metric.json

results/phase_1_7a_citation_format_correction_rerun.json
results/phase_1_10_baseline_metric.json
```

Do not copy logic blindly.

Reuse existing boundaries.

---

# STEP 4 — VERIFY TASK 1.10 RESULT

Independently verify the tracked result still reports:

```text
question_count = 200
hit_count = 194
doc_recall_at_10 = 0.97
metric_result_sha256 =
64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

Verify Task 1.9 dataset hash still matches:

```text
0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27
```

If either changed:

**STOP AND ASK ME.**

Do not integrate against a silently changed baseline.

---

# STEP 5 — VERIFY GENERATION RUNTIME CONFIG

For the live answer-command smoke, expected Phase 1 baseline runtime is:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
OPENROUTER_API_KEY present
```

Read the key only from the already-established environment/.env boundary.

Never print it.

Never log it.

Never pass it as a CLI argument.

If provider/model differs from the Task 1.7a baseline:

**STOP AND ASK ME.**

Do not silently test Task 1.11 with another model.

---

# STEP 6 — CLI MODULE

Implement:

```text
src/cli/phase1.py
```

It should be executable via:

```bash
python -m src.cli.phase1 --help
```

Use:

```text
argparse
```

or the repository's existing stdlib CLI convention.

Do not add Typer/Click/Fire.

No dependency change should be needed.

---

# STEP 7 — CLI SUBCOMMANDS

Exactly these Phase 1 subcommands are required:

```text
answer
evaluate
```

Do not add a large command tree.

Help output should make both visible.

---

# STEP 8 — ANSWER ARGUMENT

Require:

```text
--question
```

Example:

```bash
python -m src.cli.phase1 answer --question "What risk factors does the company report?"
```

Reject:

```text
missing question
empty string
whitespace-only string
```

with a clear non-zero CLI error.

Do not read the question from a hardcoded file.

Do not build an interactive REPL.

---

# STEP 9 — ANSWER WIRING

The answer subcommand must use existing classes/functions.

Conceptually:

```text
load Settings
→ verify provider/model
→ open Task 1.5 index
→ load Task 1.4 BGE query model
→ construct BaselineRetriever
→ construct OpenRouterProvider
→ construct MinimalGenerator
→ MinimalGenerator.answer(question)
→ print answer
→ print citations
```

Do not copy `MinimalGenerator` logic into the CLI.

Do not copy BGE encoding logic.

Do not implement a second retriever.

---

# STEP 10 — RETRIEVAL K FOR ANSWER

Generation remains:

```text
top 5 chunks
```

Use Task 1.7's existing behavior.

Do not change answer generation to k=10 just because Task 1.10 evaluates
retrieval at 10.

The distinction is intentional:

```text
generation context k = 5
retrieval evaluation k = 10
```

Document it clearly.

---

# STEP 11 — ANSWER OUTPUT

Successful answer output must be human-readable.

Minimum:

```text
Answer:
<generated answer>

Citations:
- <chunk_id>
- <chunk_id>
```

For zero parsed citations:

```text
Citations:
(none)
```

Do not hide zero citations.

Do not print vectors.

Do not print the entire top-5 context.

Do not print the API key or authorization header.

---

# STEP 12 — DO NOT REPAIR ANSWER CITATIONS

If the model emits:

```text
【document.htm::chunk1】
```

or another malformed attempt, do not convert it.

The CLI must print the generated answer faithfully.

The parsed citation list remains Task 1.7's strict parser output.

Do not post-process the answer to manufacture valid citations.

---

# STEP 13 — ANSWER ERROR HANDLING

On:

```text
missing GENERATION_MODEL
missing OPENROUTER_API_KEY
unsupported GENERATION_PROVIDER
retriever failure
model-load failure
OpenRouter error
malformed provider response
```

print a concise safe error and exit non-zero.

Do not print secret-bearing raw exceptions.

Reuse existing `GenerationError` / provider error behavior where possible.

---

# STEP 14 — EVALUATE MUST REUSE TASK 1.10

The evaluate subcommand must NOT implement:

```text
hit logic
first_hit_rank logic
category aggregation
doc_recall@10 math
```

again.

There must be one metric implementation.

Inspect `scripts/run_baseline_metric.py`.

Use the smallest safe reuse approach.

Preferred order:

1. call an already-importable Task 1.10 runner function if it exists;
2. if needed, perform a narrow zero-semantic-change refactor so the
   existing script and new CLI call the same runner;
3. if the current script is intentionally CLI-only and refactoring would
   be material, delegate to it using `sys.executable` and an absolute
   repo-relative path.

If this choice is materially ambiguous after inspection:

**STOP AND ASK ME.**

Do not duplicate 200-question evaluation logic.

---

# STEP 15 — PRESERVE TASK 1.10 BASELINE ARTIFACT

Task 1.11 must not erase historical Task 1.10 evidence.

Preserve:

```text
results/phase_1_10_baseline_metric.json
```

If the existing Task 1.10 runner overwrites that tracked result every time,
prefer a narrow optional output-path mechanism with default behavior
unchanged, so Task 1.11 can write its integration rerun separately.

Preferred Task 1.11 integration result:

```text
results/phase_1_11_smoke_evaluation.json
```

If the existing runner already supports a safe output override, reuse it.

If adding an output override would require choosing a materially new public
contract:

**STOP AND ASK ME.**

Do not silently destroy the Task 1.10 baseline artifact.

---

# STEP 16 — EVALUATE OUTPUT

The command:

```bash
python -m src.cli.phase1 evaluate
```

must visibly print at least:

```text
question_count: 200
hit_count: 194
doc_recall@10: 0.970000
```

or the actual recomputed values if something legitimately changed.

However, because Task 1.10 established deterministic logical output,
anything other than the frozen logical result is an integration failure
until explained.

Do not hide the number behind logs.

---

# STEP 17 — EVALUATE RESULT VALIDATION

After the Task 1.11 evaluate run verify:

```text
question_count = 200
hit_count = 194
doc_recall@10 = 0.970000
metric_result_sha256 =
64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

Runtime/timestamps/latencies may differ.

Logical retrieval output must not.

If logical hash differs:

**STOP AND ASK ME.**

Do not average results.

Do not accept approximate equality in retrieved identities.

---

# STEP 18 — LIVE ANSWER DEMO QUESTION

Use exactly ONE paid live answer call for Task 1.11's end-to-end answer
demonstration.

Do not run another 10-case citation smoke.

Select the demo question deterministically from existing tracked evidence:

```text
1. read configs/citation_integrity_smoke.json
2. read results/phase_1_7a_citation_format_correction_rerun.json
3. consider only cases whose expected_behavior is "answer"
4. consider only cases that PASSed the historical Task 1.7a rerun
5. choose the lowest case_id
```

This selects a previously demonstrated ordinary answer case for the CLI
integration smoke without changing the question set or making repeated
paid calls.

Important:

```text
This is only a one-command integration demonstration.
It does NOT replace the Task 1.7a 8/10 compliance result.
```

Do not claim the selected demo proves general citation compliance.

---

# STEP 19 — NO RETRY / CHERRY-PICKING ON THE LIVE DEMO

Run the selected question exactly once through:

```bash
python -m src.cli.phase1 answer --question "<exact tracked question>"
```

If the model produces malformed citation formatting on this new run:

do NOT retry.

Do NOT switch to another historically passing case.

Do NOT edit the answer.

Record the real result.

This prevents Task 1.11 from manufacturing a successful Phase 1 exit demo
through repeated calls.

---

# STEP 20 — LIVE DEMO CITATION CHECK

For the exact live demo call, mechanically verify the official citation exit
criteria using the already-implemented Task 1.8 machinery.

Need to verify:

```text
at least one strict valid citation for this expected-answer demo
every cited chunk ID exists
every cited chunk ID was among the exact top-5 supplied to that same
generation call
no malformed citation attempt
```

Do not validate against a second retrieval if Task 1.8 already provides a
recording-retriever mechanism.

Reuse the same exact-context capture approach established in Task 1.8.

If the CLI implementation does not expose enough internals to perform this
check safely:

use the smallest test/instrumentation boundary that preserves the exact
same generation call.

Do not make a second OpenRouter call merely for validation.

If exact-context validation would require a material public-contract
change:

**STOP AND ASK ME.**

---

# STEP 21 — LIVE DEMO RESULT SEMANTICS

If the one live demo returns:

```text
non-empty answer
>=1 strict valid citation
all citations exist
all citations were supplied
no malformed citation attempt
```

then the command-level citation exit demonstration:

```text
PASS
```

If the command itself works but the model reproduces the known malformed
fullwidth-bracket behavior:

```text
Task 1.11 = WARN
Phase 1 exit citation criterion = NOT demonstrated on this run
```

Do not retry.

Do not close Phase 1 automatically.

Stop for user decision after committing truthful Task 1.11 integration
work.

If retrieval/provider/CLI infrastructure is broken:

```text
BLOCKED
```

---

# STEP 22 — PORTABLE CLI TESTS

Add focused tests, preferably:

```text
tests/test_phase1_cli.py
```

No real network in portable tests.

Use fake/injected dependencies where possible.

Test at minimum:

```text
--help exits 0 and lists answer/evaluate
answer requires --question
empty question rejected

answer path:
  retriever/generator wiring invoked correctly
  answer printed
  citations printed
  zero citations shown explicitly
  vectors/context not printed
  provider error becomes non-zero safe CLI failure

evaluate path:
  delegates to Task 1.10 runner
  does not duplicate metric computation
  prints question_count/hit_count/doc_recall@10
  propagates runner failure as non-zero

no API key appears in output/error text
```

If dependency injection requires a small internal helper function in
`src/cli/phase1.py`, that is acceptable.

Do not build a general dependency-injection framework.

---

# STEP 23 — NO NEW PAID PYTEST TEST

Do not add another ordinary pytest test that performs a live OpenRouter
call.

Task 1.11's paid answer smoke is the explicit manual/dedicated command run.

Portable and full pytest should not gain an additional surprise API bill
from this task.

Preserve existing `generation_api` marker behavior.

---

# STEP 24 — COMMAND CWD BEHAVIOR

Inspect the existing project convention.

If `python -m src.cli.phase1` is documented as repo-root invocation, that
is acceptable.

Do not invent package installation just to make it globally callable.

At minimum verify from repository root:

```bash
python -m src.cli.phase1 --help
```

works.

If current CLI/package conventions already require CWD independence,
follow them.

---

# STEP 25 — NO FASTAPI

Do not implement:

```text
FastAPI
HTTP endpoint
server
SSE
streaming
AWS
Docker
```

Phase 4 owns serving.

Task 1.11 is a local command only.

---

# STEP 26 — NO ADVANCED RETRIEVAL

Do not add:

```text
BM25
hybrid search
metadata filters
reranker
CRAG
router
tree retrieval
graph retrieval
SQL routing
```

The Phase 1 exit criterion explicitly requires no advanced retrieval added
prematurely.

The answer command must exercise the crude existing vector-only path.

---

# STEP 27 — NO GENERATION CHANGES

Do not alter:

```text
Task 1.7a prompt
citation parser
provider
model
temperature
top-5 generation context
abstention contract
```

Task 1.11 integrates the existing generator.

It does not tune it.

If a citation-format failure reappears:

record it.

Do not fix it inside Task 1.11.

---

# STEP 28 — NO EVAL CHANGES

Do not alter:

```text
Task 1.9 200-question dataset
target document labels
Task 1.10 doc_recall@10 semantics
k=10
metric result
```

The evaluate command integrates the frozen baseline.

It does not redesign the evaluation.

---

# STEP 29 — TASK 1.11 SUMMARY RESULT

Create:

```text
results/phase_1_11_end_to_end_summary.json
```

subject to actual repository naming conventions.

Include:

```text
schema_version

answer_command
evaluate_command

generation:
  provider
  requested_model
  demo_case_id
  demo_question
  answer_nonempty
  parsed_citations
  citation_integrity_status
  citation_failure_reasons if any
  retrieval_k = 5
  latency if readily available

evaluation:
  question_count
  hit_count
  doc_recall_at_10
  smoke_eval_sha256
  metric_run_config_hash
  metric_result_sha256
  matches_task_1_10

phase_1_exit_criteria:
  each official criterion
  PASS / WARN / FAIL
  concise evidence

known_warnings:
  Task 1.7a 8/10 citation-format compliance

created_at_utc
```

Do not store:

```text
OPENROUTER_API_KEY
authorization headers
full top-5 chunk text
raw provider response
vectors
```

---

# STEP 30 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_END_TO_END.md
```

Document:

## Commands

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

## Answer Path

```text
question
→ Task 1.6 vector retrieval, k=5
→ Task 1.7a generation
→ answer + strict parsed citations
```

## Evaluate Path

```text
Task 1.9 frozen 200 questions
→ Task 1.6 retrieval, k=10
→ Task 1.10 doc_recall@10
```

## Configuration

Answer command requires:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b for the frozen Phase 1 smoke
OPENROUTER_API_KEY in ignored .env/process environment
```

Explain provider/model remain architecturally replaceable.

Evaluate command requires no API key.

## Outputs

Show concise example formatting without inventing a metric result.

Use the actual metric after the real run.

## Known Warning

State prominently:

```text
Task 1.7a general citation-format compliance remains 8/10.
The one-command demo does not supersede that diagnostic.
```

## Non-Goals

No FastAPI, advanced retrieval, guardrails, or production deployment.

## Phase 1 Exit Review

List every official criterion and its evidence/status.

---

# STEP 31 — UPDATE DEVELOPER COMMANDS DOC

If consistent with current documentation conventions, add a small section
or cross-link in:

```text
project_plan/DEVELOPER_COMMANDS.md
```

for the two Phase 1 commands.

Do not turn `scripts/dev.py` into the user-facing RAG command unless the
repository already explicitly requires that.

Keep `dev.py` as foundation/developer tooling.

---

# STEP 32 — UPDATE REPOSITORY STRUCTURE

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly.

Mark:

```text
src/cli/phase1.py
```

implemented as the Phase 1 local CLI.

Do not claim FastAPI/production API is implemented.

---

# STEP 33 — RUN LOCAL CLI TESTS

Run:

```bash
python -m src.cli.phase1 --help
```

Verify:

```text
answer
evaluate
```

are visible.

Run portable unit tests before live generation.

---

# STEP 34 — RUN THE REAL EVALUATE COMMAND

Run:

```bash
python -m src.cli.phase1 evaluate
```

Required logical result:

```text
question_count: 200
hit_count: 194
doc_recall@10: 0.970000
metric_result_sha256:
64438c1c5ee0769763a274af8cafd200472116889cbd5ee4b045f37557907328
```

Confirm the result is saved under the intended Task 1.11 integration path
without destroying Task 1.10 history.

No OpenRouter call should occur.

---

# STEP 35 — RUN THE ONE LIVE ANSWER COMMAND

Determine the fixed demo question using Step 18.

Then run exactly once:

```bash
python -m src.cli.phase1 answer --question "<exact tracked demo question>"
```

Record:

```text
provider
model
answer non-empty
printed citations
citation integrity check
```

Never record the API key.

No retry.

---

# STEP 36 — PHASE 1 OFFICIAL EXIT REVIEW

After both commands run, evaluate each official criterion separately.

## Criterion 1

```text
One command accepts a question and returns an answer.
```

PASS only if the real answer command succeeds.

## Criterion 2

```text
The answer contains valid source citations.
```

PASS only if the one live expected-answer demo has >=1 strict valid
citation and no malformed citation attempt.

If the known fullwidth issue appears:

WARN/FAIL for this criterion.

## Criterion 3

```text
Every citation resolves back to a stored source chunk.
```

PASS only if all strict citations from the exact live demo resolve.

## Criterion 4

```text
A 200-question evaluation runs end to end.
```

PASS only if `python -m src.cli.phase1 evaluate` completes successfully.

## Criterion 5

```text
doc_recall@10 is printed and saved.
```

PASS only if the command visibly prints and saves:

```text
194 / 200 = 0.970000
```

with the expected logical hash.

## Criterion 6

```text
Integration bugs found during the vertical slice are documented.
```

PASS only if Progress/docs retain:

```text
Task 1.7 / 1.8 citation-format issue
Task 1.7a correction and residual 8/10 warning
any Task 1.11 integration bug found
```

## Criterion 7

```text
No advanced retrieval component added prematurely.
```

PASS only if Git diff confirms none was added.

---

# STEP 37 — PHASE 1 CLOSURE SEMANTICS

Use truthful statuses.

## If Task 1.11 answer demo citation check PASSES and evaluation matches

Task 1.11:

```text
PASS
```

Phase 1:

```text
COMPLETE WITH WARN
```

because the historical general citation compliance remains:

```text
8/10
```

even though the required one-command end-to-end demo succeeded.

Do not erase that warning.

## If the live answer command works but its citation check FAILS due the
known fullwidth-format issue

Task 1.11:

```text
WARN
```

Phase 1:

```text
NOT CLOSED — citation exit criterion not demonstrated on the final live run
```

Stop for my decision.

Do not retry or switch model.

## If evaluate differs from Task 1.10 logical result or infrastructure breaks

Task 1.11:

```text
BLOCKED
```

Investigate and stop.

---

# STEP 38 — DO NOT START PHASE 2

Even if Task 1.11 PASSes:

do NOT create:

```text
src/eval/truth_contract.py
configs/eval_tags.*
3,000-question dataset
DEV/TEST split
```

Do not begin Task 2.1.

The final response should stop and wait for approval.

---

# STEP 39 — TEST SUITES

After implementation and explicit integration commands:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required for implementation correctness:

```text
0 failures
```

Use actual test counts.

Remember:

```text
Task 1.11's one paid live answer command
```

is separate from portable pytest.

---

# STEP 40 — SAFETY / UPSTREAM IMMUTABILITY

Verify unchanged:

```text
Task 1.9 dataset
Task 1.10 baseline result
Task 1.6 retrieval semantics
Task 1.7a prompt/generation semantics
Task 1.8 citation validator semantics
Task 1.5 index
Task 1.4 embeddings
Task 1.3 chunks
Task 1.2 normalized Markdown
frozen data/
```

A narrow Task 1.10 runner refactor for reuse is acceptable only if its
metric semantics and prior command behavior remain identical.

---

# STEP 41 — SECRET SAFETY

Verify:

```bash
git check-ignore -v .env
```

Inspect `.env.example`.

It must contain placeholders only.

Run a secret scan across all staged candidates.

The real OpenRouter key must never appear in:

```text
CLI arguments
console output
results
docs
tests
Progress.md
Git diff
```

---

# STEP 42 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected tracked Task 1.11 files may include:

```text
src/cli/phase1.py
tests/test_phase1_cli.py
results/phase_1_11_end_to_end_summary.json
results/phase_1_11_smoke_evaluation.json
project_plan/PHASE1_END_TO_END.md
project_plan/DEVELOPER_COMMANDS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Possibly a narrowly refactored:

```text
scripts/run_baseline_metric.py
src/eval/baseline_metrics.py
```

only if required for reuse with zero metric-semantic change.

Do not stage:

```text
.env
data/
artifacts/
model cache
raw provider responses
large prompt/context dumps
```

---

# STEP 43 — UPDATE Progress.md

Preserve all history.

Append:

```markdown
## YYYY-MM-DD — Phase 1.11 End-to-End Command
```

Use actual local execution date.

Include:

## Objective

Explain this is the final Phase 1 integration/orchestration task.

## Initial State

Record:

```text
Task 1.10 commit
340-test baseline
Task 1.10 194/200 = 0.97
Task 1.7a 8/10 historical warning
```

## Commands

Record exactly:

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

## Answer Command

Record:

```text
retrieval k=5
provider/model
demo case ID
answer returned
printed citation IDs
citation-integrity result
```

Do not paste a long answer.

## Evaluate Command

Record:

```text
questions=200
hits=194
doc_recall@10=0.970000
metric_result_sha256
matches Task 1.10 = YES
```

## Tests

Record:

```text
new Task 1.11 tests
doctor
portable
full
```

## Phase 1 Exit Review

Include all 7 official criteria with explicit PASS/WARN/FAIL.

## Known Warning

Keep:

```text
Task 1.7a general citation-format compliance = 8/10
```

visible.

Do not claim the one live command erases this.

## Safety

Confirm:

```text
API key not logged/committed
no citation repair
no model switch
no advanced retrieval
no Task 1.9/1.10 semantic changes
no upstream artifact mutation
no Phase 2 work
```

## Files Created / Modified

List actual tracked files.

## Git

Record Task 1.11 commit.

## Result

Use exactly one:

```text
PASS — Phase 1 one-command answer and 200-question evaluation are integrated

WARN — integration commands work, but final live citation exit demonstration
did not pass; Phase 1 not closed pending user decision

BLOCKED — Phase 1 integration command could not be established safely
```

## Phase Status

If Task 1.11 PASSes:

```text
Phase 1 — Make It Work End to End — COMPLETE WITH WARN
  ...
  1.11 End-to-End Command        — COMPLETE

Known Phase 1 warning:
Task 1.7a citation-format compliance remains 8/10.
```

If WARN:

```text
Phase 1 — Make It Work End to End — NOT CLOSED
  1.11 End-to-End Command        — COMPLETE WITH WARN

Blocking exit criterion:
final live answer citation integrity not demonstrated
```

Do not start Phase 2.

---

# STEP 44 — COMMIT TASK 1.11

After:

```text
CLI implemented
portable/full tests pass
evaluate command reproduces Task 1.10
one live answer command executed exactly once
citation result recorded truthfully
Phase 1 exit review completed
secret scan clean
Progress.md updated
```

create one coherent Task 1.11 commit.

Preferred message:

```text
Add Phase 1 end-to-end commands
```

or concise equivalent consistent with `GIT_CONVENTIONS.md`.

Do not include Phase 2 work.

Do not amend Task 1.10 history.

---

# STEP 45 — PHASE TAG

Do NOT create a Phase 1 tag automatically unless BOTH are true:

```text
1. repository Git conventions explicitly require the tag at this exact
   phase-exit point
2. Task 1.11's live citation exit demonstration passed
```

If tagging semantics are ambiguous because Phase 1 is COMPLETE WITH WARN:

**STOP AND ASK ME.**

Do not invent or force a tag.

---

# STEP 46 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

Do not invent one.

If push authorization is ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.11 is complete only if:

```text
[ ] Task 1.10 commit verified
[ ] Task 1.10 baseline result/hash verified
[ ] Task 1.7a 8/10 warning preserved truthfully

[ ] src/cli/phase1.py implemented
[ ] python -m src.cli.phase1 --help works
[ ] answer subcommand documented
[ ] evaluate subcommand documented

[ ] answer requires --question
[ ] answer rejects empty question
[ ] answer uses Task 1.6 retriever
[ ] answer uses generation k=5
[ ] answer uses Task 1.7a MinimalGenerator
[ ] answer uses existing OpenRouter provider
[ ] answer prints non-empty answer
[ ] answer prints parsed citations clearly
[ ] answer does not print vectors/context/API key
[ ] no citation normalization/repair

[ ] evaluate reuses Task 1.10 metric runner
[ ] metric logic not duplicated
[ ] Task 1.9 dataset unchanged
[ ] Task 1.10 metric semantics unchanged
[ ] Task 1.10 historical result preserved

[ ] real evaluate command run
[ ] question_count = 200
[ ] hit_count = 194
[ ] doc_recall@10 = 0.970000
[ ] metric_result_sha256 matches Task 1.10
[ ] metric printed
[ ] metric saved

[ ] exactly one real paid answer demo call
[ ] demo question selected deterministically from tracked prior PASS evidence
[ ] no retry/cherry-picking
[ ] live answer citation integrity checked against exact supplied top-5
[ ] every strict citation resolves to stored chunk
[ ] every strict citation was supplied
[ ] malformed attempt recorded truthfully if it occurs

[ ] portable CLI tests added
[ ] no additional paid live pytest added
[ ] doctor passes
[ ] portable suite 0 failures
[ ] full suite 0 failures

[ ] official Phase 1 exit criteria evaluated one by one
[ ] integration bugs documented
[ ] no advanced retrieval added
[ ] Task 1.7a warning not erased

[ ] no FastAPI
[ ] no router
[ ] no BM25
[ ] no reranker
[ ] no CRAG
[ ] no guardrail framework
[ ] no Phase 2 truth contract

[ ] API key absent from staged/tracked output
[ ] upstream artifacts unchanged

[ ] PHASE1_END_TO_END.md created
[ ] REPOSITORY_STRUCTURE.md updated narrowly
[ ] Progress.md updated

[ ] one coherent Task 1.11 commit created
[ ] no Phase 2 work committed
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.10 result/hash differs

Task 1.9 dataset hash differs

configured provider/model differs from Task 1.7a baseline

the CLI location conflicts with an already-frozen repository convention

reusing Task 1.10 requires a material metric refactor

preserving Task 1.10 result history requires a new durable artifact
convention that is not already established

you are considering changing the generator prompt/model/provider

you are considering normalizing fullwidth citations

you are considering retries to make the live answer pass

you are considering choosing a second demo question after a failed live run

you are considering changing retrieval to improve the metric

the evaluate command does not reproduce Task 1.10 logical output

Phase 1 tag semantics are ambiguous under COMPLETE WITH WARN

repository docs materially conflict

Git push authorization is unclear

any other durable implementation decision would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.11 does NOT:

```text
fix the residual Task 1.7a citation-format issue
switch OpenRouter model
change generation prompt
repair citations
run another 10-case citation ablation
change the 200-question eval
change doc_recall@10
improve retrieval
add BM25
add hybrid retrieval
add metadata filters
add reranking
add CRAG
add router
add tree navigation
add SQL/XBRL routing
add graph retrieval
add FastAPI
add guardrails
deploy anything
start Phase 2
```

The desired final Phase 1 integration is only:

```text
COMMAND 1

python -m src.cli.phase1 answer --question "..."

question
→ vector retrieval k=5
→ grounded generation
→ answer
→ citations printed


COMMAND 2

python -m src.cli.phase1 evaluate

200 frozen questions
→ vector retrieval k=10
→ doc target membership
→ 194 hits / 200
→ doc_recall@10 = 0.970000
→ printed + saved
```

---

# FINAL RESPONSE TO ME

After completing Task 1.11, return:

## Task

```text
task_1.11_end_to_end_command.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Task 1.10 Baseline

Report:

```text
Task 1.10 commit
questions = 200
hits = 194
doc_recall@10 = 0.970000
metric_result_sha256
```

## Commands

Report exactly:

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

## Answer Command

Report:

```text
demo case ID
provider
requested model
retrieval k
answer non-empty YES/NO
parsed citations
citation integrity PASS/WARN/FAIL
```

Do not paste the API key or a long answer.

## Citation Verification

Report for the same exact live call:

```text
malformed attempts
valid citation count
all cited IDs exist YES/NO
all cited IDs were supplied YES/NO
```

## Evaluate Command

Report:

```text
question_count
hit_count
doc_recall@10
metric_result_sha256
matches Task 1.10 YES/NO
result path
```

## Official Phase 1 Exit Review

Report every criterion:

```text
1. one command accepts question + returns answer
2. answer contains valid source citations
3. every citation resolves to stored source chunk
4. 200-question evaluation runs end to end
5. doc_recall@10 printed + saved
6. integration bugs documented
7. no advanced retrieval added
```

Use PASS/WARN/FAIL per criterion.

## Existing Warning

Confirm:

```text
Task 1.7a general citation-format compliance remains 8/10.
The one-command demo does not supersede that result.
```

## Tests

Report:

```text
new Task 1.11 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
```

## Safety

Confirm:

```text
API key not logged/committed
no citation repair
no model/provider switch
no retrieval changes
Task 1.9 dataset unchanged
Task 1.10 semantics/result history preserved
upstream artifacts unchanged
no Phase 2 work
```

## Files Modified

List actual tracked/project files only.

## Git

Report:

```text
commit created YES/NO
commit hash
commit message
remote status
push performed YES/NO
tag created YES/NO
```

## Progress.md

Confirm the entry:

```text
## YYYY-MM-DD — Phase 1.11 End-to-End Command
```

was appended.

## Phase 1 Status

If the live answer citation exit check PASSED and evaluation matched:

```text
Phase 1 — COMPLETE WITH WARN
Known warning: Task 1.7a citation-format compliance remains 8/10.
```

If the live answer citation check failed:

```text
Phase 1 — NOT CLOSED
Reason: final live citation exit criterion was not demonstrated.
```

## Next

Do not begin Phase 2.

Finally state:

```text
No Phase 2 work started.
```

Stop and wait for my approval.
