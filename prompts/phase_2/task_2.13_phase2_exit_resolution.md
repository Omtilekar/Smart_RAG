# Task 2.13 — Phase 2 Exit Resolution After Cross-Model Agreement

## Objective

Resolve Phase 2 honestly after the user-approved Task 2.13 methodology change.

The cross-model agreement study is COMPLETE. The original human-calibration requirement was NOT performed and must not be retroactively claimed as satisfied.

This task is a Phase 2 closure / roadmap-reconciliation task only.

Do NOT start Phase 3 implementation.

---

## Authoritative current facts

Before changing anything, re-read the current repository state from:

- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PHASE2_LLM_JUDGE_VALIDATION.md`
- `Progress.md`
- `results/phase_2_13_cross_model_agreement.json`
- `results/phase_2_13_llm_judge_validation.json` if still present
- Phase 2 result/config files from Tasks 2.1–2.12
- `project_plan/GIT_CONVENTIONS.md`

The completed Task 2.13 cross-model study currently records:

- cases: 100 / 100
- primary judge: `qwen3.5:9b`
- comparator: `gpt-oss:20b`
- exact agreement: 88 / 100 = 88.0%
- Cohen's kappa: 0.737
- Qwen repeatability: 100.0%
- GPT-OSS repeatability: 95.0%
- structured-output success: 100.0% for both models
- fixture checks: 3/3 for both models
- human validation performed: NO
- human-validated judge: NO
- paid API calls: 0
- protected SEC TEST opened: NO
- official SEC TEST runs: 0/3

The original `PROJECT_EXECUTION.md` Task 2.13 requirement called for blinded human labels. The user explicitly replaced that methodology with a cross-model agreement study.

This replacement must be represented as an explicit roadmap amendment, not as a claim that human validation happened.

---

## Stage 1 — Repository preflight

Print:

`[STAGE 1/6] Repository preflight`

Verify:

1. Current branch and Git status.
2. Cross-model result artifact exists.
3. Recompute/verify the study result identity/hash if the artifact stores one.
4. Verify all 100 Qwen judgments exist.
5. Verify all 100 GPT-OSS judgments exist.
6. Verify repeatability artifacts are complete.
7. Verify:
   - human validation performed = false
   - human validated judge = false
8. Verify protected SEC TEST is still unopened.
9. Verify official TEST run budget remains 0/3.
10. Verify no paid OpenRouter/OpenAI/Anthropic judge calls were used for Task 2.13.

If the cross-model study is incomplete or inconsistent, STOP.

Do NOT rerun the 100-case study merely to refresh timestamps.

---

## Stage 2 — Re-read the exact Phase 2 exit criteria

Print:

`[STAGE 2/6] Re-read Phase 2 exit criteria`

Read the CURRENT `project_plan/PROJECT_EXECUTION.md`.

List every Phase 2 exit criterion exactly enough to audit it.

Do not rely on memory or on this prompt for the other exit criteria.

Build an audit table:

| Exit criterion | Repository evidence | Status | Notes |
|---|---|---|---|

For the original judge-human-agreement criterion, record:

- original criterion: required agreement against human labels
- original criterion satisfied literally: NO
- reason: human calibration not performed
- user-approved replacement: cross-model agreement study
- replacement study complete: YES
- replacement result: 88.0% exact agreement, kappa 0.737
- human-validated claim allowed: NO

---

## Stage 3 — Formalize the roadmap amendment

Print:

`[STAGE 3/6] Formalize Task 2.13 roadmap amendment`

The user has explicitly chosen the cross-model study as the replacement for manual human calibration.

Update the planning documentation so that this decision is explicit and auditable.

Requirements:

1. Preserve the original Task 2.13 human-validation requirement in historical text or an amendment note.
2. Do NOT rewrite history as though the original requirement never existed.
3. Add a dated/user-approved amendment stating that for this project:
   - manual 100-case human calibration is deferred/not performed;
   - the completed cross-model agreement study is accepted as the Task 2.13 substitute;
   - this substitution does NOT make the judge human validated;
   - `faithfulness.implemented` must not be flipped solely because of cross-model agreement;
   - accuracy/precision/recall/F1 against human truth must not be claimed.
4. The amended Phase 2 exit logic may treat Task 2.13 as complete via this explicit substitution, but must label the limitation clearly.

Use wording similar to:

> Task 2.13 methodology amendment: by explicit user decision, the original blinded-human calibration requirement is replaced for this project iteration by a frozen cross-model agreement study using qwen3.5:9b and gpt-oss:20b. This satisfies the amended Task 2.13 completion requirement, but does not constitute human validation and does not establish judge accuracy.

Do not weaken or alter unrelated Phase 2 criteria.

---

## Stage 4 — Full Phase 2 exit audit

Print:

`[STAGE 4/6] Phase 2 exit audit`

Audit Tasks 2.1 through 2.13 from actual repository evidence.

At minimum verify the known frozen facts remain unchanged:

### Task 2.1
- truth-contract implementation and hash still present.

### Task 2.2
- supported tag registry still frozen.
- registry hash unchanged.

### Task 2.3
- 2,810-question dataset unchanged.
- 50 narrative questions remain `pending_review`.
- do not promote those 50 to gold.

### Task 2.4
- DEV/TEST split remains intact.
- protected TEST payload not opened.
- official TEST runs remain 0/3.

### Task 2.5 / 2.6
- evaluation schema and deterministic metrics remain intact.
- `faithfulness` is not silently promoted to human-validated.
- `citation_grounding` and other previously deferred metrics remain governed by their actual frozen status.

### Task 2.7
- MS MARCO validation result unchanged.

### Task 2.8
- evidence-alignment result unchanged.
- `gold_evidence_count=0` remains honest under the frozen truth-window mismatch.

### Task 2.9
- canonical 23-field chunk schema unchanged.

### Task 2.10
- canonical hashing identities unchanged.

### Task 2.11
- run-log v1/v2 compatibility unchanged.

### Task 2.12
- FinanceBench retrieval validation unchanged:
  - 150 questions
  - 84 documents
  - 77 defensibly evidence-aligned
  - doc_recall@10 = 0.9221
  - evidence_recall@10 = 0.2641
- do not rerun generation or alter the authoritative retrieval result.

### Task 2.13
- cross-model agreement study complete.
- human validation not performed.
- human-validated judge = NO.
- cross-model agreement = 88.0%.
- Cohen's kappa = 0.737.
- Qwen repeatability = 100.0%.
- GPT-OSS repeatability = 95.0%.
- structured-output success = 100% for both.
- no paid judge calls.
- protected TEST 0/3.

If any other current Phase 2 exit criterion is not satisfied, STOP and report it instead of marking Phase 2 complete.

---

## Stage 5 — Tests, docs, status, Git

Print:

`[STAGE 5/6] Regression and Phase 2 status`

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Report exact counts.

Update, as appropriate:

- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PHASE2_LLM_JUDGE_VALIDATION.md`
- `Progress.md`
- any Phase 2 verification/closure document already established by repository convention
- small tracked Phase 2 status/result artifact if the repo already uses one

