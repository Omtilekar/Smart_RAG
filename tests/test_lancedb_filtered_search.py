"""Task 3.9 - portable tests for src.index.lancedb_index.exact_cosine_search_filtered.
Tiny synthetic LanceDB tables (pytest tmp_path) - never touches the real
project index."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest

from src.index import lancedb_index as idx

DIM = idx.EMBEDDING_DIMENSION


def _unit_vector(seed: int, dim: int = DIM) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype(np.float32)
    return (v / np.linalg.norm(v)).tolist()


def _mixed_cik_year_table(n: int = 20) -> pa.Table:
    ciks = [111] * 5 + [222] * (n - 5)  # cik=111 is rare (5 rows)
    years = [2018] * 3 + [2019] * 2 + [2020] * (n - 5)
    return pa.table({
        "chunk_id": [f"doc{i}.htm::chunk0" for i in range(n)],
        "document_id": [f"doc{i}.htm" for i in range(n)],
        "cik": ciks, "company": [f"COMPANY {i}" for i in range(n)],
        "form_type": ["10-K"] * n, "fiscal_year": years,
        "source": ["edgar_corpus"] * n, "source_filename": [f"doc{i}.htm" for i in range(n)],
        "source_split": ["train"] * n, "ordinal": [0] * n, "text": [f"chunk text {i}" for i in range(n)],
        "token_count": [10] * n, "chunk_config_hash": ["abc123"] * n,
        "normalizer_version": ["phase1-minimal-v1"] * n, "normalization_build_sha256": ["x" * 64] * n,
        "development_manifest_sha256": ["y" * 64] * n, "vector": [_unit_vector(i) for i in range(n)],
    })


def _open_table(tmp_path):
    import lancedb
    db = lancedb.connect(str(tmp_path))
    return db.create_table("chunks", data=_mixed_cik_year_table())


def test_filtered_search_returns_only_matching_rows(tmp_path):
    table = _open_table(tmp_path)
    q = _unit_vector(0)
    result = idx.exact_cosine_search_filtered(table, q, limit=50, where="cik = 111")
    assert set(result.column("cik").to_pylist()) == {111}


def test_filtered_search_is_a_true_prefilter_not_a_postfilter(tmp_path):
    # cik=111 has only 5 rows; limit=50 far exceeds that - a postfilter
    # (top-50 nearest neighbors THEN filtered) would likely lose some of
    # the 5 true matches since cik=222 dominates the table (15/20 rows).
    table = _open_table(tmp_path)
    q = _unit_vector(0)
    result = idx.exact_cosine_search_filtered(table, q, limit=50, where="cik = 111")
    assert result.num_rows == 5


def test_filtered_search_compound_predicate(tmp_path):
    table = _open_table(tmp_path)
    q = _unit_vector(0)
    result = idx.exact_cosine_search_filtered(table, q, limit=50, where="cik = 111 AND fiscal_year = 2018")
    assert result.num_rows == 3
    assert set(result.column("fiscal_year").to_pylist()) == {2018}


def test_filtered_search_rejects_nonpositive_limit(tmp_path):
    table = _open_table(tmp_path)
    with pytest.raises(idx.VectorIndexError):
        idx.exact_cosine_search_filtered(table, _unit_vector(0), limit=0, where="cik = 111")


def test_filtered_search_rejects_malformed_query_vector(tmp_path):
    table = _open_table(tmp_path)
    with pytest.raises(idx.VectorIndexError):
        idx.exact_cosine_search_filtered(table, [1.0, 2.0], limit=5, where="cik = 111")


def test_filtered_search_no_matching_rows_returns_empty(tmp_path):
    table = _open_table(tmp_path)
    result = idx.exact_cosine_search_filtered(table, _unit_vector(0), limit=50, where="cik = 999999")
    assert result.num_rows == 0


def test_filtered_search_ranking_order_matches_unfiltered_within_subset(tmp_path):
    table = _open_table(tmp_path)
    q = _unit_vector(0)
    filtered = idx.exact_cosine_search_filtered(table, q, limit=50, where="cik = 222")
    distances = filtered.column("_distance").to_pylist()
    assert distances == sorted(distances)
