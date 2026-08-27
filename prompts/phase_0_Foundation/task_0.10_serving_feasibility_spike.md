# Task 0.10 — Serving Feasibility Spike

You are working inside my SEC RAG repository.

We are executing:

```text
Phase 0 — Build the System Foundation
Task 0.10 — Serving Feasibility Spike
```

Current Phase 0 status:

```text
0.0 Git Safety Preflight        — COMPLETE
0.1 Python Environment          — COMPLETE
0.2 CUDA/GPU Validation         — COMPLETE
0.3 Repository Structure        — COMPLETE
0.4 Dependency Management       — COMPLETE
0.5 Configuration System        — COMPLETE
0.6 Logging                     — COMPLETE
0.7 Storage Abstraction         — COMPLETE
0.8 Basic Automated Tests       — COMPLETE
0.9 Developer Commands          — COMPLETE
0.10 Serving Feasibility Spike  — CURRENT
```

Task 0.9 deliberately did NOT mark Phase 0 complete because the current
`project_plan/PROJECT_EXECUTION.md` still contains Task 0.10 and serving
latency / serving-target exit criteria.

This task resolves those remaining Phase 0 questions.

---

# AUTHORITATIVE SOURCE

Before doing anything else, read the actual current:

```text
project_plan/PROJECT_EXECUTION.md
```

Locate:

```text
Phase 0
Task 0.10 — Serving feasibility spike
Phase 0 exit criteria
the serving decision-threshold table
```

Treat that text as authoritative.

This prompt summarizes the intended experiment, but if exact numerical
details or component names differ from the current `PROJECT_EXECUTION.md`,
follow `PROJECT_EXECUTION.md` and record the discrepancy.

Do NOT silently invent or reinterpret requirements.

---

# PURPOSE

The purpose of this task is to answer an architecture question early:

> Is the planned retrieval-serving stack plausibly compatible with a
> serverless / lightweight production serving target, or should the project
> plan around a continuously running service such as Fargate instead?

This task is NOT intended to prove production latency.

It is intended to replace estimates with measurements early enough that the
deployment architecture can still change cheaply.

---

# EXPECTED PROVISIONAL STACK

Verify against the current execution plan before implementing.

The expected Phase 0.10 representative stack is approximately:

```text
representative corpus:   ~100,000 chunks
chunk size:              512 tokens
embedding model:         BAAI/bge-small-en-v1.5
vector store:            LanceDB
retrieval depth:         top 50
reranker:                MiniLM cross-encoder
reranker runtime:        ONNX / INT8 where specified by the plan
```

These are **provisional serving-spike components**.

They do NOT mean:

```text
final chunk size selected
final embedding model selected
final reranker selected
final LanceDB index configuration selected
```

Those decisions belong primarily to Phase 3.

---

# HARD SCOPE BOUNDARY

Do NOT begin Phase 1.

In particular, do NOT implement production versions of:

```text
src/normalize/*
src/chunk/*
src/embeddings/*
src/index/*
src/retrieval/*
src/generation/*
```

The serving spike may contain benchmark-specific code under:

```text
scripts/
```

but that code must be clearly labeled:

```text
FEASIBILITY / BENCHMARK CODE
NOT PRODUCTION PIPELINE IMPLEMENTATION
```

Do not quietly turn Task 0.10 into Phase 1.

---

# PRIMARY OUTPUTS

The preferred tracked outputs are:

```text
scripts/serving_spike.py
configs/serving_spike.json
results/phase_0_10_serving_spike.json
project_plan/SERVING_FEASIBILITY.md
Progress.md
```

Potentially also:

```text
tests/test_serving_spike.py
```

for small deterministic helper tests.

Large generated benchmark artifacts must live under:

```text
artifacts/serving_spike/
```

and remain Git-ignored.

Do not place an index under:

```text
results/
```

or:

```text
data/
```

---

# STEP 1 — VERIFY PHASE 0 FOUNDATION

Activate:

```text
.venv/
```

Run:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Then verify:

```bash
python scripts/dev.py data
```

Expected on this machine:

```text
environment: PASS
portable tests: PASS
local frozen data: AVAILABLE
```

If the existing Phase 0 foundation is broken before the spike begins:

stop.

Do not benchmark on top of a broken environment.

---

# STEP 2 — RECORD HARDWARE / SOFTWARE CONTEXT

Record enough context to make benchmark results interpretable.

At minimum:

```text
OS
Python version
CPU model
physical/logical CPU count
system RAM
GPU model
GPU VRAM
PyTorch version
torch.version.cuda
LanceDB version
sentence-transformers version
ONNX Runtime version if used
reranker model/version
```

Do not record:

```text
personal username
personal home-directory path
machine serial number
```

Use sanitized machine information in tracked results.

---

# STEP 3 — DETERMINE SERVING EXECUTION MODE

The serving feasibility question is primarily about:

```text
Lambda / CPU serverless
versus
Fargate / continuously warm service
```

Therefore the authoritative benchmark path should be:

```text
CPU serving
```

unless the current execution plan explicitly says otherwise.

Do NOT use the RTX 5060 result as the primary serverless latency number.

The GPU remains useful for building embeddings quickly, but:

```text
retrieval-serving benchmark latency
```

must reflect the intended production serving environment.

If you use GPU for corpus embedding/index construction to save time:

document that separately.

Do not mix GPU build time with CPU serving latency.

---

# STEP 4 — BUILD A REPRESENTATIVE CORPUS

Create approximately:

```text
100,000 chunks
```

using the existing frozen SEC corpus.

Prefer:

```text
EDGAR-CORPUS
```

because it resembles the narrative retrieval workload.

Do NOT alter:

```text
data/
```

Read from it only.

Do NOT execute Phase 1.1's 1,500-filing development-corpus selection.

This spike needs a representative latency corpus, not the frozen Phase 1
development corpus.

The benchmark corpus must be clearly labeled:

```text
DISPOSABLE SERVING-SPIKE CORPUS
NOT PHASE 1 DEVELOPMENT CORPUS
```

---

# STEP 5 — MAKE CORPUS SELECTION REPRODUCIBLE

Use deterministic selection.

Record in:

```text
configs/serving_spike.json
```

at minimum:

```text
source
selection method
seed, if applicable
target chunk count
chunk size
embedding model
retrieval top-k
reranker
benchmark query count
```

Do not rely on:

```text
whatever rows happened to be read first
```

without documenting it.

Prefer a deterministic hash/sample or otherwise reproducible ordering.

---

# STEP 6 — USE BENCHMARK-ONLY 512-TOKEN CHUNKING

If the execution plan specifies:

```text
512-token chunks
```

implement only enough benchmark-local chunking logic to create the
representative corpus.

Do NOT create the production:

```text
src/chunk/
```

implementation.

Use the actual tokenizer associated with the selected embedding model when
practical.

Record:

```text
tokenizer/model
max token length
overlap, if any
number of chunks created
mean token count
p50 token count
p95 token count
```

If the plan specifies overlap, honor it.

Otherwise do not invent complex chunking behavior.

---

# STEP 7 — KEEP SOURCE METADATA LIGHTWEIGHT

Each spike chunk should retain enough metadata to inspect results, such as:

```text
chunk_id
CIK if available
year
section
text
```

Use actual available EDGAR-CORPUS fields.

Do not redesign the frozen production chunk schema here.

The Phase 2 chunk schema remains a separate design contract.

---

# STEP 8 — STORE DERIVED SPIKE DATA UNDER `artifacts/`

Use the storage abstraction.

Preferred conceptual location:

```text
artifacts/serving_spike/<config_hash>/
```

Potential contents:

```text
chunks.parquet
lancedb/
onnx/
benchmark_temp/
```

Do not modify:

```text
data/
```

Do not place large generated files under:

```text
results/
```

---

# STEP 9 — CREATE A CONFIG HASH

Generate a deterministic hash from the serving-spike configuration.

For example, hash canonical JSON containing:

```text
corpus selection
chunk size
embedding model
retrieval depth
reranker model
reranker runtime
quantization mode
```

Use this hash only to identify/reuse spike artifacts.

Do not claim this is the future production:

```text
chunk_config_hash
```

unless it happens to follow the same eventual contract.

Call it something explicit such as:

```text
spike_config_hash
```

---

# STEP 10 — EMBED THE REPRESENTATIVE CORPUS

Use:

```text
BAAI/bge-small-en-v1.5
```

if that matches the execution plan.

Embedding dimension should be verified, not assumed.

The known Task 0.2 value is:

```text
384
```

but verify it.

It is acceptable to build corpus embeddings using GPU because this is an
offline preparation step.

Record:

```text
device used for build
embedding dimension
chunk count
embedding elapsed time
peak VRAM if GPU used
```

Do NOT use corpus-build throughput as serving latency.

---

# STEP 11 — BUILD THE LANCEDB SPIKE INDEX

Create the benchmark index only under:

```text
artifacts/serving_spike/
```

Record:

```text
LanceDB version
index/table configuration
vector count
dimension
on-disk size
build time
```

Do not implement the final project indexing pipeline.

Do not add production index abstractions.

Use the simplest index configuration prescribed by the current
`PROJECT_EXECUTION.md`.

