"""Regression test for a real bug found during Task 3.3: the embedding
checkpoint loader (originally written for Task 3.2's fixed 384-dim BGE-
small candidates) had EMBEDDING_DIMENSION hardcoded, so loading a
768/1024-dim checkpoint (Task 3.3's other candidates) silently failed
validation and discarded real, already-embedded progress. Portable - no
GPU/model/network, tiny synthetic checkpoints only."""

from __future__ import annotations

import json

import numpy as np
import pytest

from scripts.run_phase3_chunking_ablation import (
    _load_embed_checkpoint, _save_embed_checkpoint, _clear_embed_checkpoint, EMBEDDING_DIMENSION,
)


def _write_checkpoint(tmp_path, dimension, done):
    vectors = np.random.RandomState(0).randn(done, dimension).astype(np.float32)
    _save_embed_checkpoint(tmp_path, vectors, done)
    return vectors


def test_default_dimension_preserves_task32_behavior(tmp_path):
    # Task 3.2's own call site never passes `dimension` - must keep
    # defaulting to the frozen 384 (BGE-small).
    vectors = _write_checkpoint(tmp_path, EMBEDDING_DIMENSION, done=10)
    loaded, done = _load_embed_checkpoint(tmp_path, n=100)
    assert done == 10
    assert loaded.shape == (10, EMBEDDING_DIMENSION)
    np.testing.assert_array_equal(loaded, vectors)


def test_explicit_dimension_loads_non_bge_small_checkpoint(tmp_path):
    # The Task 3.3 bug: a 768-dim checkpoint must load correctly when the
    # caller passes its own dimension explicitly.
    vectors = _write_checkpoint(tmp_path, 768, done=16640)
    loaded, done = _load_embed_checkpoint(tmp_path, n=323971, dimension=768)
    assert done == 16640
    assert loaded.shape == (16640, 768)
    np.testing.assert_array_equal(loaded, vectors)


def test_mismatched_dimension_is_rejected_not_silently_wrong(tmp_path):
    # A 768-dim checkpoint read back with the WRONG expected dimension
    # (e.g. forgetting to pass dimension=768) must be treated as invalid
    # (None, 0) - never silently accepted with the wrong shape.
    _write_checkpoint(tmp_path, 768, done=16640)
    loaded, done = _load_embed_checkpoint(tmp_path, n=323971, dimension=384)
    assert loaded is None
    assert done == 0


def test_1024_dim_checkpoint_roundtrip(tmp_path):
    vectors = _write_checkpoint(tmp_path, 1024, done=500)
    loaded, done = _load_embed_checkpoint(tmp_path, n=323971, dimension=1024)
    assert done == 500
    assert loaded.shape == (500, 1024)
    np.testing.assert_array_equal(loaded, vectors)


def test_clear_checkpoint_removes_both_files(tmp_path):
    _write_checkpoint(tmp_path, 768, done=10)
    data_path = tmp_path / "embeddings.checkpoint.npy"
    meta_path = tmp_path / "embeddings.checkpoint.json"
    assert data_path.is_file() and meta_path.is_file()
    _clear_embed_checkpoint(tmp_path)
    assert not data_path.is_file() and not meta_path.is_file()


def test_no_checkpoint_returns_none(tmp_path):
    loaded, done = _load_embed_checkpoint(tmp_path, n=100, dimension=768)
    assert loaded is None
    assert done == 0
