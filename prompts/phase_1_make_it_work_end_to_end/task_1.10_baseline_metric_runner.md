# Task 1.10 — Baseline Metric Runner

You are working inside my SEC RAG repository.

Task file:

`task_1.10_baseline_metric_runner.md`

We are executing:

```text
Phase 1 — Make It Work End to End
Task 1.10 — Baseline Metric Runner
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
  1.10 Baseline Metric Runner                 — CURRENT
  1.11 End-to-End Command                     — NOT STARTED
```

Do NOT begin Task 1.11.

---

# AUTHORITATIVE TASK DEFINITION

`project_plan/PROJECT_EXECUTION.md` defines Task 1.10:

```text
### 1.10 Baseline metric runner

- Implement doc_recall@10.
- Hand-check a few calculations.
- Print question count, hit count, and recall.
- Save run metadata and configuration.
```

Task 1.11 separately owns the final end-to-end user command.

Task 1.10 therefore implements and executes the retrieval metric only.

---

# VERIFIED TASK 1.9 INPUT

Task 1.9 is complete.

Current recorded dataset:

```text
dataset:
results/phase_1_9_smoke_evaluation.json

config:
configs/phase_1_9_smoke_evaluation.json

summary:
results/phase_1_9_smoke_evaluation_summary.json

question count:
200

unique target documents:
200

label_granularity:
document

retrieval_metric:
doc_recall@10

smoke_eval_sha256:
0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27
```

Category distribution:

```text
business:             40
risk_factors:         40
mdna:                 40
market_risk:          40
financial_statements: 40
```

Candidate counts recorded by Task 1.9:

```text
business:             1,427
risk_factors:         1,420
mdna:                 1,482
market_risk:          1,431
financial_statements: 1,478
```

Task 1.9 traceability:

```text
200/200 target docs present in Task 1.1 manifest
200/200 source rows resolved
200/200 assigned source sections non-empty
0/200 known empty-source filings selected
15/15 manual question inspections passed
```

Task 1.9 test state:

```text
portable: 311 passed, 9 deselected
full:     320 passed
```

Task 1.9 was committed as:

```text
"Add Phase 1 smoke evaluation set"
```

Use the actual Git commit hash from the repository.

Do not invent it if not shown in Progress.md.

---

# EXISTING RETRIEVER CONTRACT

Task 1.6 provides:

```python
BaselineRetriever.retrieve(question, k=5)
```

with configurable positive integer `k`.

For Task 1.10 call:

```python
retrieve(question, k=10)
```

The retriever returns ranked CHUNK results with at least:

```text
rank
score
distance
chunk_id
document_id
text
source metadata
```

Current retrieval stack:

```text
query model:
BAAI/bge-small-en-v1.5

resolved revision:
5c38ec7c405ec4b44b94cc5a9bb96e735b38267a

chunk_config_hash:
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd

LanceDB table:
chunks

row count:
162,357

search:
exact cosine

ANN indexes:
0

query convention:
Task 1.4 / Task 1.6 existing BGE query encoder

score:
1.0 - raw cosine distance

distance:
raw LanceDB cosine distance
```

Do not alter this stack.

---

# TASK 1.10 METRIC CONTRACT — FROZEN

## Metric Name

The primary metric is exactly:

```text
doc_recall@10
```

Do not rename it:

```text
recall@10
chunk_recall@10
hit_rate@10
MRR
accuracy@10
```

Those would imply different semantics.

## Retrieval Unit

The existing retriever returns ranked chunks.

For each evaluation question:

```python
results = retriever.retrieve(question, k=10)
```

The metric considers exactly those first 10 returned CHUNK results.

Do NOT deduplicate documents before choosing the top 10.

Do NOT retrieve more than 10 and then collapse to 10 documents.

## Per-Question Hit

A question is a hit when:

```text
target_document_id
```

appears as the exact:

```text
result.document_id
```

on ANY of the 10 returned chunks.

Formally:

```text
hit(q) = 1
if ∃ result in top_10_chunks(q)
such that result.document_id == q.target_document_id

otherwise 0
```

Exact string equality only.

Do not match on:

```text
CIK
company
fiscal year
filename prefix
same filing family
same source section
fuzzy string similarity
```

