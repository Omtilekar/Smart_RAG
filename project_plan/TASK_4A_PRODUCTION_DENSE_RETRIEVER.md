# Task 4.A - Production Dense Retriever Integration (Gate A)

Status: COMPLETE (2026-10-25). Prompt: `project_plan/task_4.A_production_dense_retriever_integration.md`.

The live FastAPI dense route now serves the frozen full-corpus production
artifact instead of the Phase 1 development index.

```text
BEFORE  BAAI/bge-small-en-v1.5 (384-d) | 162,357-row dev LanceDB | BaselineRetriever
AFTER   Qwen/Qwen3-Embedding-0.6B (1024-d) | 10,487,096-row production LanceDB | ProductionDenseRetriever
```

No chunks, embeddings or indexes were rebuilt. No OpenRouter call, no AWS
access, protected TEST unopened (0/3).

## Why the dev retriever could not be reused

`BaselineRetriever` / `RetrievalResult` hardcode the Phase 1 17-column schema.
The Task 4.4 production table has a different 24-column schema.

| Concept | Dev schema (Phase 1) | Production schema (Task 4.2/4.4) |
| --- | --- | --- |
| Chunk identity | `chunk_id` = `<document_id>::chunk<n>` | `chunk_uid` (sha256 hex), `chunk_local_id` (`chunk000000`) |
| Dev-only provenance | `source_filename`, `source_split`, `normalizer_version`, `normalization_build_sha256`, `development_manifest_sha256` | not present |
| Production-only | not present | `accession`, `period_end`, `filed_date`, `sic`, `section_id`, `section_title`, `char_start`, `char_end`, `content_type`, `table_id`, `chunk_schema_version` |
| `company` | populated | NULL for every EDGAR-CORPUS row sampled |
| Vector | `vector[384]` | `vector[1024]` |
| Table | `chunks`, exact cosine, no index | `chunks`, exact cosine, BTree scalar indexes on `cik`, `fiscal_year`, no ANN |

## What was built

- `src/retrieval/production.py`
  - `ProductionRetrievalResult`: exposes the attribute names downstream code reads
    (`chunk_id`, `document_id`, `text`, `company`, `fiscal_year`, `source`, `rank`,
    `score`, `distance`) plus `chunk_uid`, `accession`, `section_*`, offsets. No vector.
  - Canonical identity stays `chunk_uid`. The citation id is derived, never stored:
    `chunk_id = <document_id>::<chunk_local_id>` (matches the citation parser).
  - A NULL `company` becomes `"CIK <cik>"`, never `None` or a fabricated name.
  - `ProductionDenseRetriever`: Qwen3 query encoder (frozen spec, instruction prefix,
    normalized float32) -> exact cosine search. Accepts `cik` / `fiscal_year` as a scalar
    PRE-filter by reusing `build_predicate` and `exact_cosine_search_filtered` unchanged.
  - `load_production_contract` / `validate_production_table` / `smoke_lookup`: startup
    checks. `score = 1 - cosine distance`, identical to the dev retriever.
  - `build_production_cache_identity`: the retrieval-cache identity for the production index.
- `src/api/dependencies.py`: `DENSE_RETRIEVER_MODE` selects the path. Production loads Qwen3
  only (never BGE) and opens one LanceDB handle. Dev is an explicit opt-in.
- `src/config.py`: one new setting, `DENSE_RETRIEVER_MODE` (`production` default, or `dev`).
  Paths and identity come from the existing frozen config/summary and `src/storage.py`,
  so no path or model setting was duplicated.

## Startup validation (fail closed)

Before `/status` reports ready, production mode checks, without scanning vectors:

1. Frozen config and summary agree, and the index identity hash re-computes.
2. The live Qwen3 embedding identity hash (model, revision, dimension, dtype,
   normalization, passage and query conventions) equals the one the index was built with.
3. Row count equals 10,487,096, all 24 columns exist, vector is `fixed_size_list[1024]`,
   zero ANN indexes, BTree indexes on `cik` and `fiscal_year` exist.
4. A one-row peek confirms `chunk_config_hash` and `chunk_schema_version`.
5. A self-retrieval smoke (one stored vector searched inside its own cik+year slice) returns distance ~0.

Any failure raises `DependencyInitializationError` with a concise reason and no local path.
There is no fallback to the dev index.

## Cache separation

