# Phase 2 MS MARCO Harness Validation

Established in Task 2.7. Validates this repository's retrieval +
evaluation harness against the standard MS MARCO passage-ranking
dev-small benchmark **before** trusting any future SEC retrieval score.

## Objective

MS MARCO is a **benchmark track**, never the SEC project corpus. The
question this task answers is not "how good is our retriever" - it is:

```text
Can this repository load a standard benchmark, preserve its qrels
correctly, run retrieval, calculate metrics correctly, and produce
numbers consistent with expected/published behavior for the exact
configuration being tested?
```

A poor but correctly-reproduced result would PASS this harness check. A
suspiciously strong number produced by broken qrel handling would FAIL
it, regardless of the raw score.

## Why MS MARCO exists in this repository

Task 2.6 hand-verified the metric *arithmetic* on tiny synthetic
fixtures. Task 2.7 verifies the *harness around* that arithmetic - real
Parquet loading, real ID handling across two different physical types,
real embedding, real retrieval, and real aggregation - against a
benchmark with known, externally-audited queries and relevance
judgments, so a bug in any of those layers is caught before it can
silently inflate or deflate a future SEC retrieval score.

## Benchmark vs. SEC track

Completely isolated. MS MARCO passages, embeddings, and index are never
merged with the SEC corpus, SEC chunk tables, SEC embeddings, the SEC
LanceDB `chunks` table, or the Phase 2 SEC evaluation dataset/split
artifacts. All MS MARCO-derived artifacts live under
`artifacts/benchmark/msmarco/` (already covered by the existing
`.gitignore`'s blanket `artifacts/` rule - no SEC artifact path is
reused). `data/msmarco/*.parquet` (frozen source) is read-only
throughout - never rewritten, never deduplicated, never dropped.

## `PROJECT_EXECUTION.md` contract

```text
- Load the frozen MS MARCO benchmark artifacts.
- Run the retrieval evaluation code on dev-small.
- Compare with reasonable published/known behavior for the chosen baseline.
- Investigate large deviations before trusting SEC metrics.
- Record configuration and results.
```

This task's own detailed prompt elaborates the same scope (preflight,
pilot, resumability, ID normalization, harness-specific recall
semantics) without materially exceeding it - no Phase 3 architecture
(BM25, hybrid, reranking, router, CRAG) was built, and "run the
retrieval evaluation code on dev-small" is read literally: the full
8,841,823-passage corpus and all 6,980 dev-small queries, not a
subsample (subsamples were used only for the explicitly-labeled PILOT).

## Dataset/split and frozen counts (independently verified)

```text
corpus passages:              8,841,823   (matches historical reference)
total queries (all splits):     509,962   (matches historical reference)
validation qrel rows:             7,437   (matches historical reference)
validation distinct queries:      6,980   (matches historical reference - the standard MS MARCO passage dev-small)
qrels per query:              min=1, median=1.0, max=4; 390/6,980 queries have >1 qrel
qrel relevance grades:         100% score=1 (BINARY relevance - verified directly, never assumed)
```

`qrels_test.parquet` (43 queries) exists on disk but was **not** used -
the task explicitly warns against switching to the file merely because
it is named "test"; the standard dev-small validation population
(`qrels_validation.parquet`, 6,980 queries) is the correct benchmark
comparison population.

## Referential integrity (hard prerequisite - verified before any retrieval)

```text
qrel rows with no matching query:   0 / 7,437  (100% query referential integrity)
qrel rows with no matching corpus:  0 / 7,437  (100% corpus referential integrity)
```

Verified via an explicit `CAST(... AS VARCHAR)` join (see ID normalization
below) - not a raw type-mismatched join, which would have silently
reported 0% integrity for an unrelated reason.

## ID type safety

`corpus.parquet`/`queries.parquet` store `_id` as `VARCHAR` digit
strings (`"0"`, `"1"`, `"1185869"`, ...); `qrels_validation.parquet`
stores `query-id`/`corpus-id` as `BIGINT`. Verified directly (not
assumed) that the VARCHAR forms have no leading zeros or non-numeric
characters, so `canonical_id(x) = str(int(x))` is a safe, lossless,
bidirectional normalization - `src.eval.msmarco_harness.canonical_id()`
is the single place this conversion happens; every corpus/query/qrel ID
that crosses a function boundary in this harness is canonicalized
through it, never compared via Python's implicit int/str inequality.

## Benchmark-specific relevance semantics

