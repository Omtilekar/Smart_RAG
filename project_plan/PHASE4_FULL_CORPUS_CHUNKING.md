# Phase 4 Task 4.2 — Full-Corpus Chunking

Scales the frozen Task 3.2 winner (`fixed`/256-token window/0 overlap,
`chunk_config_hash=ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`)
from the 1,493-document Phase 3 development corpus to the complete Task 4.1
full-corpus normalization output (91,086 documents). Reuses
`src/chunk/fixed_window.py`'s tokenizer/window/offset logic and
`src/chunk/metadata_schema.py`'s canonical Task 2.9 schema/identity
unmodified — this is a scale-out task, not a new chunking experiment. No
GPU, no embedding, no index, no LLM call.

## Objective

Apply the already-selected chunking strategy to the complete Task 4.1
corpus and produce a deterministic, versioned, resumable, sharded Parquet
chunk corpus for Task 4.3.

## Stage 1-2 — Preflight and binding to Task 4.1

Verified directly before any build code ran:

```text
Task 4.1 status:                COMPLETE
Task 4.1 manifest entries:      91,086 (recomputed hash matches exactly)
Task 4.1 phase_4_1_config_hash: 754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f
Task 4.1 build_manifest_sha256: 3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9
NORMALIZED / VALID_EMPTY_SOURCE / failed: 90,239 / 847 / 0
```

The Task 4.1 build manifest (`manifest.jsonl`) is the authoritative document
inventory — the driver never globs the artifact directory and assumes every
file present belongs to the current build. Every document's content is
re-hashed against the manifest's `content_sha256` at the moment it is read
for chunking (a single read serves both integrity verification and
tokenization — no separate full-corpus pre-pass hash sweep).

`scripts/dev.py doctor`/`test --portable` passed before and after. Free
disk was ample (171+ GB) for the projected output.

## Stage 3 — Reproducing the frozen Task 3.2 winner exactly

```text
recomputed chunk_config_hash: ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
frozen chunk_config_hash:     ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06
match: TRUE
```

Recomputed via `src.artifacts.versioning.semantic_hash()` directly from the
checked-in `configs/phase_3_2_chunk_A1.json` — the exact winner config,
loaded verbatim, never rebuilt from Task 4.1 identities. **The frozen
config dict itself still carries Task 1.2's dev-corpus provenance fields
(`input_normalization_build_sha256`, `development_manifest_sha256`) as part
of its own hashed semantics** — this is expected and correct: those fields
identify *which chunking recipe* Task 3.2 selected, not *which corpus* Task
4.2 applies it to. Corpus/build provenance is a completely separate
identity (`phase_4_2_build_config_hash`, below) — exactly the "separate
semantic identity from build identity" split this task's own prompt
specifies.

