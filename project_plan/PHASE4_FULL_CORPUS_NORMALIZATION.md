# Phase 4 Task 4.1 — Full-Corpus Normalization

Scales Task 1.2's minimal EDGAR-CORPUS -> Markdown normalizer from the
1,500-filing Phase 1 development corpus to the complete, frozen
91,086-filing EDGAR-CORPUS. Body-rendering logic
(`src/normalize/edgar_markdown.py`'s `render_body`/`normalize_newlines`/
`output_filename`) is byte-for-byte unchanged from Task 1.2 — only the
frontmatter contract and the driver (resumable, checkpointed, over the full
corpus instead of a curated 1,500-row manifest) are new.

## Objective

Apply the selected normalization pipeline to the complete EDGAR-CORPUS,
preserve deterministic document identity, preserve the frozen metadata
contract where the full corpus can actually support it, and produce a
config hash + build manifest Task 4.2 can consume. Deliberately does not
chunk, embed, index, retrieve, or call an LLM — CPU + disk I/O only, no GPU.

## Stage 1-2 — Preflight and source identity audit

Verified directly against the live repository before any code was written:

- Phase 3 exit audit: PASSED (`project_plan/PHASE3_EXIT_AUDIT.md`).
- Phase 4 had not started; Task 4.1 is the next roadmap task.
- `src/normalize/edgar_markdown.py` / `normalizer_version=phase1-minimal-v1`
  are still the selected normalizer per `project_plan/PHASE1_NORMALIZATION.md`.
- `scripts/dev.py doctor` / `test --portable` pass before and after this task.

Full-corpus source audit (direct DuckDB query against
`data/edgar_corpus/{train,test,validation}.parquet`, read-only):

```text
total rows:                 91,086  (train=47,000, test=22,036, validation=22,050)
distinct filenames:         91,086  (0 duplicate filename groups)
distinct (cik, year) pairs: 91,086  (0 duplicate groups)
null/empty identity fields: 0
distinct CIKs:               25,937
year range:                  1993-2020
all-20-sections-empty rows:     847
```

Matches the frozen `PROJECT_EXECUTION.md`/`DATA_READINESS_REPORT.md` totals
exactly. Document identity reuses EDGAR-CORPUS's own `filename` verbatim
(e.g. `1005817_2016.htm`) — the same convention Task 1.1/1.2 already used,
never a row number, array position, UUID, or invented accession.

## Stage 3 — Freezing the full-corpus metadata contract

### The `company` gap (stopped, reported, user-decided)

Task 1.2's dev-corpus frontmatter populated `company` for **100%** of its
1,500 rows via a CIK -> name join against `data/xbrl.duckdb`'s `submissions`
table, because Task 1.1 deliberately restricted selection to the
XBRL-aligned 2016-2020 population. Against the full corpus, that same join
only covers:

```text
CIKs covered:   6,877 / 25,937  = 26.51%
rows covered:  31,047 / 91,086  = 34.09%
```

(independently re-measured here; matches `DATA_READINESS_REPORT.md`'s
already-frozen 26.51% CIK-overlap figure exactly). EDGAR-CORPUS itself has
no company-name column at all (confirmed directly from the parquet schema:
`filename`, `cik`, `year`, `section_*` only). Some covered CIKs also have
more than one distinct historical name in `submissions` (company renames) —
e.g. CIK 1338929 has 4.

This is exactly the situation `PROJECT_EXECUTION.md`'s Stage 3/hard-stop
list anticipates: a frozen downstream field that the full corpus can't
satisfy without either fabricating values or defining a nullable policy
that didn't exist yet. **Stopped and reported to the user** (field, source
availability, coverage, policy choices, recommended non-fabricating
policy); user selected **nullable company** (2026-09-12) over
drop-the-field or restrict-to-XBRL-covered-rows-only alternatives.

Adopted policy, frozen in `configs/phase_4_1_full_corpus_normalization.json`:

```text
company:
  source:      data/xbrl.duckdb submissions (frozen, read-only), cik -> name
  match key:   cik only (no accession/period join - EDGAR-CORPUS has no accession)
  tie-break:   when a CIK has multiple distinct names, use the row with max(filed)
  missing:     null - never fabricated, never guessed from filename/ticker heuristics
```

### Full-corpus frontmatter contract

`FULL_CORPUS_FRONTMATTER_KEYS` (`src/normalize/edgar_markdown.py`) drops
Task 1.2's `development_manifest_sha256` (no per-filing dev manifest exists
at full-corpus scale) and makes `company` genuinely nullable:

```yaml
---
cik: 1000298
company: "IMPAC MORTGAGE HOLDINGS INC"
form_type: "10-K"
fiscal_year: 2011
source: "edgar_corpus"
source_filename: "1000298_2011.htm"
document_id: "1000298_2011.htm"
source_split: "validation"
---
```

vs. an uncovered CIK:

```yaml
---
cik: 1003114
company: null
form_type: "10-K"
fiscal_year: 1995
source: "edgar_corpus"
source_filename: "1003114_1995.txt"
document_id: "1003114_1995.txt"
source_split: "train"
---
```

