"""Tests for src/index/lancedb_index_full.py (Task 4.4).

Uses temporary LanceDB directories (pytest tmp_path) and tiny synthetic
24-column data throughout - never touches the real 10,487,096-row
production index (artifacts/indexes_full/). The real build is
scripts/build_vector_index_full.py's own run, not a unit test.
"""

import datetime

import numpy as np
import pyarrow as pa
import pytest

from src.index import lancedb_index_full as idxf
from src.index.lancedb_index import exact_cosine_search, exact_cosine_search_filtered

DIM = idxf.EMBEDDING_DIMENSION


def _unit_vector(seed: int, dim: int = DIM) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.tolist()


def _sample_table(n: int = 5) -> pa.Table:
    return pa.table({
        "chunk_schema_version": [2] * n,
        "chunk_uid": [f"uid-{i}" for i in range(n)],
        "chunk_local_id": [f"local-{i}" for i in range(n)],
        "document_id": [f"doc{i}.htm" for i in range(n)],
        "accession": [f"0000000000-00-{i:06d}" for i in range(n)],
        "cik": [1000 + i for i in range(n)],
        "company": [f"COMPANY {i}" for i in range(n)],
        "form_type": ["10-K"] * n,
        "fiscal_year": [2018 + (i % 3) for i in range(n)],
        "period_end": [datetime.date(2018, 12, 31)] * n,
        "filed_date": [datetime.date(2019, 2, 1)] * n,
        "sic": [1000] * n,
        "section_id": [None] * n,
        "section_title": [None] * n,
        "ordinal": [0] * n,
        "char_start": [0] * n,
        "char_end": [10] * n,
        "content_type": ["text"] * n,
        "table_id": [None] * n,
        "source": ["edgar_corpus"] * n,
        "text": [f"chunk text {i}" for i in range(n)],
        "token_count": [10] * n,
        "chunk_config_hash": ["h" * 64] * n,
        "vector": [_unit_vector(i) for i in range(n)],
    })


# ------------------------------------------------------- table creation