The production cache identity differs from the dev identity in `retriever_kind`, model,
revision, dimension, embedding identity hash, chunk config hash, table schema label, index
identity hash and row count. A regression test shares one cache between a dev-keyed and a
production-keyed retriever and proves a cached dev result is never returned after the switch.
Failures are not cached (unchanged behavior). The cache is not disabled.

## Security order is unchanged

`ProductionDenseRetriever` -> `CachedRetriever` -> retrieval-security guard -> context guard
-> prompt -> provider -> output guard. Tests prove a poisoned production chunk is removed
before the prompt, that fully poisoned evidence abstains with no provider call, and that
telemetry counts the block.

## `/status`

Production mode reports `dense_retriever_mode=production`,
`embedding_model=Qwen/Qwen3-Embedding-0.6B`, its revision, `embedding_dimension=1024`,
`dense_index_row_count=10487096`, `dense_index_identity_hash`, `artifact_status=production`.
No path, secret or vector is exposed, and the stale BGE keys are gone in this mode. Dev mode
reports its own values (`artifact_status=development`).

## Real local smoke

`scripts/smoke_production_dense.py` -> `results/phase_4a_production_dense_smoke.json`
(live Qwen3 on the RTX 5060 + the real 10.5M-row table; fake provider for the API leg).

| Measure | Value |
| --- | --- |
| Index open | 1.4 s |
| Table validation | 0.014 s |
| Startup smoke lookup | 0.15 s |
| Qwen3 model load | 9.8 s |
| Full app startup (model + index + XBRL + gazetteer) | 27.8 s |
| Query embedding, warm | 45.5 ms |
| Company + year scoped search, first / warm | 61.5 ms / 77.4 ms |
| Company-only scoped search | 81.9 ms |
| **Unscoped search (2 queries)** | **33.0 s, 33.3 s** |
| `POST /query` end to end (fake provider, unscoped) | 32.6 s |
| Process RSS after app startup | about 4.7 GB (from 43 MB) |
| GPU memory allocated | about 2.4 GB |

Scoped results are deterministic across repeats and all returned chunks belong to the
requested cik / fiscal year. Unscoped results span many companies as expected.

## Findings and remaining gaps

1. **Unscoped dense search takes about 33 s per query.** This is exact (flat) cosine over
   10.5M x 1024 vectors with no ANN or quantization (a frozen Task 4.4 decision), and it matches
   Task 4.4's own diagnostic (p50 33.6 s). Scoping by company and year with the existing BTree
   pre-filter is about 500x faster. The live router does not pass filters yet, so every live
   dense question currently pays the full-scan cost. Wiring the selected metadata pre-filter
   (Gate B) is now the top priority; quantization/ANN would be a separate, re-evaluated decision.
2. CRAG stays disabled. The calibrated 0.5531 threshold came from the 323,971-chunk dev
   corpus, and top-1 score distributions over 10.5M chunks differ, so applying it would be
   unverified. `crag_threshold` stays `None` in the cache identity.
3. `Dockerfile` and `.dockerignore` still describe the dev index and ship no artifact. A
   container started with the new default would fail closed. Deployment (Task 4.11) is
   deferred, so this was not changed here.
4. `.env.example` was not updated (access to that file was blocked in this session). Add
   `DENSE_RETRIEVER_MODE=production` (or `dev`) there.
5. About 4.7 GB RSS and a 28 s startup matter for the Task 4.15 performance work.
6. Company names are NULL in the artifact, so prompts show `CIK <n>` instead of a company name.

## Tests

- New: `tests/test_production_retriever.py` (schema adaptation, vector contract, filter
  contract, index and identity validation, cache separation, fail-closed startup, no BGE load
  in production mode, `/query` and `/status` through the app, retrieval-security integration).
- Updated: `tests/test_api_dependencies.py`, `tests/test_api_retrieval_cache_integration.py`
  (pin the explicit dev mode), `tests/test_static_ui.py` (UI now reports the production index).
- `scripts/dev.py doctor` PASS; `test --portable` 2384 passed, 38 deselected;
  `pytest -m "not generation_api"` 2418 passed, 1 skipped, 2 failed. The two failures are
  `tests/test_phase3_trusted_baseline.py::...test_real_dev_scope_is_nonempty_and_frozen_shape`
  and `tests/test_primary_html_parser.py::test_real_primary_document_structural_parsing`.
  Both fail on `ImportError: DLL load failed while importing testing: An Application Control
  policy has blocked this file` (pandas) and touch no changed code. A third test hit the same
  block on one run and passed on the next.
