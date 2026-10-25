# Task 4.13 — Exact Retrieval Cache for the SEC RAG Serving Path

## Objective

Add a production-oriented **exact retrieval cache** to the current SEC RAG service so repeated dense-retrieval requests can skip redundant query embedding + LanceDB search when the retrieval inputs and retrieval artifact identity are unchanged.

This task is an optimization layer only.

It must **not** change retrieval semantics, routing decisions, safety behavior, citation behavior, generation behavior, frozen evaluation results, or protected TEST usage.

The cache must be safe against stale results when we later replace the current live development dense index with the frozen 10,487,096-row Qwen production index.

---

# 0. Read First / Preflight

Before changing anything, inspect the current repository and identify the real runtime path for:

- `POST /query`
- API dependency construction / startup
- dense retriever interface
- query embedding
- LanceDB lookup
- CRAG / relevance grading
- context construction
- context guardrails
- generation
- output/citation guards
- `/status`
- typed settings/config
- existing tests around retrieval and API startup

Also read:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- current Phase 4 readiness/deployment docs
- current UI architecture page if present
- the current live `/status` contract

Confirm before implementation:

1. current branch
2. working-tree state
3. current portable/non-generation test baseline
4. protected TEST usage remains `0/3`

Do not modify unrelated files.

---

# 1. Scope Decision — Exact Cache Only

Implement **exact retrieval caching**, not semantic caching.

Do NOT add a semantic-similarity cache in this task.

Reason:

- exact caching is deterministic and easy to invalidate correctly,
- semantic caching can return retrieval evidence for a merely similar query,
- semantic cache thresholds introduce a new quality/safety decision that would require its own evaluation task,
- we should not add that new scientific variable during a serving-optimization task.

Document semantic caching as a possible future experiment only.

---

# 2. Cache Boundary

Cache **retrieval results/evidence only**.

Do NOT cache:

- final LLM answers,
- generated text,
- final API responses,
- guardrail decisions,
- citation validation results,
- prompt text,
- structured safety output,
- OpenRouter responses.

The safe conceptual flow should become:

```text
Query
  ↓
Input Guardrails
  ↓
Route Decision
  ↓
Dense Retrieval Cache Lookup
  ├── HIT
  │     ↓
  │  Cached retrieval evidence
  │
  └── MISS
        ↓
     Query Embedding
        ↓
     LanceDB Search
        ↓
     Retrieval Evidence
        ↓
     Cache Store
        ↓
  downstream pipeline
```

After a hit or miss, the existing downstream path must continue normally.

In particular:

- provenance validation must still run,
- context guardrails must still run,
- generation must still run when the route requires it,
- citation validation must still run,
- output guardrails must still run.

If CRAG/relevance grading currently lives *outside* the retriever, it should continue to run on cached retrieval results each request.

If it is inseparable from the retriever contract, preserve the current contract exactly and include every relevant grading/config identity in the cache key.

Do not weaken safety to increase cache hit rate.

---

# 3. Architecture Pattern

Prefer a small wrapper/decorator around the current dense retriever rather than rewriting the retriever itself.

Recommended shape:

```text
DenseRetriever protocol/interface
        ↑
        |
ExistingRetriever
        |
CachedRetriever
        |
FastAPI dependencies
```

Suggested module:

```text
src/retrieval/cache.py
```

or the closest path consistent with the existing repository conventions.

The wrapper must expose the same retrieval contract expected by the rest of the system.

Do not force cache-specific logic into unrelated routing, generation, or guardrail modules.

---

# 4. Cache Backend

For this task, implement a **bounded in-process memory cache** using Python standard-library primitives.

Do NOT introduce Redis or another infrastructure dependency yet.

Requirements:

- bounded maximum number of entries,
- TTL expiration,
- LRU eviction,
- thread-safe access,
- deterministic cache keys,
- explicit cache statistics,
- explicit clear/reset operation for tests/maintenance,
- no raw-query logging,
- no secrets stored.

Use an implementation such as:

- `OrderedDict`
- `threading.RLock`
- monotonic time for TTL

or an equally simple standard-library design.

Do not add a third-party caching library unless the existing project already has one and there is a compelling reason.

Important deployment note:

This cache is **per Python process**.

