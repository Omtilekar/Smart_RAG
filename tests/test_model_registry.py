"""Tests for src/embeddings/model_registry.py (Task 3.3 generalized
embedding-model adapter). Portable - no GPU/model/network; uses only the
frozen spec dataclasses and Task 2.10's canonical hashing."""

from __future__ import annotations

import numpy as np
import pytest

from src.artifacts.versioning import embedding_identity_hash
from src.embeddings import bge as legacy_bge
from src.embeddings import model_registry as mr

FROZEN_BGE_SMALL_IDENTITY_HASH = "b39a67c9eb6487fc98f266f23742afd0a30321d98067505802a1e219b27bec84"


# --------------------------------------------------------------- BGE-small legacy regression

def test_bge_small_spec_matches_legacy_repository_and_revision():
    assert mr.BGE_SMALL.repository == legacy_bge.MODEL_REPO
    assert mr.BGE_SMALL.revision == legacy_bge.MODEL_REVISION


def test_bge_small_spec_matches_legacy_query_convention():
    assert mr.BGE_SMALL.query_prefix == legacy_bge.QUERY_INSTRUCTION


def test_bge_small_spec_matches_legacy_passage_convention():
    assert mr.BGE_SMALL.passage_prefix == ""


def test_bge_small_spec_reproduces_frozen_embedding_identity_hash():
    identity = mr.BGE_SMALL.embedding_identity()
    assert embedding_identity_hash(identity) == FROZEN_BGE_SMALL_IDENTITY_HASH


def test_bge_small_dimension_matches_legacy():
    assert mr.BGE_SMALL.dimension == legacy_bge.EMBEDDING_DIMENSION


def test_bge_small_is_control():
    assert mr.BGE_SMALL.is_control is True
    assert all(not c.is_control for c in mr.ALL_CANDIDATES if c.candidate_id != "bge_small")


# --------------------------------------------------------------- registry shape

def test_all_candidates_have_unique_ids():
    ids = [c.candidate_id for c in mr.ALL_CANDIDATES]
    assert len(ids) == len(set(ids))


def test_candidates_by_id_matches_all_candidates():
    assert set(mr.CANDIDATES_BY_ID) == {c.candidate_id for c in mr.ALL_CANDIDATES}


def test_exactly_one_control():
    controls = [c for c in mr.ALL_CANDIDATES if c.is_control]
    assert len(controls) == 1
    assert controls[0] is mr.BGE_SMALL


def test_all_revisions_look_like_pinned_commit_shas_not_main():
    for c in mr.ALL_CANDIDATES:
        assert c.revision != "main"
        assert len(c.revision) >= 12  # short/long git SHA, never a branch name


def test_all_candidates_use_cosine_similarity():
    # Task 3.3's frozen retrieval-comparability policy - no candidate may
    # require a different similarity metric.
    assert all(c.similarity_metric == "cosine" for c in mr.ALL_CANDIDATES)


def test_model_specific_prefixes_are_not_shared_across_candidates():
    # A copy-paste bug that swapped one model's prefix onto another would
    # collapse this set below the number of genuinely distinct conventions.
    query_prefixes = {c.candidate_id: c.query_prefix for c in mr.ALL_CANDIDATES}
    assert query_prefixes["bge_small"] == query_prefixes["bge_base"]  # same BGE family, verified from model card
    assert query_prefixes["nomic_embed"] != query_prefixes["bge_small"]
    assert query_prefixes["qwen3_embedding"] != query_prefixes["bge_small"]
    assert query_prefixes["nomic_embed"] != query_prefixes["qwen3_embedding"]


def test_nomic_query_and_passage_prefixes_differ():
    assert mr.NOMIC_EMBED.query_prefix != mr.NOMIC_EMBED.passage_prefix
    assert mr.NOMIC_EMBED.query_prefix == "search_query: "
    assert mr.NOMIC_EMBED.passage_prefix == "search_document: "


def test_no_candidate_requires_unapproved_trust_remote_code():
    # Verified empirically (see project_plan/PHASE3_EMBEDDING_MODEL_BENCHMARK.md):
    # none of the four frozen candidates need trust_remote_code=True with the
    # installed transformers/sentence-transformers versions.
    assert all(c.trust_remote_code is False for c in mr.ALL_CANDIDATES)


def test_all_candidates_encode_full_256_token_chunk_within_max_seq_length():
    # Frozen Task 3.2 chunks are <=256 BGE-tokenizer tokens; every candidate's
    # own tokenizer was verified empirically to produce well under its own
    # max_seq_length for the same text (see PHASE3_EMBEDDING_MODEL_BENCHMARK.md).
    assert all(c.max_seq_length >= 512 for c in mr.ALL_CANDIDATES)


# --------------------------------------------------------------- embedding_identity hashing

def test_embedding_identity_hash_deterministic():
    h1 = embedding_identity_hash(mr.BGE_BASE.embedding_identity())
    h2 = embedding_identity_hash(mr.BGE_BASE.embedding_identity())
    assert h1 == h2


def test_embedding_identity_hash_differs_across_candidates():
    hashes = {c.candidate_id: embedding_identity_hash(c.embedding_identity()) for c in mr.ALL_CANDIDATES}
    assert len(set(hashes.values())) == len(hashes)


def test_embedding_identity_hash_changes_with_revision():
    from dataclasses import replace
    changed = replace(mr.BGE_BASE, revision="0" * 40)
    assert embedding_identity_hash(changed.embedding_identity()) != embedding_identity_hash(mr.BGE_BASE.embedding_identity())


def test_embedding_identity_hash_changes_with_dimension():
    from dataclasses import replace
    changed = replace(mr.BGE_BASE, dimension=999)
    assert embedding_identity_hash(changed.embedding_identity()) != embedding_identity_hash(mr.BGE_BASE.embedding_identity())


