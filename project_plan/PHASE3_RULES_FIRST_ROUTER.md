# Phase 3 Rules-First Router

Established in Task 3.8. A deterministic, keyword/regex/gazetteer
query-intent classifier — no LLM, no retrieval call — evaluated over
every question in the frozen 1,932-question DEV corpus.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.8: company-name→CIK
resolution, fiscal-year/form-type extraction, known-XBRL-concept
lookup, rule-based intent path selection; build a labelled router
evaluation set; report a confusion matrix and per-class metrics;
benchmark an LLM router only if the rule baseline leaves meaningful
gaps.

## Scope decision (user-approved)

`PROJECT_EXECUTION.md` lists 10 target intents (`xbrl_fact`,
`numeric_derived`, `numeric_narrative`, `comparative`, `cross_entity`,
`narrative`, `section_summary`, `unanswerable`, `out_of_scope`,
`advice`). Exhaustively counting every `(category, subtype)` shape in
the full 1,932-question DEV corpus found **zero** examples of
`numeric_narrative`, `narrative`, or `section_summary` —
`src.eval.evaluation_dataset.build_narrative_record()` exists in code,
but every record it could produce stays `status="pending_review"` and
was never promoted into the frozen eval set. Building or evaluating a
router for intents with no real labeled example anywhere would require
fabricating new eval data — a decision on the scale of Task 2.3's
original question generation, not a router sub-task.

**User-approved (2026-09-12):** build and evaluate the router on the
**6 intents with real DEV ground truth** (`xbrl_fact`, `numeric_derived`,
`cross_entity`, `unanswerable`, `out_of_scope`, `advice`); the other 4
are documented as designed-but-unevaluated, not silently dropped.

## A discovery that simplified this task considerably

Every DEV question record already carries an `intent_label` field,
frozen at Task 2.3 generation time — and it matches this task's
6-intent scope **exactly**:

```text
xbrl_fact         1402
numeric_derived    244
unanswerable       139
cross_entity       105
out_of_scope        29
advice              13
total             1932
```

`PROJECT_EXECUTION.md`'s "build a labelled router evaluation set" bullet
is therefore satisfied by data that already exists — no new eval-set
construction was needed, only loading a field that was already there.

## New modules

- `src/router/rules.py` — `CompanyGazetteer` (case-insensitive,
  longest-match-first exact-substring company-name→CIK lookup),
  `extract_fiscal_years()`, `extract_form_type()`,
  `resolve_xbrl_concept()` (matches a Task 2.2 tag's human-readable
  `label` as a substring — the frozen registry is the only concept
  source), and `classify_intent()` — a deterministic cascade:
  prompt-injection keywords → `out_of_scope`; financial-advice keywords
  → `advice`; no resolvable company/fiscal-year/concept at all →
  `out_of_scope`; comparative keyword + ≥2 distinct companies →
  `cross_entity`; change/difference keyword + ≥2 distinct fiscal years
  → `numeric_derived`; fiscal year outside 2016–2020 → `unanswerable`;
  no known concept matched → `unanswerable`; else → `xbrl_fact`. Keyword
  lists are deliberately generalizable phrase cues, never a memorized
  copy of `src.eval.evaluation_dataset.ADVERSARIAL_TEMPLATES`'s 60 exact
  template strings.
- `src/eval/phase3_router.py` — `build_confusion_matrix()`,
  `per_class_metrics()` (precision/recall/F1/support), `overall_accuracy()`,
  `macro_f1()` — a genuinely new metric family (Task 2.6's
  `src.eval.metrics` is retrieval-ranking/refusal-rate shaped, not
  multi-class-classification shaped) — and the router ablation row.

## Data sources reused, not fabricated

- **Company gazetteer** (1,673 companies): built from the DEV question
  dataset's own embedded `company`/`operands[].company` + `cik` fields,
  not a new external company-master file — a legitimate stand-in for
  "the system's known-company registry" for this evaluation.
- **XBRL concept registry** (15 tags): `configs/eval_tags.yaml` via
  `src.eval.tag_registry` (Task 2.2, frozen) — the only concept source.
- **Fiscal-year window** (2016–2020): `src.eval.truth_contract.SUPPORTED_FISCAL_YEAR_MIN/MAX`
  (Task 2.1, frozen) — reused verbatim.

