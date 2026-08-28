# Phase 1 Fixed-Window Chunking

**Phase 1 baseline chunking contract.** Established in Task 1.3. This is
deliberately the crudest defensible chunker — fixed 512-token windows, no
section awareness, no ablations — per `PROJECT_EXECUTION.md`'s Phase 1
framing ("does the whole system work, even badly?"). It is **not** the
frozen Phase 2 production chunk schema (`PROJECT_EXECUTION.md` Task 2.9);
this document describes the Task 1.3 baseline only.

## Purpose

Task 1.2 produced one deterministic Markdown document per filing. Task 1.3
splits each document's body into fixed 512-token windows and persists them
as Parquet — the input format Task 1.4's embedding pipeline will consume.

## Input: corrected Task 1.2 normalized corpus

```text
normalizer_version:            phase1-minimal-v1
artifact path:                  artifacts/normalized/phase1-minimal-v1/
normalization_build_sha256:     fd0abad26111412d792033373e02a0a6a3fb1d0d7a47dbad6063e98c2272244b
development_manifest_sha256:    d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b
document count:                  1,500
```

Both checksums are independently recomputed by
`scripts/chunk_development_corpus.py` on every run — from the live
`artifacts/normalized/phase1-minimal-v1/*.md` files and the live
`results/phase_1_1_development_corpus.json`, never trusted from a stored
value — and the run refuses (`BLOCKED`) if either has drifted.