Do NOT change frozen data or prior result values merely to make the exit audit pass.

If and only if every Phase 2 exit criterion passes under the explicit methodology amendment:

Set status to something equivalent to:

```text
Phase 2 — COMPLETE WITH NOTE

NOTE:
The original human LLM-judge calibration was not performed.
By explicit user-approved roadmap amendment, Task 2.13 used a completed
cross-model agreement study instead:
qwen3.5:9b vs gpt-oss:20b,
88.0% exact agreement, Cohen's kappa 0.737.
This is not human validation.
```

Do not write simply `HUMAN VALIDATION PASS`.

### Git

Follow `project_plan/GIT_CONVENTIONS.md`.

If the repository convention permits a Phase 2 exit tag and the amended exit audit genuinely passes, create the normal Phase 2 completion tag.

Do not invent a remote.
Do not push if no remote exists.

Commit this closure as one coherent commit.

Suggested commit message:

`Close Phase 2 with documented judge-methodology amendment`

---

## Stage 6 — Determine the real next task

Print:

`[STAGE 6/6] Determine next roadmap task`

After Phase 2 status is resolved, re-read the CURRENT Phase 3 section in `project_plan/PROJECT_EXECUTION.md`.

Do not guess the first Phase 3 task from memory.

Report exactly:

```text
PHASE 2 STATUS:
  ...

TASK 2.13:
  CROSS-MODEL AGREEMENT STUDY COMPLETE
  HUMAN VALIDATION NOT PERFORMED

PHASE 2 AMENDMENT:
  ...

TESTS:
  doctor: ...
  portable: ...
  full: ...

PROTECTED TEST:
  opened: NO
  official runs: 0/3

GIT:
  commit: ...
  phase-2 tag: ...

NEXT ROADMAP TASK:
  <exact task number and title from current PROJECT_EXECUTION.md>
```

Then STOP.

Do NOT implement the first Phase 3 task in this task.

---

## Hard rules

- No new OpenRouter model is needed; the cross-model study is already complete.
- Do not rerun Task 2.13 just to obtain a different agreement number.
- Do not cherry-pick or tune model settings after seeing the completed result.
- Do not call cross-model agreement "accuracy".
- Do not call the judge human validated.
- Do not change `faithfulness.implemented` solely because of the cross-model study.
- Do not open protected SEC TEST.
- Do not consume any official TEST run.
- Do not start Phase 3 implementation.
- Preserve all prior task hashes/results unless a real inconsistency is found.