## Duplicate Chunks From the Target Document

If several top-10 chunks belong to the target document:

```text
the question still contributes exactly one hit
```

Do not count multiple target chunks as multiple hits.

## First-Hit Rank

For diagnostics, record:

```text
first_hit_rank
```

as the smallest chunk rank whose `document_id` equals the target.

If the target is absent:

```text
first_hit_rank = null
```

This is diagnostic only.

Do NOT introduce MRR in this task.

## Aggregate Metric

For the frozen Task 1.9 dataset:

```text
question_count = 200
hit_count = sum(hit(q))
doc_recall@10 = hit_count / question_count
```

Use full-precision arithmetic internally.

When printing/displaying, include both:

```text
raw fraction/count
decimal recall
```

Example format only:

```text
questions=200 hits=137 doc_recall@10=0.685000
```

Do NOT use the example number as an expected result.

---

# SECONDARY DIAGNOSTICS — NOT PRIMARY METRICS

Also record simple descriptive diagnostics:

```text
hit_count by category
doc_recall@10 by category
first_hit_rank distribution for hits
retrieval latency p50/p95
total run wall time
```

The five Task 1.9 categories each have 40 questions.

These diagnostics are useful for debugging but are NOT additional frozen
research metrics.

Do not introduce:

```text
MRR
NDCG
MAP
chunk recall
precision
answer accuracy
citation quality
```

in Task 1.10.

---

# CRITICAL RULE — DO NOT ASSUME

If any implementation decision is not clearly resolved by:

1. the actual repository,
2. `project_plan/PROJECT_EXECUTION.md`,
3. `project_plan/PHASE1_SMOKE_EVALUATION.md`,
4. `project_plan/PHASE1_RETRIEVER.md`,
5. Task 1.9 dataset/config/summary,
6. current Task 1.6 retriever code,
7. the metric contract above,

then:

**STOP AND ASK ME.**

Do not silently choose:

```text
document deduplication before top-10
a different k
a different retrieval model
a different metric denominator
a different definition of a document hit
a query skip policy
a retry policy
a failure-to-retrieve policy
a different question subset
a new model/index
an approximate index
a new dependency
a generation call
a citation-quality metric
a Task 1.11 interface
```

When asking:

- state exactly what is ambiguous,
- state what repository evidence you found,
- give the smallest useful options,
- explain downstream impact,
- wait for my answer.

Inspection first.

Assumption never.

---

# IMPORTANT ACCEPTED PHASE 1 WARNING

Task 1.7a remains:

```text
COMPLETE WITH WARN
```

The generation citation-format smoke improved:

```text
3/10 -> 8/10
```

with two residual fullwidth-bracket citation failures.

This warning remains visible and unresolved.

Task 1.10 does NOT call generation, so it neither fixes nor exercises that
issue.

Do not rewrite Task 1.7a history.

Do not claim Phase 1 citation compliance is fully resolved.

---

# PRIMARY OBJECTIVES

Complete only:

1. verify Task 1.9 is committed and unchanged,
2. validate the exact 200-question evaluation input,
3. implement a small reusable `doc_recall@10` calculation,
4. run Task 1.6 retrieval at `k=10` for all 200 questions,
5. save per-question retrieval/metric evidence,
6. calculate exact hit count and `doc_recall@10`,
7. record category diagnostics,
8. hand-check a deterministic sample of calculations,
9. independently cross-check aggregate arithmetic,
10. print question count, hit count, and recall,
11. save run configuration and provenance,
12. prove deterministic logical results on a second run,
13. add focused tests,
14. document the baseline metric,
15. update `Progress.md`,
16. create one coherent Task 1.10 commit,
17. stop before Task 1.11.

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

```text
Task 1.9 committed
working tree clean except intentional Task 1.10 prompt state
Task 1.11 implementation absent
```

If unexplained changes exist:

**STOP AND ASK ME.**

---

# STEP 2 — VERIFY FOUNDATION

Activate `.venv`.

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

Do not call OpenRouter.

---

# STEP 3 — READ CURRENT AUTHORITATIVE MATERIAL

Read:

```text
project_plan/PROJECT_EXECUTION.md
project_plan/PHASE1_SMOKE_EVALUATION.md
project_plan/PHASE1_RETRIEVER.md
project_plan/PHASE1_VECTOR_INDEX.md
project_plan/PHASE1_EMBEDDINGS.md
project_plan/TESTING.md
project_plan/GIT_CONVENTIONS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Inspect:

```text
src/eval/smoke_dataset.py
src/retrieval/baseline.py
src/index/lancedb_index.py
src/embeddings/bge.py

scripts/build_smoke_evaluation.py
scripts/smoke_retrieval.py

configs/phase_1_9_smoke_evaluation.json
results/phase_1_9_smoke_evaluation.json
results/phase_1_9_smoke_evaluation_summary.json
results/phase_1_6_retriever_summary.json
```

Use the actual repo.

---

# STEP 4 — VERIFY TASK 1.9 DATASET

Before writing metric code verify:

```text
question_count = 200
unique question_id = 200
unique target_document_id = 200
label_granularity = document
retrieval_metric = doc_recall@10
smoke_eval_sha256 =
0b2c25dcbde141cafb5694ae748c5131d556d543195158aa3794dec325657a27
```

Recompute `smoke_eval_sha256` independently using Task 1.9's documented
canonical procedure.

If it does not match:

**STOP AND ASK ME.**

Do not evaluate a silently modified dataset.

---

# STEP 5 — VERIFY TASK 1.6 RETRIEVER

Verify current real retrieval path still has:

```text
configurable k
exact cosine search
no ANN
no BM25
no reranker
no generation
```

Run a tiny real `k=10` retrieval smoke before the 200-query run.

Required:

```text
10 returned results
ranks 1..10
document_id present on all
chunk_id present on all
```

Do not change Task 1.6.

---

# STEP 6 — IMPLEMENT PURE METRIC LOGIC

Add a narrow evaluation module, preferably:

```text
src/eval/baseline_metrics.py
```

or a repository-consistent equivalent.

Keep pure metric logic separate from model/index I/O.

Conceptually:

```python
def evaluate_doc_recall_at_k(
    *,
    target_document_id: str,
    retrieved_results: Sequence[...],
    k: int,
) -> ...:
    ...
```

and/or:

```python
def summarize_doc_recall(cases: Sequence[...]) -> ...
```

The exact class/function design should fit the current repository style.

If there is a genuine conflict between dataclass/dict style:

inspect existing `src/eval/` and follow it.

If still ambiguous in a consequential way:

**STOP AND ASK ME.**

---

# STEP 7 — PER-QUESTION RESULT CONTRACT

For every one of the 200 questions record at minimum:

```text
question_id
question
category

target_document_id

k = 10
hit
first_hit_rank

retrieved_chunk_ids
retrieved_document_ids
```

For each returned rank it is useful to retain compact evidence:

```text
rank
chunk_id
document_id
score
distance
```

Do NOT store:

```text
384-d vectors
full chunk text
full source filings
generation output
```

The result should remain small and inspectable.

---

# STEP 8 — EXACT TOP-10 LENGTH

Each successful evaluation question must call:

```python
retriever.retrieve(question, k=10)
```

and return exactly 10 ranked chunks.

If fewer than 10 results are returned from the real 162,357-row table:

this is an invariant violation.

Do not silently evaluate with fewer results.

Fail clearly.

---

# STEP 9 — QUERY FAILURE POLICY

A failure to retrieve/encode a question is NOT a miss.

It is a runner failure.

Do not convert:

```text
exception
empty retrieval due infrastructure error
model-load failure
index-read failure
```

into:

```text
hit = false
```

That would corrupt the metric.

Surface the error and fail the run.

---

# STEP 10 — DOCUMENT HIT LOGIC

For each question:

```python
target = question["target_document_id"]
retrieved_document_ids = [r.document_id for r in results]
hit = target in retrieved_document_ids
```

If hit:

```text
first_hit_rank = minimum r.rank where r.document_id == target
```

Do not deduplicate first.

Do not compare CIK/company/year.

---

# STEP 11 — AGGREGATE

After exactly 200 successful retrievals:

```text
question_count = 200
hit_count = number of hit=True cases
doc_recall@10 = hit_count / 200
```

Assert:

```text
0 <= hit_count <= 200
0.0 <= doc_recall@10 <= 1.0
```

Do not round before calculating.

---

# STEP 12 — CATEGORY DIAGNOSTICS

For each:

```text
business
risk_factors
mdna
market_risk
financial_statements
```

record:

```text
question_count
hit_count
doc_recall@10
```

Expected denominator:

```text
40/category
```

If not 40:

fail dataset validation.

Do not rebalance.

---

# STEP 13 — FIRST-HIT-RANK DIAGNOSTICS

For hit questions record count by:

```text
rank 1
rank 2
...
rank 10
```

This is descriptive only.

Do NOT convert it to MRR.

Do not add another headline metric.

---

# STEP 14 — RUN CONFIGURATION

Create a small tracked config, preferably:

```text
configs/phase_1_10_baseline_metric.json
```

Include stable run-defining fields such as:

```text
schema_version
metric_name = doc_recall@10
k = 10

