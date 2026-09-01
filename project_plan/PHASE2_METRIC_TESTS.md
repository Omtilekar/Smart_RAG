# Phase 2 Metric Unit Tests

Established in Task 2.6. Implements and hand-verifies the deterministic
metric formulas `PROJECT_EXECUTION.md`'s Task 2.6 section requires
(Recall@K, document Recall@K, chunk Recall@K, MRR, nDCG@K, exact match,
refusal metrics), so that later Phase 3 experiments cannot produce
plausible-looking but mathematically wrong results. No retrieval, no
generation, no TEST evaluation, no LLM, no GPU - this task runs on tiny
hand-constructed fixtures whose answers are known before the
implementation runs.

## Objective

A future developer changing `src/eval/metrics.py` should be able to run
`pytest tests/test_metrics.py` and trust that a formula regression (a
wrong log base, an off-by-one cutoff, MRR silently becoming mean rank)
is caught immediately - because every expected value in that file is
computed by hand (or by raw `math.log2` arithmetic written directly in
the test), never by calling the function under test to produce its own
expected answer.

## `PROJECT_EXECUTION.md` contract

```text
Recall@K
document Recall@K
chunk Recall@K
MRR
nDCG@K
exact match
refusal metrics when applicable
```

This task's own detailed prompt elaborates the same list with edge
cases, applicability rules, and persistence requirements - materially
consistent, not narrower or conflicting. No `PROJECT_EXECUTION.md`
discrepancy was found.

## Metric registry: before and after

Task 2.5 already registered all 11 metric names; Task 2.6 only changes
which ones have a real, hand-tested implementation (`implemented`), and
never touches `available_for_current_gold` except where genuinely
justified by what gold labels already exist.

| Metric | implemented (before) | implemented (after) | available_for_current_gold |
|---|---|---|---|
| `doc_recall@10` | true (Task 1.10) | true (unchanged) | true |
| `chunk_recall@10` | false | **true** | **false** (no chunk gold) |
| `doc_mrr` | false | **true** | true |
| `chunk_mrr` | false | **true** | **false** (no chunk gold) |
| `doc_ndcg@10` | false | **true** | true |
| `numeric_exact_match` | false | **true** | true |
| `numeric_tolerance_match` | false | false (unchanged - deferred) | true |
| `correct_refusal_rate` | false | **true** | true |
| `citation_format_compliance` | true (Task 1.7a/1.8) | true (unchanged) | true |
| `citation_grounding` | false | false (unchanged - deferred) | false |
| `faithfulness` | false | false (unchanged - deferred) | false |

**`chunk_recall@10` and `chunk_mrr` are implemented=true /
available_for_current_gold=false simultaneously** - this is the exact
example Task 2.5's own design anticipated (a formula can be
mathematically correct and hand-tested while the real gold labels it
needs do not exist yet). Nothing here promotes narrative to gold, adds
chunk-level gold, or claims TEST/DEV was scored.

## Scope decision: what Task 2.6 owns

**Implemented** (new `src/eval/metrics.py`, this task):
`chunk_recall@10`'s and `chunk_mrr`'s formulas (generic `first_hit_rank`/
`reciprocal_rank`, applied to chunk-granularity IDs), `doc_mrr`,
`doc_ndcg@10`, `numeric_exact_match`, `correct_refusal_rate`, plus the
shared `aggregate_rate` primitive.

**Deliberately deferred, not implemented here:**

- **`numeric_tolerance_match`** - no tolerance policy (absolute/relative,
  boundary inclusivity) is frozen anywhere in the authoritative roadmap.
  Per the task's own Stop Condition B ("do not invent one"), this stays
  schema-only (`implemented=false`) until a future task freezes a
  tolerance policy.
- **`citation_grounding`** - would require chunk/evidence-level gold that
  does not exist (Stop Condition E).
- **`faithfulness`** - would require an LLM judge (Stop Condition D) -
  explicitly not implemented here, and OpenRouter/OpenAI/Anthropic were
  never called during this task.

**Not implemented anywhere in this task** (explicitly out of scope per
Section 5): an LLM judge, a narrative faithfulness judge, the retrieval
pipeline, the generator, guardrails, CRAG, router, or reranker - even
though metric names referencing those concepts exist in the registry.

