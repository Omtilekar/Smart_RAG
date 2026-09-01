# Task 2.7 — MS MARCO Harness Validation

## Phase

**Phase 2 — Make the Numbers Trustworthy**

Current state:

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
  2.6 Metric Unit Tests                       — COMPLETE
  2.7 MS MARCO Harness Validation             — CURRENT
```

Known historical Phase 1 warning:

```text
Task 1.7a citation-format compliance = 8/10
```

Known Phase 2 notes:

```text
Task 2.3:
50 narrative questions remain pending_review.
They are not gold.

Task 2.6 deferred:
numeric_tolerance_match
citation_grounding
faithfulness
```

Do not change these statuses during Task 2.7.

---

# Objective

Validate the project's **retrieval + evaluation harness** against the standard MS MARCO benchmark before trusting future SEC retrieval experiments.

MS MARCO is:

```text
BENCHMARK TRACK
```

not:

```text
SEC PROJECT CORPUS
```

The goal is not to optimize MS MARCO.

The goal is to answer:

```text
Can this repository load a standard benchmark,
preserve its qrels correctly,
run retrieval,
calculate metrics correctly,
and produce numbers that are consistent with
the expected behavior / published reference
for the exact configuration being tested?
```

Task 2.7 is therefore a **harness correctness test**.

A poor but correctly reproduced baseline may PASS the harness test.

A suspiciously strong number produced by incorrect qrel handling must FAIL.

---

# 1. Read Authoritative Sources First

Before changing anything, read:

1. `project_plan/PROJECT_EXECUTION.md`
2. `DATA_READINESS_REPORT.md`
3. `project_plan/PHASE2_METRIC_TESTS.md`
4. `project_plan/PHASE2_EVALUATION_SCHEMA.md`
5. `src/eval/metrics.py`
6. `src/eval/evaluation_schema.py`
7. `src/eval/eval_store.py`
8. `src/eval/baseline_metrics.py`
9. existing retrieval/index/embedding abstractions
10. existing storage/config abstractions
11. `Progress.md`

Also inspect:

```text
data/msmarco/corpus.parquet
data/msmarco/queries.parquet
data/msmarco/qrels_validation.parquet
```

or the actual current paths returned by the repository storage layer.

Do not assume filenames if the repository now exposes them through `src/storage.py`.

---

# 2. Authoritative Task Scope Wins

Read the exact Task 2.7 section in:

```text
project_plan/PROJECT_EXECUTION.md
```

before implementation.

If it materially differs from this detailed prompt:

```text
PROJECT_EXECUTION.md wins.
```

Document the discrepancy in `Progress.md`.

Do not silently choose the larger scope.

---

# 3. Establish Baseline

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
portable-test baseline
full-test baseline

evaluation_schema_version
evaluation_schema_hash

implemented metrics
current-gold metric availability

official SEC TEST evaluations consumed
```

Historical Task 2.6 reference:

```text
full suite: 639 passed

official SEC TEST evaluations consumed:
0 / 3
```

Do not force these values if legitimate repository changes have occurred.

---

# 4. Re-Verify MS MARCO Frozen Data

Before building any benchmark code, independently verify the local benchmark files.

Expected frozen reference:

```text
corpus passages:
8,841,823

queries:
509,962

validation qrel rows:
7,437

validation distinct queries:
6,980
```

The validation split is the standard:

```text
MS MARCO dev-small
```

Verify directly from local data.

Do not merely trust `Progress.md`.

---

# 5. Referential Integrity

Verify:

```text
every validation qrel query_id exists in queries
every validation qrel corpus_id exists in corpus
```

Expected:

```text
100% query referential integrity
100% corpus referential integrity
```

This is a hard prerequisite.

If either is below 100%:

```text
STOP
```

Do not run retrieval on a malformed benchmark.

---

# 6. ID Type Safety

Historical ingestion identified an important issue:

```text
MS MARCO corpus IDs and qrel IDs may have different physical types.
```

Inspect actual Parquet schemas.

Normalize identifiers explicitly.

For example:

```text
"12345"
```

and:

```text
12345
```

must represent the same passage if that is the frozen source semantics.

Do not depend on Python's implicit equality between unlike types.

Add tests covering ID normalization.

---

# 7. Dataset Immutability

