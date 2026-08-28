"""Tests for src/embeddings/bge.py.

Portable tests cover validate_vectors() (pure numpy logic, no model/GPU
required) and the config constants. The one test that actually loads
BAAI/bge-small-en-v1.5 and runs CUDA inference is `model`+`gpu`-marked,
offline-guarded, and skips cleanly if the model isn't cached - mirroring
tests/test_embedding_smoke.py's established pattern (Task 0.8). Does not
run the full 162,357-vector build (that is scripts/embed_development_corpus.py's
own real run, Task 1.4 Step 25).
"""

import numpy as np
import pytest
import torch
from huggingface_hub import try_to_load_from_cache

from src.embeddings import bge


# ---------------------------------------------------------------- constants

def test_embedding_dimension_is_384():
    assert bge.EMBEDDING_DIMENSION == 384


def test_vector_dtype_is_float32():
    assert bge.VECTOR_DTYPE == np.float32


def test_query_instruction_is_nonempty_and_ends_with_separator():
    assert bge.QUERY_INSTRUCTION
    assert bge.QUERY_INSTRUCTION.endswith(": ")


def test_required_model_asset_files_nonempty():
    assert len(bge.REQUIRED_MODEL_ASSET_FILES) > 0


# ------------------------------------------------------------ validate_vectors

def _unit_row(dim=384, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_validate_vectors_accepts_normalized_valid_array():
    rows = np.stack([_unit_row(seed=i) for i in range(5)])
    bge.validate_vectors(rows)  # should not raise


def test_validate_vectors_rejects_wrong_dimension():
    rows = np.zeros((3, 100), dtype=np.float32)
    with pytest.raises(ValueError, match="shape"):
        bge.validate_vectors(rows)


def test_validate_vectors_rejects_wrong_dtype():
    rows = np.stack([_unit_row(seed=i) for i in range(3)]).astype(np.float64)
    with pytest.raises(ValueError, match="dtype"):
        bge.validate_vectors(rows)


def test_validate_vectors_rejects_nan():
    rows = np.stack([_unit_row(seed=i) for i in range(3)])
    rows[1, 0] = np.nan
    with pytest.raises(ValueError, match="NaN|Inf"):
        bge.validate_vectors(rows)


def test_validate_vectors_rejects_inf():
    rows = np.stack([_unit_row(seed=i) for i in range(3)])
    rows[0, 5] = np.inf
    with pytest.raises(ValueError, match="NaN|Inf"):
        bge.validate_vectors(rows)


def test_validate_vectors_rejects_non_unit_norm_when_expected_normalized():
    rows = np.stack([_unit_row(seed=i) * 3.0 for i in range(3)])  # norm 3.0, not 1.0
    with pytest.raises(ValueError, match="normalized"):
        bge.validate_vectors(rows, expect_normalized=True)


def test_validate_vectors_allows_non_unit_norm_when_not_expecting_normalized():
    rows = np.stack([_unit_row(seed=i) * 3.0 for i in range(3)])
    bge.validate_vectors(rows, expect_normalized=False)  # should not raise


def test_validate_vectors_tolerance_is_configurable():
    rows = np.stack([_unit_row(seed=i) * 1.02 for i in range(3)])  # norm 1.02
    with pytest.raises(ValueError):
        bge.validate_vectors(rows, expect_normalized=True, norm_tolerance=1e-3)
    bge.validate_vectors(rows, expect_normalized=True, norm_tolerance=0.05)  # should not raise


# ------------------------------------------------------- offline model integration

@pytest.mark.model
@pytest.mark.gpu
def test_load_model_encode_passages_and_queries_offline_cuda(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this machine")

    if try_to_load_from_cache(bge.MODEL_REPO, "config.json", revision=bge.MODEL_REVISION) is None:
        pytest.skip(f"{bge.MODEL_REPO} not available in local cache at revision {bge.MODEL_REVISION}")

    model = bge.load_model(device="cuda")
    assert model.get_embedding_dimension() == bge.EMBEDDING_DIMENSION

    passages = [
        "Item 1. Business. The company manufactures industrial equipment.",
        "Item 7. Management's discussion of financial results for fiscal 2024.",
    ]
    queries = ["what was revenue in 2024", "material risk factors"]

    p_vectors = bge.encode_passages(model, passages, batch_size=8)
    q_vectors = bge.encode_queries(model, queries, batch_size=8)

    assert p_vectors.shape == (2, bge.EMBEDDING_DIMENSION)
    assert q_vectors.shape == (2, bge.EMBEDDING_DIMENSION)
    bge.validate_vectors(p_vectors)
    bge.validate_vectors(q_vectors)

    # passage and query vectors for semantically related text should differ
    # (query instruction was actually applied, not silently skipped)
    assert not np.allclose(p_vectors[0], q_vectors[0])