`render_frontmatter()`/`render_document()` (`src/normalize/edgar_markdown.py`)
were extended, backward-compatibly, to accept an explicit `keys` tuple and
to render Python `None` as the bare YAML `null` literal — Task 1.2's own
call site is untouched (no `keys` argument passed, no `None` value ever
produced there), so its behavior is provably unchanged.

`cik`/`fiscal_year` are cast to Python `int` (int64/int32 per Task 1.1's
original rule) from the source's native `VARCHAR` columns.
`form_type="10-K"` and `source="edgar_corpus"` remain constants, matching
Task 1.2 (EDGAR-CORPUS is structurally a 10-K-only corpus — its 20
`section_*` columns are exactly the standard 10-K Item numbers).
`accession`/`period_end`/`filed_date`/`sic` are not part of this frontmatter
contract at all (same as Task 1.2 — they are Task 2.9's chunk-schema
concern, already frozen there as always-NULL for `edgar_corpus`).

Config: `configs/phase_4_1_full_corpus_normalization.json` — frozen fields
listed in the config's own `config` object (task, normalizer_version,
source files/identity, section ordering/newline/empty-section/
empty-document policy, frontmatter keys and types, company-name policy
with its measured coverage, document-id/output-filename policy, build
manifest schema version). Hashed via Task 2.10's
`src.artifacts.versioning.semantic_hash()` — no second hashing convention.

```text
phase_4_1_config_hash: 754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f
```

## Stage 4 — Task 1.2 regression (body-compatibility)

`render_body`/`normalize_newlines`/`output_filename` are called completely
unmodified by the new driver. Verified two ways:

1. **Synthetic regression** (`tests/test_phase_4_1_full_corpus_normalization.py::test_body_bytes_identical_between_dev_and_full_corpus_frontmatter_contracts`,
   portable): identical section input rendered through Task 1.2's original
   `FRONTMATTER_KEYS` path and the new `FULL_CORPUS_FRONTMATTER_KEYS` path
   produces byte-identical **body** text; only the frontmatter (documented,
   expected) differs.
2. **Real-artifact regression** (`local_data`-marked): document
   `1005817_2016.htm`, present in both the real Phase 1 dev-corpus artifact
   (`artifacts/normalized/phase1-minimal-v1/1005817_2016.md`) and the live
   EDGAR-CORPUS source, produces an identical body when re-rendered through
   the full-corpus driver.

Text normalization semantics were never touched by this task.

## Stage 5-6 — Resumable driver and pilot

`scripts/normalize_full_corpus.py`. Checkpoint contract:

- One unit = one source `document_id`. Append-only NDJSON
  (`build_state.jsonl`): a header record binds the checkpoint to an exact
  `phase_4_1_config_hash` + `source_document_ids_sha256`; every subsequent
  line is a `NORMALIZED | VALID_EMPTY_SOURCE | FAILED` unit record with its
  `content_sha256`. Resuming under a different config hash or a different
  source document-id set is refused (`SystemExit`), never silently rebuilt.
- Every completed unit is re-verified against the real file on disk (hash
  match) before being treated as "done" — a corrupted or missing output
  file is silently re-queued, never silently accepted.
- `FAILED` units are always retried on the next invocation; only
  `NORMALIZED`/`VALID_EMPTY_SOURCE` units are ever skipped.
- Per-document writes are atomic (`write` to `*.md.tmp` then `os.replace`).
- Source parquet is read through a DuckDB **view**, not a materialized
  table, and fetched in batches of 500 document_ids at a time — the full
  corpus's ~13 GB of section text is never held in memory at once. Peak
  RSS measured directly at 524 MB during the real bulk run (`psutil`).
- Progress is printed every 2,000 processed units: count, percent,
  elapsed, docs/sec, bytes written, failure count — never a silent
  multi-hour detached run.

Pilot (`--pilot`): a deterministic stratified sample (16 documents) covering
every source split, four year bands (1993-99, 2000-09, 2010-19, 2020),
the largest and smallest documents by section-text length, and 5 explicit
empty-source documents. The pilot writes into the *same* checkpoint as the
full run — it is not a separate throwaway build; a later `--run` simply
resumes past it, which is itself a live demonstration of the resume
contract.

## Stage 7 — Full build

Two prior partial invocations (a 16-document pilot and a 2,000-document
throughput benchmark) plus one bulk `--run` completed the corpus:

```text
[NORMALIZE]  91,086 / 91,086 100.00%   elapsed=2981.6s   docs/s=29.87   written_GB_this_run=12.87   failures_this_run=0
```

Bulk-run measurements: 89,070 units processed in 2,981.6 s (29.87 docs/sec),
peak RSS 524,283,904 bytes, 0 failures throughout every invocation.

Failure policy: every source row's outcome is exactly one of
`NORMALIZED | VALID_EMPTY_SOURCE | FAILED` — verified by
`summarize_final()`'s `missing_count` (rows accounted for by neither a
verified completion nor an explicit FAILED record) being `0`. No fourth
"silently skipped" state exists.

