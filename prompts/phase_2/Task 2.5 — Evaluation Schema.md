# Task 2.5 — Evaluation Schema

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
  2.5 Evaluation Schema                       — CURRENT
```

Known Phase 1 warning:

```text
Task 1.7a citation-format compliance = 8/10
```

Known Phase 2 note:

```text
50 Task 2.3 narrative questions remain status=pending_review.

Task 2.4 assigned:
DEV pending narrative  = 35
TEST pending narrative = 15

None are gold.
```

Do not change either historical status in Task 2.5.

---

# Objective

Design and implement the **authoritative evaluation-result schema and storage contract** that all later retrieval, generation, routing, CRAG, reranking, and end-to-end experiments must use.

Task 2.5 does **not** optimize the system and does **not** run the held-out TEST benchmark.

It defines how evaluation results are represented, validated, versioned, and persisted.

The key objective is:

```text
Every future metric must be traceable to:
- exactly which code ran,
- exactly which evaluation set ran,
- exactly which split was used,
- exactly which retrieval/chunk/index configuration ran,
- exactly which models ran,
- exactly which questions produced the aggregate,
- exactly which metric definition was used.
```

A result without reproducible provenance is not a valid experiment result.

---

# 1. Read Authoritative Sources First

Before modifying anything, inspect:

1. `project_plan/PROJECT_EXECUTION.md`
2. `project_plan/PHASE2_DEV_TEST_SPLIT.md`
3. `project_plan/PHASE2_EVALUATION_DATASET.md`
4. `project_plan/PHASE2_TRUTH_CONTRACT.md`
5. `project_plan/PHASE2_TAG_REGISTRY.md`
6. `project_plan/REVIEW_RESOLUTIONS.md` if present in the repository
7. `src/eval/dev_test_split.py`
8. `src/eval/test_access.py`
9. `src/eval/evaluation_dataset.py`
10. `src/eval/baseline_metrics.py`
11. `results/phase_2_4_split_manifest.json`
12. `results/phase_2_4_split_summary.json`
13. `results/phase_2_4_ci_golden.json`
14. `Progress.md`

Also inspect the existing:

```text
artifacts/eval/eval.duckdb
```

schema read-only before changing it.

Task 2.4 already created this database for TEST-access logging.

Do not overwrite or recreate it blindly.

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
portable tests
```

Record:

```text
HEAD
working-tree state
portable-test baseline
full-test baseline

Task 2.3 dataset hash
Task 2.4 split version
Task 2.4 split-assignment hash
DEV hash
TEST hash
CI hash
```

Historical Task 2.4 reference state:

```text
gold_total:      2,760
DEV gold:        1,932
TEST gold:         828

pending narrative:
DEV:                35
TEST:               15

CI set:             200
DEV/TEST CIK overlap: 0

full test suite:
515 passed
```

These are historical references, not values to force if legitimate repository changes have occurred.

---

# 3. Inspect Existing eval.duckdb

Open:

```text
artifacts/eval/eval.duckdb
```

and inspect:

```text
tables
columns
types
constraints
indexes if any
```

Task 2.4 already owns:

```text
test_access_log
```

with fields similar to:

```text
access_id
timestamp_utc
git_sha
eval_set_version
source_dataset_sha256
split_version
test_sha256
kind
purpose
run_number
```

Do not delete, rename, truncate, or semantically change this table unless the current authoritative roadmap explicitly requires migration.

Task 2.5 should **extend** the evaluation database safely.

---

# 4. Evaluation Schema Principles

The schema must follow these rules:

```text
1. immutable run identity
2. reproducible provenance
3. per-question results retained
4. aggregates derived from per-question results
5. metric definitions versioned
6. DEV / TEST / CI explicitly distinguished
7. TEST discipline preserved
8. document relevance and chunk relevance never conflated
9. missing metrics represented explicitly
10. infrastructure failures never silently become misses
```

Do not create a table that stores only:

```text
experiment_name
accuracy
```

That is insufficient.

---

# 5. Define Evaluation Run Identity

Every evaluation run must have a globally unique:

```text
run_id
```

Use a deterministic or UUID-based run identifier according to repository conventions.

`run_id` must not be reused.

A run represents one evaluation execution using one frozen combination of:

```text
code
dataset
split
retrieval configuration
index/chunk configuration
model configuration
metric schema
```

---

# 6. Evaluation Run Table

Implement an authoritative run-level table, conceptually:

```text
eval_runs
```

The exact name may follow current repository conventions.

At minimum include:

```text
run_id

timestamp_utc
git_sha

split
eval_set_version
source_dataset_sha256
split_version
split_assignment_sha256

question_set_sha256
question_count

chunk_config_hash
index_config_hash
retrieval_config_hash

embed_model
embed_model_revision

rerank_model
rerank_model_revision

generation_model
generation_provider

router_version
crag_config_hash

metric_schema_version

status
error_type
error_message
```

