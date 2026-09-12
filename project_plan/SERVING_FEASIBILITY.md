# Serving Feasibility Spike

Phase 0, Task 0.10 (`project_plan/PROJECT_EXECUTION.md`, "### 0.10 Serving
feasibility spike"). Produced by `scripts/serving_spike.py` — throwaway
benchmark code, not a production pipeline component.

## Question

Is the provisional retrieval-serving architecture (bge-small embeddings +
LanceDB + MiniLM cross-encoder reranking) plausibly compatible with a
serverless (Lambda-shaped, CPU-only) serving target, or should the project
plan around a continuously running service (Fargate) instead?

## Scope

Representative architecture experiment, not a production benchmark and not
a relevance-quality evaluation. Answers a latency/feasibility question only.

## Benchmark Stack

| Component | Value |
|---|---|
| Corpus | ~100,000 chunks (EDGAR-CORPUS) |
| Chunk size | 512 tokens, no overlap |
| Embedding model | `BAAI/bge-small-en-v1.5` (384-dim, verified not assumed) |
| Vector store | LanceDB 0.37.1 — flat (brute-force) and `IVF_PQ` (100 partitions, 48 sub-vectors, 8 bits) |
| Retrieval depth | top-50 |
| Reranker | `Xenova/ms-marco-MiniLM-L-6-v2`, ONNX Runtime 1.29.0, INT8 (pre-quantized), `CPUExecutionProvider` |
| CPU threads | 2 (`torch.set_num_threads` + ONNX `intra_op_num_threads`, documented small-Lambda-like allocation, not tuned further) |
| Query count | 180 measured (+10 warm-up), 2 reproducibility passes |
| Cold samples | 10 fresh subprocesses |

Provisional components — **not** final Phase 3 selections. Config is
recorded verbatim, and traceable via `spike_config_hash`, in
`configs/serving_spike.json` and `results/phase_0_10_serving_spike.json`.

## Corpus

100,000 chunks were selected deterministically (`ORDER BY hash(filename)`)
from `data/edgar_corpus/*.parquet` sections `section_1, section_1A, section_7,
section_7A, section_8`, spanning 2,504 unique filings. Mean token count
485.0, p50 512 (chunk-length cap), p95 512. This is the **DISPOSABLE
SERVING-SPIKE CORPUS** — explicitly not the Phase 1 development corpus, and
`data/` was only read, never modified.

## Hardware / Runtime

| Field | Value |
|---|---|
| OS | Windows-10-10.0.26200-SP0 |
| Python | 3.11.9 |
| CPU | AMD64 Family 25 Model 97 Stepping 2 (AuthenticAMD), 32 logical CPUs |
| System RAM | 33.3 GB |
| GPU | NVIDIA GeForce RTX 5060 Laptop GPU, 8.55 GB VRAM |
| PyTorch | 2.13.0+cu130 (`torch.version.cuda` 13.0) |
| LanceDB | 0.37.1 |
| sentence-transformers | 6.0.0 |
| ONNX Runtime | 1.29.0 |

Corpus embeddings were built on GPU (offline preparation step, explicitly
**not** the serving latency path — see Embedding Build note below). All
serving-latency measurement (warm and cold) ran on CPU only, per Step 3.

## Methodology

- **Warm-up**: 10 unmeasured queries before sampling (models/index already
  loaded).
- **Warm measurement**: 180 measured queries per pass, 2 passes for
  reproducibility (see Results — Reproducibility below).
- **Cold measurement**: 10 independent fresh-process samples, each spawned
  via `subprocess` running `serving_spike.py --cold-run`, timing process
  start → imports → model init → LanceDB open → first query.
- **Component timing**: `time.perf_counter()` around each stage inside
  `run_single_query()`; serialization/logging excluded from timed intervals.
- **Memory**: `psutil` RSS at baseline, after imports, after LanceDB open,
  after embedding-model load, after reranker load, after one query, and
  peak during the warm benchmark.
- **CPU constraint**: `CPU_THREADS = 2` applied to both PyTorch and ONNX
  Runtime intra-op threads for the primary (warm/cold) benchmark, to avoid
  an unconstrained 32-core laptop silently inflating the result.

## Results

### Component timing (ms, warm, pass 1, n=170)

| Component | p50 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|
| Query embedding (CPU) | 20.2 | 27.1 | 32.2 | 39.9 |
| Vector retrieval (flat) | 101.1 | 152.5 | 171.4 | 199.2 |
| Vector retrieval (quantized) | 10.0 | 21.2 | 28.6 | 39.8 |
| Reranking (ONNX INT8, top-50) | 2801.7 | 3399.3 | 3830.2 | 3961.1 |

### End-to-end path timing (ms, warm, pass 1, n=170)

| Path | p50 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|
| Vector-only (flat) | 120.2 | 184.4 | 205.5 | 231.1 |
| Vector-only (quantized) | 30.4 | 50.6 | 56.7 | 74.6 |
| Vector + rerank | 2939.4 | 3545.5 | **4014.2** | 4138.4 |

### Reproducibility (pass 2 vs pass 1)

| Path | Pass 1 p95 | Pass 2 p95 | Delta |
|---|---:|---:|---:|
| Vector-only (flat) | 205.5 ms | 209.3 ms | +1.9% |
| Vector + rerank | 4014.2 ms | 4544.0 ms | +13.2% |

The vector+rerank delta between passes is larger than ideal for a
controlled benchmark. It is consistent with the documented laptop
thermal/background-load caveat (Step 46) rather than a measurement bug —
component-level timing (embedding, retrieval) stayed stable between passes;
only the CPU-bound reranker pass showed drift, which is expected of a
2-thread-constrained ONNX workload sharing a 32-core consumer laptop with
background processes. It does not change the decision: both passes are
well above every relevant threshold.

### Process-cold proxy (10 subprocess samples)

| Stat | Value |
|---|---:|
| p50 | 14.26 s |
| p90 | 14.99 s |
| p95 | 18.65 s |
| min / max | 14.07 s / 18.65 s |

**Local process-cold proxy — not a real AWS Lambda cold start.** No
container init, no cold ENI/VPC attach, no Lambda runtime bootstrap; OS
filesystem page cache may also remain warm across subprocesses on this
machine. Real Lambda cold starts could be faster (smaller, purpose-built
container) or slower (network-attached storage, cold ENI) than this proxy.

### Memory (RSS, MB)

| Stage | RSS |
|---|---:|
| Baseline | 2897.8 |
| After imports | 2897.9 |
| After LanceDB open | 2900.3 |
| After embedding model load | 2939.5 |
| After reranker load | 2975.2 |
| After one query | 5052.2 |
| Peak during warm benchmark | 7347.1 |

Cloud memory-tier scaling (distinct Lambda 1/2/4 GB allocations) was **not**
reproduced — Docker Desktop is installed on this machine but its daemon was
not running, and starting it was out of scope for this benchmark (Step 26).
Only single-configuration process RSS was measured; this is a documented
gap, not a fabricated tier result.

### Artifact sizes

| Artifact | Size |
|---|---:|
| LanceDB flat index | 287.6 MB |
| LanceDB quantized (`IVF_PQ`) index | 292.9 MB |
| Reranker ONNX INT8 model | 23.0 MB |

`.venv` size is **not** reported as a deployment package estimate — it is a
CUDA development environment (includes GPU-specific PyTorch packages) and
is not representative of a CPU serving package (Step 25).

### Embedding build (offline preparation, not serving latency)

100,000 chunks embedded on GPU in 1197.4 s (peak VRAM 2656.7 MB). This is a
one-time offline corpus-preparation cost and is explicitly excluded from
the serving-latency numbers above.

## Decision Thresholds

From `project_plan/PROJECT_EXECUTION.md`, "### 0.10 Serving feasibility
spike" (frozen, applied without modification after seeing results):

| Warm p95 | Action |
|---|---|
| < 500 ms | Proceed with the serverless design |
| 500 ms – 2 s | Proceed, but constrain reranker size and candidate pool in Phase 3 |
| > 2 s | Change serving target to warm compute; revisit Phase 3 assumptions |

Also: if process-cold alone exceeds 10 s, the serverless target is
unsuitable regardless of warm performance.

## Decision

**Fargate / continuously warm service preferred as the Phase 4 default
serving target.**

Measured evidence:

- Warm p95 (vector + rerank) = **4014.2 ms** (pass 1) / 4544.0 ms (pass 2)
  — both **> 2 s**, triggering "change serving target to warm compute."
- Process-cold p95 = **18.65 s** — **> 10 s**, independently disqualifying
  a serverless (Lambda) target regardless of warm performance.
- Both thresholds point the same direction; the decision does not depend
  on a marginal call.

The dominant cost is CPU-bound ONNX reranking of 50 candidates at up to 512
tokens each under a 2-thread constraint (p50 ≈ 2.8 s of the ≈2.9-3.9 s
total path) — not query embedding (p50 20 ms) or vector search (p50 10-101
ms depending on index type). This means the architecture question is really
about the reranker's CPU cost under a small-instance thread budget, and
Phase 3 candidate-pool/reranker-size choices materially affect whether this
picture could later change — but as measured now, on the provisional stack,
Lambda is not a viable default.

This decision means "default deployment direction for later engineering,"
not "production environment already built." Task 0.10 deployed nothing;
Phase 4 still owns actual deployment (Step 33).

## Limitations

- 100,000 chunks — a representative subset, not the full ~14M-chunk
  projected production corpus.
- Local process-cold proxy, **not** a real AWS Lambda cold start (no
  container init, no cold ENI/VPC attach, no Lambda runtime bootstrap; OS
  filesystem page cache may remain warm across subprocesses on this
  machine).
- No generation/LLM latency included — retrieval/reranking serving path
  only (Step 28).
- No relevance-quality evaluation performed or claimed — Phase 2
  establishes trustworthy measurement, Phase 3 does scientific ablations
  (Step 29).
- Provisional components (bge-small, MiniLM, 512-token/no-overlap
  chunking, top-50) — not final Phase 3 selections.
- Cloud memory-tier scaling (e.g. distinct Lambda 1 GB/2 GB/4 GB
  allocations) was **not** reproduced — Docker Desktop is installed on this
  machine but its daemon was not running, and starting it was out of scope
  for this benchmark; only single-configuration process RSS was measured.
- Single development machine, single measurement session — laptop
  thermal/background-load variance is possible (observed directly in the
  pass-1-vs-pass-2 rerank delta above).
- `PROJECT_EXECUTION.md`'s Task 0.10 checklist also lists "deploy a minimal
  retrieval function to the candidate serving target" and "repeat with and
  without binary quantization" and "repeat across plausible memory
  allocations." These were **not** performed as literally stated: no actual
  cloud deployment occurred (the local process-cold proxy substitutes for
  it, per Step 22/23); the quantization comparison performed is flat vs.
  LanceDB `IVF_PQ` (product quantization), not binary quantization
  specifically, since `IVF_PQ` is the simplest defensible LanceDB ANN
  configuration and the plan did not name an exact quantization scheme
  (Step 11); and memory-tier repetition was skipped per the Step 26 WARN
  fallback (Docker unavailable) rather than fabricated. This is recorded as
  a discrepancy per the standing instruction to record rather than silently
  resolve conflicts with `PROJECT_EXECUTION.md`.

## Phase 3 Re-check

Task 3.14 (`scripts/run_phase3_serving_recheck.py`,
`results/phase_3_14_serving_recheck.json`). Re-measured CPU-only warm
latency for the ACTUAL Phase 3 selected stack, using this spike's own
`CPU_THREADS=2`/warm-up/measurement convention so the numbers are
directly comparable to the decision thresholds above.

### What actually got selected (materially different from this spike's placeholders)

| Component | This spike (Task 0.10) | Phase 3 selection |
|---|---|---|
| Embedding | `bge-small-en-v1.5` (384-dim, small) | `Qwen/Qwen3-Embedding-0.6B` (1024-dim, ~1.19 GB model — Task 3.3 winner) |
| Retrieval | vector-only / vector+rerank | dense-only (Task 3.5's RRF hybrid was a **negative result**) |
| Reranker | MiniLM ONNX INT8 (dominant cost, 2.8s p50) | **none** — Task 3.6's cross-encoder reranking was a **negative result**, `no_rerank` selected |
| Corpus | 100,000 chunks | 323,971 chunks (full frozen Task 3.2 corpus) |
| Quantization | flat vs. `IVF_PQ` compared | **none applied** — flat/exact search throughout Phase 3 (`src.index.lancedb_index.exact_cosine_search`); this is an honest gap, not a fabricated selection |

### Results (CPU-only, `CPU_THREADS=2`, 79 measured queries + 10 warm-up, frozen 89-question DEV scope)

| Stage | p50 (ms) | p95 (ms) |
|---|---:|---:|
| Query embedding (CPU, Qwen3-Embedding-0.6B) | 505.0 | 594.7 |
| Vector retrieval (flat, 323,971 rows, 1024-dim) | 554.7 | 589.3 |
| **End-to-end (dense-only, no rerank)** | **1065.2** | **1163.0** |

Frozen production index size: 1.464 GiB (1,572,353,043 bytes) — up from
this spike's 287.6 MB, driven by ~3.2x more chunks and ~2.7x the vector
dimensionality, with no quantization applied to offset it.

### Re-checked decision

Applying this document's own frozen thresholds to the new warm p95
(1163.0 ms): **500 ms – 2 s → "proceed, but constrain reranker size and
candidate pool."** This is an improvement over Task 0.10's original
verdict (warm p95 was 4014.2 ms, `> 2 s`) — entirely because the
dominant cost driver identified in Task 0.10 (CPU-bound cross-encoder
reranking) is **absent from the real selected pipeline**: Task 3.6
found reranking credibly regressed quality on this corpus, so
`no_rerank` was selected, which incidentally also removes the single
largest latency cost the original spike measured. The "constrain
reranker size" instruction is therefore already trivially satisfied
(reranker size = zero).

However, this does **not** overturn the overall Fargate-preferred
recommendation. Task 0.10's serverless disqualification had two
independent legs — warm p95 `> 2 s` **and** process-cold p95 (18.65 s)
`> 10 s` — and only the first is resolved here. Cold start was not
re-measured (a new cold-start benchmark was out of scope for this
re-check), but Qwen3-Embedding-0.6B's on-disk weights (~1.19 GB) are
roughly 9x larger than bge-small's, so process-cold latency can only be
expected to be worse, not better, than the spike's already-disqualifying
18.65 s figure. **Fargate / continuously warm service remains the
recommended Phase 4 default serving target**, now for the narrower and
more clearly-scoped reason of cold-start cost alone rather than warm
reranking cost.

### Limitations of this re-check

- Cold start was not re-measured (reasoned about via model-size
  comparison instead, see above).
- No quantized index exists to re-measure — Phase 3 never explored
  quantization; this is a documented gap against Task 3.14's "after the
  selected quantization" wording, not something to fabricate a
  selection for.
- No cloud memory-tier repetition, matching Task 0.10's own
  Docker-unavailable gap.
- Single-machine, single-session CPU measurement (2-thread-constrained,
  but still a development laptop, not real Lambda/Fargate CPU) — same
  caveat as Task 0.10's own numbers.

Task 0.10 does not permanently freeze performance or the serving decision
— Phase 4 should re-verify cold-start behavior directly on the actual
target compute once real deployment work begins, rather than relying on
this re-check's size-based reasoning indefinitely.
