# Task 1.7a — Correct Citation Format Compliance

You are working inside my SEC RAG repository.

Task file:

`task_1.7a_correct_citation_format_compliance.md`

We are executing a narrow corrective task between the completed Task 1.8
citation-integrity smoke and Task 1.9's ~200-question smoke evaluation.

Current status:

```text
Data Preparation                   — COMPLETE
Phase 0 — Foundation               — COMPLETE
Phase 1 — Make It Work End to End  — IN PROGRESS
  1.1 Select Development Corpus    — COMPLETE
  1.2 Minimal Normalization        — COMPLETE
  1.3 Minimal Fixed-Window Chunker — COMPLETE
  1.4 Baseline Embedding Pipeline  — COMPLETE
  1.5 Vector-Only Index            — COMPLETE
  1.6 Baseline Retriever           — COMPLETE
  1.7 Minimal Generation Layer     — COMPLETE
  1.8 Citation Integrity Smoke     — COMPLETE WITH WARN
  1.7a Citation Format Correction  — CURRENT
  1.9 200-Question Smoke Eval      — BLOCKED PENDING THIS CORRECTION
```

This task is numbered `1.7a` because the defect belongs to Task 1.7's
generation-output contract, even though Task 1.8 discovered and measured it.

Do NOT rewrite Task 1.7 or Task 1.8 history.
Do NOT begin Task 1.9.

---

# WHY THIS CORRECTIVE TASK EXISTS

Task 1.8's integrity checker is working correctly.

Recorded live Task 1.8 result:

```text
provider:             OpenRouter
requested model:      openai/gpt-oss-20b
live cases:           10
ordinary cases:       8
abstention controls:  2

citation-integrity PASS: 3/10
citation-integrity FAIL: 7/10
```

All seven failures were citation-output compliance failures:

```text
6 cases used fullwidth brackets such as:
【1158114_2016.htm::chunk106】

1 case used a truncated citation such as:
[chunk63]

one case compounded both behaviors
```

Critically:

```text
unknown_chunk_id failures:        0
citation_not_in_supplied_context: 0
```

Every syntactically valid citation that was produced referred to a real
chunk that was actually supplied to the generation call.

Therefore the current evidence points narrowly to generation
citation-format compliance rather than retrieval corruption, context
leakage, hallucinated chunk IDs, out-of-context citations, or index
identity failure.

Task 1.8's implementation has 286/286 tests passing and MUST NOT be
weakened to manufacture a green result.

---

# USER-APPROVED CORRECTION STRATEGY — FROZEN

## 1. Prompt-only correction first

Change only the Task 1.7 generation prompt/instructions needed to improve
citation-format compliance.

Do NOT switch generation models during this task.
Do NOT switch providers.
Do NOT normalize malformed citations after generation.
Do NOT modify the Task 1.8 validator to accept forms that currently fail.

The purpose is to change one variable:

```text
citation-format instructions in the generation prompt
```

and then rerun the exact same Task 1.8 smoke.

## 2. Keep the same generation provider/model configuration

Use the existing runtime configuration.

Expected current testing setup:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
```

The model remains runtime-configurable in architecture.

Do NOT permanently hardcode `openai/gpt-oss-20b` into source code.

If the local runtime model has changed unexpectedly from the model used in
Task 1.8:

**STOP AND ASK ME** before rerunning the comparison.

We want a same-model before/after prompt comparison.

## 3. Keep the Task 1.8 validator unchanged

The existing rules remain authoritative:

```text
fullwidth 【...】 citation attempt               -> FAIL
truncated [chunk63] citation attempt            -> FAIL
unknown exact chunk ID                         -> FAIL
real but unsupplied chunk ID                   -> FAIL
non-abstaining answer with zero valid citation -> FAIL
legitimate abstention with zero citation       -> allowed
```

Do NOT convert `【】` to `[]`.
Do NOT expand `[chunk63]`.
Do NOT fuzzy-match or repair IDs.

## 4. Rerun the exact same 10 Task 1.8 cases

Use the existing tracked Task 1.8 question/config set unchanged.

Exactly:

```text
10 cases
8 ordinary answer cases
2 abstention controls
```

Do NOT substitute easier questions.
Do NOT rewrite questions.
Do NOT create a new smoke population.

## 5. PASS threshold

To unblock Task 1.9:

```text
10/10 Task 1.8 citation-integrity cases must PASS
```

If the rerun is:

```text
10/10 -> PASS and Task 1.9 may become NEXT
<10/10 -> WARN
```

If fewer than 10 cases pass:

- record the exact residual failures,
- do not weaken the validator,
- do not silently switch model,
- do not begin Task 1.9,
- stop and ask me whether to try a different OpenRouter model or another
  explicitly approved correction.

---

# CRITICAL RULE — DO NOT ASSUME

If an implementation decision is not clearly resolved by:

1. the actual repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_GENERATION.md`,
4. `project_plan/PHASE1_CITATION_INTEGRITY.md`,
5. current Task 1.7 code/tests,
6. current Task 1.8 code/tests/config/results,
7. current runtime generation configuration,

