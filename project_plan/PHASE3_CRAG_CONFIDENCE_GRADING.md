# Phase 3 CRAG-Style Confidence Grading

Established in Task 3.7. Calibrates a retrieval-confidence-based refusal
gate over the Task 3.5-selected, Task 3.6-unreranked dense-only
retrieval mode — reusing the frozen Task 3.3 dense retrieval score
rather than adding an LLM grader (PROJECT_EXECUTION.md's own framing).

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.7: reuse existing retrieval/
reranker signals to build a confidence gate; candidate features are
top-1 score, top-3 mean score, top-1-to-top-5 gap, and candidate count
after filtering; calibrate thresholds on DEV; measure true refusal
rate, false refusal rate, and missed failure rate.

## Two contract decisions the roadmap left open (resolved by documented engineering judgment, not the user)

Unlike Task 3.6's reranker-model choice (an arbitrary external fact only
the user could supply), these two gaps are implementation-detail
judgment calls with a defensible answer derivable from the repository's
own prior decisions — resolved here and frozen in
`configs/phase_3_7_crag_confidence_grading.json` before any formal run:

1. **Score source.** The roadmap names "top-1 reranker score," but Task
   3.6 selected `no_rerank` — there is no reranker score. Every feature
   is computed from the frozen Task 3.3 **dense retrieval score**
   (cosine similarity, higher is better) instead.
2. **Evaluation population.** Every other Phase 3 task evaluates
   ranking quality on the frozen 89-question `DEV/evaluable-subset`,
   which contains *only* answerable questions — it has zero "should
   refuse" examples and cannot calibrate a refusal gate alone. This
   task's population is therefore two disjoint DEV subsets, neither
   newly invented:
   - `should_answer` = the exact frozen 89-question scope (unchanged).
   - `should_refuse` = every DEV question whose `(category, subtype)`
     is in `src.eval.phase3_baseline.NOT_APPLICABLE_SHAPES`
     (`unanswerable/year_outside_window`, `adversarial/prompt_injection`,
     `adversarial/financial_advice`, `adversarial/off_scope`) — a fixed
     classification already defined in Task 3.1, reused verbatim.
     Live count verified at plan time: 71+16+13+13 = **113 questions**.

   Deliberately **excluded**: DEV questions that are retrieval-
   applicable but whose gold document is missing from the indexed
   1,500-filing corpus (the ~94% of DEV Task 3.1 excluded from the
   89-question scope). Reusing that population here would silently
   reopen Task 3.1's own scope decision without review — left for a
   future task if ever needed.

## New modules

- `src/crag/confidence.py` — `compute_confidence_features()`,
  `should_refuse()` (single-feature gate: refuse iff `top1_score <
  threshold`), `classify_outcome()`, and
  `calibrate_threshold_youden_j()` — a deterministic, non-parametric
  sweep over every observed `top1_score` as a candidate cutoff,
  maximizing Youden's J (`true_refusal_rate - false_refusal_rate`).
  Ties broken by the lowest candidate threshold (conservative default).