Not every field will apply to every run.

Use nullable fields where appropriate.

Do not insert fake strings such as:

```text
"N/A"
"none"
"unknown"
```

where SQL `NULL` is semantically correct.

---

# 7. Required Provenance

At minimum, every run must preserve the provenance already required by the project:

```text
run_id
git_sha
chunk_config_hash
embed_model
rerank_model
generation_model
split
eval_set_version
timestamp
metrics
```

Extend this where required to support the current repository's newer Phase 2 provenance.

In particular, also preserve:

```text
source_dataset_sha256
split_version
split_assignment_sha256
registry hash/version if relevant
truth-contract hash/version if relevant
index identity/config hash
```

A future developer must be able to determine whether two runs are legitimately comparable.

---

# 8. Split Contract

Allowed split values should be explicit.

Current semantic values:

```text
dev
test
ci
```

Potential build/diagnostic modes must not masquerade as an evaluation split.

Validate split values.

Do not permit arbitrary strings silently.

---

# 9. CI Semantics

`ci` means:

```text
Task 2.4's 200-question DEV-derived CI regression set
```

It must always be marked as:

```text
reportable_benchmark = false
```

or equivalent schema metadata.

CI results are allowed for:

```text
regression detection
continuous integration
sanity checks
```

CI numbers must not be represented as final benchmark results.

---

# 10. TEST Semantics

`test` means the protected Task 2.4 held-out set.

Any evaluation run with:

```text
split = "test"
```

must be linked to the sanctioned Task 2.4 TEST-access mechanism.

Task 2.5 must not create an alternate TEST reader that bypasses:

```text
src/eval/test_access.py
```

Do not weaken the maximum planned three-evaluation-access discipline.

---

# 11. TEST Run Accounting

Future TEST evaluation runs should be traceable between:

```text
test_access_log
```

and:

```text
eval_runs
```

Design a clear relationship.

For example:

```text
eval_runs.test_access_id
```

may reference the corresponding test-access event.

Do not duplicate independent TEST-access counters in multiple places.

Task 2.4 remains authoritative for TEST-access policy.

---

# 12. Per-Question Result Table

Create an authoritative per-question result table, conceptually:

```text
eval_question_results
```

Each evaluated question should produce one result row per run.

At minimum:

```text
run_id
question_id

category
subtype
answer_type

status

retrieval_status
generation_status

latency_ms
```

and relevant metric/diagnostic fields.

Use a composite uniqueness rule such as:

```text
(run_id, question_id)
```

to prevent duplicate scoring.

---

# 13. Do Not Store Only Aggregates

The primary evaluation evidence is:

```text
per-question result rows
```

Aggregate metrics must be computed from those rows.

Do not write:

```text
doc_recall@10 = 0.84
```

with no underlying question-level records.

Otherwise later error analysis and independent metric recomputation become impossible.

---

# 14. Retrieval Result Representation

Design a schema capable of recording retrieved candidates per question.

This may be a separate child table such as:

```text
eval_retrieved_items
```

Potential fields:

```text
run_id
question_id
rank

chunk_id
document_id / accession
cik

retrieval_score
rerank_score

retrieval_source
```

Do not flatten an arbitrary top-50 retrieval result into dozens of fixed columns like:

```text
chunk_1
chunk_2
...
chunk_50
```

Use rows.

---

# 15. Retrieval Rank Integrity

For each:

```text
run_id + question_id
```

enforce:

```text
rank starts at 1
rank is unique
rank is positive
```

Do not silently repair duplicate ranks.

Invalid result structures should fail validation.

---

# 16. Document Relevance vs Evidence Relevance

This distinction is non-negotiable.

The schema must support both:

```text
document-level relevance
chunk/evidence-level relevance
```

They are not interchangeable.

Use explicit fields/metrics such as:

```text
doc_hit_at_10
doc_first_hit_rank

chunk_hit_at_10
chunk_first_hit_rank
```

where relevant.

Do NOT create a generic:

```text
retrieval_hit
```

field whose granularity is ambiguous.

---

# 17. Document-Level Metrics

Task 1 established:

```text
doc_recall@10
```

The Phase 2 schema should support document metrics such as:

```text
doc_recall@k
doc_mrr
doc_ndcg@k
```

only where their definitions are explicitly implemented later.

Do not compute new metrics merely because the schema supports them.

Task 2.5 defines storage.

It does not fabricate evaluation results.

---

# 18. Chunk-Level Metrics

The project explicitly distinguishes:

```text
doc_recall@k
```

from:

```text
chunk_recall@k
```

`chunk_recall@k` applies only where real evidence-level gold labels exist.

Do not derive chunk relevance from:

```text
same document
same company
same section
semantic similarity
```

unless a later authoritative task defines such labels.

Task 2.5 must support chunk metrics without pretending they are currently available for all questions.

---

# 19. Metric Definitions Table