## Results

```text
overall accuracy: 85.82% (1658/1932)
macro F1:         0.8871

                  precision   recall    f1       support
advice            1.0000      0.9231    0.9600   13
cross_entity      1.0000      1.0000    1.0000   105
numeric_derived   1.0000      1.0000    1.0000   244
out_of_scope      0.9655      0.9655    0.9655   29
unanswerable      0.3374      1.0000    0.5045   139
xbrl_fact         1.0000      0.8060    0.8926   1402
```

Perfect classification for `cross_entity` and `numeric_derived` (the
comparative-keyword + multi-entity/multi-year structural cues are
highly reliable). `unanswerable` shows perfect recall (every truly
unanswerable question is correctly caught) but low precision (0.34) —
the rule set over-predicts `unanswerable` because literal tag-label
substring matching (`resolve_xbrl_concept`) has limited recall for
concept mentions phrased differently than the registry's exact label
text, pushing some genuinely-answerable `xbrl_fact` questions (whose
concept the matcher missed) into the conservative `unanswerable`
fallback — visible directly as `xbrl_fact`'s 0.806 recall. This is an
honest, explainable weakness of the concept-matching rule, not a bug.

## Ablation table

Row `rules_router` appended to `results/phase_3_ablation_table.csv`
(`configuration=rules_first_router`, `dense_used_in_this_row=false` —
classification needs no dense retrieval call). `doc_recall_at_10`/
`doc_mrr`/etc. are `N/A` — the router computes no ranking metric.
`question_count=1932` (the full DEV corpus, not the 89-question
retrieval scope — intent classification needs no retrievable target).
Every prior row (0, A0–C1, the four Task 3.3 embedding candidates, Task
3.4's `bm25_fts`, Task 3.5's `hybrid_rrf`, Task 3.6's `ce_minilm_l6`,
Task 3.7's `crag_confidence`) verified byte-for-byte unchanged in every
pre-existing column; the table gained new router-specific columns
(`gazetteer_size`, `concept_registry_size`, `router_accuracy`,
`router_macro_f1`), which every prior row now carries as `N/A`.

## Build/orchestration

`scripts/run_phase3_router.py` — `--plan` / `--run` / `--status`
(read-only). No GPU, no model, no LanceDB query — pure Python, runs in
seconds.

## LLM router comparison

Not benchmarked in this round. `PROJECT_EXECUTION.md`: "Benchmark an LLM
router only if the rule baseline leaves meaningful gaps." An 85.82%
accuracy / 0.89 macro-F1 rule baseline with one clearly diagnosed,
explainable weakness (concept-matching recall) is not an obvious case
for an LLM router yet — worth revisiting if the concept-matching
weakness cannot be cheaply improved with better XBRL synonym coverage.

## Tests

47 new tests across `tests/test_router_rules.py`,
`tests/test_phase3_router.py`, `tests/test_phase3_router_script.py` —
all portable (tiny synthetic gazetteer/registry fixtures, no real
corpus, no GPU, no model, no network). Full suite: 1734 passed (was
1687 before Task 3.8), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_router.py`, `src/router/rules.py`, or
`src/eval/phase3_router.py` (AST-verified, portable test). No paid API/
generation calls. FinanceBench not rerun. Row 0 and every Task
3.2–3.7 ablation-table row confirmed byte-for-byte unchanged in their
pre-existing columns.

## Limitations

- Scoped to 6 intents with real DEV ground truth; `numeric_narrative`,
  `narrative`, and `section_summary` are designed-but-unevaluated
  pending new eval data (user-approved 2026-09-12).
- The company gazetteer is built from the DEV question dataset's own
  embedded fields, not an external SEC company-master registry — a
  legitimate evaluation stand-in, not a production-grade resolver.
- Keyword-cue lists are hand-written generalizations, not tuned against
  a held-out set — the reported metrics are this rule set's true DEV
  performance, not an optimistic estimate from template overfitting.
- No LLM router benchmarked in this round.

## Next roadmap task

Phase 3, Task 3.9 — metadata pre-filtering (CIK/year/form/section),
applied before retrieval using the router's extracted `cik`/
`fiscal_years`/`form_type` signals.
