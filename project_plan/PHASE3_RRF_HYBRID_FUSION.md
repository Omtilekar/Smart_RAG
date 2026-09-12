# Phase 3 RRF Hybrid Fusion

Established in Task 3.5. Reciprocal Rank Fusion (RRF) over the two
already-frozen Phase 3 retrieval components — the Task 3.3 dense winner
(`Qwen/Qwen3-Embedding-0.6B`) and the Task 3.4 sparse LanceDB-native FTS
baseline — evaluated over the exact frozen 89-question `DEV/evaluable-
subset`. Fusion only: chunking, the dense model/index, and the sparse
index are unchanged from Tasks 3.2–3.4.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.5: fuse dense + sparse
candidates with RRF; measure whether hybrid retrieval improves ranking
quality while preserving the dense model's already-perfect
`doc_recall@50` candidate-set ceiling (89/89).

## Parent-stream reproduction (Stage 2)

Neither parent's full top-50 ranked chunk list was persisted anywhere
with self-verifying provenance suitable for direct reuse (Task 3.3
never wrote per-query ranked lists to disk; Task 3.4's git-ignored
diagnostics predate this task and carry no embedded identity tag). This
script therefore **reruns retrieval only** for both parents against
their already-frozen, unmodified artifacts — no embeddings recomputed,
no index rebuilt. Every one of the 89 recomputed per-question metrics
(hit10/rank10/rr10/ndcg10/hit50/rank50) is verified to reproduce the
frozen Task 3.3/3.4 values **exactly** before the hybrid result is
trusted:

```text
[HYBRID] dense parent reproduces frozen metrics exactly (89 questions).
[HYBRID] sparse parent reproduces frozen metrics exactly (89 questions).
```

## RRF definition (frozen, untuned)

```text
rrf_k = 60
RRF(d) = [1/(rrf_k+dense_rank(d)) if d in dense candidates else 0]
       + [1/(rrf_k+sparse_rank(d)) if d in sparse candidates else 0]
```

Ranks are 1-based. Fusion uses ranks only — dense cosine distances and
sparse `_score` values are preserved on the fused result for provenance
but are never normalized, scaled, or added into `rrf_score`. Fusion
happens at the **chunk_id** level, never `document_id`.

Candidate pools: dense depth 50, sparse depth 50, final hybrid depth 50.
Deterministic tie-break (only ever changes exact-score ties): higher
`rrf_score` → lower `best_parent_rank` → lower dense rank (missing =
∞) → lower sparse rank (missing = ∞) → lexical `chunk_id` ascending.

## New modules

- `src/retrieval/fusion.py` — pure `rrf_fuse()`, no I/O, no LanceDB, no
  model. Validates `rrf_k`/`limit`, rejects a duplicate `chunk_id`
  within one parent stream, never mutates parent result objects.
- `src/retrieval/hybrid.py` — `HybridRetriever`, the composition
  boundary: calls the dense retriever exactly once, the sparse
  retriever exactly once, fuses with `rrf_fuse()`. A parent failure
  propagates — never silently degrades to a one-arm result.
- `src/eval/phase3_hybrid.py` — hybrid-vs-dense/hybrid-vs-sparse
  gain/loss classification, first-gold-hit-rank movement, fusion-source
  composition, the frozen Stage 9 selection rule
  (`select_hybrid_configuration`), and the hybrid ablation row. Reuses
  `phase3_baseline`/`phase3_ablation`'s scope guards and paired
  bootstrap unmodified. Deliberately does **not** reuse
  `phase3_ablation.is_practical_tie()` (that rule is keyed on a
  Recall@50 hit delta, which is structurally uninformative here since
  Gate 1 already requires hybrid to match dense's 89/89 ceiling exactly)
  — a correctly-scoped `is_practical_tie_hybrid()` keyed on the
  Recall@10 hit delta is defined instead, per Stage 9's own spec.

## Results

```text
Mode          R@10       R@50       MRR       nDCG@10
Dense Qwen    88/89      89/89      0.9251    0.9407
Sparse FTS    86/89      88/89      0.8830    0.9028
RRF hybrid    88/89      89/89      0.9457    0.9566
```

Hybrid preserves the dense model's 89/89 R@50 ceiling exactly (Gate 1
passes) and raises both MRR (+0.0206) and nDCG@10 (+0.0160) as point
estimates over dense. However, the 95% paired bootstrap intervals for
both deltas include 0 (N=89), and the Recall@10 hit delta is exactly 0
(hybrid gains 1 question, loses 1 question relative to dense) — the
frozen Stage 9 practical-tie rule (`is_practical_tie_hybrid`) therefore
classifies hybrid and dense as **practically tied**.

