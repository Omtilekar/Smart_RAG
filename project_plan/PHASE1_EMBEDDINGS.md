# Phase 1 Baseline Embedding Pipeline

**Phase 1 baseline embedding contract.** Established in Task 1.4. This
embeds every Task 1.3 chunk with `BAAI/bge-small-en-v1.5` — one model only,
full FP32, no quantization, no ablation — per `PROJECT_EXECUTION.md`'s
Phase 1 framing. It is not a model comparison and makes no retrieval-quality
claim; Phase 3 owns embedding-model benchmarking.

## Purpose

Task 1.3 produced 162,357 fixed-window chunks. Task 1.4 converts each
chunk's `text` into a 384-dimensional dense vector and persists a
self-contained, traceable embedding artifact — the input Task 1.5's
LanceDB vector-only index will consume.

## Input: Task 1.3 chunk corpus

```text
chunk_config_hash:    f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
chunk artifact:         artifacts/chunks/f1dc04d4.../chunks.parquet
row count:                162,357
unique chunk_id count:      162,357
distinct chunk_config_hash values in the file: exactly 1 (matches above)
empty text rows:              0
```

All verified directly against the live `chunks.parquet` before any encoding
started, not trusted from `results/phase_1_3_chunking_summary.json` alone.

## User-approved decisions

Two conventions were resolved by **direct inspection of the cached
model's own README** (an authoritative source per the task's own rule —
"direct inspection of the local cached model/configuration") rather than
assumed from a library default or asked about:

| Decision | Resolution | Source |
|---|---|---|
| Passage convention | Raw text, no instruction prefix | Model card: "no instruction needs to be added to passages" |
| Query convention | Prepend `"Represent this sentence for searching relevant passages: "` | Model card's query-instruction table row for `BAAI/bge-small-en-v1.5` |
| `normalize_embeddings` | `True`, for both queries and passages | Model card's own documented usage example (`model.encode(..., normalize_embeddings=True)`) — the model's *documented* correct usage, not sentence-transformers' library default (which is `False`) |

Six further decisions had no resolution anywhere in the repo and were
explicitly approved before implementation:

| Decision | Approved answer |
|---|---|
| Vector dtype | `float32` (matches the model's native output) |
| GPU batch size | 128 |
| Precision policy | Full FP32, no autocast |
| OOM fallback | Halve batch size, retry, record actual batch size(s) used |
| Artifact location | New `storage.embeddings_dir(chunk_config_hash, embedding_model)`, mirroring `index_dir`'s existing compound-key pattern |
| Artifact format / metadata policy | Single self-contained Parquet file: all 16 Task 1.3 chunk columns + a `vector` column |

## Model contract

```text
repository:            BAAI/bge-small-en-v1.5
revision:               5c38ec7c405ec4b44b94cc5a9bb96e735b38267a (same
                        cached snapshot used by Task 1.3's tokenizer -
                        single cached revision, unambiguous)
sentence-transformers:   6.0.0
transformers:             5.16.1
torch:                     2.13.0+cu130
torch.version.cuda:         13.0
GPU:                        NVIDIA GeForce RTX 5060 Laptop GPU
embedding dimension:         384 (verified via model.get_embedding_dimension(),
                            not assumed)
offline guarantee:           HF_HUB_OFFLINE=1 + local_files_only=True +
                            explicit per-file try_to_load_from_cache()
                            precheck across 10 required model assets
                            (config.json, config_sentence_transformers.json,
                            modules.json, sentence_bert_config.json,
                            model.safetensors, 1_Pooling/config.json,
                            tokenizer.json, tokenizer_config.json, vocab.txt,
                            special_tokens_map.json) before construction -
                            raises rather than downloads if any is missing
```

## Query / passage contract

```python
# src/embeddings/bge.py
encode_passages(model, texts, batch_size)   # raw text, no prefix
encode_queries(model, texts, batch_size)    # QUERY_INSTRUCTION + text
```

Both call `model.encode(..., normalize_embeddings=True, convert_to_numpy=True)`
and cast to `float32`. The query path is a genuinely separate function
(not a flag on the same call site), so a future caller cannot accidentally
embed a query with the passage convention or vice versa. Verified directly:
the same underlying text embedded via each path produces measurably
different vectors (`not np.allclose(p_vectors[0], q_vectors[0])`, tested).

The full 162,357-chunk build uses **only** `encode_passages` — no query
embedding happens during the real build. A tiny query smoke test
(`test_load_model_encode_passages_and_queries_offline_cuda`) verifies the
query path works correctly for Task 1.6's future use, without performing
any retrieval.

## Vector contract

```text
normalize_embeddings:  True
vector_dtype:            float32
dimension:                384
```

Verified across the full 162,357-vector artifact: all finite (no NaN/Inf),
every vector's L2 norm within `1e-6` of `1.0` (measured min `0.9999999`,
max `1.0000001`).