then:

**STOP AND ASK ME.**

Do not silently choose a different model/provider, new parser, new
validator, response repair, retries, structured output, new smoke set,
semantic grader, timeout, or generation parameter.

When asking:
- state exactly what is ambiguous,
- state what repository evidence you found,
- present the smallest useful options,
- explain downstream impact,
- wait for my answer.

Inspection first. Assumption never.

---

# AUTHORITATIVE SCOPE

The only intended production-code behavioral change in this task is the
Task 1.7 prompt's citation-format instruction.

Conceptually:

```text
BEFORE
question
→ top-5 retrieval
→ grounded prompt
→ same model sometimes emits 【...】 or [chunk63]
→ strict validator correctly fails

AFTER
question
→ same top-5 retrieval
→ minimally corrected grounded prompt
→ same provider/model/settings
→ exact ASCII [chunk_id] requirement
→ same strict validator
```

Do not redesign the pipeline.

---

# PRIMARY OBJECTIVES

1. Verify Task 1.8 is committed and its WARN result is current.
2. Verify the exact 10-case Task 1.8 config/result.
3. Verify the current Task 1.7 prompt implementation.
4. Make the smallest prompt-only citation-format correction.
5. Add focused prompt-regression tests.
6. Keep the citation parser unchanged.
7. Keep the Task 1.8 validator unchanged.
8. Keep provider/model/settings unchanged.
9. Rerun the exact same 10-case Task 1.8 smoke.
10. Require 10/10 PASS to unblock Task 1.9.
11. Record before/after comparison truthfully.
12. Update documentation and `Progress.md`.
13. Create one coherent corrective Git commit.
14. Stop before Task 1.9.

---

# STEP 1 — VERIFY GIT STATE

Run:

```bash
git status --short
git branch --show-current
git log --oneline --decorate -10
git tag --list
```

Verify:
- Task 1.8 commit exists.
- Task 1.8 commit message is `Add citation integrity smoke check`.
- working tree is clean except intentional Task 1.7a prompt state.
- Task 1.9 implementation is absent.

If unexplained changes exist: **STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv`.

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Required: zero failures.

Do not make a live OpenRouter request during the portable suite.

---

# STEP 3 — READ CURRENT CONTRACTS

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_GENERATION.md
project_plan/PHASE1_CITATION_INTEGRITY.md
project_plan/PHASE1_RETRIEVER.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/generation/minimal.py
src/generation/citations.py
src/generation/provider.py
src/generation/openrouter.py
src/eval/citation_integrity.py
scripts/smoke_generation.py
scripts/smoke_citation_integrity.py
configs/citation_integrity_smoke.json
results/phase_1_7_generation_summary.json
results/phase_1_8_citation_integrity_summary.json
tests/test_minimal_generation.py
tests/test_citation_integrity.py
tests/test_openrouter_provider.py
```

Use actual code/interfaces.

---

# STEP 4 — REPRODUCE TASK 1.8 BASELINE

Before modifying the prompt, read the tracked Task 1.8 result and record
the exact baseline.

Expected current values:

```text
10 total
3 passed
7 failed
7 cases with malformed attempts
0 unknown-ID cases
0 out-of-context-ID cases
```

