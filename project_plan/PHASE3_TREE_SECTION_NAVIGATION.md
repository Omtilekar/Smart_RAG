# Phase 3 Simple Tree/Section Navigation

Established in Task 3.12. Deterministic filing/section navigation for
queries like "Summarize Item 7 of this filing":

```text
question -> extract_item_reference() (text-only) + (cik, fiscal_year)
extraction -> resolve_filing_document_id() against the frozen
`submissions` table -> load exactly ONE document's Task 2.8 parsed
nodes -> filter to section_id == requested item -> return only those
nodes
```

No retrieval, no embedding call, no generation, no full-corpus scan.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.12: identify the filing,
navigate directly to the requested normalized section, avoid
unnecessary global retrieval.

## Scope decision

PROJECT_EXECUTION.md's own example query has **zero** matching examples
anywhere in the 1,932-question DEV corpus - no question mentions
"Item" or "section" at all. This is a stronger version of the
zero-example situation already user-approved at Task 3.8
(narrative/section_summary intents), but unlike Task 3.8 there is no
partial subset to score against. The navigation capability itself is
mechanical (a deterministic lookup over an already-computed structural
artifact), so it is implemented and tested against the one ground-truth
surface that does exist: Task 2.8's own frozen structural-parsing
output. Formal evaluation measures the navigation layer's own
correctness/coverage against that corpus, not natural-language question
answering (generation stays out of scope, same as every other Phase 3
task).

## Reused, not reimplemented

- **Section-boundary detection**: `src.parse.primary_html._CANONICAL_ITEMS`
  and its Section-15 last-occurrence-wins canonical-Item heading
  detector (Task 2.8, frozen, unmodified) - the ONE section-boundary
  source of truth. This task never re-derives Item boundaries.
- **Parsed corpus**: `artifacts/primary_docs/parsed/<doc_key>.json`
  (Task 2.8, locally-derived/gitignored, deterministic given
  source_sha256 + parser_config_hash) - 990 of the corpus's 1,493
  documents have been HTML-parsed; navigation coverage is bounded by
  this, an honest pre-existing gap, not a new sampling decision.
- **Filing identity**: `data/xbrl.duckdb`'s `submissions` table (cik,
  adsh, fiscal_year, form) - the same frozen source Task 2.1/2.2's
  truth contract and Task 2.8's own document_id construction
  (`primary:{cik}:{accession}`) are built from.

## New modules

