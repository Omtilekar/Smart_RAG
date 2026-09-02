"""Task 2.10 - tests for src.artifacts.versioning (config hashing,
identity, manifests, compatibility enforcement)."""

from __future__ import annotations

import json
import math

import pytest

from src.artifacts import versioning as v
from src.chunk.fixed_window import chunk_config_hash as legacy_chunk_config_hash

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

PHASE1_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"


# --------------------------------------------------------------- canonical serialization

class TestCanonicalSerialization:
    def test_key_order_independence(self):
        a = v.canonical_json_bytes({"x": 1, "y": 2})
        b = v.canonical_json_bytes({"y": 2, "x": 1})
        assert a == b

    def test_nested_structures(self):
        payload = {"a": [1, 2, {"b": "c"}], "d": {"e": [3, 4]}}
        assert v.canonical_json_bytes(payload) == v.canonical_json_bytes(json.loads(json.dumps(payload)))

    def test_unicode_preserved_not_escaped(self):
        payload = {"company": "Ünïcödé Cörp™"}
        blob = v.canonical_json_bytes(payload)
        assert "Ünïcödé Cörp™".encode("utf-8") in blob

    def test_unicode_key_order_independence(self):
        a = v.canonical_json_bytes({"café": 1, "naïve": 2})
        b = v.canonical_json_bytes({"naïve": 2, "café": 1})
        assert a == b

    def test_nan_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": float("nan")})

    def test_positive_infinity_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": float("inf")})

    def test_negative_infinity_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": float("-inf")})

    def test_set_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": {1, 2, 3}})

    def test_arbitrary_object_rejected(self):
        class Thing:
            pass
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": Thing()})

    def test_callable_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": lambda: 1})

    def test_path_object_rejected(self):
        from pathlib import Path
        with pytest.raises(v.ConfigHashError):
            v.canonical_json_bytes({"x": Path("/tmp/foo")})

    def test_path_normalized_to_string_accepted(self):
        from pathlib import Path
        v.canonical_json_bytes({"x": str(Path("some/logical/path"))})

    def test_mappings_arrays_strings_ints_floats_bools_null(self):
        payload = {"m": {"k": 1}, "arr": [1, 2, 3], "s": "text", "i": 42, "f": 1.5, "b": True, "n": None}
        v.canonical_json_bytes(payload)

    def test_semantic_hash_is_64_hex(self):
        h = v.semantic_hash({"a": 1})
        assert len(h) == 64
        assert v.SHA256_RE.match(h)

    def test_semantic_hash_deterministic_key_order(self):
        assert v.semantic_hash({"x": 1, "y": 2}) == v.semantic_hash({"y": 2, "x": 1})


# --------------------------------------------------------------- hash validation

class TestValidateSha256:
    def test_valid_accepted(self):
        v.validate_sha256(HASH_A, "field")

    @pytest.mark.parametrize("bad", ["A" * 64, "z" * 64, "abc", "", "g" * 64, "a" * 63, "a" * 65])
    def test_malformed_rejected(self, bad):
        with pytest.raises(v.ConfigHashError):
            v.validate_sha256(bad, "field")

    def test_non_string_rejected(self):
        with pytest.raises(v.ConfigHashError):
            v.validate_sha256(12345, "field")


# --------------------------------------------------------------- chunk config hash

