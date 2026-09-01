# Task 2.4 — DEV/TEST Split

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current repository state:

```text
Data Preparation                              — COMPLETE
Phase 0 — Foundation                          — COMPLETE
Phase 1 — Make It Work End to End             — COMPLETE WITH WARN

Phase 2 — Make the Numbers Trustworthy        — IN PROGRESS
  2.1 XBRL Truth Contract                     — COMPLETE
  2.2 Freeze Supported Tag Registry           — COMPLETE
  2.3 Build the Full Evaluation Dataset       — COMPLETE WITH NOTE
  2.4 DEV/TEST Split                          — CURRENT
```

Known Phase 1 warning:

```text
Task 1.7a citation-format compliance = 8/10
```

Known Phase 2 note:

```text
Task 2.3 has 50 LLM-generated narrative questions with:

status = "pending_review"

They are NOT gold.
```

Do not modify either historical status during this task.

---

# Objective

Split the frozen Task 2.3 evaluation dataset into:

```text
DEV  ≈ 70%
TEST ≈ 30%
```

while preventing company/entity leakage.

The split must be:

- deterministic;
- reproducible;
- company-disjoint;
- compatible with multi-company questions;
- approximately stratified by SIC and fiscal year;
- approximately balanced across evaluation categories/subtypes;
- versioned and hashed;
- protected against accidental test-set inspection;
- ready for later experiments without requiring another split.

The test set becomes the project's held-out benchmark.

Once Task 2.4 is complete:

```text
DEV  = experimentation / tuning / ablations
TEST = frozen final evaluation
CI   = 200-question subset drawn ONLY from DEV
```

---

# 1. Authoritative Sources

Before implementing anything, read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `project_plan/REVIEW_RESOLUTIONS.md` if it exists in the repository
3. `project_plan/PHASE2_EVALUATION_DATASET.md`
4. `results/phase_2_3_evaluation_dataset.json`
5. `results/phase_2_3_evaluation_dataset_summary.json`
6. `configs/phase_2_3_evaluation_dataset.json`
7. `src/eval/evaluation_dataset.py`
8. `src/eval/truth_contract.py`
9. `src/eval/tag_registry.py`
10. `Progress.md`

If repository-local `REVIEW_RESOLUTIONS.md` is still absent, do not invent its existence.

Use the currently available authoritative roadmap and Task 2.3's frozen outputs.

---

# 2. Establish Baseline

Before modifying anything:

```bash
git branch
git status --short
git log --oneline --decorate -15
python --version
python -c "import sys; print(sys.executable)"
```

Run:

```text
doctor
portable test suite
```

Record:

```text
HEAD
working-tree state
Task 2.3 dataset path
Task 2.3 dataset hash
Task 2.3 record count
current test count
```

Expected historical Task 2.3 reference:

```text
master questions:       2,810

numeric:                2,000
comparative:              500
unanswerable:              200
adversarial:                60
narrative:                  50

deterministic/gold-ready: 2,760
narrative pending_review:    50

dataset_sha256:
bf85e1a12ac70645d906a75fa79563c06dbb7620d6e870d4eb29505a326f922a

full test suite:
469 passed
```

Recompute the Task 2.3 semantic dataset hash independently before splitting.

If it does not match the stored hash:

```text
STOP
```

Do not split a dataset whose identity has changed unexpectedly.

---

# 3. Treat Task 2.3 as Frozen Input

Do NOT modify:

```text
results/phase_2_3_evaluation_dataset.json
configs/phase_2_3_evaluation_dataset.json
results/phase_2_3_evaluation_dataset_summary.json
```

Task 2.4 creates derived split artifacts.

It does not rewrite Task 2.3.

---

# 4. Core Split Rule — By Company, Never by Question

The split must occur on:

```text
CIK / company identity
```

not on individual question rows.

Strict invariant:

```text
CIK(dev) ∩ CIK(test) = ∅
```

A company appearing in DEV may never appear in TEST.

This applies across:

```text
different years
different accessions
different tags
different categories
different subtypes
```

Example:

If CIK 320193 appears in DEV for an Assets question, every other question involving that company must also remain in DEV.

Never use:

```python
train_test_split(question_rows)
```

at the raw question level.

That would leak company knowledge across splits.

