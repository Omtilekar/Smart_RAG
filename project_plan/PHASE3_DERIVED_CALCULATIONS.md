# Phase 3 Deterministic Derived Calculations

Established in Task 3.11. Arithmetic layer on top of Task 3.10's
structured fact lookup — no retrieval, no embedding call, no
generation, no second fact-eligibility rule:

```text
question -> Task 3.8 router -> two operands, each fetched via
Task 3.10's XbrlFactIndex.lookup() -> deterministic arithmetic
-> exact-match score
```

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.11: "Retrieve facts with
models/rules; calculate facts with deterministic code" — growth,
percentage of revenue, year-over-year difference, cross-company
comparison.

## Scope decision

The full 1,932-question DEV corpus has exactly two `operation` values
with real ground truth: `difference` (244 questions) and `greater_than`
(105 questions). Zero examples of growth-rate or percentage-of-revenue
anywhere in DEV. Implemented the two operations with real ground
truth; growth/percentage-of-revenue documented as designed-but-
unevaluated. Same scope pattern already used and user-approved at Task
3.8 (6 of 10 router intents had real examples).

## Reused, not reimplemented

- **Fact fetch**: `src.sql.xbrl_lookup.XbrlFactIndex` (Task 3.10,
  frozen, unmodified) — every operand for every calculation goes
  through this, never a second fact selector.
- **Routing/extraction**: Task 3.8's `src.router.rules.classify_intent()`
  (frozen, unmodified) applied to each question's raw TEXT ONLY.
  `difference` needs exactly one resolved company and exactly two
  distinct fiscal years (text order preserved via
  `extract_fiscal_years`); `greater_than` needs exactly two distinct
  resolved companies and exactly one fiscal year.
- **Scoring**: `src.eval.metrics.numeric_exact_match()` (Task 2.3,
  frozen, unmodified) for `difference`; exact CIK match against the
  question's own `expected_answer` company name for `greater_than`
  (never a fuzzy string comparison).

## New modules

- `src/sql/derived.py` — `DerivedResult`, `compute_difference()`
  (`value(fiscal_year_b) - value(fiscal_year_a)`, b = later/"to" year,
  a = earlier/"from" year, as they appear in question text),
  `compute_greater_than()` (order-independent; ties reported as their
  own outcome, never silently broken).
- `src/eval/phase3_derived.py` — config-hash wrapper, `derived_rates`
  (reusing Task 2.6's `aggregate_rate` unmodified), and the derived-
  calculations ablation row.

## Formal evaluation (Stage 7)

```text
difference:    routing_coverage=79.51% (194/244)  computed=100% (194/194)  exact_match=100% (194/194)
greater_than:  routing_coverage=82.86% (87/105)    computed=100% (87/87)    exact_match=100% (87/87)
```

Same root cause as Tasks 3.8/3.10: routing coverage is gated by router
extraction accuracy (needs 2 distinct years, or 2 distinct companies,
correctly resolved from text). **Once a question is attempted, the
deterministic calculation layer is perfect** — every attempted
operand-pair that resolved to found facts produced a computed result,
and every computed result exactly matched ground truth, for both
operations.

## Ablation table

Row `derived_calculations` appended to `results/phase_3_ablation_table.csv`
(`configuration=deterministic_derived_calculations`,
`dense_used_in_this_row=false`). `doc_recall_at_10`/etc. are `N/A` — no
ranking metric computed. New columns: `difference_question_count`,
`greater_than_question_count`, `difference_routing_coverage`,
`difference_exact_match_rate`, `greater_than_routing_coverage`,
`greater_than_exact_match_rate` — every prior row (0, A0-C1, the four
Task 3.3 embedding candidates, `bm25_fts`, `hybrid_rrf`, `ce_minilm_l6`,
`crag_confidence`, `rules_router`, `metadata_prefilter`, `xbrl_sql_path`)
verified byte-for-byte unchanged in every pre-existing column, now
carrying these new columns as `N/A`.

## Build/orchestration

`scripts/run_phase3_derived.py` — `--plan` / `--run` / `--status`
(read-only). No GPU, no model, no LanceDB — pure Python + one
read-only DuckDB connection; runs in seconds.

## Tests

New tests across `tests/test_derived_calculations.py`,
`tests/test_phase3_derived.py`, `tests/test_phase3_derived_script.py` —
all portable (synthetic in-memory DuckDB, no real frozen database
touched). Also updated the `later_task_columns` set in six pre-existing
test files (`test_phase3_sparse.py`, `test_phase3_hybrid.py`,
`test_phase3_rerank.py`, `test_phase3_crag.py`, `test_phase3_router.py`,
`test_phase3_filter.py`) to include `ABLATION_TABLE_DERIVED_EXTRA_COLUMNS`
— the same additive-column maintenance cost paid by every prior task.
Full suite: 1843 passed (was 1811 before Task 3.11), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_derived.py`, `src/sql/derived.py`, or
`src/eval/phase3_derived.py` (AST-verified, portable test, checking
oracle ground-truth `cik`/`fiscal_year`/`operands` fields are never used
for routing). No paid API/generation calls. FinanceBench not rerun. Row
0 and every Task 3.2-3.10 ablation-table row confirmed byte-for-byte
unchanged in their pre-existing columns.

## Limitations

- `routing_coverage` for both operations depends entirely on Task 3.8's
  router correctly extracting 2 distinct years or 2 distinct companies
  from text — a question needing this but only resolving 1 is never
  attempted, and counts against coverage, not against the calculation
  layer's own correctness (near-perfect once reached).
- Growth-rate and percentage-of-revenue operations are designed-but-
  unevaluated: no DEV ground truth exists for them yet.
- No retrieval, reranking, CRAG gating, or generation in this path.

## Next roadmap task

Phase 3, Task 3.12 — per `project_plan/PROJECT_EXECUTION.md`'s exact
numbered contract.