class TestChunkConfigHash:
    def test_deterministic(self):
        config = {"a": 1, "b": [1, 2]}
        assert v.compute_chunk_config_hash(config) == v.compute_chunk_config_hash(config)

    def test_semantic_change_changes_hash(self):
        h1 = v.compute_chunk_config_hash({"window_size_tokens": 512})
        h2 = v.compute_chunk_config_hash({"window_size_tokens": 256})
        assert h1 != h2

    def test_key_order_does_not_change_hash(self):
        h1 = v.compute_chunk_config_hash({"a": 1, "b": 2})
        h2 = v.compute_chunk_config_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_historical_phase1_hash_reproduces_exactly(self):
        import pathlib
        config = json.loads((pathlib.Path("configs") / "chunk_development_corpus.json").read_text(encoding="utf-8"))
        assert v.compute_chunk_config_hash(config) == PHASE1_CHUNK_CONFIG_HASH

    def test_tokenizer_revision_change_changes_hash(self):
        a = v.compute_chunk_config_hash({"tokenizer": {"repo": "x", "revision": "rev1"}})
        b = v.compute_chunk_config_hash({"tokenizer": {"repo": "x", "revision": "rev2"}})
        assert a != b

    def test_overlap_change_changes_hash(self):
        a = v.compute_chunk_config_hash({"window_size_tokens": 512, "overlap_tokens": 0})
        b = v.compute_chunk_config_hash({"window_size_tokens": 512, "overlap_tokens": 64})
        assert a != b

    def test_fixed_window_delegates_to_centralized_utility(self):
        import pathlib
        config = json.loads((pathlib.Path("configs") / "chunk_development_corpus.json").read_text(encoding="utf-8"))
        assert legacy_chunk_config_hash(config) == v.compute_chunk_config_hash(config)


# --------------------------------------------------------------- embedding identity

def make_embedding_identity(**overrides) -> dict:
    base = dict(
        model_repository="BAAI/bge-small-en-v1.5",
        model_revision="5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        embedding_dimension=384,
        vector_dtype="float32",
        normalize_embeddings=True,
        passage_convention="raw_text_no_instruction",
        query_convention="prepend:x",
    )
    base.update(overrides)
    return v.compute_embedding_identity(**base)


class TestEmbeddingIdentity:
    def test_deterministic(self):
        assert v.embedding_identity_hash(make_embedding_identity()) == v.embedding_identity_hash(make_embedding_identity())

    def test_revision_sensitive(self):
        a = v.embedding_identity_hash(make_embedding_identity(model_revision="rev1"))
        b = v.embedding_identity_hash(make_embedding_identity(model_revision="rev2"))
        assert a != b

    def test_repository_sensitive(self):
        a = v.embedding_identity_hash(make_embedding_identity(model_repository="repo/a"))
        b = v.embedding_identity_hash(make_embedding_identity(model_repository="repo/b"))
        assert a != b

    def test_dimension_sensitive(self):
        a = v.embedding_identity_hash(make_embedding_identity(embedding_dimension=384))
        b = v.embedding_identity_hash(make_embedding_identity(embedding_dimension=768))
        assert a != b

    def test_normalization_sensitive(self):
        a = v.embedding_identity_hash(make_embedding_identity(normalize_embeddings=True))
        b = v.embedding_identity_hash(make_embedding_identity(normalize_embeddings=False))
        assert a != b

    def test_missing_field_rejected(self):
        identity = make_embedding_identity()
        del identity["model_revision"]
        with pytest.raises(v.ArtifactManifestError):
            v.embedding_identity_hash(identity)

    def test_bge_embedding_identity_matches_frozen_constants(self):
        from src.embeddings import bge
        identity = bge.embedding_identity()
        assert identity["model_repository"] == "BAAI/bge-small-en-v1.5"
        assert identity["model_revision"] == "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
        assert identity["embedding_dimension"] == 384
        assert identity["normalize_embeddings"] is True


# --------------------------------------------------------------- index identity