If the plan does not specify an ANN configuration:

prefer the simplest defensible representative LanceDB configuration and
document exactly what was used.

Do not tune dozens of index parameters.

---

# STEP 12 — VERIFY INDEX CORRECTNESS BEFORE BENCHMARKING

Perform a tiny sanity check.

For a few queries verify:

```text
query embedding succeeds
LanceDB returns top-k
returned rows have text
candidate count matches expected top-k where possible
```

This is NOT relevance evaluation.

Do not compute retrieval-quality conclusions from this spike.

The task measures feasibility and latency.

---

# STEP 13 — PREPARE REPRESENTATIVE QUERIES

Use at least:

```text
100
```

measured queries.

Prefer:

```text
~200
```

if runtime remains reasonable.

Queries must have realistic lengths and forms for SEC RAG, for example:

```text
company revenue questions
risk-factor questions
business-description questions
operating expense questions
year-over-year questions
section-oriented questions
```

Do NOT call an LLM to generate them.

Do NOT use these as the Phase 1/2 evaluation set.

Label them:

```text
SERVING LATENCY PROBES ONLY
```

Make the query list deterministic/reproducible.

It may be stored as a small tracked JSON file or generated deterministically
from a tracked configuration.

---

# STEP 14 — RERANKER IMPLEMENTATION

Follow the actual Task 0.10 stack from `PROJECT_EXECUTION.md`.

Expected form:

```text
MiniLM cross-encoder
ONNX runtime
INT8 quantization
```

If the plan names an exact model, use that exact model.

If it only says MiniLM and gives no model identifier, a reasonable default
candidate is:

```text
cross-encoder/ms-marco-MiniLM-L-6-v2
```

but do NOT silently choose it.

Record the choice and why.

---

# STEP 15 — MODEL CACHE / DOWNLOAD POLICY

First inspect local Hugging Face caches.

If the reranker model is already available:

use it offline where practical.

If the model is not available and the spike genuinely requires it:

a one-time model download from the official Hugging Face repository is
allowed only if:

```text
the source is documented
the cache is outside the repository
no weights become trackable
the download is necessary to execute the frozen spike design
```

Do not download or mutate any project data.

Do not silently switch reranker models just because one is cached.

---

# STEP 16 — ONNX / INT8 DEPENDENCIES

Inspect the current environment first.

If ONNX inference requires missing packages such as:

```text
onnxruntime
```

install only the minimal packages necessary for the specified spike.

Any new direct dependency must be:

```text
pinned
documented
reproducible
```

Because this is benchmark/development infrastructure rather than a frozen
production stack, prefer adding such dependency to:

```text
requirements-dev.txt
```

unless the current architecture documents it as a runtime dependency.

Do not add:

```text
large unrelated optimization frameworks
```

without need.

After dependency changes run:

```bash
python -m pip check
python scripts/dev.py test --portable
```

---

# STEP 17 — VERIFY THE ONNX RERANKER

Before timing:

1. load the reranker,
2. score a few query-document pairs,
3. verify finite scores,
4. verify intended ONNX provider,
5. verify INT8 model is actually being used if INT8 is required.

Do not label a PyTorch FP32 reranker:

```text
ONNX INT8
```

unless it truly is.

Record:

```text
model
runtime
execution provider
quantization
model file size
```

---

# STEP 18 — DEFINE THE TWO PRIMARY SERVING PATHS

Benchmark at minimum:

## Path A — Vector retrieval only

```text
query
→ query embedding
→ LanceDB top-50
```

## Path B — Vector + reranking

```text
query
→ query embedding
→ LanceDB top-50
→ MiniLM rerank
→ top results
```

This gives an explicit:

```text
reranker OFF
vs
reranker ON
```

comparison.

If the execution plan specifies another on/off comparison, include it.

Do not invent a dozen ablations.

---

# STEP 19 — COMPONENT TIMINGS

Measure separately:

```text
query embedding
vector retrieval
candidate materialization
reranking
total vector-only
total vector+rerank
```

Use:

```text
time.perf_counter()
```

or an equivalent high-resolution monotonic clock.

Do not measure via logging timestamps.

Avoid including benchmark result serialization in request latency.

---

# STEP 20 — WARM-UP

Before collecting warm latency samples:

```text
load models
open LanceDB
run several unmeasured representative queries
```

Suggested:

```text
5–20 warm-up queries
```

Do not include warm-up measurements in the latency distribution.

Record the exact warm-up count.

---

# STEP 21 — WARM LATENCY MEASUREMENT

Measure a sufficiently large number of queries.

Preferred:

```text
>=100 measured requests
```

and ideally:

```text
~200
```

For each path calculate:

```text
count
mean
median / p50
p90
p95
p99 if sample size supports it
min
max
```

The primary architecture metric is:

```text
warm p95
```

Do not report only averages.

---

# STEP 22 — COLD / PROCESS-COLD MEASUREMENT

Cold-start behavior must be measured separately.

Use fresh subprocesses.

A cold iteration should include the relevant process startup path such as:

```text
Python process start
imports
model initialization
LanceDB open
first query
```

Run multiple cold iterations.

Suggested minimum:

```text
5
```

Prefer:

```text
10
```

if runtime is reasonable.

Record each sample individually in the result JSON.

---

# STEP 23 — LABEL COLD RESULTS ACCURATELY

A new local process is NOT the same as a real AWS Lambda cold start.

Call the result:

```text
local process-cold proxy
```

or similar.

Do NOT write:

```text
Lambda cold start = 4.2 seconds
```

unless Lambda itself was tested.

The architecture decision may use the proxy as evidence, but the report must
state the limitation.

OS filesystem page cache may remain warm across subprocesses.

Document that limitation.

---

# STEP 24 — MEMORY MEASUREMENT

Measure process memory at meaningful stages.

At minimum:

```text
baseline process
after imports
after LanceDB open
after embedding model load
after reranker load
peak during warm query execution
```

Use a reliable process-RSS mechanism.

If a small dependency such as:

```text
psutil
```

is genuinely needed, pin and document it as a dev/benchmark dependency.

Do not rely solely on:

```text
tracemalloc
```

because it misses large native allocations from model runtimes.

---

# STEP 25 — RECORD ON-DISK FOOTPRINT

Measure:

```text
representative LanceDB index size
embedding model files used
reranker ONNX/INT8 model size
other serving artifacts needed by the request path
```

Do not count:

```text
the entire CUDA development .venv
```

as a serverless deployment package estimate.

The current environment contains GPU-specific PyTorch packages that are not
representative of a CPU production package.

If you report `.venv` size, clearly label it:

```text
DEVELOPMENT ENVIRONMENT SIZE — NOT DEPLOYMENT PACKAGE SIZE
```

---

# STEP 26 — MEMORY-TIER / RESOURCE-TIER MEASUREMENT

Read the exact 0.10 requirement in `PROJECT_EXECUTION.md`.

If it specifies memory tiers or resource tiers, measure them credibly.

Preferred order:

1. If Docker or another already-installed resource-limiting mechanism can
   provide meaningful controlled tiers, use it.
2. Otherwise report measured RSS/resource usage and explicitly state that
   cloud memory-tier scaling was not directly reproduced locally.

Do NOT fabricate:

```text
Lambda 1 GB latency
Lambda 2 GB latency
Lambda 4 GB latency
```

from a laptop benchmark.

If the authoritative Phase 0 exit gate requires actual tier measurements and
they cannot be performed credibly, use:

```text
WARN
```

rather than pretending they were measured.

---

# STEP 27 — CPU THREAD CONTROL

Record CPU thread configuration.

Libraries involved may use:

```text
PyTorch threads
OpenMP threads
ONNX Runtime threads
BLAS threads
```

For the primary benchmark:

choose one deterministic reasonable serving configuration and document it.

Do not let an 8/16-core development laptop silently use every core while
claiming the result represents a small Lambda allocation.

If the execution plan specifies thread/resource settings, follow it.

Otherwise consider a constrained serving-like CPU configuration.

Any unconstrained-machine benchmark should be labeled clearly.

---

# STEP 28 — NO LLM GENERATION

Do NOT include:

```text
OpenAI API
Anthropic API
local generative model
answer generation
```

in Task 0.10.

The feasibility question here concerns the retrieval/reranking serving stack.

Generation-provider latency is an independent network/service latency.

No API credentials should be required.

---

# STEP 29 — NO RELEVANCE CLAIMS

Do not claim:

```text
bge-small is best
MiniLM improves accuracy
top-50 is optimal
512 tokens is optimal
```

based on this task.

There is no trusted evaluation set yet.

Phase 2 establishes trustworthy measurement.

Phase 3 performs scientific retrieval ablations.

Task 0.10 only asks:

```text
Can a representative version of this architecture serve fast enough?
```

---

# STEP 30 — COMPUTE DECISION METRICS

At minimum produce a table similar to:

| Path | Warm p50 | Warm p95 | Process-cold p50 | Process-cold p95 | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Vector only | ... | ... | ... | ... | ... |
| Vector + reranker | ... | ... | ... | ... | ... |

Also report component p50/p95:

```text
embedding
LanceDB
reranker
```

All values must come from raw samples.

Do not hand-edit measured values.

---