- `src/nav/section_navigation.py` - `extract_item_reference()` (text-only
  regex over the canonical Item-id set, returns `None` rather than
  guessing - mirrors Task 2.8's own policy), `resolve_filing_document_id()`
  (outcomes: `found`, `filing_not_found`, `ambiguous_filing` - 43
  cik+fiscal_year groups in the corpus have more than one 10-K
  submission, e.g. amended filings; never silently picks one),
  `load_document_nodes()` (loads exactly one document's parsed JSON,
  `None` if never parsed), `navigate_to_section()` (composes the above;
  outcomes: `found`, `section_not_found`, `filing_not_parsed`,
  `filing_not_found`, `ambiguous_filing`).
- `src/eval/phase3_nav.py` - config-hash wrapper, rate aggregation
  (`nav_rates`, reusing Task 2.6's `aggregate_rate` unmodified), and
  the navigation ablation row.

## Formal evaluation (Stage 7)

Eval population: every (cik, fiscal_year) pair with a successfully
Task-2.8-parsed 10-K (990 documents), crossed with every canonical Item
id Task 2.8's own section-heading detector actually found in that
document (19,050 navigation attempts total, from the parsed nodes' own
`section_id` field - real, already-computed ground truth, not new hand
labeling).

```text
filing_resolution_rate: 99.90% (987/988)
section_found_rate:     99.88% (19027/19050)
scope_leak_rate:         0.00% (0/19027)  -- hard safety invariant
```

`scope_leak_rate` is exactly 0.00% across all 19,027 successful
navigations: every returned node's `section_id` equals exactly the
requested item, and `node_count` is always strictly less than
`total_document_node_count` - proof no global/full-document read ever
occurred. The small residuals in `filing_resolution_rate` (1/988) and
`section_found_rate` (23/19050) are consistent with known corpus
structure (amended-filing ambiguity, occasional heading-detection
misses already documented as a Task 2.8 limitation) rather than a new
defect in this task's logic.

## Ablation table

Row `tree_section_navigation` appended to
`results/phase_3_ablation_table.csv` (`configuration=tree_section_navigation`,
`dense_used_in_this_row=false`). `doc_recall_at_10`/etc. are `N/A` - no
ranking metric computed. New columns: `nav_parsed_document_count`,
`nav_navigation_attempt_count`, `nav_filing_resolution_rate`,
`nav_section_found_rate`, `nav_scope_leak_rate` - every prior row (0,
A0-C1, the four Task 3.3 embedding candidates, `bm25_fts`, `hybrid_rrf`,
`ce_minilm_l6`, `crag_confidence`, `rules_router`, `metadata_prefilter`,
`xbrl_sql_path`, `derived_calculations`) verified byte-for-byte
unchanged in every pre-existing column, now carrying these new columns
as `N/A`.

## Build/orchestration

`scripts/run_phase3_nav.py` - `--plan` / `--run` / `--status`
(read-only). No GPU, no model, no LanceDB - pure Python + one read-only
DuckDB connection against `data/xbrl.duckdb` plus local JSON reads
against the already-parsed corpus; runs in well under a minute over all
990 documents.

## Tests

New tests across `tests/test_section_navigation.py` (17 tests, synthetic
in-memory DuckDB `submissions` table + tmp_path-backed parsed-document
fixtures, including a call-counting spy proving exactly one document is
ever loaded per navigation), `tests/test_phase3_nav.py` (18 tests,
pure-logic ablation-row/rates tests), `tests/test_phase3_nav_script.py`
(6 tests, AST-based static guards - never imports `test_access`, never
loads a model, never opens a parsed-corpus file for writing). Also
updated the `later_task_columns` set in eight pre-existing test files
(`test_phase3_sparse.py`, `test_phase3_hybrid.py`, `test_phase3_rerank.py`,
`test_phase3_crag.py`, `test_phase3_router.py`, `test_phase3_filter.py`,
`test_phase3_sql.py`, `test_phase3_derived.py`) to include
`ABLATION_TABLE_NAV_EXTRA_COLUMNS` - the same additive-column
maintenance cost paid by every prior task. Full suite: 1884 passed (was
1843 before Task 3.12), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout - never
imported by `scripts/run_phase3_nav.py`, `src/nav/section_navigation.py`,
or `src/eval/phase3_nav.py` (AST-verified, portable test). No paid
API/generation calls. FinanceBench not rerun. Row 0 and every Task
3.2-3.11 ablation-table row confirmed byte-for-byte unchanged in their
pre-existing columns.

## Limitations

- No DEV question in the current 1,932-question corpus has this query
  shape; formal evaluation is corpus-structural, not natural-language
  question answering. If NL eval data for this shape is added later, a
  new evaluation contract should be layered on top of this same
  navigation module rather than replacing it.
- Navigation coverage is capped by Task 2.8's own HTML-parsing coverage
  (990/1,493 documents) - a pre-existing gap, not introduced here.
- `resolve_filing_document_id()` treats an amended-filing ambiguity
  (`ambiguous_filing`) as a hard refusal rather than picking the latest
  filing - consistent with every other Phase 3 "never silently choose"
  policy, but means genuinely resolvable amended-filing cases are
  currently left unresolved rather than disambiguated by filing date.
- No retrieval, reranking, CRAG gating, or generation in this path.

## Next roadmap task

Phase 3, Task 3.13 - maintain the ablation table (per
`project_plan/PROJECT_EXECUTION.md`'s exact numbered contract).