dataset_path
expected_smoke_eval_sha256

retriever = baseline_vector
embedding_model
embedding_revision
chunk_config_hash
index_table
distance_metric = cosine
search_mode = exact

document_hit_definition
```

Do not include timestamps in the stable config.

No OpenRouter/model-generation config belongs here.

---

# STEP 15 — METRIC RUN CONFIG HASH

Compute:

```text
metric_run_config_hash
```

as SHA-256 over canonical JSON of the stable Task 1.10 config.

Use the same repository convention:

```text
sort_keys=True
stable separators
UTF-8
```

This is provenance, not a metric.

---

# STEP 16 — RUNNER SCRIPT

Create a thin script, preferably:

```text
scripts/run_baseline_metric.py
```

or repository-consistent equivalent.

It should:

1. load and validate Task 1.10 config,
2. load and verify Task 1.9 dataset/hash,
3. construct the real Task 1.6 retriever once,
4. reuse the same model/index handles across all 200 questions,
5. retrieve exactly `k=10`,
6. calculate per-question hit/first-hit rank,
7. aggregate hit count/recall,
8. calculate category diagnostics,
9. record runtime diagnostics,
10. write result JSON,
11. print the required headline line,
12. exit non-zero on invariant failure.

Do not rebuild embeddings or index.

---

# STEP 17 — PRINTED OUTPUT

At the end print clearly:

```text
question_count: 200
hit_count: <actual integer>
doc_recall@10: <actual decimal>
```

A single summary line in addition is fine:

```text
questions=200 hits=<N> doc_recall@10=<value>
```

Do not bury the requested metric in logs.

Do not print only a percentage.

---

# STEP 18 — RESULT FILE

Create a tracked result, preferably:

```text
results/phase_1_10_baseline_metric.json
```

Include:

```text
schema_version

metric_name
k
question_count
hit_count
doc_recall_at_10

category_results
first_hit_rank_counts

dataset_path
smoke_eval_sha256

metric_run_config_hash

retriever provenance:
  embedding model
  embedding revision
  chunk_config_hash
  index path/key if repo-safe
  table name
  search mode
  distance metric

runtime:
  run_seconds
  retrieval latency p50/p95

questions:
  200 compact per-question result records