Task 2.7 must treat:

```text
data/msmarco/*
```

as frozen source data.

Do not:

```text
rewrite corpus.parquet
rewrite queries.parquet
rewrite qrels
change IDs
drop rows
deduplicate qrels destructively
```

Any benchmark-specific derived files belong under:

```text
artifacts/benchmark/
```

or the repository-designated ignored artifact root.

---

# 8. Benchmark Namespace Isolation

MS MARCO must remain completely separate from the SEC corpus.

Do not insert MS MARCO passages into:

```text
SEC LanceDB tables
SEC chunk tables
SEC embedding artifacts
SEC DEV/TEST evaluation dataset
eval-set split artifacts
```

Use a benchmark-specific namespace such as:

```text
artifacts/benchmark/msmarco/
```

or whatever `PROJECT_EXECUTION.md` specifies.

The benchmark must be disposable without affecting SEC retrieval.

---

# 9. Determine the Exact Retrieval Configuration

Before running anything expensive, determine the exact configuration Task 2.7 requires.

Possible configurations may include:

```text
dense retrieval
lexical/BM25 retrieval
benchmark-specific hybrid retrieval
reranking
```

Do not infer that all of them belong to Task 2.7.

In particular:

```text
DO NOT start Phase 3 production BM25/hybrid/reranker work
unless PROJECT_EXECUTION.md explicitly requires
that component for Task 2.7 harness validation.
```

Benchmark-only plumbing is acceptable where required.

Production SEC optimization is not.

---

# 10. Do Not Tune on MS MARCO

MS MARCO exists here to validate wiring.

Do not perform:

```text
parameter sweeps
embedding-model selection
fusion-weight optimization
reranker tuning
chunk-size tuning
query-rewrite tuning
```

just to increase the benchmark score.

Use the exact frozen configuration required by the roadmap.

One predetermined configuration.

One legitimate result.

---

# 11. Published Reference Before Run

Before the measured benchmark run, determine the expected published/reference result for the **same evaluation setup**.

The reference must match, as applicable:

```text
dataset version
split
retriever/model
metric
cutoff
qrel interpretation
index/search type
```

Do not compare:

```text
MRR@10
```

against a published:

```text
nDCG@10
```

number.

Do not compare:

```text
MS MARCO passage ranking
```

against a document-ranking benchmark.

Do not compare different model variants under the same shorthand name.

---

# 12. Never Invent a Published Baseline

If the exact reference value is not present in the repository:

first inspect the authoritative documents and existing source metadata.

If external lookup is genuinely required and permitted by the task:

record:

```text
source
exact benchmark
model
metric
reported value
version/date if relevant
```

If no trustworthy apples-to-apples reference can be established:

```text
DO NOT fabricate a pass threshold.
```

Instead report:

```text
HARNESS EXECUTED
REFERENCE COMPARISON BLOCKED
```

and explain why.

---

# 13. Freeze Reference Before Measurement

Do not run the benchmark first and then search for a published number that happens to resemble the result.

Record the intended comparison reference before the final measured run.

This prevents post-hoc baseline selection.

---

# 14. Metric Semantics

Use Task 2.6 metric implementations wherever they apply.

Potential retrieval metrics include:

```text
Recall@K
MRR
nDCG@K
```

Use only metrics required by Task 2.7.

Do not add arbitrary headline metrics.

Metric names must carry their cutoff and level when required.

---

# 15. MS MARCO Relevance Granularity

MS MARCO qrels identify relevant:

```text
passages
```

Therefore benchmark relevance is passage-level.

Do not label the MS MARCO benchmark metric:

```text
doc_recall
```

unless the roadmap explicitly defines passage IDs as "documents" for this benchmark abstraction.

Prefer benchmark-accurate terminology such as:

```text
passage_recall@k
MRR
nDCG@k
```

or the exact naming required by `PROJECT_EXECUTION.md`.

Do not confuse SEC:

```text
document relevance
chunk relevance
```

with MS MARCO:

```text
passage relevance
```

---

# 16. Multiple Qrels

Do not assume every MS MARCO query has exactly one relevant passage.

Inspect:

```text
qrels_validation.parquet
```

and characterize:

```text
minimum relevant passages/query
median
maximum
queries with >1 qrel
```

The evaluation implementation must support multiple relevant passage IDs.

