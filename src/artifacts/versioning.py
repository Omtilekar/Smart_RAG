"""Task 2.10 - the one authoritative configuration-hashing and
artifact-versioning utility.

Central rule (task's own Final Principle):

    Configuration determines artifact identity.
    Artifact provenance must be inspectable.
    Incompatible artifacts must never be silently reused.

This module owns exactly three semantic identities:

    chunk_config_hash        "How were chunks generated?"
    embedding identity/hash  "Which exact embedding semantics produced vectors?"
    index identity/hash      "Which chunk/vector/index configuration produced
                               this searchable index?"

It does NOT redefine Task 2.9's `chunk_uid`/`chunk_local_id`/
`chunk_schema_version` (src/chunk/metadata_schema.py, untouched), and it
does NOT redefine any already-frozen Task 1.x/2.1-2.9 hash (development
manifest hash, normalization build hash, evaluation dataset hash, split
hash, tag registry hash, truth contract hash, evaluation schema hash) -
those are reused/reused-by-reference, never recomputed with a different
algorithm here (Section 20: each identifier answers exactly one
question; do not overload one "config_hash" to mean all of them).

`src/chunk/fixed_window.py`'s pre-existing `chunk_config_hash()` already
implemented the same canonical-JSON-then-SHA-256 primitive correctly
(verified: independently recomputing Phase 1's frozen hash from
configs/chunk_development_corpus.json via this module's
`semantic_hash()` reproduces
f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd
exactly - legacy compatibility: PASS) - it is preserved as a thin
delegating wrapper, not reimplemented, so exactly one canonical
serialization/hashing implementation exists project-wide.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ARTIFACT_MANIFEST_VERSION = 1
ARTIFACT_TYPES: tuple[str, ...] = ("chunks", "embeddings", "index")

# Fields that describe *when/where* an artifact was built, never *what it
# means* - must never influence a semantic hash (Section 9/35).
PROVENANCE_FIELDS: tuple[str, ...] = ("created_at_utc", "git_sha")


class ConfigHashError(ValueError):
    """Raised when a payload cannot be canonically, machine-independently
    serialized - never silently stringified or coerced."""


class ArtifactManifestError(ValueError):
    """Raised for a malformed, incomplete, or unsupported-version artifact
    manifest."""


class ArtifactCompatibilityError(ValueError):
    """Raised the moment two artifacts in a chunk -> embedding -> index
    chain (or an eval binding) disagree on identity. Never a warning, never
    a silent fallback to another artifact."""


# --------------------------------------------------------------- canonical serialization

def canonical_json_bytes(payload: Any) -> bytes:
    """The one canonical serialization contract (Section 7): key-order
    independent, machine-independent, UTF-8 encoded. Delegates NaN/
    +-Infinity rejection and unsupported-type rejection (sets, Path
    objects, callables, arbitrary objects) to `json.dumps` itself
    (`allow_nan=False` raises ValueError on non-finite floats; anything
    without a native JSON representation raises TypeError) rather than
    hand-rolling a second check - both are wrapped into one clear
    `ConfigHashError` here so every caller sees one exception type."""
    try:
        text = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ConfigHashError(f"payload is not canonically serializable: {exc}") from exc
    return text.encode("utf-8")


def semantic_hash(payload: Any) -> str:
    """SHA-256 hex digest over `canonical_json_bytes(payload)`. Never
    Python's `hash()`, never `repr()`, never `pickle`."""
    import hashlib
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def validate_sha256(value: str, field_name: str) -> None:
    """Lowercase, exactly-64-hex-character SHA-256 shape only - rejects
    malformed input outright rather than silently lowercasing/truncating/
    padding it (Section 33)."""
    if not isinstance(value, str) or not SHA256_RE.match(value):
        raise ConfigHashError(f"{field_name} is not a lowercase 64-hex-character SHA-256 digest: {value!r}")


# --------------------------------------------------------------- chunk config hash

def compute_chunk_config_hash(config: Mapping[str, Any]) -> str:
    """Canonical chunk-configuration semantic hash - the single
    implementation `src.chunk.fixed_window.chunk_config_hash()` now
    delegates to. Captures every parameter that could change chunk
    boundaries/content/IDs/token counts (tokenizer identity, window size,
    stride, partial-window policy, frontmatter/body policy, source
    representation identity); excludes provenance (no timestamps/git SHA
    ever belong in a chunk config dict - Phase 1's `build_chunk_config()`
    already omits them)."""
    return semantic_hash(config)


# --------------------------------------------------------------- embedding identity

REQUIRED_EMBEDDING_IDENTITY_FIELDS: tuple[str, ...] = (
    "model_repository", "model_revision", "embedding_dimension",
    "vector_dtype", "normalize_embeddings", "passage_convention", "query_convention",
)


