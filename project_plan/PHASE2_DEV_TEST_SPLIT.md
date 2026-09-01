# Phase 2 DEV/TEST Split

Established in Task 2.4. Splits the frozen Task 2.3 evaluation dataset
(`results/phase_2_3_evaluation_dataset.json`, 2,810 questions,
`dataset_sha256=bf85e1a12ac70645d906a75fa79563c06dbb7620d6e870d4eb29505a326f922a`)
into a company-disjoint DEV/TEST pair, plus a 200-question CI regression
subset drawn only from DEV. TEST becomes the project's held-out
benchmark.

## Objective

A future developer should be able to open this document and know: why
the split happens by company and not by question, how multi-company
questions are handled without leaking company knowledge across the
split, what TEST protection actually guarantees, and how many
evaluation runs against TEST remain.

## Task 2.3 source identity

```text
source path:      results/phase_2_3_evaluation_dataset.json
dataset_sha256:    bf85e1a12ac70645d906a75fa79563c06dbb7620d6e870d4eb29505a326f922a
question_count:    2,810
gold-ready:        2,760  (numeric, comparative, unanswerable, adversarial)
pending narrative:    50  (status="pending_review" - never gold)
```

`scripts/build_dev_test_split.py` recomputes this hash independently on
every run before doing anything else and refuses to proceed
(`SystemExit`) if it does not match. Task 2.3's own files
(`src/eval/evaluation_dataset.py`, `scripts/build_evaluation_dataset.py`,
`configs/phase_2_3_evaluation_dataset.json`,
`results/phase_2_3_evaluation_dataset.json`,
`results/phase_2_3_evaluation_dataset_summary.json`) are read-only
inputs to Task 2.4 and are never modified.

## Why question-level random splitting is prohibited

A naive `train_test_split(question_rows)` at the question level would
let the same company's real financial facts appear in both DEV and
TEST — since the same CIK produces multiple questions (different tags,
years, categories), a model could effectively "see" a company's Assets
value in DEV and then be evaluated on that same company's Revenues in
TEST, inflating scores without testing genuine generalization. The
split must therefore occur on company identity, never on individual
question rows.

## CIK grouping and multi-entity connected components

The split unit is a **connected component of CIKs**, not a single CIK
and not a question. `src/eval/dev_test_split.py::extract_participating_ciks()`
identifies every entity a question references:

```text
numeric / narrative / unanswerable:  {cik}            (one top-level field)
year_over_year_difference:           {cik}            (single company, two years)
cross_entity_comparison:             {cik_a, cik_b}   (from operands[].cik)
prompt_injection / off_scope:        {}               (no structured company field)
financial_advice:                    {}               (see note below)
```

`cross_entity_comparison` is the only Task 2.3 record shape naming more
than one company. A union-find over all CIKs, with an edge added for
every `cross_entity_comparison` question's operand pair, produces
connected components — chained cross-entity questions (A-B, B-C) merge
into one three-company component `{A, B, C}` that is never split. Real
data: 150 cross-entity questions, 150 unique CIK edges, 2,229 connected
components total, largest component size 4.