def test_create_chunk_table_name_and_row_count(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    assert table.count_rows() == 5
    assert idxf.TABLE_NAME == "chunks"
    assert db.list_tables().tables == ["chunks"]


def test_create_chunk_table_retains_all_24_columns(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(3))
    assert set(table.schema.names) == set(idxf.EXPECTED_COLUMNS)
    assert len(idxf.EXPECTED_COLUMNS) == 24


def test_create_chunk_table_creates_no_index_at_all(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    assert table.list_indices() == []


def test_append_shard_accumulates_rows(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(3))
    idxf.append_shard(table, _sample_table(2))
    assert table.count_rows() == 5


# ------------------------------------------------------- schema validation

def test_validate_shard_schema_passes_for_identical_schema():
    a = _sample_table(3)
    b = _sample_table(5)
    idxf.validate_shard_schema(b, reference_schema=a.schema)  # should not raise


def test_validate_shard_schema_rejects_extra_column():
    a = _sample_table(3)
    b = _sample_table(3).append_column("extra", pa.array([1, 2, 3]))
    with pytest.raises(idxf.VectorIndexFullError):
        idxf.validate_shard_schema(b, reference_schema=a.schema)


def test_validate_shard_schema_rejects_missing_column():
    a = _sample_table(3)
    b = _sample_table(3).drop(["company"])
    with pytest.raises(idxf.VectorIndexFullError):
        idxf.validate_shard_schema(b, reference_schema=a.schema)


# ------------------------------------------------------- validate_chunk_table

def test_validate_chunk_table_passes_for_correct_table(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    idxf.validate_chunk_table(table, expected_row_count=5)  # should not raise


def test_validate_chunk_table_rejects_wrong_row_count(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    with pytest.raises(idxf.VectorIndexFullError, match="row count"):
        idxf.validate_chunk_table(table, expected_row_count=999)


def test_validate_chunk_table_rejects_missing_column(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    incomplete = _sample_table(3).drop(["company"])
    table = idxf.create_chunk_table(db, incomplete)
    with pytest.raises(idxf.VectorIndexFullError, match="schema mismatch"):
        idxf.validate_chunk_table(table, expected_row_count=3)


def test_validate_chunk_table_passes_with_scalar_indexes_present(tmp_path):
    # Unlike Task 1.5's stricter module, a scalar (non-vector) index must
    # NOT be treated as a violation here.
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    from lancedb.index import BTree
    table.create_index("cik", config=BTree(), name="cik_btree", replace=False)
    idxf.validate_chunk_table(table, expected_row_count=5)  # should not raise


# ------------------------------------------------------- scalar indexes

def test_build_scalar_indexes_creates_expected_columns(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    built = idxf.build_scalar_indexes(table)
    assert set(built) == set(idxf.SCALAR_INDEX_COLUMNS)
    idxf.validate_scalar_indexes(table)  # should not raise


def test_build_scalar_indexes_is_idempotent(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    idxf.build_scalar_indexes(table)
    second = idxf.build_scalar_indexes(table)
    assert second == []  # nothing left to build - never silently rebuilds


def test_validate_scalar_indexes_rejects_missing_index(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    with pytest.raises(idxf.VectorIndexFullError, match="missing"):
        idxf.validate_scalar_indexes(table)


def test_no_vector_ann_index_created_by_scalar_index_build(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    table = idxf.create_chunk_table(db, _sample_table(5))
    idxf.build_scalar_indexes(table)
    idxf.validate_chunk_table(table, expected_row_count=5)  # should not raise


# --------------------------------------------- reused Task 1.5 search helpers

def test_exact_cosine_search_self_match_ranks_first_1024d(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    data = _sample_table(5)
    table = idxf.create_chunk_table(db, data)

    query = data.column("vector")[0].as_py()
    results = exact_cosine_search(table, query, limit=5, expected_dimension=DIM)

    uids = results.column("chunk_uid").to_pylist()
    dists = results.column("_distance").to_pylist()
    assert uids[0] == "uid-0"
    assert dists[0] == pytest.approx(0.0, abs=1e-5)
    assert dists == sorted(dists)


def test_exact_cosine_search_filtered_by_cik(tmp_path):
    db = idxf.open_database(tmp_path / "db")
    data = _sample_table(5)
    table = idxf.create_chunk_table(db, data)
    idxf.build_scalar_indexes(table)

    query = data.column("vector")[2].as_py()
    results = exact_cosine_search_filtered(
        table, query, limit=5, where="cik = 1002", expected_dimension=DIM
    )
    assert results.num_rows == 1
    assert results.column("chunk_uid")[0].as_py() == "uid-2"


# --------------------------------------------------- real index (local_data)
#
# Deliberately does NOT perform an exact_cosine_search: a single query
# against the real 10,487,096-row table takes ~30s (measured directly -
# see project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md), which would make
# this test unacceptably slow to run routinely. This checks structural
# integrity only (row count/schema/scalar indexes/no ANN index) - the
# real self-retrieval/search-latency evidence lives in
# results/phase_4_4_full_corpus_vector_index_summary.json, produced by
# scripts/build_vector_index_full.py's own run, not by pytest.

PHASE_4_1_CONFIG_HASH = "754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
MODEL_REPO = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
EXPECTED_ROW_COUNT = 10_487_096


@pytest.mark.local_data
def test_real_task_4_4_index_structural_integrity():
    from src.storage import get_storage

    storage = get_storage()
    db_path = storage.index_dir_full(PHASE_4_1_CONFIG_HASH, CHUNK_CONFIG_HASH, MODEL_REPO, MODEL_REVISION)
    if not db_path.is_dir():
        pytest.skip(f"Task 4.4 full-corpus index not present at {db_path}")

    db = idxf.open_database(db_path)
    table = idxf.open_chunk_table(db)

    idxf.validate_chunk_table(table, expected_row_count=EXPECTED_ROW_COUNT)
    idxf.validate_scalar_indexes(table)