class TestIndexIdentity:
    def _identity(self, **overrides):
        base = dict(chunk_schema_version=1, chunk_config_hash=HASH_A, embedding_identity_hash=HASH_B,
                    distance_metric="cosine", index_type="exact_flat", table_name="chunks")
        base.update(overrides)
        return v.compute_index_identity(**base)

    def test_deterministic(self):
        assert v.compute_index_identity_hash(self._identity()) == v.compute_index_identity_hash(self._identity())

    def test_chunk_hash_sensitive(self):
        a = v.compute_index_identity_hash(self._identity(chunk_config_hash=HASH_A))
        b = v.compute_index_identity_hash(self._identity(chunk_config_hash=HASH_C))
        assert a != b

    def test_embedding_hash_sensitive(self):
        a = v.compute_index_identity_hash(self._identity(embedding_identity_hash=HASH_A))
        b = v.compute_index_identity_hash(self._identity(embedding_identity_hash=HASH_C))
        assert a != b

    def test_metric_sensitive(self):
        a = v.compute_index_identity_hash(self._identity(distance_metric="cosine"))
        b = v.compute_index_identity_hash(self._identity(distance_metric="l2"))
        assert a != b

    def test_index_type_sensitive(self):
        a = v.compute_index_identity_hash(self._identity(index_type="exact_flat"))
        b = v.compute_index_identity_hash(self._identity(index_type="ivf_pq"))
        assert a != b

    def test_rejects_malformed_chunk_hash(self):
        with pytest.raises(v.ConfigHashError):
            self._identity(chunk_config_hash="not-a-hash")

    def test_lancedb_index_identity_helper(self):
        from src.index.lancedb_index import index_identity
        identity = index_identity(chunk_schema_version=1, chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B)
        assert identity["distance_metric"] == "cosine"
        assert identity["index_type"] == "exact_flat"
        assert identity["table_name"] == "chunks"


# --------------------------------------------------------------- manifests

def make_chunk_manifest(**overrides):
    base = dict(chunk_schema_version=1, chunk_config_hash=HASH_A, chunk_config={"a": 1}, row_count=10)
    base.update(overrides)
    return v.build_chunk_manifest(**base)


def make_embedding_manifest(**overrides):
    base = dict(chunk_schema_version=1, chunk_config_hash=HASH_A, embedding_identity={"x": 1},
                embedding_identity_hash_value=HASH_B, row_count=10)
    base.update(overrides)
    return v.build_embedding_manifest(**base)


def make_index_manifest(**overrides):
    base = dict(chunk_schema_version=1, chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B,
                index_identity={"y": 2}, index_identity_hash_value=HASH_C, row_count=10)
    base.update(overrides)
    return v.build_index_manifest(**base)


class TestManifests:
    def test_chunk_manifest_required_fields(self):
        manifest = make_chunk_manifest()
        v.validate_artifact_manifest(manifest, "chunks")

    def test_embedding_manifest_required_fields(self):
        manifest = make_embedding_manifest()
        v.validate_artifact_manifest(manifest, "embeddings")

    def test_index_manifest_required_fields(self):
        manifest = make_index_manifest()
        v.validate_artifact_manifest(manifest, "index")

    def test_wrong_artifact_type_rejected(self):
        manifest = make_chunk_manifest()
        with pytest.raises(v.ArtifactManifestError):
            v.validate_artifact_manifest(manifest, "embeddings")

    def test_missing_required_field_rejected(self):
        manifest = make_chunk_manifest()
        del manifest["row_count"]
        with pytest.raises(v.ArtifactManifestError):
            v.validate_artifact_manifest(manifest, "chunks")

    def test_unsupported_manifest_version_rejected(self):
        manifest = make_chunk_manifest()
        manifest["artifact_manifest_version"] = 999
        with pytest.raises(v.ArtifactManifestError):
            v.validate_artifact_manifest(manifest, "chunks")

    def test_malformed_hash_field_rejected(self):
        manifest = make_chunk_manifest()
        manifest["chunk_config_hash"] = "not-a-hash"
        with pytest.raises(v.ArtifactManifestError):
            v.validate_artifact_manifest(manifest, "chunks")

    def test_serialization_round_trip(self):
        manifest = make_index_manifest()
        text = json.dumps(manifest)
        restored = json.loads(text)
        v.validate_artifact_manifest(restored, "index")

    def test_verified_historical_label_present(self):
        manifest = make_chunk_manifest(verified_historical=True)
        assert manifest["provenance_label"] == "verified historical artifact provenance"

    def test_verified_historical_label_absent_by_default(self):
        manifest = make_chunk_manifest()
        assert "provenance_label" not in manifest

    def test_provenance_change_does_not_change_semantic_fingerprint(self):
        m1 = make_chunk_manifest(created_at_utc="2026-01-01T00:00:00Z", git_sha="aaa")
        m2 = make_chunk_manifest(created_at_utc="2027-06-06T00:00:00Z", git_sha="bbb")
        assert v.manifest_semantic_fingerprint(m1) == v.manifest_semantic_fingerprint(m2)

    def test_semantic_change_changes_fingerprint(self):
        m1 = make_chunk_manifest(row_count=10)
        m2 = make_chunk_manifest(row_count=11)
        assert v.manifest_semantic_fingerprint(m1) != v.manifest_semantic_fingerprint(m2)