**`doc_recall@50` was NOT added** - `PROJECT_EXECUTION.md`'s Task 2.6
section says "Recall@K" generically, not a specific k=50 requirement,
and Task 2.5's registry only names `doc_recall@10`/`chunk_recall@10`
concretely. `first_hit_rank()`/`hit_at_k()` in `src/eval/metrics.py` are
already k-generic (any k works), so adding a `doc_recall@50` metric
definition later is a pure additive registry change, not a rewrite -
deferred per Section 30, not silently added.

## `doc_recall@10` is NOT reimplemented

`src/eval/baseline_metrics.py` (Task 1.10) remains the frozen,
authoritative implementation - exact `document_id` string equality
against exactly `k` rank-ordered chunk results, no document
deduplication before the cutoff, one hit maximum per question. Task 2.6
adds a generic `first_hit_rank(ranked_ids, relevant_ids, k)` in
`src/eval/metrics.py` that reproduces the identical hit/first-hit-rank
definition for *any* ID granularity and *any* k (needed for `doc_mrr`,
`doc_ndcg@10`, `chunk_recall@10`, `chunk_mrr`) - verified to agree with
`baseline_metrics.evaluate_question()` on the same fixtures
(`tests/test_metrics.py::test_agrees_with_task_1_10_baseline_metrics_hit_and_rank`
and `..._miss`). `src/eval/baseline_metrics.py` itself was not modified.

## Formulas frozen in this task

### Recall / hit-at-k

```text
hit@k(rank)   = rank is not None and rank <= k
recall        = count(hit) / count(applicable questions)
```

`first_hit_rank(ranked_ids, relevant_ids, k)` scans the first `k` IDs in
rank order and returns the minimum matching rank, or `None`. No
deduplication - a target's second occurrence never changes the answer,
but nothing is discarded before the cutoff either (Section 39/9).

### MRR

```text
RR(rank)  = 1/rank if rank is not None else 0
MRR       = mean(RR over all questions)
```

Never "mean rank" and never "1/mean rank" - both are mathematically
different from MRR and explicitly tested to differ
(`test_mrr_never_mean_rank_or_inverse_mean_rank`).

### nDCG@k (binary relevance)

```text
DCG@k   = sum_{i=1..k} rel_i / log2(i + 1)      (rel_i in {0,1})
IDCG@k  = sum_{i=1..min(num_relevant,k)} 1/log2(i + 1)
nDCG@k  = DCG@k / IDCG@k                         (None if num_relevant == 0)
```

**Relevance is binary**, not graded - no task before this one defines a
relevance grade anywhere in the frozen gold labels (Task 2.1-2.4), so
`dcg_at_k()` raises `MetricInputError` on any relevance value outside
`{0, 1}` rather than silently accepting a grade the project's gold does
not actually support. A future graded-relevance gold label would need a
new `metric_version`, never a silent change to `doc_ndcg@10` version
`1.0`.

