# Phase 2 Evaluation Schema

Established in Task 2.5. Defines the authoritative evaluation-result
schema and storage contract that every later retrieval, generation,
routing, CRAG, reranking, and end-to-end experiment must use. Task 2.5
builds measurement infrastructure only - it runs no retrieval, no
generation, no TEST evaluation, and produces zero real metric values.

## Objective

A future developer adding a Phase 3 experiment should be able to open
this document, call `src.eval.eval_store`, and know exactly how to
record a reproducible, auditable result - without inventing a new
ad-hoc table or column.

## Relationship to `PROJECT_EXECUTION.md`'s Task 2.5 section

`PROJECT_EXECUTION.md` describes Task 2.5 narrowly - "freeze fields
needed for reproducible experiments" (`question_id`, `question`,
`question_type`, `expected_answer`, `unit`, `cik`, `year`,
`accession/adsh`, `tag`, `source`, `evidence label`, `split`,
`eval_set_version`). Every one of those fields already exists, frozen,
in Task 2.3's question records and Task 2.4's split manifest - Task 2.5
does not need to "freeze" them again. This task's own prompt asks for
something larger and consistent with that field list: a full
run/result/metric storage layer so that *future experiment output*
(not just the frozen questions) is equally reproducible and auditable.
The two are complementary, not conflicting - no discrepancy was found
that required stopping.

## Schema version and hash

```text
evaluation_schema_version:  1
evaluation_schema_hash:     13aec6b2d80d1be70f3d8117bf4914274605910697f88d058f93bfe933332338
```

`src.eval.evaluation_schema.compute_evaluation_schema_hash()` hashes a
canonical dict built directly from the same Python data structures used
to generate the `CREATE TABLE` statements (table/column
names/types/nullability/CHECK constraints) plus the metric-definition
registry plus the valid-enum-value lists - never DDL string formatting,
never a timestamp, never the DuckDB file's physical bytes. A semantic
change (add a column, change a CHECK, add/remove a metric) always
changes the hash; whitespace/formatting changes to `create_sql()` never
do (verified deterministic - `tests/test_evaluation_schema.py`).

## Database location

```text
artifacts/eval/eval.duckdb   (GITIGNORED - already true from Task 2.4)
```

Created by Task 2.4 for `test_access_log`. Task 2.5 extends it
idempotently via `src.eval.eval_store.initialize_schema()` - never
deletes or recreates the file.

## Table relationships

```text
eval_runs
   |
   +-- eval_question_results  (run_id, question_id)
   |       |
   |       +-- eval_retrieved_items  (run_id, question_id, rank)
   |       +-- eval_stage_timings    (run_id, question_id, stage)
   |
   +-- eval_metrics  (run_id, metric_name, metric_version, scope, ...)

metric_definitions   (metric_name, metric_version)  - referenced by eval_metrics,
                                                       not owned by any one run

eval_schema_metadata  (schema_version)  - one row per schema version ever seen

test_access_log   (EXISTING, Task 2.4, untouched)
   |
   +-- eval_runs.test_access_id  (nullable FK-by-convention, populated
                                   only when eval_runs.split = 'test')
```

## Run lifecycle

```text
start_run(...)               -> INSERT eval_runs, status="running"
record_question_result(...)  -> one row per (run_id, question_id)
record_retrieved_items(...)  -> ranked candidates for one question
record_metric(...)           -> one aggregate metric observation
record_stage_timing(...)     -> one per-question per-stage latency
complete_run(...)            -> validates persisted count == expected, status="complete" (or "partial")
fail_run(...)                -> status="failed", error_type/error_message recorded
```

Every write function except `start_run` first checks the run is
`status="running"` (`RunNotRunningError` otherwise) - **completed and
failed runs are immutable**. There is no `INSERT OR REPLACE` path for
evaluation evidence; a corrected re-run gets a new `run_id`.

**Transaction-safety policy** (Section 39, deliberate, documented
choice): a run that crashes mid-write without `complete_run()` or
`fail_run()` being called stays `status="running"` forever. This project
does not implement an automatic "mark stale running runs as failed"
sweep - a `running` run with a very old `timestamp_utc` is itself the
signal that something went wrong, and a human/later script can call
`fail_run()` explicitly. This avoids the alternative failure mode of
auto-marking a run failed while it is still legitimately in progress.

## Required provenance

Every `eval_runs` row carries, at minimum (NOT NULL):
`run_id, timestamp_utc, split, eval_set_version, source_dataset_sha256,
split_version, split_assignment_sha256, question_set_sha256,
question_count, expected_question_count, metric_schema_version, status`.

Nullable, populated where applicable: `git_sha, chunk_config_hash,
index_config_hash, retrieval_config_hash, embed_model,
embed_model_revision, rerank_model, rerank_model_revision,
rerank_config_hash, rerank_k, generation_provider,
generation_requested_model, generation_response_model,
generation_prompt_version, generation_temperature, router_version,
router_config_hash, crag_enabled, crag_config_hash, test_access_id,
error_type, error_message, completed_at_utc`. A run with no reranker
stores `rerank_model = NULL`, never a fake model name (Section 33).

