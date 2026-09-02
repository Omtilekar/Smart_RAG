"""Task 2.11 - tests for src.eval.run_logging."""

from __future__ import annotations

import json
import math

import pytest

from src.artifacts.versioning import ArtifactCompatibility, ArtifactCompatibilityError
from src.eval import run_logging as rl

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
GIT_SHA_1 = "d" * 40
GIT_SHA_2 = "e" * 40
RUN_ID_1 = "11111111-1111-4111-8111-111111111111"
RUN_ID_2 = "22222222-2222-4222-8222-222222222222"
TIMESTAMP = "2026-09-02T15:42:13.123456Z"


def make_embedding_model(**overrides) -> dict:
    base = dict(model_repository="BAAI/bge-small-en-v1.5", model_revision="x" * 40, embedding_dimension=384,
                vector_dtype="float32", normalize_embeddings=True, identity_hash=HASH_A)
    base.update(overrides)
    return base


def build(**overrides):
    kwargs = dict(
        chunk_schema_version=1, chunk_config_hash=HASH_B, embedding_model=make_embedding_model(),
        retrieval_config={"method": "vector", "top_k": 10}, reranker_config={"enabled": False},
        generation_model=None, split="dev", eval_set_version="phase2-v1", split_version="phase2-split-v1",
        metrics={"doc_recall@10": 0.97}, index_identity_hash=HASH_C,
        git_state={"git_sha": GIT_SHA_1, "git_dirty": False}, run_id=RUN_ID_1, timestamp=TIMESTAMP,
    )
    kwargs.update(overrides)
    return rl.build_run_record(**kwargs)


# --------------------------------------------------------------- required fields

class TestRequiredFields:
    def test_all_mandatory_roadmap_fields_present(self):
        record = build()
        data = record.to_dict()
        for field in rl.MANDATORY_ROADMAP_FIELDS:
            assert field in data

    def test_mandatory_field_count_is_11(self):
        assert len(rl.MANDATORY_ROADMAP_FIELDS) == 11

    def test_missing_required_field_rejected(self):
        record = build()
        data = record.to_dict()
        del data["metrics"]
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_run_record(data)

    def test_generation_model_null_explicit_not_omitted(self):
        record = build(generation_model=None)
        data = record.to_dict()
        assert "generation_model" in data
        assert data["generation_model"] is None


# --------------------------------------------------------------- run ids

class TestRunId:
    def test_generated_is_valid_uuid4(self):
        run_id = rl.generate_run_id()
        rl.validate_run_id(run_id)

    def test_different_calls_different_ids(self):
        assert rl.generate_run_id() != rl.generate_run_id()

    def test_injected_id_preserved(self):
        record = build(run_id=RUN_ID_2)
        assert record.run_id == RUN_ID_2

    def test_same_config_different_run_ids(self):
        r1 = build(run_id=RUN_ID_1)
        r2 = build(run_id=RUN_ID_2)
        assert r1.run_id != r2.run_id
        # everything else semantically identical except run_id/hash
        assert r1.chunk_config_hash == r2.chunk_config_hash

    @pytest.mark.parametrize("bad", ["not-a-uuid", "", "11111111-1111-1111-8111-111111111111", RUN_ID_1.upper()[:-1] + "z"])
    def test_malformed_id_rejected(self, bad):
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_run_id(bad)


# --------------------------------------------------------------- timestamp

class TestTimestamp:
    def test_utc_z_form_accepted(self):
        rl.validate_timestamp("2026-09-02T15:42:13.123456Z")

    def test_utc_z_form_no_microseconds_accepted(self):
        rl.validate_timestamp("2026-09-02T15:42:13Z")

    @pytest.mark.parametrize("bad", [
        "2026-09-02T15:42:13", "2026-09-02 15:42:13Z", "2026-09-02T15:42:13+05:00",
        "09/02/2026 15:42:13", "2026-13-40T00:00:00Z", "",
    ])
    def test_naive_or_malformed_timestamp_rejected(self, bad):
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_timestamp(bad)

    def test_injected_clock_deterministic(self):
        r1 = build(timestamp=TIMESTAMP)
        r2 = build(timestamp=TIMESTAMP)
        assert r1.timestamp == r2.timestamp == TIMESTAMP

    def test_current_utc_timestamp_is_valid(self):
        rl.validate_timestamp(rl.current_utc_timestamp())