Create a centralized metric-definition registry/table or code contract.

For each metric record:

```text
metric_name
metric_version
level
description
higher_is_better
required_gold_type
applicable_categories
parameters
```

Examples:

```text
doc_recall@10
chunk_recall@10
doc_mrr
chunk_mrr
ndcg@10
numeric_exact_match
numeric_tolerance_match
correct_refusal
citation_format_compliance
citation_grounding
faithfulness
```

Do not mark all of these implemented.

The schema may reserve/support metrics.

Clearly distinguish:

```text
defined
implemented
available_for_current_gold
```

---

# 20. Metric Naming Must Be Explicit

Never store ambiguous metric names such as:

```text
recall
accuracy
hit_rate
```

Prefer granularity-bearing names:

```text
doc_recall@10
chunk_recall@10
numeric_exact_match
correct_refusal_rate
```

Metric identity must carry enough information to prevent accidental comparison of different definitions.

---

# 21. Metric Versioning

Metric definitions can evolve.

Therefore include:

```text
metric_version
```

or an equivalent schema/version reference.

Changing:

```text
cutoff k
normalization
numeric tolerance
document dedup behavior
relevance definition
```

must invalidate direct comparison with prior metric versions.

Do not silently reuse the same metric identifier for changed semantics.

---

# 22. Metric Value Table

Prefer a normalized aggregate metric table such as:

```text
eval_metrics
```

rather than adding one new database column whenever a metric is invented.

Possible schema:

```text
run_id
metric_name
metric_version

scope
category
subtype

k
value
numerator
denominator

notes
```

The precise design may differ.

Key requirement:

```text
future metrics must not require destructive schema migrations.
```

---

# 23. Scope of Aggregate Metrics

Metrics may apply to:

```text
overall
category
subtype
tag
year
intent
```

Do not hardcode hundreds of columns for each slice.

Use normalized dimensions or a carefully designed JSON field only if repository conventions support it.

Prefer typed columns for important dimensions.

---

# 24. Numerator / Denominator

Whenever possible store:

```text
numerator
denominator
```

alongside rates.

Example:

```text
doc_recall@10
value       = 0.970000
numerator   = 194
denominator = 200
```

This makes audit/recomputation easier.

Do not store only rounded percentages.

---

# 25. Numeric Answer Evaluation Fields

The evaluation schema must support numeric questions.

Potential per-question fields or child records should permit:

```text
expected_value
expected_unit

predicted_value
predicted_unit

numeric_parse_status
absolute_error
relative_error
exact_match
tolerance_match
```

Do not alter Task 2.3 gold values.

Task 2.5 only defines how future predictions/scores are stored.

---

# 26. Comparative / Derived Evaluation

Support evaluation records for:

```text
year_over_year_difference
cross_entity_comparison
```

without creating a second gold-answer definition.

Future scoring must compare the system answer against the Task 2.3 gold representation.

Do not recompute ground truth differently inside the evaluation schema layer.

---

# 27. Unanswerable Evaluation

The schema should support explicit expected/refusal behavior.

Possible fields:

```text
expected_behavior
observed_behavior
correct_refusal
```

Do not reduce refusal scoring to generic exact string matching.

The exact scoring implementation belongs to later metric work unless Task 2.5 explicitly owns it.

---

# 28. Adversarial Evaluation

Support:

```text
prompt_injection
financial_advice
off_scope
```

with behavior-oriented evaluation fields.

Potential structure:

```text
guard_triggered
refusal_observed
expected_behavior
behavior_match
```

Do not implement Phase 4 guards here.

The schema merely needs to accommodate later results.

---

# 29. Narrative Questions

Current narrative questions remain:

```text
pending_review
```

They are not part of current gold DEV/TEST evaluation.

The schema may support future narrative metrics such as:

```text
faithfulness
groundedness
human_score
judge_score
judge_model
judge_prompt_version
```

but Task 2.5 must not score the pending narrative questions.

Do not promote them.

---

# 30. LLM-as-Judge Provenance

For any future judge-based metric, the schema must preserve:

```text
judge_provider
judge_model
judge_model_revision if available
judge_prompt_version
judge_temperature
judge_raw_result / structured result reference
```

A judge score without judge provenance is invalid.

Do not run a judge during Task 2.5.

---

# 31. Generation Provenance

For runs involving generation preserve at least:

```text
generation_provider
generation_requested_model
generation_response_model
generation_prompt_version
generation_temperature
```

where available.

Do not assume requested model and response model are always identical.

Phase 1 already encountered provider/model provenance concerns; retain explicit values.

---

# 32. Retrieval Provenance

Future retrieval experiments must record enough detail to reproduce them.

At minimum support:

```text
retrieval_method
retrieval_config_hash

embedding_model
embedding_revision

index_type
index_config_hash

chunk_config_hash

candidate_k
final_k
```

Later hybrid experiments may additionally require:

```text
vector_weight
bm25_weight
fusion_method
```

Do not implement hybrid retrieval in Task 2.5.

Just ensure schema evolution can represent it.

---

# 33. Reranker Provenance

Support nullable:

```text
rerank_model
rerank_revision
rerank_config_hash
rerank_k
```

A no-reranker run should use:

```text
NULL
```

not a fake model name.

---

# 34. Router / CRAG Provenance

Support future nullable provenance such as:

```text
router_version
router_config_hash

crag_enabled
crag_config_hash
```

Again:

```text
schema support != feature implementation
```

Do not build router or CRAG code.

---

# 35. Latency Schema

Support stage-level timing.

Prefer a normalized structure such as:

```text
eval_stage_timings
```

with fields:

```text
run_id
question_id
stage
latency_ms
```

Potential stages:

```text
routing
embedding
retrieval
reranking
generation
guard
total
```

Do not force every stage to exist.

Do not conflate missing stage with zero milliseconds.

---

# 36. Cost / Token Usage

Support later generation cost accounting.

Fields may include:

```text
input_tokens
cached_input_tokens
output_tokens
total_tokens

provider_cost_usd
```

where actually available.

Missing provider metadata should remain NULL.

Never fabricate cost from assumed public prices inside the schema layer.

---

# 37. Error Taxonomy

Infrastructure/system errors must never become ordinary evaluation misses.

Create explicit result status/error semantics.

Suggested states:

```text
success
retrieval_error
generation_error
judge_error
timeout
invalid_output
schema_error
```

Use the authoritative current roadmap if it defines alternatives.

A question whose retriever crashed is not:

```text
doc_hit = false
```

It is an evaluation execution error.

---

# 38. Run Status

Run-level status should distinguish:

```text
running
complete
failed
partial
aborted
```

or repository-equivalent.

Never report aggregate metrics from an incomplete run without explicitly indicating partial status and denominator.

---

# 39. Transaction Safety

Evaluation persistence must be transactional enough to avoid a run appearing complete when only half of its question rows were written.

At minimum:

```text
create run -> running
write question results
write retrieved items / metrics
validate counts
mark run -> complete
```

If failure occurs:

```text
mark failed / rollback according to documented policy
```

Do not leave a falsely complete run.

---

# 40. Expected Question Count Validation

Every evaluation run must know the expected question count for its split/set.

Examples:

```text
CI:   200
DEV:  1,932 current gold questions
TEST: 828 current gold questions
```

For TEST, obtain records only through the sanctioned access path.

Do not hardcode these historical counts permanently if the evaluation-set version changes.

Read them from split/version metadata.

Before marking a run complete:

```text
persisted result count == expected question count
```

unless the run is explicitly partial.

---

# 41. Evaluation Set Identity

Preserve:

```text
eval_set_version
source_dataset_sha256
```

and split identity:

```text
split_version
split_assignment_sha256
question_set_sha256
```

This is crucial.

A result from:

```text
phase2-v1
```

cannot silently be compared against a future regenerated evaluation set.

---

# 42. Config Hash Compatibility

The project requires config hashes to prevent stale-artifact comparisons.

Add validation hooks for relationships such as:

```text
index.chunk_config_hash
==
run.chunk_config_hash
```

where both exist.

Task 2.5 may implement generic compatibility validation.

Do not rebuild indexes.

Do not run Phase 3 ablations.

---

# 43. Immutable Completed Runs

Once:

```text
status = complete
```

a run's semantic provenance and question results should not be silently overwritten.

Provide explicit failure or a deliberate replacement/new-run workflow.

Do not implement:

```text
INSERT OR REPLACE
```

for completed evaluation evidence unless the semantics are exceptionally well controlled.

Prefer a new `run_id`.

---

# 44. Schema Version

Define:

```text
evaluation_schema_version
```

For example:

```text
1
```

Store it both:

```text
in code/config
and in eval.duckdb metadata
```

A future incompatible migration must increment it.

---

# 45. Database Metadata Table

Consider a small schema metadata table:

```text
eval_schema_metadata
```

containing:

```text
schema_version
created_at_utc
migration_version
```

Do not put run-specific data here.

---

# 46. Safe Schema Migration

Because `eval.duckdb` already exists from Task 2.4, Task 2.5 must initialize/migrate idempotently.

Requirements:

```text
first initialization -> create missing Task 2.5 tables
second initialization -> no destructive changes
existing test_access_log -> preserved
existing rows -> preserved
```

Do not solve migration by deleting:

```text
artifacts/eval/eval.duckdb
```

and recreating it.

---

# 47. DuckDB Foreign-Key Practicality

Inspect what constraints DuckDB supports reliably in the currently installed version.

Use SQL constraints where practical.

Also enforce invariants in application-level validation.

Do not rely solely on database constraints if the engine's ALTER/migration support makes them fragile.

Document the choice.

---

# 48. Recommended Tables

