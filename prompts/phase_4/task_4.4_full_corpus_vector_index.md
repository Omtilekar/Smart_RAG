# Task 4.4 — Full-Corpus Vector Index

## Objective

Build and validate the full-corpus production-scale vector index over the
frozen Task 4.3 embedding artifact.

This is a SCALE-OUT / INDEX-BUILD task.

Do NOT:
- re-normalize documents,
- re-chunk documents,
- re-embed chunks,
- reopen Phase 3 model/chunking decisions,
- add BM25/RRF hybrid retrieval,
- add reranking,
- change CRAG,
- open protected TEST,
- make paid LLM/API calls,
- silently introduce ANN/quantization/index changes not already authorized.

Task 4.4 must consume the frozen Task 4.3 embeddings exactly as they exist.

The primary goal is:

Task 4.3 frozen embedding shards
    ->
validated full-corpus LanceDB table
    ->
validated exact cosine retrieval path
    ->
production-scale index artifact + manifest

Before implementation, read the repository and authoritative roadmap.
If `project_plan/PROJECT_EXECUTION.md` defines Task 4.4 more specifically
than this prompt, follow it unless it conflicts with a frozen fact below.
Report any material conflict instead of silently resolving it.

---

# Repository Root

Windows project root:

`C:\Om\Codes\RAG`

Before changing code, inspect at minimum:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PHASE1_VECTOR_INDEX.md`
- `project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md`
- `project_plan/PHASE3_METADATA_PREFILTERING.md`
- `project_plan/SERVING_FEASIBILITY.md`
- `project_plan/PHASE4_FULL_CORPUS_CHUNKING.md`
- Task 4.3 documentation if present
- `src/index/lancedb_index.py`
- `src/storage.py`
- Task 1.5 index-build code/tests
- Task 3.x retrieval/index code relevant to the final selected stack

Also inspect the real Task 4.3 final manifests rather than trusting
Progress.md alone.

---

# Correct Progress.md Typo First

The current Task 4.3 entry ends with:

`Next roadmap task: 4.3 Full-corpus embedding.`

That is stale.

Correct it to the actual Task 4.4 name after confirming the authoritative
roadmap wording.

Do not otherwise rewrite historical Progress.md entries.

---

# Frozen Upstream Inputs

## Task 4.1

Full-corpus normalization config hash:

`754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f`

Documents:

- total: 91,086
- non-empty: 90,239
- valid empty-source: 847

Normalizer:

`phase1-minimal-v1`

---

## Task 4.2

Frozen chunk configuration:

- fixed window
- 256 content tokens
- zero overlap
- stride 256
- non-section-aware
- final partial retained

Frozen chunk config hash:

`ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06`

Chunk schema version:

`2`

Full-corpus chunk count:

`10,487,096`

Chunk shards:

`54`

Canonical shard IDs:

`00000` through `00053`

Task 4.2 shard manifest SHA-256:

`b0421c390e218099f20563faffcfaa8791678ba571995738f5cd7df82a7088ac`

---

# Frozen Task 4.3 Embedding Artifact

Embedding model:

`Qwen/Qwen3-Embedding-0.6B`

Model revision:

`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`

Dimension:

`1024`

Persisted dtype:

`float32`

Normalization:

`normalize_embeddings=True`

Corpus encoding:

documents/passages, no query prompt

Final embedding count:

`10,487,096`

Final shard count:

`54`

Final Task 4.3 output size:

`17.23 GiB`

Task 4.3 final manifest SHA-256 as defined by the Task 4.3 audit:

`a4d1421bb287ea6aa21398f1fca99f1e11650b7c0d49979077140bb17456fbc8`

IMPORTANT:

Do not assume this value is necessarily the raw byte SHA-256 of
`embedding_manifest.json`.

Inspect the Task 4.3 manifest-generation code / manifest fields and verify
it using the exact canonicalization semantics used by Task 4.3.

---

# Local Task 4.3 Artifact Root

The frozen local source is:

`C:\Om\Codes\RAG\artifacts\embeddings_full\754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f\ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06\qwen3-embedding-0.6b_97b0c614`

Expected structure:

```text
qwen3-embedding-0.6b_97b0c614/
├── embeddings/
│   ├── worker_0/
│   │   └── *.embeddings.parquet
│   └── worker_1/
│       └── *.embeddings.parquet
└── final/
    ├── embedding_manifest.json
    └── validation_summary.json