def compute_embedding_identity(*, model_repository: str, model_revision: str,
                                embedding_dimension: int, vector_dtype: str,
                                normalize_embeddings: bool, passage_convention: str,
                                query_convention: str) -> dict:
    """Structured embedding-model semantic identity (Section 15/16) -
    deliberately more than a sanitized model-name path label. Distinguishes
    same-repository-different-revision, different dimension, different
    normalization policy, and different passage/query conventions from one
    another. Generic/model-agnostic on purpose - callers supply the exact
    values from their own model wrapper's frozen constants (e.g.
    `src.embeddings.bge`) rather than this module guessing/duplicating
    them."""
    return {
        "embedding_identity_version": 1,
        "model_repository": model_repository,
        "model_revision": model_revision,
        "embedding_dimension": embedding_dimension,
        "vector_dtype": vector_dtype,
        "normalize_embeddings": normalize_embeddings,
        "passage_convention": passage_convention,
        "query_convention": query_convention,
    }


def embedding_identity_hash(identity: Mapping[str, Any]) -> str:
    missing = [f for f in REQUIRED_EMBEDDING_IDENTITY_FIELDS if f not in identity]
    if missing:
        raise ArtifactManifestError(f"embedding identity missing required fields: {missing}")
    return semantic_hash(identity)


# --------------------------------------------------------------- index identity

REQUIRED_INDEX_IDENTITY_FIELDS: tuple[str, ...] = (
    "chunk_schema_version", "chunk_config_hash", "embedding_identity_hash",
    "distance_metric", "index_type", "table_name",
)


def compute_index_identity(*, chunk_schema_version: int, chunk_config_hash: str,
                            embedding_identity_hash: str, distance_metric: str,
                            index_type: str, table_name: str,
                            extra: Mapping[str, Any] | None = None) -> dict:
    """Binds an index to chunk semantics + embedding semantics + the
    index/table configuration itself (Section 19). `index_type` is the
    deliberate extension point for Phase 3 (`"ivf_pq"`, `"fts"`,
    `"hybrid"`, ...) - Phase 1's baseline is `"exact_flat"` (no ANN index,
    matching `src.index.lancedb_index`'s frozen contract). `extra` allows a
    later index type to add its own identity-bearing parameters (e.g. IVF
    nlist/nprobe) without changing this function's signature."""
    validate_sha256(chunk_config_hash, "chunk_config_hash")
    validate_sha256(embedding_identity_hash, "embedding_identity_hash")
    identity = {
        "index_identity_version": 1,
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "embedding_identity_hash": embedding_identity_hash,
        "distance_metric": distance_metric,
        "index_type": index_type,
        "table_name": table_name,
    }
    if extra:
        identity["extra"] = dict(extra)
    return identity


def compute_index_identity_hash(identity: Mapping[str, Any]) -> str:
    missing = [f for f in REQUIRED_INDEX_IDENTITY_FIELDS if f not in identity]
    if missing:
        raise ArtifactManifestError(f"index identity missing required fields: {missing}")
    return semantic_hash(identity)


# --------------------------------------------------------------- manifests

def _manifest_semantic_fields(manifest: Mapping[str, Any]) -> dict:
    """Every manifest field except the non-semantic provenance ones
    (Section 35) - used only to demonstrate/test that provenance never
    changes a manifest's meaning, never persisted as a separate value."""
    return {k: v for k, v in manifest.items() if k not in PROVENANCE_FIELDS}


def manifest_semantic_fingerprint(manifest: Mapping[str, Any]) -> str:
    """SHA-256 over the manifest with `created_at_utc`/`git_sha` excluded.
    Two manifests built from identical semantic configuration but on
    different machines/dates produce the same fingerprint."""
    return semantic_hash(_manifest_semantic_fields(manifest))


def build_chunk_manifest(*, chunk_schema_version: int, chunk_config_hash: str,
                          chunk_config: Mapping[str, Any], row_count: int,
                          source_identity: str | None = None,
                          created_at_utc: str | None = None, git_sha: str | None = None,
                          verified_historical: bool = False) -> dict:
    validate_sha256(chunk_config_hash, "chunk_config_hash")
    manifest = {
        "artifact_manifest_version": ARTIFACT_MANIFEST_VERSION,
        "artifact_type": "chunks",
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "chunk_config": dict(chunk_config),
        "row_count": row_count,
        "created_at_utc": created_at_utc,
        "git_sha": git_sha,
    }
    if source_identity is not None:
        manifest["source_identity"] = source_identity
    if verified_historical:
        manifest["provenance_label"] = "verified historical artifact provenance"
    return manifest