## Stage 8 — Validation

**Completeness** (measured against the real build):

```text
source rows:              91,086
unique normalized outcomes: 91,086  (NORMALIZED=90,239, VALID_EMPTY_SOURCE=847)
missing:                        0
duplicate normalized IDs:       0
unexplained failures:            0
```

**Text/formatting**: every `NORMALIZED`/`VALID_EMPTY_SOURCE` output was
validated *at write time* (`validate_full_corpus_output()`) — not merely a
sample — for: valid frontmatter delimiters/required keys, `form_type`/
`source` constants, source-identity match, correct empty-vs-non-empty body
per `is_all_sections_empty()`, at least one Item heading when non-empty,
exactly one trailing newline, and UTF-8 encodability.

**Source immutability** (re-verified after the build):

```text
data/edgar_corpus/{train,test,validation}.parquet: unchanged (sizes/hashes match pre-build)
data/xbrl.duckdb:              7,011,053,568 bytes  (~6.53 GiB, matches documented ~6.6 GB)
raw XBRL ZIPs:                 36  (matches frozen fact)
primary filings:               990  (matches frozen fact)
```

Also covered by a dedicated `local_data` test
(`test_plan_mode_never_modifies_frozen_source_files`) that hashes the
frozen source files before/after a `--plan` invocation.

**Deterministic sample trace** (manually inspected, spanning 1990s/2000s/
2010s/2020, all three splits, a resolved-company document, an unresolved
(null-company) document, and an empty-source document):

- `1000298_2011.htm` (validation split, 2011) — `company: "IMPAC MORTGAGE
  HOLDINGS INC"` resolved via XBRL join, correct Item-1/1A/... ordering.
- `1003114_1995.txt` (train split, 1995) — `company: null` (CIK not in
  XBRL submissions), `VALID_EMPTY_SOURCE`, zero-byte body, exactly one
  trailing newline.
- `1005817_1995.txt` — also `VALID_EMPTY_SOURCE` (distinct row/year from
  the unrelated `1005817_2016.htm` Task 1.2 dev-corpus example — same CIK,
  no identity collision).

## Stage 9 — Build identity and determinism

```text
phase_4_1_config_hash:  754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f
build_manifest_sha256:  3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9
```

Determinism verification (no second full 13 GB duplicate build):

1. `phase_4_1_config_hash` — `semantic_hash()` over the frozen config dict.
2. Deterministic sorted-`document_id` processing/manifest order.
3. Per-document `content_sha256` in both `build_state.jsonl` and
   `manifest.jsonl`.
4. Idempotent resume — re-running `--run` against the complete checkpoint
   reprocessed exactly 0 units (verified directly, the finalization
   invocation).
5. `--verify-sample` — re-rendered the 16-document Stage 6 pilot sample
   fully in memory (no disk write) and diffed `content_sha256` against the
   manifest: **0 mismatches**.

Tracked result: `results/phase_4_1_full_corpus_normalization.json`.
Full per-document manifest (git-ignored, too large for Git):
`artifacts/normalized_full/<phase_4_1_config_hash>/manifest.jsonl`
(91,086 lines, one per source document, sorted by `document_id`).

## Known limitations

- `company` is `null` for 65.91% of rows (60,039/91,086) — an honest,
  measured, user-approved gap, not a defect. Never fabricated.
- `accession`/`period_end`/`filed_date`/`sic` remain entirely absent from
  this frontmatter (unchanged from Task 1.2/Task 2.9's already-frozen
  policy for `edgar_corpus`) — Task 2.9's chunk schema already documents
  these as legitimately NULL for this source.
- Output layout is a flat directory of 91,086 `*.md` files (matching Task
  1.2's convention) rather than sharded subdirectories — a valid,
  already-repository-supported layout per the prompt's own "or another
  layout already supported by the repository" allowance.
- `normalized_dir_for_config()` (new `src/storage.py` method) is additive;
  Task 1.2's existing `normalized_dir(version)` and its on-disk
  `artifacts/normalized/phase1-minimal-v1/` output are completely
  untouched — no collision, no migration.

## Next consumer

Task 4.2 (full-corpus chunking) reads
`artifacts/normalized_full/754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f/*.md`
plus `manifest.jsonl`, applies the Phase 3-selected `fixed/256/0` chunking
configuration, and writes versioned chunk Parquet.

## Reproducing this build

```bash
python scripts/normalize_full_corpus.py --plan     # audit + config hash only
python scripts/normalize_full_corpus.py --pilot    # 16-doc stratified sample
python scripts/normalize_full_corpus.py --run       # full build, resumable
python scripts/normalize_full_corpus.py --status    # checkpoint status
python scripts/normalize_full_corpus.py --verify-sample  # determinism spot-check
```

Read-only against `data/edgar_corpus/*.parquet` and `data/xbrl.duckdb`;
writes only `artifacts/normalized_full/<hash>/` (git-ignored) and the two
small tracked files (`configs/phase_4_1_full_corpus_normalization.json`,
`results/phase_4_1_full_corpus_normalization.json`).