---

# 5. Critical Multi-Entity Rule

Task 2.3 contains:

```text
150 cross_entity_comparison questions
```

These questions may contain more than one CIK.

A simple:

```text
question.cik -> split
```

implementation is therefore insufficient.

Example:

```text
Question Q:
Company A vs Company B

Company A -> DEV
Company B -> TEST
```

would make the question impossible to assign without leakage.

Therefore construct an **entity graph**:

```text
node = CIK
edge = two CIKs appear in the same evaluation question
```

Compute connected components.

Every connected component is an indivisible split group.

Conceptually:

```text
CIK A ─ CIK B
        │
        CIK C

=> {A, B, C} must all belong to the same split.
```

The split unit must therefore be:

```text
connected CIK component
```

not necessarily one individual CIK.

---

# 6. Verify Multi-CIK Extraction

Inspect the actual Task 2.3 schema.

Do not assume the field containing the second entity.

Identify all entity identifiers referenced by each record.

For every question derive:

```text
participating_ciks
```

Examples:

### Normal numeric

```text
{CIK_A}
```

### Year-over-year

```text
{CIK_A}
```

### Cross-entity

```text
{CIK_A, CIK_B}
```

### Narrative

```text
{CIK_A}
```

### Entity-free adversarial

possibly:

```text
{}
```

Do not miss CIKs stored inside operand/provenance structures.

---

# 7. Entity-Free Questions

Some questions may legitimately have no company identity, especially:

```text
off_scope
some adversarial cases
```

These do not create company leakage.

Assign them deterministically after entity-component assignment while preserving:

```text
category
subtype
overall DEV/TEST ratio
```

Do not invent fake CIK values.

Do not use company `0` or `-1` as a pseudo-company because that would incorrectly bind all entity-free questions into one leakage group.

---

# 8. DEV / TEST Target

Target:

```text
DEV  ≈ 70%
TEST ≈ 30%
```

This is an approximate target, not permission to violate company separation.

Priority order:

```text
1. zero company leakage
2. preserve multi-entity components
3. preserve gold semantics
4. approximate 70/30
5. preserve category/year/SIC distributions
```

Never split a company/component merely to hit exactly 70.000%.

---

# 9. Gold vs Pending Review

Task 2.3 contains:

```text
2,760 deterministic/gold-ready questions
50 narrative questions with status=pending_review
```

Do NOT promote narrative questions to gold.

For Task 2.4:

### Gold-active records

```text
numeric
comparative
unanswerable
adversarial
```

may enter active DEV/TEST benchmark files.

### Pending narrative records

Assign their CIK/component to DEV or TEST using the same company split so their future destination is already determined.

But keep them:

```text
status = pending_review
```

and exclude them from headline DEV/TEST gold counts.

Do not silently convert:

```text
pending_review -> accepted
```

---

# 10. Future Narrative Acceptance

The split design must make later human review safe.

If a narrative question is eventually:

```text
accepted
```

it must inherit the split already assigned to its company/component.

Do NOT rerun the DEV/TEST split after human review.

Do NOT move accepted narrative questions between splits to improve balance.

This prevents future benchmark manipulation.

If rejected:

```text
remove/ignore the question
```

without changing any other company assignment.

---

# 11. SIC Stratification

The project calls for DEV/TEST stratification by:

```text
SIC
fiscal year
```

SIC was previously noted as available in SEC raw submission metadata but not necessarily persisted in `data/xbrl.duckdb`.

Inspect the current repository first.

If SIC is not already available in an approved derived artifact:

use the existing frozen raw SEC data read-only.

Do NOT:

```text
download SEC data
modify data/xbrl.duckdb
add columns/tables to frozen source data
```

A small deterministic derived CIK/accession→SIC mapping may be created if needed.

---

# 12. SIC Mapping Semantics

Determine the actual available SIC grain from the frozen SEC metadata.

Prefer accession-specific SIC where available.

For component-level stratification, derive a deterministic representative SIC.

Possible defensible strategies include:

```text
most frequent SIC among Task 2.3 source filings for the CIK
```

with a deterministic tie-break.

Do not silently choose.

Document the exact rule.

Missing SIC must be represented explicitly:

```text
sic = unknown
```

not guessed.

---