## Selection (Stage 9)

```text
Selected: dense_only
Reason: hybrid is practically tied with dense (Recall@10 hit delta=0,
MRR/nDCG@10 95% CIs include 0) - dense-only preferred: simpler, avoids
a second retrieval path at query time. Hybrid did not earn its extra
complexity.
```

This is a **fully valid negative result** per the roadmap's own framing
— dense-only remains the selected retrieval mode. Gate 1 (candidate-
recall preservation) passed; Gate 2's practical-tie clause resolved the
trade-off in favor of the simpler architecture, exactly as frozen before
the formal run.

### Per-question movement vs dense

```text
hit@10:  gained=1  lost=1  unchanged=87
hit@50:  gained=0  lost=0  unchanged=89
rank10 movement: improved=9  worsened=4  unchanged=76
```

### Fusion-source composition

```text
top10 (890 slots across 89 questions): both=714  dense_only=97  sparse_only=79
top50 (4450 slots across 89 questions): both=1084  dense_only=1710  sparse_only=1656
```

Hybrid genuinely draws on sparse evidence at both depths (not merely
reproducing dense order) — roughly 18% of top-10 hybrid slots came
exclusively from the sparse arm.

## Ablation table

Row `hybrid_rrf` appended to `results/phase_3_ablation_table.csv`
(`configuration=rrf_hybrid_fusion`, `retrieval_mode=hybrid`,
`dense_used_in_this_row=true`, `selected=dense_only`). Every prior row
(0, A0–C1, the four Task 3.3 embedding candidates, Task 3.4's
`bm25_fts`) verified byte-for-byte unchanged in every pre-existing
column; the table gained new hybrid-specific columns (`fusion_method`,
`rrf_k`, `dense_candidate_k`/`sparse_candidate_k`/`final_candidate_k`,
`sparse_index_identity`, `delta_vs_sparse_*`, `hit10_gained_vs_dense`,
`hit10_lost_vs_dense`, `hit50_gained_vs_dense`, `hit50_lost_vs_dense`,
`hybrid_both_parent_top10/50`, `hybrid_dense_only_top10/50`,
`hybrid_sparse_only_top10/50`, `dense_latency_p50_ms`,
`sparse_latency_p50_ms`, `fusion_latency_p50_ms`, `selected`), which
every prior row now carries as `N/A` — the same additive mechanism Task
3.4 already established.

## Build/orchestration

`scripts/run_phase3_rrf_hybrid.py` — `--plan` / `--run` (Stages 1–7) /
`--compare` (Stages 8–9) / `--status` (read-only).

## Tests

162 new tests across `tests/test_rrf_fusion.py`,
`tests/test_hybrid_retriever.py`, `tests/test_phase3_hybrid.py`, and
`tests/test_phase3_rrf_hybrid_script.py` — all portable (synthetic
parent-ranking fixtures, no real corpus, no GPU, no model, no network).
Full suite: 1600 passed (was 1518 before Task 3.5), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported by `scripts/run_phase3_rrf_hybrid.py`, `src/retrieval/fusion.py`,
`src/retrieval/hybrid.py`, or `src/eval/phase3_hybrid.py` (AST-verified,
portable test). No paid API/generation calls. FinanceBench not rerun.
Frozen Task 3.2 chunk config, Task 3.3 dense winner identity, and Task
3.4 sparse baseline identity verified unchanged before the run. Row 0
and every Task 3.2/3.3/3.4 ablation-table row confirmed byte-for-byte
unchanged in their pre-existing columns.

## Limitations

- Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-
  subset (4.9% of full DEV).
- N=89 is small; the practical-tie rule is exactly why a promising point
  estimate (+0.02 MRR) did not translate into a selected architecture
  change — a larger DEV scope could change this conclusion.
- `doc_recall@50` was already at ceiling (89/89) for the dense parent,
  so hybrid could only match it, never improve it — this is expected
  and documented, not a flaw in the fusion.
- No reranking, CRAG, router, or metadata pre-filtering — RRF fusion
  only.
- `chunk_recall@10`, `chunk_mrr`, `precision@5`, `faithfulness`,
  `citation_grounding`, and generation metrics remain N/A.

## Next roadmap task

Phase 3, Task 3.6 — cross-encoder reranking, using `qwen3_embedding`
dense-only retrieval (the Task 3.5-selected mode) as the candidate
source.
