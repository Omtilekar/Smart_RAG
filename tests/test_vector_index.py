"""Tests for src/index/lancedb_index.py.

Uses temporary LanceDB directories (pytest tmp_path) and tiny synthetic
data throughout - never touches the real 162,357-row project index
(artifacts/indexes/). The real index build is
scripts/build_vector_index.py's own run (Task 1.5 Step 37), not a unit
test.
"""

import numpy as np
import pyarrow as pa
import pytest

from src.index import lancedb_index as idx

DIM = idx.EMBEDDING_DIMENSION


def _unit_vector(seed: int, dim: int = DIM) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.tolist()


def _sample_table(n: int = 5) -> pa.Table:
    return pa.table({
        "chunk_id": [f"doc{i}.htm::chunk0" for i in range(n)],
        "document_id": [f"doc{i}.htm" for i in range(n)],
        "cik": [1000 + i for i in range(n)],
        "company": [f"COMPANY {i}" for i in range(n)],
        "form_type": ["10-K"] * n,
        "fiscal_year": [2018] * n,
        "source": ["edgar_corpus"] * n,
        "source_filename": [f"doc{i}.htm" for i in range(n)],
        "source_split": ["train"] * n,
        "ordinal": [0] * n,
        "text": [f"chunk text {i}" for i in range(n)],
        "token_count": [10] * n,
        "chunk_config_hash": ["abc123"] * n,
        "normalizer_version": ["phase1-minimal-v1"] * n,
        "normalization_build_sha256": ["x" * 64] * n,
        "development_manifest_sha256": ["y" * 64] * n,
        "vector": [_unit_vector(i) for i in range(n)],
    })


# ------------------------------------------------------- table creation

def test_create_chunk_table_name_and_row_count(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(5))
    assert table.count_rows() == 5
    assert idx.TABLE_NAME == "chunks"
    assert db.list_tables().tables == ["chunks"]


def test_create_chunk_table_retains_all_17_columns(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(3))
    assert set(table.schema.names) == set(idx.EXPECTED_COLUMNS)
    assert len(idx.EXPECTED_COLUMNS) == 17


def test_create_chunk_table_creates_no_ann_index(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(5))
    assert table.list_indices() == []


def test_open_database_root_is_used_directly(tmp_path):
    db_path = tmp_path / "myindex"
    db = idx.open_database(db_path)
    idx.create_chunk_table(db, _sample_table(2))
    assert db_path.is_dir()
    assert (db_path / "chunks.lance").is_dir()


def test_open_chunk_table_after_reconnect(tmp_path):
    db_path = tmp_path / "db"
    db1 = idx.open_database(db_path)
    idx.create_chunk_table(db1, _sample_table(4))
    db2 = idx.open_database(db_path)
    table = idx.open_chunk_table(db2)
    assert table.count_rows() == 4


# ------------------------------------------------------- validate_chunk_table

def test_validate_chunk_table_passes_for_correct_table(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(5))
    idx.validate_chunk_table(table, expected_row_count=5)  # should not raise


def test_validate_chunk_table_rejects_wrong_row_count(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(5))
    with pytest.raises(idx.VectorIndexError, match="row count"):
        idx.validate_chunk_table(table, expected_row_count=999)


def test_validate_chunk_table_rejects_missing_column(tmp_path):
    db = idx.open_database(tmp_path / "db")
    incomplete = _sample_table(3).drop(["company"])
    table = idx.create_chunk_table(db, incomplete)
    with pytest.raises(idx.VectorIndexError, match="schema mismatch"):
        idx.validate_chunk_table(table, expected_row_count=3)


# ------------------------------------------------------- query vector validation

def test_validate_query_vector_accepts_correct_shape():
    v = idx.validate_query_vector(_unit_vector(0))
    assert v.shape == (DIM,)
    assert v.dtype == np.float32


def test_validate_query_vector_rejects_wrong_dimension():
    with pytest.raises(idx.VectorIndexError, match="384"):
        idx.validate_query_vector([0.1, 0.2, 0.3])


def test_validate_query_vector_rejects_empty():
    with pytest.raises(idx.VectorIndexError):
        idx.validate_query_vector(np.array([], dtype=np.float32))


