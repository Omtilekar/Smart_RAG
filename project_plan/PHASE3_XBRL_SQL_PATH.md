# Phase 3 Structured XBRL SQL Path

Established in Task 3.10. A deterministic structured lookup path for
`xbrl_fact`-routed questions — no retrieval, no embedding call, no
generation:

```text
question -> Task 3.8 router -> (cik, fiscal_year, tag) -> Task 2.1/2.2
truth-contract fact lookup -> value + unit + filing provenance
```

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.10: use the truth-contract
semantics in the production selector; return value + unit + filing
provenance; do not route unsupported numeric narrative questions to
SQL.

## Reused, not reimplemented

- **Fact selector**: `src.eval.truth_contract.eligible_facts()` (Task
  2.1/2.2, frozen, unmodified) is the *only* production fact selector —
  every filter (form, fiscal-year window, coreg/segments, taxonomy,
  qtrs, unit, dedup) is exactly the one already-audited Phase 2
  eligibility rule. A tag outside `configs/eval_tags.yaml`'s frozen
  registry always resolves to `outcome="unsupported_tag"`, enforced at
  the fact-selector layer as defense in depth — even though the
  router's own fiscal-year-window and concept-matching rules should
  already prevent most such questions from reaching this path.
- **Routing**: Task 3.8's `src.router.rules.classify_intent()` (frozen,
  unmodified) — a question is attempted only if it is routed to
  `xbrl_fact` intent *and* the router resolves exactly one CIK, exactly
  one fiscal year, and one known concept from its raw text.
- **Scoring**: `src.eval.metrics.numeric_exact_match()` (Task 2.3,
  frozen, unmodified) compares the SQL lookup's value+unit against the
  question's own hidden `expected_value`/`expected_unit` fields — used
  only to score the output *after* the lookup, never to drive routing
  (no test leakage).

## New modules

- `src/sql/xbrl_lookup.py` — `XbrlFactIndex`: eagerly builds a
  `(tag, cik, fiscal_year) -> [EligibleFact]` index from
  `eligible_facts()`, **one query per tag** (15 total), never one query
  per question. `.lookup(cik, fiscal_year, tag)` returns one of four
  outcomes: `found`, `not_found`, `ambiguous` (multiple eligible
  filings disagree on the same fact — a genuine cross-filing value
  revision; never silently picks one, mirroring `truth_contract.py`'s
  own same-accession duplicate policy), or `unsupported_tag`.
- `src/eval/phase3_sql.py` — config-hash wrapper, rate aggregation
  (`sql_rates`, reusing Task 2.6's `aggregate_rate` unmodified), and the
  SQL-path ablation row.

## Formal evaluation (Stage 7)

Two disjoint DEV populations, both already labeled (no new eval-set
construction, same discovery pattern as Task 3.8):

- **`xbrl_fact` target** (1,402 questions, `intent_label == "xbrl_fact"`):
  measures `routing_coverage`, `sql_found_rate`, `sql_exact_match_rate`.
- **Trap population** (139 questions, `subtype` in `unsupported_tag` /
  `year_outside_window` — constructed to have *no* valid SQL answer):
  measures `trap_leak_rate`, the hard safety invariant this task must
  never violate.

## Results

```text
routing_coverage:     80.60% (1130/1402)
sql_found_rate:       99.91% (1129/1130)
sql_exact_match_rate: 99.91% (1129/1130)
trap_leak_rate:        0.00% (0/139)
```

`routing_coverage` (80.60%) lands almost exactly on Task 3.8's own
`xbrl_fact` recall (80.60%) — the same, already-diagnosed root cause:
literal tag-label substring matching has limited recall for
differently-phrased concept mentions, so ~19.4% of true `xbrl_fact`
questions never reach the SQL path at all (they are routed to
`unanswerable` instead — a safe failure mode, not a wrong answer).
**Once a question is attempted, the SQL path is essentially perfect**:
99.91% of attempts find a fact, and every fact found is an exact match
except one. **`trap_leak_rate` is exactly 0.00%** — the SQL path never
once confidently answered a question from the population specifically
constructed to have no valid answer, across all 139 trap questions.

## Ablation table

Row `xbrl_sql_path` appended to `results/phase_3_ablation_table.csv`
(`configuration=structured_xbrl_sql_path`, `retrieval=structured_sql_no_retrieval`,
`dense_used_in_this_row=false`). `doc_recall_at_10`/etc. are `N/A` — the
SQL path computes no ranking metric; `xbrl_fact_question_count=1402`,
`trap_question_count=139`. Every prior row (0, A0–C1, the four Task 3.3
embedding candidates, Task 3.4's `bm25_fts`, Task 3.5's `hybrid_rrf`,
Task 3.6's `ce_minilm_l6`, Task 3.7's `crag_confidence`, Task 3.8's
`rules_router`, Task 3.9's `metadata_prefilter`) verified byte-for-byte
unchanged in every pre-existing column; the table gained new SQL-path-
specific columns (`xbrl_fact_question_count`, `trap_question_count`,
`routing_coverage`, `sql_found_rate`, `sql_exact_match_rate`,
`trap_leak_rate`), which every prior row now carries as `N/A`.

## Build/orchestration

`scripts/run_phase3_sql.py` — `--plan` / `--run` / `--status`
(read-only). No GPU, no model, no LanceDB — pure Python + one read-only
DuckDB connection against `data/xbrl.duckdb`; runs in seconds.

## Tests

50 new tests across `tests/test_xbrl_lookup.py`,
`tests/test_phase3_sql.py`, `tests/test_phase3_sql_script.py` — all
portable (a synthetic in-memory DuckDB database mirroring the real
`data/xbrl.duckdb` schema, same convention as `tests/test_truth_contract.py`
— never touches the real frozen database). Full suite: 1811 passed (was
1778 before Task 3.10), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_sql.py`, `src/sql/xbrl_lookup.py`, or
`src/eval/phase3_sql.py` (AST-verified, portable test — including a
check that oracle ground-truth `cik`/`fiscal_year` fields are never used
for routing). No paid API/generation calls. FinanceBench not rerun. Row
0 and every Task 3.2–3.9 ablation-table row confirmed byte-for-byte
unchanged in their pre-existing columns.

## Limitations

- `routing_coverage`/`sql_found_rate`/`sql_exact_match_rate` depend
  entirely on Task 3.8's router extraction accuracy — a misrouted or
  incompletely-extracted `xbrl_fact` question is never attempted, and
  is counted against `routing_coverage`, not against the SQL path's own
  correctness (which is near-perfect once reached).
- `data/xbrl.duckdb` is opened read-only; this task never writes to it.
- No retrieval, reranking, CRAG gating, or generation in this path — a
  pure structured lookup, deliberately narrower than the full RAG
  pipeline.

## Next roadmap task

Phase 3, Task 3.11 — deterministic derived calculations (growth,
percentage of revenue, year-over-year difference, cross-company
comparison), built on top of this task's structured fact lookup rather
than a second, model-based numeric computation.