Document that future multi-worker/ECS deployments will each have their own cache. A shared Redis/ElastiCache backend can be considered later if measurements justify it.

Do not add Redis now.

---

# 5. Recommended Defaults

Add typed configuration consistent with the existing settings system.

Recommended defaults:

```text
RETRIEVAL_CACHE_ENABLED=true
RETRIEVAL_CACHE_MAX_ENTRIES=512
RETRIEVAL_CACHE_TTL_SECONDS=900
RETRIEVAL_CACHE_SCHEMA_VERSION=v1
```

If the repository has a stronger existing naming/config convention, follow it.

Validate settings:

- max entries > 0
- TTL > 0
- schema version non-empty

Update `.env.example` with placeholders/defaults only.

Do not put secrets into tracked files.

---

# 6. Query Canonicalization

Exact cache identity should normalize only harmless formatting differences.

Recommended canonicalization:

1. require string input as normal,
2. Unicode normalize with NFC,
3. strip leading/trailing whitespace,
4. collapse runs of internal whitespace to a single space.

Do NOT:

- remove punctuation,
- stem,
- lowercase/casefold unless existing retrieval logic already guarantees case insensitivity,
- rewrite company names,
- rewrite years,
- rewrite financial metrics.

The cache must never merge two queries that may be semantically different.

Examples that MAY map to the same canonical query:

```text
"What was Apple's revenue in 2020?"
"  What   was Apple's revenue in 2020?  "
```

Examples that must remain different:

```text
"What was Apple's revenue in 2020?"
"What was Apple's revenue in 2021?"
```

---

# 7. Cache Key Contract

Do NOT use query text alone as the cache key.

Build a versioned deterministic identity over every input that can change retrieval output.

At minimum include:

```text
cache_schema_version
canonical_query
route / retriever kind
top_k / k
metadata filters / scope
embedding model identity
embedding model revision if available
embedding dimension if part of runtime identity
chunk config hash
dense index/table identity
dense index artifact identity / build hash / manifest hash if available
retrieval algorithm/version
similarity metric
relevant CRAG/retrieval threshold if it changes the cached contract
other retrieval knobs that affect returned evidence
```

Use canonical JSON with sorted keys or another deterministic encoding.

Hash the canonical identity using SHA-256.

The storage key should be the hash, not the raw query.

This is critical because when the service later switches from:

```text
LIVE NOW
BAAI/bge-small-en-v1.5
development index
162,357 rows
```

to the frozen production artifact:

```text
Qwen/Qwen3-Embedding-0.6B
1024 dimensions
10,487,096 rows
```

the cache identity must change automatically so stale development-index results cannot be served from cache.

Do not hardcode only the current dev artifact.

---

# 8. Cached Value Contract

Cache only the retrieval result needed by the existing downstream pipeline.

Preserve:

- ranking order,
- scores,
- chunk/document identifiers,
- source/provenance fields,
- metadata required by context construction,
- all fields required by existing retrieval consumers.

Do not cache embedding tensors unless the existing retrieval contract specifically requires them downstream.

Do not expose vectors to the API.

Avoid shared mutable state bugs.

On cache write/read, ensure callers cannot mutate the stored cache object and corrupt later hits.

Use immutable dataclasses/tuples where already available, or defensive copy/serialization consistent with current models.

---

# 9. What Is Cacheable

Cache successful dense retrieval executions.

A successful result may contain zero evidence if zero results is a valid normal retrieval outcome.

Do NOT cache:

- exceptions,
- model-loading failures,
- LanceDB failures,
- timeout failures,
- malformed retrieval output,
- dependency initialization failures.

Transient failures must be retried by the normal request path on the next request.

---

# 10. Statistics / Observability

Track at least:

```text
enabled
entries
max_entries
ttl_seconds
hits
misses
evictions
expirations
hit_rate
```

Optional if cleanly supported:

```text
stores
bypasses
```

Do not track or expose raw query strings.

Do not expose cached SEC text through `/status`.

Integrate a concise cache status into the existing `GET /status` response without breaking current fields.

Example concept:

```json
{
  "retrieval_cache": {
    "enabled": true,
    "backend": "memory_lru_ttl",
    "entries": 12,
    "max_entries": 512,
    "ttl_seconds": 900,
    "hits": 34,
    "misses": 18,
    "hit_rate": 0.6538
  }
}
```

