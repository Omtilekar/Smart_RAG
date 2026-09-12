# Phase 3 Cross-Encoder Reranking

Established in Task 3.6. Cross-encoder reranking of the frozen 50-chunk
Qwen dense candidate pool (the Task 3.5-selected dense-only retrieval
mode — RRF hybrid was practically tied with dense and dense-only was
preferred as the simpler architecture), evaluated over the exact frozen
89-question `DEV/evaluable-subset`.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.6: benchmark a small serving
cross-encoder, optionally compare to a larger quality ceiling, rerank a
fixed candidate pool, keep candidate-set recall separate from reranked
top-k quality. Primary metrics: MRR, nDCG@10, Precision@5, Recall@5.

## Candidate-grid ambiguity (resolved by user decision)

Unlike Task 3.3's explicit four-model table, `PROJECT_EXECUTION.md`
names no specific reranker — just "a small serving candidate" and an
optional "larger quality ceiling." This is a materially ambiguous task
contract per the Task 3.99 controlled-execution-loop's own LOOP STEP 1
rule ("if the task contract is materially ambiguous, STOP for the
user"). The user selected **`cross-encoder/ms-marco-MiniLM-L6-v2` only**
for this round; the optional larger-ceiling comparison was explicitly
deferred.

Pinned revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, resolved
from the installed sentence-transformers 6.0.0's own cache ref at pilot
time — never `"main"`.

## Pilot findings (verified before formal code was written)

- `sentence_transformers.CrossEncoder.predict()` returns one raw,
  **unbounded logit** per (question, passage) pair — no sigmoid/softmax
  by default. Higher is more relevant; never treated as a probability.
  Verified: a clearly relevant pair scored ~9.1, a mismatched pair ~-7.3.
- `num_labels=1`, `max_seq_length=512`.
- Model size ~92 MB; loads fp32 on GPU with the pinned revision; no CPU
  fallback observed.

## New modules

- `src/rerank/cross_encoder.py` — `RerankerModelSpec` + generic
  `load_model()`/`score_pairs()`/`validate_scores()`, mirroring
  `src.embeddings.model_registry`'s spec/adapter pattern. A reranker's
  own semantic identity (`reranker_identity()`) deliberately does not
  reuse `compute_embedding_identity()` — a reranker has no embedding
  dimension/passage-query convention of that shape; it reuses the
  canonical `semantic_hash()` primitive on its own honestly-shaped
  payload (same pattern as Task 3.4's `sparse_index_identity()`).
- `src/retrieval/reranked.py` — `RerankedRetriever`: retrieves the base
  dense pool once, scores all texts with the cross-encoder, resorts.
  Reranking can only reorder a fixed candidate set, never change it —
  `doc_recall@50` is therefore mathematically identical before and
  after, verified at run time
  (`src.eval.phase3_rerank.assert_candidate_set_recall_unchanged`).
- `src.eval.metrics.precision_at_k()` — new Task 3.6 metric, reusing the
  same binary-relevance-vector convention (`document_relevances_at_k`,
  one hit maximum) already established for nDCG — never a new
  deduplication rule.
- `src/eval/phase3_rerank.py` — config-hash wrapper, the frozen
  selection rule (`select_rerank_configuration`), and the reranking
  ablation row. Its own `is_practical_tie_rerank()` is keyed on the
  Recall@5 hit delta (this task's primary depth), deliberately distinct
  from Task 3.2's Recall@50-keyed rule (meaningless here — reranking
  cannot change Recall@50 by construction) and Task 3.5's Recall@10-keyed
  rule (a different depth).

## Formal evaluation (Stage 7)

One dense retrieval pass per question produces the 50-chunk base pool;
the same 50 chunks are rescored by the cross-encoder and resorted — no
second dense retrieval call, no embedding/index rebuild, no sparse
retrieval, no generation. The dense parent was verified to reproduce its
frozen Task 3.3 per-question metrics exactly (89/89 questions) before
any reranked number was trusted.

## Results — a large, credible negative result

```text
                no_rerank (dense-only)   reranked (ce_minilm_l6)   delta
doc_recall@5:   0.9663 (86/89)           0.7753 (69/89)            -0.1910
doc_precision@5: 0.1933                  0.1551                    -0.0382
doc_mrr:        0.9251                   0.6580                    -0.2671
doc_ndcg@10:    0.9407                   0.7074                    -0.2333
```

This is not a subtle tie: the 95% paired bootstrap intervals are
entirely below 0 for both MRR (`[-0.3499, -0.1869]`) and nDCG@10
(`[-0.3060, -0.1627]`), and hit@5 vs no-rerank shows `gained=0, lost=17,
unchanged=72` — reranking never helps a single question and actively
demotes the correct document out of the top-5/top-10 window for 17 of
89. `doc_recall@50` is unchanged (89/89, verified identical by
construction — same candidate set, only reordered), confirming the
regression is purely a reranking-quality effect, not a retrieval bug.

**Selected: `no_rerank`** — "reranking does not improve any ranking
metric over no-rerank on the frozen priority order." The frozen rule
resolved this cleanly and automatically (uniformly worse on every
metric, not a one-up-one-down trade-off, so no user decision was
required).

### Why this likely happened (not investigated further — out of scope for this task)

`cross-encoder/ms-marco-MiniLM-L6-v2` is trained on MS MARCO web-search
query/short-passage pairs. SEC 10-K chunks are long, dense financial
narrative/tabular text quite unlike its training distribution, and the
frozen `max_seq_length=512` truncates most 256-token chunks only
lightly, so truncation is an unlikely sole cause. A domain-mismatched
cross-encoder producing meaningfully *worse* rankings than a purpose-
benchmarked dense embedding (Task 3.3) is a plausible, unsurprising
outcome — investigating further (e.g. trying the deferred "larger
quality ceiling" candidate, or a finance-domain reranker) is a decision
for a future task, not this one.

## Ablation table

Row `ce_minilm_l6` appended to `results/phase_3_ablation_table.csv`
(`configuration=cross_encoder_reranking`, `retrieval_mode=dense_only`,
`dense_used_in_this_row=true`, `selected=no_rerank`). Every prior row
(0, A0–C1, the four Task 3.3 embedding candidates, Task 3.4's
`bm25_fts`, Task 3.5's `hybrid_rrf`) verified byte-for-byte unchanged in
every pre-existing column; the table gained new rerank-specific columns
(`reranker_model`, `reranker_revision`, `reranker_identity`,
`rerank_base_k`, `doc_recall_at_5`, `doc_recall_at_5_hits`,
`delta_vs_no_rerank_*`, `hit5_gained_vs_no_rerank`,
`hit5_lost_vs_no_rerank`, `reranker_latency_p50_ms`,
`reranker_latency_p95_ms`; `selected` is shared with Task 3.5's hybrid
row), which every prior row now carries as `N/A` — the same additive
mechanism Tasks 3.4/3.5 already established.

## Build/orchestration

`scripts/run_phase3_reranker.py` — `--plan` / `--run` (Stages 1–7) /
`--compare` (Stages 8–9) / `--status` (read-only).

## Tests

46 new tests across `tests/test_cross_encoder.py`,
`tests/test_reranked_retriever.py`, `tests/test_phase3_rerank.py`,
`tests/test_phase3_reranker_script.py`, plus 4 new `precision_at_k` unit
tests in `tests/test_metrics.py` — all portable (fake retrievers/score
functions, no real model download, no GPU, no network). Full suite:
1650 passed (was 1600 before Task 3.6), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_reranker.py`, `src/rerank/cross_encoder.py`,
`src/retrieval/reranked.py`, or `src/eval/phase3_rerank.py` (AST-verified,
portable test). No paid API/generation calls. FinanceBench not rerun.
Frozen Task 3.2 chunk config, Task 3.3 dense winner identity, and Task
3.5 selection (`dense_only`) verified unchanged before the run. Row 0
and every Task 3.2/3.3/3.4/3.5 ablation-table row confirmed byte-for-byte
unchanged in their pre-existing columns.

## Limitations

- Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-
  subset (4.9% of full DEV).
- Only `cross-encoder/ms-marco-MiniLM-L6-v2` was benchmarked — the
  roadmap's optional larger-quality-ceiling comparison was explicitly
  deferred, not attempted in this round.
- `doc_recall@50` is mathematically identical before/after reranking
  (same candidate set, only reordered) — never claimed as an
  improvement or regression.
- `chunk_recall@10`, `chunk_mrr`, `faithfulness`, `citation_grounding`,
  and generation metrics remain N/A.

## Next roadmap task

Phase 3, Task 3.7 — CRAG-style confidence grading, using
`qwen3_embedding` dense-only retrieval (unreranked — Task 3.6 selected
`no_rerank`) as the candidate source.
