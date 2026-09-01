# Task 2.6 — Metric Unit Tests

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
  2.4 DEV/TEST Split                          — COMPLETE
  2.5 Evaluation Schema                       — COMPLETE
  2.6 Metric Unit Tests                       — CURRENT
```

Known historical Phase 1 warning:

```text
Task 1.7a citation-format compliance = 8/10
```

Known Phase 2 note:

```text
50 narrative questions remain pending_review.
35 are assigned to DEV components.
15 are assigned to TEST components.
0 are gold.
```

Do not change either historical status.

---

# Objective

Implement **hand-constructed, independently verifiable unit tests for the project's evaluation metrics** so that later Phase 3 experiments cannot produce plausible-looking but mathematically incorrect results.

The core rule is:

```text
Metric correctness must be proven on tiny cases
whose answers are known before the implementation runs.
```

This task is about:

```text
metric definitions
metric arithmetic
edge cases
metric applicability
aggregation correctness
schema compatibility
regression protection
```

It is NOT about:

```text
running the full DEV benchmark
running TEST
benchmarking retrieval models
improving retrieval
using an LLM
using GPU
producing headline performance numbers
```

---

# 1. Read the Authoritative Contract First

Before changing anything, read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
3. `src/eval/evaluation_schema.py`
4. `src/eval/eval_store.py`
5. `src/eval/baseline_metrics.py`
6. `src/eval/citation_integrity.py`
7. `project_plan/PHASE1_BASELINE_METRICS.md`
8. `results/phase_2_5_evaluation_schema.json`
9. `results/phase_2_4_ci_golden.json`
10. `Progress.md`

Also inspect:

```text
tests/test_baseline_metrics.py
tests/test_evaluation_schema.py
tests/test_eval_store.py
```

Use the exact Task 2.6 section of `PROJECT_EXECUTION.md` as the final authority.

Do not infer a different task merely because this prompt is more detailed.

If the roadmap's Task 2.6 scope is materially narrower than this prompt:

```text
follow PROJECT_EXECUTION.md
and document the difference.
```

---

# 2. Establish Baseline

Before modification:

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
portable tests
```

Record:

```text
HEAD
working-tree state
evaluation_schema_version
evaluation_schema_hash
registered metric count
implemented metric count
available-for-current-gold count
portable test baseline
full test baseline
```

Expected historical Task 2.5 reference:

```text
evaluation_schema_version = 1

evaluation_schema_hash =
13aec6b2d80d1be70f3d8117bf4914274605910697f88d058f93bfe933332338

registered metrics = 11

full suite = 580 passed
```

Do not force these values if legitimate repository changes have occurred.

---

# 3. Inspect the Current Metric Registry

Task 2.5 currently registers:

```text
doc_recall@10
chunk_recall@10
doc_mrr
chunk_mrr
doc_ndcg@10
numeric_exact_match
numeric_tolerance_match
correct_refusal_rate
citation_format_compliance
citation_grounding
faithfulness
```

Before implementing anything, print/inspect for every metric:

```text
name
version
level
implemented
available_for_current_gold
required_gold_type
applicable_categories
higher_is_better
```

Do not silently change those values.

---

# 4. Critical Distinction — Defined vs Implemented

Task 2.5 deliberately distinguishes:

```text
DEFINED
IMPLEMENTED
AVAILABLE FOR CURRENT GOLD
```

These mean different things.

For example:

```text
chunk_recall@10
```

can have mathematically tested implementation while still being:

```text
available_for_current_gold = false
```

because real chunk/evidence-level labels do not yet exist.

Likewise:

```text
faithfulness
```

may remain schema-defined only if it requires a later judge implementation.

Do not mark a metric:

```text
implemented = true
```

merely because its database schema exists.

Only change that flag when a real implementation exists and Task 2.6 legitimately owns it.

---

# 5. Scope Decision Before Coding

Determine exactly which metric implementations Task 2.6 owns.

The repository's broader evaluation design includes deterministic retrieval metrics:

```text
recall@10
recall@50
MRR
nDCG@10
```

and generation/system metrics including:

```text
numeric exact match
faithfulness
correct refusal
```

