"""Tests for src/retrieval/baseline.py.

Portable tests use fake/injected encode_fn and search_fn - no real model or
LanceDB table is loaded, matching Task 1.6 Step 17's testability
requirement. The one test that touches the real cached BGE model and the
real Task 1.5 index is `model`+`gpu`+`local_data`-marked and skips cleanly
if either is unavailable, mirroring tests/test_baseline_embeddings.py and
tests/test_embedding_smoke.py's established pattern. Does not rebuild the
index inside pytest.
"""

import numpy as np
import pyarrow as pa
import pytest
from huggingface_hub import try_to_load_from_cache

from src.retrieval import baseline as br


def _fake_encode(model, texts, batch_size=1):
    """Deterministic fake query encoder - returns a distinct unit-ish
    vector per text, never a real BGE call."""
    n = len(texts)
    vecs = np.zeros((n, 384), dtype=np.float32)
    for i in range(n):
        vecs[i, 0] = 1.0  # nonzero, finite, fixed shape - content is irrelevant here
    return vecs


def _fake_search_factory(row_count: int, captured: dict):
    """Returns a fake search_fn that records what it was called with and
    returns `row_count` canned rows with strictly increasing _distance."""
    def _fake_search(table, query_vector, limit):
        captured["table"] = table
        captured["query_vector"] = query_vector
        captured["limit"] = limit
        n = min(row_count, limit)
        columns = {
            "chunk_id": [f"doc{i}.htm::chunk0" for i in range(n)],
            "document_id": [f"doc{i}.htm" for i in range(n)],
            "text": [f"chunk text {i}" for i in range(n)],
            "cik": [1000 + i for i in range(n)],
            "company": [f"COMPANY {i}" for i in range(n)],
            "form_type": ["10-K"] * n,
            "fiscal_year": [2018] * n,
            "source": ["edgar_corpus"] * n,
            "source_filename": [f"doc{i}.htm" for i in range(n)],
            "source_split": ["train"] * n,
            "ordinal": [0] * n,
            "token_count": [10] * n,
            "chunk_config_hash": ["abc123"] * n,
            "normalizer_version": ["phase1-minimal-v1"] * n,
            "normalization_build_sha256": ["x" * 64] * n,
            "development_manifest_sha256": ["y" * 64] * n,
            "_distance": [i * 0.1 for i in range(n)],
        }
        return pa.table(columns)
    return _fake_search


def _make_retriever(row_count=5, captured=None):
    captured = captured if captured is not None else {}
    retriever = br.BaselineRetriever(
        model=object(),  # never actually used by _fake_encode
        table=object(),  # never actually used by the fake search
        encode_fn=_fake_encode,
        search_fn=_fake_search_factory(row_count, captured),
    )
    return retriever, captured


# ------------------------------------------------------------------ k behavior

def test_default_k_returns_5_results():
    retriever, _ = _make_retriever(row_count=20)
    results = retriever.retrieve("what was revenue")
    assert len(results) == 5


def test_custom_k_10_returns_10_results():
    retriever, _ = _make_retriever(row_count=20)
    results = retriever.retrieve("what was revenue", k=10)
    assert len(results) == 10


def test_k_passed_through_to_search_as_limit():
    retriever, captured = _make_retriever(row_count=20)
    retriever.retrieve("question", k=7)
    assert captured["limit"] == 7


@pytest.mark.parametrize("bad_k", [0, -1, -5])
def test_invalid_nonpositive_k_rejected(bad_k):
    retriever, _ = _make_retriever()
    with pytest.raises(ValueError):
        retriever.retrieve("question", k=bad_k)


@pytest.mark.parametrize("bad_k", [5.0, "5", None, [5]])
def test_non_integer_k_rejected(bad_k):
    retriever, _ = _make_retriever()
    with pytest.raises(TypeError):
        retriever.retrieve("question", k=bad_k)


def test_bool_k_rejected():
    retriever, _ = _make_retriever()
    with pytest.raises(TypeError):
        retriever.retrieve("question", k=True)


# ---------------------------------------------------------------- input validation

def test_empty_question_rejected():
    retriever, _ = _make_retriever()
    with pytest.raises(ValueError):
        retriever.retrieve("")


def test_whitespace_only_question_rejected():
    retriever, _ = _make_retriever()
    with pytest.raises(ValueError):
        retriever.retrieve("   \n\t  ")


def test_non_string_question_rejected():
    retriever, _ = _make_retriever()
    with pytest.raises(TypeError):
        retriever.retrieve(12345)


# --------------------------------------------------------------- encoder/search calls

def test_encoder_called_exactly_once_per_retrieve():
    calls = []

    def counting_encode(model, texts, batch_size=1):
        calls.append(texts)
        return _fake_encode(model, texts, batch_size)

    retriever = br.BaselineRetriever(
        model=object(), table=object(),
        encode_fn=counting_encode, search_fn=_fake_search_factory(5, {}),
    )
    retriever.retrieve("what was revenue")
    assert len(calls) == 1
    assert calls[0] == ["what was revenue"]


