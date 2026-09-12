"""Task 3.6 - portable tests for src.rerank.cross_encoder. No real model
download/load here (that belongs to the local GPU/model pilot) - only
the pure spec/identity/validation logic."""

from __future__ import annotations

import numpy as np
import pytest

from src.rerank import cross_encoder as ce


def test_reranker_identity_hash_deterministic():
    from src.artifacts.versioning import semantic_hash
    identity = ce.CROSS_ENCODER_MINILM_L6.reranker_identity()
    assert semantic_hash(identity) == semantic_hash(identity)


def test_reranker_identity_changes_with_revision():
    from dataclasses import replace
    from src.artifacts.versioning import semantic_hash
    spec_a = ce.CROSS_ENCODER_MINILM_L6
    spec_b = replace(spec_a, revision="0" * 40)
    assert semantic_hash(spec_a.reranker_identity()) != semantic_hash(spec_b.reranker_identity())


def test_reranker_identity_shape():
    identity = ce.CROSS_ENCODER_MINILM_L6.reranker_identity()
    assert identity["model_repository"] == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert identity["score_activation"] == "raw_logit"


def test_candidate_registry_contains_frozen_candidate():
    assert "ce_minilm_l6" in ce.CANDIDATES_BY_ID
    assert ce.CANDIDATES_BY_ID["ce_minilm_l6"] is ce.CROSS_ENCODER_MINILM_L6


def test_validate_scores_accepts_correct_shape():
    ce.validate_scores(np.array([1.0, 2.0, 3.0], dtype=np.float32), expected_count=3)


def test_validate_scores_rejects_wrong_count():
    with pytest.raises(ValueError):
        ce.validate_scores(np.array([1.0, 2.0], dtype=np.float32), expected_count=3)


def test_validate_scores_rejects_nan():
    with pytest.raises(ValueError):
        ce.validate_scores(np.array([1.0, float("nan")], dtype=np.float32), expected_count=2)


def test_validate_scores_rejects_2d():
    with pytest.raises(ValueError):
        ce.validate_scores(np.array([[1.0], [2.0]], dtype=np.float32), expected_count=2)
