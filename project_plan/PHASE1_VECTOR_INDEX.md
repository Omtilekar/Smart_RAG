# Phase 1 Vector-Only Index

**Phase 1 baseline vector-index contract.** Established in Task 1.5. This
is an integration-correctness baseline, not an indexing-strategy
experiment: a plain LanceDB table, exact/flat cosine search, no ANN index,
one self-contained table.

## Purpose

Task 1.4 produced 162,357 dense vectors. Task 1.5 makes them searchable —
the first queryable vector store in the pipeline — for Task 1.6's baseline
retriever.

## Frozen decisions (approved before this task began)

| Decision | Value |
|---|---|
| Index type | Plain LanceDB table, exact/flat vector search — no IVF_PQ, HNSW, or IVF_FLAT |
| Similarity metric | Cosine |
| Table contents | All 17 Task 1.4 columns retained (self-contained — no join back to `chunks.parquet` needed) |
| Table name | `chunks` |

## Task 1.4 input provenance

```text
embedding artifact:    artifacts/embeddings/f1dc04d4.../BAAI--bge-small-en-v1.5/embeddings.parquet
chunk_config_hash:       f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
embedding model:           BAAI/bge-small-en-v1.5, revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
row count:                   162,357 (independently verified: unique chunk_id
                             162,357, single chunk_config_hash value, vector
                             field fixed_size_list<float32>[384], all finite)
```

## Empirically verified LanceDB 0.37.1 behavior

Before touching real data, a tiny synthetic table (4 known vectors: an
exact copy of the query, a near-duplicate, an orthogonal vector, and an
opposite vector) was built and queried to verify the actual installed
API's behavior rather than assuming it from memory or another version's
docs:

```text
same-as-query   -> _distance = 0.0
near-duplicate    -> _distance ~= 0.006
orthogonal          -> _distance = 1.0
opposite              -> _distance = 2.0
```

This confirms, for LanceDB 0.37.1's cosine distance specifically:
**lower `_distance` means more similar**, range approximately `[0, 2]`
(`_distance = 1 - cosine_similarity`), and ranking behaved exactly as
expected (identical first, near second, orthogonal third, opposite last).

Also verified directly:

- `lancedb.connect(path)` treats `path` itself as the database root — no
  nested `db/`/`store/` subdirectory is created or required. `index_dir()`
  is used directly as the connection target.
- `create_table()` creates **zero** ANN indexes automatically
  (`table.list_indices() == []` immediately after creation) — exact/flat
  search is simply what `.search()` does until `.create_index()` is
  explicitly called, which this codebase never does.
- `.distance_type("cosine")` (the current API — `.metric()` is a
  deprecated alias) must be called **explicitly** per query. The untouched
  default is `"l2"`, confirming the task's warning not to rely on it.

## Backend

```text
LanceDB version:    0.37.1 (matches the pinned requirement exactly)
database path:        artifacts/indexes/f1dc04d4.../BAAI--bge-small-en-v1.5/
table name:             chunks
```

Built via `src.storage.get_storage().index_dir(chunk_config_hash,
embedding_model)` — the existing Task 0.7 storage contract (previously
reserved conceptually for this exact purpose, per `STORAGE.md`), not a new
path convention. No separate index-config identity hash was introduced:
the existing `(chunk_config_hash, embedding_model)` compound key is
sufficient, since every decision that affects the index's content (which
chunks, which model, exact/cosine search, all-17-columns) is either
already captured by that key or frozen project-wide (Decisions 1–4 above),
with nothing left that would require a distinct durable hash for Phase 1.

## Search contract

```text
search mode:      exact (no ANN index exists on the table)
metric:              cosine, requested explicitly via .distance_type("cosine")
distance field:        _distance (LanceDB's own column name — never renamed
                     to "score", since that would imply a semantic
                     conversion this task doesn't perform)
ranking direction:      lower _distance = more similar
```

`src/index/lancedb_index.py` exposes `exact_cosine_search(table,
query_vector, limit)` — accepts only a numeric 384-d vector (never a
natural-language question; Task 1.6 owns query encoding via
`src.embeddings.bge.encode_queries()` upstream of this function).
Malformed query vectors (wrong dimension, empty, NaN, +-Inf) are rejected
outright — never truncated or padded.

## Table schema

All 17 columns retained exactly as produced by Task 1.4:

```text
chunk_id, document_id, cik (int64), company, form_type, fiscal_year (int32),
source, source_filename, source_split, ordinal (int32), text,
token_count (int32), chunk_config_hash, normalizer_version,
normalization_build_sha256, development_manifest_sha256,
vector (fixed_size_list<float32>[384])
```

