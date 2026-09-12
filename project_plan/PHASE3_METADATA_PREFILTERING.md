# Phase 3 Metadata Pre-Filtering

Established in Task 3.9. Scalar CIK + fiscal_year pre-filtering applied
before exact/brute-force dense cosine search, using Task 3.8's
rules-first router to extract the filter values from each question's
raw text — evaluated over the exact frozen 89-question `DEV/evaluable-
subset`.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.9: apply scope (CIK, year,
form, section) before retrieval where possible; use exact/brute-force
search for very narrow filtered candidate pools where it is more
accurate and cheaper than ANN.

## Filter-dimension scoping (verified against the real frozen artifact)

The roadmap lists four dimensions. Checked directly against the frozen
323,971-row chunk artifact before writing any code:

- **`cik`** — 1,370 distinct values. Real, discriminative. Implemented.
- **`fiscal_year`** — 5 distinct values (2016–2020). Real, discriminative.
  Implemented.
- **`form_type`** — a single constant value (`"10-K"`) across every row
  (the Phase 1 baseline constraint). Filtering on it is a no-op — not
  implemented as a real filter.
- **`section`** — no such column exists at all. Task 3.2 selected FIXED
  (non-section-aware) splitting as the chunking winner, so no chunk
  carries section metadata.

This is the "where possible" scoping the roadmap's own wording
anticipates, not a silently reduced contract — documented explicitly in
`configs/phase_3_9_metadata_prefiltering.json`'s `filter_dimension_decision`.

## Extraction source (no test leakage)

`cik`/`fiscal_year` are extracted from each question's raw **text only**
via Task 3.8's frozen, unmodified `src.router.rules.classify_intent()` —
never from the question record's own hidden ground-truth fields, which
would be test leakage (the real system never sees those fields at query
time). A question is filtered only if the router resolves **exactly
one** distinct CIK **and** exactly one distinct fiscal year from its
text; otherwise it falls back to unfiltered dense search, recorded
explicitly per question — never silently treated as filtered.

## LanceDB prefilter semantics (verified empirically, Stage 2)

Before writing any formal code: built a disposable synthetic table with
a rare filter value and `limit` far exceeding the number of matching
rows. LanceDB 0.37.1's `.where()` **defaults to `prefilter=True`** —
confirmed by comparing all three: the default and explicit
`prefilter=True` both returned every true match; `prefilter=False`
(computing the top-`limit` nearest neighbors across the WHOLE table
first, then discarding non-matches) returned fewer, silently losing
true matches dominated out by the majority filter value. `prefilter=True`
is passed explicitly in `src.index.lancedb_index.exact_cosine_search_filtered()`
for clarity even though it was already the default — never relying on
an unstated default for a correctness-critical choice.

## New modules

- `src/index/lancedb_index.py` — `exact_cosine_search_filtered()`
  (additive, Task 1.5's existing `exact_cosine_search()` untouched):
  identical contract plus a scalar `where` predicate applied as a true
  pre-filter.
- `src/retrieval/filtered.py` — `MetadataFilteredRetriever` and
  `build_predicate()` (builds a safe SQL predicate from validated Python
  ints only — never raw text — immune to injection by construction).
  Falls back to `exact_cosine_search()` when no filter value is given.
- `src/eval/phase3_filter.py` — config-hash wrapper and the filtering
  ablation row. **Selection reuses `src.eval.phase3_ablation.select_round_winner`/
  `is_practical_tie`/`paired_bootstrap_delta_ci` completely unmodified**
  — unlike Tasks 3.5/3.6 (whose candidate-set Recall@50 was structurally
  locked, making the original Recall@50-keyed practical-tie rule
  meaningless), Task 3.9's baseline and filtered arms search the *same*
  embeddings/index and can have a genuinely different Recall@50, so the
  original Task 3.2/3.3 rule applies exactly as designed. Only the
  tie-break (`filtered_tiebreak_key`) is new: prefer the simpler
  unfiltered baseline on a practical tie.

## Results

```text
                unfiltered baseline   metadata-prefiltered   delta
doc_recall@10:  0.9888 (88/89)        1.0000 (89/89)         +0.0112
doc_recall@50:  1.0000 (89/89)        1.0000 (89/89)          0.0000
doc_mrr:        0.9251                1.0000                 +0.0749
doc_ndcg@10:    0.9407                1.0000                 +0.0593
```

**All 89/89 questions were filtered** — the router extracted exactly
one CIK and exactly one fiscal year from every question's text (these
are all single-company, single-fiscal-year `xbrl_fact`-shaped questions
by construction, which is exactly what Task 3.8 classifies most
reliably). Restricting the candidate pool to only the named document's
own chunks makes the retrieval problem trivial to win — the correct
document is the *only* document in the pool, so its own highest-scoring
chunk is guaranteed to rank first. The result is a clean sweep: perfect
Recall@10, MRR, and nDCG@10.