Do not trust this prompt over the actual result JSON.

If the tracked result materially differs: **STOP AND ASK ME.**

---

# STEP 5 — FREEZE THE SMOKE SET

Read:

```text
configs/citation_integrity_smoke.json
```

Verify:
- 10 case IDs,
- exact question texts,
- exact expected-behavior fields,
- 8 answer cases,
- 2 abstention controls.

Record a checksum or other deterministic before-state if current repo
conventions support it.

The corrective rerun must use this same file unchanged.

If this config changes during Task 1.7a, FAIL the task.

---

# STEP 6 — VERIFY CURRENT PROVIDER/MODEL WITHOUT PRINTING SECRETS

Expected:

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
OPENROUTER_API_KEY present
```

Never print or log the key.

If provider/model differs from Task 1.8: **STOP AND ASK ME.**

---

# STEP 7 — LOCATE THE CURRENT PROMPT

Inspect the Task 1.7 prompt construction in `src/generation/minimal.py`
or its actual location.

Confirm the existing contract:
- use only supplied context,
- no outside knowledge,
- cite exact chunk IDs,
- do not invent citations,
- abstain if unsupported.

Task 1.7 already removed context labels like:

```text
[chunk_id: X]
```

in favor of non-bracket labels such as:

```text
Chunk ID: X
```

Do NOT reverse that fix.

---

# STEP 8 — MAKE THE SMALLEST PROMPT-ONLY CORRECTION

The corrected citation instruction must explicitly state:

```text
1. Citation markers MUST use ASCII "[" and "]".
2. Never use Unicode/fullwidth "【" or "】".
3. Copy the COMPLETE Chunk ID exactly as supplied in context.
4. Never abbreviate a chunk ID to "[chunk63]" or similar.
5. Put nothing except the exact Chunk ID inside citation brackets.
6. The only valid form is:
   [<exact supplied Chunk ID>]
```

Include one valid FORMAT example and invalid examples.

For example:

```text
VALID FORMAT EXAMPLE:
[1158114_2016.htm::chunk106]