# 13. Fiscal-Year Stratification

Measure fiscal-year distribution across:

```text
2016
2017
2018
2019
2020
```

Task 2.3 currently has a known 2016 skew.

Do not "fix" the source dataset by changing question selection.

Task 2.4 should instead assign components so DEV and TEST have reasonably similar year distributions.

Do not mutate Task 2.3 to rebalance years.

---

# 14. Category / Subtype Preservation

In addition to SIC/year, preserve the five-category structure as closely as possible:

```text
numeric
comparative
narrative_pending_review
unanswerable
adversarial
```

and important subtypes:

```text
year_over_year_difference
cross_entity_comparison
year_outside_window
unsupported_tag
prompt_injection
financial_advice
off_scope
```

Do not let TEST accidentally contain almost none of a category.

---

# 15. Deterministic Split Algorithm

Implement a deterministic group-level splitter.

Suitable architecture:

```text
questions
   ↓
extract participating CIKs
   ↓
build connected components
   ↓
compute component statistics
   ↓
deterministically assign components
   ↓
assign entity-free questions
   ↓
validate
```

The optimization objective should approximately preserve:

```text
70/30 question count
category distribution
subtype distribution
fiscal-year distribution
SIC distribution
```

subject to the hard constraint:

```text
no component may be divided
```

Do not optimize against any model/retrieval performance.

---

# 16. Stable Tie-Breaking

Whenever multiple component assignments are equally good, use a deterministic tie-break.

For example:

```text
SHA-256 over canonical component identity
```

Never use:

```python
hash(...)
```

because Python's built-in hash is process-salted.

If a PRNG is used, it must use a frozen explicit seed and deterministic ordered input.

A hash-based method is preferable.

---

# 17. Split Configuration

Create:

```text
configs/phase_2_4_dev_test_split.json
```

or repository-equivalent.

Include semantic parameters such as:

```text
split_version
dev_fraction
test_fraction

grouping:
  entity_key
  multi_entity_component_policy

stratification:
  sic
  fiscal_year
  category
  subtype

pending_review_policy
entity_free_policy
tie_break_algorithm

source_dataset_version
source_dataset_sha256
```

Do not include timestamps in the semantic config hash.

---

# 18. Split Version / Hash

Freeze a split version, e.g.:

```text
phase2-split-v1
```

Compute:

```text
split_config_sha256
split_assignment_sha256
```

The split assignment hash should change if any question/component changes split.

Formatting-only changes should not affect semantic hashes.

---

# 19. Output Architecture

Use separate artifacts.

Recommended structure:

```text
results/
  phase_2_4_dev.json
  phase_2_4_ci_golden.json
  phase_2_4_split_manifest.json
  phase_2_4_split_summary.json

artifacts/
  eval/
    phase_2_4_test.json
    eval.duckdb
```

Adjust paths only if repository conventions establish a better location.

Critical rules:

```text
DEV may be tracked.
CI golden set may be tracked.
TEST question/gold content must NOT be casually tracked/read.
```

The full test contents must remain gitignored.

---

# 20. Public Split Manifest

The tracked split manifest should contain enough information to reproduce/verify assignment without exposing test question/gold content.

For example:

```text
question_id
split
status
component_id
```

and safe aggregate provenance.

Do not duplicate full TEST:

```text
question text
expected answers
gold evidence
```

inside a tracked manifest.

Otherwise gitignoring the TEST file achieves nothing.

---

# 21. Test File Protection

Explicitly verify with:

```bash
git check-ignore -v <test-file>
git add -n .
```

that the private TEST artifact cannot accidentally be committed.

If necessary, add a narrow `.gitignore` rule.

Do not ignore all `results/`.

Do not break existing tracked result conventions.

---

# 22. TEST Access Logging

Create a controlled test-access mechanism, for example:

```text
src/eval/test_access.py
```

or an equivalent repository-consistent location.

Any legitimate evaluation-time access to the TEST benchmark should record in:

```text
eval.duckdb
```

at minimum:

```text
access_id
timestamp_utc
git_sha
eval_set_version
source_dataset_sha256
split_version
test_sha256
purpose
run_number
```

Potential future evaluation purposes:

```text
baseline_rerank
router_crag
final
```