**No relevant items in gold (`num_relevant == 0`) returns `None`**
(not applicable) - a documented, deliberate convention (not a silent
`0.0`, which would be indistinguishable from "gold has relevant items
but none were retrieved").

**Discount convention**: `1/log2(rank + 1)`, the standard IR convention,
adopted explicitly here (not silently guessed) because no prior task in
this repository defines a different one - documented so a future
developer never has to guess why this specific formula was chosen.

### Numeric exact match

```text
match = (gold_unit == predicted_unit) and (float(gold_value) == float(predicted_value))
```

Compares **canonical parsed floats**, never display-formatted strings -
`"1000000"`, `"1000000.0"`, and `"1e6"` are all the same canonical value
and all match each other. Unit equality is required first - `"100 USD"`
never matches `"100 shares"` merely because the magnitude is identical
(Section 17); no currency conversion, no unit inference. An unparseable
value string (either side) raises `MetricInputError` - the caller is
responsible for recording `numeric_parse_status="invalid"` and
`exact_match=False` on that question's result row, never silently
coercing or crashing.

EPS unit note: the frozen tag registry
(`configs/eval_tags.yaml`, verified in Task 2.2) uses plain `"USD"` for
`EarningsPerShareBasic`/`EarningsPerShareDiluted` - never a
`"USD/shares"` compound unit - confirmed directly from the real registry
before writing the EPS test case, not guessed from this task's prompt
text.

### Correct refusal

```text
correct_refusal = (expected_behavior == observed_behavior)
```

Purely structural label comparison - never fragile substring matching
on free text (e.g. `"cannot" in answer.lower()`). `observed_behavior` is
expected to be produced by a later, separate evaluator/classifier; this
function only compares two already-structured labels.

### Shared rate aggregation

```text
aggregate_rate(flags) = {
    value:       count(True in flags) / len(flags),
    numerator:   count(True in flags),
    denominator: len(flags),
}
```

Used by `doc_recall@10`-style rates, `correct_refusal_rate`, and the
`citation_format_compliance` regression test. Raises `MetricInputError`
on an empty `flags` list rather than `ZeroDivisionError` or a fabricated
`0.0`. **N/A is never appended to `flags` at all** - a question the
metric does not apply to is excluded before this function is called, so
the denominator only ever contains applicable, successfully-scored
questions (Section 23).

## Hand-derived known-answer fixture (Section 37)

Toy fixture, `k=10`, one relevant document per question:

```text
Q1: relevant target at rank 1
Q2: relevant target at rank 2
Q3: relevant target at rank 10
Q4: relevant target at rank 11   (outside k=10 window - a genuine miss)
Q5: no relevant result at all

first_hit_rank:  Q1=1, Q2=2, Q3=10, Q4=None, Q5=None
RR:              Q1=1, Q2=0.5, Q3=0.1, Q4=0, Q5=0

recall@10  = 3/5 = 0.6
MRR        = (1 + 0.5 + 0.1 + 0 + 0) / 5 = 0.32

doc_ndcg@10 per question (num_relevant=1 each; Q5 num_relevant=0 -> N/A):
  Q1 = 1/log2(2) / 1.0  = 1.0                  (perfect ranking)
  Q2 = 1/log2(3) / 1.0  = 0.6309297535714575
  Q3 = 1/log2(11) / 1.0 = 0.2890648263178879
  Q4 = 0 / 1.0          = 0.0
  Q5 = not applicable

mean nDCG@10 (Q1-Q4 only) = (1.0 + 0.6309297535714575 + 0.2890648263178879 + 0.0) / 4
                          = 0.47999864497233635
```

## Multi-relevant fixture (Section 38)

```text
gold relevant documents: A, B, C   (num_relevant = 3)
retrieved (ranks 1-5):   X, B, Y, A, Z

relevances aligned to ranks 1..5: [0, 1, 0, 1, 0]

DCG@5   = 1/log2(3) + 1/log2(5)                         (B at rank2, A at rank4)
        = 0.6309297535714575 + 0.4306765580733931
        = 1.0616063116448506

IDCG@5  = 1/log2(2) + 1/log2(3) + 1/log2(4)              (3 relevant ideally at ranks 1-3)
        = 1.0 + 0.6309297535714575 + 0.5
        = 2.1309297535714578

nDCG@5  = DCG@5 / IDCG@5 = 0.49818925746641285
```

This distinct fixture (vs. the single-relevant Task 1.10-style fixture)
is documented separately, per Section 38, because the single-target
semantics are not automatically identical to a multi-relevant-document
benchmark.

## Duplicate document/chunk fixture (Section 39)

```text
rank 1 -> document X, chunk 1
rank 2 -> document X, chunk 2
rank 3 -> target document Y, chunk 1

first_hit_rank(document_ids=[X, X, Y], relevant={Y}, k=3) = 3
```

No document dedup before the cutoff - matches Task 1.10's historical
definition exactly (verified by the regression tests against
`baseline_metrics.py`).

## N/A vs. zero, and execution errors vs. misses

`aggregate_rate()` never receives a flag for a non-applicable question -
the caller filters by category/subtype applicability
(`numeric_exact_match` never applies to `prompt_injection`;
`correct_refusal_rate` never applies to ordinary numeric questions)
before building the `flags` list. Likewise, a question whose
`eval_question_results.status` is `retrieval_error`/`generation_error`/
`timeout`/`schema_error` (Task 2.5's error taxonomy) must never be
scored `False` by a metric - it is excluded from the applicable set
entirely, exactly like a non-applicable question, and the run's overall
completeness is instead tracked by `eval_runs.status`
(`partial`/`failed`).

## Evaluation-store round trip

`tests/test_metrics.py::test_metric_round_trip_through_eval_store`
(in-memory DuckDB, never the real `eval.duckdb`, never TEST): builds the
5-question toy fixture above, computes `doc_recall@10` via
`aggregate_rate`, persists it via `eval_store.record_metric()`, reads it
back, and **independently re-aggregates from the persisted
`eval_question_results.doc_first_hit_rank` rows** (never trusting the
stored `eval_metrics` row to prove itself) - both aggregations agree
exactly (`value=0.6, numerator=3, denominator=5`).

## Schema-hash consequence (Section 41)

Changing `implemented` on 6 metric definitions changed
`eval_schema_metadata`'s content-derived `evaluation_schema_hash`,
because `evaluation_schema_hash` is computed over
`canonical_schema_dict()`, which includes `METRIC_DEFINITIONS`:

```text
evaluation_schema_version:  1            (UNCHANGED - no table/column/constraint changed)
evaluation_schema_hash before: 13aec6b2d80d1be70f3d8117bf4914274605910697f88d058f93bfe933332338
evaluation_schema_hash after:  7dd055a16b9c19ead250e3b5bc94f672d9d857dd65766b30ff64612a66fed126
```

**Why the version did not bump**: Task 2.5's versioning policy reserves
`evaluation_schema_version` increments for structurally incompatible
migrations (a table/column/constraint change that would make an old
row's shape invalid). An `implemented`/`available_for_current_gold` flag
is registry *metadata about the metric*, not a change to any metric's
mathematical definition (cutoff, normalization, tolerance, relevance
model) - none of the six `metric_version` values changed, so a run
scored under any of these metrics before and after this task remains
directly comparable. This is the same content-hash-changes-but-version-
doesn't reasoning already used for Task 2.2's `registry_hash`.

`src/eval/eval_store.py::initialize_schema()` was extended (Section
43/46 - a legitimate Task 2.5 extension, not a Task 2.6 file, but the
gap was discovered while implementing Task 2.6) to **resync** existing
`metric_definitions` rows when their content changes, rather than only
inserting missing ones - a pre-existing real DB would otherwise have
kept the stale `implemented=false` values forever. This never touches
run-scoped evidence (`eval_runs`/`eval_question_results`/`eval_metrics`)
- only the shared, code-owned `metric_definitions` table - and is
covered by a new regression test
(`test_metric_definitions_resynced_on_reinit_without_duplicating`).
`scripts/init_evaluation_schema.py` was re-run (copy-test first, then
the real database) to apply this resync; `test_access_log` remained
byte-identical (2 rows) before and after.

## TEST discipline

`artifacts/eval/phase_2_4_test.json` was never read for metric examples;
`src.eval.test_access.load_test_set()` was never called. Official TEST
evaluation runs consumed by this task: **0 / 3**. `test_access_log`'s 2
`build_validation` rows (from Task 2.4) were independently re-verified
unchanged after the schema re-sync.

## Validation commands

```bash
python -m pytest tests/test_metrics.py -q
python -m pytest tests/test_evaluation_schema.py tests/test_eval_store.py -q
python scripts/init_evaluation_schema.py
python -m pytest -q
```

## Final matrix

| Metric | Formula frozen | Implementation | Current gold | Hand-tested |
|---|---|---|---|---|
| `doc_recall@10` | yes (Task 1.10) | yes (Task 1.10, unchanged) | yes | yes (regression vs. Task 1.10) |
| `chunk_recall@10` | yes | yes (Task 2.6) | **no** | yes (synthetic labels) |
| `doc_mrr` | yes | yes (Task 2.6) | yes | yes |
| `chunk_mrr` | yes | yes (Task 2.6) | **no** | yes (synthetic labels) |
| `doc_ndcg@10` | yes (binary, log2 discount) | yes (Task 2.6) | yes | yes |
| `numeric_exact_match` | yes | yes (Task 2.6) | yes | yes |
| `numeric_tolerance_match` | **no - deferred** | no | yes | schema/validation only |
| `correct_refusal_rate` | yes | yes (Task 2.6) | yes | yes |
| `citation_format_compliance` | yes (Task 1.7a/1.8) | yes (unchanged) | yes | yes (aggregation regression only) |
| `citation_grounding` | no - needs evidence gold | no | no | no |
| `faithfulness` | no - needs LLM judge | no | no | no |

## Remaining deferred metric implementations

- `numeric_tolerance_match` - blocked on a frozen tolerance policy
  (absolute vs. relative, boundary inclusivity) from a future
  authoritative task.
- `chunk_recall@10`/`chunk_mrr` real-gold scoring - blocked on Task 2.8
  (primary-document parsing for evidence labels) or a later chunk-level
  gold-labeling task.
- `citation_grounding` - blocked on the same chunk/evidence-level gold.
- `faithfulness` - blocked on a future, explicitly-scoped LLM-judge task
  (not this one).
- `doc_recall@50` (or any other k) - not requested by
  `PROJECT_EXECUTION.md`'s Task 2.6 section; the underlying
  `first_hit_rank`/`hit_at_k` functions already support any k, so adding
  it later is a pure additive registry change.
