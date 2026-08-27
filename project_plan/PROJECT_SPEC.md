# SEC RAG — Full Project Specification

Living document. Current as of the completion of Phase 1 (data acquisition).

Every number in the "achieved" sections is measured. Every number in the
"planned" sections is an estimate and marked as such.

---

## Table of contents

1. [Current state](#1-current-state)
2. [What the project is](#2-what-the-project-is)
3. [Data inventory](#3-data-inventory)
4. [Storage architecture](#4-storage-architecture)
5. [Build pipeline](#5-build-pipeline)
6. [Retrieval architecture](#6-retrieval-architecture)
7. [Model inventory](#7-model-inventory)
8. [Guardrails](#8-guardrails)
9. [Evaluation](#9-evaluation)
10. [Serving](#10-serving)
11. [Cost](#11-cost)
12. [Repository layout](#12-repository-layout)
13. [Build order](#13-build-order)
14. [Open decisions](#14-open-decisions)
15. [Known gaps](#15-known-gaps)
16. [Deliberately excluded](#16-deliberately-excluded)

---

## 1. Current state

### Done

**Phase 1 — data acquisition and validation. Complete.**

Four sources downloaded, validated, and cross-checked. 21 GB on disk after
cleanup. Five silent bugs found and documented during validation.

**Design decisions settled**: corpus choice, retrieval path structure, router
design, reranking approach, CRAG adaptation, guardrail placement, model
tiering, evaluation methodology.

### Not started

Parsing, chunking, embedding, index construction, retrieval, reranking,
router, guardrails, eval harness, API, deployment. Everything downstream of
data.

### Position

End of week 1–2 of an ~8 week plan.

### The most valuable artifact so far

The bug log in `Progress.md`. Five failures found in validation code, none of
which crashed:

| Bug | Symptom | Root cause |
|---|---|---|
| `coreg`/`segments` dropped | False 56.5% duplicate rate, 92–99% restatement rate | Fund per-holding line items collapsed onto one key |
| `index.json` type field | Would have required filename guessing | `type` is a MIME-icon class, not a document role |
| String vs int CIK compare | Clean `0.00%` overlap, no error | EDGAR-CORPUS `cik` is VARCHAR, XBRL is BIGINT |
| `r[0]` in set comprehension | `0.00%` join rate | Kept only half of each `(cik, year)` tuple |
| Naive coverage window | 27.17% join rate | Single-digit-row noise years inflated denominator |

All five produced *believable wrong numbers*. This is the section to keep
most carefully — evidence of questioning your own output is rarer than
evidence of building things.

---

## 2. What the project is

Question answering over US public company filings, built around the specific
ways naive RAG fails on this corpus:

| Failure mode | Design response |
|---|---|
| Right company, wrong fiscal year | Metadata pre-filtering before vector search |
| Hallucinated financial figures | Numeric questions answered by SQL over XBRL, not retrieval |
| Confident answer when retrieval failed | CRAG grading via reranker score, with refusal |
| Unsupported claims in output | Groundedness and citation validation on output |
| Unmeasurable quality | 3,000-question eval set, mostly deterministic, running in CI |

Two tracks:

- **Benchmark track** — MS MARCO. Verifies the retrieval and eval code is
  correctly wired against published baselines. Not part of the project corpus.
- **Project track** — SEC filings. What the project is about.

---

## 3. Data inventory

### Measured, on disk

| Source | Content | Rows / docs | Size |
|---|---|---|---|
| MS MARCO (`BeIR/msmarco`) | Web passages + queries + qrels | 8,841,823 passages; 509,962 queries | 1.6 GB |
| EDGAR-CORPUS (`c3po-ai/edgar-corpus`) | 10-K filings, pre-sectioned, tables stripped | 91,086 filings; 25,937 CIKs; 1993–2020 | 5.4 GB |
| XBRL Financial Statement Data Sets | Financial facts | 90,685,753 facts; 218,166 submissions; 10,757 companies; 291,429 tags | 2.9 GB raw + 6.6 GB DuckDB |
| Primary documents | Complete 10-Ks, tables intact | 990 filings, 2021–2024 | 4.48 GB |

**Total: 21 GB** after deleting the disposable XBRL extraction cache.

### Validation results

| Check | Result | Verdict |
|---|---|---|
| MS MARCO referential integrity (3 splits) | 100.00% | PASS |
| MS MARCO dev-small confirmed | exactly 6,980 queries | PASS |
| XBRL duplicate rate (full SEC key) | 0.0000% (32 / 90.7M) | PASS |
| XBRL restatement rate `(cik, tag, ddate, qtrs)` | 23.56% | WARN |
| EDGAR-CORPUS section fill | 5 of 20 sections below 50% | WARN |
| EDGAR-CORPUS tables absent | 0/10 samples show tabular structure | confirmed |
| Primary docs table survival | 298/300 have tables, mean 135.8/doc | PASS |
| Primary docs inline XBRL | 300/300 | PASS |
| CIK overlap EDGAR-CORPUS ∩ XBRL | 26.51% | FAIL (structural) |
| `(cik, year)` join, overlapping years only | **81.71%** | the operative number |

The CIK overlap FAIL is definitional, not a data problem: EDGAR-CORPUS spans
1993–2020 while XBRL covers 2016–2024. Most EDGAR-CORPUS companies predate
the XBRL mandate or deregistered. **Within the overlapping window the join
rate is 81.71%**, which is what governs eval design.

### Sparse EDGAR-CORPUS sections

| Section | Fill rate |
|---|---|
| `section_1A` (Risk Factors) | 25.6% |
| `section_1B` | 24.4% |
| `section_9A` | 30.1% |
| `section_9B` | 27.0% |
| `section_15` | 32.4% |

Property of the source filings, not fixable. Tree navigation over these items
will find nothing for roughly two thirds of filings.

---

## 4. Storage architecture

### Principle

**Durable state separates from compute.** State lives in files that can sit in
S3. Compute is stateless and scales to zero. Idle cost is storage only.

### Layout

```
data/
  benchmark/                    # MS MARCO — never mixed with project data
    corpus.parquet
    queries.parquet
    qrels_{train,validation,test}.parquet
    index/                      # separate vector + BM25 namespace

  raw/
    xbrl/*.zip                  # 2.9 GB, quarterly source ZIPs
    primary/{cik}/{accession}.htm   # 990 files, 4.48 GB

  edgar_corpus/
    {train,test,validation}.parquet # 5.4 GB

  okf/                          # normalized layer, PLANNED
    {cik}/{year}/{accession}.md

  chunks/                       # PLANNED
    part-*.parquet              # partitioned by cik, year

  index/                        # PLANNED
    vectors.lance/              # binary quantized + fp16 rescore
    bm25/
    graph.duckdb

  xbrl.duckdb                   # 6.6 GB, facts + submissions
  eval.duckdb                   # PLANNED, one row per eval run
```

### Storage abstraction

Single root, no hardcoded paths anywhere else:

```python
STORAGE_ROOT = os.getenv("STORAGE_ROOT", "./data")   # later: s3://bucket
```

All access goes through `src/storage.py`. LanceDB, DuckDB, and pyarrow accept
`s3://` URIs directly, so migration is a config change.

### Format choices

| Artifact | Format | Reason |
|---|---|---|
| Normalized documents | Markdown + YAML frontmatter | Human-readable, diffable, OKF-aligned, re-chunkable without re-parsing |
| Chunks | Parquet, partitioned by `cik`/`year` | Columnar scan, partition pruning makes scoped search a file-selection problem |
| Vectors | LanceDB | Lazy reads from S3, no server, scale-to-zero |
| BM25 | Tantivy or rank_bm25 | Local, no server |
| XBRL facts | DuckDB | Embedded, columnar, single file, reads parquet natively |
| Graph | DuckDB tables (`nodes`, `edges`) | Graph is small (~10K nodes); avoids a second database. Neo4j Desktop for visual exploration only |
| Eval results | DuckDB | Queryable experiment log; README tables generated from it |

### Vector storage math (estimated)

~14M chunks projected (91K filings × ~150 chunks).

| Representation | Bytes/vector | Total |
|---|---|---|
| fp32, 1024-dim | 4,096 | 57 GB |
| fp16, 1024-dim | 2,048 | 29 GB |
| fp16, 384-dim | 768 | 11 GB |
| Binary quantized, 1024-dim | 128 | **1.8 GB** |

**Two-stage retrieval**: search wide on binary vectors, rescore top-N with
fp16 vectors read from storage. Keeps the hot index inside Lambda's 10 GB
memory ceiling. Recall cost of quantization is an ablation to measure.

---

## 5. Build pipeline

### Entry depths

Sources enter at different stages because they arrive in different states.

| Source | Enters at | Why |
|---|---|---|
| Primary docs (990) | Parse | Raw HTML, 136 tables/doc, inline XBRL |
| EDGAR-CORPUS (91K) | Normalize | Already split into `section_1`…`section_15` |
| MS MARCO (8.8M) | Chunk/embed | Already passage-sized |
| XBRL (90.7M facts) | — | Bypasses documents entirely, straight to DuckDB |

### Stage 1 — Parse (primary docs only)

Docling. HTML → Markdown with table structure preserved. Table serialization
format is an ablation variable (Markdown vs HTML vs CSV), tested against FinQA.

Inline XBRL (`ix:` namespace) present in 100% of primary docs — extractable as
a structured overlay.

### Stage 2 — Normalize (OKF layer)

One Markdown file per filing:

```markdown
---
cik: 1045810
ticker: NVDA
company: NVIDIA CORP
form_type: 10-K
fiscal_year: 2023
accession: "0001045810-24-000029"
sic: 3674
source: edgar_corpus | primary
sections: [item_1, item_1a, item_7, item_8]
---

# Item 1. Business
...
```

Partitioned `{cik}/{year}/{accession}.md`.

**Why persist this layer**: chunking strategy is an ablation variable. Without
a normalized layer every chunking experiment means re-parsing. With it, each
experiment is a cheap pass over clean Markdown. This is the decision that makes
the ablation table affordable.

`sic` comes from XBRL `sub.txt` — free industry metadata, currently unused.

### Stage 3 — Chunk

Section-aware splitting on heading boundaries, size-capped within long
sections. Every chunk inherits full frontmatter plus `section_id`.

Ablation grid: size {256, 512, 1024}, overlap {0, 64, 128}, section-aware vs
fixed-window, table serialization format.

### Stage 4 — Embed

Local GPU (RTX 5060, 8 GB), fp16, batched. Query and passage prefixes applied
per model family — **omitting these degrades recall silently with no error**.

Estimated: ~14M chunks, overnight run.

**Blackwell note**: RTX 50-series reports `sm_120` and requires PyTorch built
against CUDA 12.8+. Verify before anything else.

### Stage 5 — Index

| Index | Source | Scope |
|---|---|---|
| Vector | All chunks | Binary quantized + fp16 rescore |
| BM25 | All chunks | Full |
| XBRL SQL | `num.txt` + `sub.txt` | Complete, already built |
| Tree | OKF section hierarchy | Free — no separate index |
| Graph | See below | Subset |

### Graph sources (available, unbuilt)

| Graph | Source | Cost | Status |
|---|---|---|---|
| Concept hierarchy | `pre.txt` in XBRL ZIPs | Reload only | **Downloaded, not loaded** |
| Industry grouping | `sic` in `sub.txt` | Reload only | **Downloaded, not loaded** |
| Company co-mention | Name matching vs 10,757-name gazetteer | ~1 day, deterministic | Buildable now |
| Subsidiary ownership | Exhibit 21 | ~990 extra requests | **Not downloaded** |
| Customers/suppliers | LLM extraction over `section_1` | Expensive | Scope to 990 docs if at all |

Exhibit 21 is the highest-quality graph available and is missing because the
fetch pulled primary documents only.

---

## 6. Retrieval architecture

### Paths

| Path | Handles | Backing store |
|---|---|---|
| Hybrid (vector + BM25) | Narrative, semantic | LanceDB + BM25 index |
| SQL over XBRL | Numeric facts, comparisons | DuckDB |
| Tree navigation | "Summarize Item 7 of this filing" | OKF section hierarchy |
| Graph | Multi-entity relationships | DuckDB `nodes`/`edges` |

Tree navigation is a **second hop** — it operates within a known document, so
it runs after retrieval identifies which filing.

### Router

Single call returning intent and filters:

```json
{
  "intent": "numeric",
  "filters": {"cik": 1045810, "fiscal_year": 2023, "form_type": "10-K"},
  "paths": ["xbrl_sql"],
  "complexity": "single_hop"
}
```

**Rules first.** Company name → CIK is a lookup over the 10,757-name XBRL
gazetteer. Year is regex. Form type is keyword matching. Intent starts as
keyword rules. An LLM router is benchmarked *against* this baseline; adopt it
only where rules measurably lose.

Router accuracy is measured against a labelled query→path set. Misrouting is
the dominant failure mode once multiple paths exist.

### Filtering — pre, never post

Post-filtering (retrieve globally, then discard out-of-scope) returns empty
sets when scope is narrow, because 3 documents will not appear in the global
top-100 of a 14M-chunk index.

Strategy by selectivity:

| Filter matches | Strategy |
|---|---|
| 1–20 docs (~3K chunks) | Brute-force exact. Faster *and* more accurate than ANN at this size |
| Hundreds–thousands | Load matching partitions, index on the fly |
| Broad | Filtered ANN |

Partitioning by `cik`/`year` makes narrow scoping a file-selection problem.

Note: HNSW degrades under selective filters — traversal keeps landing on
excluded nodes. Another reason narrow scopes should not use ANN.

### Hybrid fusion

Reciprocal Rank Fusion over dense and sparse lists. RRF combines incomparable
score scales heuristically; the cross-encoder downstream produces one
comparable score across both sources. That is the stronger argument for
reranking than the metric lift alone.

### Reranking

Cross-encoder reads query and chunk **concatenated** in one forward pass, so
attention flows between them — it can connect "FY2023" to "fiscal year ended
January 28, 2024", which independent bi-encoder embeddings cannot.

**Retrieval is tuned for recall@50. Reranking is tuned for precision@5.**
Tuning both against the same metric produces a system worse than either stage
alone.

**A reranker cannot improve recall** — it reorders the candidate set, it does
not expand it. If recall@50 changes when only the reranker changed, the
harness is broken.

CPU serving path optimizations, in order of leverage:

1. Distilled model (MiniLM ~22M vs bge-reranker-base 278M) — largest lever
2. ONNX export + int8 quantization — 2–4× on CPU
3. Reduce candidate count k (linear cost)
4. Raise Lambda memory (vCPU scales with it)

Target: 150–400 ms. Estimated, to be measured.

### CRAG grading — free

The cross-encoder already scores every candidate. **Top-1 score below a
calibrated threshold means retrieval failed.** No extra LLM call, no added
latency. Threshold calibrated where score correlates with answer correctness.

Fallback ladder: rewrite query → alternate path → refuse.

**Deviation from the paper**: the original CRAG falls back to web search.
Rejected — external sources break the provenance guarantee that makes this
system worth using.

SQL path results skip reranking entirely; there is nothing to reorder.

---

## 7. Model inventory

No model is selected from a leaderboard. MTEB is a shortlisting tool; the only
scoreboard that counts is the eval set for this corpus.

### Embedding — candidates to benchmark

| Model | Dims | Context | Notes |
|---|---|---|---|
| `bge-small-en-v1.5` | 384 | 512 | Cheap floor; 384-dim halves index size |
| `bge-base-en-v1.5` | 768 | 512 | Mid workhorse |
| `nomic-embed-text-v1.5` | 768 | 8192 | Long context, Matryoshka truncation |
| `Qwen3-Embedding-0.6B` | 1024 | 8192 | Quality ceiling that fits 8 GB |
| Titan Embed v2 (API) | 1024 | 8192 | Commercial reference point |

Selection criteria, ordered:

1. **Must run in two places** — batch on GPU *and* per-query on Lambda CPU.
   Size is a throughput question at build time, a latency question at query
   time. Pick for the harder one.
2. Retrieval quality on this corpus
3. Context length — 512 is tight for financial prose, worse for tables
4. Query/passage prefix handling
5. Dimensionality → memory at query time (not storage cost; storage is cheap)
6. License — Apache 2.0 or MIT

**Benchmark method**: 50k-chunk subset, ~1 hour per model. Only the winner
runs the full corpus.

### Reranking

| Model | Params | Role |
|---|---|---|
| `ms-marco-MiniLM-L-6-v2` | ~22M | Serving candidate, ONNX int8 |
| `bge-reranker-base` | 278M | Comparison |
| `bge-reranker-v2-m3` | 568M | Quality ceiling, GPU offline |
| Cohere Rerank (Bedrock) | — | Managed baseline |

`ms-marco-MiniLM` was trained on MS MARCO, which is why the MS MARCO
benchmark track exists — running it validates the reranker is wired correctly
against published baselines.

### Generation

| Role | Tier | Selection criterion |
|---|---|---|
| Generation | Mid | **Correct-refusal rate on unanswerable questions** |
| Router (if LLM needed) | Budget | Beats the rule baseline or is not used |
| Advice classifier | Budget | Binary, every query |
| Eval judge | Frontier, **different family from generator** | Avoids self-preference bias |

Generation lives behind a provider interface:

```python
generate(prompt, context) -> answer
```

Two implementations: Ollama (local) and an API model. Batch jobs — graph
extraction, eval question generation, LLM-as-judge — run local where latency
is irrelevant and volume is high. The live path uses the API, because a demo
that only works when a home machine is awake is worthless.

**Why not local for serving**: 8 GB VRAM is insufficient for RAG-shaped
prompts (5 chunks ≈ 3–4k tokens) alongside the embedding model. Small models
are also weakest at "answer only from context, otherwise decline" — the exact
instruction the CRAG refusal path depends on.

**The headline generation metric is correct-refusal rate.** A model that
scores well on faithfulness but answers unanswerable questions is unusable in
a system claiming verifiable output.

---

## 8. Guardrails

Three checkpoints. Cheap deterministic checks first; LLM only for the
ambiguous remainder.

### Input gate

| Check | Implementation |
|---|---|
| Length cap | Hard limit |
| PII in query | Presidio |
| Scope enforcement | Rules — non-filing questions declined |
| Injection patterns | Pattern match + classifier |
| Rate limiting | API Gateway |

### Context gate — the RAG-specific one

Retrieved content is **data, never instruction**. Defense is architectural,
not filter-based:

- Retrieved text enclosed in explicit delimiters
- System prompt states delimited content is untrusted data
- Instruction-shaped patterns stripped before assembly

A deliberately poisoned document is planted in the test corpus;
`tests/test_injection.py` asserts the system does not follow its instructions.

### Output gate

| Check | Implementation |
|---|---|
| Groundedness | Every claim verified against retrieved context |
| Citation validation | Cited chunk IDs exist and contain the claim |
| Financial advice refusal | Classifier — "what did X report" answerable, "should I buy X" not |
| PII leakage | Presidio |

The advice boundary is deliberate. This is a document retrieval system, not a
registered investment adviser.

### Metric

**False-positive rate**, not block rate. Blocking everything is trivial.
Report precision, recall, and FPR per guard against a 200-query labelled set.

---

## 9. Evaluation

Stages measured separately. An end-to-end score cannot distinguish retrieval
failure from generation failure, and they need different fixes.

### Test set (~3,000, planned)

| Category | Count | Source | Scoring |
|---|---|---|---|
| Numeric | ~2,000 | XBRL facts | Exact match, deterministic |
| Comparative / multi-hop | ~500 | Computed over XBRL | Exact match |
| Narrative | ~200 | LLM-generated from risk factors, hand-verified | LLM judge |
| Unanswerable | ~200 | Companies/years outside corpus | Refusal rate |
| Adversarial | ~100 | Injection, advice, off-scope | Guard trigger rate |

**Scope to 2016–2020 EDGAR-CORPUS filings.** The 81.71% `(cik, year)` join
rate only holds in the overlapping window. Outside it, ground truth points at
documents not in the corpus.

**Anchor questions to the accession**, not the fiscal year. "What did NVIDIA
report in the 10-K filed 2024-02-21?" has one answer; "in FY2023" has several,
given a 23.56% restatement rate. Anchoring also yields the retrieval label for
free — you know exactly which document should be returned.

**Turn restatements into an eval category.** Questions where the same concept
has different values across filings specifically test whether retrieval returns
the *right* document rather than a plausible one. That dimension came out of a
data problem found during validation.

Exclude the 33,322 negative-`Assets` rows (~0.5%) — known tagging errors.

The 291,429 distinct tags confirm the 15-standard-tag approach; the tail is
custom extension tags that do not generalize.

### External eval sets

| Set | Purpose |
|---|---|
| MS MARCO | **Harness correctness** — matches published baselines or there is a bug |
| FinanceBench (150) | Independent human-annotated evidence; catches generator bias in the auto-generated set. CC-BY-NC, eval only |
| FinQA | Table serialization ablation |
| HotpotQA | Multi-hop, out-of-domain |

### Metrics

**Retrieval** — deterministic, seconds, no LLM: recall@10, recall@50, MRR,
nDCG@10. 90% of experimentation happens here; 50 configs in an afternoon.

**Generation** — exact match (numeric), faithfulness (narrative),
correct-refusal (unanswerable).

**System** — p50/p95 latency, cost per query, index build time.

### Judge validation

LLM-as-judge failure modes: verbosity preference, run-to-run inconsistency,
sycophancy, self-preference toward its own family.

Two mitigations:

1. Judge from a **different model family** than the generator
2. **Validate against human labels** — hand-label 100 answers, run the judge
   on the same 100, report agreement. Every judge-based number then carries a
   known error bar

### CI

200-question golden set on every commit via GitHub Actions. Build fails if
recall@10 drops more than 2% from the previous commit. Full 3,000 weekly and
before any architectural decision.

Every run logged to `eval.duckdb`: config hash, git SHA, all metrics,
timestamp. README ablation tables are generated by querying it, not assembled
by hand.

---

## 10. Serving

### Query path

```
Input guard  →  Router  →  Retrieve  →  Rerank + CRAG  →  Generate  →  Output guard
                  ↓          ↑
            filters extracted
```

Router fans to SQL, hybrid+tree, or graph. SQL results bypass reranking.

### Deployment

FastAPI in a single container. Lambda or Fargate — both scale to zero.

Constraints: Lambda 10 GB memory ceiling (drives binary quantization), 250 MB
deployment package (drives ONNX over PyTorch for the reranker), cold start
measured and reported.

Retrieval logic stays a plain Python module; FastAPI is a thin wrapper. No AWS
SDK calls in core logic, so the compute target stays swappable.

### Observability

CloudWatch for infrastructure. Per-query structured logging: router decision,
paths fired, candidate count, rerank top-1 score, CRAG trigger, latency per
stage, token counts.

---

## 11. Cost

### One-time

| Item | Cost |
|---|---|
| Embedding 14M chunks (local GPU) | Electricity |
| Eval question generation (local model) | Electricity |
| Graph extraction, if LLM-based, 990 docs | Estimated, low |
| Full-corpus LLM graph extraction | **Rejected** — four figures, no proportional benefit |

### Recurring

| State | Cost |
|---|---|
| Idle (S3 storage only) | ~$2/month estimated |
| Per query | Pennies |
| **Eval sweep** (3,000 × 1 config) | The dominant LLM cost |

**Evaluation, not serving, is the LLM bill.** Ten configs × 3,000 questions =
30,000 calls. Mitigations: most questions are exact-match scored so the judge
touches only ~200 narrative answers per config; early retrieval experiments
use a budget generator since retrieval metrics do not involve the generator at
all.

---

## 12. Repository layout

```
src/
  ingest/          DONE — fetch_msmarco, fetch_edgar_corpus,
                   fetch_xbrl, fetch_primary_docs, validate, common
  parse/           PLANNED — Docling wrapper, table serialization
  normalize/       PLANNED — OKF layer writer
  index/           PLANNED — chunk, embed, build vector/BM25/graph
  retrieval/       PLANNED — hybrid, filters, rerank, CRAG
  router/          PLANNED — rules, then LLM fallback
  guards/          PLANNED — input, context, output
  api/             PLANNED — FastAPI
  eval/            PLANNED — question generation, metrics, judge
  storage.py       PLANNED — single storage abstraction
configs/           experiment configs
tests/             unit + injection resistance
infra/             deployment
prompts/           agent task prompts
data/              see storage layout
Progress.md        engineering log
FAILURES.md        PLANNED — 10 queries the system gets wrong, with diagnosis
```

---

## 13. Build order

Dependency-ordered. Steps 1–4 are not optional; everything after is.

| # | Step | Depends on | Note |
|---|---|---|---|
| 1 | Eval question generator from XBRL | XBRL (done) | **Before retrieval.** Build the instrument first |
| 2 | OKF normalization + chunking | EDGAR-CORPUS (done) | Start with a 1,500-filing tier |
| 3 | Embedding + vector/BM25 index | 2 | Benchmark 4 models on a 50k subset |
| 4 | Hybrid baseline, **measured on MS MARCO first** | 1, 3 | Confirms the harness before trusting SEC numbers |
| 5 | Reranking | 4 | Largest single quality lever |
| 6 | CRAG grading | 5 | Reuses reranker score; ~half a day |
| 7 | Router + metadata filtering | 4 | Rules baseline first |
| 8 | Scale to full corpus | 3–7 stable | Overnight embedding run |
| 9 | Guardrails | 7 | Scope + refusal early; rest here |
| 10 | API + deployment | 9 | |
| 11 | Graph paths | 8 | Optional. Exhibit 21 first if built |

**Scope discipline**: if week 8 arrives mid-way, ship what is measured and
document the rest as designed-and-costed. A measured hybrid baseline with a
real eval harness beats an unmeasured system with four retrieval paths.

---

## 14. Open decisions

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| 1 | Eval scope: full 1993–2020 or 2016–2020 | **2016–2020** — the 81.71% join only holds there | Step 1 (critical path) |
| 2 | Fetch Exhibit 21? ~990 requests | Yes if building a graph — best quality, deterministic | Step 11 |
| 3 | Load `pre.txt` and `sic` from existing ZIPs | Yes — reload only, `sic` is free metadata regardless | Step 11 |
| 4 | Embedding dims: 384 vs 1024 | Decide from the 50k benchmark, not in advance | Step 3 |
| 5 | Graph store | DuckDB. Neo4j Desktop for visual exploration only | Step 11 |

---

## 15. Known gaps

Stated explicitly. A project claiming no limitations is not credible.

- **EDGAR-CORPUS has no tables.** Table retrieval can only be tested on the
  990 primary docs, not at scale
- **Sections 1A, 1B, 9A, 9B, 15 are 25–32% filled.** Tree navigation over
  these finds nothing for most filings
- **23.56% restatement rate.** Resolved by accession-anchoring, not eliminated
- **CIK overlap is 26.51% overall.** Eval must scope to 2016–2020
- **Exhibit 21 not downloaded.** The best available graph is missing
- **`pre.txt` and `sic` downloaded but never loaded**
- **English only.** No 20-F or 40-F
- **Point-in-time.** No incremental update pipeline
- **990 primary docs are large-cap only** (selected by total Assets) —
  table extraction is untested on small filers
- **Judge agreement unmeasured** until step 1 completes

---

## 16. Deliberately excluded

| Excluded | Reason |
|---|---|
| Kubernetes | A container behind FastAPI serves this. Adds weeks, answers nothing asked |
| Always-on vector DB | Bills 24/7 regardless of traffic; breaks scale-to-zero |
| Neo4j in the serving path | Persistent server; same problem. Desktop for exploration only |
| Local LLM in the serving path | 8 GB VRAM insufficient for RAG prompts; demo must work when the desktop is off |
| Fine-tuned embedding model | Benchmark off-the-shelf first. Future work |
| LLM-as-reranker | Slower and costlier than a cross-encoder, no added capability |
| CRAG document refinement | Marginal once a good reranker exists. Revisit if measured |
| Full-corpus LLM graph extraction | Four figures for a path most queries never touch |
| 8-K filings for document count | Padding — 150K/year, ~5% more chunks, no content |
| CRAG web-search fallback | Breaks the provenance guarantee |