# --------------------------------------------------------------- compatibility (positive + negative)

class TestCompatibility:
    def _compat(self, **overrides):
        base = dict(chunk_schema_version=1, chunk_config_hash=HASH_A, embedding_identity_hash=HASH_B,
                    index_identity_hash=HASH_C, eval_set_version="phase2-v1")
        base.update(overrides)
        return v.ArtifactCompatibility(**base)

    def test_valid_chain_passes(self):
        compat = self._compat()
        chunk_m = make_chunk_manifest(chunk_schema_version=1, chunk_config_hash=HASH_A)
        emb_m = make_embedding_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B)
        idx_m = make_index_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B, index_identity_hash_value=HASH_C)
        v.assert_artifact_compatible(compat, chunk_manifest=chunk_m, embedding_manifest=emb_m,
                                      index_manifest=idx_m, manifest_eval_set_version="phase2-v1")

    def test_stale_chunk_hash_fails(self):
        compat = self._compat()
        chunk_m = make_chunk_manifest(chunk_config_hash=HASH_C)  # doesn't match compat's HASH_A
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, chunk_manifest=chunk_m)

    def test_stale_embedding_identity_fails(self):
        compat = self._compat()
        emb_m = make_embedding_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_C)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, embedding_manifest=emb_m)

    def test_embedding_stale_chunk_hash_fails(self):
        compat = self._compat()
        emb_m = make_embedding_manifest(chunk_config_hash=HASH_C, embedding_identity_hash_value=HASH_B)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, embedding_manifest=emb_m)

    def test_index_dimension_style_mismatch_fails(self):
        # a "dimension mismatch" manifests as a different embedding_identity_hash
        # (dimension is one of the identity ingredients) - verified failing here.
        compat = self._compat()
        idx_m = make_index_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_C, index_identity_hash_value=HASH_C)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, index_manifest=idx_m)

    def test_wrong_index_config_fails(self):
        compat = self._compat()
        idx_m = make_index_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B, index_identity_hash_value=HASH_A)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, index_manifest=idx_m)

    def test_schema_version_mismatch_fails(self):
        compat = self._compat(chunk_schema_version=1)
        chunk_m = make_chunk_manifest(chunk_schema_version=2, chunk_config_hash=HASH_A)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, chunk_manifest=chunk_m)

    def test_eval_set_mismatch_fails(self):
        compat = self._compat(eval_set_version="phase2-v1")
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, manifest_eval_set_version="phase2-v2")

    def test_missing_manifest_field_fails_via_manifest_error(self):
        compat = self._compat()
        broken = make_chunk_manifest(chunk_config_hash=HASH_A)
        del broken["row_count"]
        with pytest.raises(v.ArtifactManifestError):
            v.assert_artifact_compatible(compat, chunk_manifest=broken)

    def test_wrong_artifact_type_fails_via_manifest_error(self):
        compat = self._compat()
        wrong_type = make_embedding_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B)
        with pytest.raises(v.ArtifactManifestError):
            v.assert_artifact_compatible(compat, chunk_manifest=wrong_type)

    def test_row_count_included_in_manifest_for_downstream_validation(self):
        manifest = make_chunk_manifest(row_count=162357)
        assert manifest["row_count"] == 162357

    def test_row_count_mismatch_across_chain_fails(self):
        compat = self._compat()
        chunk_m = make_chunk_manifest(chunk_config_hash=HASH_A, row_count=162_357)
        emb_m = make_embedding_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B, row_count=99_999)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, chunk_manifest=chunk_m, embedding_manifest=emb_m)

    def test_row_count_consistent_across_chain_passes(self):
        compat = self._compat()
        chunk_m = make_chunk_manifest(chunk_config_hash=HASH_A, row_count=162_357)
        emb_m = make_embedding_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B, row_count=162_357)
        idx_m = make_index_manifest(chunk_config_hash=HASH_A, embedding_identity_hash_value=HASH_B,
                                     index_identity_hash_value=HASH_C, row_count=162_357)
        v.assert_artifact_compatible(compat, chunk_manifest=chunk_m, embedding_manifest=emb_m, index_manifest=idx_m)

    def test_failure_is_artifact_compatibility_error_type(self):
        compat = self._compat()
        chunk_m = make_chunk_manifest(chunk_config_hash=HASH_C)
        with pytest.raises(v.ArtifactCompatibilityError):
            v.assert_artifact_compatible(compat, chunk_manifest=chunk_m)