Follow the project's existing Pydantic/API schema conventions.

---

# 11. Logging

Add safe structured cache events only if consistent with current logging conventions.

Allowed concepts:

```text
retrieval_cache_hit
retrieval_cache_miss
retrieval_cache_store
retrieval_cache_evict
retrieval_cache_expire
```

Do not log:

- raw user query,
- full cached evidence,
- vectors,
- prompts,
- API keys,
- PII values.

If a cache key needs to be logged for debugging, log only a short prefix of the SHA-256 digest.

---

# 12. API / Dependency Wiring

Wire the cache at service startup through the existing dependency builder.

Conceptually:

```text
base_dense_retriever = ...
if settings.retrieval_cache_enabled:
    dense_retriever = CachedRetriever(base_dense_retriever, cache, identity_provider)
else:
    dense_retriever = base_dense_retriever
```

Do not duplicate model/index loading.

Do not initialize a second embedding model or second LanceDB table merely for caching.

A cache hit must skip the expensive dense retrieval work.

The rest of the request path must remain unchanged.

---

# 13. Structured XBRL Route

Do NOT change the deterministic XBRL query semantics in this task.

Primary scope is the dense retrieval path.

If the current architecture makes it trivial to place the same exact-cache abstraction around XBRL safely, document the option but do not expand scope without a strong reason.

Structured XBRL caching can be a separate follow-up task because:

- DuckDB queries are already deterministic and relatively inexpensive,
- invalidation identity differs from the dense index,
- mixing the two in one first implementation increases risk.

---

# 14. UI / Architecture Update

If the local project showcase UI from Task 4.12 exists, update only the architecture/status presentation needed to reflect the new cache.

In the dense route show:

```text
Route Decision
   ↓
Exact Retrieval Cache
   ├── HIT ─────────────► Cached Candidate Evidence
   │
   └── MISS
          ↓
     Query Embedding
          ↓
     LanceDB Search
          ↓
     Candidate Evidence
          ↓
       Cache Store
```

Status:

```text
Retrieval Cache
LIVE
Exact-query LRU + TTL
In-process
```

Do not label it as semantic cache.

Do not imply it is shared across processes.

Do not imply it fixes the existing production dense-index integration gap.

The UI must continue to show truthfully:

```text
live dense index:
BAAI/bge-small-en-v1.5
162,357 rows

production artifact:
Qwen/Qwen3-Embedding-0.6B
10,487,096 rows
integration pending
```

---

# 15. Tests — Unit

Add focused deterministic tests.

At minimum prove:

### Basic hit/miss

1. first query = miss
2. underlying retriever called once
3. same query again = hit
4. underlying retriever call count remains one
5. results are identical

### Canonical whitespace

Queries differing only by harmless whitespace normalization should hit the same entry.

### Retrieval parameter isolation

Different `k/top_k` values must not collide.

### Filter isolation

Different metadata/company/year/form filters must not collide.

### Artifact isolation

Two otherwise identical queries with different index/model/config identity must not collide.

This is critical for the future BGE → Qwen production migration.

### TTL expiration

Use an injectable/test clock if practical.

Do not write sleep-heavy tests.

After TTL expiry:

- entry is treated as miss,
- retrieval runs again,
- expiration count increments.

### LRU eviction

With a small test capacity:

- oldest least-recently-used entry is evicted,
- recently accessed entry survives,
- eviction counter is correct.

### Disabled mode

When cache is disabled:

- every call reaches underlying retriever,
- behavior/result remains unchanged.

### Exceptions

Underlying retrieval exception must not create a cache entry.

### Empty valid result

A valid empty retrieval response may be cached if it is a normal successful result.

### Mutation isolation

Mutating one returned result must not mutate the cached value seen by later callers.

### Thread safety

Add a focused concurrency test if practical with the chosen implementation.

Do not make it flaky.

---

# 16. Tests — Integration

Add an integration test through the real dependency wiring using mocks/fakes for expensive external pieces.

Prove:

```text
request 1
  cache miss
  dense retrieval invoked

request 2, same retrieval identity
  cache hit
  dense retrieval not invoked again
```

But still prove downstream processing runs normally.

Do not make OpenRouter calls.