**Selected: `metadata_prefilter`** — "filtered is a credible improvement
over reference baseline on the frozen priority order with no
regression-protection violation." Resolved automatically by the
unmodified Task 3.2/3.3 selection rule, no user decision required.

## Ablation table

Row `metadata_prefilter` appended to `results/phase_3_ablation_table.csv`
(`configuration=metadata_prefiltered_dense`, `retrieval=dense_exact_cosine_prefiltered`,
`dense_used_in_this_row=true`, `selected=metadata_prefilter`,
`filtered_question_count=89`, `fallback_question_count=0`). Every prior
row (0, A0–C1, the four Task 3.3 embedding candidates, Task 3.4's
`bm25_fts`, Task 3.5's `hybrid_rrf`, Task 3.6's `ce_minilm_l6`, Task
3.7's `crag_confidence`, Task 3.8's `rules_router`) verified byte-for-
byte unchanged in every pre-existing column; the table gained two new
filter-specific columns (`filtered_question_count`,
`fallback_question_count`), which every prior row now carries as `N/A`.

## Build/orchestration

`scripts/run_phase3_filter.py` — `--plan` / `--run` (Stage 7) /
`--compare` (Stages 8–9) / `--status` (read-only).

## Tests

79 new tests across `tests/test_lancedb_filtered_search.py`,
`tests/test_filtered_retriever.py`, `tests/test_phase3_filter.py`,
`tests/test_phase3_filter_script.py` — all portable (tiny synthetic
LanceDB tables, fake retriever functions, no real corpus, no GPU, no
model, no network). Full suite: 1778 passed (was 1734 before Task 3.9),
0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_filter.py`, `src/retrieval/filtered.py`,
or `src/eval/phase3_filter.py` (AST-verified, portable test). No paid
API/generation calls. FinanceBench not rerun. Unfiltered baseline
re-verified to reproduce its frozen Task 3.3 per-question metrics
exactly (89/89 questions) before any filtered number was trusted. Row 0
and every Task 3.2–3.8 ablation-table row confirmed byte-for-byte
unchanged in their pre-existing columns.

## Limitations

- Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-
  subset (4.9% of full DEV) — all single-company, single-fiscal-year
  questions by construction, so 100% router-extraction coverage here is
  not evidence the filter would extract cleanly for the harder
  `comparative`/`cross_entity` multi-company DEV questions the 89-scope
  deliberately excludes.
- `form_type`/`section` are not real filter dimensions given the
  current frozen chunk artifact (constant value / no column at all,
  respectively).
- Extraction errors are a real, measured risk (a wrongly-extracted CIK
  or fiscal year would search the wrong document's chunks entirely,
  guaranteeing a miss) — this evaluation measures that risk honestly
  using the router's real text-only extraction, not oracle ground truth;
  it happened not to occur on this particular 89-question scope.
- `chunk_recall@10`, `chunk_mrr`, `precision@5`, `faithfulness`,
  `citation_grounding`, and generation metrics remain N/A.

## Next roadmap task

Phase 3, Task 3.10 — structured XBRL SQL path for supported numeric
questions, using the Task 3.8 router's `xbrl_fact` intent classification
to decide when to route to it instead of retrieval.