# --------------------------------------------------------------- storage integration

class TestStorageIntegration:
    def test_different_chunk_configs_different_paths(self):
        from src.storage import get_storage
        storage = get_storage()
        assert storage.chunks_dir(HASH_A) != storage.chunks_dir(HASH_B)

    def test_different_embedding_identities_different_locations(self):
        from src.storage import get_storage
        storage = get_storage()
        a = storage.embeddings_dir_for_identity(HASH_A, HASH_B)
        b = storage.embeddings_dir_for_identity(HASH_A, HASH_C)
        assert a != b

    def test_different_index_identities_different_locations(self):
        from src.storage import get_storage
        storage = get_storage()
        a = storage.index_dir_for_identity(HASH_A, HASH_B)
        b = storage.index_dir_for_identity(HASH_A, HASH_C)
        assert a != b

    def test_identity_paths_validate_hash_format(self):
        from src.storage import get_storage
        storage = get_storage()
        with pytest.raises(v.ConfigHashError):
            storage.embeddings_dir_for_identity("not-a-hash", HASH_B)
        with pytest.raises(v.ConfigHashError):
            storage.index_dir_for_identity(HASH_A, "not-a-hash")

    def test_traversal_protection_still_intact_on_new_methods(self):
        from src.storage import StorageError, get_storage
        storage = get_storage()
        # A hash-shaped traversal attempt is still format-rejected before
        # safe_component() would even see it - defense in depth either way.
        with pytest.raises((v.ConfigHashError, StorageError)):
            storage.embeddings_dir_for_identity("../" + "a" * 61, HASH_B)

    def test_legacy_phase1_location_still_resolves(self):
        from src.storage import get_storage
        storage = get_storage()
        legacy_path = storage.embeddings_dir(PHASE1_CHUNK_CONFIG_HASH, "BAAI/bge-small-en-v1.5")
        assert legacy_path.name == "BAAI--bge-small-en-v1.5"
        legacy_index = storage.index_dir(PHASE1_CHUNK_CONFIG_HASH, "BAAI/bge-small-en-v1.5")
        assert legacy_index.name == "BAAI--bge-small-en-v1.5"

    def test_legacy_and_identity_paths_do_not_collide(self):
        from src.storage import get_storage
        storage = get_storage()
        legacy = storage.embeddings_dir(HASH_A, "BAAI/bge-small-en-v1.5")
        by_identity = storage.embeddings_dir_for_identity(HASH_A, HASH_B)
        assert legacy != by_identity


# --------------------------------------------------------------- determinism (fresh-process style)