- `src/eval/phase3_crag.py` — config-hash wrapper, rate aggregation
  (reusing Task 2.6's `aggregate_rate` unmodified), and the CRAG
  ablation row. `refusal_metric` (a base ablation-table column that has
  been `N/A` through every prior task) is finally populated here with
  `missed_failure_rate`.

## Formal evaluation (Stage 7)

One dense retrieval pass per question (202 total: 89 should-answer + 113
should-refuse) over the already-frozen, unmodified Qwen dense index — no
embeddings recomputed, no index rebuilt. The dense parent was verified
to reproduce its frozen Task 3.3 per-question metrics exactly (89/89
questions) before any CRAG number was trusted.

## Results

```text
calibrated threshold (top1_score): 0.5531
Youden's J:                        0.7644   (well-separated distributions)

true_refusal_rate:    83.19%  (94/113)   should-refuse questions correctly refused
false_refusal_rate:    6.74%  ( 6/89)    should-answer questions incorrectly refused
missed_failure_rate:  16.81%  (19/113)   should-refuse questions incorrectly answered
```

A single dense-cosine-similarity feature (no reranker, no LLM grader)
separates answerable from should-refuse questions with a strong Youden's
J of 0.76 — the retrieval score alone carries real, usable signal about
whether the corpus actually contains a relevant answer, at the cost of
mislabeling roughly 1 in 15 genuinely answerable questions as low-
confidence.

## Ablation table

Row `crag_confidence` appended to `results/phase_3_ablation_table.csv`
(`configuration=crag_confidence_grading`, `retrieval_mode=dense_only`,
`dense_used_in_this_row=true`, `refusal_metric=missed_failure_rate`).
`doc_recall_at_10`/`doc_mrr`/`doc_ndcg_at_10`/`precision_at_5` are `N/A`
for this row — CRAG computes no ranking metric, only a refusal-gate
metric, and `question_count` is `should_answer_count + should_refuse_count
= 202`, not the 89-question ranking scope other rows use. Every prior
row (0, A0–C1, the four Task 3.3 embedding candidates, Task 3.4's
`bm25_fts`, Task 3.5's `hybrid_rrf`, Task 3.6's `ce_minilm_l6`) verified
byte-for-byte unchanged in every pre-existing column; the table gained
new CRAG-specific columns (`crag_feature`, `crag_threshold`,
`crag_calibration_method`, `should_answer_count`, `should_refuse_count`,
`true_refusal_rate`, `false_refusal_rate`, `missed_failure_rate`,
`crag_youden_j`), which every prior row now carries as `N/A`.

## Build/orchestration

`scripts/run_phase3_crag.py` — `--plan` / `--run` (Stages 1–10) /
`--status` (read-only). No `--compare` stage: unlike Tasks 3.5/3.6,
there is no paired "with vs without" retrieval-quality comparison to
run — CRAG calibrates and reports a standalone gate.

## Tests

37 new tests across `tests/test_crag_confidence.py`,
`tests/test_phase3_crag.py`, `tests/test_phase3_crag_script.py` — all
portable (synthetic score fixtures, no real corpus, no GPU, no model, no
network). Full suite: 1687 passed (was 1650 before Task 3.7), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_crag.py`, `src/crag/confidence.py`, or
`src/eval/phase3_crag.py` (AST-verified, portable test). No paid API/
generation calls. FinanceBench not rerun. Frozen Task 3.2 chunk config,
Task 3.3 dense winner identity, and Task 3.5/3.6 selections
(`dense_only`/`no_rerank`) verified unchanged before the run. Row 0 and
every Task 3.2–3.6 ablation-table row confirmed byte-for-byte unchanged
in their pre-existing columns.

## Limitations

- `should_answer` (89) and `should_refuse` (113) are fixed, purpose-
  built DEV subsets, not a random DEV sample — the 202-question
  population is small.
- Threshold calibrated and measured on the same population (no held-out
  split) — a known optimistic-bias limitation, consistent with how
  every other frozen Phase 3 threshold in this project was set with
  visibility into DEV behavior, but documented rather than hidden.
- Single global threshold on `top1_score` only — per-intent thresholds
  and the other three candidate features (`top3_mean_score`,
  `top1_top5_gap`, `candidate_count`) were recorded diagnostically but
  did not gate the decision in this round.
- DEV questions with a retrieval-applicable-but-uncovered gold document
  were not used as `should_refuse` evidence — a deliberate scope
  boundary carried over from Task 3.1.
- No generation — this measures a pure retrieval-confidence gate, not
  end-to-end answer quality or citation faithfulness.

## Next roadmap task

Phase 3, Task 3.8 — rules-first router (company-name→CIK resolution,
fiscal-year/form-type extraction, known-XBRL-concept lookup, intent
classification), using `qwen3_embedding` dense-only unreranked retrieval
as the downstream candidate source.
