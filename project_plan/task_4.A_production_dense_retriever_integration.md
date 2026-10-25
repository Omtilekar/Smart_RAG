# Task 4.A — Production Dense Retriever Integration

## Objective

Replace the current live development dense retriever with a production-compatible retriever that serves the frozen full-corpus Qwen3/LanceDB artifact.

This is **Gate A** of local production readiness.

The goal is to make these three layers match:

```text
selected retrieval configuration
=
production artifact
=
live FastAPI dense serving path
```

Current known state:

```text
LIVE NOW
- embedding model: BAAI/bge-small-en-v1.5
- dense index: development LanceDB
- row count: 162,357

FROZEN PRODUCTION ARTIFACT
- embedding model: Qwen/Qwen3-Embedding-0.6B
- embedding dimension: 1024
- normalized vectors
- chunk/index rows: 10,487,096
```

Do not rebuild the production index.
Do not change chunking.
Do not change embedding selection.
Do not run protected TEST.
Do not access AWS.
Do not make paid generation calls.

---

## 0. Read First / Preflight

Before editing anything, inspect the current repository and trace the real live dense path end to end.

Read at minimum:

- `Progress.md`
- `PROJECT_OVERVIEW.md` if present
- `project_plan/PROJECT_EXECUTION.md`
- current Phase 4 readiness/deployment docs
- `src/api/app.py`
- `src/api/service.py`
- `src/api/schemas.py`
- API dependency/bootstrap code
- `src/retrieval/`
- `src/embeddings/`
- `src/index/`
- `src/storage.py`
- relevant configs/manifests for the production index
- current `/status` implementation
- existing retrieval-cache code if Task 4.13 exists
- existing retrieval-security code if Task 4.14 exists

Also inspect the production LanceDB schema directly.

Do not assume it matches the Phase 1 development schema.

Record:

```text
dev retriever schema
production retriever schema
dev chunk identifier
production chunk identifier
metadata fields
vector field name
table name
distance/similarity configuration
embedding query contract
```

Confirm before implementation:

1. current branch
2. working-tree state
3. current test baseline
4. protected TEST usage remains 0/3
5. no OpenRouter calls will be made
6. no AWS access is required

---

## 1. Core Problem to Fix

The live FastAPI service currently uses the Phase 1 development retriever/index.

The full-corpus production index was built later with a different embedding model and production schema.

Do NOT try to make the production index pretend to be the old development artifact.

Instead, build a **production retriever / adapter** whose public output matches the downstream retrieval contract while internally reading the production schema correctly.

Preferred architecture:

```text
FastAPI / service layer
        |
        v
DenseRetriever interface
        |
        +--> DevDenseRetriever        (legacy/test only if still needed)
        |
        '--> ProductionDenseRetriever (new live implementation)
                    |
                    v
              Qwen query encoder
                    |
                    v
          Production LanceDB table
                    |
                    v
          normalized RetrievalResult
```

Downstream consumers should not need to know whether the source was the old dev index or the new production index.

---

## 2. Do Not Reuse Incompatible Assumptions

Inspect the current development `BaselineRetriever` / result schema carefully.

If it hardcodes the old Phase 1 chunk schema, do not extend those assumptions into production.

Do not assume fields such as old `chunk_id`, filename layout, development-only metadata columns, or row ordering exist in the production table.

Build an explicit adapter from production rows to the common retrieval result contract.

Where production uses `chunk_uid` or another identifier, preserve it as the canonical production chunk identity.

If the existing API/citation layer requires a stable string citation ID, derive it deterministically from the production chunk identity without changing the underlying artifact.

---

## 3. Production Query Embedding

The live production dense path must use:

```text
Qwen/Qwen3-Embedding-0.6B
dimension: 1024
```

Use the exact frozen query-encoding convention from the production embedding build.

Before implementation, inspect:

- frozen embedding config
- model revision
- query prompt/instruction usage
- normalization setting
- dtype
- similarity metric

Do not guess.

The query embedding contract must match the vectors already stored in the production index.

Add an explicit runtime assertion:

```text
query_vector_dimension == production_index_dimension
```

Fail closed with a clear startup/readiness error if they do not match.

Do not silently fall back to BGE.

---

## 4. Production Index Discovery and Validation

At startup, validate the production index before reporting readiness.

Verify at minimum:

```text
index/table exists
expected table name
row count == expected manifest count
vector dimension == 1024
required metadata fields exist
production artifact identity matches configured manifest
```

Expected full-corpus row count:

```text
10,487,096
```

Do not scan all vectors at startup.

Use metadata/schema/manifest checks and a tiny deterministic smoke lookup.

If the repository already has a production manifest/hash contract, use it.

Do not create a second competing versioning system.

---

## 5. Storage / Configuration

Make the live dense retriever config-driven.

Do not hardcode local absolute paths.

Use the existing `src/storage.py` / settings conventions.

Add or reuse settings for concepts such as:

```text
DENSE_RETRIEVER_MODE=production
PRODUCTION_DENSE_INDEX_PATH=...
PRODUCTION_DENSE_TABLE=...
PRODUCTION_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
```

