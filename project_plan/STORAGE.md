# Storage

`src/storage.py` is the one authoritative map of where things live —
future modules should get paths from `get_storage()` instead of writing
`Path("data/xbrl.duckdb")` or `Path("artifacts/chunks")` independently.

## Goals

1. Make the frozen-input / generated-output boundary explicit and hard to
   violate by accident.
2. Give generated artifacts a deterministic, versioned identity
   (`chunk_config_hash`, embedding model, eval version, ...) so the same
   config always resolves to the same location and a different config
   never collides with it.
3. Stay local-first now, without closing the door on an S3 backend later.

## Frozen vs. generated boundary

**Frozen inputs** (`data/*`, produced by Data Preparation, documented in
`DATA_READINESS_REPORT.md`) are read-only. `src/storage.py` never deletes,
renames, moves, truncates, overwrites, repartitions, or downloads into any
frozen-input path — it only ever *reads* their locations.

**Generated outputs** live entirely under a separate `artifacts/` root,
never inside `data/`. `results/` is a third, distinct location for small,
human-readable, sometimes-committed summaries — never large generated
artifacts.

## Local directory layout

Actual current `data/` layout (inspected directly, not assumed):

```text
data/                          # FROZEN — read-only, Data Preparation output
├── .gitkeep
├── msmarco/                   # corpus/queries/qrels parquet
├── edgar_corpus/              # {train,test,validation}.parquet
├── raw/
│   ├── xbrl/                  # 36 quarterly ZIPs
│   └── primary/               # {cik}/{accession}.htm, 990 filings
├── interim/audit_xbrl_meta/   # derived, from the Phase 1 audit - not a
│                               # storage.py concern; not centralized here
├── xbrl.duckdb                # 90.7M facts + submissions
└── validation_report.md

artifacts/                     # GENERATED, git-ignored, created on demand
├── normalized/<version>/
├── chunks/<chunk_config_hash>/
├── indexes/<chunk_config_hash>/<embedding_model_key>/
├── eval/<eval_version>/
└── cache/                     # not yet exposed by a helper - see below

results/                       # small, sometimes-committed summaries
```

`artifacts/` does not exist on disk until something explicitly creates a
subdirectory under it (verified directly — see Verification below); it is
not created by importing `src.storage` or by calling `get_storage()`.

**Note on `PROJECT_SPEC.md`'s storage-architecture section**: that document
sketches an earlier `data/okf/`, `data/chunks/`, `data/index/` layout
(generated artifacts nested inside `data/`). Neither that layout nor this
one existed on disk before this task — Task 0.7's own instructions
explicitly specify `artifacts/` as a sibling of `data/` unless the
repository already defines another *implemented* convention, and none did.
This is the same kind of staleness already flagged for `PROJECT_SPEC.md`'s
data-inventory numbers in the pre-Phase-0 baseline; reconciling
`PROJECT_SPEC.md`'s prose with the actual implemented layout is future
documentation work, not something this task silently overrides.

## `src/storage.py` API

```python
from src.storage import get_storage, safe_component, StorageError

storage = get_storage()          # cached StoragePaths singleton

# frozen inputs (Path properties, read-only)
storage.msmarco_root
storage.edgar_corpus_root
storage.raw_xbrl_root
storage.primary_docs_root
storage.xbrl_db

# generated outputs (deterministic, versioned)
storage.normalized_dir(version)
storage.chunks_dir(chunk_config_hash)
storage.index_dir(chunk_config_hash, embedding_model)
storage.eval_dir(eval_version)

# existence checks (frozen inputs; type/existence only, no content validation)
storage.require_file(path)
storage.require_dir(path)

# explicit, restricted output creation
storage.ensure_dir(path)         # only under artifacts_root/results_root
```

`StoragePaths` is a frozen dataclass (`repo_root`, `data_root`,
`artifacts_root`, `results_root`); `get_storage()` builds it from
`src.config.get_settings()` — `data_root` is `Settings.storage_root`
directly, so a `STORAGE_ROOT` override moves the frozen-input root, while
`artifacts_root`/`results_root` stay repo-relative regardless (generated
engineering outputs live with the repo, not wherever raw data happens to be
mounted — verified directly).