Do not invent different experiment names if `PROJECT_EXECUTION.md` defines exact milestone names.

---

# 23. Three-Run Test Discipline

The intended test policy is:

```text
maximum planned evaluation runs: 3
```

roughly:

```text
1. after baseline + rerank
2. after router + CRAG
3. final
```

Task 2.4 itself must NOT consume one of these evaluation runs.

Dataset construction/validation is not a model evaluation run.

Distinguish in logging between:

```text
build/validation
evaluation_access
```

The controlled evaluator should refuse or require an explicit override if a fourth evaluation run is attempted.

Do not silently allow unlimited TEST evaluation.

---

# 24. Do Not Evaluate TEST During Task 2.4

Do NOT run:

```text
vector retriever
BM25
hybrid retrieval
reranker
CRAG
router
generator
```

against TEST during this task.

Task 2.4 only freezes the split.

There should be:

```text
0 TEST performance metrics
```

produced by this task.

---

# 25. No Manual TEST Inspection

Do not manually inspect or print TEST questions after the split is frozen.

Validation should rely on:

```text
programmatic schema checks
hashes
aggregate distributions
company-overlap checks
```

Manual quality inspection belongs to DEV.

Do not print individual TEST questions in console logs, documentation, or `Progress.md`.

---

# 26. DEV Dataset

Create the active DEV set from gold-ready Task 2.3 records whose assigned company/component is DEV.

DEV is the only split to use for:

```text
retrieval experiments
chunk-size experiments
embedding comparisons
BM25/hybrid experiments
reranking
CRAG calibration
router tuning
threshold tuning
error analysis
```

DEV can be inspected freely.

---

# 27. TEST Dataset

Create TEST from gold-ready Task 2.3 records whose assigned component is TEST.

TEST is:

```text
FROZEN
```

Do not tune against it.

Do not inspect misses during ordinary development.

Do not use TEST to decide:

```text
chunk size
embedding model
reranker
threshold
router rule
CRAG threshold
prompt
generation model
```

---

# 28. Create the 200-Question CI Golden Set

Create exactly:

```text
200 questions
```

drawn exclusively from DEV.

Never from TEST.

The CI set should be deterministic and reasonably representative of the active DEV categories/subtypes.

It may be overfit through repeated CI exposure.

Therefore it must be explicitly labelled:

```text
CI regression set
NOT reportable benchmark
```

No headline result should ever come from the CI subset.

---

# 29. CI Selection

Use deterministic selection.

Prefer category/subtype coverage over selecting the first 200 IDs.

Do not include:

```text
pending_review narrative
```

until accepted.

Record:

```text
ci_set_version
ci_set_sha256
source_dev_hash
```

The CI set must remain stable unless the evaluation dataset itself is intentionally versioned.

---

# 30. Narrative Pending-Review Assignment Artifact

Create a small artifact such as:

```text
results/phase_2_4_pending_review_assignments.json
```

containing only safe information such as:

```text
question_id
component_id
assigned_split
status=pending_review
```

Do not mark them gold.

This allows future human review without rerunning the company split.

---

# 31. Hard Leakage Checks

Task 2.4 must assert:

```text
all_dev_ciks ∩ all_test_ciks = ∅
```

where:

```text
all_*_ciks
```

means every participating CIK from every question, including secondary entities in cross-entity questions.

Do not check only each record's primary CIK.

Also verify:

```text
no connected component appears in both splits
```

---

# 32. Dataset Completeness

For gold-ready records verify:

```text
DEV question_ids ∪ TEST question_ids
    =
all Task 2.3 gold-ready question_ids
```

and:

```text
DEV question_ids ∩ TEST question_ids
    =
∅
```

Expected gold-ready population before split:

```text
2,760
```

unless independent inspection of the actual Task 2.3 artifact establishes otherwise.

The 50 pending narratives must be accounted for separately.

No question should disappear silently.

---

# 33. Question-ID Stability

Do NOT regenerate Task 2.3 question IDs.

The DEV/TEST files must preserve the exact original:

```text
question_id
```

Task 2.4 adds split metadata.

It does not create new semantic questions.

---

# 34. Distribution Report

Generate diagnostics for DEV and TEST:

```text
question count
fraction

category
subtype
fiscal year
SIC
tag
answer type

unique CIKs
unique accessions

component count
largest component
median component size

entity-free count
pending-review count
```

Report differences between DEV and TEST distributions.

Do not claim perfect stratification if component constraints prevented it.

---

# 35. Special Cross-Entity Diagnostics

Report:

```text
number of cross-entity questions
number of unique CIK edges
number of connected components
largest connected component size
```

Explicitly verify every cross-entity question has all participating entities assigned to the same split.

This is a required gate.

---

# 36. Determinism Verification

Run Task 2.4 twice in fresh processes from identical Task 2.3 input.

Verify identical:

```text
DEV question IDs/order
TEST question IDs/order
pending-review assignments
CI question IDs/order

split assignment hash
DEV hash
TEST hash
CI hash
config hash
```

Timestamps/access-log records may differ.

Semantic split artifacts must not.

---

# 37. Test Hash

Compute a strong semantic hash of the TEST content.

Store the hash in the tracked summary/manifest.

Do NOT store the actual TEST questions/answers in the tracked summary.

Future evaluations must verify the loaded TEST artifact matches the frozen:

```text
test_sha256
```

before scoring it.

---

# 38. Independent Leakage Verification

After the normal split validator passes, perform a separate one-off verification that does not call the production overlap-check helper.

Independently:

1. parse DEV;
2. collect every CIK, including operand entities;
3. parse TEST;
4. collect every CIK;
5. compute intersection.

Expected:

```text
0
```

Also independently verify every Task 2.3 gold question appears exactly once across DEV or TEST.

---

# 39. Manual Inspection

Manual inspection should use DEV only.

Inspect a deterministic DEV sample across:

```text
numeric
comparative
unanswerable
adversarial
```

and narrative only if explicitly reviewing pending candidates.

Do not manually inspect TEST records.

Record that TEST was not manually inspected after freeze.

---

# 40. No Network / LLM / GPU Required

Task 2.4 should be deterministic and local.

Do not use:

```text
OpenRouter
OpenAI
Anthropic
web
SEC downloads
Hugging Face downloads
LLMs
GPU inference
```

This is a data-partitioning task.

No API credits should be spent.

---

# 41. Tests

Add comprehensive tests, likely:

```text
tests/test_dev_test_split.py
```

At minimum cover:

### Basic grouping

```text
same CIK always same split
different years same CIK cannot leak
different categories same CIK cannot leak
```

### Multi-entity

```text
A-B question connects A and B
B-C question produces component A-B-C
component never split
secondary CIK counted in leakage checks
```

### Entity-free

```text
entity-free questions handled without fake CIK
deterministic assignment
```

### Ratio

```text
split approximately targets 70/30
group integrity takes precedence over exact ratio
```

### Stratification

```text
category stats generated
subtype stats generated
year stats generated
SIC stats generated
```

### Pending narrative

```text
pending_review never promoted to gold
pending records receive stable component assignment
pending records excluded from active DEV/TEST gold counts
```

### Determinism

```text
same input -> same assignment
same input -> same hashes
same component ordering differences -> same semantic result
```

### Leakage

```text
CIK(dev) ∩ CIK(test) == empty
all participating CIKs checked
```

### Completeness

```text
every gold-ready Task 2.3 record assigned exactly once
no duplicate question IDs
no lost questions
```

### CI

```text
exactly 200 CI questions
all CI questions belong to DEV
zero CI questions belong to TEST
no pending_review narrative in CI
```

### TEST safety

```text
test file path ignored by Git
tracked manifest contains no test question/gold payload
```

---

# 42. Real-Artifact Integration Test

Add a `local_data`-marked integration test using the real:

```text
2,810-record Task 2.3 dataset
```

Verify:

```text
source hash matches
gold-ready count matches
pending count matches
split builds successfully
zero company overlap
all records accounted for
cross-entity components safe
CI set exactly 200
TEST hash matches manifest
```

Do not evaluate retrieval.

---

# 43. Task 2.3 Regression Gate

Verify Task 2.4 does not modify:

```text
src/eval/evaluation_dataset.py
scripts/build_evaluation_dataset.py
configs/phase_2_3_evaluation_dataset.json
results/phase_2_3_evaluation_dataset.json
results/phase_2_3_evaluation_dataset_summary.json
```