## Split semantics

`eval_runs.split` is CHECK-constrained to exactly `('dev', 'test',
'ci')` - enforced both at the SQL level and in
`evaluation_schema.validate_split()` before any insert, so an invalid
value is rejected before it ever reaches the database.

- **`dev`** - the 1,932-question Task 2.4 DEV set. Freely used for
  tuning, ablations, error analysis.
- **`ci`** - Task 2.4's 200-question DEV-derived CI regression set.
  `results/phase_2_4_ci_golden.json` itself carries
  `"reportable_benchmark": false`; no headline result may ever cite a
  `split="ci"` run.
- **`test`** - the 828-question Task 2.4 held-out set. See TEST
  integration below.

## TEST integration

`eval_runs.test_access_id` links a `split="test"` run to the exact
`test_access_log` row (from `src.eval.test_access.load_test_set()`) that
authorized reading TEST content. `start_run(split="test", ...)`
**requires** `test_access_id` and verifies, before inserting anything,
that a row with that `access_id` and `kind='evaluation_access'` exists
in `test_access_log` (`TestAccessLinkageError` otherwise). Task 2.5
introduces no alternate TEST reader - `src/eval/test_access.py` remains
the only sanctioned path, and `eval_store.py` never imports it and never
writes to `test_access_log` itself (verified by
`tests/test_eval_store.py::test_no_fourth_run_budget_bypass_introduced`).
The three-evaluation-run budget is entirely Task 2.4's responsibility;
Task 2.5 only records which access authorized a given run, so a future
developer can join `eval_runs` to `test_access_log` and see exactly
which of the three evaluation runs (`baseline_rerank`, `router_crag`,
`final`) produced which metrics.