If the query path requires a generation provider in the test, inject a deterministic fake/local provider.

Do not run `generation_api`.

---

# 17. Local Performance Smoke

Add a small non-protected cache benchmark or smoke script using safe hand-written queries.

No protected TEST.

No paid API calls.

Prefer testing the retriever/cache directly rather than full generation.

Measure:

- cold retrieval latency
- warm cache-hit latency
- observed speedup
- hit/miss counts

Use the current live local dense index.

Do not set a fake performance claim in advance.

Report measured values only.

A cache hit should not perform query embedding or LanceDB search.

If instrumentation can prove those calls were skipped, record that.

---

# 18. Correctness Gate

For a fixed set of non-protected development queries:

Compare cache-disabled vs cache-enabled retrieval output.

Require exact equality for the retrieval contract used downstream:

- same number of results
- same ordering
- same identifiers
- same scores within the project's existing deterministic tolerance
- same metadata/provenance

The cache is allowed to improve latency only.

It is not allowed to change answer/retrieval quality.

---

# 19. Regression Commands

Run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Also run the new cache-specific tests explicitly.

Do NOT run paid generation tests.

Do NOT access AWS.

Do NOT rebuild full-corpus chunks, embeddings, or indexes.

Do NOT open protected TEST.

Protected TEST usage must remain:

```text
0/3
```

---

# 20. Documentation

Update the appropriate project docs.

At minimum:

```text
Progress.md
project_plan/PROJECT_EXECUTION.md
```

and any architecture/readiness document that now needs the cache layer recorded.

Document:

- why exact cache was chosen,
- why semantic cache is deferred,
- cache boundary,
- key identity/invalidation strategy,
- current backend = per-process in-memory LRU+TTL,
- configuration,
- measured local cache performance,
- limitations,
- future shared-cache option.

Do not rewrite frozen historical Phase 1–3 results.

Do not present caching as a scientific retrieval improvement.

It is a serving/runtime optimization.

---

# 21. Important Non-Goals

Do NOT:

- implement semantic retrieval caching,
- cache final generated answers,
- add Redis,
- add AWS ElastiCache,
- change embedding model,
- change chunking,
- change LanceDB index content,
- change retrieval ranking,
- change CRAG threshold,
- change router behavior,
- change guardrails,
- change citation semantics,
- change generation provider,
- touch frozen evaluation artifacts,
- use protected TEST,
- make OpenRouter calls,
- access AWS.

---

# 22. Acceptance Criteria

Task is complete only if all are true:

```text
[ ] exact dense retrieval cache implemented
[ ] bounded LRU behavior
[ ] TTL expiration
[ ] thread-safe
[ ] config-driven enable/max-size/TTL/schema-version
[ ] safe deterministic cache identity
[ ] cache key includes retrieval artifact/config identity
[ ] future dev-index -> production-index migration cannot reuse stale entries
[ ] cache hit skips dense embedding/search
[ ] downstream safety/generation/citation pipeline still executes
[ ] failures are not cached
[ ] no raw query in status/logging
[ ] cache metrics visible in /status
[ ] cache-disabled behavior remains unchanged
[ ] cached and uncached retrieval results are equivalent
[ ] unit tests pass
[ ] integration tests pass
[ ] portable suite passes
[ ] non-generation suite passes
[ ] zero paid API calls
[ ] zero AWS access
[ ] protected TEST remains 0/3
[ ] docs updated
[ ] architecture UI updated if present
```

---

# 23. Final Report

At the end, show:

```text
CACHE DESIGN
- backend
- max entries
- TTL
- canonicalization rules
- key components
- cached value contract

INTEGRATION
- files created
- files modified
- exact cache insertion point
- /status changes

CORRECTNESS
- cache-enabled vs disabled equivalence result
- failure/expiration/eviction behavior

PERFORMANCE
- cold retrieval latency
- warm cache-hit latency
- measured speedup
- cache hit/miss counts

REGRESSION
- doctor result
- portable result
- non-generation pytest result
- cache-specific test result

SAFETY
- OpenRouter calls: 0
- AWS access: 0
- protected TEST usage: 0/3

GIT
- git status
- git diff --stat
```

Do NOT commit or push automatically.

Wait for explicit approval before committing.