Only add settings that are actually needed by the existing configuration system.

If artifact identity is already derivable from manifests/config hashes, prefer that instead of duplicating config fields.

Do not expose local filesystem paths in public API responses.

---

## 6. Common Retrieval Result Contract

Normalize production retrieval rows into the same conceptual result shape required downstream.

At minimum preserve what the current downstream code actually needs, such as:

```text
stable chunk/document identity
text
score/distance
cik
fiscal year
form type
accession / filing identity
section metadata if available
source/provenance fields
```

Inspect actual consumers before deciding exact fields.

Do not expose raw vectors.

Do not drop provenance needed by:

- context guard
- retrieval-security guard
- citation validation
- UI source rendering

Add typed tests proving that production rows satisfy the downstream contract.

---

## 7. Similarity / Score Semantics

The production index and stored vectors were built under the frozen similarity contract.

Verify the actual LanceDB metric/index settings.

Do not change them.

If LanceDB returns distance rather than similarity, normalize score semantics carefully and document them.

Do not reuse a CRAG threshold against a score scale that differs from the scale used during calibration.

Important:

Task 4.A is primarily production dense integration.

If the production query path cannot safely reuse the frozen CRAG threshold because score semantics differ, report that clearly and leave CRAG disabled until its live score scale is verified.

Do not silently apply an invalid threshold.

---

## 8. Metadata Prefilter Compatibility

The production retriever must be designed so the already-selected metadata prefilter can be wired cleanly.

Support retrieval inputs that can carry filters such as:

```text
cik
fiscal_year
form_type
accession if appropriate
```

Do not force full-corpus global retrieval when a narrow scope is known.

If metadata prefiltering is already implemented in `src/retrieval/filtered.py`, reuse that logic where compatible.

Do not rewrite the algorithm.

For this task, the minimum requirement is:

```text
ProductionDenseRetriever can accept the metadata/filter contract
```

If the live router is not yet passing filters, preserve backward compatibility and document that Group 3/4 wiring remains a follow-up.

---

## 9. Retrieval Cache Integration

If the exact retrieval cache from Task 4.13 exists, the production dense retriever must work behind it.

The cache identity must change automatically when switching from the dev index to the production index.

Verify the key includes enough artifact identity to prevent this bug:

```text
query cached against BGE dev index
        ↓
switch to Qwen production index
        ↓
old cached evidence reused  ❌
```

Expected behavior:

```text
dev artifact identity != production artifact identity
```

therefore cache miss after the switch.

Add a regression test for this.

Do not disable the cache permanently.

Do not cache failures.

---

## 10. Retrieval Security Integration

If Task 4.14 exists, production retrieval output must still flow through retrieval security.

Required order:

```text
Production dense retrieval
        ↓
retrieval cache boundary as designed
        ↓
retrieval-security guard
        ↓
context guard
        ↓
generation
```

A production-index migration must not bypass:

- provenance validation
- duplicate defense
- RAG-poisoning checks
- context isolation

Add integration coverage.

---

## 11. API Dependency Wiring

Update the FastAPI dependency/bootstrap layer so the production retriever becomes the live dense retriever when production mode is selected.

Concept:

```text
startup
  ↓
load settings
  ↓
load Qwen query encoder
  ↓
open production LanceDB
  ↓
validate schema + artifact identity
  ↓
construct ProductionDenseRetriever
  ↓
wrap with cache if enabled
  ↓
inject into QueryService
```

Do not load both BGE and Qwen in production mode unless tests explicitly need both.

Avoid duplicate model loads.

Avoid opening multiple identical LanceDB handles unnecessarily.

---

## 12. `/status` Truthfulness

Update `/status` so it clearly reports the live dense runtime.

When production mode is active, it should expose safe fields such as:

```text
dense_retriever_mode: production
embedding_model: Qwen/Qwen3-Embedding-0.6B
embedding_dimension: 1024
dense_index_row_count: 10487096
artifact_status: production
```

Do not expose:

- absolute local paths
- secrets
- raw vectors

Remove or retire stale values that still claim the live service uses BGE once production mode is active.

If a dev mode remains for tests, `/status` should reflect the actual active mode.

---

## 13. Health / Readiness Behavior

Keep `/health` as liveness only if that is the existing contract.

Use `/status` / readiness reporting for dense dependency readiness.

Production dense readiness should fail if:

```text
Qwen model not loadable
production index missing
schema incompatible
dimension mismatch
artifact identity mismatch
required provenance columns missing
```

Do not crash with an opaque stack trace.

Return/log a concise internal reason safely.

---

## 14. Legacy Development Retriever

Do not delete the dev retriever immediately if tests or historical reproducibility still depend on it.

Preferred policy:

```text
production retriever = default live mode
dev retriever = explicit test/dev mode only
```

Do not let runtime silently fall back from production to dev if production initialization fails.

Silent fallback would make `/status` misleading.

Fail closed instead.

---

## 15. Retrieval Correctness Tests