**Provenance correction note**: Task 1.2 was originally built as
`normalizer_version="v1"`, then corrected to `"phase1-minimal-v1"` in a
dedicated follow-up before any Task 1.3 code was written (commit `b0162fe`,
see `Progress.md`'s "Phase 1.2 Correction" entry). Task 1.3 was built only
against the corrected location.

## User-approved decisions

Every genuinely undefined chunking-semantics question was resolved by
explicit approval before implementation — none were assumed:

| Decision | Approved answer |
|---|---|
| Tokenizer | `BAAI/bge-small-en-v1.5`'s tokenizer, matching Task 1.4's embedding model |
| Overlap / stride | Zero overlap (`stride_tokens = window_size_tokens = 512`) |
| Final partial window | Kept, never dropped or merged |
| What gets chunked | Markdown body only; YAML frontmatter parsed into chunk metadata, never tokenized |
| Special-token counting | 512 content tokens only (`add_special_tokens=False`) |
| Text preservation | Offset-mapping slicing (exact source substrings), not token-id decode |
| 7 empty-source documents | 0 chunks each, an explicit approved exception |
| Parquet layout | Single file (`chunks.parquet`) |
| Chunk schema | Full traceability set (16 columns, listed below) |
| Chunk ID / ordinal | `{document_id}::chunk{ordinal}`, zero-based |

## Tokenizer contract

```text
repository:          BAAI/bge-small-en-v1.5
revision:             5c38ec7c405ec4b44b94cc5a9bb96e735b38267a (fixed snapshot,
                      cached from Task 0.2)
loading:              AutoTokenizer.from_pretrained(..., local_files_only=True)
offline guarantee:    HF_HUB_OFFLINE=1 set before any HF import; required
                      cached asset files (tokenizer.json, tokenizer_config.json,
                      vocab.txt, special_tokens_map.json) precisely checked via
                      huggingface_hub.try_to_load_from_cache() before load -
                      a missing asset raises BLOCKED, never silently downloads
tokenizer kind:       fast (Rust-backed), verified via tokenizer.is_fast -
                      required for return_offsets_mapping support
special tokens:       add_special_tokens=False - the persisted token_count is
                      content tokens only; Task 1.4's own encode() call adds
                      [CLS]/[SEP] at embedding time, not here
```

Why bge-small's tokenizer specifically: `window_size_tokens=512` was already
fixed by `PROJECT_EXECUTION.md`, and `PROJECT_SPEC.md`'s model-inventory
table lists `bge-small-en-v1.5`'s own context length as 512 — the window
size exists to match this exact model. The connection was real but never
stated explicitly in the plan, so it was confirmed by explicit approval
rather than assumed.

## Chunking contract

```text
window_size_tokens:    512
stride_tokens:           512  (overlap_tokens = window_size - stride = 0)
partial_window_policy:    keep - the final window of every document is
                          emitted even if shorter than 512 tokens; never
                          dropped, never merged backward
frontmatter_body_policy:   body_only_frontmatter_to_metadata - YAML
                          frontmatter is parsed into structured chunk
                          columns (cik, company, fiscal_year, ...) and never
                          tokenized/appears in chunk text
heading_behavior:          Markdown "## Item N" headings are ordinary body
                          text - they may appear naturally inside any window,
                          are not treated specially, and are never
                          duplicated or stripped
decode_offset_policy:       offset_mapping_slicing - chunk text is an exact
                          substring of the normalized document body
                          (body_text[offsets[start][0]:offsets[end-1][1]]),
                          not tokenizer.decode(token_ids)
```

**Text preservation, verified directly**: offset-mapping slicing
reconstructs the original source text exactly, character-for-character,
except for pure-whitespace runs the tokenizer's pre-tokenizer does not
attach to any token (e.g. a single trailing space at the very end of a
document, or between two adjacent tokens) - verified empirically on a
synthetic Unicode/punctuation sample before the real build. This never
drops real content, only occasional whitespace between tokens - noted as a
known limitation below rather than silently accepted.

**Window generation is naturally exhaustive**: for zero overlap
(`stride == window_size`), consecutive windows partition the document's
token stream into contiguous, non-overlapping ranges with no gaps -
verified directly (`windows cover every token exactly once`, tested).
Manual inspection additionally confirmed exact token-boundary continuity:
one document's chunk boundary split the word "polyolefin-based" into
`"...polyole"` (end of chunk *k*) and `"fin-based..."` (start of chunk
*k*+1) - no character lost, no character duplicated, a genuine mid-word
split from fixed-window chunking with no section/word-boundary awareness
(exactly as specified - "ignore section boundaries").

## Chunk schema (Phase 1 baseline - not the Phase 2 frozen schema)

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | string | `{document_id}::chunk{ordinal}` |
| `document_id` | string | Task 1.1 identity, == EDGAR-CORPUS `filename` |
| `cik` | int64 | |
| `company` | string | XBRL-sourced provenance, via Task 1.1/1.2 |
| `form_type` | string | always `"10-K"` |
| `fiscal_year` | int32 | |
| `source` | string | always `"edgar_corpus"` |
| `source_filename` | string | == `document_id` |
| `source_split` | string | `train` / `test` / `validation` |
| `ordinal` | int32 | zero-based, sequential per document |
| `text` | string | exact source substring, never empty |
| `token_count` | int32 | content tokens only, `1 <= token_count <= 512` |
| `chunk_config_hash` | string | see below |
| `normalizer_version` | string | `"phase1-minimal-v1"` |
| `normalization_build_sha256` | string | Task 1.2 provenance |
| `development_manifest_sha256` | string | Task 1.1 provenance |

No `accession`, `section_id`, `section_title`, or `table_id` field exists -
Task 1.3 does not know any of these (fixed-window chunking is explicitly
section-unaware, and EDGAR-CORPUS carries no accession field at all - see
`PHASE1_DEVELOPMENT_CORPUS.md`).

## Chunk ID and `chunk_config_hash`

```text
chunk_id:            "{document_id}::chunk{ordinal}", e.g.
                      "1005817_2016.htm::chunk0" - deterministic, globally
                      unique (document_id is already unique per Task 1.1),
                      human-readable
ordinal:              zero-based, sequential within each document

chunk_config_hash algorithm: SHA-256 over canonical JSON
  (json.dumps(config, sort_keys=True, separators=(",",":"))) of the chunk
  config dict - the same convention already established by Task 1.1's
  development_manifest_sha256 and Task 1.2's normalization_build_sha256,
  deliberately reused rather than inventing a new one. No timestamp is
  part of the hashed config.

chunk_config_hash (real build): f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
```

## Output location and layout

```text
artifact path:   artifacts/chunks/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/chunks.parquet
layout:            single Parquet file (not sharded/partitioned) - simplest
                  defensible layout at this corpus size (162,357 rows,
                  ~181.8 MiB), per Phase 1's "develop small" principle
```

Written via `src.storage.get_storage().chunks_dir(chunk_config_hash)` +
`ensure_dir()` - the Task 0.7 storage contract, never a hardcoded path.
Git-ignored generated pipeline state; only a small tracked summary
(`results/phase_1_3_chunking_summary.json`) and config
(`configs/chunk_development_corpus.json`) are committed.

**Overwrite/rebuild policy**: because `chunk_config_hash` is derived from
every semantic decision that affects chunk content (tokenizer
repo+revision, window/stride, all policy fields, and both upstream
checksums), two genuinely different inputs cannot legitimately collide on
the same hash. A rebuild that finds an existing `chunks.parquet` at the
same hash with the same row count is therefore treated as an idempotent
rewrite of identical content, not a conflicting build; a different row
count at the same hash is treated as a real conflict and refused.

## Real build statistics

```text
chunk count:              162,357
documents with >=1 chunk:  1,493
documents with 0 chunks:     7  (the approved empty-source set, exact match verified)

chunks/document:  min=1  median=103  p95=208  max=869
tokens/chunk:      min=1  median=512  p95=512  max=512

full (512-token) chunks:  160,872
partial chunks:              1,485
total emitted tokens:      82,748,156

Parquet artifact size:   190,631,710 bytes (~181.8 MiB)
build runtime:             ~182-199s (two independent runs)
```

The `tokens/chunk` minimum of 1 is real, not a bug: one document's final
partial window happened to land on a single trailing `"."` token after 69
full 512-token windows - inspected directly and confirmed to be genuine
content, not an artifact.

## Empty-source document handling

The 7 documents Task 1.2 established as having zero EDGAR-CORPUS source
text (all `section_*` columns empty-string) produce **0 chunks each** - an
explicit approved exception, not a silent gap:

```text
18498_2018.htm, 1324424_2018.htm, 71691_2016.htm, 1388410_2016.htm,
1388410_2018.htm, 883241_2017.htm, 1110803_2019.htm
```

This falls out naturally from `compute_token_windows(0, ...)` returning an
empty list - no special-casing was needed in the windowing logic itself.
The build script separately cross-checks that the zero-chunk document set
matches this exact approved list (neither more nor fewer), failing loudly
if it ever diverges.

## Determinism

Verified across two independent fresh-process runs:

```text
run 1 chunk_config_hash: f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
run 2 chunk_config_hash: f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
chunk count:              162,357 both runs
chunk_id row order hash:    identical (SHA-256 over the newline-joined
                            chunk_id column, order-sensitive)
chunk text content hash:     identical (SHA-256 over the NUL-joined text
                            column)
```

Logical dataset (row order, chunk IDs, chunk text, metadata) is fully
deterministic; physical Parquet byte-identity across runs was not asserted
(not required by Task 1.3 - only the logical content is a contract).

## Manual inspection

11 documents traced (2 per year 2016-2020, one known-sparse, one
known-empty) from normalized Markdown through to their chunks. All 11/11
passed: correct metadata (cik/fiscal_year), correct chunk count relative to
body length, first chunk always begins with the document's first non-empty
`## Item` heading (including the sparse case, `1004702_2020.md`, whose
first heading is `## Item 1B` since Item 1/1A were empty in source), last
chunk always a partial window (`token_count < 512`), and the known-empty
document (`18498_2018.htm`) confirmed to produce exactly 0 chunks. A
token-boundary continuity check (adjacent chunks of the same document)
confirmed exact, gap-free, non-duplicated text coverage.

## Known limitations

- Deliberately crude Phase 1 baseline - no section-aware splitting, no
  chunk-size ablation, no table awareness. Item headings may be split
  across a chunk boundary just like any other text.
- Fixed windows can split mid-word or mid-sentence with no semantic
  awareness whatsoever (verified directly, see "polyolefin-based" example
  above) - this is the explicit design, not a defect.
- Pure-whitespace runs between tokens (rare - a run of whitespace the
  tokenizer's pre-tokenizer doesn't attach to any token, e.g. a trailing
  space at a document's very end) are not captured by offset-mapping
  slicing. Never real content, confirmed empirically.
- 7 of 1,500 documents produce 0 chunks by design (no EDGAR-CORPUS source
  text existed for them - see `PHASE1_NORMALIZATION.md`).
- This is not the Phase 2 frozen chunk schema (`PROJECT_EXECUTION.md` Task
  2.9) - fields, chunk-ID convention, and hashing approach may all change
  once Phase 2's truth-contract and evidence-alignment requirements are
  known.
- No embedding, retrieval, or evaluation of chunk quality has been
  performed - Task 1.3 only produces the chunk artifact.

## Next consumer

Task 1.4 (Baseline Embedding Pipeline) reads
`artifacts/chunks/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/chunks.parquet`,
loads `BAAI/bge-small-en-v1.5` on GPU, and embeds each chunk's `text`
column.

## Reproducing this build

```bash
python scripts/chunk_development_corpus.py
```

Reads `results/phase_1_1_development_corpus.json` and
`artifacts/normalized/phase1-minimal-v1/*.md` read-only, loads the
tokenizer offline from local cache, performs no network access, writes only
`artifacts/chunks/<chunk_config_hash>/chunks.parquet` (git-ignored),
`results/phase_1_3_chunking_summary.json`, and
`configs/chunk_development_corpus.json` (both tracked). Verified to
reproduce an identical `chunk_config_hash` and identical logical chunk
content across independent fresh-process runs.