INVALID:
【1158114_2016.htm::chunk106】
[chunk106]
[chunk_id: 1158114_2016.htm::chunk106]
```

Make clear the example is formatting-only and the real answer may cite
only IDs present in the current supplied context.

---

# STEP 9 — FINAL FORMAT CONSTRAINT, NOT REPAIR

It is acceptable to instruct:

```text
Before returning the answer, ensure every citation uses ASCII square
brackets and contains an exact, complete Chunk ID copied from supplied
context.
```

Do not request chain-of-thought.
Do not ask the model to reveal internal checking.
Do not add a second provider call.
Do not post-process malformed output.

---

# STEP 10 — PRESERVE ALL OTHER PROMPT SEMANTICS

Do not change:
- grounding,
- no-outside-knowledge rule,
- abstention,
- top-5 context,
- answer style except what is necessary for citation syntax.

Keep the prompt minimal.

---

# STEP 11 — NO PARSER CHANGE

Do NOT modify runtime behavior in:

```text
src/generation/citations.py
```

If a parser change seems necessary: **STOP AND ASK ME.**

---

# STEP 12 — NO VALIDATOR CHANGE

Do NOT weaken or normalize behavior in:

```text
src/eval/citation_integrity.py
```

No fullwidth conversion.
No fuzzy matching.
No truncated-ID repair.
No model-specific exception.

This must remain the same measuring instrument.

---

# STEP 13 — NO MODEL/PROVIDER/GENERATION-PARAMETER ABLATION

Keep the same:
- provider,
- model,
- temperature,
- stream behavior,
- max-token behavior,
- provider routing,
- retrieval.

Expected current deterministic settings:

```text
temperature = 0.0
stream = false
```

If actual Task 1.8 settings differ, preserve actual settings.

If any generation parameter must change: **STOP AND ASK ME.**

---

# STEP 14 — PROMPT REGRESSION TESTS

Add/update focused unit tests verifying the prompt includes:
- ASCII brackets required,
- fullwidth brackets forbidden,
- complete exact Chunk ID required,
- `[chunkN]` abbreviation forbidden,
- extra prefix/content inside brackets forbidden,
- valid example,
- invalid examples,
- only supplied IDs allowed,
- grounding rule retained,
- abstention rule retained.

Use fake provider/retriever components.
No network.

Also verify context labels remain non-bracketed.

---

# STEP 15 — ONE PROVIDER CALL PER ANSWER

Preserve:

```text
1 retrieval
1 provider request
```

No retries.
No repair call.
No LLM judge.

---

# STEP 16 — RUN TARGETED TESTS FIRST

Run focused tests before any paid/live request, e.g.:

```bash
python -m pytest tests/test_minimal_generation.py -q
python -m pytest tests/test_citation_integrity.py -q
python -m pytest tests/test_openrouter_provider.py -q
```

Use actual filenames.

Required: zero failures.

---

# STEP 17 — VERIFY THE MEASURING INSTRUMENT IS UNCHANGED

Before live rerun inspect:

```bash
git diff -- src/generation
git diff -- src/eval
git diff -- configs/citation_integrity_smoke.json
```

Expected behavioral diff:
- generation prompt only.

Expected no behavioral changes:
- citation parser,
- citation-integrity validator,
- smoke questions/config.

If broader: investigate before proceeding.

---

# STEP 18 — RERUN THE EXACT SAME TASK 1.8 SMOKE

Run the existing Task 1.8 smoke command:

```bash
python scripts/smoke_citation_integrity.py
```

or the actual documented equivalent.

Requirements:

```text
same 10 case IDs
same 10 question texts
same expected behavior
same 8/2 composition
same retriever
same provider
same model
same generation settings
same validator
one generation per case
```

No retries.
No cherry-picking.
No replacement outputs.

---

# STEP 19 — REQUIRED PASS THRESHOLD

Task 1.7a PASS requires:

```text
10/10 citation-integrity PASS
```

For PASS:

```text
malformed-attempt cases = 0
unknown-ID cases = 0
out-of-context-ID cases = 0
missing-required-citation cases = 0
```

Abstention controls may have zero citations under the unchanged Task 1.8
contract.

---

# STEP 20 — IF 10/10 PASSES

If 10/10:
- Task 1.7a = PASS.
- Preserve Task 1.8's historical WARN.
- Record a separate post-correction result.
- Mark the citation-format warning resolved by prompt-only correction.
- Task 1.9 may become NEXT.
- Do NOT start Task 1.9.

---

# STEP 21 — IF FEWER THAN 10/10 PASSES

If 0–9/10:
- Task 1.7a = WARN.
- Record exact failures.
- Task 1.9 remains pending user decision.
- STOP.

Do not:
- make another prompt revision in the same task,
- switch model,
- switch provider,
- normalize citations,
- modify validator,
- retry failures.

Wait for my decision.

---

# STEP 22 — BEFORE/AFTER RESULT

Create a small tracked summary, preferably:

```text
results/phase_1_7a_citation_format_correction_summary.json
```

subject to repo conventions.

Include:

```text
baseline:
  source result path
  total
  passed
  failed
  malformed
  unknown
  out_of_context
  missing_required

correction:
  type = prompt_only
  provider
  requested_model
  generation settings
  unchanged smoke config path

rerun:
  total
  passed
  failed
  malformed
  unknown
  out_of_context
  missing_required