Add focused tests proving the production adapter works.

At minimum:

### Schema adaptation
- production row maps correctly into common retrieval result
- stable production chunk identity preserved
- provenance fields preserved

### Vector contract
- query embedding dimension = 1024
- normalized query vector if required by frozen contract
- wrong dimension fails

### Index validation
- expected row count/schema accepted
- missing required field rejected
- wrong artifact identity rejected

### Retrieval
- top-k returns expected count
- scores/order deterministic on a small fixture
- no vectors exposed

### Dev/prod separation
- dev cache entries do not collide with production cache entries
- production mode never loads BGE silently

---

## 16. Integration Tests

Use mocks/small fixtures where possible.

Prove:

```text
POST /query
  ↓
production dense dependency
  ↓
ProductionDenseRetriever called
  ↓
retrieval-security/context/output pipeline unchanged
```

Do not call OpenRouter.

Inject a fake/local deterministic generation provider where needed.

Prove `/status` reports the production model/index identity.

Also prove startup fails safely when the production artifact contract is invalid.

---

## 17. Real Local Production Smoke

After unit/integration tests pass, run a local real-artifact smoke test using the actual production Qwen model + LanceDB index.

Use only safe hand-written non-protected queries.

Do NOT use protected TEST.

Suggested smoke checks:

```text
1 generic narrative SEC query
1 company-scoped query
1 company + year scoped query
1 query expected to return multiple chunks
```

Record:

```text
query embedding time
retrieval time
returned chunk IDs
returned CIK/year metadata
top scores/distances
```

Do not invoke paid generation.

Prefer direct retriever smoke first.

If the full `/query` path requires generation, use Ollama or a fake provider only.

---

## 18. Performance Snapshot

This is not Task 4.15's full performance benchmark.

But capture a small integration snapshot so we know the production retriever is usable.

Measure:

```text
model load time
index open time
first query latency
warm query latency
memory after model/index initialization
```

Do not make final production performance claims yet.

Full p50/p95/p99/concurrency belongs to Task 4.15.

---

## 19. UI / Architecture Update

If the project showcase UI exists, update the architecture/status presentation only after the production dense path is genuinely live.

Change:

```text
LIVE NOW
BGE dev index
162,357 rows
```

to:

```text
LIVE NOW
Qwen/Qwen3-Embedding-0.6B
10,487,096 rows
1024-d normalized vectors
```

Only do this after the real local service proves the new path is active.

Move the old BGE index to a historical/development label if still useful.

Do not update UI claims before runtime verification.

---

## 20. Documentation

Update:

```text
Progress.md
PROJECT_OVERVIEW.md
project_plan/PROJECT_EXECUTION.md
```

and any relevant readiness/architecture docs.

Document:

- why the dev retriever was incompatible
- production schema mapping
- production artifact identity
- live embedding model
- live index row count
- migration behavior
- cache invalidation behavior
- security compatibility
- remaining gaps

Do not rewrite frozen historical results.

---

## 21. Regression Commands

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Also run the new production-retriever-specific tests.

Do NOT:

- run `generation_api`
- make OpenRouter calls
- access AWS
- rebuild chunks
- rebuild embeddings
- rebuild production LanceDB
- open protected TEST

Protected TEST usage must remain:

```text
0/3
```

---

## 22. Acceptance Criteria

Gate A is complete only if:

```text
[ ] production Qwen query encoder used in live production mode
[ ] live dense retriever reads the 10,487,096-row production LanceDB artifact
[ ] production schema adapted explicitly
[ ] no dev-schema assumptions leak into production retrieval
[ ] query vector dimension verified at 1024
[ ] frozen query encoding convention verified from artifact/config
[ ] production artifact/schema validated at startup
[ ] no silent fallback to BGE
[ ] production results preserve provenance
[ ] exact retrieval cache remains compatible
[ ] dev/prod cache identities cannot collide
[ ] retrieval-security/context/output guards remain in path
[ ] `/status` truthfully reports Qwen + 10,487,096 live rows
[ ] real local production-index smoke passes
[ ] portable tests pass
[ ] non-generation tests pass
[ ] zero OpenRouter calls
[ ] zero AWS access
[ ] protected TEST remains 0/3
[ ] documentation updated
```

---

## 23. Final Report

At the end, show:

```text
BEFORE
- live embedding model
- live dense row count
- live retriever implementation

AFTER
- live embedding model
- live dense row count
- live retriever implementation
- production table/schema identity

ADAPTER
- dev schema
- production schema
- field mappings
- canonical chunk identity

CACHE
- confirmation dev/prod cache keys differ

SECURITY
- confirmation production retrieval still flows through retrieval security

SMOKE
- queries used
- top results
- first/warm retrieval timings
- memory snapshot

REGRESSION
- doctor
- portable
- non-generation pytest
- production-retriever-specific tests

SAFETY
- OpenRouter calls: 0
- AWS access: 0
- protected TEST usage: 0/3

GIT
- git status
- git diff --stat
```

Do not commit or push automatically.

Wait for explicit approval before committing.