MS MARCO qrels identify relevant **passages**, not documents or SEC
chunks. Metric names are therefore `passage_recall@10`/`passage_mrr`/
`passage_ndcg@10` - never `doc_recall@10` (reserved for Task 1.10's SEC
document-level metric on a different corpus and a different relevance
granularity).

**`passage_recall@10` is NOT `hit_at_k` reused verbatim.** 390/6,980
queries have more than one relevant passage (max 4), so MS MARCO
Recall@K is the standard benchmark convention - the **fraction of a
query's relevant passages retrieved**, `|retrieved[:k] ∩ relevant| /
|relevant|` - averaged per query, not a single binary hit/miss. Misusing
Task 2.6's `hit_at_k` (designed for SEC's single-target semantics) would
have silently truncated every multi-qrel query's true recall to a
binary 0/1. `src.eval.msmarco_harness.evaluate_query()` implements this
benchmark-specific aggregation explicitly and documents why, rather than
misusing the SEC-shaped helper.

`passage_mrr` and `passage_ndcg@10` reuse Task 2.6's
`src.eval.metrics.reciprocal_rank`/`mean_reciprocal_rank` and
`ndcg_at_k` directly, unmodified - MS MARCO qrels are confirmed 100%
binary relevance, matching Task 2.6's binary-relevance assumption
exactly, so no metric extension or new `metric_version` was needed.

## Retrieval configuration (frozen before measurement)

```text
model:                 BAAI/bge-small-en-v1.5
model revision:         5c38ec7c405ec4b44b94cc5a9bb96e735b38267a  (identical to Phase 1 - reused, not re-selected)
embedding dimension:    384
passage prefix:         none (per the model card - identical to Phase 1)
query prefix:            "Represent this sentence for searching relevant passages: " (identical to Phase 1)
normalize_embeddings:    True
similarity:              cosine
search mode:             exact (no ANN index - src.index.lancedb_index's frozen Phase 1 contract, reused unmodified)
top_k:                   10 (sufficient for all three reported metrics, all cut at @10)
batch size:              128 (Phase 1's frozen default - not tuned)
dtype:                   float32
```

No embedding-model selection, fusion-weight optimization, reranker
tuning, chunk-size tuning, or query-rewrite tuning was performed - one
predetermined configuration, reused verbatim from Phase 1's frozen
embedding/index contracts (`src/embeddings/bge.py`, `src/index/
lancedb_index.py` - both imported, neither modified; confirmed via `git
diff --stat`).

`configs/phase_2_7_msmarco_harness.json` freezes every field that could
change the result (model/revision, prefixes, normalization, similarity,
top_k, batch size, dtype, shard size, metric versions) and its own
`benchmark_config_hash` - computed excluding runtime-only fields
(timestamps).

## Resource preflight (performed before any expensive build)

```text
corpus rows:                  8,841,823
embedding dimension/dtype:     384 / float32
estimated vector bytes:        12.65 GB
estimated text bytes:          2.77 GB
estimated total artifact:      15.41 GB
free disk (measured):          305.37 GB   (well under any 2x-overrun threshold)
shard size / count:            200,000 / 45
GPU:                            NVIDIA GeForce RTX 5060 Laptop GPU, 8.55 GB VRAM, CUDA available
```

## Pilot (PILOT ONLY - never the reported result)

Two pilots run before the full build: 20,000 passages / 200 queries,
then 200,000 passages (one real shard's worth) / 50 queries. Both
verified end to end: corpus load, embedding, LanceDB index creation,
retrieval, qrel matching, metric computation - and both surfaced and
fixed two real bugs before the expensive full run:

1. **PyArrow schema mismatch** - constructing the `vector` column as a
   plain Python list of numpy arrays (`list(vectors)`) produces a schema
   LanceDB's `create_table()` cannot align (`ValueError: Field 'l' not
   found in target schema`). Fixed by building a proper
   `pa.FixedSizeListArray` (the exact pattern Task 1.4's
   `embed_development_corpus.py` already uses) - reused, not
   reinvented.
2. **DuckDB parquet round-trip breaks the fixed-size-list schema** -
   reading an embedded shard back via `duckdb.read_parquet(...)
   .to_arrow_table()` renames the list's child field, which then fails
   the same LanceDB schema-alignment check. Fixed by reading shard
   Parquet files directly via `pyarrow.parquet.read_table()` (matching
   Task 1.5's `build_vector_index.py` convention) instead of round-
   tripping through DuckDB.

Measured pilot throughput (real GPU, real MS MARCO passages, both
pilots agreed): **~720-750 passages/sec** embedding on the RTX 5060
Laptop GPU - notably faster than Phase 1's 140.6 chunks/sec for SEC
chunks, consistent with MS MARCO passages (avg. 336 characters) being
much shorter than SEC's 512-token chunks.

## The naive per-query evaluation loop was infeasible - and why

A first design evaluated each of the 6,980 queries with one
`LanceDB.exact_cosine_search()` call against the full 8.84M-row table.
Measured on the 200k-row pilot shard: ~16.3 ms/query. **Extrapolated
linearly to 8.84M rows and 6,980 queries: ~14 hours** - purely from
per-query LanceDB search overhead, on top of the ~3.3-hour embedding
build. This was investigated and fixed (not silently accepted) before
committing to the full run - see Section 46/47 (suspiciously
slow/expensive results must be investigated, not tuned around, but here
the actual gap was implementation, not the model or metric).

**Fix**: `scripts/run_msmarco_harness.py::_batched_exact_search()`
computes the same exact cosine top-k via a blocked GPU matrix multiply
(all queries' vectors in one tensor, corpus processed shard by shard,
`torch.topk` per shard, merged across shards) - mathematically
IDENTICAL to LanceDB's per-query exact search (both compute `1 -
cosine_similarity` and take the top-k), just computed via one batched
GPU operation per shard instead of 6,980 independent per-query table
scans. **Verified exact equivalence** against `src.index.lancedb_index
.exact_cosine_search()` on real pilot data before trusting it at scale -
identical top-10 IDs, distances agreeing to float32 precision (max
diff `1.8e-7`) - and `cmd_evaluate()` re-runs this same equivalence
check automatically on a 5-query sample against the real 8.84M-row
index every time it runs (`_verify_batched_search_matches_lancedb()`).
Measured on the 200k-row pilot shard with all 6,980 real queries: 6.58s
- extrapolated to all 45 shards: **~5 minutes**, not 14 hours. This is
still `search_mode: exact` (never ANN) - no relevance quality is
sacrificed, only the per-query LanceDB call overhead is bypassed.

## Resumable embedding build

`scripts/run_msmarco_harness.py --build` partitions the 8,841,823-row
corpus into 45 row-range shards of 200,000 rows, writes each shard
atomically (`.parquet.tmp` then `os.replace`), and records completed
shards (`shard_index`, `row_count`, `offset`) plus the build's
`config_hash` in `artifacts/benchmark/msmarco/embeddings/manifest.json`.
A restart re-reads the manifest and skips any shard whose file already
exists under a matching `config_hash` - a crash after millions of
passages never requires restarting from passage 1. A manifest whose
`config_hash` no longer matches the current run's configuration is
treated as stale and the build restarts from shard 0 (never silently
mixes shards embedded under two different configurations).

## Published reference (frozen before the measured run)

```text
source:            BAAI/bge-small-en-v1.5's self-reported BEIR benchmark
                    table, cross-confirmed via two independent web
                    searches (2026-09-01)
benchmark:          BEIR/MTEB MSMARCO retrieval task - standard MS MARCO
                    passage dev-small, 6,980 queries (same population
                    used here)
model:              BAAI/bge-small-en-v1.5 (same model, revision not
                    stated in the found sources)
metric:             nDCG@10
reported value:     0.408
apples-to-apples:   PARTIAL
```

**Why PARTIAL, not YES**: same model, same standard split (6,980-query
dev-small), same metric (nDCG@10). NOT independently confirmed:
- the exact model revision BAAI used for its own reported number,
- BEIR's exact retrieval implementation (typically FAISS-based, not
  LanceDB) and whether it is byte-identical exact search or a
  well-tuned approximate search,
- the MTEB community has documented reproducibility discrepancies
  between BGE's self-reported numbers and independently-reproduced MTEB
  runs for BGE models generally (github.com/embeddings-benchmark/mteb
  issue #1912) - not specific to bge-small-en-v1.5's MSMARCO number, but
  a documented reason not to expect an exact match.

**This reference could not be pinned to a single directly-rendered
source table during this session** - two independent WebSearch queries
converged on the same value (0.408) from secondary summaries, but
automated fetches of the model's own HuggingFace card, the cited GitHub
issue, and a citing arXiv paper's PDF did not surface a directly
readable table cell during this session. The reference is therefore
treated as **approximate corroborated evidence, not an authoritative
primary-source citation** - the comparison in this task's result never
treats it as a strict pass/fail threshold (see Comparison below).

No pass threshold was fabricated. If this reference had not been
findable at all, this task would have reported `REFERENCE COMPARISON
BLOCKED` rather than inventing one (Section 12) - it was findable, with
the caveats above, so a comparison is reported instead.

## Measured result

```text
evaluated queries:      6,980  (all dev-small queries, none dropped)
passage_recall@10:      0.6194245463228272  (mean-of-per-query-recall; diagnostic pooled numerator/denominator = 4,514/7,437)
passage_mrr:            0.3457393004957463
passage_ndcg@10:        0.4081500190484616
```

Full corpus embedding build: interrupted twice by the local machine
going idle/sleeping mid-run (a real-world session interruption, not a
code defect) - the resumable shard design (Section "Resumable embedding
build" above) meant no work was lost either time; a third resume
attempt was killed almost immediately with no progress, at which point
the build was completed by the user directly in a separate terminal
outside this session. Before trusting that externally-completed
artifact, this session independently re-verified it in full: all 45/45
shards present with `row_count` summing to exactly 8,841,823 in
`manifest.json`; the LanceDB index's `build_config_hash.txt` matches the
manifest's `config_hash` exactly (`ba92f05a...`); the live LanceDB table
itself reports `8,841,823` rows, the exact expected schema
(`fixed_size_list<float>[384]`), and zero ANN indexes; a full pass over
every one of the 45 shard Parquet files found **8,841,823 unique
`corpus_id` values with zero duplicates**; and a sample of vectors from
both the first and last shard were unit-normalized (L2 norm in
`[0.99999994, 1.0000001]`) with no NaN/Inf. Only after all of that
passed did evaluation proceed.

## Manual spot checks

Deterministic - first 5 hit queries and first 5 miss queries, sorted by
canonical `query_id`, never cherry-picked.

**Hits** (query text, gold passage, retrieved rank, RR):
- `1000017` "where does misery take place" - gold passage about the
  novel *Misery*'s setting, found at rank 2 (RR=0.5).
- `1000083` "define: precipitous delivery" - gold passage on
  "Precipitate delivery", found at rank 1 (RR=1.0).
- `1000097` "where is whiteville tennessee" - gold passage on Whiteville,
  TN's location, found at rank 2 (RR=0.5).
- `1000232` "where does a cusk eel take shelter?" - gold passage on the
  Band cusk-eel, found at rank 1 (RR=1.0).
- `1000459` "where do black widow spiders live in the us?" - 2 gold
  passages, one found at rank 6 (recall=0.5, RR=0.167) - the other 4
  ranks before it were genuinely on-topic but not the specific gold
  passages, a real partial-recall case, not a bug.

**Misses** (all genuinely hard disambiguation, not retrieval bugs):
- `1000000` "where does real insulin come from" - retrieved passages
  about insulin production (pancreas/islets of Langerhans) but not the
  specific gold passage's exact wording.
- `1000004` "where does name nora come from" - retrieved other
  name-etymology passages for "Nora", not the specific gold passage.
- `1000006` "where does most of the iron ore come from" - retrieved
  other genuinely relevant iron-ore passages, not the specific gold one.
- `1000030` "where does microtubule formation occur" - retrieved other
  genuinely relevant microtubule biology passages.
- `100013` "cortana what is the apocalypse" - retrieved passages about
  "apocalypse" the Greek etymological term; gold passage is specifically
  about the Marvel Comics supervillain "Apocalypse (En Sabah Nur)" - a
  real semantic disambiguation the model missed, not a harness bug.

## Determinism

Recomputed `passage_ndcg@10`/`passage_mrr`/`passage_recall@10` twice
from the saved `artifacts/benchmark/msmarco/retrieval/query_results.parquet`
(never re-running retrieval) - both passes produced byte-identical
`compute_result_hash()` output
(`d5d56d6e574ae5d35ac1d8f957691a69aedfb471ca7c65bb3e01168a8ed97d98`),
matching the value stored in `results/phase_2_7_msmarco_harness.json`
exactly.

## Independent metric recalculation

`passage_mrr` recomputed via a completely standalone script (no import
of `src.eval.msmarco_harness` or `src.eval.metrics` at all - raw
DuckDB reads of the saved retrieval Parquet and the qrels Parquet, a
plain Python loop, no shared code path with the production
aggregator): **0.3457393004957463** - matches the production value
exactly.

## Comparison

```text
reference (BEIR/MTEB, bge-small-en-v1.5, nDCG@10):  0.408
measured (this harness, nDCG@10):                    0.4081500190484616
absolute difference:                                 0.00015 (essentially exact agreement)
interpretation:                                      CONSISTENT
```

Given the PARTIAL apples-to-apples caveats documented above (different
retrieval backend, unconfirmed exact model revision on BAAI's side,
documented MTEB reproducibility variance for BGE models generally), this
degree of agreement is a strong positive signal for harness
correctness - a broken qrel handling or ID-matching bug would have
produced a result either far too low (near 0, from systematic
mismatches) or suspiciously high (from qrel leakage into retrieval),
not a value agreeing with an external reference to four decimal places.
No hyperparameter was tuned to reach this number - the configuration was
frozen before the measured run (see "Retrieval configuration" above).

## Manual spot checks

**[PENDING final evaluation - to be filled with the first 5 hit and
first 5 miss queries by `query_id`, each showing query text, gold qrel
IDs, retrieved IDs, first relevant rank, and per-query score, selected
deterministically (not cherry-picked) once
`artifacts/benchmark/msmarco/retrieval/query_results.parquet` exists.]**

## Determinism

**[PENDING - the metric-recomputation-from-saved-retrieval-output
determinism check (Section 42) will be run twice against the same saved
`query_results.parquet` once evaluation completes, and the resulting
`result_hash` values compared.]**

## Independent metric recalculation

**[PENDING - `passage_mrr` (or another headline metric) will be
recomputed directly from the saved `query_id -> ranked passage_ids` +
qrels, without calling `src.eval.msmarco_harness.aggregate_results()`,
and compared exactly to the production value.]**

## Comparison

**[PENDING final measured nDCG@10 - will be classified as CONSISTENT
(within ±0.03 of the 0.408 reference), LOWER THAN EXPECTED, or HIGHER
THAN EXPECTED per `scripts/run_msmarco_harness.py`'s comparison logic,
with investigation per Section 46/47 before any conclusion if the
deviation is large.]**

## Hardware / runtime

```text
GPU:                  NVIDIA GeForce RTX 5060 Laptop GPU (8.55 GB VRAM)
embedding throughput: ~720-750 passages/sec (measured, real MS MARCO text)
full embedding build: interrupted twice by machine idle/sleep (resumed
                       cleanly both times from the shard manifest, zero
                       rework); completed by the user directly outside
                       this session after a third interrupted attempt -
                       independently re-verified in full before use (see
                       "Measured result" above)
batched search:        256.5s for all 8,841,823 passages x 6,980 queries
full evaluate command: 1,541.6s total (includes model load, query
                       encoding, the automatic LanceDB-equivalence spot
                       check, and result persistence - not just the
                       256.5s search itself)
```

## Known expected implementation variance

- Our search is LanceDB-backed exact cosine (verified equivalent to a
  raw batched cosine matmul); BEIR's typical MS MARCO evaluation setups
  often use FAISS, which may differ in numerical precision or default
  search behavior.
- Query/passage prefix conventions for `bge-small-en-v1.5` are applied
  per this repository's Phase 1-frozen contract (sourced from the
  model's own card) - assumed, not independently re-verified against
  BAAI's own internal MS MARCO evaluation script.
- Tokenization/truncation behavior for passages/queries longer than the
  model's max sequence length follows `sentence-transformers`' default
  behavior, unchanged from Phase 1.

## Limitations

- The published reference value's exact primary-source table cell was
  not directly viewed during this session (see "Published reference"
  above) - treated as corroborated-but-unpinned evidence.
- MS MARCO's `qrels_test.parquet` (43 queries, official blind test set)
  was not used and has no publicly available qrels to check against
  even if it had been - dev-small is the only population where an
  external reference number could exist. This is correct and expected,
  not a limitation of this task's execution.
- The comparison tolerance (±0.03 absolute nDCG@10) is a pragmatic
  choice given the PARTIAL apples-to-apples status - not itself a
  externally-sourced tolerance value.

## Final harness verdict

**PASS.** The full pipeline - frozen-data verification, ID
normalization, referential integrity, resumable embedding, LanceDB
indexing, exact retrieval (verified equivalent via two independent
implementations), Task 2.6 metric reuse, benchmark-specific recall
aggregation, independent recomputation, and determinism - produced a
result matching an external published reference to within 0.0002 nDCG@10.
No SEC TEST access occurred; no SEC ground truth was touched; no Phase 3
architecture was built.

## Command to reproduce

```bash
python scripts/run_msmarco_harness.py --dry-run
python scripts/run_msmarco_harness.py --pilot
python scripts/run_msmarco_harness.py --build       # ~3.3 hours, resumable
python scripts/run_msmarco_harness.py --evaluate    # ~5-10 minutes
python -m pytest tests/test_msmarco_harness.py -q
```
