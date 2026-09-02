# Phase 2 Config Hashing and Artifact Versioning

Established in Task 2.10. Freezes the repository-wide configuration/
artifact identity and compatibility contract: which parameters determine
a chunk/embedding/index artifact's identity, how that identity is
hashed, how it is bound into a small manifest sidecar, and how a mismatch
in that chain fails loudly rather than silently reusing a stale artifact.

## Objective

A future developer wiring up a Phase 3 retrieval/evaluation run should
be able to open this document, call `src.artifacts.versioning`, and
answer - before spending a GPU-second or a TEST evaluation run - "are
the chunk, embedding, and index artifacts I'm about to use actually
compatible with my current configuration and with each other?"

## Relationship to `PROJECT_EXECUTION.md`'s Task 2.10 section

`PROJECT_EXECUTION.md`'s Task 2.10 checklist (hash chunking
configuration; version chunk/index directories; store embedding-model
identity; store eval-set version; prevent stale-index/new-config
mismatches; add CI assertions) matches this task's own prompt exactly.
No discrepancy found; nothing required stopping.

## Task 2.9 / 2.10 / 2.11 boundary

- **Task 2.9** freezes chunk-record *semantics* - what a chunk record's
  fields mean (`chunk_uid`, `chunk_local_id`, `chunk_schema_version`,
  field types/nullability). Untouched by this task.
- **Task 2.10** freezes artifact/config *identity and compatibility* -
  how a chunking/embedding/index configuration hashes to an identity, how
  that identity is bound into a manifest, and how an incompatible chain
  fails.
- **Task 2.11** will record experiment *runs* using the identities this
  task exposes (run_id, timestamps, metrics) - not implemented here.

## Canonical serialization

One primitive, `src.artifacts.versioning.canonical_json_bytes()`:

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"),
           ensure_ascii=False, allow_nan=False).encode("utf-8")
