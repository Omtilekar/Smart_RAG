# Phase 1 Baseline Retriever

**Phase 1 baseline retrieval contract.** Established in Task 1.6. Composes
Task 1.4's BGE query encoder with Task 1.5's exact-cosine LanceDB search
into the first natural-language retrieval path. Vector-only — no BM25, no
hybrid search, no reranking, no CRAG, no routing, and no generation. Task
1.7 owns generation.

## Purpose

```text
question
  → Task 1.4 BGE query encoder (query convention, not passage convention)
  → normalized 384-d float32 vector
  → Task 1.5 exact cosine LanceDB search ("chunks" table)
  → ranked chunk results
```

The retriever works independently of generation and returns full
provenance for every result, so Task 1.8's citation-integrity check needs
no external join.

## Frozen user decisions

Four decisions arrived pre-approved with this task (no repository
contradiction found, so accepted as given — see `Progress.md`'s Task 1.5
entry for the general policy on this):

| Decision | Value |
|---|---|
| Default `k` | `5`, caller-configurable, must be a positive `int` |
| Distance and score | Both returned: `distance` = raw LanceDB `_distance` (lower better); `score = 1.0 - distance` (higher better), never clamped, never rounded internally |
| Result contents | `rank`, `score`, `distance`, plus all 16 Task 1.5 metadata columns — `vector` never included |

## Query Pipeline

```python
from src.retrieval.baseline import BaselineRetriever

retriever = BaselineRetriever(model, table)  # both loaded/opened once, reused across calls
results = retriever.retrieve("What was total revenue?", k=5)
```

- `encode_fn`/`search_fn` default to `src.embeddings.bge.encode_queries` and
  `src.index.lancedb_index.exact_cosine_search` respectively, but are
  constructor-injectable — no DI framework, just optional callables — so
  portable unit tests never need a real model or LanceDB table.
- The query path (`encode_queries`) is used exactly once per `retrieve()`
  call, never the passage path (`encode_passages`).
- A `BaselineRetriever` instance reuses its model and table handle across
  calls — no reload/reopen per call.

## Query contract (reused exactly from Task 1.4/1.5 — nothing new invented)

```text
query convention:      "Represent this sentence for searching relevant passages: "
                       prepended exactly once (src.embeddings.bge.QUERY_INSTRUCTION)
model:                    BAAI/bge-small-en-v1.5
revision:                   5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
dimension:                    384
dtype:                          float32
normalize_embeddings:              True
device:                              cuda
offline:                               HF_HUB_OFFLINE=1 + local_files_only=True
                                    + per-file cache precheck (Task 1.4's
                                    existing load_model())
```

**Long-query behavior** (Task 1.6 Step 24): `bge.py` defines no explicit
truncation of its own — the behavior is inherited entirely from
sentence-transformers' default `SentenceTransformer.encode()`, which
truncates internally at the model's `max_seq_length` (verified: `512`).
A synthetic 2000+-token query was tested and returned a valid `(1, 384)`
finite vector with no error — confirming this pre-existing, unmodified
Task 1.4 behavior rather than introducing a new truncation policy. Not
altered by this task.

## Search contract (reused exactly from Task 1.5)

```text
backend:          LanceDB 0.37.1
table:               chunks
mode:                  exact (no ANN index)
metric:                  cosine, via .distance_type("cosine")
distance field:            _distance (LanceDB's own name)
rank semantics:               LanceDB's own result order, exposed as
                            1-based `rank` (1, 2, ..., k) — no independent
                            rank convention exists elsewhere in the repo
k > table rows:                 not exercised (table has 162,357 rows; every
                            k value tested, 5 and 10, is far below that) —
                            no project-defined behavior for k > row count
                            exists or was needed here
```

## Result schema

```python
@dataclass(frozen=True)
class RetrievalResult:
    rank: int
    score: float
    distance: float
    chunk_id: str
    document_id: str
    text: str
    cik: int
    company: str
    form_type: str
    fiscal_year: int
    source: str
    source_filename: str
    source_split: str
    ordinal: int
    token_count: int
    chunk_config_hash: str
    normalizer_version: str
    normalization_build_sha256: str
    development_manifest_sha256: str
```