However Task 2.5's current registry is the authoritative current implementation target.

Therefore:

### Do

Implement/test deterministic metric functions that the current Task 2.6 contract explicitly owns.

### Do not

Implement:

```text
LLM judge
narrative faithfulness judge
retrieval pipeline
generator
guardrails
CRAG
router
reranker
```

merely because corresponding metrics exist in the registry.

---

# 6. Prefer One Metric Module

If Task 2.6 requires new deterministic metric implementations, create one centralized module such as:

```text
src/eval/metrics.py
```

or use the exact repository-designated path.

Avoid scattering metric formulas across:

```text
scripts/
CLI
retrievers
database code
tests
```

Conceptually:

```text
evaluation data
     ↓
metric functions
     ↓
per-question metric evidence
     ↓
aggregate metric values
     ↓
eval_store
```

Metric computation must remain separate from persistence.

---

# 7. Hand-Computed Fixtures Are Mandatory

The most important Task 2.6 requirement:

**Do not calculate the test's expected result using the implementation being tested.**

Bad:

```python
expected = metric_function(...)
assert metric_function(...) == expected
```

Also bad:

```python
expected = helper_that_uses_same_formula(...)
```

Instead construct tiny cases and write expected values explicitly.

Example:

```text
Ranks of first relevant result:
Q1 -> 1
Q2 -> 2
Q3 -> 4
Q4 -> no hit

Expected reciprocal ranks:
1
1/2
1/4
0

Expected MRR:
(1 + 0.5 + 0.25 + 0) / 4
= 0.4375
```

The human-readable derivation must be visible either in test comments or the Task 2.6 documentation.

---

# 8. Document Recall Semantics

Do not casually redefine the Phase 1 metric.

Task 1.10 established:

```text
doc_recall@10
```

with:

```text
cutoff = first 10 retrieved CHUNK results
hit = target document appears in any of those 10
no document dedup before cutoff
one hit maximum per question
```

If Task 2.6 generalizes document recall, preserve this existing metric version unless the authoritative roadmap explicitly introduces a new version.

Test explicitly:

```text
target at rank 1
target at rank 10
target at rank 11
no target
duplicate chunks from target document
duplicate chunks from irrelevant document
fewer than k results
empty result list
```

Critical boundary:

```text
rank 10 = HIT
rank 11 = MISS
```

---

# 9. Recall Aggregation

Hand-test an aggregate example.

Example:

```text
Q1 hit
Q2 miss
Q3 hit
Q4 hit

expected:
numerator   = 3
denominator = 4
recall      = 0.75
```

Verify:

```text
numerator
denominator
value
```

all agree.

Do not store a rounded percentage as the canonical metric.

---

# 10. MRR

If MRR implementation belongs to Task 2.6, implement standard reciprocal-rank semantics exactly as defined by the authoritative roadmap.

For each query:

```text
RR = 1 / rank_of_first_relevant_result
```

No relevant result:

```text
RR = 0
```

Aggregate:

```text
MRR = mean(RR)
```

Required fixtures should include:

```text
relevant rank 1
relevant rank 2
relevant rank > 2
multiple relevant results — first one wins
no relevant result
empty ranked list
```

Hand-derived example:

```text
ranks = [1, 2, 4, miss]

RR = [1, 0.5, 0.25, 0]

MRR = 0.4375
```

Do not accidentally calculate:

```text
mean rank
1 / mean rank
```

Neither is MRR.

---

# 11. MRR Granularity

Keep:

```text
doc_mrr
```

and:

```text
chunk_mrr
```

separate.

For synthetic unit tests, chunk-level relevance can be represented with synthetic labels.

That does NOT mean current Task 2.3 questions suddenly have real chunk-level gold.

Do not change:

```text
chunk_mrr.available_for_current_gold = false
```

unless a later authoritative evidence-label task has actually completed.

---

# 12. nDCG@10

If `doc_ndcg@10` belongs to Task 2.6 implementation, test the full definition.

Explicitly implement:

```text
DCG@k
IDCG@k
nDCG@k = DCG@k / IDCG@k
```

Freeze the exact discount convention.

Common convention:

```text
gain_i / log2(rank_i + 1)
```

but use the repository's authoritative formula if already specified.

Do not guess silently.

---

# 13. nDCG Hand Cases

Include cases whose outcomes are obvious.

### Perfect ranking

Relevant items occupy ideal positions.

Expected:

```text
nDCG = 1.0
```

### Reversed ranking

Relevant items appear later.

Expected:

```text
0 < nDCG < 1
```

with hand-computed exact expected value.

### No relevant results retrieved

Expected:

```text
nDCG = 0
```

### No relevant items in gold

Define behavior explicitly according to the adopted metric contract.

Usually this requires either:

```text
not applicable
```

or a documented zero convention.

Do not choose silently.

---

# 14. nDCG Binary vs Graded Relevance

Determine whether current project relevance is:

```text
binary
```

or:

```text
graded
```

Do not build graded relevance because nDCG supports it mathematically unless the project's gold labels actually define grades.

If current gold is binary:

```text
relevant = 1
irrelevant = 0
```

test binary nDCG.

Design implementation so future graded relevance could be versioned without changing current semantics.

---

# 15. nDCG Cutoff

Explicitly test:

```text
rank 10 contributes
rank 11 does not
```

for:

```text
doc_ndcg@10
```

Do not accidentally compute full-list nDCG and label it `@10`.

---

# 16. Numeric Exact Match

If Task 2.6 owns `numeric_exact_match`, define exactly what constitutes a match.

Task 2.3 stores canonical numeric truth separately from display formatting.

The metric must compare canonical numeric values, not formatted strings.

Examples:

```text
gold: 1000000
predicted: 1000000
=> exact match
```

Potential representation equivalence:

```text
1000000
1000000.0
1e6
```

should be handled according to the approved numeric parsing contract.

Do not make a decision silently.

Document it.

---

# 17. Currency / Unit Safety

Do not let:

```text
100 USD
```

match:

```text
100 shares
```

merely because the numeric magnitude is identical.

If units are part of the metric contract, test:

```text
same value + same unit     -> match
same value + wrong unit    -> no match
```

Do not perform currency conversion.

Do not infer missing units.

---

# 18. EPS

Include at least one synthetic EPS case if numeric metric logic is implemented.

Example semantic comparison:

```text
gold = 2.31 USD/shares
prediction = 2.31 USD/shares
```

or whatever unit representation the frozen tag registry actually uses.

Read the actual registry.

Do not guess the unit from this prompt.

---

# 19. Negative and Zero Values

Include:

```text
0
negative value
positive value
very large value
small decimal
```

Do not treat a negative numeric gold value as invalid merely because it is negative.

Task 2.1 deliberately allows legitimate signed facts.

---

# 20. Numeric Tolerance Match

If Task 2.6 owns:

```text
numeric_tolerance_match
```

freeze the tolerance policy before writing tests.

Possible elements:

```text
absolute tolerance
relative tolerance
OR/AND relationship
zero denominator behavior
unit requirement
```

Do not choose arbitrary tolerance values based on what makes generated answers pass.

Tolerance is benchmark semantics.

If the authoritative roadmap has not selected tolerance yet:

```text
STOP or keep metric schema-only
```

rather than inventing one.

---

# 21. Tolerance Boundary Tests

If the tolerance is defined, test:

```text
exactly inside tolerance
exactly on boundary
just outside boundary
negative values
zero gold
very small gold
large values
wrong unit
```

Boundary behavior must be explicit:

```text
<= tolerance
```

versus:

```text
< tolerance
```

Do not leave it accidental.

---

# 22. Correct Refusal

If Task 2.6 owns deterministic `correct_refusal_rate` semantics, define the expected inputs explicitly.

Do not score refusal by fragile substring logic such as:

```python
"cannot" in answer.lower()
```

unless the authoritative roadmap explicitly defines such a baseline.

Prefer scoring a structured observed behavior generated by a later evaluator:

```text
expected_behavior
observed_behavior
```

Unit-test the metric arithmetic separately from any future classifier.

Example:

```text
expected refusal cases = 4
correct refusals        = 3

correct_refusal_rate = 3/4 = 0.75
```

---