The final exact design should follow repository conventions, but likely needs approximately:

```text
eval_schema_metadata

eval_runs

eval_question_results

eval_retrieved_items

eval_metrics

eval_stage_timings

test_access_log     # EXISTING, preserved
```

Potential additional table:

```text
metric_definitions
```

if a database-backed registry is appropriate.

Avoid creating many tables that have no current or planned use.

---

# 49. Python API

Create an authoritative evaluation-storage module such as:

```text
src/eval/eval_store.py
```

or the exact path required by `PROJECT_EXECUTION.md`.

It should expose narrow operations such as:

```python
initialize_schema(...)
start_run(...)
record_question_result(...)
record_retrieved_items(...)
record_metric(...)
record_stage_timing(...)
complete_run(...)
fail_run(...)
get_run(...)
```

Exact naming may differ.

Do not expose raw ad-hoc SQL throughout later scripts if one centralized storage API can prevent inconsistent runs.

---

# 50. Validation Layer

Create functions that validate:

```text
split
status
metric names/versions
run provenance
question IDs
duplicate result rows
retrieval ranks
metric ranges where applicable
question count
test-access linkage
```

Fail loudly on malformed evaluation evidence.

---

# 51. Metric Range Validation

Where mathematically valid, enforce basic ranges:

```text
recall -> [0,1]
MRR    -> [0,1]
nDCG   -> [0,1]
rates   -> [0,1]
latency -> >=0
rank    -> >=1
counts  -> >=0
```

Do not apply `[0,1]` to arbitrary numeric metrics such as:

```text
absolute_error
latency
cost
```

---

# 52. Metric Applicability

Do not pretend every metric applies to every question.

Examples:

```text
numeric_exact_match:
numeric / comparative only

correct_refusal:
unanswerable / relevant adversarial categories

faithfulness:
narrative/generation categories

chunk_recall:
only questions with verified chunk-level gold
```

Represent non-applicable metrics as absent/NULL, not zero.

Zero means the metric was applicable and the system scored zero.

---

# 53. Metric Definition vs Result

Keep separate:

```text
metric definition
```

and:

```text
metric observation/value
```

Do not duplicate metric semantics in every run record.

---

# 54. Per-Question Diagnostics

Support useful diagnostics such as:

```text
doc_first_hit_rank
chunk_first_hit_rank
retrieved_count

answer_text reference / bounded field
citation_count

refusal_detected
numeric_parse_status
```

Do not require every diagnostic for every run.

The schema should allow sparse applicability.

---

# 55. Raw Answers and Large Payloads

Do not bloat `eval.duckdb` unnecessarily with huge contexts.

Reasonable storage:

```text
system answer text
short structured outputs
retrieved IDs/scores
```

Avoid duplicating:

```text
entire source filings
entire retrieved chunk corpus
full prompts with large contexts
```

If large artifacts are required later, store:

```text
artifact path
artifact hash
```

instead.

---

# 56. Question Content

Prefer storing:

```text
question_id
```

as the foreign semantic identity.

Do not duplicate frozen question text/gold answers unnecessarily in every run.

The evaluation set already owns question/gold truth.

If a denormalized snapshot is needed for audit reasons, document why.

---

# 57. Do Not Touch Gold Labels

Task 2.5 must not change:

```text
questions
expected values
expected behaviors
split assignments
CI selection
pending-review status
```

It only defines result storage.

---

# 58. No TEST Evaluation

Task 2.5 must use:

```text
synthetic fixtures
CI schema examples
DEV-safe examples
```

for testing.

Do NOT call:

```text
load_test_set(... evaluation_access ...)
```

to exercise evaluation storage.

Task 2.5 must consume:

```text
0 / 3
```

official TEST runs.

---

# 59. Existing TEST Access Log Regression

Explicitly verify Task 2.5 preserves:

```text
Task 2.4 build_validation log
```

and all current `test_access_log` semantics.

After migration:

```text
existing rows before == existing rows after
```

for the current database.

Do not accidentally reset run budget accounting.

---

# 60. Synthetic Evaluation Run

Create a deterministic synthetic integration smoke run using a temporary DuckDB database.

Example:

```text
split = ci
questions = small synthetic set
```

Test:

```text
initialize
start run
write question results
write retrieved items
write metrics
write timings
complete run
read back
```

Do not write fake experiment results into the real production `eval.duckdb` merely for tests.

---

# 61. Optional Real CI Schema Smoke

If useful, perform a non-model, metadata-only validation against:

```text
results/phase_2_4_ci_golden.json
```

Examples:

```text
validate question IDs
validate expected question count
validate provenance hashes
```

Do not execute retrieval or generation.

---

# 62. Independent Schema Verification

After implementation, inspect the real `eval.duckdb` directly using raw DuckDB SQL rather than the production Python abstraction.

Verify:

```text
expected tables exist
expected columns/types exist
test_access_log preserved
schema version correct
no unexpected rows inserted
```

