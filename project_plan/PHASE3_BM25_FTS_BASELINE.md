# Phase 3 LanceDB BM25/FTS Sparse Baseline

Established in Task 3.4. A DEV-only, sparse-only lexical retrieval
baseline built with LanceDB-native full-text search over the frozen Task
3.2 chunking winner (`fixed`/256/0), evaluated over the exact frozen
89-question `DEV/evaluable-subset` used by Tasks 3.1–3.3. Retrieval
modality only changes (`dense-only -> sparse-only`); chunks, the frozen
Task 3.3 dense winner identity, candidate depth (50), and every metric
implementation stay identical to prior Phase 3 tasks. No hybrid fusion,
no reranking, no CRAG, no router, no metadata pre-filtering, no
generation.

## Objective

`project_plan/PROJECT_EXECUTION.md` Task 3.4: add LanceDB-native
FTS/BM25 as the initial sparse baseline, verify raw scores/ranks are
available, and compare dense vs sparse retrieval independently (no
fusion) as evidence for the Task 3.5 hybrid-retrieval decision.

## Installed LanceDB API audit (Stage 2)

Installed version: **`lancedb==0.37.1`**. Audited empirically against a
disposable synthetic table before any real-corpus code was written
(never assumed from memory or a different version):

- `Table.create_fts_index(...)` is deprecated as of lancedb 0.25.0. The
  supported path is `table.create_index(column, config=FTS())`.