# 23. Non-Applicable Questions

Metrics must not count non-applicable questions as failures.

For example:

```text
numeric_exact_match
```

does not apply to:

```text
prompt_injection
```

and:

```text
correct_refusal_rate
```

does not automatically apply to ordinary numeric questions.

Test explicitly that:

```text
N/A != 0
```

The denominator must contain only applicable successfully scored questions according to the metric contract.

---

# 24. Execution Errors Must Not Become Metric Misses

This is a critical Task 2.5 invariant.

Test cases such as:

```text
retrieval_error
generation_error
timeout
schema_error
```

must not silently become:

```text
hit = false
exact_match = false
```

unless the metric contract explicitly defines that treatment.

Prefer:

```text
metric unavailable for that row
run partial/failed
```

according to the evaluation schema.

Test denominator behavior explicitly.

---

# 25. Empty Inputs

Every metric implementation must define behavior for empty input.

Do not allow:

```text
ZeroDivisionError
NaN silently persisted
Infinity
```

Possible valid behaviors include:

```text
ValueError
None / not applicable
```

depending on the metric contract.

Choose deliberately and test it.

---

# 26. Invalid Inputs

Add negative tests for malformed data such as:

```text
rank = 0
rank < 0
duplicate rank
NaN score/value
infinite score/value
wrong type
missing required relevance label
negative denominator
numerator > denominator
```

Use the existing Task 2.5 validation layer where appropriate rather than duplicating validation logic.

---

# 27. Citation Format Regression

`citation_format_compliance` is already implemented.

Task 2.6 should include regression tests confirming its metric aggregation semantics without rerunning the historical live LLM diagnostic.

Use synthetic cases:

```text
8 valid
2 invalid

expected:
8 / 10 = 0.8
```

Do NOT:

```text
call OpenRouter
regenerate the historical 10 answers
claim the Phase 1 8/10 warning is resolved
```

---

# 28. Citation Grounding

`citation_grounding` is currently schema-defined.

Do not mark it implemented unless Task 2.6 explicitly owns a deterministic grounding metric with genuine evidence labels.

Testing a mathematical aggregator on synthetic booleans is acceptable if useful.

That does not establish real-system availability.

Preserve the distinction.

---

# 29. Faithfulness

Do not implement an LLM judge during Task 2.6.

If:

```text
faithfulness
```

requires judge-based scoring, leave:

```text
implemented = false
```

unless the authoritative Task 2.6 contract explicitly defines a deterministic implementation.

Do not use OpenRouter.

Do not use the generation model as its own judge.

---

# 30. Retrieval Recall@50

The broader project design includes:

```text
recall@50
```

while Task 2.5 currently registers:

```text
doc_recall@10
chunk_recall@10
```

Do not silently add `doc_recall@50` merely because older project documentation mentions it.

Check `PROJECT_EXECUTION.md`.

If 2.6 explicitly requires `recall@50`:

1. add a properly versioned metric definition;
2. implement it;
3. update schema hash/version only if the Task 2.5 versioning contract requires it;
4. test rank-50/rank-51 boundaries.

Otherwise defer it.

---

# 31. Metric Implementation Purity

Metric functions should preferably be pure.

Example:

```text
input:
gold relevance / result rows

output:
metric result
```

They should not:

```text
open DuckDB
read TEST
perform retrieval
call models
write files
inspect Git
```

Persistence belongs to:

```text
eval_store.py
```

Metric computation belongs to:

```text
metrics.py
```

---

# 32. Per-Question Before Aggregate

Where appropriate, metric implementations should expose enough per-question diagnostics that the aggregate can be independently recomputed.

Example:

```text
doc_recall@10

per question:
hit
first_hit_rank
```

then:

```text
aggregate =
sum(hit) / count(applicable_questions)
```

Do not create opaque aggregate-only implementations.

---

# 33. Independent Aggregate Test

For every aggregate metric implemented in Task 2.6:

1. create per-question synthetic inputs;
2. compute the expected aggregate manually;
3. run the production implementation;
4. independently aggregate the stored/per-question outputs using simple one-off test logic;
5. compare both.

Do not call the production aggregate helper to independently verify itself.