Tokenizer offline availability confirmed directly (`try_to_load_from_cache`
for `tokenizer.json`/`tokenizer_config.json`/`vocab.txt`/
`special_tokens_map.json`, all present at revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`) — no network access ever
attempted (`HF_HUB_OFFLINE=1` set before import).

**Regression** (`local_data`+`model`-marked test
`test_regression_reproduces_frozen_dev_chunk_boundaries_and_text`): document
`1005817_2016.htm`, present in both the frozen Task 3.2 A1 dev chunk
artifact and Task 4.1's full-corpus output, re-chunked through the real
production tokenizer/window/offset path reproduces **identical** chunk
text, token counts, and ordinals against the frozen dev artifact's rows —
PASSED.

## Schema v2 — `company` becomes nullable

Task 4.1's approved policy leaves `company` `NULL` for 65.91% of the full
corpus (no XBRL CIK→name match). Task 2.9's frozen schema had `company` as
non-nullable — satisfiable only because Task 1.1's dev corpus was
pre-filtered to the XBRL-aligned population. Per
`project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`'s own schema-evolution
policy (a nullability change requires a version bump),
`CHUNK_SCHEMA_VERSION` incremented **1 → 2**. No other field changed.
Historical v1 data (the frozen 162,357-row Task 1.2/2.9 dev-corpus audit,
every Phase 3 ablation-table chunk) is unaffected — those call sites pin
`chunk_schema_version=1` as their own literal
(`scripts/run_phase3_trusted_baseline.py`'s `CHUNK_SCHEMA_VERSION = 1`,
`scripts/audit_chunk_metadata_schema.py`'s new
`HISTORICAL_CHUNK_SCHEMA_VERSION = 1`), never this module's "current"
default. See `project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`'s "Schema v2"
section for the full rationale.

## Offset and section metadata policy

`char_start`/`char_end` are populated for every non-empty chunk, half-open
`[start, end)`, and the round-trip invariant
(`normalized_body[char_start:char_end] == chunk_text`) is checked **for
every single chunk at build time** (`chunk_one_document()`), not just a
sample — a mismatch raises immediately and the document is recorded
`FAILED` rather than silently accepted.

`split_mode=fixed` (non-section-aware, the frozen Task 3.2 winner) means a
chunk may freely cross an Item-heading boundary. No unambiguous
single-section mapping exists for such a chunk, so **`section_id` and
`section_title` are always `NULL`** for every production row — documented
honestly here rather than adding a new section-aware splitter (explicitly
out of scope for this task).

`accession`/`period_end`/`filed_date`/`sic` remain `NULL` (unchanged from
Task 2.9's frozen `edgar_corpus` policy). `content_type` is always
`"prose"`, `table_id` always `NULL` (EDGAR-CORPUS never had tables).

## Separating semantic identity from build identity

```text
chunk_config_hash (semantic, frozen, unchanged):
  ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06

phase_4_2_build_config_hash (new, this task):
  9253de8418deef249ef412e3e3b155e4551c6d35b117aac4cdf67b0e292994e9
```

The build-identity config (`configs/phase_4_2_full_corpus_chunking.json`)
binds: task, `input_phase_4_1_config_hash`,
`input_phase_4_1_build_manifest_sha256`, `normalizer_version`,
`chunk_schema_version` (2), the selected `chunk_config_hash`, tokenizer
repository/revision, output format, shard policy (target 200,000 rows/
shard, boundary between documents only), Parquet compression (`zstd` — no
prior production convention existed; the dev pipeline relied on PyArrow's
implicit `snappy` default, so `zstd` was chosen explicitly and recorded,
per this task's own "choose and record a normal deterministic default"
instruction), and manifest schema version. Hashed via
`semantic_hash()` — the one canonical implementation, no second hashing
convention.

## Output namespace — cannot collide with dev/Phase 3 artifacts

New, additive `src/storage.py` method:

```python
storage.chunks_dir_full(phase_4_1_config_hash, chunk_config_hash)
  -> artifacts/chunks_full/<phase_4_1_config_hash>/<chunk_config_hash>/
```

Keyed by **both** identities, at a different root (`chunks_full/`, not
`chunks/`) from the existing `chunks_dir(chunk_config_hash)` — which, for
this exact same `chunk_config_hash`, already holds the 1,493-document
Phase 3 A1 dev artifact
(`artifacts/chunks/ba99e2f786.../chunks.parquet`). Verified directly: the
two paths differ, the dev artifact was never opened for writing, and its
content hash is unchanged after the full-corpus build completed.

## Resumable sharded build

`scripts/chunk_full_corpus.py`. Design:

- **Checkpoint** (`build_state.jsonl`, append-only NDJSON): a header record
  binds `phase_4_1_config_hash` + `phase_4_1_build_manifest_sha256` +
  `phase_4_2_build_config_hash` + `chunk_schema_version` +
  `chunk_config_hash` — resuming under any different identity is refused
  (`SystemExit`).
- **Shard atomicity as the single source of document completion**: a
  shard's chunk rows are buffered in memory (bounded — never the whole
  corpus, never more than ~200,000 rows at once), written to a temp
  Parquet file, hashed, atomically `os.replace`d into place, and **only
  then** is one checkpoint line appended containing the shard's identity
  *and* the full list of `{document_id, chunk_count}` it contains. This
  makes "which documents are done and which shard they're in" a single
  atomic write per shard — there is no window where a shard file exists
  but only some of its documents are marked complete (a real correctness
  gap in a naive per-document-checkpoint-line design, avoided here).
- **Resume verification**: every checkpoint shard record is re-hashed
  against the real on-disk file before being trusted; a missing or
  corrupted shard invalidates every document it claims to contain — those
  documents are silently re-queued (not silently accepted), into a
  brand-new shard index (shard indices are monotonic, an invalidated
  shard's index is never reused, so no filename collision risk).
- `VALID_EMPTY_SOURCE` and `FAILED` documents get an immediate, single-line
  checkpoint record (no shard dependency, since they contribute zero rows).
  `FAILED` is never treated as complete — always retried on the next run.
- Source text is read one small file at a time (never the whole corpus in
  RAM); the in-progress shard buffer is the only large-ish in-memory
  structure, bounded by the shard target.
- Progress printed every 2,000 documents: count/percent, chunks this run,
  docs/sec, elapsed, ETA, failure count.

**Simulated interruption test** (`test_simulated_interruption_resume_no_duplicate_chunks`,
portable, synthetic fixtures): a `run()` call limited to 3/6 documents,
followed by a resuming `run()` call for the rest, produces the same total
chunk count as an uninterrupted from-scratch run, with zero duplicate
`chunk_uid` across all published shards — verified directly before trusting
this on the real corpus.

## Stage 6 — Pilot

Deterministic stratified sample (17 documents): one per (source split ×
year band [1993–99, 2000–09, 2010–19, 2020]) with a `NORMALIZED` outcome,
the 5 lexicographically-first `VALID_EMPTY_SOURCE` documents, plus the
largest and smallest `NORMALIZED` documents by on-disk byte size (a `stat()`
sample across the corpus, never a full read). Ran cleanly: 12 non-empty
documents → 3,299 chunks, 0 failures, all Stage 6 correctness checks
passed (windows ≤ 256 tokens, zero overlap, partial final window kept,
0-based contiguous ordinals, deterministic `chunk_local_id`/`chunk_uid`,
exact offset round-trip, Task 2.9 schema conformance, empty source → 0
chunks). `--verify-sample` re-rendered the same sample in memory and
diffed against the manifest: 0 mismatches.

## Stage 7 — Full build

Completed across three invocations:

1. A 3,000-document throughput benchmark: 218.5 s, 13.83 docs/s.
2. A long background run, interrupted by a **system-wide low-memory kill**
   (32 GB total RAM; the harness's low-memory watchdog killed the
   longest-running background process, the same class of environmental
   interruption `project_plan/PHASE3_CHUNKING_ABLATION.md` documented for
   an earlier task — not a defect in this driver). Checkpoint verified
   fully intact afterward: 0 corrupted shards, 66,440/91,086 documents
   already durably complete.
3. The resumed completion run for the remaining 24,646 documents: 1,550.0 s,
   **15.90 docs/s**, peak RSS 2,318,495,744 bytes, 0 failures. This is the
   trustworthy measured throughput figure.

```text
[CHUNK] documents:  91,086 / 91,086 (100.00%)   chunks_this_run=2,726,613   docs/s=15.91   elapsed=1548.7s   failures=0
```

## Stage 8 — Full-corpus validation (every row, not a sample)

Streamed all 54 shards exactly once (never all 10.49M rows in one table):

```text
source documents:                 91,086
documents accounted for:          91,086
expected valid-empty documents:      847
valid-empty documents found:         847
unexpected zero-chunk documents:       0
failed documents:                      0

duplicate chunk_uid:                   0
total unique chunk_uids:      10,487,096
missing from manifest:                 0
extra document ids:                    0

wrong chunk_config_hash rows:          0
wrong schema_version rows:             0
wrong source rows:                     0
token_count > 256:                     0
token_count <= 0:                      0
non-contiguous ordinals:               0

sum(shard row_count):         10,487,096
sum(document chunk_count):    10,487,096
row counts reconcile:               TRUE
shard hash mismatches:                 0
```

**All violation counts are zero, measured against the complete real
corpus** — not asserted, not sampled.

## Stage 9 — Sample quality inspection

17 documents (the Stage 6 pilot sample), each traced end-to-end: Task 4.1
manifest entry → normalized file/body (re-verified by content hash) →
selected chunk rows (located via `document_manifest.parquet`) →
`chunk_local_id`/`chunk_uid` (recomputed and compared) → char offsets
(round-trip re-checked against the real body text) → document manifest →
shard manifest. **17/17 passed, 0 failures.**

## Stage 10 — Build identity and Task 4.3 handoff

```text
phase_4_2_build_config_hash:  9253de8418deef249ef412e3e3b155e4551c6d35b117aac4cdf67b0e292994e9
document_manifest_sha256:     b8e5706f05001c323401192c36a5f4326d92a6b77f14dfa4916fdf67f8ba9da0
shard_manifest_sha256:        b0421c390e218099f20563faffcfaa8791678ba571995738f5cd7df82a7088ac
shard count:                  54
total chunk count:            10,487,096
parquet_compression:          zstd
total artifact size:          3,406,258,160 bytes (~3.17 GiB)
```

Full artifact layout (git-ignored, under `artifacts/`):

```text
artifacts/chunks_full/<phase_4_1_config_hash>/<chunk_config_hash>/
  shards/part-00000.parquet ... part-00053.parquet
  build_state.jsonl            (append-only checkpoint log)
  document_manifest.parquet    (one row per Task 4.1 document: status/shard_id/chunk_count)
  shard_manifest.json          (per-shard id/path/row_count/sha256/first+last document_id/
                                 chunk_config_hash/chunk_schema_version — independently
                                 verifiable/transferable, so Task 4.3 can take one shard,
                                 verify it, embed it, and checkpoint independently, whether
                                 that runs on this laptop or Colab/H100 later)
```

Tracked result: `results/phase_4_2_full_corpus_chunking.json`. Tracked
config: `configs/phase_4_2_full_corpus_chunking.json`.

## Known limitations

- `section_id`/`section_title` are `NULL` for every production row — an
  honest consequence of the frozen fixed/non-section-aware split, not a
  defect (see "Offset and section metadata policy" above).
- `company` is `NULL` for 65.91% of chunks, inherited unchanged from Task
  4.1's approved policy.
- The build required one resume after an environmental (not code-level)
  interruption; the measured 15.90 docs/s figure comes from the resumed
  segment only, since the interrupted segment's process was killed before
  it could report its own final statistics.
- `content_type` is always `"prose"` — EDGAR-CORPUS never had tables (Data
  Preparation, confirmed already).

## Next consumer

Task 4.3 (full-corpus embedding) reads
`artifacts/chunks_full/754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f/ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06/shards/*.parquet`
plus `shard_manifest.json`, embeds each chunk's `text` column with the
Phase 3-selected `Qwen/Qwen3-Embedding-0.6B`, and checkpoints per shard.

## Reproducing this build

```bash
python scripts/chunk_full_corpus.py --plan            # identity/config only, no writes
python scripts/chunk_full_corpus.py --pilot            # 17-doc stratified sample
python scripts/chunk_full_corpus.py --run               # full build, resumable
python scripts/chunk_full_corpus.py --status             # checkpoint status
python scripts/chunk_full_corpus.py --verify-sample       # determinism spot-check
```

Read-only against the Task 4.1 artifact; writes only
`artifacts/chunks_full/<p41-hash>/<chunk-hash>/` (git-ignored) and the two
small tracked config/result files. No GPU required.