created_at_utc
```

Do not store absolute personal filesystem paths.

Do not store vectors or chunk text.

---

# STEP 19 — LOGICAL RESULT HASH

Compute a deterministic:

```text
metric_result_sha256
```

over the logical metric outputs excluding:

```text
created_at_utc
latency values
wall-clock runtime
```

Include stable fields such as:

```text
question_id
target_document_id
hit
first_hit_rank
retrieved_chunk_ids
retrieved_document_ids
```

This enables a meaningful second-run determinism check.

Do not hash runtime noise.

---

# STEP 20 — PERFORMANCE DIAGNOSTICS

Measure:

```text
per-question retrieval latency
total run wall time
```

Record at least:

```text
p50
p95
```

Label:

```text
Phase 1 evaluation-run diagnostic — NOT a production benchmark
```

Do not compare this directly to Task 0.10's serving spike as if they were
the same workload.

---

# STEP 21 — DETERMINISM RUN

Run the full 200-question metric twice in fresh processes.

Required logical equality:

```text
same question count
same hit count
same doc_recall@10
same per-question hit values
same first_hit_rank values
same retrieved chunk ID order
same retrieved document ID order
same metric_result_sha256
```

Latency/timestamps may differ.

If logical results differ:

**STOP AND ASK ME** after investigating deterministic implementation issues.

Do not average the two recalls.

---

# STEP 22 — HAND-CHECK CALCULATIONS

Hand-check at least:

```text
10 cases
```

Use a deterministic sample from the saved results:

```text
first 5 hit cases by question_id
first 5 miss cases by question_id
```

If fewer than 5 hits or fewer than 5 misses exist, use all available from
that class and fill the remaining slots with the next cases from the other
class.

For each hand-check inspect:

```text
question_id
target_document_id
10 retrieved document_ids
stored hit
stored first_hit_rank
```

Manually verify:

```text
hit == exact target membership
first_hit_rank == first exact matching rank
```

Record:

```text
10/10 PASS
```

or actual result.

Do not inspect semantic answer quality.

---

# STEP 23 — INDEPENDENT AGGREGATE CROSS-CHECK

After the result file is written, independently re-read it with a separate
small one-off calculation that does NOT call the metric aggregation helper.

Compute:

```text
independent_hit_count = count(question.hit == true)
independent_recall = independent_hit_count / len(questions)
```

Verify exact match to stored:

```text
hit_count
doc_recall_at_10
```

This is required because Task 1.10 explicitly asks to hand-check
calculations.

Do not merely call the same function twice.

---

# STEP 24 — UNIT TESTS

Add focused tests, preferably:

```text
tests/test_baseline_metrics.py
```

Use synthetic retrieval rows.

Cover at minimum:

```text
target at rank 1 -> hit
target at rank 10 -> hit
target absent -> miss
target appears multiple times -> one hit, first rank retained
same CIK/company but wrong document_id -> miss
target would appear at rank 11 -> miss when k=10
exact string equality
empty retrieval rejected when 10 expected
wrong k rejected
aggregate hit count
aggregate recall
category aggregation
first-hit-rank counts
config hash determinism
result hash ignores runtime/timestamp fields
result hash changes when retrieval identity changes
```

Do not need real model/index for portable tests.

---

# STEP 25 — REAL-DATA INTEGRATION TEST

Where appropriate add one `local_data` + `model` + `gpu` marked integration
test using a SMALL subset, not all 200 questions.

It should prove:

```text
real Task 1.9 question loads
real Task 1.6 retriever accepts k=10
10 results returned
metric helper evaluates exact document membership
```

Do not make the full 200-run part of ordinary pytest.

The full metric run is the dedicated Task 1.10 script.

---

# STEP 26 — NO GENERATION

Task 1.10 must NOT call:

```text
MinimalGenerator
OpenRouterProvider
generation API
citation parser
citation-integrity smoke
```

This is retrieval evaluation only.

No API key is needed.

---

# STEP 27 — NO RETRIEVAL CHANGES

Do NOT change:

```text
BGE model
query prefix
vector normalization
LanceDB metric
index type
exact-search mode
retrieval result score semantics
chunking
k default in Task 1.6
```

Task 1.10 supplies `k=10` explicitly.

If the baseline metric is poor, record it.

Do not optimize the retriever inside the metric task.

---

# STEP 28 — NO FILTERING / RERANKING

Do not add:

```text
metadata filtering
BM25
hybrid search
reranking
CRAG
routing
graph retrieval
```

Phase 1 is measuring the deliberately crude vector baseline.

---

# STEP 29 — NO METRIC SHOPPING

Do not calculate several metrics and choose the flattering one.

Primary metric is frozen:

```text
doc_recall@10
```

If the number is poor:

record the poor number.

Phase 1 asks whether the system works, not whether it is good.

---

# STEP 30 — NO FINAL-RESEARCH CLAIM

Every result/documentation location must label the metric as:

```text
Phase 1 smoke baseline
NOT the final benchmark
NOT a trustworthy research result
```

Task 1.9 ground truth is only document-level.

Phase 2 will establish stronger truth/evaluation methodology.

---

# STEP 31 — DOCUMENTATION

Create:

```text
project_plan/PHASE1_BASELINE_METRICS.md
```

unless repository naming conventions clearly require another name.

Document:

## Purpose

First retrieval metric over the Phase 1 200-question smoke set.

## Metric Definition

Give exact `doc_recall@10` formula.

Explicitly state:

```text
top 10 are chunk results
no document dedup before cutoff
hit if any returned chunk's document_id equals target_document_id
```

## Dataset

Record:

```text
200 questions
smoke_eval_sha256
document-level labels
```

## Retriever

Record Task 1.6 model/index/search provenance.

## Run

Record:

```text
question count
hit count
doc_recall@10
metric_run_config_hash
metric_result_sha256
```

## Category Diagnostics

Record five category counts/recalls.

## First-Hit Rank

Descriptive distribution only.

## Hand Checks

Record the deterministic 10-case manual arithmetic check.

## Determinism

Record two-run logical equality.

## Performance

Record p50/p95 and wall time as evaluation diagnostics only.

## Limitations

At minimum:

```text
document-level target only
no chunk-level gold evidence
template-generated broad questions
vector-only exact baseline
no metadata filters
no BM25
no reranker
no answer correctness
no generation evaluation
Task 1.7a citation-format warning remains unresolved at 8/10
not final benchmark
```

## Next Task

```text
Task 1.11 — end-to-end command
```

---

# STEP 32 — UPDATE REPOSITORY STRUCTURE

Update:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

narrowly to list the baseline metric module/script/config/result.

Do not imply Phase 2 evaluation is implemented.

---

# STEP 33 — UPDATE Progress.md

Preserve all history.

Append:

```markdown
## YYYY-MM-DD — Phase 1.10 Baseline Metric Runner
```

Use actual local execution date.

Include:

## Objective

Explain Task 1.10 computes the first document-level retrieval metric over
the frozen Task 1.9 smoke set.

## Initial State

Record:

```text
Task 1.9 commit hash/message
Task 1.9 dataset/hash
question count
Task 1.6 retriever/index/model provenance
test baseline
```

## Metric Contract

Record explicitly:

```text
metric = doc_recall@10
k = 10 chunk results
no document dedup before cutoff
exact target_document_id equality
one hit maximum per question
```

## Run Configuration

Record:

```text
config path
metric_run_config_hash
dataset hash
retriever provenance
```

## Result

Record actual:

```text
question_count
hit_count
doc_recall@10
```

Do not soften a poor result.

## Category Diagnostics

Record all five category values.

## First-Hit-Rank Diagnostics

Record counts.

## Determinism

Record two-run logical equality and `metric_result_sha256`.

## Manual Checks

Record 10 inspected cases and result.

## Independent Aggregate Check

Record independent hit-count/recall recomputation.

## Performance

Record p50/p95 retrieval latency and total wall time.

Label not production benchmark.

## Accepted Existing Warning

Keep visible:

```text
Task 1.7a remains COMPLETE WITH WARN at 8/10 citation-format compliance.
Task 1.10 does not exercise generation.
```

## Tests

Record:

```text
new Task 1.10 tests
doctor
portable
full
```

## Safety

Confirm:

```text
no generation/OpenRouter
dataset unchanged
retriever unchanged
index unchanged
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
frozen data unchanged
no Task 1.11 work
```

## Files Created / Modified

List actual tracked files.

## Git

Record Task 1.10 commit.

## Result Status

Use exactly one:

```text
PASS — baseline doc_recall@10 runner implemented and executed successfully