# STEP 31 — APPLY THE FROZEN DECISION THRESHOLDS

Use the exact decision table in:

```text
project_plan/PROJECT_EXECUTION.md
```

Expected architecture guidance from the frozen plan is approximately:

```text
warm p95 < 500 ms
    -> serving approach is feasible; proceed

warm p95 500 ms–2 s
    -> feasible only with optimization; retain as risk

warm p95 > 2 s
    -> change serving assumption / favor continuously warm service

process-cold proxy > 10 s
    -> Lambda is likely the wrong default target
```

Verify these numbers against the actual document before applying them.

Do not shift thresholds after seeing the benchmark.

---

# STEP 32 — MAKE A SERVING-TARGET DECISION

Task 0.10 is incomplete if it only reports latency.

It must record a Phase 0 serving architecture decision.

Possible outcomes might include:

```text
Lambda remains the preferred Phase 4 target
```

or:

```text
Fargate / continuously warm container becomes the preferred Phase 4 target
```

or:

```text
Lambda remains possible only after specific optimization; Fargate is the
safer default
```

Base the decision on measured evidence including:

```text
warm p95
process-cold proxy
memory
model/index footprint
initialization cost
```

Do not select a target because it sounds more production-like.

---

# STEP 33 — DISTINGUISH DECISION FROM FINAL DEPLOYMENT

The decision should mean:

```text
default deployment direction for later engineering
```

not:

```text
production environment already built
```

Task 0.10 does NOT deploy anything.

Phase 4 still owns actual deployment.

---

# STEP 34 — WRITE MACHINE-READABLE CONFIG

Create:

```text
configs/serving_spike.json
```

Include at minimum:

```json
{
  "schema_version": 1,
  "corpus": {},
  "chunking": {},
  "embedding": {},
  "lancedb": {},
  "retrieval": {},
  "reranker": {},
  "queries": {},
  "warmup": {},
  "measurement": {},
  "resource_controls": {}
}
```

Do not copy this structure blindly if a simpler actual config is clearer.

The important requirement is:

```text
every benchmark result can be traced to the config that produced it
```

---

# STEP 35 — WRITE MACHINE-READABLE RESULTS

Create:

```text
results/phase_0_10_serving_spike.json
```

Store:

```text
spike_config_hash
timestamp
environment metadata
corpus metadata
component versions
raw cold samples
aggregated cold statistics
aggregated warm statistics
component timing statistics
memory statistics
artifact sizes
decision thresholds
final serving-target decision
limitations
```

Do not put large text chunks or vectors in this JSON.

Keep it small and Git-worthy.

---

# STEP 36 — OPTIONAL CSV

If useful, also create:

```text
results/phase_0_10_serving_spike.csv
```

containing per-query latency measurements.

Keep it reasonably small.

For example:

```text
query_id
path
embedding_ms
retrieval_ms
rerank_ms
total_ms
```

This is encouraged if it materially improves auditability.

Do not generate a multi-gigabyte benchmark log.

---

# STEP 37 — WRITE THE HUMAN-READABLE REPORT

Create:

```text
project_plan/SERVING_FEASIBILITY.md
```

Recommended structure:

```markdown
# Serving Feasibility Spike

## Question

What serving target is supported by measured evidence?

## Scope

Representative architecture experiment, not production benchmark.

## Benchmark Stack

...

## Corpus

...

## Hardware / Runtime

...

## Methodology

Warm vs process-cold
number of samples
CPU/thread settings

## Results

component timing table
end-to-end timing table
memory table
artifact-size table

## Decision Thresholds

copied/summarized from PROJECT_EXECUTION.md

## Decision

Lambda / Fargate / conditional

## Limitations

100k chunks, not full corpus
local process-cold != Lambda cold start
no generation latency
no relevance-quality conclusions
provisional models/components

## Phase 3 Re-check

The selected production-like stack must be re-benchmarked after Phase 3
component selection.
```

Do not oversell the result.

---

# STEP 38 — DOCUMENT THE PHASE 3 RE-CHECK

This Phase 0 spike is intentionally early.

The report must state:

> Phase 3 must re-check the selected production-like retrieval stack against
> the Phase 0 feasibility budget after chunking, embeddings, reranking, and
> retrieval configuration have been scientifically selected.

Task 0.10 does not permanently freeze performance.

---

# STEP 39 — TEST BENCHMARK HELPERS

If `scripts/serving_spike.py` contains deterministic logic worth protecting,
add a small:

```text
tests/test_serving_spike.py
```

Test things such as:

```text
config hashing deterministic
percentile/stat computation
result schema construction
benchmark artifact path stays under artifacts/
```

Do NOT run the full 100k-chunk benchmark in pytest.