resolved
created_at_utc
```

No API key.
No large prompt/context dump.

Use actual baseline values from the tracked Task 1.8 result.

---

# STEP 23 — PRESERVE HISTORICAL TASK 1.8 EVIDENCE

Do NOT erase the original Task 1.8 3/10 evidence.

If rerunning the existing smoke command would overwrite:

```text
results/phase_1_8_citation_integrity_summary.json
```

inspect current artifact conventions.

Prefer:
- a separate output path for the corrective rerun, or
- a truthful preserved baseline artifact before rerunning.

If preserving history requires choosing a new durable artifact convention
not already established: **STOP AND ASK ME.**

Do not silently overwrite history.

---

# STEP 24 — DOCUMENTATION

Update `project_plan/PHASE1_GENERATION.md` with a narrow correction note:

```text
Task 1.8 found citation-format compliance failures.
No unknown/out-of-context citation failures were observed.
Task 1.7a changed only citation-format instructions.
Parser/validator/provider/model/settings stayed unchanged.
```

Document the new requirements:
- ASCII `[]` only,
- exact full supplied ID,
- no `【】`,
- no truncation,
- no extra label text inside brackets.

Optionally append a historical note to
`project_plan/PHASE1_CITATION_INTEGRITY.md`:

```text
original Task 1.8 baseline: 3/10
post-correction rerun: X/10
```

Do not rewrite Task 1.8 as if it originally passed.

---

# STEP 25 — TEST SUITES

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required: zero failures.

Use actual counts.

Keep separate:
- pytest implementation correctness,
- live 10-case citation compliance.

---

# STEP 26 — SAFETY

Confirm unchanged:
- Task 1.5 index,
- Task 1.4 embeddings,
- Task 1.3 chunks,
- Task 1.2 normalized Markdown,
- frozen data,
- Task 1.6 retrieval behavior.

Prompt-only means prompt-only.

Reconfirm:

```bash
git check-ignore -v .env
```

Inspect `.env.example` and ensure placeholders only.

Run secret scan over staged candidates.

---

# STEP 27 — UPDATE Progress.md

Preserve all prior history.

Append:

```markdown
## YYYY-MM-DD — Phase 1.7a Citation Format Compliance Correction
```

Use actual execution date.

Include:

### Objective
Prompt-only correction prompted by Task 1.8's 3/10 live result.

### Baseline
Record exact 10-case Task 1.8 counts.

### Root-Cause Evidence
Record observed fullwidth/truncated behavior and the zero unknown/out-of-
context counts.

### Frozen Strategy

```text
prompt-only
same provider
same model
same generation settings
same 10 questions
same validator
no normalization/repair
10/10 required to unblock Task 1.9
```

### Prompt Change
Precisely describe the citation-format instruction change.

### Tests
Record focused, doctor, portable, full.

### Live Rerun
Record all citation-integrity counts.

### Before / After

```text
before: 3/10
after:  X/10
```

### Safety
Confirm parser, validator, questions, model, provider, retrieval, upstream
artifacts unchanged and API key absent from tracked/logged files.

### Result

Use exactly one:

```text
PASS — prompt-only citation-format correction achieved 10/10 on the
unchanged Task 1.8 smoke

WARN — prompt-only correction did not achieve 10/10; Task 1.9 remains
pending user decision

BLOCKED — controlled prompt-only comparison could not be executed safely
```

If PASS:

```text
1.7 Minimal Generation Layer               — COMPLETE
1.8 Citation Integrity Smoke               — COMPLETE WITH HISTORICAL WARN
1.7a Citation Format Compliance Correction — COMPLETE
1.9 200-Question Smoke Eval                — NEXT
```

If WARN:

```text
1.7a Citation Format Compliance Correction — COMPLETE WITH WARN
1.9 200-Question Smoke Eval                — PENDING USER DECISION
```

---

# STEP 28 — LIKELY TRACKED FILES

Likely modifications:

```text
src/generation/minimal.py
tests/test_minimal_generation.py
results/phase_1_7a_citation_format_correction_summary.json
project_plan/PHASE1_GENERATION.md
project_plan/PHASE1_CITATION_INTEGRITY.md (optional historical note)
Progress.md
```

A tiny smoke-script output-path enhancement is allowed only if needed to
preserve the historical Task 1.8 result and if it does not change validator
semantics.

If artifact-history handling is ambiguous: **STOP AND ASK ME.**

---

# STEP 29 — COMMIT

After:
- prompt correction complete,
- focused/full tests pass,
- same 10-case rerun complete,
- historical Task 1.8 baseline preserved,
- result recorded truthfully,
- secret scan clean,
- Progress updated,

create one coherent corrective commit.

Preferred message:

```text
Tighten generation citation format
```

Do not amend/squash Task 1.8.
Do not include Task 1.9.

---

# STEP 30 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

If authorization is unclear: **STOP AND ASK ME.**
Never force-push.

---

# ACCEPTANCE CRITERIA

```text
[ ] Task 1.8 commit/result verified
[ ] original Task 1.8 3/10 baseline preserved
[ ] exact 10-case question set unchanged