WARN — metric runner completed with one documented non-blocking issue

BLOCKED — metric could not be computed defensibly
```

A low recall is NOT itself WARN/BLOCKED.

Poor retrieval quality is a valid Phase 1 result.

## Phase Status

If PASS:

```text
1.9 200-Question Smoke Evaluation           — COMPLETE
1.10 Baseline Metric Runner                 — COMPLETE
1.11 End-to-End Command                     — NEXT
```

Keep Task 1.7a WARN visible separately.

---

# STEP 34 — SAFETY / UPSTREAM IMMUTABILITY

After Task 1.10 verify unchanged:

```text
results/phase_1_9_smoke_evaluation.json
Task 1.1 manifest
normalized Markdown
chunks.parquet
embeddings.parquet
LanceDB index
frozen data/
generation code
citation validator
```

Task 1.10 reads them.

It does not mutate them.

---

# STEP 35 — TEST SUITES

After implementation and metric execution run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Required:

```text
0 failures
```

Use actual counts.

Do not hardcode 320 as final.

Do not hide the full 200 metric run inside portable pytest.

---

# STEP 36 — GIT SAFETY

Run:

```bash
git status --short
git status --ignored --short
git add -n .
```

Expected trackable Task 1.10 files may include:

```text
src/eval/baseline_metrics.py
scripts/run_baseline_metric.py
configs/phase_1_10_baseline_metric.json
results/phase_1_10_baseline_metric.json
tests/test_baseline_metrics.py
project_plan/PHASE1_BASELINE_METRICS.md
project_plan/REPOSITORY_STRUCTURE.md
Progress.md
```

Use actual repo-consistent names.

Do not stage:

```text
.env
data/
artifacts/
model cache
embeddings
LanceDB fragments
temporary metric runs
```

Run secret/personal-path scan.

---

# STEP 37 — COMMIT TASK 1.10

After:

```text
dataset/hash verified
metric runner implemented
200-question real run completed
hand checks pass
independent arithmetic check passes
second-run determinism passes
tests pass
safety checks pass
Progress.md updated
```

create one coherent commit.

Preferred message:

```text
Add baseline retrieval metric runner
```

or concise equivalent consistent with Git conventions.

Do not include Task 1.11 work.

Do not tag Phase 1 yet.

---

# STEP 38 — PUSH POLICY

Inspect:

```bash
git remote -v
```

If no remote:

```text
push deferred — no remote configured
```

Do not invent one.

If authorization is ambiguous:

**STOP AND ASK ME.**

Never force-push.

---

# ACCEPTANCE CRITERIA

Task 1.10 is complete only if:

```text
[ ] Task 1.9 commit verified
[ ] Task 1.9 dataset unchanged
[ ] smoke_eval_sha256 independently recomputed and matched
[ ] exactly 200 questions validated
[ ] all labels document-level
[ ] all records specify doc_recall@10