# --------------------------------------------------------------- git

class TestGitProvenance:
    def test_full_sha_accepted(self):
        rl.validate_git_sha(GIT_SHA_1)

    @pytest.mark.parametrize("bad", ["HEAD", "main", "latest", "unknown", "a" * 39, "A" * 40, "g" * 40, ""])
    def test_malformed_sha_rejected(self, bad):
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_git_sha(bad)

    def test_dirty_flag_retained_true(self):
        record = build(git_state={"git_sha": GIT_SHA_1, "git_dirty": True})
        assert record.git_dirty is True

    def test_dirty_flag_retained_false(self):
        record = build(git_state={"git_sha": GIT_SHA_1, "git_dirty": False})
        assert record.git_dirty is False

    def test_real_current_git_state_resolves(self):
        state = rl.current_git_state()
        rl.validate_git_sha(state["git_sha"])
        assert isinstance(state["git_dirty"], bool)


# --------------------------------------------------------------- hashes

class TestHashes:
    def test_chunk_config_hash_validated(self):
        with pytest.raises(rl.RunLogValidationError):
            build(chunk_config_hash="not-a-hash")

    def test_embedding_identity_hash_validated(self):
        with pytest.raises(rl.RunLogValidationError):
            build(embedding_model=make_embedding_model(identity_hash="not-a-hash"))

    def test_index_identity_hash_validated(self):
        with pytest.raises(rl.RunLogValidationError):
            build(index_identity_hash="not-a-hash")

    def test_index_identity_hash_none_allowed(self):
        record = build(index_identity_hash=None)
        assert record.index_identity_hash is None

    def test_run_record_sha256_deterministic(self):
        r1 = build()
        r2 = build()
        assert r1.run_record_sha256 == r2.run_record_sha256

    def test_run_record_sha256_excludes_itself(self):
        record = build()
        data = record.to_dict()
        recomputed = rl.compute_run_record_sha256(data)
        assert recomputed == data["run_record_sha256"]

    def test_tampering_metric_detected(self):
        record = build()
        data = record.to_dict()
        data["metrics"] = {"doc_recall@10": 0.5}
        with pytest.raises(rl.RunRecordIntegrityError):
            rl.validate_run_record(data)

    def test_tampering_git_sha_detected(self):
        record = build()
        data = record.to_dict()
        data["git_sha"] = GIT_SHA_2
        with pytest.raises(rl.RunRecordIntegrityError):
            rl.validate_run_record(data)

    def test_tampering_chunk_config_hash_detected(self):
        record = build()
        data = record.to_dict()
        data["chunk_config_hash"] = HASH_C
        with pytest.raises(rl.RunRecordIntegrityError):
            rl.validate_run_record(data)


# --------------------------------------------------------------- embedding model

class TestEmbeddingModel:
    def test_repository_revision_dimension_normalization_retained(self):
        record = build()
        em = record.embedding_model
        assert em["model_repository"] == "BAAI/bge-small-en-v1.5"
        assert em["embedding_dimension"] == 384
        assert em["normalize_embeddings"] is True

    def test_missing_revision_rejected(self):
        embedding_model = make_embedding_model()
        del embedding_model["model_revision"]
        with pytest.raises(rl.RunLogValidationError):
            build(embedding_model=embedding_model)

    def test_missing_identity_hash_rejected(self):
        embedding_model = make_embedding_model()
        del embedding_model["identity_hash"]
        with pytest.raises(rl.RunLogValidationError):
            build(embedding_model=embedding_model)


# --------------------------------------------------------------- retrieval config