Do not use only `eval_store.py` to prove `eval_store.py` worked.

---

# 63. Schema Snapshot

Generate a small tracked schema artifact such as:

```text
results/phase_2_5_evaluation_schema.json
```

Include:

```text
evaluation_schema_version
table names
columns
types
primary/unique keys
semantic relationships
metric registry version
database path
```

Do not include private TEST content.

---

# 64. Schema Hash

Compute a deterministic semantic:

```text
evaluation_schema_hash
```

from canonical schema/metric definitions.

Do not hash:

```text
created timestamp
database file bytes
DuckDB physical layout
```

The schema hash should represent logical evaluation semantics.

---

# 65. Documentation

Create:

```text
project_plan/PHASE2_EVALUATION_SCHEMA.md
```

Document:

- objective;
- schema version;
- database location;
- table relationships;
- run lifecycle;
- required provenance;
- split semantics;
- TEST linkage;
- CI semantics;
- question-result model;
- retrieval-result model;
- metric model;
- doc vs chunk relevance distinction;
- error taxonomy;
- latency/cost support;
- model/judge provenance;
- schema migration policy;
- immutability policy;
- validation commands;
- known deferred features.

Include a compact relationship diagram such as:

```text
eval_runs
   |
   +-- eval_question_results
   |       |
   |       +-- eval_retrieved_items
   |       +-- eval_stage_timings
   |
   +-- eval_metrics

test_access_log
   |
   +-- linked to TEST eval_runs
```

---

# 66. Explicit Reporting Rule

Document prominently:

```text
doc_recall@k != chunk_recall@k
```

Document-level recall must never be labelled simply:

```text
retrieval recall
```

when evidence-level labels are not available.

The stronger metric is:

```text
chunk_recall@k
```

on the verified evidence-labelled subset.

Until those labels exist, leave chunk metrics unavailable.

---

# 67. No Fake Metric Values

Task 2.5 should create:

```text
schema
definitions
validation
storage APIs
tests
documentation
```

It should NOT create fake aggregate records such as:

```text
chunk_recall@10 = 0
faithfulness = 1
correct_refusal = 100%
```

because those evaluations have not run.

NULL/unavailable is not failure.

---

# 68. Do Not Re-run Phase 1 Baseline as Task 2.5 Evidence

Task 1.10 already recorded:

```text
doc_recall@10 = 194/200 = 0.97
```

Do not rerun it just to populate the new schema unless `PROJECT_EXECUTION.md` explicitly requires migration/import.

If historical result import is desirable, create an explicit migration design rather than pretending the old run originally used the new schema.

---

# 69. Historical Result Import Policy

Decide/document whether earlier Phase 1 results are:

```text
A. left as historical JSON artifacts
or
B. imported as legacy runs
```

Do not silently import them.

If imported, mark:

```text
legacy_import = true
```

and preserve original metric semantics exactly.

Do not rewrite historical provenance.

Prefer leaving them untouched unless the execution plan explicitly wants migration.

---

# 70. Tests

Add comprehensive tests, likely:

```text
tests/test_evaluation_schema.py
tests/test_eval_store.py
```

At minimum cover:

### Initialization

```text
fresh DB initializes
existing DB migrates idempotently
existing test_access_log preserved
schema initialization twice is safe
```

### Run lifecycle

```text
start run
complete run
fail run
cannot complete nonexistent run
cannot silently overwrite completed run
```

### Provenance

```text
required provenance enforced
valid split enforced
eval-set identity preserved
config hashes preserved
```

### Question results

```text
one row per run/question
duplicate run/question rejected
unknown run rejected
valid status accepted
invalid status rejected
```

### Retrieval results

```text
rank starts >=1
duplicate rank rejected
document/chunk IDs nullable only according to contract
scores retain precision
```

### Metrics

```text
metric definition registered
metric version required
numerator/denominator consistency
rate range validation
non-applicable metric remains absent/NULL
```

### Doc vs chunk distinction

```text
doc metric cannot masquerade as chunk metric
chunk metric requires appropriate gold-label declaration
```

### CI

```text
ci accepted as split
ci marked non-reportable
```

### TEST

```text
TEST run requires sanctioned access linkage
Task 2.4 access log untouched
no fourth-run budget bypass introduced
```

### Determinism

```text
same logical schema -> same schema hash
same metric definitions -> same metric-registry hash
```

### Transactions

```text
partial failure cannot leave run marked complete
```

---

# 71. Real Database Migration Test

Create a controlled local-data integration test that:

1. copies the real `eval.duckdb` to a temporary location;
2. records the existing `test_access_log`;
3. initializes/migrates Task 2.5 schema on the copy;
4. verifies existing access rows are unchanged;
5. verifies all new tables;
6. verifies initialization is idempotent;
7. performs a synthetic run on the copied DB.

Do NOT destructively test migration against the only real DB copy.