class TestDeterminism:
    def test_same_config_same_hash_across_calls(self):
        config = {"nested": {"a": [1, 2, {"b": "café"}]}, "z": 1}
        assert v.compute_chunk_config_hash(config) == v.compute_chunk_config_hash(dict(config))

    def test_one_parameter_change_changes_hash(self):
        base = {"window_size_tokens": 512, "stride_tokens": 512}
        changed = {"window_size_tokens": 512, "stride_tokens": 256}
        assert v.compute_chunk_config_hash(base) != v.compute_chunk_config_hash(changed)

    def test_nested_unicode_config_deterministic(self):
        config = {"company_examples": ["Ünïcödé Cörp™", "日本語"], "nested": {"k": "v"}}
        assert v.compute_chunk_config_hash(config) == v.compute_chunk_config_hash(json.loads(json.dumps(config)))


# --------------------------------------------------------------- real Phase 1 chain (local_data)

@pytest.mark.local_data
class TestRealPhase1Chain:
    def test_full_chunk_embedding_index_chain_compatible(self):
        from pathlib import Path

        import pyarrow.parquet as pq

        from src.embeddings.bge import MODEL_REPO, embedding_identity
        from src.index.lancedb_index import TABLE_NAME, index_identity, open_chunk_table, open_database
        from src.storage import get_storage

        storage = get_storage()
        config = json.loads((Path("configs") / "chunk_development_corpus.json").read_text(encoding="utf-8"))
        chunk_hash = v.compute_chunk_config_hash(config)
        assert chunk_hash == PHASE1_CHUNK_CONFIG_HASH

        chunk_table = pq.read_table(storage.chunks_dir(chunk_hash) / "chunks.parquet")
        assert chunk_table.num_rows == 162_357

        emb_table = pq.read_table(storage.embeddings_dir(chunk_hash, MODEL_REPO) / "embeddings.parquet")
        assert emb_table.num_rows == 162_357

        db = open_database(storage.index_dir(chunk_hash, MODEL_REPO))
        assert db.list_tables().tables == [TABLE_NAME]
        table = open_chunk_table(db)
        assert table.count_rows() == 162_357
        assert len(table.list_indices()) == 0

        emb_identity = embedding_identity()
        emb_identity_hash = v.embedding_identity_hash(emb_identity)
        idx_identity = index_identity(chunk_schema_version=1, chunk_config_hash=chunk_hash,
                                       embedding_identity_hash_value=emb_identity_hash)
        idx_identity_hash = v.compute_index_identity_hash(idx_identity)

        chunk_manifest = v.build_chunk_manifest(chunk_schema_version=1, chunk_config_hash=chunk_hash,
                                                 chunk_config=config, row_count=162_357)
        embedding_manifest = v.build_embedding_manifest(chunk_schema_version=1, chunk_config_hash=chunk_hash,
                                                          embedding_identity=emb_identity,
                                                          embedding_identity_hash_value=emb_identity_hash, row_count=162_357)
        index_manifest = v.build_index_manifest(chunk_schema_version=1, chunk_config_hash=chunk_hash,
                                                 embedding_identity_hash_value=emb_identity_hash,
                                                 index_identity=idx_identity, index_identity_hash_value=idx_identity_hash,
                                                 row_count=162_357)

        compat = v.ArtifactCompatibility(chunk_schema_version=1, chunk_config_hash=chunk_hash,
                                          embedding_identity_hash=emb_identity_hash,
                                          index_identity_hash=idx_identity_hash, eval_set_version="phase2-v1")
        v.assert_artifact_compatible(compat, chunk_manifest=chunk_manifest, embedding_manifest=embedding_manifest,
                                      index_manifest=index_manifest)

    def test_no_artifact_mutation(self):
        from pathlib import Path
        from src.storage import get_storage

        storage = get_storage()
        chunk_path = storage.chunks_dir(PHASE1_CHUNK_CONFIG_HASH) / "chunks.parquet"
        before = chunk_path.stat().st_mtime_ns
        import pyarrow.parquet as pq
        pq.read_table(chunk_path)
        after = chunk_path.stat().st_mtime_ns
        assert before == after