[ ] provider unchanged
[ ] model unchanged
[ ] generation settings unchanged
[ ] retrieval unchanged
[ ] parser unchanged
[ ] validator unchanged

[ ] ASCII [ ] explicitly required
[ ] fullwidth 【 】 explicitly forbidden
[ ] complete supplied Chunk ID required
[ ] [chunkN] abbreviation forbidden
[ ] extra text inside brackets forbidden
[ ] valid and invalid examples present
[ ] grounding/abstention rules preserved

[ ] prompt regression tests added/updated
[ ] context labels remain non-bracketed
[ ] one provider call per answer
[ ] no repair/retry loop

[ ] same 10 live cases rerun
[ ] 8 answer + 2 abstention controls
[ ] no failed case retried/replaced

[ ] before/after recorded
[ ] malformed/unknown/out-of-context/missing counts recorded

[ ] PASS only if 10/10
[ ] if <10/10, WARN and stop before Task 1.9
[ ] no validator weakening
[ ] no model switch without approval

[ ] doctor passes
[ ] portable suite zero failures
[ ] full suite zero failures

[ ] .env ignored
[ ] .env.example placeholders only
[ ] API key absent from tracked/logged files

[ ] upstream artifacts unchanged
[ ] Task 1.8 historical WARN preserved
[ ] Progress.md updated
[ ] one corrective commit created
[ ] no Task 1.9 work
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME if:

```text
configured provider/model differs from Task 1.8
Task 1.8 smoke questions changed
historical result preservation requires a new unresolved artifact convention
prompt-only rerun is <10/10 and you are considering another correction
you are considering model/provider switch
you are considering normalizing 【】
you are considering expanding [chunk63]
you are considering parser/validator changes
you are considering retries/repair/second LLM call
a new dependency appears necessary
repo docs materially conflict
Git push authorization is unclear
any durable choice would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.7a does NOT:
- change retrieval,
- change embeddings/index/chunking/normalization,
- change provider/model,
- compare models,
- change generation settings,
- change parser/validator,
- normalize/repair malformed citations,
- retry generations,
- use an LLM judge,
- score semantic support,
- change the 10 Task 1.8 questions,
- build Task 1.9,
- calculate doc_recall@10,
- implement FastAPI.

The controlled experiment is:

```text
same questions
same retriever
same context behavior
same provider
same model
same settings
same validator

ONLY CHANGE:
citation-format prompt instruction
```

Then measure:

```text
before: 3/10
after:  X/10
```

---

# FINAL RESPONSE TO ME

After completing Task 1.7a, return:

## Task

```text
task_1.7a_correct_citation_format_compliance.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Baseline
Report total/passed/failed and malformed/unknown/out-of-context/missing
counts.

## Controlled Variables
Confirm provider, model, generation settings, smoke questions, retrieval,
parser, and validator were unchanged.

## Prompt Change
Give a concise before/after description.

## Tests
Report focused tests, doctor, portable, and full suite counts.

## Live Rerun
Report provider/model, 10 total, 8 answer, 2 abstention, pass/fail and all
integrity failure counts.

## Before / After

```text
before = 3/10
after  = X/10
```

## Resolution

If 10/10:

```text
Phase 1 citation-format compliance warning resolved by prompt-only
correction.
```

If <10/10:

```text
Prompt-only correction did not fully resolve citation-format compliance.
Task 1.9 remains pending user decision.
```

## Safety
Confirm no normalization/repair, no model switch, API key not logged/
committed, Task 1.8 baseline preserved, upstream artifacts unchanged.

## Files Modified
List actual tracked files only.

## Git
Report commit created, hash, message, remote, push status.

## Progress.md
Confirm the Phase 1.7a entry was appended.

## Next Task

If and only if rerun is 10/10:

```text
task_1.9_200_question_smoke_evaluation.md
```

Do not start it.

If fewer than 10/10:

```text
No Task 1.9 work started. Waiting for user decision on the next correction.
```

Stop and wait for my approval.