Do not throw away secondary qrels.

---

# 17. Correct Recall@K

For each query:

```text
gold_relevant_ids = set(qrels)
retrieved_ids = ranked retrieval output
```

Define Recall@K according to the authoritative benchmark convention.

Do not accidentally substitute:

```text
binary hit@K
```

for:

```text
fraction of all relevant passages retrieved
```

when a query has multiple qrels.

This distinction must be tested.

If the project's Task 2.6 generic recall helper has different semantics:

do not misuse it.

Implement benchmark-specific aggregation explicitly and document why.

---

# 18. MRR Semantics

For MRR:

```text
RR = 1 / rank(first relevant passage)
```

No relevant passage retrieved:

```text
RR = 0
```

Aggregate:

```text
MRR = mean over evaluated queries
```

Use Task 2.6's hand-verified implementation if semantically identical.

Do not duplicate the formula unnecessarily.

---

# 19. nDCG Semantics

Use the exact relevance values contained in qrels.

Determine whether the current MS MARCO qrels are:

```text
binary
```

or:

```text
graded
```

from the data itself.

Do not assume.

Apply the Task 2.6 nDCG implementation only if its relevance assumptions match.

If not, extend it deliberately with tests and metric versioning rather than silently changing existing semantics.

---

# 20. No SEC TEST Access

Task 2.7's word:

```text
TEST
```

must never be confused with the protected SEC:

```text
Phase 2 TEST split.
```

MS MARCO benchmark validation must not access:

```text
artifacts/eval/phase_2_4_test.json
```

and must not call:

```text
load_test_set()
```

Official SEC TEST evaluation count must remain:

```text
0 / 3
```

MS MARCO dev-small evaluation does not consume an SEC TEST run.

---

# 21. Use Validation / Dev-Small Only

Unless `PROJECT_EXECUTION.md` explicitly says otherwise, use:

```text
qrels_validation.parquet
```

corresponding to:

```text
6,980-query dev-small
```

Do not switch to the 43-query MS MARCO `test` artifact merely because it is named "test".

The benchmark comparison is based on the standard dev-small validation population.

---

# 22. Query Coverage

Before retrieval verify:

```text
all 6,980 dev-small queries load
all have non-empty query text
all have at least one valid qrel
all qrel passage IDs resolve to corpus passages
```

Report exact counts.

Any dropped query must be explicit.

Do not silently reduce the denominator.

---

# 23. Expensive-Run Preflight

MS MARCO contains:

```text
8,841,823 passages
```

Before building a full dense index or similarly expensive artifact:

calculate:

```text
expected rows
embedding dimensionality
dtype
raw vector size
estimated total artifact size
available disk
estimated batch count
checkpoint/resume design
```

Print this before proceeding.

Do not accidentally generate tens of GB without a preflight.

---

# 24. Pilot Before Full Build

If Task 2.7 requires embedding/indexing the full benchmark:

run a small representative pilot first.

For example:

```text
10k–50k passages
small query sample
```

The pilot must verify:

```text
ID preservation
embedding dimension
index insertion
retrieval rank ordering
qrel matching
metric pipeline
memory behavior
artifact paths
```

The pilot result is not the benchmark result.

Clearly label it:

```text
PILOT ONLY
```

---

# 25. GPU Use

If the chosen benchmark configuration requires embedding MS MARCO with the existing sentence-transformer:

GPU use is allowed and expected.

Explicitly verify:

```text
requested device = cuda
actual model device = cuda
```

Do not silently fall back to CPU for a multi-million-passage embedding job.

Record:

```text
GPU model
embedding model
model revision
dimension
dtype
batch size
```

---

# 26. Reuse Existing Model Cache

Do not re-download an already cached model unnecessarily.

Use the repository's frozen model/revision policy where applicable.

If the required model is unavailable locally:

follow the existing dependency/model-cache conventions.

Do not substitute another model because it is convenient.

---

# 27. Resumable Embedding Build

If a full embedding build is required:

it must be resumable.

Use deterministic partitions/checkpoints.

A crash after millions of passages must not require restarting from passage 1.

Record:

```text
completed partitions
row ranges
hash/config identity
```

Do not modify source Parquet files.

---

# 28. Deterministic Passage Identity

Every derived embedding/index row must preserve the exact original:

```text
MS MARCO corpus_id
```

Do not replace it with:

```text
row number
LanceDB row index
hash(text)
```

unless maintained only as internal metadata alongside the canonical ID.

Qrel comparison must operate on canonical passage IDs.

---

# 29. Query Encoding Contract

Use the correct query encoding convention for the selected embedding model.

Check:

```text
query prefix
passage prefix
normalization
similarity function
```

from the existing Phase 1 embedding/retrieval contract.

Do not change prefix behavior only for MS MARCO unless the model requires it and the change is documented.

---

# 30. Similarity Contract

Freeze and record:

```text
cosine
dot product
L2
```

as applicable.

Do not compare published results produced with one similarity definition against an implementation using another without documenting the mismatch.

---

# 31. Exact vs ANN Retrieval

Record whether benchmark retrieval uses:

```text
exact
```

or:

```text
approximate nearest-neighbor
```

search.

If using ANN, record all relevant index parameters.

Do not attribute an ANN recall loss to metric-harness failure.

If practical, verify a small sample against exact search.

---

# 32. Retrieval K

Retrieve enough candidates for every metric being reported.

For example:

```text
metric max cutoff = K
retrieval top_k >= K
```

Do not compute:

```text
Recall@50
```

from only:

```text
top 10
```

retrieval results.

---

# 33. Ranking Integrity

For every query:

```text
rank begins at 1
rank is unique
canonical passage ID is preserved
retrieved count <= requested K
```

If duplicate passage IDs occur:

identify the cause.

Do not silently deduplicate unless benchmark semantics explicitly require it.

---

# 34. Tiny Synthetic Harness Tests First

Before the real benchmark, add tests that exercise the entire benchmark evaluator with tiny synthetic data.

Cover:

```text
one relevant passage at rank 1
one relevant passage at rank K
one relevant passage outside K
multiple qrels
no retrieved relevant item
empty result list
unknown corpus ID
duplicate rank
ID string/int normalization
```

Expected values must be hand-derived.

---

# 35. Local Mini-Benchmark Integration Test

Construct a tiny local benchmark using a few real or synthetic passages.

Verify end to end:

```text
load corpus
load queries
load qrels
retrieve
score
persist/report
```

This must run quickly in portable/local-data testing.

Do not require the full 8.8M-passage benchmark for ordinary CI.

---

# 36. Full Benchmark Is Not a Portable Test

The real MS MARCO run must be marked appropriately:

```text
local_data
benchmark
slow
GPU
```

according to repository test conventions.

`pytest` portable mode must not accidentally trigger:

```text
8.8M-passage embedding/index build
```

or a multi-hour benchmark.

---

# 37. Evaluation Persistence

Determine whether Task 2.7's benchmark run should be recorded in:

```text
eval.duckdb
```

under the Task 2.5 schema.

If yes:

use the centralized:

```text
eval_store
```

API.

Do not write direct ad-hoc database tables.

Record provenance such as:

```text
run_id
git_sha
benchmark name
benchmark split
benchmark version/hash
retrieval config
embedding model/revision
index config
metric definitions
timestamp
status
```

---

# 38. Benchmark vs SEC Split Semantics

Task 2.5 currently constrains run split values around:

```text
dev
test
ci
```

Do not weaken that schema casually just to fit MS MARCO.

If benchmark provenance requires a new concept:

first inspect the current schema design.

Possible clean approaches include:

```text
benchmark_name / benchmark_split metadata
```

rather than changing SEC split semantics.

If a schema change is necessary:

document it and follow Task 2.5 migration/version/hash rules.

Do not smuggle `"msmarco"` into a constrained split field.

---

# 39. Keep Aggregate and Per-Query Evidence

For the real benchmark, preserve enough evidence to reproduce aggregate metrics.

At minimum:

```text
query_id
relevant passage IDs or reference thereto
retrieved passage IDs
ranks
metric-relevant per-query diagnostics
```

Do not store only:

```text
MRR = ...
```

with no evidence.

Large retrieval payloads may remain in ignored artifacts if necessary.

Tracked result files should remain compact.

---

# 40. Result Artifact

Create a tracked summary such as:

```text
results/phase_2_7_msmarco_harness.json
```

Include:

```text
benchmark
split
query_count
qrel_count
corpus_count

configuration
model/revision
retrieval type
index type
similarity
top_k

metric definitions
measured metrics

reference metrics
reference source
absolute difference
relative difference where meaningful

run duration
artifact hashes
git SHA

final harness verdict
```

Do not include millions of retrieval rows in the tracked JSON.

---

# 41. Detailed Artifact

Large per-query retrieval evidence should go under:

```text
artifacts/benchmark/msmarco/
```

and remain Git-ignored.

Record a SHA-256 for the large artifact in the tracked summary.

This allows provenance without committing large benchmark output.

---

# 42. Result Determinism

Run the metric calculation twice from the same saved retrieval results.

Expected:

```text
same query count
same metric values
same canonical metric-result hash
```

This checks evaluation determinism without rerunning expensive model retrieval twice.

If retrieval itself is deterministic under the chosen backend, verify a manageable query subset twice as an additional diagnostic.

---

# 43. Independent Metric Recalculation

After producing the benchmark summary:

independently recompute at least the headline metric directly from:

```text
saved query -> ranked passage IDs
+
qrels
```

Do not call the same production aggregate function.

Compare exact values.

Example:

```text
production MRR:   X
independent MRR:  X
```

They must agree within the mathematically justified tolerance.

---

# 44. Manual Spot Checks

Select deterministic cases such as:

```text
first 5 hit queries by query_id
first 5 miss queries by query_id
```

For each manually verify:

```text
query text
gold qrel IDs
retrieved IDs
first relevant rank
per-query score
```

Do not cherry-pick visually nice examples.

---

# 45. Compare Against Reference

The final comparison must distinguish:

```text
MATCH / CONSISTENT
LOWER THAN EXPECTED
HIGHER THAN EXPECTED
NOT COMPARABLE
REFERENCE UNAVAILABLE
```

Do not call every non-identical result a harness failure.

Published scores can differ because of:

```text
model revision
index/search implementation
metric library
tokenization
similarity
query/passage prefixes
approximate search
```

Diagnose configuration differences before concluding the metric harness is broken.

---

# 46. Suspiciously High Results

A result much higher than a reference is not automatically good.

Investigate possible leakage/bugs:

```text
qrels included in retrieval features
query text accidentally indexed
query IDs mistaken for corpus IDs
gold passage forced into candidates
evaluation on subset of easy queries
dropped misses
denominator error
train split accidentally used
```

A harness-validation task should distrust unexplained improvement.

---

# 47. Suspiciously Low Results

Investigate:

```text
ID type mismatch
wrong split
wrong model revision
incorrect embedding prefixes
unnormalized embeddings
wrong similarity metric
corpus rows missing
qrels incorrectly parsed
ANN misconfiguration
cutoff mismatch
```

Do not tune hyperparameters before diagnosing correctness.

---

# 48. No SEC Retrieval Evaluation

Task 2.7 should not run:

```text
Phase 2 DEV retrieval benchmark
Phase 2 TEST retrieval benchmark
```

The objective is still harness validation.

SEC evaluation follows after the harness is trusted and later architecture is built.

---

# 49. No Generation

Task 2.7 is retrieval/evaluation only.

Do not use:

```text
OpenRouter
OpenAI
Anthropic
Ollama generation
LLM judge
```

No generation metric belongs here.

Therefore:

```text
API spend = $0
LLM calls = 0
```

---

# 50. No Reranking Unless Explicitly Required

Do not introduce production reranking simply because:

```text
ms-marco-MiniLM
```

was trained on MS MARCO.

If Task 2.7 explicitly requires a reranker-specific harness check, implement only the benchmark validation needed.

Otherwise reranking remains later work.

Do not start Phase 3 prematurely.

---

# 51. No Hybrid Optimization Unless Explicitly Required

The broader design says MS MARCO is used before trusting hybrid SEC results.

That does not automatically authorize Phase 3 optimization during Task 2.7.

Follow the exact `PROJECT_EXECUTION.md` Task 2.7 scope.

If it requests only harness validation:

do only harness validation.

---

# 52. Resource Safety

Before a large benchmark run print:

```text
free disk
estimated artifact size
GPU VRAM
system RAM
corpus rows
estimated embedding rows
existing completed partitions
```

Do not exceed a reasonable storage/runtime threshold silently.