`src/storage.py` consumes `src.config.Settings` exclusively; it never reads
`os.environ`/`STORAGE_ROOT`/`.env` on its own. Dependency direction:
`src.config` → `src.storage` → future pipeline modules.

Task 0.7 only *centralizes locations and identity*. It does not implement
`read_parquet()`/`write_parquet()`/`open_duckdb()`/`open_lancedb()` or any
other serialization helper — those belong close to the code that actually
produces/consumes each format.

## Artifact versioning

| Helper | Identity | Implemented now? |
|---|---|---|
| `normalized_dir(version)` | a normalizer version string | path helper only — no normalizer exists yet |
| `chunks_dir(chunk_config_hash)` | an already-computed config hash | path helper only — hashing the chunk config is the future chunker's job, not Task 0.7's |
| `index_dir(chunk_config_hash, embedding_model)` | **both** together | path helper only — the same chunks may be embedded with several models in Phase 3, so neither key alone is sufficient identity |
| `eval_dir(eval_version)` | an eval-set version string | path helper only — no eval dataset exists yet |

None of these downstream systems (normalizer, chunker, embedder, eval-set
generator) exist yet. This task provides only the deterministic *location*
each will write to once it does.

## Safe path components (`safe_component`)

Embedding model names and other identifiers may contain `/`, `:`, or
spaces (e.g. `BAAI/bge-small-en-v1.5`). `safe_component()` handles two
cases differently, on purpose:

- **Legitimate multi-segment identifiers are normalized**: `/` and `\`
  between segments become `--`, then remaining `:`/whitespace become `-`.
  `BAAI/bge-small-en-v1.5` → `BAAI--bge-small-en-v1.5`.
- **Path-traversal or absolute-path-shaped input is rejected outright**
  (`StorageError`), never silently sanitized: a `..` or `.` segment
  anywhere, a leading `/` or `\`, a drive-qualified prefix (`C:\...`), or
  the bare strings `.`/`..`/empty string. `storage.chunks_dir("../escape")`
  raises `StorageError` — verified directly, matching the literal example
  in this task's own spec.

## Directory-creation policy

- Importing `src.storage`: creates nothing.
- Calling `get_storage()`: creates nothing (cheap — no filesystem writes,
  no existence checks, no data scanning).
- Requesting a generated path (`storage.chunks_dir(...)` etc.): creates
  nothing — it's pure path construction.
- `storage.ensure_dir(path)` is the **only** thing that writes to disk, and
  only when called explicitly. It refuses (raises `StorageError`) to
  create anything outside `artifacts_root`/`results_root` — so it can never
  be pointed at a frozen-input location by mistake — and is idempotent
  (repeated calls on the same path are safe, no error, no duplicate
  creation).

## S3 boundary

```text
Current backend: local filesystem
S3 backend: NOT IMPLEMENTED
```

No `boto3`/`s3fs`/AWS credentials/uploads/downloads exist anywhere in this
module, and none were added as dependencies. What *is* deliberately
S3-compatible: every generated-artifact path is built from a small set of
POSIX-style logical components (`chunks/<hash>`, `indexes/<hash>/<model>`,
...) resolved beneath one root (`artifacts_root`). A future S3 backend
could map those same logical keys beneath an S3 prefix instead of a local
directory — but no such backend, interface, or placeholder class
(`S3Storage`, `CloudStorage`, etc.) exists yet. This section states that
plainly rather than implying cloud-readiness that hasn't been built.

## Logging integration

`src/storage.py` uses `src.logging_utils.get_logger`/`log_event` for one
event: `ensure_dir()` logs `artifact_dir_created` at INFO level, but only
when it actually creates a new directory (not on a no-op repeat call).
Plain path construction (`storage.chunks_dir(...)`, `storage.xbrl_db`,
...) never logs anything — it would be noise.

## Existing ingestion code

`src/ingest/` was **not** modified and does not use `src.storage`. Data
Preparation is complete and frozen; its existing path logic
(`STORAGE_ROOT` read directly via `os.getenv` in `src/ingest/common.py`)
continues to work exactly as before. New application code going forward
should use `src.storage` instead.