[ ] Task 1.6 retriever verified
[ ] real retrieval uses k=10
[ ] exactly 10 chunk results/question
[ ] no document dedup before top-10 cutoff

[ ] per-question hit uses exact target_document_id equality
[ ] duplicate target chunks count as one question hit
[ ] first_hit_rank recorded correctly
[ ] infrastructure errors are not converted to misses

[ ] question_count = 200
[ ] hit_count calculated
[ ] doc_recall@10 = hit_count / 200
[ ] requested headline values printed clearly

[ ] category hit counts recorded
[ ] category doc_recall@10 recorded
[ ] first-hit-rank counts recorded
[ ] no extra headline metric introduced

[ ] stable Task 1.10 config created
[ ] metric_run_config_hash computed
[ ] compact per-question evidence stored
[ ] no vectors/full chunk text stored
[ ] metric_result_sha256 computed excluding runtime noise

[ ] full 200-question run performed
[ ] second fresh-process run performed
[ ] same hits/ranks/retrieved IDs/recall on both runs
[ ] same metric_result_sha256 on both runs

[ ] 10 deterministic hand checks completed
[ ] exact target membership manually verified
[ ] first_hit_rank manually verified
[ ] independent aggregate hit-count recomputation matches
[ ] independent recall recomputation matches

[ ] focused unit tests added
[ ] small real integration test added where appropriate
[ ] full 200-run not hidden inside normal pytest
[ ] doctor passes
[ ] portable suite 0 failures
[ ] full suite 0 failures

[ ] no generation call
[ ] no OpenRouter call
[ ] no citation metric
[ ] no answer scoring
[ ] no BM25
[ ] no metadata filtering
[ ] no reranker
[ ] no router
[ ] no CRAG
[ ] no retrieval optimization

[ ] result labeled Phase 1 smoke baseline
[ ] no final-research claim
[ ] Task 1.7a 8/10 WARN remains visible

[ ] PHASE1_BASELINE_METRICS.md created
[ ] REPOSITORY_STRUCTURE.md updated narrowly
[ ] Progress.md updated

[ ] upstream artifacts unchanged
[ ] staged content reviewed
[ ] secret/personal-path scan clean
[ ] one coherent Task 1.10 commit created
[ ] no Task 1.11 work
[ ] no force-push
```

---

# STOP CONDITIONS

STOP AND ASK ME rather than assuming if:

```text
Task 1.9 dataset/hash differs