`vector` is never present. The internal LanceDB column name `_distance` is
never exposed directly — only the cleanly-named `distance` field (holding
the exact same value, never renamed to imply a different metric).

## Validation

```text
default k=5:               PASS (5 results)
k=10:                          PASS (10 results)
invalid k (0, negative,
  non-int, bool):                  PASS - all rejected (TypeError/ValueError,
                                 never silently coerced)
empty/whitespace question:            PASS - rejected
non-string question:                    PASS - rejected
score = 1 - distance,
  never clamped:                          PASS - regression-tested including
                                       a negative-distance case
                                       (distance=-1e-7 -> score=1.0000001,
                                       not clamped to 1.0)
rank starts at 1, sequential:              PASS
result order preserved from search:            PASS
vector omitted:                                  PASS
approved metadata returned:                        PASS (exact field-set
                                                 comparison)
Unicode query:                                        PASS
real-corpus smoke (6 questions):                         PASS - all 5-result,
                                                       provenance intact
determinism (repeated query,
  same k):                                                PASS - identical
                                                       chunk IDs, identical
                                                       order, max score
                                                       diff 0.00e+00 across
                                                       two calls
```

### Real smoke results (concise, not a relevance claim)

| Question (truncated) | Top chunk_id | Company (FY) | Score |
|---|---|---|---:|
| What was the company's total revenue? | `1158114_2016.htm::chunk106` | APPLIED OPTOELECTRONICS, INC. (2016) | 0.7573 |
| What are the main risk factors described... | `1425627_2018.htm::chunk9` | TRANSBIOTEC, INC. (2018) | 0.8144 |
| What was net income for the fiscal year? | `764038_2016.htm::chunk69` | SOUTH STATE CORP (2016) | 0.7757 |
| How much did the company spend on R&D? | `1566373_2020.htm::chunk226` | F-STAR THERAPEUTICS, INC. (2020) | 0.7659 |
| What is the company's total outstanding debt? | `898174_2020.htm::chunk160` | REINSURANCE GROUP OF AMERICA INC (2020) | 0.7611 |
| Did the company pay dividends to shareholders? | `857737_2018.htm::chunk52` | ICONIX BRAND GROUP, INC. (2018) | 0.8062 |

These are smoke questions confirming the pipeline returns *something*
topically plausible end-to-end — not a trusted relevance evaluation. Task
1.9's ~200-question smoke eval and Phase 2's truth-contract-backed set are
the actual measurement instruments.

## Performance

```text
Phase 1 smoke diagnostic - NOT a production benchmark

query count:              30 (after 3 unmeasured warm-up queries)
k:                            5
query embedding:                 p50 ~9.9 ms
exact search:                        p50 ~120.6 ms
total retrieve:                          p50 ~131.8 ms, p95 ~139.4 ms
```

Consistent with Task 1.5's own standalone search diagnostic (~143-165 ms
p50/p95 at the same `k=5`) — the additional ~10 ms is query embedding,
everything else is the exact brute-force cosine scan over 162,357 vectors.

## Known limitations

- Vector-only — no BM25/FTS, no hybrid retrieval.
- Exact scan — inherits Task 1.5's ANN-free search, so latency will not
  scale to a full production corpus without an indexing decision (Phase
  3/4, not here).
- No reranker.
- No metadata pre-filtering (CIK/year/form scoping) — every query searches
  the full 162,357-row table.
- No CRAG confidence grading, no router.
- No generation — Task 1.7 owns turning these results into an answer.
- No relevance evaluation — the smoke questions above demonstrate
  integration correctness, not retrieval quality. That begins in Task 1.9+
  and is only trustworthy starting Phase 2.

## Next consumer

Task 1.7 (Minimal Generation Layer) sends the top-5 `RetrievalResult.text`
values plus a minimal prompt to a generation model and returns a cited
answer.

## Reproducing this smoke run

```bash
python scripts/smoke_retrieval.py
```

Reads the Task 1.5 LanceDB index read-only, loads the model offline from
local cache, performs no network access, writes only
`results/phase_1_6_retriever_summary.json` (tracked). No new config file
was created — Task 1.5's existing config/summary already capture the
backend/table/metric semantics this task reuses unchanged, and no new
runtime parameter required its own config (Step 26).
