# Testing

Tasks 0.1–0.7 were verified by hand, one command at a time. Task 0.8 turns
the important invariants from that manual verification into a small,
repeatable `pytest` suite — a safety net for the Phase 0 foundation before
Phase 1 starts building on top of it.

## Test philosophy

Two different kinds of test live side by side, and they fail differently on
purpose:

- **Portable correctness tests** — pure logic, no machine-specific
  capability required. These must pass on any clone, any machine, right
  after `pip install`.
- **Local capability smoke tests** — exercise a real, expensive local
  resource (26 GB of frozen SEC/XBRL data, a CUDA GPU, an already-cached
  embedding model) that a public clone may not have.

**Missing optional capability → SKIP with a clear reason. Present capability
that fails → FAIL.** A laptop with no NVIDIA GPU skipping the CUDA test is
normal; this development machine reporting `torch.cuda.is_available()` and
then failing a real matmul is a bug, not a skip. Skips are never used to
hide a real failure on a machine that has the capability.

## Test categories

Registered `pytest.ini` markers: `local_data`, `gpu`, `model`. Unmarked
tests are the portable set.

| Category | Files | What it protects |
|---|---|---|
| portable | `test_config.py`, `test_logging_utils.py`, `test_storage.py`, `test_dependencies.py`, `test_ingest_imports.py`, `test_lancedb_smoke.py` | `src.config`/`src.logging_utils`/`src.storage` behavior, critical dependency imports, existing `src.ingest` modules still importable, LanceDB+PyArrow+Python 3.11 compatibility (temp DB only) |
| `local_data` | `test_duckdb_smoke.py` | Frozen `data/` paths exist and `xbrl.duckdb` opens read-only with the expected tables/fact count — skips cleanly if the dataset isn't present |
| `gpu` | `test_gpu_smoke.py` | A real CUDA kernel (matmul) executes and returns a finite result — skips if no CUDA GPU |
| `model` (+`gpu`) | `test_embedding_smoke.py` | `BAAI/bge-small-en-v1.5` (the Phase 1 baseline) still loads and runs on CUDA through `sentence-transformers`, from the local cache only |

## Offline policy

**No test downloads a dataset or model, and no test calls an external API.**
`src.ingest.fetch_*` modules are imported (to catch dependency/import
regressions) but their `main()`/download entry points are never called.
The embedding smoke test additionally sets `HF_HUB_OFFLINE=1` and passes
`local_files_only=True` to `SentenceTransformer(...)` — two independent
guards against an accidental network call — and pre-checks
`huggingface_hub.try_to_load_from_cache(...)` before attempting to load, so
a missing model produces a clean skip rather than a confusing failure deep
inside the load call. No global network-blocking plugin was added; nothing
in this suite calls `requests.get`/`.post` or any HTTP client directly, so
there was nothing else to guard against.

No test requires a real credential — not `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `SEC_USER_AGENT`, nor AWS credentials. `python -m
pytest` runs cleanly with none of those set.

## Frozen-data policy

Tests never write to `data/`. All temporary writes use pytest's `tmp_path`
(LanceDB smoke test, config/storage override tests) or a disposable child
under the real `artifacts_root` that is removed in a `finally` block
(`storage.ensure_dir()` idempotency test) — with a session-scoped
`conftest.py` fixture as a backstop that removes `artifacts/` entirely at
the end of the run if the suite is what created it. `data/xbrl.duckdb` is
only ever opened `read_only=True`.

## Test isolation

Python's `logging` module and `src.config.get_settings`/`src.storage.
get_storage` (both `functools.lru_cache`-cached) are process-global state
that can easily leak between tests. `tests/conftest.py` has two autouse
fixtures that snapshot and restore this state around **every** test:
config/storage caches are cleared before and after each test, and the root
logger's handler list + level are captured before each test and restored
exactly afterward. This is why logging tests can freely call
`configure_logging()` and storage/config tests can freely `monkeypatch`
environment variables without needing to remember cleanup themselves — and
why the suite produces identical results regardless of run order (verified:
ran three times in a row with identical `60 passed` results).

## Running tests

Raw `pytest` commands (always available, work anywhere):

```bash
python -m pytest                                          # full suite
python -m pytest -m "not local_data and not gpu and not model"   # portable only
```

Equivalent `scripts/dev.py` shortcuts (Task 0.9 — thin wrappers over the
exact same commands, plus `doctor`/`data`/`gpu` environment checks; see
`project_plan/DEVELOPER_COMMANDS.md`):

```bash
python scripts/dev.py test
python scripts/dev.py test --portable
python scripts/dev.py smoke        # local_data/gpu/model tests only
```

## Skip semantics

```text
Missing optional machine capability -> skip, with a clear pytest.skip() reason.
Present capability that fails        -> fail. Never converted to a skip.
```

## Future expansion

Phase 1 adds component tests as normalization/chunking/embeddings/retrieval
are actually built — not before. Phase 2 adds the deterministic
recall@k/MRR/nDCG/citation/truth-contract unit tests called for in
`PROJECT_EXECUTION.md`; none of that exists yet and Task 0.8 does not
speculatively stub it out.