## Build configuration

```text
device:              cuda (verified: next(model.parameters()).device.type == 'cuda';
                     the build raises rather than falling back to CPU if
                     device resolution disagrees)
batch_size:            128 (no OOM occurred - batch_sizes_used == [128], the
                     single approved value, throughout)
precision_policy:       full FP32, no autocast
offline/local-only:      HF_HUB_OFFLINE=1 + local_files_only=True (see
                     Model contract above)
```

## Output

```text
artifact path:   artifacts/embeddings/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/BAAI--bge-small-en-v1.5/embeddings.parquet
format:            single Parquet file - all 16 Task 1.3 chunk columns
                  (chunk_id, document_id, cik, company, form_type,
                  fiscal_year, source, source_filename, source_split,
                  ordinal, text, token_count, chunk_config_hash,
                  normalizer_version, normalization_build_sha256,
                  development_manifest_sha256) plus one additional column:
                  vector: fixed_size_list<float32>[384]
vector count:      162,357
artifact size:      440,703,576 bytes (~420.3 MiB)
```

Written via `src.storage.get_storage().embeddings_dir(chunk_config_hash,
"BAAI/bge-small-en-v1.5")` + `ensure_dir()` - a new, narrow storage helper
added to `src/storage.py` (mirroring `index_dir`'s existing
`(chunk_config_hash, embedding_model)` compound-key pattern exactly) and
covered by 3 new tests. Git-ignored generated pipeline state; only a small
tracked summary (`results/phase_1_4_embedding_summary.json`) and config
(`configs/embed_development_corpus.json`) are committed.

**Metadata policy, verified**: every one of the 16 metadata columns in
`embeddings.parquet` was compared column-for-column against
`chunks.parquet` and found identical, row for row (not sampled - the full
162,357-row comparison). `chunk_id` row order in the embeddings artifact
also exactly matches `chunks.parquet`'s row order, so `vector[i]` maps to
`chunk_id[i]` mechanically, with no join required.

## Performance (real build, not estimated)

```text
model load:                3.66s
embedding inference:       1154.74s (~19.2 min)
artifact write:               1.50s
total wall time:              1161.47s (~19.4 min)

throughput:                  140.6 chunks/sec
                              71,659.9 tokens/sec (82,748,156 total Task 1.3
                              tokens / embedding_inference_seconds)
```

Not a re-use of Task 0.2's tiny 40-sentence smoke throughput (~652 texts/sec,
an unrepresentative micro-benchmark) - this is the measured real-corpus
result.

## GPU memory (build evidence, not a capacity benchmark)

```text
peak allocated:  1,411,858,944 bytes (~1.41 GB)
peak reserved:    1,962,934,272 bytes (~1.96 GB)
```

Well within the RTX 5060's 8.55 GB VRAM - no OOM occurred at batch_size=128,
confirmed by `batch_sizes_used == [128]` in the tracked summary (the
approved OOM-fallback path, halving batch size and recording the actual
value used, was never triggered).