If actual projected storage is >2× the roadmap estimate:

```text
STOP and report before proceeding.
```

Follow existing project safety conventions.

---

# 53. Artifact Reuse

If a complete benchmark index already exists and its provenance exactly matches:

```text
corpus hash
model
model revision
embedding config
index config
```

reuse it.

Do not rebuild just because this task started in a new session.

If provenance does not match:

do not reuse stale artifacts.

---

# 54. Config File

Create a versioned config such as:

```text
configs/phase_2_7_msmarco_harness.json
```

Include all semantics that could change the result:

```text
benchmark
split
corpus path
queries path
qrels path

model
model revision

query prefix
passage prefix

embedding normalization
similarity

index/search mode
top_k

metrics
metric versions

batch size
dtype

seed where applicable
```

Compute a deterministic:

```text
benchmark_config_hash
```

excluding runtime-only fields.

---

# 55. Dataset Hashes

Hash the logical benchmark inputs.

At minimum:

```text
corpus source identity/hash
queries source identity/hash
validation qrels hash
```

For very large Parquet files, follow existing repository conventions for file/semantic hashing.

Do not use Python's `hash()`.

---

# 56. Benchmark Version

Define an explicit benchmark identity such as:

```text
msmarco-dev-small-v1
```

only if consistent with repository conventions.

The identity should make clear:

```text
dataset
split
version
```

Do not call the benchmark merely:

```text
test
```

---

# 57. Tests

Likely add something such as:

```text
tests/test_msmarco_harness.py
```

Cover:

```text
dataset schema validation
ID normalization
qrel grouping
multi-qrel handling
ranking semantics
metric calculations
cutoff behavior
empty/malformed cases
benchmark/SEC namespace isolation
config hashing
result hashing
tracked-summary generation
```

Add local-data tests only where local benchmark data is required.

---

# 58. No Full Benchmark in Unit Tests

The following must not happen during ordinary:

```text
pytest
```

or:

```text
portable tests
```

```text
load 8.8M passages
build full embeddings
build full vector index
run 6,980 full retrieval queries
```

The full run must require an explicit benchmark command.

---

# 59. CLI / Script

Provide one explicit entry point such as:

```bash
python scripts/run_msmarco_harness.py
```

or:

```bash
python -m src.eval.msmarco_harness
```

according to repository conventions.

If building is separate:

```bash
python scripts/run_msmarco_harness.py --build
python scripts/run_msmarco_harness.py --evaluate
```

Only introduce multiple commands if they improve resumability/reuse.

---

# 60. Dry Run Mode

Strongly prefer:

```bash
python scripts/run_msmarco_harness.py --dry-run
```

or equivalent.

It should verify:

```text
paths
schemas
counts
config
model availability
disk estimate
artifact location
```

without starting the expensive benchmark.

---

# 61. Resume Mode

If the benchmark produces large embeddings/index artifacts:

support safe restart.

For example:

```text
--resume
```

or automatic detection of validated completed shards.

Never resume based only on file existence.

Validate config/hash compatibility first.

---

# 62. Benchmark Result Documentation

Create:

```text
project_plan/PHASE2_MSMARCO_HARNESS.md
```

Document:

- objective;
- why MS MARCO exists in this repository;
- benchmark vs SEC track;
- dataset/split;
- exact data counts;
- referential-integrity verification;
- retrieval configuration;
- metric definitions;
- reference baseline;
- measured result;
- comparison;
- known expected implementation variance;
- hardware/runtime if relevant;
- deterministic verification;
- manual spot checks;
- limitations;
- final harness verdict;
- command to reproduce.

---

# 63. Do Not Rewrite Historical Stale Numbers

Some old project documents contain superseded SEC statistics.

Task 2.7 is not the place to clean those up.

Use the current frozen data-readiness report for factual input state.

Do not rewrite historical data-acquisition sections merely because you notice old numbers.

---

# 64. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.7 MS MARCO Harness Validation
```

Include:

```text
Objective
Initial State
Authoritative Scope
MS MARCO Frozen Input Verification
Benchmark Configuration
Published/Reference Baseline
Resource Preflight
Pilot
Index/Embedding Build if applicable
Harness Implementation
Metrics
Measured Result
Reference Comparison
Independent Metric Recalculation
Manual Spot Checks
Determinism
TEST Discipline
Regression Gates
Tests
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite previous history.