---

# 72. Real Database Initialization

After copy-based migration tests pass, initialize the real:

```text
artifacts/eval/eval.duckdb
```

using the same tested migration path.

Before and after, verify:

```text
test_access_log row count
test_access_log semantic rows/hash
```

No previous rows may disappear or change.

Do not add fake evaluation runs to the real DB.

---

# 73. No Network / LLM / GPU

Task 2.5 requires:

```text
no OpenRouter
no OpenAI
no Anthropic
no SEC calls
no web calls
no Hugging Face download
no GPU inference
```

This is schema/infrastructure work.

No API credits should be spent.

---

# 74. Frozen Evaluation Artifacts

Do not modify:

```text
results/phase_2_3_evaluation_dataset.json
results/phase_2_3_evaluation_dataset_summary.json
configs/phase_2_3_evaluation_dataset.json

results/phase_2_4_dev.json
results/phase_2_4_ci_golden.json
results/phase_2_4_split_manifest.json
results/phase_2_4_split_summary.json
results/phase_2_4_pending_review_assignments.json

artifacts/eval/phase_2_4_test.json
```

`eval.duckdb` may be schema-migrated because that is Task 2.5's purpose, but existing Task 2.4 access-log evidence must remain intact.

---

# 75. Task 2.4 Regression Gate

Verify:

```text
DEV = 1,932 gold
TEST = 828 gold
CI = 200
DEV/TEST CIK overlap = 0
pending narratives = 35 DEV / 15 TEST
official TEST eval runs consumed = 0
```

Task 2.5 must not alter these.

---

# 76. Task 2.1–2.3 Regression Gate

Verify no semantic change to:

```text
src/eval/truth_contract.py
src/eval/tag_registry.py
configs/eval_tags.yaml

src/eval/evaluation_dataset.py
scripts/build_evaluation_dataset.py
Task 2.3 configs/results
```

No ground-truth or question-generation semantics belong in Task 2.5.

---

# 77. Phase 1 Regression Gate

Verify no unintended change to:

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
Phase 1 results/configs
```

Do not rerun Task 1.7a.

---

# 78. Repository Structure

Update narrowly:

```text
project_plan/REPOSITORY_STRUCTURE.md
```

Likely new files:

```text
src/eval/eval_store.py
src/eval/evaluation_schema.py

scripts/init_evaluation_schema.py

tests/test_evaluation_schema.py
tests/test_eval_store.py

results/phase_2_5_evaluation_schema.json

project_plan/PHASE2_EVALUATION_SCHEMA.md
```

Exact architecture should follow current repository conventions.

Do not create unnecessary files merely to match this example.

---

# 79. Progress.md

Append:

```text
## YYYY-MM-DD — Phase 2.5 Evaluation Schema
```

Include:

```text
Objective
Initial State
Existing eval.duckdb State
Authoritative Schema Decisions
Schema Version
Schema Hash
Tables Created
Run Provenance
Question-Level Result Contract
Retrieval Result Contract
Metric Registry
Document vs Chunk Relevance
Run Lifecycle
TEST Integration
CI Semantics
Migration Safety
Independent DB Verification
Tests
Regression Gates
Files Created/Modified
Git
Result
Phase Status
```

Do not rewrite previous Phase 2 history.

---

# 80. Git / Security

Before commit:

```bash
git status --short
git diff
git diff --stat
git add -n .
```

Verify no:

```text
artifacts/eval/eval.duckdb
artifacts/eval/phase_2_4_test.json
data/
.venv/
.env
credentials
```

are staged.

The schema summary/code/docs/tests may be tracked.

The live evaluation database remains an ignored runtime artifact.

Run secret/personal-path scan.

---

# 81. Commit

When all gates pass, create one coherent commit.

Suggested message:

```text
Add Phase 2 evaluation schema
```

Do not create a Phase 2 completion tag.

Do not push if no remote exists.

---

# 82. Stop Conditions

STOP rather than inventing semantics if:

### A. PROJECT_EXECUTION.md defines a different Task 2.5 contract

Follow it and document the discrepancy.

### B. Existing eval.duckdb cannot be migrated safely

Do not delete/recreate it.

### C. Migration changes existing test_access_log rows

Hard failure.

### D. Metric granularity is ambiguous

Do not invent a generic `recall`.

### E. Chunk-level relevance labels do not yet exist

Leave chunk metrics unavailable.

### F. TEST evaluation would be required

Do not consume an official TEST run.

### G. A schema field requires a later feature decision

Make it nullable/deferred rather than implementing the feature early.

### H. Existing Task 2.3/2.4 hashes no longer match

Stop and investigate.

---

# 83. Acceptance Criteria

Task 2.5 is complete only when:

```text
[ ] existing eval.duckdb inspected before modification
[ ] Task 2.4 test_access_log preserved exactly

[ ] evaluation schema version defined
[ ] evaluation schema hash deterministic