def test_embedding_identity_hash_changes_with_query_convention():
    from dataclasses import replace
    changed = replace(mr.NOMIC_EMBED, query_prefix="different: ")
    assert embedding_identity_hash(changed.embedding_identity()) != embedding_identity_hash(mr.NOMIC_EMBED.embedding_identity())


def test_passage_convention_label_no_prefix():
    assert mr.BGE_SMALL.passage_convention == "raw_text_no_instruction"


def test_passage_convention_label_with_prefix():
    assert mr.NOMIC_EMBED.passage_convention == "prepend:search_document: "


def test_query_convention_label_with_prefix():
    assert mr.BGE_BASE.query_convention == f"prepend:{mr.BGE_BASE.query_prefix}"


# --------------------------------------------------------------- validate_vectors

def _vecs(n, dim, norm=1.0):
    v = np.random.RandomState(0).randn(n, dim).astype(np.float32)
    v = v / np.linalg.norm(v, axis=1, keepdims=True) * norm
    return v.astype(np.float32)


def test_validate_vectors_accepts_correct_shape_dtype_normalized():
    mr.validate_vectors(_vecs(5, 384), expected_dimension=384)


def test_validate_vectors_rejects_wrong_dimension():
    with pytest.raises(ValueError):
        mr.validate_vectors(_vecs(5, 384), expected_dimension=768)


def test_validate_vectors_rejects_wrong_dtype():
    v = _vecs(5, 384).astype(np.float64)
    with pytest.raises(ValueError):
        mr.validate_vectors(v, expected_dimension=384)


def test_validate_vectors_rejects_nan():
    v = _vecs(5, 384)
    v[0, 0] = np.nan
    with pytest.raises(ValueError):
        mr.validate_vectors(v, expected_dimension=384)


def test_validate_vectors_rejects_inf():
    v = _vecs(5, 384)
    v[0, 0] = np.inf
    with pytest.raises(ValueError):
        mr.validate_vectors(v, expected_dimension=384)


def test_validate_vectors_rejects_unnormalized_when_expected():
    v = _vecs(5, 384, norm=5.0)
    with pytest.raises(ValueError):
        mr.validate_vectors(v, expected_dimension=384, expect_normalized=True)


def test_validate_vectors_allows_unnormalized_when_not_expected():
    v = _vecs(5, 384, norm=5.0)
    mr.validate_vectors(v, expected_dimension=384, expect_normalized=False)


# --------------------------------------------------------------- encode_* prefix behavior (fake model, portable)

class _FakeModel:
    """Records exactly what text/kwargs it was called with - no real model,
    no GPU, no network. Used only to verify encode_passages/encode_queries
    apply the correct prefix without accidentally swapping them."""

    def __init__(self, dim):
        self.dim = dim
        self.calls = []

    def encode(self, texts, *, batch_size, normalize_embeddings, convert_to_numpy, show_progress_bar):
        self.calls.append({"texts": list(texts), "normalize_embeddings": normalize_embeddings})
        return np.zeros((len(texts), self.dim), dtype=np.float32)


def test_encode_passages_applies_passage_prefix_not_query_prefix():
    model = _FakeModel(mr.NOMIC_EMBED.dimension)
    mr.encode_passages(mr.NOMIC_EMBED, model, ["hello"], batch_size=1)
    assert model.calls[0]["texts"] == ["search_document: hello"]


def test_encode_queries_applies_query_prefix_not_passage_prefix():
    model = _FakeModel(mr.NOMIC_EMBED.dimension)
    mr.encode_queries(mr.NOMIC_EMBED, model, ["hello"], batch_size=1)
    assert model.calls[0]["texts"] == ["search_query: hello"]


def test_encode_passages_no_prefix_when_empty():
    model = _FakeModel(mr.BGE_SMALL.dimension)
    mr.encode_passages(mr.BGE_SMALL, model, ["hello"], batch_size=1)
    assert model.calls[0]["texts"] == ["hello"]


def test_encode_queries_uses_normalize_embeddings_flag_from_spec():
    model = _FakeModel(mr.BGE_SMALL.dimension)
    mr.encode_queries(mr.BGE_SMALL, model, ["hello"], batch_size=1)
    assert model.calls[0]["normalize_embeddings"] is True


def test_encode_output_dtype_is_float32():
    model = _FakeModel(mr.BGE_SMALL.dimension)
    out = mr.encode_passages(mr.BGE_SMALL, model, ["hello"], batch_size=1)
    assert out.dtype == np.float32


# --------------------------------------------------------------- load_model forces fp32

def test_load_model_forces_float32_weights(monkeypatch):
    """Qwen3-Embedding-0.6B's own config defaults to bfloat16 under
    sentence-transformers; load_model() must force float32 explicitly for
    every candidate rather than silently inheriting a model's own default
    precision (verified empirically: bf16 broke the unit-norm check)."""
    import torch
    captured = {}

    class _FakeParam:
        dtype = torch.float32
        device = torch.device("cuda:0")

    class _FakeST:
        def __init__(self, repo, revision, trust_remote_code, device, model_kwargs):
            captured["model_kwargs"] = model_kwargs
            captured["revision"] = revision

        def parameters(self):
            return iter([_FakeParam()])

        def get_embedding_dimension(self):
            return mr.QWEN3_EMBEDDING.dimension

    import sentence_transformers
    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", _FakeST)
    mr.load_model(mr.QWEN3_EMBEDDING, device="cuda")
    assert captured["model_kwargs"] == {"torch_dtype": torch.float32}
    assert captured["revision"] == mr.QWEN3_EMBEDDING.revision