question count is not exactly 200

the dataset no longer has document-level targets

Task 1.6 cannot return exactly 10 results for k=10

the repo already defines doc_recall@10 differently

someone proposes deduplicating documents before the top-10 cutoff

someone proposes using CIK/company/year rather than exact document_id

you are considering treating retrieval exceptions as misses

you are considering changing retrieval to improve the number

you are considering BM25/reranking/filtering

you are considering adding answer/citation metrics

a new dependency appears necessary

a result/config artifact already exists with conflicting semantics

repository docs materially conflict

Git push authorization is unclear

any other durable implementation decision would require guessing
```

---

# IMPORTANT NON-GOALS

Task 1.10 does NOT:

```text
change the Task 1.9 question set
create chunk-level ground truth
build Phase 2 truth contracts
call OpenRouter
generate answers
score answer correctness
score citation correctness
fix Task 1.7a's residual citation format issue
add BM25
add hybrid retrieval
add filters
add reranking
add CRAG
add routing
optimize the baseline
implement Task 1.11
build FastAPI
```

The desired result is only:

```text
200 frozen Task 1.9 questions
        ↓
Task 1.6 exact vector retrieval, k=10
        ↓
exact target_document_id membership
        ↓
hit / miss per question
        ↓
hit_count / 200
        ↓
doc_recall@10
        ↓
saved + printed reproducible Phase 1 baseline number
```

---

# FINAL RESPONSE TO ME

After completing Task 1.10, return:

## Task

```text
task_1.10_baseline_metric_runner.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Input Dataset

Report:

```text
dataset path
question count
smoke_eval_sha256
label granularity
metric label
```

## Retriever Provenance

Report:

```text
module/API
k
embedding model/revision
chunk_config_hash
index table/row count
search mode
distance metric
```

## Metric Definition

State exactly:

```text
doc_recall@10 = number of questions whose target_document_id occurs in
any of the first 10 retrieved chunk results / total questions
```

Confirm:

```text
document dedup before cutoff = NO
exact document_id equality = YES
```

## Headline Result

Report actual:

```text
question_count
hit_count
doc_recall@10
```

## Category Results

Report:

```text
business: questions / hits / recall
risk_factors: questions / hits / recall
mdna: questions / hits / recall
market_risk: questions / hits / recall
financial_statements: questions / hits / recall
```

## First-Hit Ranks

Report counts for ranks 1–10.

## Run Provenance

Report:

```text
config path
result path
metric_run_config_hash
metric_result_sha256
```

## Determinism

Confirm:

```text
two fresh-process runs
same hit count
same recall
same per-question hit/rank
same retrieved chunk/document IDs
same metric_result_sha256
```

## Hand Checks

Report:

```text
cases checked = 10
result
```

Explain sampling rule.

## Independent Arithmetic Check

Report independent:

```text
hit_count
recall
match stored result = YES/NO
```

## Performance

Report:

```text
retrieval latency p50
retrieval latency p95
total wall time
```

Label:

```text
Phase 1 evaluation-run diagnostic — not production benchmark
```

## Tests

Report:

```text
new Task 1.10 tests
portable passed/failed/skipped
full passed/failed/skipped
doctor PASS/FAIL
```

## Existing Warning

Confirm:

```text
Task 1.7a citation-format compliance remains 8/10 and unresolved.
Task 1.10 did not call generation.
```

## Safety

Confirm:

```text
Task 1.9 dataset unchanged
retriever unchanged
index unchanged
embeddings unchanged
chunks unchanged
normalized Markdown unchanged
frozen data unchanged
no OpenRouter
no Task 1.11 work
```

## Files Modified

List actual tracked/project files only.

## Git

Report:

```text
commit created: YES/NO
commit hash
commit message
remote status
push performed: YES/NO
```

## Progress.md

Confirm:

```text
## YYYY-MM-DD — Phase 1.10 Baseline Metric Runner
```

was appended.

## Next Task

If PASS:

```text
task_1.11_end_to_end_command.md
```

Do not start it.

Finally state:

```text
No Task 1.11 work started.
```

Stop and wait for my approval.