def test_validate_query_vector_rejects_nan():
    v = np.array(_unit_vector(0))
    v[0] = np.nan
    with pytest.raises(idx.VectorIndexError, match="NaN|Inf"):
        idx.validate_query_vector(v)


def test_validate_query_vector_rejects_inf():
    v = np.array(_unit_vector(0))
    v[0] = np.inf
    with pytest.raises(idx.VectorIndexError, match="NaN|Inf"):
        idx.validate_query_vector(v)


def test_validate_query_vector_never_truncates_or_pads():
    # a too-long vector must be rejected outright, not truncated
    with pytest.raises(idx.VectorIndexError):
        idx.validate_query_vector(list(range(400)))


# ------------------------------------------------------- exact_cosine_search

def test_exact_cosine_search_self_match_ranks_first(tmp_path):
    db = idx.open_database(tmp_path / "db")
    data = _sample_table(5)
    table = idx.create_chunk_table(db, data)

    query = data.column("vector")[0].as_py()  # exact copy of row 0's own vector
    results = idx.exact_cosine_search(table, query, limit=5)

    ids = results.column("chunk_id").to_pylist()
    dists = results.column("_distance").to_pylist()
    assert ids[0] == "doc0.htm::chunk0"
    assert dists[0] == pytest.approx(0.0, abs=1e-5)
    assert dists == sorted(dists)  # ascending distance = descending similarity


def test_exact_cosine_search_orthogonal_ranks_worse_than_identical(tmp_path):
    db = idx.open_database(tmp_path / "db")
    data = pa.table({
        "chunk_id": ["same", "orthogonal", "opposite"],
        "document_id": ["d", "d", "d"], "cik": [1, 1, 1], "company": ["c", "c", "c"],
        "form_type": ["10-K"] * 3, "fiscal_year": [2020] * 3, "source": ["edgar_corpus"] * 3,
        "source_filename": ["d", "d", "d"], "source_split": ["train"] * 3, "ordinal": [0, 0, 0],
        "text": ["t", "t", "t"], "token_count": [1, 1, 1], "chunk_config_hash": ["h", "h", "h"],
        "normalizer_version": ["v", "v", "v"], "normalization_build_sha256": ["n" * 64] * 3,
        "development_manifest_sha256": ["m" * 64] * 3,
        "vector": [
            [1.0] + [0.0] * (DIM - 1),
            [0.0, 1.0] + [0.0] * (DIM - 2),
            [-1.0] + [0.0] * (DIM - 1),
        ],
    })
    table = idx.create_chunk_table(db, data)

    results = idx.exact_cosine_search(table, [1.0] + [0.0] * (DIM - 1), limit=3)
    ids = results.column("chunk_id").to_pylist()
    dists = dict(zip(ids, results.column("_distance").to_pylist()))
    assert ids[0] == "same"
    assert dists["same"] < dists["orthogonal"] < dists["opposite"]
    assert dists["same"] == pytest.approx(0.0, abs=1e-5)
    assert dists["orthogonal"] == pytest.approx(1.0, abs=1e-3)
    assert dists["opposite"] == pytest.approx(2.0, abs=1e-3)


def test_exact_cosine_search_returns_text_and_metadata(tmp_path):
    db = idx.open_database(tmp_path / "db")
    data = _sample_table(5)
    table = idx.create_chunk_table(db, data)
    results = idx.exact_cosine_search(table, data.column("vector")[0].as_py(), limit=1)
    for field in ("chunk_id", "text", "document_id", "cik", "fiscal_year", "_distance"):
        assert field in results.column_names


def test_exact_cosine_search_rejects_malformed_query(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(3))
    with pytest.raises(idx.VectorIndexError):
        idx.exact_cosine_search(table, [0.1, 0.2], limit=3)


def test_exact_cosine_search_rejects_nonpositive_limit(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(3))
    with pytest.raises(idx.VectorIndexError, match="limit"):
        idx.exact_cosine_search(table, _unit_vector(0), limit=0)


def test_exact_cosine_search_creates_no_ann_index(tmp_path):
    db = idx.open_database(tmp_path / "db")
    table = idx.create_chunk_table(db, _sample_table(5))
    idx.exact_cosine_search(table, _unit_vector(0), limit=3)
    assert table.list_indices() == []