unless a genuine Task 2.3 bug is discovered.

If a Task 2.3 bug is discovered:

```text
STOP
```

Do not quietly fix it inside Task 2.4 because that would invalidate the frozen input dataset and its hash.

---

# 44. Task 2.1 / 2.2 Regression Gate

Verify no semantic changes to:

```text
src/eval/truth_contract.py
src/eval/tag_registry.py
configs/eval_tags.yaml
```

Task 2.4 consumes question records.

It does not redefine ground truth.

---

# 45. Phase 1 Regression Gate

Confirm no semantic changes to:

```text
src/retrieval/
src/generation/
src/index/
src/embeddings/
src/chunk/
src/normalize/
src/eval/citation_integrity.py
src/eval/smoke_dataset.py
src/eval/baseline_metrics.py
src/cli/
Phase 1 configs/results
```

Do not rerun Task 1.7a.

---

# 46. Frozen Source Safety

Confirm no modification to:

```text
data/xbrl.duckdb
data/edgar_corpus/
data/raw/primary/
data/raw/xbrl/
```

Reading SEC raw ZIP metadata for SIC is allowed.

Writing to frozen source is not.

---

# 47. Documentation

Create:

```text
project_plan/PHASE2_DEV_TEST_SPLIT.md
```

Document:

- objective;
- Task 2.3 source identity;
- why question-level random splitting is prohibited;
- CIK grouping;
- multi-entity connected-component logic;
- entity-free policy;
- 70/30 target;
- SIC source and derivation;
- fiscal-year stratification;
- category/subtype balancing;
- narrative pending-review policy;
- output paths;
- split hashes;
- test-set discipline;
- three-run policy;
- CI golden-set policy;
- validation commands;
- known limitations.

Explicitly state:

```text
TEST is frozen and not used for tuning.
CI is from DEV and is not a reportable benchmark.
```

---

# 48. Repository Structure

Update narrowly:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

for new Task 2.4 components only.

Likely:

```text
src/eval/dev_test_split.py
src/eval/test_access.py
scripts/build_dev_test_split.py
configs/phase_2_4_dev_test_split.json
results/phase_2_4_dev.json
results/phase_2_4_ci_golden.json
results/phase_2_4_split_manifest.json
results/phase_2_4_split_summary.json
```

Do not mark later Phase 2 tasks complete.

---

# 49. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.4 DEV/TEST Split
```

Include:

```text
Objective
Initial State
Task 2.3 Source Identity
Split Contract
Entity Grouping
Cross-Entity Connected Components
SIC Mapping
Stratification
DEV/TEST Counts
Pending Narrative Handling
CI Golden Set
TEST Protection
TEST Access Logging
Distribution Diagnostics
Independent Leakage Check
Determinism
Tests
Frozen Data Safety
Regression Gates
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite Task 2.3 history.

---

# 50. Git / Security

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Explicitly confirm TEST does NOT appear in the staging dry run.

Check:

```bash
git check-ignore -v <test-path>
```

Run secret/personal-path scan.

Verify no:

```text
data/
artifacts/
.venv/
.env
credentials
private TEST data
```

would be committed.

---

# 51. Commit

If all gates pass, create one coherent commit.

Suggested message:

```text
Freeze Phase 2 dev test split
```

Do not tag Phase 2 complete.

Do not push if no remote exists.

---

# 52. Stop Conditions

STOP instead of silently weakening the split if:

### A. Task 2.3 hash changed

Do not split an altered dataset.

### B. A CIK appears in both DEV and TEST

Hard failure.

### C. A cross-entity question spans splits

Hard failure.

### D. Multi-entity connected components make the target ratio impossible

Preserve leakage safety first and report the achievable ratio.

### E. SIC semantics cannot be established

Do not invent SIC.

Use an explicit unknown stratum where appropriate and document it.

### F. TEST content would be committed

Fix ignore/storage discipline before proceeding.

### G. Pending narrative questions would be promoted to gold

Do not proceed.

### H. CI set contains TEST questions

Hard failure.

### I. A later evaluation requires viewing TEST during this task

Do not run it.

---

# 53. Acceptance Criteria

Task 2.4 is complete only when:

```text
[ ] Task 2.3 dataset hash independently verified
[ ] Task 2.3 master dataset unchanged

[ ] deterministic DEV/TEST splitter implemented
[ ] target approximately 70/30
[ ] grouping performed by CIK/entity
[ ] multi-entity connected components implemented
[ ] every participating CIK considered
[ ] CIK(dev) ∩ CIK(test) = 0
[ ] no cross-entity question spans splits

[ ] SIC stratification implemented or explicitly unknown where unavailable
[ ] fiscal-year distribution considered
[ ] category distribution considered
[ ] subtype distribution considered

[ ] all 2,760 gold-ready records assigned exactly once
[ ] 50 pending narrative records remain pending_review
[ ] pending narrative split inheritance recorded
[ ] no narrative record silently promoted to gold

[ ] DEV artifact created
[ ] private TEST artifact created
[ ] TEST artifact gitignored
[ ] tracked manifest does not leak TEST content
[ ] DEV hash recorded
[ ] TEST hash recorded
[ ] split assignment hash recorded

[ ] controlled TEST-access logging exists
[ ] Task 2.4 consumes zero official TEST evaluation runs
[ ] no retrieval/generation evaluation performed on TEST

[ ] 200-question CI golden set created
[ ] CI drawn only from DEV
[ ] CI contains no TEST records
[ ] CI marked non-reportable

[ ] independent leakage verification passes
[ ] two fresh split builds are semantically identical

[ ] portable tests pass
[ ] local-data integration test passes
[ ] full suite passes

[ ] frozen SEC source data unchanged
[ ] Task 2.3 regression passes
[ ] Task 2.2 regression passes
[ ] Task 2.1 regression passes
[ ] Phase 1 regression passes

[ ] no network/LLM/API/GPU usage
[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git staging dry-run safe
[ ] one coherent Task 2.4 commit created
```

---

# 54. Final Console Summary

Print:

```text
PHASE 2.4 — DEV/TEST SPLIT
==========================

Source dataset:
  version:                     <version>
  questions total:             2,810
  gold-ready:                  2,760
  pending narrative:              50
  dataset hash:                <hash>

Split:
  version:                     <version>
  config hash:                 <hash>
  assignment hash:             <hash>

Gold DEV:
  questions:                   <count>
  fraction:                    <percentage>
  unique CIKs:                 <count>

Gold TEST:
  questions:                   <count>
  fraction:                    <percentage>
  unique CIKs:                 <count>
  test hash:                   <hash>

Entity safety:
  connected components:        <count>
  largest component:           <count>
  cross-entity questions:      150
  DEV/TEST CIK overlap:        0
  cross-split entity questions:0

Pending narrative:
  total:                       50
  assigned DEV components:     <count>
  assigned TEST components:    <count>
  promoted to gold:            0

CI golden:
  questions:                   200
  source:                      DEV ONLY
  TEST overlap:                0
  reportable benchmark:        NO
  hash:                        <hash>

Stratification:
  SIC:                         PASS / WITH DOCUMENTED LIMITATION
  fiscal year:                 PASS
  category/subtype:            PASS

TEST discipline:
  private path ignored:        PASS
  access log initialized:      PASS
  official TEST eval runs used:0 / 3
  TEST manually inspected:     NO

Validation:
  completeness:                PASS
  independent leakage check:   PASS
  deterministic rebuild:       PASS
  frozen-data safety:          PASS

Tests:
  portable:                    <result>
  full:                        <result>

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact next task name from PROJECT_EXECUTION.md>
```

---

# Final Principle

The purpose of Task 2.4 is not merely to create two files.

It is to preserve the credibility of every later benchmark result.

The following invariant is non-negotiable:

```text
NO COMPANY INFORMATION LEAKS BETWEEN DEV AND TEST.
```

That includes secondary companies inside cross-entity questions.

Therefore:

```text
Do not split questions independently.
Do not split filings independently.
Do not split years independently.
Do not split a multi-entity connected component.
Do not inspect TEST to improve the system.
Do not tune on TEST.
Do not put TEST in CI.
Do not promote pending narrative questions to gold.
Do not reshuffle the split later to improve metrics.
```

Once frozen, the TEST assignment stays frozen.

DEV is where the system gets better.

TEST is where we find out whether it actually did.