Task 2.5 itself never calls `load_test_set()` - it consumed **0/3**
official TEST evaluation runs (verified: `test_access_log` held exactly
2 `build_validation` rows, from Task 2.4's determinism check, both
before and after Task 2.5's migration and all Task 2.5 testing).

## Question-level result contract

`eval_question_results` - one row per `(run_id, question_id)`
(`PRIMARY KEY`, duplicate insert raises `DuplicateResultError`). Carries
`category`/`subtype`/`answer_type` (denormalized from the question, not
re-derived), a required `status` (CHECK-constrained to `success`,
`retrieval_error`, `generation_error`, `judge_error`, `timeout`,
`invalid_output`, `schema_error` - Section 37's error taxonomy),
`retrieval_status`/`generation_status`, `latency_ms`, document-vs-chunk
first-hit ranks, numeric-answer evaluation fields
(`expected_value`/`predicted_value`/`absolute_error`/`exact_match`/
`tolerance_match`/...), behavior fields for unanswerable/adversarial
(`expected_behavior`/`observed_behavior`/`correct_refusal`/
`guard_triggered`/`behavior_match`), token/cost fields, and full
judge-provenance fields (`judge_provider`/`judge_model`/
`judge_prompt_version`/`judge_temperature`/...). **A question whose
retriever crashed is `status="retrieval_error"`, never
`doc_hit_at_10=false`** - infrastructure failure is never silently
converted into an evaluation miss (Section 37/10 of the schema
principles).

Only `question_id` is stored as the semantic link to a question - the
schema never duplicates frozen question text or gold values (Section
56). `answer_text` is a bounded field for the system's own short
generated answer, not the retrieved context; large payloads (full
filings, full retrieved chunk corpus, full prompts) are never stored
here - if a future task needs to keep large artifacts, it stores a path
and a hash, not the content (Section 55).

## Retrieval-result contract

`eval_retrieved_items` - one row per `(run_id, question_id, rank)`,
never a flattened `chunk_1..chunk_50` column layout. `rank` is
CHECK-constrained `>= 1` at the SQL level and validated in Python before
any row is written; duplicate ranks for the same `(run_id,
question_id)` are rejected outright (`ValueError`), never silently
repaired. `chunk_id`/`document_id`/`cik` are nullable so a
document-level-only retrieval result can still be recorded honestly.

## Metric model

`eval_metrics` stores individual aggregate observations - `run_id`,
`metric_name`, `metric_version`, a `scope` (CHECK-constrained to
`overall`/`category`/`subtype`/`tag`/`year`/`intent`), the matching
dimension value, an optional `k`, `value`, `numerator`, `denominator`,
and free-text `notes`. `record_metric()` requires the
`(metric_name, metric_version)` pair to already exist in
`metric_definitions` - an unregistered metric name is rejected
(`ValueError`), preventing an ambiguous ad-hoc metric string from ever
entering the results. Duplicate `(run_id, metric_name, metric_version,
scope, dimension, k)` combinations are rejected
(`DuplicateResultError`). `numerator`/`denominator` are validated for
basic consistency (`0 <= numerator <= denominator`) whenever both are
supplied, so recomputation from raw counts is always possible.

## Metric-definition registry

`src.eval.evaluation_schema.METRIC_DEFINITIONS` (mirrored into the
`metric_definitions` table by `initialize_schema()`) is the single
source of truth for metric semantics, versioned independently of any
run. Each entry distinguishes three things that must never be conflated:

```text
defined                      the schema/registry knows this metric exists
implemented                  real scoring code exists in this repo TODAY
available_for_current_gold   the gold labels this metric needs exist TODAY
```

| metric | level | implemented | available_for_current_gold |
|---|---|---|---|
| `doc_recall@10` | document | **true** (Task 1.10) | true (Task 1.9 gold) |
| `chunk_recall@10` | chunk | false | **false** (no evidence-level gold) |
| `doc_mrr` | document | false | true |
| `chunk_mrr` | chunk | false | false |
| `doc_ndcg@10` | document | false | true |
| `numeric_exact_match` | answer | false | true (Task 2.3 gold) |
| `numeric_tolerance_match` | answer | false | true |
| `correct_refusal_rate` | behavior | false | true |
| `citation_format_compliance` | answer | **true** (Task 1.7a/1.8) | true |
| `citation_grounding` | answer | false | false |
| `faithfulness` | narrative | false | **false** (narrative is pending_review) |

No metric is marked `implemented=true` unless real scoring code already
computes it elsewhere in this repository - Task 2.5 fabricates no
results and marks nothing implemented merely because the schema can now
store it (Section 17/67).

## Document relevance vs. chunk/evidence relevance

Never conflated. `eval_question_results` carries separate
`doc_first_hit_rank` and `chunk_first_hit_rank` columns; the metric
registry carries separate `doc_recall@10`/`chunk_recall@10` and
`doc_mrr`/`chunk_mrr` entries. There is no generic `retrieval_hit` field
anywhere in this schema. **Until chunk/evidence-level gold labels exist
in a later authoritative task, every `chunk_*` metric's
`available_for_current_gold` stays `false` and must never be populated**
- reporting a `chunk_recall@10` number today, derived from "same
document" or "same company" proxies, would misrepresent the strength of
the evidence and is explicitly prohibited (Section 16/18/66).

## Error taxonomy

`eval_question_results.status` (CHECK-constrained):
`success, retrieval_error, generation_error, judge_error, timeout,
invalid_output, schema_error`. `eval_runs.status`:
`running, complete, failed, partial, aborted`.

## Migration safety

`initialize_schema()` only issues `CREATE TABLE IF NOT EXISTS` and
idempotent `INSERT ... WHERE NOT EXISTS`-guarded metadata/metric-registry
seeding - it never drops, truncates, or alters `test_access_log` or any
Task 2.5 table. Verified twice: once against a **copy** of the real
`eval.duckdb` (`scripts/init_evaluation_schema.py` step 1, and
`tests/test_eval_store.py::test_real_db_migration_on_copy`), and only
after that passed, against the real database itself. `test_access_log`
row count and content were byte-identical before and after in both
cases (2 rows, both `kind="build_validation"` from Task 2.4's own
determinism checks).

## Immutability policy

Once `status="complete"` (or `"failed"`), no write function will touch
that run's rows again - every write function calls `_require_running()`
first. There is no destructive-replace path. A corrected/re-run
experiment always gets a fresh `run_id`.

## Validation commands

```bash
python scripts/init_evaluation_schema.py
python -m pytest tests/test_evaluation_schema.py tests/test_eval_store.py -q
python -m pytest -q
python -c "import duckdb; con = duckdb.connect('artifacts/eval/eval.duckdb', read_only=True); print(con.execute('select table_name from information_schema.tables').fetchall())"
```

## Known deferred features

- No metric is actually computed by Task 2.5 - it defines storage only.
  Phase 3 experiments populate `eval_metrics` for the first time.
- `chunk_recall@10`/`chunk_mrr`/`citation_grounding`/`faithfulness` stay
  `available_for_current_gold=false` until a later authoritative task
  creates evidence-level gold labels or a human-reviewed narrative gold
  set.
- No stale-`running`-run auto-failure sweep exists (see Transaction-
  safety policy above) - deliberate, not an oversight.
- `router_version`/`router_config_hash`/`crag_enabled`/`crag_config_hash`
  are already real nullable `eval_runs` columns, settable today via
  `start_run(**provenance)`, even though no router/CRAG code exists yet
  - schema support, not feature implementation (Section 34).
  Hybrid-retrieval fields (`vector_weight`, `bm25_weight`,
  `fusion_method`, Section 32) are NOT yet columns - `start_run()`
  rejects any keyword not already in `eval_runs`' column set. Adding
  them later is a plain additive `ALTER TABLE ... ADD COLUMN` migration
  (DuckDB supports this) that leaves every existing row's new column
  `NULL` - no destructive migration is needed when hybrid retrieval is
  actually implemented.
