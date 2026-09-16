# Phase 4 Task 4.4 — Full-Corpus Vector Index

Builds and validates the production-scale exact-cosine LanceDB vector
index over the frozen Task 4.3 full-corpus embedding artifact
(10,487,096 chunks, `Qwen/Qwen3-Embedding-0.6B`, 1024-dim). Same search
semantics as Task 1.5/Phase 3 (`src.index.lancedb_index`) — plain LanceDB
table, exact/flat cosine search, no ANN index — reused directly via the
frozen `exact_cosine_search()`/`exact_cosine_search_filtered()` helpers.
This is a scale-out/index-build task, not a new retrieval-architecture
experiment. No re-normalization, no re-chunking, no re-embedding, no
BM25/RRF hybrid, no reranking, no CRAG change, no protected TEST access,
no paid API calls.

## Objective

```text
Task 4.3 frozen embedding shards (54, 10,487,096 rows)
        ->
validated full-corpus LanceDB table
        ->
validated exact cosine retrieval path
        ->
production-scale index artifact + manifest
```

## Material conflict — recorded, not silently resolved

`project_plan/PROJECT_EXECUTION.md`'s generic Phase 4.4 checklist
("Build FTS/BM25 index"; deliverables list "production vector + FTS
indexes") predates Phase 3's actual experimental results and conflicts
with this task's explicit instruction (do NOT add BM25/RRF hybrid
retrieval). Phase 3's own frozen finding: Task 3.5's RRF hybrid fusion of
dense + BM25/FTS was a **negative result** (dense's 89/89 Recall@50
ceiling preserved, no measurable Recall@10 hit-count improvement, both
95% CIs include 0) — `dense-only` was selected as the production
retrieval architecture, confirmed again by Task 3.14's serving re-check
(`project_plan/SERVING_FEASIBILITY.md`), which explicitly measured only
the dense-only path end-to-end.