**Note on `financial_advice`**: these adversarial questions render a
real company name into the question text (e.g. "Should I buy ACME CORP
stock right now?"), reusing the same real-company-cycling pattern as the
numeric/comparative categories — but the Task 2.3 record schema does not
persist a structured `cik` field for this subtype (only `question`,
`expected_behavior`, `intent_label`, no entity reference). This is not a
Task 2.3 defect requiring a stop: the correct behavior for these
questions (`safe_scoped_response`) does not depend on any retrieved
company fact, so there is no genuine leakage risk in treating them as
entity-free. This is a documented design characteristic of the frozen
Task 2.3 schema, not something Task 2.4 silently patches.

## Entity-free policy

Entity-free questions (`prompt_injection`, `off_scope`, `financial_advice`)
each become their own singleton pseudo-component
(`entityfree-<question_id>`) with zero CIKs — no fake CIK value (`0`,
`-1`, etc.) is ever invented, since that would incorrectly bind every
entity-free question into one artificial leakage group. These
pseudo-components carry no leakage risk and are assigned to DEV/TEST
after all real CIK-based components, using the same deterministic
hash-ordered greedy balance, continuing the same running dev/test
counters (Section 7 of the task spec).

## 70/30 target and assignment algorithm

Priority order (never violated out of sequence):

```text
1. zero company leakage
2. never split a connected component
3. never promote pending_review to gold
4. approximate 70/30 (by gold question count only)
5. approximate category/subtype/fiscal-year/SIC balance
```

Algorithm (`src.eval.dev_test_split.assign_splits`): components are
ordered by `SHA-256(selection_key("phase2-split-component-order", component_id))`
— never Python's salted `hash()` — to avoid any bias from CIK numeric
value or original record order. Processing in that fixed order, each
component is assigned to whichever side (DEV/TEST) currently has the
smaller `assigned_gold_count / target_gold_count` ratio (a standard
deterministic greedy group-balancing rule). Real CIK-based components
are processed first, then entity-free singleton components continue the
same running counters. Pending-review narrative questions ride along
with their company's component and never affect the ratio computation.

Real result: **1,932 DEV / 828 TEST gold questions = exactly 70.0% / 30.0%**
— the fine granularity of ~2,760 gold questions spread across 2,270
distinct components (2,229 CIK-based + entity-free singletons) let the
greedy balance land on the target ratio exactly, without ever needing to
split a component.

## SIC source and derivation

`data/xbrl.duckdb` does not persist SIC (its `submissions` table has no
`sic` column). SIC is read directly and read-only from the frozen SEC
quarterly financial-statement datasets already on disk
(`data/raw/xbrl/*.zip`, each containing a `sub.txt` member with
`adsh -> sic`) — no download, no write back to frozen source.

Component-level representative SIC
(`src.eval.dev_test_split.representative_sic`): pool every real
`accession` referenced anywhere in Task 2.3 records for the component's
CIK(s) (top-level `accession` on numeric records, operand `accession` on
comparative records), look up each accession's SIC, and take the
**most frequent SIC, tied-broken by lexicographically smallest SIC
code**. A component with no resolvable accession (e.g. an
`unsupported_tag`/`year_outside_window` record whose CIK never appears
elsewhere in Task 2.3 with a real accession) is `sic = "unknown"` -
never guessed.

## Fiscal-year stratification

Measured, not forced. The known Task 2.3 2016 skew (see
`project_plan/PHASE2_EVALUATION_DATASET.md`) is preserved, not "fixed" -
Task 2.4 does not touch question selection. DEV/TEST fiscal-year
proportions track the overall 70/30 split closely (e.g. 2016: 883 DEV /
347 TEST ≈ 71.8%/28.2%; 2018: 178 DEV / 102 TEST ≈ 63.6%/36.4%) because
components are small and numerous, but perfect per-year stratification
is not claimed or guaranteed — see `results/phase_2_4_split_summary.json`
for full year/category/subtype/SIC breakdowns on both sides.

## Category/subtype balancing

Not separately optimized — a byproduct of the fine-grained greedy
balance on total gold count. Real result (DEV/TEST, target 70/30):
numeric 1402/598 (70.1%/29.9%), cross_entity_comparison 105/45
(70.0%/30.0%), year_over_year_difference 244/106 (69.7%/30.3%),
unsupported_tag 68/32 (68.0%/32.0%), year_outside_window 71/29
(71.0%/29.0%). The three small adversarial subtypes (20 items each) show
more quantization noise (e.g. prompt_injection 16/4 = 80%/20%) since 20
items cannot hit 70/30 exactly without ever splitting a component - this
is expected and not claimed to be perfect stratification.

## Narrative pending-review policy

`status="pending_review"` narrative questions are threaded through the
exact same component graph as gold questions - a narrative record
inherits whatever split its company's component receives, computed in
the same pass, so **no separate split decision is ever made for
narrative**. They are excluded from the gold DEV/TEST counts and from
the 70/30 ratio target. Real result: 35 narrative questions inherited
DEV, 15 inherited TEST - none promoted to gold, none moved after the
fact. `results/phase_2_4_pending_review_assignments.json` records
`question_id` / `component_id` / `assigned_split` / `status` (no
question text or gold content) so a future human-review task can accept
or reject each question without ever rerunning the company split. An
accepted narrative question inherits its already-assigned split
permanently; a rejected one is simply removed/ignored without touching
any other assignment.

## Output paths

```text
results/phase_2_4_dev.json                      tracked - DEV gold, full content, freely inspectable
results/phase_2_4_ci_golden.json                tracked - 200-question CI subset of DEV, full content
results/phase_2_4_split_manifest.json           tracked - question_id/split/status/component_id only, ALL 2,810 questions
results/phase_2_4_split_summary.json            tracked - distributions/hashes, no question content
results/phase_2_4_pending_review_assignments.json  tracked - narrative split inheritance, no question text
configs/phase_2_4_dev_test_split.json           tracked - semantic build config + split_config_hash
artifacts/eval/phase_2_4_test.json              GITIGNORED - full TEST content
artifacts/eval/eval.duckdb                       GITIGNORED - TEST access log
```

`artifacts/` and `*.duckdb` were already covered by the project's
existing `.gitignore` (from Task 0's foundation work) - no new ignore
rule was needed. Verified with `git check-ignore -v
artifacts/eval/phase_2_4_test.json` (matches) and `git add -n .` (TEST
never appears in the dry-run staging list).

## Split hashes

```text
split_version:            phase2-split-v1
split_config_hash:        c3f36d987e794bf7ebd8d395659de2f6b19db4bf7357319037b9c6dc7f19eb5f
split_assignment_sha256:  931b7eb987ecdd697a571534c4041de7a0538fb22ef83c4de00fcec855fe6dd5
dev_sha256:               2818e6a07f8a465a648bd9e10c78642fec6e8d20f07ca379ef790a190c0c96ee
test_sha256:              6ce8bf8d1b33d449e7a259175592a0f5a0ecd56059582eade483c19b3c8c8f3e
ci_sha256:                adc544629a98026634d0200ee943e978c8436150dcb9e7028e758b77f1730c09
```

All five verified identical across two independent fresh-process runs of
`scripts/build_dev_test_split.py` against the same Task 2.3 input -
fully deterministic, no LLM/random component anywhere in the pipeline.
`split_assignment_sha256` covers every one of the 2,810 questions'
`(question_id, split, status, component_id)`; `dev_sha256`/`test_sha256`/
`ci_sha256` reuse `src.eval.evaluation_dataset.compute_dataset_sha256`
(the same canonical-JSON SHA-256 convention as Task 2.3) over the full
record content of each subset.

## Test-set discipline

TEST is frozen the moment this task's build completes. It is not used
for tuning chunk size, embedding model, reranker, thresholds, router
rules, CRAG thresholds, prompts, or the generation model. No retrieval,
BM25, hybrid, reranker, CRAG, router, or generation code was run against
TEST during Task 2.4 - **0 TEST performance metrics were produced by
this task**. TEST was not manually inspected after the split was frozen;
all manual inspection in this task used DEV only (Section 39).

`src/eval/test_access.py::load_test_set(purpose)` is the only sanctioned
way to read TEST content. It re-verifies the on-disk file's hash against
the tracked manifest's `test_sha256` before returning anything, and logs
every access (with `git_sha`, `eval_set_version`,
`source_dataset_sha256`, `split_version`, `test_sha256`, `purpose`,
`run_number`) to `artifacts/eval/eval.duckdb`'s `test_access_log` table.

## Three-run policy

```text
maximum planned evaluation runs against TEST: 3
  1. baseline_rerank
  2. router_crag
  3. final
```

Task 2.4's own construction/validation access is logged as
`kind="build_validation"` and never counts toward this budget - only
`kind="evaluation_access"` rows (produced exclusively by
`load_test_set()`) are counted. A fourth `load_test_set()` call raises
`TestAccessError` unless the caller explicitly passes
`allow_override=True`. `PROJECT_EXECUTION.md` does not name exact
milestone strings for these three runs, so the task's own suggested
purpose names (`baseline_rerank`, `router_crag`, `final`) are used
directly rather than invented.

## CI golden-set policy

`results/phase_2_4_ci_golden.json` - exactly 200 questions, drawn
**exclusively from DEV** (`src.eval.dev_test_split.select_ci_golden`),
never from TEST. Selection is deterministic and subtype-stratified: a
largest-remainder proportional quota per gold subtype (excluding
narrative, which is never eligible for CI), then a `selection_key`-hash-
ordered deterministic draw within each subtype. **The CI set is
explicitly a CI regression set, not a reportable benchmark** - it may be
overfit through repeated CI exposure over the life of the project. No
headline result should ever be reported from the CI subset;
`results/phase_2_4_ci_golden.json` carries
`"reportable_benchmark": false` for exactly this reason.

## Validation commands

```bash
python scripts/build_dev_test_split.py
python -m pytest tests/test_dev_test_split.py tests/test_test_access.py -q
python -m pytest -q
git check-ignore -v artifacts/eval/phase_2_4_test.json
git add -n .
```

## Known limitations

- SIC stratification is measured and approximated, not guaranteed exact
  - the long tail of ~300 distinct SIC codes across a ~2,270-component
  population means some rare SIC codes appear only once and land
  entirely on one side by chance, not by design.
- Fiscal-year and category/subtype balance are *approximated* through
  the fine granularity of the component structure, not directly
  optimized - see the real numbers above for the actual achieved
  balance, including the small adversarial subtypes' visible
  quantization noise.
- `financial_advice` questions carry no structured CIK and are treated
  as entity-free for split purposes (see note above) - a real company
  name appearing in a `financial_advice` question's text is not
  tracked as a leakage-relevant entity reference, which is a deliberate,
  documented choice, not an oversight.