def test_search_vector_is_384_dimensional():
    retriever, captured = _make_retriever(row_count=5)
    retriever.retrieve("question")
    assert captured["query_vector"].shape == (384,)


# ------------------------------------------------------------------------- rank

def test_rank_numbering_starts_at_1_and_is_sequential():
    retriever, _ = _make_retriever(row_count=5)
    results = retriever.retrieve("question", k=5)
    assert [r.rank for r in results] == [1, 2, 3, 4, 5]


def test_result_order_preserved_from_search():
    retriever, _ = _make_retriever(row_count=5)
    results = retriever.retrieve("question", k=5)
    assert [r.chunk_id for r in results] == [f"doc{i}.htm::chunk0" for i in range(5)]


# --------------------------------------------------------------- distance / score

def test_raw_distance_preserved_exactly():
    retriever, _ = _make_retriever(row_count=3)
    results = retriever.retrieve("question", k=3)
    assert [r.distance for r in results] == [0.0, 0.1, pytest.approx(0.2)]


@pytest.mark.parametrize("distance,expected_score", [
    (0.0, 1.0),
    (0.25, 0.75),
    (1.0, 0.0),
    (-1e-7, 1.0000001),
])
def test_score_equals_one_minus_distance(distance, expected_score):
    table = pa.table({f: [v] for f, v in {
        "chunk_id": "c", "document_id": "d", "text": "t", "cik": 1, "company": "co",
        "form_type": "10-K", "fiscal_year": 2020, "source": "edgar_corpus",
        "source_filename": "d", "source_split": "train", "ordinal": 0, "token_count": 1,
        "chunk_config_hash": "h", "normalizer_version": "v",
        "normalization_build_sha256": "n", "development_manifest_sha256": "m",
        "_distance": distance,
    }.items()})
    results = br._to_results(table)
    assert results[0].score == pytest.approx(expected_score, abs=1e-9)
    assert results[0].distance == distance


def test_score_is_not_clamped_above_one():
    # distance slightly negative (float rounding artifact, observed in Task 1.5's
    # self-retrieval check) must NOT be clamped back to distance=0/score=1
    table = pa.table({f: [v] for f, v in {
        "chunk_id": "c", "document_id": "d", "text": "t", "cik": 1, "company": "co",
        "form_type": "10-K", "fiscal_year": 2020, "source": "edgar_corpus",
        "source_filename": "d", "source_split": "train", "ordinal": 0, "token_count": 1,
        "chunk_config_hash": "h", "normalizer_version": "v",
        "normalization_build_sha256": "n", "development_manifest_sha256": "m",
        "_distance": -1.1920928955078125e-07,
    }.items()})
    results = br._to_results(table)
    assert results[0].score > 1.0


# ------------------------------------------------------------------- result schema

def test_vector_omitted_from_result():
    retriever, _ = _make_retriever(row_count=3)
    results = retriever.retrieve("question", k=3)
    for r in results:
        assert not hasattr(r, "vector")


def test_internal_distance_field_name_not_exposed():
    retriever, _ = _make_retriever(row_count=3)
    results = retriever.retrieve("question", k=3)
    for r in results:
        assert not hasattr(r, "_distance")


def test_approved_metadata_fields_present():
    retriever, _ = _make_retriever(row_count=1)
    r = retriever.retrieve("question", k=1)[0]
    expected = {
        "rank", "score", "distance", "chunk_id", "document_id", "text", "cik",
        "company", "form_type", "fiscal_year", "source", "source_filename",
        "source_split", "ordinal", "token_count", "chunk_config_hash",
        "normalizer_version", "normalization_build_sha256",
        "development_manifest_sha256",
    }
    actual = set(r.__dataclass_fields__.keys())
    assert actual == expected


# ------------------------------------------------------------------------ Unicode

def test_unicode_question_accepted():
    retriever, captured = _make_retriever(row_count=3)
    results = retriever.retrieve("café naïve “Item 7” revenue growth—2020", k=3)
    assert len(results) == 3


# ------------------------------------------------------------- real model/index

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"


@pytest.mark.model
@pytest.mark.gpu
@pytest.mark.local_data
def test_real_retrieve_k5_against_task_1_5_index(monkeypatch):
    import torch
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this machine")
    if try_to_load_from_cache(MODEL_NAME, "config.json", revision=MODEL_REVISION) is None:
        pytest.skip(f"{MODEL_NAME} not available in local cache at revision {MODEL_REVISION}")

    from src.storage import get_storage
    from src.embeddings.bge import load_model
    from src.index.lancedb_index import open_database, open_chunk_table

    storage = get_storage()
    db_path = storage.index_dir(CHUNK_CONFIG_HASH, MODEL_NAME)
    if not db_path.is_dir():
        pytest.skip(f"Task 1.5 index not present at {db_path}")

    model = load_model(device="cuda")
    db = open_database(db_path)
    table = open_chunk_table(db)

    retriever = br.BaselineRetriever(model=model, table=table)
    results = retriever.retrieve("what was the company's revenue", k=5)

    assert len(results) == 5
    for r in results:
        assert r.text
        assert r.chunk_id
        assert r.form_type == "10-K"
        assert not hasattr(r, "vector")