- Native score field: **`_score`**, **higher is better** — verified
  directly (a chunk mentioning a term 3× outranked one mentioning it
  once for that term's query).
- Result ordering matches descending `_score`.
- `table.list_indices()` / `table.index_stats(name)` give full index
  introspection (type, columns, row/segment counts, and the exact
  tokenizer configuration used).
- The index (and its exact configuration) persists across a fresh
  `lancedb.connect()` in a brand-new process — verified by reopening a
  probe table from a new connection object.
- With the installed default `with_position=False`, a query containing
  a literal ASCII double-quote character (`"`) is parsed as a phrase
  query and raises `ValueError: Invalid input, position is not found
  but required for phrase queries...` for otherwise ordinary text. No
  other character class tested (percent signs, currency symbols,
  hyphenated terms, slashes, parentheses, Unicode punctuation, `10-K`,
  `Item 1A`, `R&D`, apostrophes, curly quotes, boolean-looking words
  like `AND`/`OR`/`NOT`) raised an error. Verified separately that
  **none** of the 89 frozen DEV question texts contain a literal
  double-quote character, so this finding never changes the formal
  Task 3.4 result — `src.index.lancedb_fts.sanitize_fts_query()`
  strips that one character class anyway, so the general-purpose
  `SparseRetriever` boundary never crashes on ordinary natural-language
  input.

## Frozen sparse contract

`configs/phase_3_4_bm25_fts_baseline.json` freezes: the frozen 89-
question scope identity (verified against
`results/phase_3_1_trusted_baseline.json` before the formal run), the
frozen `chunk_config_hash`
(`ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06` —
fixed 256-token windows, zero overlap), the frozen Task 3.3 dense
winner identity (recorded for provenance/Stage-8 comparison only —
never used to score a sparse query), the simplest documented/default
LanceDB `FTS()` configuration (never tuned: `simple` tokenizer,
`stem=True`, `remove_stop_words=True`, `lower_case=True`,
`ascii_folding=True`, `with_position=False`), the query-sanitization
rule above, `candidate_k=50`, and every non-retrieval component
explicitly `false` (generation/reranker/CRAG/router/metadata-
pre-filter).

## Sparse artifact identity (never overloading Task 2.10's embedding-based index identity)

`src.artifacts.versioning.compute_index_identity()` requires an
`embedding_identity_hash` — a real semantic fact for a dense index that
a sparse-only artifact does not have. Rather than force a fake
embedding identity into that field, `src.index.lancedb_fts.sparse_index_identity()`
defines its own honestly-shaped identity (chunk semantics + LanceDB
version + table/column/index-name + tokenizer config), hashed with the
same canonical `semantic_hash()` primitive (never a second hashing
implementation). The sparse artifact lives at a **separate** LanceDB
path (`artifacts/indexes/<chunk_config_hash>/lancedb_fts_sparse/`) from
the trusted Task 3.3 dense Qwen index — the dense artifact was never
opened, mutated, or touched during Task 3.4.

## Build

`scripts/run_phase3_bm25_fts_baseline.py --build` indexes the frozen
Task 3.2 chunk Parquet directly (same chunk IDs, document IDs, text,
metadata — no rechunking, no re-normalization, no embedding step).

```text
rows indexed:      323,971
FTS build time:    3.9s
index size:        295,378,841 bytes (~282 MB)
```

Reopened in a fresh `lancedb.connect()` call and re-validated (row
count, indexed column, FTS index presence/type) before evaluation.

## Sparse-query robustness smoke (Stage 6)

Real sparse artifact, 10 representative query shapes (mixed case,
punctuation, `%`, `$`, year/number, hyphenated terms, slashes,
parentheses, Unicode punctuation, `Item 1A`/`10-K`/`R&D`) plus 6
malformed/edge inputs (empty string, whitespace-only, non-string
question, `k=0`, negative `k`, boolean `k`) — every malformed input was
rejected cleanly with `TypeError`/`ValueError`, no crash.

## Formal evaluation (Stage 7)

Exactly the frozen 89-question `DEV/evaluable-subset`, `candidate_k=50`,
generation and dense retrieval both OFF.

```text
doc_recall@10:  86/89 = 0.9663
doc_recall@50:  88/89 = 0.9888
doc_mrr:        0.8830
doc_ndcg@10:    0.9028
p50 latency:    6.5 ms   p95 latency: 8.5 ms
```

`src.eval.baseline_metrics.evaluate_question()` requires exactly `k`
ranked results (correct for dense exact-cosine search, which always
returns `k` rows). LanceDB's native FTS only returns rows with a
nonzero match score, so a sparse query can legitimately return fewer
than `candidate_k`. The script therefore computes doc_recall@10/@50,
doc_mrr, and doc_ndcg@10 directly from Task 2.6's granularity-agnostic
`first_hit_rank()`/`hit_at_k()`/`reciprocal_rank()`/`ndcg_at_k()` plus
Task 3.1's `document_relevances_at_k()` — the same functions Task 1.10's
own docstring guarantees reproduce identical semantics, never a new
metric implementation. No question in the formal 89-question run was
actually underfilled below 50 results.

## Dense vs sparse comparison (Stage 8, analysis only — no fusion)

Paired by `question_id` against the frozen Task 3.3 `qwen3_embedding`
dense winner, using `src.eval.phase3_ablation.paired_bootstrap_delta_ci`
(seed 42, 10,000 iterations) reused unmodified:

```text
                delta        95% CI includes 0?
doc_recall@10:  -0.0225
doc_recall@50:  -0.0112
doc_mrr:        -0.0422
doc_ndcg@10:    -0.0378
```

Dense is stronger overall on this scope — consistent with Task 3.3's
result and expected for a purely lexical baseline against a strong
instruction-tuned dense encoder. This is a **valid, useful** Task 3.4
outcome per the roadmap's own framing: standalone aggregate quality
does not need to beat dense for the sparse baseline to be worth
keeping as a hybrid-fusion input.

### Complementarity (the evidence Task 3.5 needs)

```text
hit@10:  both=85   dense_only=3   sparse_only=1   neither=0
hit@50:  both=88   dense_only=1   sparse_only=0   neither=0
```

Sparse uniquely recovers **1** question dense misses at hit@10 that
dense alone would not answer, while losing 3 dense catches — non-zero
complementarity in both directions is direct evidence that Task 3.5
(RRF hybrid fusion) is worth attempting, without pre-judging the
outcome.

First-hit-rank@10 comparison: `sparse_better=10`, `dense_better=13`,
`same=66`.

## Ablation table

Row `bm25_fts` appended to `results/phase_3_ablation_table.csv`
(`configuration=sparse_lancedb_fts_baseline`, `retrieval_mode=sparse_only`,
`dense_used_in_this_row=false`). Every prior row (`0`, `A0`–`C1`, the
four Task 3.3 embedding candidates) is verified byte-for-byte unchanged
in every pre-existing column; the table gained new sparse-specific
columns (`retrieval_mode`, `sparse_backend`, `lancedb_version`,
`fts_indexed_column`, `dense_used_in_this_row`,
`delta_vs_qwen_dense_*`, `dense_only_hits_at_*`, `sparse_only_hits_at_*`,
`fts_build_seconds`, `fts_index_size_bytes`, `fts_search_latency_p*`),
which every prior row now carries as `N/A` — additive, never a breaking
schema change (`src.eval.phase3_baseline._row_to_csv_dict()`'s existing
`.get(col, NA)` default already anticipated exactly this extension).

## Build/orchestration

`scripts/run_phase3_bm25_fts_baseline.py` — `--plan` / `--build` /
`--evaluate` / `--compare` / `--run` (all three in sequence) /
`--status` (read-only). New reusable modules:

- `src/index/lancedb_fts.py` — LanceDB-native FTS index build/search
  primitives and the sparse artifact identity (companion to, never a
  modification of, `src/index/lancedb_index.py`).
- `src/retrieval/sparse.py` — `SparseRetriever.retrieve(question, k=50)`,
  the sparse-only application boundary (companion to, never a
  modification of, `src/retrieval/baseline.py`). Preserves the native
  `_score` faithfully as `sparse_score`; never renames it to a dense-
  style distance, never normalizes it across queries, never combines it
  with a dense score.
- `src/eval/phase3_sparse.py` — pure-logic config hash, dense/sparse hit
  complementarity, first-hit-rank comparison, and the sparse ablation
  row, reusing `src.eval.phase3_baseline`/`phase3_ablation`'s scope
  guards and paired bootstrap unmodified.

## Tests

77 new tests across `tests/test_lancedb_fts.py`,
`tests/test_sparse_retriever.py`, `tests/test_phase3_sparse.py`, and
`tests/test_phase3_bm25_fts_script.py` — all portable (tiny disposable
LanceDB tables, no real corpus, no GPU, no model, no network). Full
suite: 1518 passed (was 1441 before Task 3.4), 0 skipped.

## Regression gates

Protected SEC TEST: unopened, 0/3 official runs used throughout — never
imported/touched by `scripts/run_phase3_bm25_fts_baseline.py` or any
Task 3.4 module (AST-verified, portable test). No paid API/generation
calls. FinanceBench not rerun. Frozen Task 3.2 chunk config and Task
3.3 dense winner identity verified unchanged before every stage. Row 0
and every prior ablation-table row verified byte-for-byte unchanged in
their pre-existing columns.

## Limitations

- Evaluated only over the frozen Task 3.1 89-question DEV/evaluable-
  subset (4.9% of full DEV).
- N=89 is small; bootstrap CIs govern which sparse-vs-dense differences
  are credible.
- Sparse-only baseline: no RRF/hybrid fusion, no reranking, no CRAG, no
  router, no metadata pre-filtering, no generation.
- `chunk_recall@10`, `chunk_mrr`, `precision@5`, `faithfulness`,
  `citation_grounding`, and generation metrics remain N/A.

## Next roadmap task

Phase 3, Task 3.5 — RRF hybrid fusion of the frozen Task 3.3 dense
candidates with this Task 3.4 sparse baseline, using the complementarity
evidence above.