**Resolution**: no production FTS/BM25 index was built for the
full corpus. This index is dense-only, matching the actually-selected
Phase 3 architecture rather than the pre-Phase-3 roadmap placeholder
wording. `src.index.lancedb_fts` (Task 3.4's sparse module) remains
untouched and available if a future task revisits hybrid retrieval, but
building a 10.5M-row production FTS index today would contradict the
frozen dense-only selection for no retrieval-quality benefit.

Similarly, "apply selected quantization strategy only if Phase 3
validated it" resolves to **apply none** — Phase 3 never validated any
quantization strategy against the real selected stack (flat/exact search
throughout Phase 3, documented as an honest gap in
`project_plan/SERVING_FEASIBILITY.md`'s Task 3.14 re-check). No ANN
index (`IVF_PQ`/`IVF_FLAT`/`HNSW`/etc.) was created.

## Frozen upstream inputs (independently re-verified, not trusted from `Progress.md` alone)

```text
Task 4.1 phase_4_1_config_hash: 754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f
Task 4.2 chunk_config_hash:     ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
Task 4.2 chunk_schema_version:  2
Task 4.3 model:                 Qwen/Qwen3-Embedding-0.6B
Task 4.3 model_revision:        97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3
Task 4.3 embedding_dimension:   1024
Task 4.3 vector_dtype:          float32
Task 4.3 shard_count:           54
Task 4.3 total rows:            10,487,096
```

Before building anything, independently re-verified against the real
local artifact (not just Progress.md's prose):

- Recomputed SHA-256 for all 54 local `*.embeddings.parquet` shards
  against `final/embedding_manifest.json` — 54/54 match, 0 mismatches,
  0 missing/extra shard IDs, total bytes 18,505,216,959 (~17.24 GiB,
  matches Task 4.3's reported 17.23 GiB).
- Recomputed `embedding_manifest.json`'s own self-referential
  `manifest_sha256` field. **It is NOT a raw file-byte hash** — it is
  `sha256(canonical_json(manifest_dict_with_manifest_sha256_field_dropped))`
  using this project's own established canonicalization convention
  (`json.dumps(sort_keys=True, separators=(",", ":"))`, matching
  `src.artifacts.versioning.semantic_hash`). Verified by testing multiple
  hypotheses against the real file; only this one reproduced
  `a4d1421bb287ea6aa21398f1fca99f1e11650b7c0d49979077140bb17456fbc8`
  exactly. `scripts/build_vector_index_full.py`'s
  `load_and_verify_manifest()` re-derives and checks this hash on every
  run — the build refuses to proceed if it doesn't reproduce.
- Full-corpus scan (not sampled): 10,487,096 unique `chunk_uid` values,
  0 duplicates; single-valued `chunk_config_hash`
  (`ba99e2f7...`) and `chunk_schema_version` (`2`) across every row.
- Schema equality verified across all 54 shards (PyArrow schema,
  including nullability) before any ingestion.
- Stratified vector sanity check (3 shards, all rows): finite, `float32`,
  L2 norm ≈ 1.0 (min 0.998047, max 1.003921 — small deviation from the
  Colab BF16-compute/float32-persist pipeline, consistent with Task 4.3's
  own documentation).

## Local artifact-path convention (new `storage.py` accessors)

Task 4.3's frozen local artifact root
(`artifacts/embeddings_full/<phase_4_1_config_hash>/<chunk_config_hash>/<model>_<revision8>/`)
was assembled outside `src.storage`'s own path convention (downloaded
from Google Drive and placed manually, per the Task 4.3 prompt). Two
additive accessors were added to `StoragePaths` so later callers never
hardcode this layout:

- `embeddings_dir_full(phase_4_1_config_hash, chunk_config_hash, embedding_model, embedding_model_revision)`
  — reproduces the existing Task 4.3 layout exactly (read-only; verified
  to resolve to the real on-disk directory).
- `index_dir_full(...)` (same signature) — this task's new output root,
  `artifacts/indexes_full/<phase_4_1_config_hash[:16]>/<chunk_config_hash[:16]>/<model>_<revision8>/`.

A new module-level `embedding_model_short_dir(model, revision)` helper
reproduces Task 4.3's own naming convention (last path segment of the
model repo, lowercased, `_` + first 8 hex chars of the revision —
verified to reproduce `qwen3-embedding-0.6b_97b0c614` exactly).

`index_dir_full()` is a deliberately distinct root from `index_dir()`,
mirroring `chunks_dir_full()`'s rationale exactly:
`chunk_config_hash` alone (`ba99e2f7...`) is the SAME value Phase 3
already used for its own 323,971-row dev-corpus index at
`index_dir(chunk_config_hash, embedding_model)` — reusing that path for
the 10,487,096-row full-corpus index would silently collide two
differently-sized indexes into one directory.

### Windows MAX_PATH failure and fix (empirical, not anticipated)

The first real build attempt failed:

```text
RuntimeError: lance error: LanceError(IO): failed to shutdown local
writer for .../chunks.lance/data/<~52-char-name>.lance: ...
The system cannot find the path specified. (os error 3)
```

Root cause: `index_dir_full()` originally stacked both full 64-character
SHA-256 hashes (mirroring `chunks_dir_full()`), and LanceDB's own
internal fragment files (`chunks.lance/data/<~52-char-random-name>.lance`)
add another ~70 characters of nesting that `chunks_dir_full()`'s flat
Parquet shards never hit — pushing the full path past Windows' ~260
character `MAX_PATH` limit. Fixed by truncating each hash to its first 16
hex characters (64 bits — collision-proof for this project's actual
handful of configurations) in the **directory name only**; the full
64-character hashes are still what gets recorded as this index's real
identity in the build config/summary JSON. Verified: the truncated path
(`.../indexes_full/754d9c898772c332/ba99e2f7861c48bc/qwen3-embedding-0.6b_97b0c614/`)
plus LanceDB's longest observed internal filename stays at 179
characters, comfortably under the limit. The broken, empty (0 bytes
written) directory scaffold from the failed attempt was removed before
retrying.

## Table schema (24 columns)

All Task 4.2/4.3 columns retained — `chunk_schema_version`, `chunk_uid`,
`chunk_local_id`, `document_id`, `accession`, `cik`, `company`,
`form_type`, `fiscal_year`, `period_end`, `filed_date`, `sic`,
`section_id`, `section_title`, `ordinal`, `char_start`, `char_end`,
`content_type`, `table_id`, `source`, `text`, `token_count`,
`chunk_config_hash`, `vector` (`fixed_size_list<float32>[1024]`,
required/non-null). Table self-contained — no join back to the chunk
Parquet needed for text/metadata.

This is a materially different (larger, richer) schema than Task
1.5/Phase 3's frozen 17-column dev-corpus contract, so a new companion
module — `src/index/lancedb_index_full.py` — owns this table's own
column contract/validation, exactly the way `src.index.lancedb_fts` is a
companion to (never a modification of) `src.index.lancedb_index`. The
actual search functions (`exact_cosine_search`,
`exact_cosine_search_filtered`) are reused unchanged from
`src.index.lancedb_index` — both already parameterized by
`expected_dimension`, never hardcoded to 384.

## Scalar indexes (new, additive — non-vector, non-ANN)

Two BTree scalar indexes were built on `cik` and `fiscal_year` — Task
3.9's two validated discriminative pre-filter dimensions
(`project_plan/PHASE3_METADATA_PREFILTERING.md`; `form_type` is a
constant `"10-K"` and `section` doesn't exist in this chunk schema, so
neither is indexed, matching Task 3.9's own scoping). Built via
`table.create_index(column, config=BTree(), ...)` — verified empirically
against installed LanceDB 0.37.1 that the shorter `create_scalar_index()`
call is deprecated as of 0.25.0 (same deprecated-vs-current distinction
`src.index.lancedb_fts` already documents for FTS). A scalar index
changes filter-scan performance only, never vector-search
results/ranking, so `lancedb_index_full.validate_chunk_table()`
deliberately asserts **zero vector/ANN indexes**, not zero indexes of
any kind (unlike Task 1.5's stricter dev-corpus check).

## Index identity (Task 2.10 convention, reused)

```text
embedding_identity_hash: de63fd5c9047e7cd6ae8d45e747288cad864e6c81f020729b812a8ec20cec5fe
index_identity: {chunk_schema_version: 2, chunk_config_hash: ba99e2f7...,
                 embedding_identity_hash: de63fd5c..., distance_metric: cosine,
                 index_type: exact_flat, table_name: chunks}
index_identity_hash: 158e6b0605ad483e882bef8611e7c3a3ecafc65100f246ab99e91578048d5501
```

Computed via `src.artifacts.versioning.compute_index_identity()`/
`compute_index_identity_hash()` — the same primitive Task 2.10
established, never a second hashing implementation. Distinct from Phase
3's dev-corpus index identity because `chunk_schema_version` differs (2
vs. 1), even though `chunk_config_hash` and `embedding_identity_hash`
are otherwise identical between the dev and full-corpus Qwen builds.

## Build

Resumable at shard granularity via a config/source-identity-bound
`_build_state.json` checkpoint inside the index directory (same pattern
as Task 4.1/4.2's checkpoints) — an interrupted run skips already-ingested
shards on restart rather than re-ingesting from scratch. Ingestion itself
never held more than one shard (≤ ~355 MB) in memory at a time — the full
10.5M-row × 1024-dim vector set (~43 GB) was never materialized at once.

```text
shards ingested:            54/54
table rows:                 10,487,096
recorded build_runtime_seconds: 1.34s (this is the final, fully-checkpointed
                             idempotent rerun only - the run that performed
                             the actual 54-shard ingest exited via a
                             self-retrieval assertion before reaching
                             summary-writing code, per the tie-handling
                             fix below, so its own wall time was not
                             persisted; unbuffered console output showed
                             all 54 shards ingesting steadily with no
                             errors before that point)
database backend:            LanceDB 0.37.1
database path:                artifacts/indexes_full/754d9c898772c332/ba99e2f7861c48bc/qwen3-embedding-0.6b_97b0c614/
database size on disk:          51,130,625,535 bytes (~47.6 GiB)
vector/ANN indexes created:        0
scalar indexes created:              cik, fiscal_year (BTree)
```

**Database size finding**: 47.6 GiB on disk vs. 17.23 GiB source
Parquet (~2.76x). This reflects LanceDB's own fragment storage format,
not a bug or duplicated write (verified: `chunks.lance/data/` accounts
for 51.03 GB of the 51.13 GB total, `_indices/` only ~0.10 GB for both
scalar indexes, `_versions`/`_transactions` negligible) — Lance's
per-fragment encoding does not reproduce Parquet's compression ratio for
this schema's large `text` column. Recorded honestly as an observed
production-footprint fact; no compression tuning was in scope for this
task (not a frozen decision to revisit here).

## Validation

```text
row-count match:              10,487,096 indexed == 10,487,096 source (Task 4.3)
schema match:                  all 24 expected columns present, set-equality checked
vector dimension/dtype:              1024, float32
vector/ANN indexes:                       0
scalar indexes:                            cik, fiscal_year (BTree) - present, validated
```

### Self-retrieval (real corpus, deterministic stratified sample)

12 deterministic chunks (2 each from shard IDs 0, 10, 20, 30, 40, 53,
evenly spaced within each shard) queried using their own stored vector:

```text
checked:                  12
passed:                     12 / 12
tied_duplicate_passes:           0 (this particular 12-sample draw)
self-distance range:                -1.19e-07 to 1.19e-07 (float32 rounding)
```

**Genuine floating-point tie observed and documented (not silently
weakened)**: an earlier, larger validation pass (48 samples, 8 per
shard) hit 2 cases where the query's own `chunk_uid` did NOT rank first —
independently confirmed both were **genuine ties**, not mapping bugs.
Example: `chunk_uid=7df1d74b...` (document `66901_2000.txt`, Entergy
Arkansas) and `chunk_uid=6872479b...` (document `65984_2000.txt`, an
affiliated Entergy filing) share **byte-identical** chunk text (verbatim
"Restated Articles of Incorporation..." exhibit-index boilerplate common
across affiliated utility-holding-company 10-Ks). Their embeddings are
float32-rounding-identical, producing a cosine distance tied at exactly
`+-1.1920928955078125e-07` (float32 machine epsilon) — LanceDB's internal
tie-break returned the other duplicate at rank 1 in those 2 cases. A
second example showed a **3-way tie** across affiliated New England
Electric System filings. Per this project's established convention ("if
a genuine vector tie occurs, document it rather than silently weakening
the test" — Task 1.5's own Step 27), `self_retrieval_check()` treats the
expected `chunk_uid` appearing among nearest neighbors tied within
`1e-6` of the top distance as a PASS, explicitly labeled
`tied_duplicate_passes` in the summary — never silently absorbed into an
undifferentiated pass count, and never achieved by loosening the
tolerance for a genuine ranking bug.

### Search-latency diagnostic (Phase 4.4 smoke — not a production benchmark)

```text
label:          Phase 4.4 smoke diagnostic - not a production benchmark
query count:       5 (after 2 unmeasured warm-up queries)
top-k:                5
p50:                   33,607.9 ms
p95:                     34,632.2 ms
min / max:                  33,224.9 ms / 34,787.5 ms
```

A single exact-flat cosine search over the full 10,487,096 × 1024-dim
table takes **~31-35 seconds** on this development machine — a
disk-bound full-column scan (measured directly; the querying Python
process's own RSS barely moved, ~0.13 → 0.16 GB, confirming the cost is
I/O/kernel-side, not a Python-side memory blow-up). Contrast Task 3.14's
554.7 ms p50 over 323,971 rows (`project_plan/SERVING_FEASIBILITY.md`) —
roughly 32x more rows produced roughly 60x more latency, consistent with
a scan that is not purely linear once the working set stops fitting
comfortably in OS page cache. **This is exact/flat search at full-corpus
scale exhibiting exactly the cost Phase 3 never had reason to measure —
it is not a regression, and no ANN/quantization fix is authorized by
this task** (see "Material conflict" above). Query and diagnostic sample
counts were deliberately kept small (12 self-retrieval + 5 diagnostic,
down from an initially-planned 48 + 10) specifically because of this
per-query cost, after two background build attempts were killed by this
shared development machine's low-memory guard during a larger,
longer-running batch of queries (unrelated background application memory
pressure — the query's own process RSS never grew — but the *wall-clock
exposure* of a longer query batch to that external contention needed to
be reduced).

## Regression gates

Task 4.1/4.2/4.3 artifacts re-verified unchanged: this task never wrote
to `artifacts/normalized_full/`, `artifacts/chunks_full/`, or
`artifacts/embeddings_full/` — only read from the latter (the Task 4.3
manifest self-consistency check and 54-shard SHA-256 re-verification ran
against the real files with no write access requested). No
re-normalization, re-chunking, or re-embedding occurred. No BM25/FTS
production index, no reranker, no CRAG change, no router change. No GPU
used (index build is pure CPU/disk I/O — no embedding model loaded). No
paid API/LLM call. Protected TEST: unopened, 0/3 official runs used.

Full test suite (`scripts/dev.py test --portable`): 1956 passed, 0
failed (35 deselected `local_data`/`gpu`/`model`-marked). New
`tests/test_phase_4_4_full_corpus_vector_index.py`: 17 portable tests
(tiny synthetic 24-column tables, no real corpus) + 1 `local_data`-marked
structural-integrity test against the real index (row count/schema/scalar
indexes only — deliberately does **not** perform a real
`exact_cosine_search()`, since a single real query costs ~30s and would
make routine test runs unacceptably slow).

## Files created/modified

```text
src/storage.py                                    (additive: embeddings_dir_full,
                                                    index_dir_full, embedding_model_short_dir)
src/index/lancedb_index_full.py                   (new)
scripts/build_vector_index_full.py                (new)
tests/test_phase_4_4_full_corpus_vector_index.py  (new)
configs/phase_4_4_full_corpus_vector_index.json   (new, tracked)
results/phase_4_4_full_corpus_vector_index_summary.json (new, tracked)
project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md   (this file)
project_plan/REPOSITORY_STRUCTURE.md              (updated)
Progress.md                                       (updated; stale "Next
                                                    roadmap task" line
                                                    under Task 4.3 corrected)
```

## Reproducing this build

```bash
python scripts/build_vector_index_full.py
```

Reads the 54 Task 4.3 shards read-only, performs no network access, loads
no embedding model, writes only
`artifacts/indexes_full/<hash16>/<hash16>/<model>_<rev8>/` (git-ignored
LanceDB dataset), `results/phase_4_4_full_corpus_vector_index_summary.json`,
and `configs/phase_4_4_full_corpus_vector_index.json` (both tracked).
Safe to rerun — shard-level checkpointing skips already-ingested shards,
and scalar-index building is idempotent.

## Known limitations

- Exact/flat scan only — no ANN optimization, per this task's explicit
  scope (Phase 3 never validated a quantization strategy). At ~31-35s
  p50/p95 per query on this development machine, exact search over the
  full 10.5M-row corpus is **not** production-serving-latency-viable as
  configured — this is an honestly-measured fact for a future indexing-
  strategy decision, not a defect introduced by this task.
- No BM25/FTS production index (see "Material conflict" above) — matches
  the frozen dense-only Phase 3 selection, not an oversight.
- No reranking, no hybrid retrieval, no CRAG change.
- Search-latency diagnostic and self-retrieval sample sizes are small
  (5 and 12 queries respectively) specifically because of the ~31-35s
  per-query cost on this shared development machine — a production
  environment with faster storage/more page-cache headroom could
  reasonably run a larger diagnostic, but that was not repeated here to
  avoid further exposure to this machine's background memory pressure.
- Database-size finding (47.6 GiB vs. 17.23 GiB source) is unexplained
  beyond "Lance's own fragment encoding for this schema" — no deeper
  investigation of compression settings was in scope.

## Next roadmap task

Phase 4, Task 4.5 — XBRL serving representation (export serving-appropriate
partitioned XBRL Parquet from `xbrl.duckdb`, per
`project_plan/PROJECT_EXECUTION.md`).