## Validation

```text
input chunks:            162,357
output vectors:           162,357
unique chunk IDs:           162,357 (no missing, no duplicate, no extra)
chunk_id row order:          identical to chunks.parquet (index-aligned,
                             not just set-equal)
all vectors dimension 384:   verified
all vectors finite:            verified (full corpus, not sampled)
dtype:                          float32, verified via native PyArrow ->
                             NumPy conversion (not Python-object boxing,
                             which would misreport float64)
norm check:                     min 0.9999999, max 1.0000001 (well within
                             a 1e-6 tolerance of unit norm)
metadata traceability:            all 16 columns compared full-corpus
                             against chunks.parquet - exact match
```

## Manual traceability

6 rows manually inspected: the first chunk overall, the single-token chunk
found in Task 1.3 (`27673_2016.htm::chunk69`, text `"."`), a long
document's final partial chunk (`1005817_2016.htm::chunk143`, 320 tokens),
first chunks from 2017/2018/2020 documents, and the last row of the
artifact. All 6/6 confirmed correct `chunk_id`/`cik`/`fiscal_year`
alignment, `(384,)` `float32` shape, finite values, and unit norm.

## Repeat / numeric-stability check

A fresh Python process re-loaded the model and re-encoded the first 20
chunk_ids (a deterministic subset - the file's first 20 rows) independently
of the real build:

```text
same model revision:    yes (5c38ec7c...)
same chunk IDs/order:      yes
same shape/dtype:           yes ((20, 384), float32)
max abs difference:           2.98e-08
mean abs difference:           2.36e-10
tolerance used:                 1e-5 (justified: GPU floating-point
                              inference is not guaranteed bit-identical
                              across runs even with fixed weights/inputs -
                              this project does not claim it is - but the
                              measured deviation here is within float32
                              machine epsilon, i.e. effectively identical)
result:                          PASS - all 20 vectors within tolerance
```

## Known limitations

- Phase 1 baseline only - one embedding model
  (`BAAI/bge-small-en-v1.5`), no model ablation. Phase 3 owns embedding-model
  comparison (`bge-base-en-v1.5`, `nomic-embed-text-v1.5`,
  `Qwen3-Embedding-0.6B`, etc — see `PROJECT_SPEC.md`'s model inventory).
- No retrieval-quality claim of any kind - this task produces embeddings,
  not a measured recall/MRR/nDCG number. That begins in Task 1.6+ and is
  only trustworthy starting Phase 2.
- No quantization experiment (binary/product quantization is Task 0.10's
  separate, explicitly non-binding serving-spike concern, and a later
  Phase 3 decision - not conflated with this task's plain `float32` output).
- No LanceDB index exists yet - `embeddings.parquet` is a flat, unindexed
  artifact. Task 1.5 builds the first ANN/vector index from it.
- GPU floating-point inference is not asserted bit-identical across runs -
  only numerically close within a documented, justified tolerance (see
  above). This is standard for GPU inference and not treated as a defect.

## Next consumer

Task 1.5 (Vector-Only Index) reads
`artifacts/embeddings/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/BAAI--bge-small-en-v1.5/embeddings.parquet`
and builds a LanceDB table from its `vector` column and metadata.

## Reproducing this build

```bash
python scripts/embed_development_corpus.py
```

Reads `artifacts/chunks/f1dc04d4.../chunks.parquet` read-only, loads the
model offline from local cache, performs no network access, writes only
`artifacts/embeddings/<chunk_config_hash>/<embedding_model>/embeddings.parquet`
(git-ignored), `results/phase_1_4_embedding_summary.json`, and
`configs/embed_development_corpus.json` (both tracked). GPU floating-point
inference is not guaranteed bit-identical across runs (see "Repeat /
numeric-stability check" above), but was verified numerically close within
float32 machine epsilon on a deterministic 20-row subset.