Ordinary:

```bash
python -m pytest
```

must remain fast.

---

# STEP 40 — ADD A DEVELOPER COMMAND ONLY IF USEFUL

Task 0.9 intentionally kept `scripts/dev.py` small.

Do NOT automatically add:

```text
python scripts/dev.py benchmark
```

just because the spike exists.

A one-off explicit command such as:

```bash
python scripts/serving_spike.py ...
```

is sufficient.

Only extend `dev.py` if the current architecture/documentation clearly
benefits from it.

Avoid growing the developer CLI into a task runner.

---

# STEP 41 — REUSE EXISTING ARTIFACTS WHEN SAFE

The benchmark may take meaningful time.

Make the spike resumable where practical.

If:

```text
spike_config_hash
```

matches an existing benchmark corpus/index, reuse it.

Do not rebuild 100k embeddings every time merely to re-run latency tests.

However, do not silently reuse artifacts produced by a different config.

Validate identity before reuse.

---

# STEP 42 — PROVIDE A CLEAN REBUILD OPTION

Support a clearly explicit benchmark option such as:

```text
--rebuild
```

if useful.

Without that flag, matching benchmark artifacts may be reused.

Do not delete unrelated:

```text
artifacts/
```

contents.

Never implement a broad:

```text
rm -rf artifacts
```

operation.

---

# STEP 43 — LOG BENCHMARK PROGRESS

Use:

```text
src.logging_utils
```

for useful benchmark progress events.

Examples:

```text
corpus_selected
chunks_created
embeddings_completed
index_ready
warm_benchmark_completed
cold_benchmark_completed
```

Do not log every individual chunk.

Do not log full filing text.

Do not write a new file logger.

---

# STEP 44 — TIME THE BENCHMARK ITSELF SEPARATELY

Record preparation costs separately:

```text
corpus selection time
chunk creation time
embedding build time
index build time
ONNX export/quantization time if applicable
```

These are useful engineering measurements.

But do NOT include them in:

```text
request latency
```

---

# STEP 45 — VERIFY RESULTS REPRODUCIBILITY

Run at least one second warm benchmark pass against the same built artifacts.

Compare aggregate results.

They do not need to be identical, but large unexplained variance should be
investigated.

Record representative run-to-run variation.

Do not cherry-pick the fastest run.

---

# STEP 46 — AVOID THERMAL / BACKGROUND DISTORTION

This is a laptop development machine.

Before timing:

```text
avoid simultaneous GPU-heavy jobs
avoid large downloads
avoid running the full audit
```

Record that laptop thermals/background load can affect results.

If latency varies wildly:

repeat rather than selecting the convenient measurement.

---

# STEP 47 — VERIFY FROZEN DATA IS UNCHANGED

Before and after the spike verify lightweight invariants such as:

```text
data/xbrl.duckdb size
EDGAR-CORPUS source file count
raw XBRL ZIP count
primary filing count
```

Do not hash 26 GB.

The serving spike must only read source data.

---

# STEP 48 — RUN THE FOUNDATION SUITE AFTERWARD