def build_embedding_manifest(*, chunk_schema_version: int, chunk_config_hash: str,
                              embedding_identity: Mapping[str, Any],
                              embedding_identity_hash_value: str, row_count: int,
                              created_at_utc: str | None = None, git_sha: str | None = None,
                              verified_historical: bool = False) -> dict:
    validate_sha256(chunk_config_hash, "chunk_config_hash")
    validate_sha256(embedding_identity_hash_value, "embedding_identity_hash")
    manifest = {
        "artifact_manifest_version": ARTIFACT_MANIFEST_VERSION,
        "artifact_type": "embeddings",
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "embedding_identity": dict(embedding_identity),
        "embedding_identity_hash": embedding_identity_hash_value,
        "row_count": row_count,
        "created_at_utc": created_at_utc,
        "git_sha": git_sha,
    }
    if verified_historical:
        manifest["provenance_label"] = "verified historical artifact provenance"
    return manifest


def build_index_manifest(*, chunk_schema_version: int, chunk_config_hash: str,
                          embedding_identity_hash_value: str, index_identity: Mapping[str, Any],
                          index_identity_hash_value: str, row_count: int,
                          created_at_utc: str | None = None, git_sha: str | None = None,
                          verified_historical: bool = False) -> dict:
    validate_sha256(chunk_config_hash, "chunk_config_hash")
    validate_sha256(embedding_identity_hash_value, "embedding_identity_hash")
    validate_sha256(index_identity_hash_value, "index_identity_hash")
    manifest = {
        "artifact_manifest_version": ARTIFACT_MANIFEST_VERSION,
        "artifact_type": "index",
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "embedding_identity_hash": embedding_identity_hash_value,
        "index_identity": dict(index_identity),
        "index_identity_hash": index_identity_hash_value,
        "row_count": row_count,
        "created_at_utc": created_at_utc,
        "git_sha": git_sha,
    }
    if verified_historical:
        manifest["provenance_label"] = "verified historical artifact provenance"
    return manifest


_REQUIRED_MANIFEST_FIELDS: dict[str, tuple[str, ...]] = {
    "chunks": ("artifact_manifest_version", "artifact_type", "chunk_schema_version",
               "chunk_config_hash", "chunk_config", "row_count"),
    "embeddings": ("artifact_manifest_version", "artifact_type", "chunk_schema_version",
                   "chunk_config_hash", "embedding_identity", "embedding_identity_hash", "row_count"),
    "index": ("artifact_manifest_version", "artifact_type", "chunk_schema_version",
              "chunk_config_hash", "embedding_identity_hash", "index_identity",
              "index_identity_hash", "row_count"),
}

_HASH_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "chunks": ("chunk_config_hash",),
    "embeddings": ("chunk_config_hash", "embedding_identity_hash"),
    "index": ("chunk_config_hash", "embedding_identity_hash", "index_identity_hash"),
}


def validate_artifact_manifest(manifest: Mapping[str, Any], expected_artifact_type: str) -> None:
    """Validates manifest shape/version/required-fields/hash-format only -
    never artifact content. Raises ArtifactManifestError with a specific,
    actionable message on the first violation (Section 34/36)."""
    if expected_artifact_type not in ARTIFACT_TYPES:
        raise ArtifactManifestError(f"unknown artifact_type requested: {expected_artifact_type!r}")

    required = _REQUIRED_MANIFEST_FIELDS[expected_artifact_type]
    missing = [f for f in required if f not in manifest]
    if missing:
        raise ArtifactManifestError(f"manifest missing required field(s) for {expected_artifact_type!r}: {missing}")

    actual_type = manifest["artifact_type"]
    if actual_type != expected_artifact_type:
        raise ArtifactManifestError(f"wrong artifact type: expected {expected_artifact_type!r}, got {actual_type!r}")

    version = manifest["artifact_manifest_version"]
    if version != ARTIFACT_MANIFEST_VERSION:
        raise ArtifactManifestError(
            f"unsupported artifact_manifest_version {version!r} (this loader supports {ARTIFACT_MANIFEST_VERSION})"
        )

    for hash_field in _HASH_FIELDS_BY_TYPE[expected_artifact_type]:
        try:
            validate_sha256(manifest[hash_field], hash_field)
        except ConfigHashError as exc:
            raise ArtifactManifestError(str(exc)) from exc


# --------------------------------------------------------------- compatibility

def assert_chunk_manifest_compatible(manifest: Mapping[str, Any], *,
                                      expected_chunk_schema_version: int,
                                      expected_chunk_config_hash: str) -> None:
    validate_artifact_manifest(manifest, "chunks")
    if manifest["chunk_schema_version"] != expected_chunk_schema_version:
        raise ArtifactCompatibilityError(
            f"chunk artifact schema_version={manifest['chunk_schema_version']}, "
            f"current loader requires schema_version={expected_chunk_schema_version}"
        )
    if manifest["chunk_config_hash"] != expected_chunk_config_hash:
        raise ArtifactCompatibilityError(
            f"chunk artifact expects chunk hash {manifest['chunk_config_hash']}, "
            f"current config computes {expected_chunk_config_hash}"
        )