class TestRetrievalConfig:
    def test_structured_mapping_required(self):
        record = build(retrieval_config={"method": "vector", "top_k": 10, "distance_metric": "cosine"})
        assert record.retrieval_config["top_k"] == 10

    def test_top_k_change_changes_optional_hash(self):
        a = rl.compute_config_semantic_hash({"method": "vector", "top_k": 10})
        b = rl.compute_config_semantic_hash({"method": "vector", "top_k": 20})
        assert a != b

    def test_metric_change_changes_hash(self):
        a = rl.compute_config_semantic_hash({"distance_metric": "cosine"})
        b = rl.compute_config_semantic_hash({"distance_metric": "l2"})
        assert a != b

    def test_index_type_change_changes_hash(self):
        a = rl.compute_config_semantic_hash({"index_type": "exact_flat"})
        b = rl.compute_config_semantic_hash({"index_type": "ivf_pq"})
        assert a != b

    def test_key_order_does_not_change_hash(self):
        a = rl.compute_config_semantic_hash({"top_k": 10, "method": "vector"})
        b = rl.compute_config_semantic_hash({"method": "vector", "top_k": 10})
        assert a == b


# --------------------------------------------------------------- reranker config

class TestRerankerConfig:
    def test_explicit_disabled_accepted(self):
        record = build(reranker_config={"enabled": False})
        assert record.reranker_config == {"enabled": False}

    def test_enabled_without_model_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(reranker_config={"enabled": True})

    def test_enabled_with_model_and_revision_accepted(self):
        record = build(reranker_config={"enabled": True, "model": "cross-encoder/x", "revision": "rev1"})
        assert record.reranker_config["enabled"] is True

    def test_missing_enabled_key_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(reranker_config={"model": "x"})

    def test_non_bool_enabled_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(reranker_config={"enabled": "false"})

    def test_disabled_differs_semantically_from_enabled(self):
        a = rl.compute_config_semantic_hash({"enabled": False})
        b = rl.compute_config_semantic_hash({"enabled": True, "model": "x", "revision": "rev1"})
        assert a != b

    def test_model_revision_a_differs_from_b(self):
        a = rl.compute_config_semantic_hash({"enabled": True, "model": "x", "revision": "rev-a"})
        b = rl.compute_config_semantic_hash({"enabled": True, "model": "x", "revision": "rev-b"})
        assert a != b


# --------------------------------------------------------------- generation model

class TestGenerationModel:
    def test_null_accepted_for_retrieval_only(self):
        record = build(generation_model=None)
        assert record.generation_model is None

    def test_provider_model_accepted_when_enabled(self):
        record = build(generation_model={"provider": "openrouter", "model": "openai/gpt-oss-20b"})
        assert record.generation_model["provider"] == "openrouter"

    def test_missing_model_field_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(generation_model={"provider": "openrouter"})

    def test_secret_field_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(generation_model={"provider": "openrouter", "model": "x", "api_key": "sk-secret-value"})

    def test_non_mapping_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(generation_model="openrouter/gpt")


# --------------------------------------------------------------- split / eval version

class TestSplitEvalVersion:
    def test_split_required_valid_value_accepted(self):
        for split in ("dev", "ci", "test"):
            record = build(split=split)
            assert record.split == split

    def test_invalid_split_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(split="production")

    def test_empty_eval_set_version_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(eval_set_version="")

    def test_split_version_retained(self):
        record = build(split_version="phase2-split-v1")
        assert record.split_version == "phase2-split-v1"

    def test_split_digest_retained(self):
        record = build(split_sha256=HASH_A)
        assert record.split_sha256 == HASH_A

    def test_split_digest_none_allowed(self):
        record = build(split_sha256=None)
        assert record.split_sha256 is None

    def test_malformed_split_digest_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(split_sha256="not-a-hash")


# --------------------------------------------------------------- metrics