[ ] eval_runs storage implemented
[ ] per-question result storage implemented
[ ] ranked retrieval-result storage implemented
[ ] aggregate metric storage implemented
[ ] stage timing storage implemented or explicitly deferred by roadmap

[ ] run_id unique
[ ] (run_id, question_id) unique
[ ] retrieval ranks validated

[ ] git_sha recorded
[ ] split recorded
[ ] eval_set_version recorded
[ ] source_dataset_sha256 recorded
[ ] split version/hash recorded
[ ] chunk/index/retrieval provenance supported
[ ] model provenance supported

[ ] metric definitions versioned
[ ] doc_recall and chunk_recall explicitly distinct
[ ] unsupported chunk metrics remain unavailable
[ ] numerator/denominator supported
[ ] category/subtype metric slicing supported

[ ] numeric evaluation representation supported
[ ] correct-refusal representation supported
[ ] future narrative/judge provenance supported
[ ] latency/cost/token metadata supported without fabrication

[ ] infrastructure errors distinct from evaluation misses
[ ] run lifecycle implemented
[ ] incomplete run cannot masquerade as complete

[ ] CI split supported and marked non-reportable
[ ] TEST runs require sanctioned access linkage
[ ] no TEST evaluation performed
[ ] official TEST runs consumed remains 0 / 3

[ ] migration idempotent
[ ] migration tested on copy of real eval.duckdb
[ ] real DB initialized only after copy test passes
[ ] existing Task 2.4 access log unchanged

[ ] schema summary artifact created
[ ] independent raw-SQL schema verification passes

[ ] portable tests pass
[ ] local-data migration integration test passes
[ ] full suite passes

[ ] Task 2.4 split unchanged
[ ] Task 2.3 dataset unchanged
[ ] Task 2.1/2.2 semantics unchanged
[ ] Phase 1 regression passes

[ ] no network
[ ] no LLM
[ ] no GPU
[ ] no API spend

[ ] documentation updated
[ ] Progress.md appended
[ ] secret scan clean
[ ] git staging dry-run safe
[ ] coherent Task 2.5 commit created
```

---

# 84. Final Console Summary

Print:

```text
PHASE 2.5 — EVALUATION SCHEMA
==============================

Schema:
  version:                       <version>
  hash:                          <hash>
  database:                      artifacts/eval/eval.duckdb

Tables:
  eval_schema_metadata:          PASS
  eval_runs:                     PASS
  eval_question_results:         PASS
  eval_retrieved_items:          PASS
  eval_metrics:                  PASS
  eval_stage_timings:            PASS / DEFERRED
  test_access_log preserved:     PASS

Run provenance:
  git SHA:                       SUPPORTED
  eval-set version/hash:         SUPPORTED
  split version/hash:            SUPPORTED
  chunk config hash:             SUPPORTED
  index/retrieval config:        SUPPORTED
  embedding model:               SUPPORTED
  reranker model:                SUPPORTED
  generation model:              SUPPORTED
  router/CRAG provenance:        SUPPORTED / NULLABLE

Metric contract:
  metric versioning:             PASS
  numerator/denominator:         PASS
  doc vs chunk distinction:      PASS
  chunk metrics without gold:    NOT ALLOWED
  CI reportable:                 NO

TEST discipline:
  test_access_log rows preserved:<count>
  official TEST runs used:       0 / 3
  TEST evaluation performed:     NO

Migration:
  copy migration test:           PASS
  idempotent initialization:     PASS
  real DB initialization:        PASS
  previous access evidence:      UNCHANGED

Validation:
  independent SQL inspection:    PASS
  Task 2.4 regression:           PASS
  Task 2.3 regression:           PASS
  Task 2.1/2.2 regression:       PASS
  Phase 1 regression:            PASS

Tests:
  portable:                      <result>
  full:                          <result>

FINAL RESULT:
PASS / PASS WITH WARN / FAIL / BLOCKED

PHASE 2 STATUS:
IN PROGRESS

NEXT:
<exact next task from PROJECT_EXECUTION.md>
```

---

# Final Principle

Task 2.5 is not about producing a better score.

It is about making future scores **auditable and comparable**.

A metric is not trustworthy unless we can answer:

```text
Which questions were evaluated?
Which split?
Which dataset version?
Which code?
Which chunk configuration?
Which index?
Which embedding model?
Which reranker?
Which generator?
Which metric definition?
Which individual questions succeeded or failed?
Was TEST accessed legitimately?
```

Therefore:

```text
Do not store only aggregate metrics.
Do not overwrite completed runs.
Do not convert execution errors into misses.
Do not conflate document relevance with evidence relevance.
Do not score pending narrative questions.
Do not run TEST.
Do not create fake metrics.
Do not bypass Task 2.4 TEST-access controls.
Do not rebuild or optimize retrieval.
```

Build the measurement infrastructure now so every later Phase 3 comparison is defensible.