```

Key-order independent; mappings/arrays/strings/ints/floats/bools/null
all serialize via plain `json.dumps`. NaN/+-Infinity are rejected by
`allow_nan=False` (raises `ValueError`, wrapped as `ConfigHashError`);
sets, arbitrary objects, callables, and `Path` objects are rejected
because `json.dumps` has no native encoding for them (raises `TypeError`,
also wrapped as `ConfigHashError`) - never silently stringified. A `Path`
that legitimately belongs in a config must be converted to an explicit
portable string first by the caller (absolute machine paths should
normally not be hash inputs at all).

`semantic_hash(payload) = SHA256(canonical_json_bytes(payload)).hexdigest()`.
Never Python's `hash()`, `repr()`, or `pickle`.

## Semantic vs. provenance fields

Semantic configuration affects artifact identity (tokenizer/model
identity, chunk size, overlap, partial-window policy, embedding
normalization, distance metric, index type). Provenance explains
when/where an artifact was built (`created_at_utc`, `git_sha`) and must
never change a semantic hash. `PROVENANCE_FIELDS = ("created_at_utc",
"git_sha")` are excluded from `manifest_semantic_fingerprint()`, and were
never part of any chunk-config dict in the first place (Phase 1's
`build_chunk_config()` already omits them - verified directly).

## Chunk config hashing

`src/chunk/fixed_window.py`'s pre-existing `chunk_config_hash()` already
implemented the correct canonical-JSON-then-SHA-256 primitive. Rather
than reimplementing it, it now delegates to
`src.artifacts.versioning.compute_chunk_config_hash()` - exactly one
canonical serialization/hashing implementation exists project-wide, and
`chunk_config_hash()`'s external signature/return value is unchanged.

**Legacy compatibility (Section 11 requirement)**: independently
recomputing the frozen Phase 1 hash from the real
`configs/chunk_development_corpus.json` via the new centralized utility
reproduces
`f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd`
byte-for-byte (the config content is pure ASCII, so `ensure_ascii=False`
vs. the original inline implementation's default `ensure_ascii=True`
produces identical bytes) - **legacy compatibility: PASS**. No STOP
condition triggered.

`chunk_config_hash` captures: normalizer version + normalization/
development-manifest hashes, tokenizer repo/revision, window size,
overlap/stride, special-token policy, partial-window policy,
frontmatter/body policy, decode-offset policy, and the (Phase-1-internal)
`chunk_schema_version` string. It deliberately never includes batch
size, output path, `created_at`, GPU name, or Git SHA.

## Chunk directory versioning

Unchanged: `storage.chunks_dir(chunk_config_hash)` ->
`artifacts/chunks/<chunk_config_hash>/`. Same config -> same directory;
different config -> a different directory; no accidental overwrite
(Phase 1's `write_parquet()` already refuses to silently overwrite a
conflicting row count). The Phase 1 chunk Parquet was **not** rebuilt or
rewritten.

## Chunk artifact manifest

`scripts/audit_artifact_compatibility.py` writes a verified sidecar
`artifacts/chunks/<hash>/manifest.json` next to the existing frozen
Parquet (a new file only - the Parquet itself is read-only throughout):

```json
{
  "artifact_manifest_version": 1,
  "artifact_type": "chunks",
  "chunk_schema_version": 1,
  "chunk_config_hash": "f1dc04d4...",
  "chunk_config": { ... the real frozen config dict ... },
  "row_count": 162357,
  "created_at_utc": "...", "git_sha": "...",
  "provenance_label": "verified historical artifact provenance"
}
```

`provenance_label` is set only when the manifest describes a
historical artifact validated after the fact - it is never claimed to
have existed at original Phase 1 build time.

## Embedding identity

`src/embeddings/bge.py` gained `embedding_identity()`, built from its own
already-frozen constants:

```json
{
  "embedding_identity_version": 1,
  "model_repository": "BAAI/bge-small-en-v1.5",
  "model_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
  "embedding_dimension": 384,
  "vector_dtype": "float32",
  "normalize_embeddings": true,
  "passage_convention": "raw_text_no_instruction",
  "query_convention": "prepend:Represent this sentence for searching relevant passages: "
}
```

`embedding_identity_hash = src.artifacts.versioning.embedding_identity_hash(identity)`.
This is a structured identity, not merely the sanitized filesystem label
`"BAAI--bge-small-en-v1.5"` - it distinguishes same-repository-different-
revision, different dimension, different normalization policy, and
different passage/query conventions from one another, none of which the
sanitized label alone can.

`src.artifacts.versioning.compute_embedding_identity(...)` is
model-agnostic (generic dict builder + validator); `bge.py` is the one
place that supplies the real Phase 1 BGE values, so no magic
strings/numbers are duplicated between the two modules.

## Embedding artifact manifest

`artifacts/embeddings/<chunk_config_hash>/<model_repo>/manifest.json`:

```json
{
  "artifact_manifest_version": 1,
  "artifact_type": "embeddings",
  "chunk_schema_version": 1,
  "chunk_config_hash": "f1dc04d4...",
  "embedding_identity": { ... },
  "embedding_identity_hash": "b39a67c9...",
  "row_count": 162357,
  "provenance_label": "verified historical artifact provenance"
}
```

States exactly which chunk artifact/config it was built from
(`chunk_config_hash`), matching Section 17's requirement.

## Index identity

`src/index/lancedb_index.py` gained `INDEX_TYPE = "exact_flat"` and
`index_identity()`, binding the index to chunk semantics + embedding
semantics + the index/table configuration itself:

```json
{
  "index_identity_version": 1,
  "chunk_schema_version": 1,
  "chunk_config_hash": "f1dc04d4...",
  "embedding_identity_hash": "b39a67c9...",
  "distance_metric": "cosine",
  "index_type": "exact_flat",
  "table_name": "chunks"
}
```

`index_identity_hash = src.artifacts.versioning.compute_index_identity_hash(identity)`.
`index_type` is the deliberate Phase-3 extension point (`"ivf_pq"`,
`"fts"`, `"hybrid"`, ...); `compute_index_identity()` also accepts an
optional `extra` mapping for a later index type's own identity-bearing
parameters (e.g. IVF `nlist`/`nprobe`) without changing the function's
signature. None of this is implemented for Phase 3 yet - only the
contract is established now.

## Index artifact manifest

`artifacts/indexes/<chunk_config_hash>/<model_repo>/manifest.json`,
mirroring the embedding manifest shape plus `index_identity`/
`index_identity_hash`. Binds the index to both the chunk artifact and the
embedding artifact it was built from.

## Storage layout - backward compatibility

`src.storage.StoragePaths` keeps `chunks_dir()`, `embeddings_dir()`, and
`index_dir()` **completely unchanged** - they still key on
`(chunk_config_hash, embedding_model_repo_string)`, exactly Phase 1's
existing on-disk layout (`artifacts/embeddings/<hash>/BAAI--bge-small-en-v1.5/`,
`artifacts/indexes/<hash>/BAAI--bge-small-en-v1.5/`). Nothing was moved,
renamed, or rewritten.

Two new methods were added instead, for anything built going forward
under Task 2.10's tighter identity contract:

```python
storage.embeddings_dir_for_identity(chunk_config_hash, embedding_identity_hash)
storage.index_dir_for_identity(chunk_config_hash, embedding_identity_hash)
```

These key on the full `embedding_identity_hash` (a SHA-256, validated
before use via `validate_sha256()`) rather than a raw model-repository
string - collision-proof by construction even when a future Phase 3
config reuses the same model repository name with a different revision,
dimension, or normalization policy (Section 18's exact concern). The
existing `embeddings_dir()`/`index_dir()` are the right choice only for
consuming/extending Phase 1's historical artifacts; any new artifact
identity going forward should use the `*_for_identity` variants.

No `artifacts/chunks/latest`, "newest directory by timestamp," or
"highest lexical hash" semantics exist anywhere - every path is derived
deterministically from an explicit identity, never implicitly picked.

## Eval-set version binding

Reused, never recomputed, from the already-frozen Task 2.3/2.4
artifacts:

```text
eval_set_version:  phase2-v1              (results/phase_2_3_evaluation_dataset_summary.json)
dataset_sha256:    bf85e1a1...            (same file)
split_version:     phase2-split-v1        (results/phase_2_4_split_summary.json)
dev_sha256:        2818e6a0...
test_sha256:       6ce8bf8d...
ci_sha256:         adc54462...
```

`test_sha256` is a frozen digest already committed to
`phase_2_4_split_summary.json` from Task 2.4 - reading it does not
materialize or access the protected TEST question corpus.
`scripts/audit_artifact_compatibility.py` reads only these two existing
tracked result files; it opens no TEST payload. Official TEST evaluation
runs consumed remain **0/3** (verified directly against
`artifacts/eval/eval.duckdb`'s `test_access_log`: 2 rows, both
`kind='build_validation'`, `run_number IS NULL`).

## Manifest contract

`ARTIFACT_MANIFEST_VERSION = 1`, tracked separately from
`chunk_schema_version` (a manifest-layout change and a chunk-semantics
change are independent concepts - Section 34). `validate_artifact_manifest(manifest, artifact_type)`
checks: `artifact_type` matches what was requested, `artifact_manifest_version`
is supported, every required field for that artifact type is present, and
every hash-shaped field is a lowercase 64-hex-character SHA-256 digest
(malformed hashes are rejected outright, never silently lowercased/
truncated/padded).

## Compatibility enforcement

`ArtifactCompatibility(chunk_schema_version, chunk_config_hash,
embedding_identity_hash, index_identity_hash, eval_set_version)` is the
small typed object representing what a retrieval/evaluation run will
need, known *before* the run begins. It deliberately excludes Task 2.11
run-level fields (`run_id`, timestamps, metrics).

`assert_artifact_compatible(compatibility, chunk_manifest=..., embedding_manifest=...,
index_manifest=..., manifest_eval_set_version=...)` validates every
manifest passed to it and raises `ArtifactCompatibilityError` - never a
warning, never a silent rebuild, never "pick the newest matching
directory" - the instant any of the following disagree:

- chunk schema version
- chunk config hash (at the chunk, embedding, or index layer)
- embedding identity hash (at the embedding or index layer)
- index identity hash
- eval_set_version
- **row_count across the chunk/embedding/index chain** (a same-source
  artifact chain must carry the same row count end-to-end; a silent
  row-count drift is exactly the kind of stale-artifact bug this task
  exists to catch)

A manifest simply omitted from a given call is not checked - callers
validate whichever expensive component they are about to load next
(Section 25: a manifest-only check needs no GPU, no model load, no large
index open).

## Real Phase 1 chain audit

`scripts/audit_artifact_compatibility.py` (read-only against the real
artifacts, no model load, no GPU):

```text
chunk config hash legacy compatibility:  PASS
chunk artifact:      162,357 rows
embedding artifact:  162,357 rows, identity_hash b39a67c9...
index artifact:      162,357 rows, 0 ANN indexes, identity_hash ace70ee6...
eval_set_version:    phase2-v1 / split phase2-split-v1
official TEST runs used: 0/3
valid chain compatibility: PASS
```

Five negative self-checks also run against tampered copies of the same
real manifests (never against the real artifacts themselves): stale
chunk hash, stale embedding identity, stale index identity, schema-
version mismatch, eval-version mismatch - all five correctly raise
`ArtifactCompatibilityError`. Full results in
`results/phase_2_10_artifact_versioning.json`.

## CI assertions

`tests/test_artifact_versioning.py` (83 tests: 81 portable + 2
`local_data`-marked) covers canonical serialization, chunk-config
hashing (including the historical-hash reproduction test), embedding
identity, index identity, manifest validation, all required negative
compatibility scenarios from Section 31 (window size, overlap, tokenizer
revision, embedding repository/revision/dimension/normalization,
distance metric, index type, chunk schema version, eval-set version,
malformed hash, missing manifest field, wrong artifact type, row-count
mismatch), determinism (key-order independence, Unicode, provenance
independence), and storage-path integration (different identities ->
different paths, legacy paths still resolve, traversal protection
intact). The two `local_data` tests replay the exact real Phase 1 chain
audit above without model loading. CI needs no 26 GB dataset - portable
tests use small synthetic configs/manifests exclusively.

## `src/artifacts/` package note

`src/artifacts/versioning.py` is the new package. The repository's
existing `.gitignore` had an unanchored `artifacts/` rule (intended for
the top-level generated-artifact root) that would have also matched
`src/artifacts/` and silently excluded this tracked package from any
commit. Fixed narrowly by anchoring that one rule to the repo root
(`/artifacts/`) - verified directly that `artifacts/` (generated) is
still fully ignored and `src/artifacts/*.py` is now tracked.

## Known limitations

- The Phase 1 baseline's `chunk_config_hash` (`f1dc04d4...`) was computed
  and frozen before this task existed; Task 2.10 verifies and formalizes
  it rather than re-deriving a "more correct" value.
- `index_identity`'s `index_type="exact_flat"` and `extra` field are an
  extensibility contract only - no IVF_PQ/FTS/hybrid index type is
  implemented by this task.
- `embeddings_dir_for_identity()`/`index_dir_for_identity()` are not yet
  called by any Phase 1/2 build script (Phase 1's own scripts correctly
  keep using the original `embeddings_dir()`/`index_dir()` for their
  existing on-disk artifacts) - they exist for a future Phase 3 build to
  adopt when a genuinely new embedding/index identity is introduced.
- The baseline retriever (`src/retrieval/baseline.py`) was not modified;
  `assert_artifact_compatible()` is available for a future caller to
  invoke before retrieval, but no call site was added here (Section 38:
  "provide a way to assert," not "wire it into the retriever's runtime
  path" - ranking/score semantics/top-k/query prefix/generation are all
  unchanged).

## Task 2.11 boundary

Task 2.10 exposes identities (`ArtifactCompatibility` and friends) that
Task 2.11 will bind into per-run records (`run_id`, retrieval/reranker/
generation config, timestamps, metrics). No run-logging database or
schema is implemented here.