class TestMetrics:
    def test_integer_accepted(self):
        record = build(metrics={"hit_count": 194})
        assert record.metrics["hit_count"] == 194

    def test_float_accepted(self):
        record = build(metrics={"doc_recall@10": 0.97})
        assert record.metrics["doc_recall@10"] == 0.97

    def test_zero_accepted(self):
        record = build(metrics={"count": 0})
        assert record.metrics["count"] == 0

    def test_negative_value_accepted(self):
        record = build(metrics={"log_likelihood": -3.2})
        assert record.metrics["log_likelihood"] == -3.2

    def test_bool_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(metrics={"passed": True})

    def test_nan_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(metrics={"x": float("nan")})

    def test_positive_inf_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(metrics={"x": float("inf")})

    def test_negative_inf_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(metrics={"x": float("-inf")})

    def test_empty_metric_name_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(metrics={"": 1.0})

    def test_unavailable_metric_not_fabricated_as_zero(self):
        # The contract: an unavailable metric is simply absent, never 0.0.
        record = build(metrics={"doc_recall@10": 0.97})
        assert "chunk_recall@10" not in record.metrics


# --------------------------------------------------------------- persistence

class TestPersistence:
    def test_write_read_round_trip(self, tmp_path):
        record = build()
        path = rl.write_run_record(record, directory=tmp_path)
        loaded = rl.load_run_record(path)
        assert loaded == record

    def test_written_file_has_one_trailing_newline(self, tmp_path):
        record = build()
        path = rl.write_run_record(record, directory=tmp_path)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n") and not text.endswith("\n\n")

    def test_written_file_is_valid_json(self, tmp_path):
        record = build()
        path = rl.write_run_record(record, directory=tmp_path)
        json.loads(path.read_text(encoding="utf-8"))

    def test_filename_derived_from_run_id(self, tmp_path):
        record = build(run_id=RUN_ID_1)
        path = rl.write_run_record(record, directory=tmp_path)
        assert path.name == f"{RUN_ID_1}.json"

    def test_duplicate_run_id_rejected(self, tmp_path):
        record = build(run_id=RUN_ID_1)
        rl.write_run_record(record, directory=tmp_path)
        with pytest.raises(rl.RunRecordExistsError):
            rl.write_run_record(record, directory=tmp_path)

    def test_duplicate_run_id_leaves_original_unchanged(self, tmp_path):
        record = build(run_id=RUN_ID_1, metrics={"doc_recall@10": 0.97})
        path = rl.write_run_record(record, directory=tmp_path)
        original_text = path.read_text(encoding="utf-8")
        other = build(run_id=RUN_ID_1, metrics={"doc_recall@10": 0.42})
        with pytest.raises(rl.RunRecordExistsError):
            rl.write_run_record(other, directory=tmp_path)
        assert path.read_text(encoding="utf-8") == original_text

    def test_invalid_record_never_written(self, tmp_path):
        record = build()
        data = record.to_dict()
        data["metrics"] = {"bad": True}
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_run_record(data)
        assert list(tmp_path.glob("*.json")) == []

    def test_list_run_records_sorted(self, tmp_path):
        r1 = build(run_id=RUN_ID_1)
        r2 = build(run_id=RUN_ID_2)
        rl.write_run_record(r1, directory=tmp_path)
        rl.write_run_record(r2, directory=tmp_path)
        listed = rl.list_run_records(directory=tmp_path)
        assert listed == sorted(listed)
        assert len(listed) == 2

    def test_list_run_records_empty_directory(self, tmp_path):
        assert rl.list_run_records(directory=tmp_path / "does_not_exist") == []

    def test_malformed_json_on_load_rejected(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(rl.RunLogError):
            rl.load_run_record(path)


# --------------------------------------------------------------- security

class TestSecurity:
    @pytest.mark.parametrize("key", ["api_key", "apiKey", "API_KEY", "apikey"])
    def test_api_key_rejected_recursively(self, key):
        with pytest.raises(rl.RunLogValidationError):
            build(retrieval_config={"method": "vector", key: "sk-should-not-be-here"})

    def test_authorization_rejected_recursively(self):
        with pytest.raises(rl.RunLogValidationError):
            build(retrieval_config={"nested": {"Authorization": "Bearer xyz"}})

    def test_password_rejected_recursively(self):
        with pytest.raises(rl.RunLogValidationError):
            build(reranker_config={"enabled": False, "password": "hunter2"})

    def test_token_rejected_recursively(self):
        with pytest.raises(rl.RunLogValidationError):
            build(generation_model={"provider": "x", "model": "y", "access_token": "secret-token-value"})

    def test_secret_in_list_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(retrieval_config={"filters": [{"credential": "abc"}]})

    def test_no_credential_value_appears_in_exception(self):
        secret_value = "sk-super-secret-do-not-leak-12345"
        with pytest.raises(rl.RunLogValidationError) as exc_info:
            build(retrieval_config={"api_key": secret_value})
        assert secret_value not in str(exc_info.value)

    def test_benign_keys_not_falsely_rejected(self):
        # "top_k", "distance_metric", "index_type" must not collide with
        # any secret-substring pattern.
        record = build(retrieval_config={"top_k": 10, "distance_metric": "cosine", "index_type": "exact_flat"})
        assert record.retrieval_config["top_k"] == 10


# --------------------------------------------------------------- Task 2.10 integration

class TestArtifactCompatibilityIntegration:
    def _compat(self, **overrides):
        base = dict(chunk_schema_version=1, chunk_config_hash=HASH_B, embedding_identity_hash=HASH_A,
                    index_identity_hash=HASH_C, eval_set_version="phase2-v1")
        base.update(overrides)
        return ArtifactCompatibility(**base)

    def test_compatible_snapshot_builds_record(self):
        record = build(artifact_compatibility=self._compat())
        assert record.chunk_config_hash == HASH_B

    def test_chunk_mismatch_raises(self):
        compat = self._compat(chunk_config_hash=HASH_C)
        with pytest.raises(ArtifactCompatibilityError):
            build(artifact_compatibility=compat)

    def test_embedding_mismatch_raises(self):
        compat = self._compat(embedding_identity_hash=HASH_C)
        with pytest.raises(ArtifactCompatibilityError):
            build(artifact_compatibility=compat)

    def test_index_mismatch_raises(self):
        compat = self._compat(index_identity_hash=HASH_B)
        with pytest.raises(ArtifactCompatibilityError):
            build(artifact_compatibility=compat)

    def test_eval_version_mismatch_raises(self):
        compat = self._compat(eval_set_version="phase2-v2")
        with pytest.raises(ArtifactCompatibilityError):
            build(artifact_compatibility=compat)

    def test_schema_version_mismatch_raises(self):
        compat = self._compat(chunk_schema_version=999)
        with pytest.raises(ArtifactCompatibilityError):
            build(artifact_compatibility=compat)


# --------------------------------------------------------------- real Phase 1 (local_data)

# --------------------------------------------------------------- Task 2.12 schema-v2 extension

class TestExternalBenchmarkExtension:
    def test_default_evaluation_source_is_internal(self):
        record = build()
        assert record.evaluation_source == "internal_phase2"
        assert record.benchmark_name is None

    def test_current_schema_version_is_2(self):
        assert rl.EVALUATION_RUN_SCHEMA_VERSION == 2
        assert 2 in rl.SUPPORTED_RUN_SCHEMA_VERSIONS

    def test_external_benchmark_record_builds(self):
        record = build(
            evaluation_source="external_benchmark", split="open_source_150",
            benchmark_name="financebench", benchmark_version="financebench-open-source-150-v1",
            benchmark_source_hash=HASH_A,
        )
        assert record.split == "open_source_150"
        assert record.benchmark_name == "financebench"

    def test_external_benchmark_split_not_forced_into_valid_splits(self):
        # "open_source_150" is deliberately NOT in VALID_SPLITS - this must
        # succeed for evaluation_source="external_benchmark" specifically.
        record = build(evaluation_source="external_benchmark", split="open_source_150",
                        benchmark_name="financebench", benchmark_version="v1", benchmark_source_hash=HASH_A)
        assert record.split not in ("dev", "test", "ci")

    def test_external_benchmark_never_labeled_internal_test(self):
        # A reader can never mistake an external run for the protected
        # internal SEC TEST split: evaluation_source is always recorded
        # alongside split, structurally distinguishing the two even though
        # `split` itself is just a free-form population label for an
        # external run.
        record = build(evaluation_source="external_benchmark", split="open_source_150",
                        benchmark_name="financebench", benchmark_version="v1", benchmark_source_hash=HASH_A)
        assert record.evaluation_source == "external_benchmark"
        assert record.split != "test"

    def test_external_benchmark_missing_name_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(evaluation_source="external_benchmark", split="open_source_150",
                  benchmark_name=None, benchmark_version="v1", benchmark_source_hash=HASH_A)

    def test_external_benchmark_missing_version_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(evaluation_source="external_benchmark", split="open_source_150",
                  benchmark_name="financebench", benchmark_version=None, benchmark_source_hash=HASH_A)

    def test_external_benchmark_malformed_source_hash_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(evaluation_source="external_benchmark", split="open_source_150",
                  benchmark_name="financebench", benchmark_version="v1", benchmark_source_hash="not-a-hash")

    def test_internal_run_with_benchmark_fields_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(benchmark_name="financebench")

    def test_invalid_evaluation_source_rejected(self):
        with pytest.raises(rl.RunLogValidationError):
            build(evaluation_source="not-a-real-source")

    def test_v1_record_without_new_fields_still_validates(self):
        # Simulates a genuine pre-Task-2.12 record on disk: no
        # evaluation_source/benchmark_* keys at all, run_schema_version=1.
        record = build()
        data = record.to_dict()
        data["run_schema_version"] = 1
        del data["evaluation_source"]
        del data["benchmark_name"]
        del data["benchmark_version"]
        del data["benchmark_source_hash"]
        data["run_record_sha256"] = rl.compute_run_record_sha256(data)
        rl.validate_run_record(data)

    def test_v1_record_write_read_round_trip(self, tmp_path):
        record = build()
        data = record.to_dict()
        data["run_schema_version"] = 1
        for k in ("evaluation_source", "benchmark_name", "benchmark_version", "benchmark_source_hash"):
            del data[k]
        data["run_record_sha256"] = rl.compute_run_record_sha256(data)
        target = tmp_path / f"{data['run_id']}.json"
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        loaded = rl.load_run_record(target)
        assert loaded.run_id == data["run_id"]

    def test_unsupported_schema_version_rejected(self):
        record = build()
        data = record.to_dict()
        data["run_schema_version"] = 999
        with pytest.raises(rl.RunLogValidationError):
            rl.validate_run_record(data)


@pytest.mark.local_data
class TestRealPhase1Integration:
    def test_real_artifact_identities_populate_a_run_record(self, tmp_path):
        from src.artifacts.versioning import (
            ArtifactCompatibility, compute_index_identity_hash, embedding_identity_hash,
        )
        from src.chunk.metadata_schema import CHUNK_SCHEMA_VERSION
        from src.embeddings.bge import embedding_identity
        from src.index.lancedb_index import index_identity

        chunk_hash = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
        emb_identity = embedding_identity()
        emb_hash = embedding_identity_hash(emb_identity)
        idx_identity = index_identity(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_hash,
                                       embedding_identity_hash_value=emb_hash)
        idx_hash = compute_index_identity_hash(idx_identity)

        compat = ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_hash,
                                        embedding_identity_hash=emb_hash, index_identity_hash=idx_hash,
                                        eval_set_version="phase2-v1")

        record = rl.build_run_record(
            chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_hash,
            embedding_model={**emb_identity, "identity_hash": emb_hash},
            retrieval_config={"method": "vector", "index_type": "exact_flat", "distance_metric": "cosine", "top_k": 10},
            reranker_config={"enabled": False}, generation_model=None, split="dev",
            eval_set_version="phase2-v1", split_version="phase2-split-v1", metrics={"doc_recall@10": 0.97},
            index_identity_hash=idx_hash, artifact_compatibility=compat,
        )
        path = rl.write_run_record(record, directory=tmp_path)
        loaded = rl.load_run_record(path)
        assert loaded == record