`_distance` is a query-result field, never a persisted table column.

## Build

```text
input rows:      162,357
table rows:         162,357
build runtime:        8.94s (first build; 6.72s on the idempotent-reuse
                     rerun, since ingestion is skipped when an existing
                     table with the correct row count is found)
database size:          493,178,075 bytes (~470.3 MiB)
ANN indexes created:       0
```

**Safe create/reuse policy**: if `index_dir(...)` already contains a
`chunks` table, its row count is checked against the expected 162,357
before reuse; a mismatch raises rather than silently overwriting. An
unexpected additional table also raises. Verified directly: running the
build a second time detected the existing table, reused it without
re-ingesting, and produced identical validation results.

## Validation

```text
row-count match:               162,357 indexed == 162,357 source
chunk-ID uniqueness:             162,357 unique chunk_id, no duplicates
metadata equality:                 full corpus, not sampled — every one of
                                 the 16 non-vector columns compared,
                                 chunk_id-keyed (not physical row order),
                                 between the indexed table and
                                 embeddings.parquet: exact match
vector dimension/dtype:              384, float32 - verified via native
                                 PyArrow -> NumPy conversion
finite vectors:                        verified
stored-vs-source vector comparison:      200-row deterministic sample
                                 (evenly spaced across the corpus):
                                 200/200 exact bit-for-bit matches,
                                 max abs diff 0.0 - LanceDB preserves the
                                 float32 representation exactly, no
                                 quantization or precision loss
```

Physical row order inside LanceDB is **not** assumed to match insertion
order — every comparison above is keyed by `chunk_id`, never by row
position, per the task's explicit "do not rely on physical row order"
requirement.

## Self-retrieval (real corpus)

40 deterministic chunks (evenly spaced across the full 162,357-row corpus,
spanning many documents/years) were each queried using their own stored
vector:

```text
checked:                  40
passed (self at rank 1):    40 / 40
anomalies:                     none
self-distance range:             min -1.19e-07, max 0.0
```

The tiny negative value (`-1.19e-07`) is a floating-point rounding
artifact of computing `1 - cosine_similarity` on a self-comparison — not a
bug, and far below any meaningful tolerance (mathematically, self-distance
is exactly 0; IEEE 754 float32 arithmetic can round a hair below zero).
This is mapping/integrity validation, not a retrieval-quality claim.

## Search diagnostic (Phase 1 smoke — not a production benchmark)

```text
label:          Phase 1 smoke diagnostic - not a production benchmark
query count:       50 (after 5 unmeasured warm-up queries)
top-k:                5 (reused from PROJECT_EXECUTION.md's already-frozen
                    "top-5 context for generation" Phase 1 baseline
                    constant — not a new contract invented for this
                    diagnostic)
p50:                   ~143-154 ms (two build runs)
p95:                     ~153-165 ms (two build runs)
```

This is a brute-force exact scan over 162,357 384-dimensional vectors —
slower than an ANN index by design, and explicitly not compared against
Task 0.10's IVF_PQ serving-spike numbers, which measure a different,
non-binding, throwaway configuration.

## Known limitations

- Exact scan only — no ANN optimization. Query latency (~150 ms smoke
  p50/p95) will not scale to the full ~14M-chunk production corpus without
  an indexing strategy decision, which belongs to Phase 3/4, not here.
- No BM25/FTS, no hybrid retrieval — vector-only, per this task's explicit
  scope.
- No reranking.
- No retrieval-quality evaluation of any kind — self-retrieval here proves
  the vector-to-chunk_id mapping is mechanically correct, not that
  retrieval is *good*. That begins in Task 1.6+ and is only trustworthy
  starting Phase 2.

## Next consumer

Task 1.6 (Baseline Retriever) encodes a natural-language question via
`src.embeddings.bge.encode_queries()`, then calls
`exact_cosine_search(table, query_vector, limit=5)` against this table.

## Reproducing this build

```bash
python scripts/build_vector_index.py
```

Reads `artifacts/embeddings/f1dc04d4.../BAAI--bge-small-en-v1.5/embeddings.parquet`
read-only, performs no network access, loads no embedding model, writes
only `artifacts/indexes/<chunk_config_hash>/<embedding_model>/` (git-ignored
LanceDB dataset), `results/phase_1_5_vector_index_summary.json`, and
`configs/build_vector_index.json` (both tracked). Safe to rerun — detects
and reuses an existing table with the correct row count rather than
re-ingesting or silently overwriting.