After all implementation/dependency changes:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
python scripts/dev.py test
```

Expected:

```text
0 failures
```

If ONNX dependencies or benchmark code break the foundation:

Task 0.10 is not complete.

---

# STEP 49 — GIT SAFETY CHECK

Run:

```bash
git status --short
git status --ignored --short
git add -n .
git count-objects -vH
```

Do not stage yet unless the repository's current Git workflow explicitly
requires a commit at this exact point.

For the purposes of this task prompt:

```text
do not commit
do not push
```

Verify the dry run includes only small reproducibility artifacts such as:

```text
scripts/serving_spike.py
configs/serving_spike.json
results/phase_0_10_serving_spike.json
optional small CSV
project_plan/SERVING_FEASIBILITY.md
tests/test_serving_spike.py
Progress.md
dependency file changes if justified
```

It must NOT include:

```text
100k chunk corpus
embeddings
LanceDB index
ONNX model weights
Hugging Face model cache
data/
.tmp/
.venv/
```

---

# STEP 50 — CHECK RESULT ARTIFACT SIZE

Before finalizing:

```text
results/*.json
results/*.csv
```

must remain small enough to be appropriate Git artifacts.

Do not commit:

```text
vectors
candidate text for every query if large
model weights
binary indexes
```

The results should preserve measurements, not runtime state.

---

# STEP 51 — UPDATE `Progress.md`

Preserve all previous history.

Append:

```markdown
## YYYY-MM-DD — Phase 0.10 Serving Feasibility Spike
```

using the current local date.

Include:

## Objective

Explain that Task 0.10 replaced the remaining serving estimates with a
representative measured architecture experiment.

## Initial State

Record:

```text
Tasks 0.0–0.9 complete
Phase 0 not complete
serving latency unmeasured
serving target unresolved
```

## Benchmark Configuration

Record:

```text
representative chunk count
chunk length
embedding model
vector store
retrieval top-k
reranker
runtime/quantization
query count
CPU/resource configuration
```

## Corpus

Explain exactly how the ~100k benchmark chunks were derived.

State explicitly:

```text
not the Phase 1 development corpus
```

## Methodology

Record:

```text
warm-up count
warm measured request count
cold-process sample count
component timing method
memory measurement method
```

## Results

Include concise tables for:

```text
component p50/p95
vector-only p50/p95
vector+rerank p50/p95
process-cold proxy
peak RSS
artifact sizes
```

## Decision Thresholds

Record the exact frozen thresholds from `PROJECT_EXECUTION.md`.

## Serving Decision

State the chosen default serving direction and why.

Examples:

```text
Lambda remains preferred
```

or:

```text
Fargate becomes preferred
```

or another evidence-supported result.

## Limitations

At minimum:

```text
100k chunks, not full corpus
local process-cold proxy, not real Lambda
no generation/API latency
no trusted relevance evaluation yet
provisional retrieval components
```

## Phase 3 Re-check

State that latency must be re-measured after Phase 3 selects the real stack.

## Files Created / Modified

List actual tracked/project files.

Do not enumerate large ignored artifacts internally.

## Result

Use exactly one:

```text
PASS — serving feasibility measured and serving target selected

WARN — benchmark completed but one serving uncertainty remains

BLOCKED — serving feasibility could not be measured reliably
```

---

# STEP 52 — PHASE 0 EXIT GATE

After Task 0.10, re-read the official Phase 0 exit criteria directly from:

```text
project_plan/PROJECT_EXECUTION.md
```

Do not use memory.

Mark every criterion:

```text
PASS / FAIL
```

Critically include:

```text
Serving latency has been measured, not estimated.
The serving target is chosen and the decision is recorded.
```

Only if **every official Phase 0 exit criterion passes**, update status to:

```text
Data Preparation                  — COMPLETE
Phase 0 — Foundation              — COMPLETE
  0.0 Git Safety Preflight        — COMPLETE
  0.1 Python Environment          — COMPLETE
  0.2 CUDA/GPU Validation         — COMPLETE
  0.3 Repository Structure        — COMPLETE
  0.4 Dependency Management       — COMPLETE
  0.5 Configuration System        — COMPLETE
  0.6 Logging                     — COMPLETE
  0.7 Storage Abstraction         — COMPLETE
  0.8 Basic Automated Tests       — COMPLETE
  0.9 Developer Commands          — COMPLETE
  0.10 Serving Feasibility Spike  — COMPLETE

Phase 1 — Make It Work End to End — NEXT
```

If any official exit criterion remains unresolved:

```text
Phase 0 — NOT COMPLETE
```

and explain exactly why.

---

# ACCEPTANCE CRITERIA

Task 0.10 is complete only if:

```text
[ ] actual PROJECT_EXECUTION.md Task 0.10 read first
[ ] actual Phase 0 exit criteria read first

[ ] representative corpus approximately matches plan scale
[ ] representative corpus selection is deterministic
[ ] benchmark corpus is explicitly NOT Phase 1 corpus
[ ] frozen data remains read-only

[ ] baseline chunk length matches plan
[ ] chunking code remains benchmark-local, not production src/chunk code

[ ] BGE baseline model used if specified by plan
[ ] representative corpus embedded
[ ] embedding/index artifacts live under artifacts/
[ ] generated artifacts are Git-ignored

[ ] LanceDB representative index built
[ ] index size recorded
[ ] index configuration recorded

[ ] benchmark query set deterministic
[ ] queries explicitly labeled latency probes, not eval

[ ] top-k matches plan
[ ] vector-only path measured
[ ] vector+reranker path measured

[ ] MiniLM reranker matches plan
[ ] ONNX runtime actually used if required
[ ] INT8 actually used if required
[ ] reranker execution provider recorded

[ ] query-embedding latency measured
[ ] vector-search latency measured
[ ] reranker latency measured
[ ] total latency measured

[ ] warm-up excluded from timing
[ ] >=100 warm requests measured unless plan specifies otherwise
[ ] p50 measured
[ ] p95 measured
[ ] p90/p99 recorded where useful

[ ] multiple process-cold samples measured
[ ] cold result labeled local process-cold proxy
[ ] no claim that local process-cold equals Lambda cold start

[ ] process RSS measured credibly
[ ] major model/index artifact sizes measured
[ ] development CUDA environment size not misrepresented as deployment size

[ ] CPU/thread/resource configuration recorded
[ ] cloud resource tiers not fabricated

[ ] no LLM generation included
[ ] no relevance-quality conclusions made
[ ] no Phase 1 implementation started

[ ] frozen decision thresholds applied without changing them after results
[ ] serving target selected
[ ] serving decision documented

[ ] configs/serving_spike.json created
[ ] small machine-readable result artifact created
[ ] project_plan/SERVING_FEASIBILITY.md created

[ ] benchmark helper tests added where appropriate
[ ] portable tests still pass
[ ] full foundation suite still passes

[ ] frozen data unchanged
[ ] no model/index/vector artifact stageable
[ ] Progress.md updated

[ ] all official Phase 0 exit criteria re-checked
[ ] Phase 0 marked COMPLETE only if every exit criterion passes

[ ] no Git commit created
[ ] no Git push performed
[ ] no Phase 1 work started
```

---

# STOP CONDITIONS

Stop rather than manufacturing a successful result if:

```text
the current PROJECT_EXECUTION.md conflicts materially with this prompt

the representative corpus cannot be built without modifying frozen data

the specified reranker cannot actually run using the claimed ONNX/INT8 path

benchmark measurements are too unstable to support a decision

memory/resource behavior cannot be measured credibly enough for a required
exit criterion

the benchmark requires silently falling back to GPU while evaluating a CPU
serverless target

the result files cannot be tied to an exact configuration

the Phase 0 test suite regresses

the measured result fails the serving threshold
```

A threshold failure is not a failed engineering task.

If measurement says:

```text
Lambda is a bad target
```

and the evidence is sound, Task 0.10 can still PASS by recording:

```text
Fargate / continuously warm service selected
```

The point is to make the architectural decision correctly.

---

# IMPORTANT NON-GOALS

Task 0.10 does NOT:

```text
build the Phase 1 1,500-filing corpus
implement the production normalizer
implement the production chunker
select the final embedding model
select the final reranker scientifically
perform retrieval-quality evaluation
build BM25
build hybrid retrieval
implement CRAG
implement router
call an LLM
deploy Lambda
deploy Fargate
run a full-corpus 14M-chunk benchmark
claim production SLA
```

This task answers one question:

> Is the provisional retrieval-serving architecture plausible, and which
> serving target should later engineering assume?

---

# FINAL RESPONSE TO ME

After completing the task, return:

## Task

```text
task_0.10_serving_feasibility_spike.md
```

## Result

```text
PASS / WARN / BLOCKED
```

## Benchmark Stack

Report:

```text
chunk count
chunk size
embedding model
LanceDB configuration
retrieval top-k
reranker
runtime
quantization
CPU/resource configuration
query count
```

## Warm Latency

Report p50/p95 for:

```text
query embedding
vector retrieval
reranking
vector-only total
vector+rerank total
```

## Cold Proxy

Report:

```text
number of subprocess samples
process-cold p50
process-cold p95
```

State explicitly:

```text
local process-cold proxy — not real Lambda cold-start measurement
```

## Memory / Footprint

Report:

```text
peak RSS
embedding model footprint
reranker footprint
LanceDB index footprint
```

## Decision Threshold

Quote/summarize the actual threshold applied from `PROJECT_EXECUTION.md`.

## Serving Decision

State one clear result:

```text
Lambda preferred
Fargate preferred
conditional / optimization required
```

and give the measured reason.

## Limitations

List the important limitations of the spike.

## Result Artifacts

Confirm:

```text
configs/serving_spike.json
results/phase_0_10_serving_spike.json
project_plan/SERVING_FEASIBILITY.md
```

plus any other small tracked files actually created.

## Generated Artifacts

Confirm large benchmark data/index/model files are under ignored locations
and are not stageable.

## Tests

Report:

```text
portable suite
full suite
new benchmark-helper tests
```

with passed/failed/skipped counts.

## Frozen Data

Confirm:

```text
data/ unchanged
```

## Phase 0 Exit Gate

List every official Phase 0 exit criterion from the current
`PROJECT_EXECUTION.md` and report:

```text
PASS / FAIL
```

for each.

Then state exactly one:

```text
PHASE 0 COMPLETE
```

or:

```text
PHASE 0 NOT COMPLETE
```

## Next Task

Only if the full official Phase 0 exit gate passes:

```text
Phase 1 — Make It Work End to End
task_1.1_select_development_corpus.md — NEXT
```

Do not start it.

Finally state explicitly:

```text
No Git commit created.
No Git push performed.
No Phase 1 work started.
```

Stop and wait for my approval.