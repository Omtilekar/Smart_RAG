# Phase 4 Task 4.5 — XBRL Serving Representation

Exports a serving-appropriate, partitioned-Parquet re-export of the
frozen `data/xbrl.duckdb` `facts`/`submissions` tables, validates
partition-pruning correctness, and honestly benchmarks real SQL-path
latency. Per `project_plan/PROJECT_EXECUTION.md`'s Task 4.5 wording:
"Keep xbrl.duckdb for offline analysis" — `data/xbrl.duckdb` itself is
untouched throughout; this task is a purely additive, read-only-of-source
physical I/O reorganization, never a semantic recomputation. No Phase
2/3 frozen decision (the truth contract, tag registry, eligibility
rules) is reopened or reimplemented a second time.

## Measured query pattern (verified from real code, not assumed)

`PROJECT_EXECUTION.md`'s generic Task 4.5 checklist says "Partition based
on measured query patterns such as CIK/year." Before building anything,
the actual production code was inspected: Task 3.10's
`src.sql.xbrl_lookup.XbrlFactIndex` calls
`eligible_facts(con, [tag])` **once per registry tag** (15 tags), each a
`WHERE f.tag IN (...)` full-table scan — `cik`/`fiscal_year` never appear
in a SQL `WHERE` clause anywhere in the current production path; every
`(cik, fiscal_year, tag)` lookup is served from an in-memory index built
once at startup. This is a **measured** discrepancy between the roadmap's
example wording and the real code, recorded rather than silently
resolved: both a `tag`-partitioned and a `(cik, fiscal_year)`-partitioned
export were built and honestly benchmarked against both query shapes,
rather than picking one to match the roadmap's example.

## Scope: 15 enabled tags, not all 291,429 raw tags

"Serving-appropriate" means scoped to what the one real consumer
(`XbrlFactIndex`) actually reads — the 15 `enabled: true` tags in the
frozen `configs/eval_tags.yaml` registry (Task 2.2), never a second,
independently-decided tag list. Exporting all 291,429 distinct raw XBRL
tags would bloat the serving artifact with data no production code path
ever queries. `data/xbrl.duckdb` remains available, unfiltered, for any
offline analysis that needs the other 291,414 tags.

```text
source facts rows (tag IN 15 enabled tags):  15,852,990  (17.5% of 90,685,753 total)
source submissions rows (full table, small, no tag column):  218,166
distinct (cik, fiscal_year) among these tags:  64,457
distinct cik:  10,757 (same universe as the full facts table)
```

## Three partitioned artifacts (same underlying facts rows, two layouts + submissions)

```text
facts_by_tag              - PARTITION_BY (tag)               15 partitions
facts_by_cik_fiscal_year  - PARTITION_BY (cik, fiscal_year)   64,457 partitions
submissions_by_cik        - PARTITION_BY (cik)                10,757 partitions (full submissions table)
```

No eligibility filtering, deduplication, or conflict-resolution logic
from `src.eval.truth_contract.eligible_facts()` is baked into these
exports — every column is preserved verbatim from the source tables. A
future consumer still calls `eligible_facts()`/`XbrlFactIndex` for actual
answer-grade lookups; these Parquet artifacts are a physical I/O layout
choice underneath that same semantic layer, not a replacement for it.

## Identity / config hash

```text
xbrl_serving_config_hash: b9c628766c0ac48ef2e6206128862856221443ee03c976ffe1655b2003b05c7a
```

Computed via `src.artifacts.versioning.semantic_hash()` (the one
canonical hashing primitive, never reimplemented) over a small config
capturing: schema version, source table names, the eval-tag-registry
identity (`eval_tag_registry_hash`, Task 2.2's `compute_registry_hash()`
— reused, not recomputed independently), the facts row-scope rule, and
the three partition schemes. Binding to `eval_tag_registry_hash` means
a future tag-registry change (a 16th tag enabled, a qtrs/unit correction)
automatically produces a new, non-colliding export directory rather than
silently reusing a stale one.

New `src.storage` accessor: `xbrl_serving_dir(xbrl_serving_config_hash,
artifact)` → `artifacts/xbrl_serving/<config_hash>/<artifact>/`.

## Two real out-of-memory failures and their fixes (empirical, not anticipated)