---

# 65. Regression — Task 2.6

Re-run:

```text
tests/test_metrics.py
tests/test_evaluation_schema.py
tests/test_eval_store.py
```

Verify no metric semantics changed unintentionally.

If Task 2.7 required a legitimate metric extension:

add hand-constructed tests before using it.

---

# 66. Regression — Task 2.5

Verify:

```text
evaluation schema valid
schema migrations safe
test_access_log unchanged
eval store still works
```

If no schema change was required:

```text
evaluation_schema_version/hash should remain unchanged.
```

If changed:

document why according to Task 2.5 policy.

---

# 67. Regression — Task 2.4

Without reading protected TEST content verify:

```text
DEV gold = 1,932
TEST gold = 828
CI = 200

DEV/TEST CIK overlap = 0
pending narrative = 35/15
official TEST evaluation runs = 0/3
```

Do not regenerate the split.

---

# 68. Regression — Tasks 2.1–2.3

No semantic changes to:

```text
truth contract
tag registry
evaluation dataset
gold answers
gold behaviors
question IDs
split assignments
```

MS MARCO must not affect SEC ground truth.

---

# 69. Regression — Phase 1

Do not modify:

```text
SEC development corpus
normalizer
chunker
SEC embeddings
SEC LanceDB index
baseline SEC retriever
generator
citation evaluator
Phase 1 results
```

Benchmark code should be isolated.

---

# 70. Frozen Data Safety

Record before/after checks for critical frozen datasets.

At minimum:

```text
data/msmarco source files unchanged
data/edgar_corpus unchanged
data/xbrl.duckdb unchanged
SEC TEST artifact unchanged
```

No benchmark task may rewrite source data.

---

# 71. Git Safety

Before committing:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Confirm no large artifacts are staged.

Specifically exclude:

```text
benchmark embedding shards
benchmark index
full retrieval output
data/
artifacts/
eval.duckdb
.venv/
model cache
.env
credentials
```

Tracked:

```text
source
tests
config
small JSON/MD result summary
documentation
Progress.md
```

---

# 72. Commit

After all gates pass:

create one coherent Task 2.7 commit.

Suggested message:

```text
Validate evaluation harness on MS MARCO
```

or, if benchmark-specific retrieval plumbing was also legitimately required:

```text
Add and validate MS MARCO benchmark harness
```

Do not tag Phase 2 complete.

Task 2.8 still remains.

Do not push if no remote exists.

---

# 73. Stop Conditions

STOP rather than guessing if:

### A. Task 2.7 in PROJECT_EXECUTION differs materially

Follow it.

### B. Exact published comparison baseline cannot be established

Do not invent one.

### C. MS MARCO validation is not exactly 6,980 queries

Investigate before retrieval.

### D. Qrel referential integrity is not 100%

Hard failure.

### E. Required full benchmark would unexpectedly exceed resource estimates

Report before proceeding.

### F. A model/config substitution would be required

Do not substitute silently.

### G. Metric semantics differ from Task 2.6

Version/test explicitly.

### H. SEC TEST access appears necessary

It is not. Stop.

### I. Production Phase 3 architecture work appears necessary

Do not cross the phase boundary unless the authoritative roadmap explicitly makes it part of 2.7.

### J. Benchmark result differs substantially from reference

Diagnose first.

Do not tune.

---

# 74. Acceptance Criteria

Task 2.7 is complete only when:

```text
[ ] exact Task 2.7 contract confirmed from PROJECT_EXECUTION.md

[ ] MS MARCO corpus count independently verified
[ ] query count independently verified
[ ] validation qrel count independently verified
[ ] dev-small query count = 6,980
[ ] query referential integrity = 100%
[ ] corpus referential integrity = 100%

[ ] canonical corpus/query ID normalization defined
[ ] multiple-qrel semantics handled correctly

[ ] benchmark namespace isolated from SEC
[ ] frozen MS MARCO source files unchanged

[ ] exact benchmark retrieval configuration frozen
[ ] config hash computed
[ ] dataset/qrel provenance recorded

[ ] published/reference comparison identified before final run
[ ] no invented baseline value
[ ] metric definition matches reference definition

[ ] synthetic harness tests pass
[ ] local mini integration test passes

[ ] resource preflight performed before any expensive build
[ ] pilot passes before full build if full build required
[ ] expensive artifacts resumable if applicable

[ ] canonical MS MARCO passage IDs preserved through retrieval
[ ] ranking integrity validated
[ ] retrieval top-k sufficient for reported metrics

[ ] Task 2.6 metric functions reused where semantically valid
[ ] benchmark-specific semantics separately tested where needed

[ ] full dev-small benchmark completes if required
[ ] all 6,980 queries accounted for
[ ] no silent query dropping

[ ] result artifact produced
[ ] large evidence artifact hashed and ignored
[ ] headline metric independently recomputed
[ ] deterministic metric rerun matches
[ ] deterministic manual hit/miss spot checks pass

[ ] measured result compared fairly with reference
[ ] unexplained large deviation blocks PASS

[ ] no SEC DEV benchmark run
[ ] no SEC TEST benchmark run
[ ] official SEC TEST runs remain 0/3

[ ] no generation
[ ] no LLM judge
[ ] no API spend

[ ] Task 2.6 regression passes
[ ] Task 2.5 regression passes
[ ] Task 2.4 regression passes
[ ] Task 2.1-2.3 regression passes
[ ] Phase 1 regression passes

[ ] portable tests pass
[ ] full test suite passes

[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git staging dry-run safe
[ ] coherent Task 2.7 commit created
```

---

# 75. Final Console Summary

Print:

```text
PHASE 2.7 — MS MARCO HARNESS VALIDATION
=======================================

Frozen benchmark:
  corpus passages:                <count>
  total queries:                  <count>
  validation qrels:               <count>
  dev-small queries:              <count>
  query integrity:                <percent>
  corpus integrity:               <percent>

Benchmark:
  benchmark ID:                   <id>
  config hash:                    <hash>
  retrieval method:               <method>
  model:                          <model>
  revision:                       <revision>
  similarity:                     <metric>
  search mode:                    <exact / ANN / lexical / etc>
  top-k:                          <k>

Reference:
  source:                         <source>
  metric:                         <metric>
  expected/reference:             <value>
  apples-to-apples:               YES / NO

Measured:
  evaluated queries:              <count>
  Recall@K:                       <value / N-A>
  MRR:                            <value / N-A>
  nDCG@K:                         <value / N-A>

Independent recomputation:        PASS / FAIL
Deterministic metric rerun:       PASS / FAIL
Manual spot checks:               <n/n>

Comparison:
  reference:                      <value>
  measured:                       <value>
  difference:                     <value>
  interpretation:                 CONSISTENT / INVESTIGATE / NOT COMPARABLE

Isolation:
  MS MARCO mixed with SEC:        NO
  frozen benchmark modified:      NO
  SEC DEV evaluated:              NO
  SEC TEST evaluated:             NO
  official SEC TEST runs used:    0 / 3

Compute:
  GPU used:                       YES / NO
  LLM calls:                      0
  API spend:                      $0

Tests:
  new Task 2.7 tests:             <count>
  portable:                       <result>
  full:                           <result>

Regression:
  Task 2.6:                       PASS
  Task 2.5:                       PASS
  Task 2.4:                       PASS
  Task 2.1-2.3:                   PASS
  Phase 1:                        PASS

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact Task 2.8 title from PROJECT_EXECUTION.md>
```

---

# Final Principle

MS MARCO is not here to make the project look good.

It is here to catch a broken measurement system.

The important chain is:

```text
standard benchmark
      ↓
known queries + known qrels
      ↓
our retrieval implementation
      ↓
our Task 2.6 metric implementation
      ↓
our measured result
      ↓
independent recomputation
      ↓
comparison with an appropriate reference
```

Only after that chain is trustworthy should later SEC retrieval scores be treated as meaningful.

Therefore:

```text
Do not tune to MS MARCO.
Do not cherry-pick queries.
Do not drop misses.
Do not change qrels.
Do not confuse passage relevance with SEC document/chunk relevance.
Do not invent a published baseline.
Do not start Phase 3 optimization.
Do not access the protected SEC TEST set.
Do not mix MS MARCO into the SEC corpus.
```

A boring, reproducible benchmark result is the desired Task 2.7 outcome.