def assert_embedding_manifest_compatible(manifest: Mapping[str, Any], *,
                                          expected_chunk_config_hash: str,
                                          expected_embedding_identity_hash: str) -> None:
    validate_artifact_manifest(manifest, "embeddings")
    if manifest["chunk_config_hash"] != expected_chunk_config_hash:
        raise ArtifactCompatibilityError(
            f"embedding artifact was built from chunk hash {manifest['chunk_config_hash']}, "
            f"current config computes {expected_chunk_config_hash}"
        )
    if manifest["embedding_identity_hash"] != expected_embedding_identity_hash:
        raise ArtifactCompatibilityError(
            f"embedding artifact identity {manifest['embedding_identity_hash']} != "
            f"current configured embedding identity {expected_embedding_identity_hash}"
        )


def assert_index_manifest_compatible(manifest: Mapping[str, Any], *,
                                      expected_chunk_config_hash: str,
                                      expected_embedding_identity_hash: str,
                                      expected_index_identity_hash: str) -> None:
    validate_artifact_manifest(manifest, "index")
    if manifest["chunk_config_hash"] != expected_chunk_config_hash:
        raise ArtifactCompatibilityError(
            f"index expects chunk hash {manifest['chunk_config_hash']}, "
            f"current config computes {expected_chunk_config_hash}"
        )
    if manifest["embedding_identity_hash"] != expected_embedding_identity_hash:
        raise ArtifactCompatibilityError(
            f"index expects embedding identity {manifest['embedding_identity_hash']}, "
            f"current configured embedding identity is {expected_embedding_identity_hash}"
        )
    if manifest["index_identity_hash"] != expected_index_identity_hash:
        raise ArtifactCompatibilityError(
            f"index identity {manifest['index_identity_hash']} != "
            f"current configured index identity {expected_index_identity_hash}"
        )


@dataclass(frozen=True)
class ArtifactCompatibility:
    """The identity of every artifact a retrieval/evaluation run will need,
    known BEFORE that run begins (Section 23). Deliberately excludes
    Task 2.11 run-level fields (run_id, timestamp, metrics) - this object
    answers "are these artifacts compatible", not "what happened in this
    run"."""
    chunk_schema_version: int
    chunk_config_hash: str
    embedding_identity_hash: str
    index_identity_hash: str
    eval_set_version: str


def _assert_row_counts_consistent(**named_manifests: Mapping[str, Any] | None) -> None:
    """A chunk/embedding/index artifact chain built from the same source
    must carry the same row_count end-to-end - a silent row-count drift
    (e.g. an index built from a stale, differently-sized embedding
    artifact) is exactly the kind of stale-artifact bug this task exists
    to catch (Section 31 #15)."""
    present = {name: m["row_count"] for name, m in named_manifests.items() if m is not None and "row_count" in m}
    if len(set(present.values())) > 1:
        raise ArtifactCompatibilityError(f"row_count mismatch across artifact chain: {present}")


def assert_artifact_compatible(compatibility: ArtifactCompatibility, *,
                                chunk_manifest: Mapping[str, Any] | None = None,
                                embedding_manifest: Mapping[str, Any] | None = None,
                                index_manifest: Mapping[str, Any] | None = None,
                                manifest_eval_set_version: str | None = None) -> None:
    """Runs every compatibility check the caller has manifests for. A
    manifest omitted here is simply not checked (callers validate before
    loading whichever expensive components they are about to load -
    Section 25); this never assumes an omitted manifest is compatible."""
    _assert_row_counts_consistent(chunk=chunk_manifest, embedding=embedding_manifest, index=index_manifest)
    if chunk_manifest is not None:
        assert_chunk_manifest_compatible(
            chunk_manifest,
            expected_chunk_schema_version=compatibility.chunk_schema_version,
            expected_chunk_config_hash=compatibility.chunk_config_hash,
        )
    if embedding_manifest is not None:
        assert_embedding_manifest_compatible(
            embedding_manifest,
            expected_chunk_config_hash=compatibility.chunk_config_hash,
            expected_embedding_identity_hash=compatibility.embedding_identity_hash,
        )
    if index_manifest is not None:
        assert_index_manifest_compatible(
            index_manifest,
            expected_chunk_config_hash=compatibility.chunk_config_hash,
            expected_embedding_identity_hash=compatibility.embedding_identity_hash,
            expected_index_identity_hash=compatibility.index_identity_hash,
        )
    if manifest_eval_set_version is not None and manifest_eval_set_version != compatibility.eval_set_version:
        raise ArtifactCompatibilityError(
            f"eval artifact says eval_set_version={manifest_eval_set_version!r}, "
            f"requested={compatibility.eval_set_version!r}"
        )