---

# 34. Floating-Point Comparisons

For mathematically irrational/discounted metrics such as nDCG:

use:

```python
pytest.approx(...)
```

with a deliberately tight tolerance.

Do not use a loose tolerance that could hide an incorrect formula.

For exact rational metrics such as:

```text
3/4
```

prefer exact expected constants where practical.

---

# 35. Determinism

Run metric tests in fresh processes if any implementation depends on ordering.

Verify identical results regardless of:

```text
dict order
set order
irrelevant metadata order
```

Never use Python's salted:

```python
hash()
```

as part of metric semantics.

---

# 36. Test Naming

Tests should communicate the mathematical invariant.

Good:

```text
test_doc_recall_at_10_target_at_rank_10_is_hit
test_doc_recall_at_10_target_at_rank_11_is_miss
test_mrr_uses_first_relevant_rank
test_ndcg_perfect_ranking_equals_one
test_numeric_wrong_unit_is_not_match
test_execution_error_not_counted_as_retrieval_miss
```

Avoid meaningless names such as:

```text
test_metric_1
test_basic
test_case
```

---

# 37. Suggested Hand-Constructed Retrieval Fixture

Create a documented toy fixture with approximately 5 queries.

For example:

```text
Q1:
relevant target at rank 1

Q2:
relevant target at rank 2

Q3:
relevant target at rank 10

Q4:
relevant target at rank 11

Q5:
no relevant result
```

From this one fixture manually derive appropriate expected:

```text
doc_recall@10
doc_mrr
doc_ndcg@10
```

if all three are implemented.

Store the expected arithmetic directly in comments/docs.

---

# 38. Separate Multi-Relevant Fixture

If a metric supports multiple relevant documents, add a separate fixture.

Example:

```text
gold relevant docs:
A, B, C

retrieved:
X, B, Y, A, Z
```

Manually derive:

```text
recall
MRR
DCG
IDCG
nDCG
```

Do not assume the single-target Task 1.10 semantics are automatically identical to a multi-relevant-document benchmark.

Version/document the distinction.

---

# 39. Duplicate Documents / Chunks

This project retrieves chunks.

Therefore explicitly test repeated documents:

```text
rank 1 -> document X chunk 1
rank 2 -> document X chunk 2
rank 3 -> target document Y chunk 1
```

For the frozen Task 1.10-style `doc_recall@10`:

```text
first hit rank = 3
```

because rank is the chunk ranking and no document dedup occurs before cutoff.

Do not accidentally change that historical definition.

---

# 40. Metric Registry Synchronization

After implementing any previously schema-only metric:

update:

```text
METRIC_DEFINITIONS
```

only as justified.

For example:

```text
implemented = true
```

may change.

But:

```text
available_for_current_gold
```

must remain based on actual gold-label availability.

Example:

```text
chunk_mrr:
implemented = true
available_for_current_gold = false
```

may be perfectly correct.

---

# 41. Schema Hash Consequence

Task 2.5's schema hash includes metric definitions.

Therefore changing metric-definition semantics/flags may change:

```text
evaluation_schema_hash
```

Before making such a change, inspect Task 2.5's versioning contract.

If a semantic schema change requires:

```text
evaluation_schema_version
```

increment, follow that rule.

Do not accidentally mutate schema semantics while continuing to claim exactly the same version/hash.

If only adding tests and no metric definitions change:

```text
schema version/hash should remain unchanged.
```

Explicitly verify this.

---

# 42. No Fake Availability

At Task 2.6 exit, print a table:

| Metric | Implemented | Current Gold Available | Unit Tested |
|---|---:|---:|---:|

Do not make every row green just for presentation.

It is valid for something such as:

```text
faithfulness
```

to remain:

```text
implemented: false
current gold: false
unit tested: schema/validation only
```

Accuracy of status is more important than apparent completion.

---

# 43. Evaluation Store Compatibility

Verify each newly implemented metric can be persisted through:

```text
EvalStore.record_metric(...)
```

with:

```text
metric_name
metric_version
value
numerator
denominator
scope
```

where applicable.

Use a temporary database.

Do not write synthetic test results into the real:

```text
artifacts/eval/eval.duckdb
```

---

# 44. Metric Round-Trip Test

Using `tmp_path`:

```text
initialize schema
start synthetic CI run
insert synthetic question results
calculate metric
record metric
read metric back
verify exact semantic fields
complete run
```

Do not involve retrieval or generation.

This proves:

```text
metric math
+
Task 2.5 persistence
```

agree on representation.

---

# 45. TEST Must Remain Untouched

Task 2.6 must not read:

```text
artifacts/eval/phase_2_4_test.json
```

for metric examples.

Do not call:

```text
load_test_set()
```

Use:

```text
synthetic fixtures
```

and, if a real artifact is useful:

```text
DEV or CI metadata only
```

Official TEST evaluation runs consumed must remain:

```text
0 / 3
```

---

# 46. Do Not Run DEV Benchmark Either

Task 2.6 proves metric correctness.

It does not need to run all:

```text
1,932 DEV questions
```

through retrieval.

A real retrieval run would test the retrieval system and metric harness simultaneously, making failures harder to localize.

Use tiny deterministic fixtures.

---

# 47. No GPU / LLM / Network

Task 2.6 requires:

```text
NO GPU
NO OpenRouter
NO OpenAI
NO Anthropic
NO Hugging Face downloads
NO SEC network requests
NO web calls
```

It should be fast and fully portable.

The metric unit tests should run on CPU-only CI.

---

# 48. Suggested Files

Likely:

```text
src/eval/metrics.py                   new, only if metric implementations are owned here
tests/test_metrics.py                 new

project_plan/PHASE2_METRIC_TESTS.md   new
project_plan/REPOSITORY_STRUCTURE.md  narrow update
Progress.md                           append
```

Potentially:

```text
src/eval/evaluation_schema.py
```

only if Task 2.6 legitimately changes `implemented` status or metric definitions.

Do not modify files just to match this suggested list.

---

# 49. Test Coverage Requirements

At minimum cover applicable deterministic metrics with:

### Retrieval

```text
hit at rank 1
hit at boundary k
hit outside k
miss
empty results
multiple relevant
duplicate document chunks
first-relevant semantics
```

### MRR

```text
rank 1
rank 2
later rank
multiple relevant
no relevant
aggregate arithmetic
```

### nDCG

```text
perfect
imperfect
zero hit
cutoff boundary
IDCG behavior
```

### Numeric

```text
exact
different
zero
negative
large
decimal
unit match
unit mismatch
invalid parse
```

### Refusal

```text
correct refusal
incorrect refusal
non-applicable
aggregate denominator
```

### Execution status

```text
successful question
error question
N/A question
```

### Persistence

```text
metric name/version
numerator
denominator
scope
duplicate metric prevention
```

---

# 50. Independent Formula Verification

For MRR/nDCG especially, do not trust memory or a third-party library as the only source of truth.

In `PHASE2_METRIC_TESTS.md`, write down at least one small numerical derivation.

Example structure:

```text
Relevant ranks: 1, 2, miss

RR:
1
1/2
0

MRR:
(1 + 0.5 + 0) / 3
= 0.5
```

For nDCG, explicitly show:

```text
DCG
IDCG
division
expected nDCG
```

Then assert the production function against that constant.

---

# 51. Avoid sklearn Shortcut Dependency

Do not automatically introduce:

```text
sklearn.metrics.ndcg_score
```

or another external metrics library simply to avoid implementing a few transparent formulas.

These metrics are small enough to implement and audit directly unless the repository already has an approved dependency/convention.

If using a third-party function, still validate it against hand-computed cases.

---

# 52. Property / Invariant Checks

In addition to example cases, add useful invariants.

Examples:

```text
0 <= recall <= 1
0 <= MRR <= 1
0 <= binary nDCG <= 1

perfect ranking nDCG = 1
moving first relevant result downward cannot improve RR
adding an irrelevant result before first relevant cannot improve RR
```

Do not replace known-answer examples with property tests.

Use both.

---

# 53. Regression Against Phase 1 doc_recall

Do not rerun the Phase 1 retriever.

Instead construct the same mathematical representation from a small synthetic sample or read the existing Task 1.10 result artifact if safe.