1. **First attempt** (all defaults): a single `COPY ... PARTITION_BY
   (cik, fiscal_year)` over all 64,457 partitions failed —
   `Out of Memory Error: ... 24.9 GiB/25.0 GiB used`. DuckDB's own error
   message names its two standard fixes for many-partition writes:
   `SET preserve_insertion_order=false` (row order was never a project
   contract for this artifact — same "do not rely on physical row order"
   precedent as Task 1.5's LanceDB table) and a capped `memory_limit`.
2. **Second attempt** (`preserve_insertion_order=false`, `memory_limit=
   '8GB'`, `threads=4`): still failed — `Out of Memory Error: failed to
   pin block of size 256.0 KiB (7.4 GiB/7.4 GiB used)`. A single COPY
   with 64,457 concurrent partition writers is inherently memory-hungry
   regardless of these settings on this machine.
3. **Real fix**: `export_facts_by_cik_fiscal_year_batched()` splits the
   export into 44 sequential batches of 250 CIKs each, every batch its
   own `COPY ... WHERE cik IN (...) PARTITION_BY (cik, fiscal_year)` call
   writing into disjoint partition subdirectories of the same output
   root (verified empirically on a disposable synthetic table first:
   multiple sequential `COPY ... PARTITION_BY` calls into the same
   directory for disjoint value ranges combine correctly at read time).
   A config/source-identity-bound `_export_state.json` checkpoint (same
   resumable pattern as Task 4.1/4.2/4.4's checkpoints) records completed
   batch indices, so an interrupted run resumes without re-exporting
   completed batches. `facts_by_tag` (only 15 partitions) and
   `submissions_by_cik` (10,757 single-column partitions, 218K small
   rows) never needed batching — verified to complete in the single-COPY
   path without error.

## Validation

**Full-corpus fingerprint parity** (not sampled): `SELECT count(*),
sum(hash((<all columns>))) FROM <source>` compared against the same
query over `read_parquet(<export>/**/*.parquet, hive_partitioning=true)`
for all three artifacts. All three exactly match the live source:

```text
facts_by_tag:              15,852,990 rows, fingerprint 146234926186231951097706587 - MATCH
facts_by_cik_fiscal_year:  15,852,990 rows, fingerprint 146234926186231951097706587 - MATCH (same rows, different layout)
submissions_by_cik:           218,166 rows, fingerprint   2009882103500140471382179 - MATCH
```

**Partition-pruning correctness** (5 deterministic tags + 5 deterministic
`(cik, fiscal_year)` pairs): each key's row set from the partitioned
Parquet exactly matches (via count+fingerprint) the equivalent
`WHERE`-filtered query against the live `facts` table. 10/10 keys match.

**Bug found and fixed during this validation, not silently absorbed**:
the first version of this check compared the `(cik, fiscal_year)`
partitioned export (scoped to the 15 enabled tags) against an
**unscoped** live query (`WHERE cik = ? AND fiscal_year = ?`, all
291,429 raw tags) — a real apples-to-oranges mismatch, since the live
side legitimately has more rows. Every one of the 5 sample keys
"failed" this way on the first run. Root-caused directly (confirmed the
export's own full-corpus fingerprint already matched the source
perfectly, so the export was correct — the comparison query was wrong),
fixed by adding the same `AND tag IN (<15 enabled tags>)` scope to the
live baseline query, and a regression test
(`test_partition_pruning_correctness_catches_unscoped_live_query_bug`)
added so this exact mistake can't silently reappear.

## Search-latency diagnostic (Phase 4.5 smoke — not a production benchmark)

5 measured queries per shape (deterministic sample keys), one dev
machine, one measurement session:

```text
BY-TAG QUERY (the actual measured Task 3.10 production pattern):
  live DuckDB (facts table, WHERE tag = ?, unindexed scan):        p50 503.7 ms
  facts_by_tag Parquet (matching layout):                          p50  11.2 ms   (~45x faster)
  facts_by_cik_fiscal_year Parquet (wrong layout for this query):  p50 22,255.2 ms (~44x SLOWER than live DuckDB)

BY-(CIK, FISCAL_YEAR) QUERY (PROJECT_EXECUTION.md's example pattern):
  live DuckDB (facts table, WHERE cik = ? AND fiscal_year = ?):     p50   105.1 ms
  facts_by_cik_fiscal_year Parquet (matching layout):               p50 9,163.3 ms  (~87x SLOWER than live DuckDB)
  facts_by_tag Parquet (wrong layout for this query):                p50   118.8 ms  (competitive with live DuckDB)
```

**Negative result, kept and reported rather than discarded** (same
project convention as Phase 3's RRF-hybrid/reranking negative results):
the `facts_by_cik_fiscal_year` layout is dramatically *slower* than the
unpartitioned live DuckDB table for its own designed query shape — on
this machine/filesystem, the cost of enumerating 64,457 partition
directories via `read_parquet('.../**/*.parquet', hive_partitioning=true)`
at query-plan time dominates and outweighs any pruning benefit. This was
not assumed or tuned away; it was measured and is reported honestly.
`facts_by_tag` (only 15 partitions) shows the opposite, unambiguous
result: a ~45x speedup for the query pattern the real production code
actually uses today.

**Practical recommendation for a future consumer** (not implemented by
this task — Task 4.5's scope is export/validate/benchmark, not rewiring
`XbrlFactIndex`): `facts_by_tag` is a clear, measured win and the
better-justified serving layout, since it matches Task 3.10's actual
per-tag index-build query. `facts_by_cik_fiscal_year` was still built and
kept (it may serve a genuinely different future access pattern — e.g. a
per-company lookup endpoint outside today's index-build path — and
`Bitmap`/coarser-grained partitioning, e.g. by `cik` alone with
`fiscal_year` as an in-file filter, might avoid the high-cardinality
directory-enumeration cost measured here), but is **not** recommended for
today's actual query pattern as configured.

## Build

```text
build runtime (real 64,457-partition batched export): 478.5s (~8 minutes,
                                             the first successful attempt
                                             after the batching fix)
idempotent rerun (all 3 artifacts already match source fingerprints): 63.9s
                                             (dominated by DuckDB startup +
                                             the fingerprint re-verification
                                             scan, not re-export)
sizes on disk:
  facts_by_tag:               431,480,842 bytes (~411.5 MiB)
  facts_by_cik_fiscal_year:   338,350,744 bytes (~322.7 MiB)
  submissions_by_cik:          25,223,624 bytes (~24.1 MiB)
```

## Regression gates

`data/xbrl.duckdb` re-verified unchanged throughout (opened read-only
for every query in this task; no write connection ever created). No
change to `src.eval.truth_contract`, `src.eval.tag_registry`, or
`src.sql.xbrl_lookup` — all three remain exactly as Phase 2/3 froze them.
No re-normalization, re-chunking, re-embedding, or vector-index change.
No GPU used. No paid API/LLM call. Protected TEST: unopened, 0/3
official runs used.

Full test suite (`scripts/dev.py test --portable`): all portable tests
pass (+12 new in `tests/test_phase_4_5_xbrl_serving_export.py`, tiny
synthetic in-memory DuckDB tables only). New `local_data`-marked test:
row-count parity against the real export (no full benchmark re-run —
that cost is only paid by the real script's own execution).

## Files created/modified

```text
src/storage.py                                     (additive: xbrl_serving_dir)
scripts/export_xbrl_serving.py                     (new)
tests/test_phase_4_5_xbrl_serving_export.py        (new)
configs/phase_4_5_xbrl_serving_export.json         (new, tracked)
results/phase_4_5_xbrl_serving_export_summary.json (new, tracked)
project_plan/PHASE4_XBRL_SERVING_REPRESENTATION.md (this file)
project_plan/REPOSITORY_STRUCTURE.md               (updated)
project_plan/STORAGE.md                            (updated)
Progress.md                                        (updated)
```

## Reproducing this build

```bash
python scripts/export_xbrl_serving.py
```

Opens `data/xbrl.duckdb` read-only, writes only
`artifacts/xbrl_serving/<config_hash>/<artifact>/` (git-ignored),
`results/phase_4_5_xbrl_serving_export_summary.json`, and
`configs/phase_4_5_xbrl_serving_export.json` (both tracked). Safe to
rerun — the two low-cardinality artifacts are reused via a full fingerprint
match; the batched `facts_by_cik_fiscal_year` export resumes from its own
checkpoint if interrupted.

## Known limitations

- `facts_by_cik_fiscal_year`'s measured slowness is specific to this
  machine's filesystem/DuckDB version and this glob-based
  `hive_partitioning=true` read pattern — a different read strategy (an
  explicit partition-file manifest instead of a glob, or a lower-
  cardinality partition key) might perform very differently, but that
  redesign is out of this task's scope.
- No cloud-storage benchmark (S3/equivalent) was performed — both
  partitioned layouts and the live DuckDB baseline were measured on local
  NVMe/SSD only, and remote-object-storage latency characteristics (much
  higher per-request/listing latency, where partition pruning that avoids
  requests matters more) could change which layout wins.
- `XbrlFactIndex`/`eligible_facts()` were not rewired to consume either
  Parquet export — that remains a future decision (Task 4.10's FastAPI
  service, or a later task), informed by but not decided by this task's
  benchmark.

## Next roadmap task

Phase 4, Task 4.6 — Generation production interface.