Verify the Phase 2-compatible implementation agrees with Task 1.10's frozen semantics:

```text
hit determined by target document membership
within first 10 chunk results
```

Do not alter:

```text
results/phase_1_10_baseline_metric.json
```

---

# 54. Task 2.5 Regression Gate

Verify:

```text
evaluation schema initializes
eval store tests pass
test_access_log untouched
schema invariants preserved
```

If Task 2.6 makes no semantic registry change:

```text
evaluation_schema_hash must remain identical.
```

If it legitimately changes implemented metric definitions:

document why the hash/version changed according to Task 2.5 policy.

Never allow unexplained schema drift.

---

# 55. Task 2.4 Regression Gate

Verify without reading TEST content:

```text
DEV gold = 1,932
TEST gold = 828
CI = 200
DEV/TEST CIK overlap = 0
pending narrative = 35 DEV / 15 TEST
official TEST runs = 0 / 3
```

Do not regenerate the split.

---

# 56. Task 2.1–2.3 Regression Gate

No semantic changes to:

```text
truth contract
tag registry
evaluation dataset
question IDs
gold values
gold behaviors
split assignments
```

Task 2.6 tests metrics.

It does not alter what the correct answers are.

---

# 57. Phase 1 Regression Gate

Do not alter:

```text
retrieval
generation
chunking
embedding
index
citation validator
Phase 1 result artifacts
```

Do not rerun the live citation smoke.

---

# 58. Documentation

Create:

```text
project_plan/PHASE2_METRIC_TESTS.md
```

Document:

- objective;
- authoritative metric definitions;
- implemented vs schema-only metrics;
- current-gold availability;
- formulas;
- relevance granularity;
- cutoff semantics;
- MRR semantics;
- nDCG semantics;
- numeric normalization semantics;
- tolerance semantics if defined;
- refusal semantics if defined;
- N/A handling;
- execution-error handling;
- known-answer fixtures;
- test commands;
- remaining deferred metric implementations.

Include the final matrix:

| Metric | Formula frozen | Implementation | Current gold | Hand-tested |
|---|---|---|---|---|

---

# 59. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.6 Metric Unit Tests
```

Include:

```text
Objective
Initial State
Authoritative Sources
Metric Registry Before
Scope Decision
Implemented Metric Functions
Hand-Constructed Fixtures
Recall Tests
MRR Tests
nDCG Tests
Numeric Tests
Refusal Tests
Error/N-A Semantics
Metric Registry After
Schema Hash/Version Impact
Eval Store Round Trip
TEST Discipline
Regression Gates
Tests
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite historical entries.

---

# 60. Git / Security

Before committing:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Verify no:

```text
artifacts/
data/
.venv/
.env
credentials
TEST dataset
eval.duckdb
```

would be staged.

Run secret/personal-path scan.

---

# 61. Commit

After all tests pass, create one coherent Task 2.6 commit.

Suggested message:

```text
Add hand-verified evaluation metric tests
```

If Task 2.6 also legitimately implements several deterministic metrics, a message such as:

```text
Implement and verify Phase 2 evaluation metrics
```

may better describe the actual change.

Follow `GIT_CONVENTIONS.md`.

Do not tag Phase 2 complete.

Do not push if no remote exists.

---

# 62. Stop Conditions

STOP rather than inventing metric semantics if:

### A. Task 2.6 roadmap contract differs materially

Follow `PROJECT_EXECUTION.md`.

### B. Numeric tolerance is unspecified

Do not invent one.

### C. nDCG relevance grading is unspecified

Use only the explicitly supported relevance model or surface the ambiguity.

### D. Faithfulness requires an LLM judge

Do not implement the judge here.

### E. Chunk metrics need real evidence labels

Mathematical unit testing is okay; real benchmark scoring is not.

### F. TEST access is required

It is not required for unit testing. Do not consume a TEST run.

### G. A previous Phase 2 artifact hash changed unexpectedly

Stop and investigate.

### H. A test can only pass by changing gold labels

The metric or implementation is wrong. Do not modify the gold.

---

# 63. Acceptance Criteria

Task 2.6 is complete only when:

```text
[ ] exact Task 2.6 contract confirmed from PROJECT_EXECUTION.md
[ ] pre-task metric registry audited

[ ] metric formulas explicitly documented
[ ] known-answer fixtures hand-derived
[ ] expected values independent of production implementation

[ ] doc_recall@10 boundary cases tested
[ ] no-dedup-before-cutoff semantics preserved
[ ] MRR tested if owned by Task 2.6
[ ] nDCG@10 tested if owned by Task 2.6
[ ] numeric exact match tested if owned
[ ] numeric tolerance tested only if tolerance is already frozen
[ ] correct-refusal arithmetic tested if owned

[ ] doc metrics and chunk metrics remain distinct
[ ] chunk metric availability is not falsely promoted
[ ] faithfulness is not falsely marked implemented
[ ] N/A is distinct from score=0
[ ] execution errors are distinct from misses

[ ] empty-input behavior defined
[ ] invalid-input behavior tested
[ ] cutoff boundary behavior tested
[ ] duplicate-document/chunk behavior tested

[ ] metric persistence round-trip passes in temporary DB
[ ] no synthetic test rows written to real eval.duckdb

[ ] evaluation schema version/hash impact explicitly verified
[ ] Task 2.5 regression passes
[ ] Task 2.4 regression passes
[ ] Task 2.1-2.3 regression passes
[ ] Phase 1 regression passes

[ ] TEST not loaded
[ ] TEST evaluation runs consumed = 0 / 3
[ ] full DEV benchmark not run
[ ] no retrieval model execution required

[ ] no network
[ ] no LLM
[ ] no GPU
[ ] no API spend

[ ] portable tests pass
[ ] full test suite passes
[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] staging dry-run safe
[ ] coherent Task 2.6 commit created
```

---

# 64. Final Console Summary

Print:

```text
PHASE 2.6 — METRIC UNIT TESTS
=============================

Metric registry:
  total defined:                   <count>
  implemented before:              <count>
  implemented after:               <count>
  current-gold available:          <count>

Metric verification:
  doc_recall@10:                   PASS
  chunk_recall@10:                 PASS / SCHEMA-ONLY
  doc_mrr:                         PASS / DEFERRED
  chunk_mrr:                       PASS / SCHEMA-ONLY
  doc_ndcg@10:                     PASS / DEFERRED
  numeric_exact_match:             PASS / DEFERRED
  numeric_tolerance_match:         PASS / DEFERRED
  correct_refusal_rate:            PASS / DEFERRED
  citation_format_compliance:      PASS
  citation_grounding:              PASS / DEFERRED
  faithfulness:                    DEFERRED

Known-answer fixtures:
  retrieval:                       PASS
  numeric:                         PASS / N/A
  refusal:                         PASS / N/A
  edge cases:                      PASS

Semantics:
  doc vs chunk separated:          PASS
  N/A vs zero separated:           PASS
  execution errors vs misses:      PASS
  cutoff boundaries:               PASS

Schema:
  version before:                  <value>
  version after:                   <value>
  hash before:                     <value>
  hash after:                      <value>
  change justified:                YES / NO CHANGE

Evaluation-store round trip:        PASS

TEST discipline:
  TEST loaded:                     NO
  official TEST runs used:         0 / 3

Tests:
  new Task 2.6 tests:              <count>
  portable:                        <result>
  full:                            <result>

Regression:
  Task 2.5:                        PASS
  Task 2.4:                        PASS
  Task 2.1-2.3:                    PASS
  Phase 1:                         PASS

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact next task from PROJECT_EXECUTION.md>
```

---

# Final Principle

A metric bug is more dangerous than a retrieval bug.

A retrieval bug usually makes the score worse.

A metric bug can make a broken system look better.

Therefore Task 2.6 must make the core evaluation math boring, explicit, and independently checkable.

For every implemented metric we should be able to point to a tiny fixture and say:

```text
Here are the ranked results.
Here is the gold.
Here is the arithmetic by hand.
Here is the exact expected number.
Here is the production function returning the same number.
```

If that cannot be done, the metric is not ready to evaluate Phase 3 experiments.