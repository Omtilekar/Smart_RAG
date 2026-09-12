"""Task 3.4 - portable tests for src.index.lancedb_fts against tiny
disposable synthetic tables. No real corpus, no GPU, no network, no model
download - matches the existing LanceDB-portable-test convention
(tests/test_vector_index.py)."""

from __future__ import annotations

import pyarrow as pa
import pytest

from src.index import lancedb_fts as fts


def _make_table(tmp_path, name="probe"):
    db = fts.open_database(tmp_path / name)
    data = pa.table({
        "chunk_id": ["c1", "c2", "c3", "c4"],
        "document_id": ["d1", "d1", "d2", "d2"],
        "text": [
            "revenue revenue revenue increased",
            "revenue increased",
            "net income decreased",
            "risk factors cybersecurity",
        ],
    })
    table = fts.create_sparse_table(db, data)
    fts.build_fts_index(table)
    return db, table


# --------------------------------------------------------------- build / validate

def test_build_creates_named_fts_index(tmp_path):
    db, table = _make_table(tmp_path)
    names = fts.existing_fts_index_names(table)
    assert names == [fts.FTS_INDEX_NAME]


def test_validate_sparse_table_passes_for_fresh_build(tmp_path):
    db, table = _make_table(tmp_path)
    fts.validate_sparse_table(table, expected_row_count=4)


def test_validate_sparse_table_rejects_wrong_row_count(tmp_path):
    db, table = _make_table(tmp_path)
    with pytest.raises(fts.SparseIndexError):
        fts.validate_sparse_table(table, expected_row_count=5)


def test_validate_sparse_table_rejects_missing_index(tmp_path):
    db = fts.open_database(tmp_path / "noindex")
    data = pa.table({"chunk_id": ["c1"], "document_id": ["d1"], "text": ["hello"]})
    table = fts.create_sparse_table(db, data)
    with pytest.raises(fts.SparseIndexError):
        fts.validate_sparse_table(table, expected_row_count=1)


def test_row_ids_and_document_ids_and_text_preserved(tmp_path):
    db, table = _make_table(tmp_path)
    arrow = table.to_arrow()
    assert arrow.column("chunk_id").to_pylist() == ["c1", "c2", "c3", "c4"]
    assert arrow.column("document_id").to_pylist() == ["d1", "d1", "d2", "d2"]
    assert arrow.column("text").to_pylist() == [
        "revenue revenue revenue increased", "revenue increased",
        "net income decreased", "risk factors cybersecurity",
    ]


# --------------------------------------------------------------- persistence

def test_index_persists_after_reopen_in_fresh_connection(tmp_path):
    db, table = _make_table(tmp_path)
    db2 = fts.open_database(tmp_path / "probe")
    table2 = fts.open_sparse_table(db2)
    fts.validate_sparse_table(table2, expected_row_count=4)
    results = fts.fts_search(table2, "revenue", limit=10).to_pylist()
    assert {r["chunk_id"] for r in results} == {"c1", "c2"}


# --------------------------------------------------------------- score field / direction / ranking

def test_native_score_field_is_score_and_higher_is_better(tmp_path):
    db, table = _make_table(tmp_path)
    results = fts.fts_search(table, "revenue", limit=10).to_pylist()
    assert all("_score" in r for r in results)
    by_id = {r["chunk_id"]: r["_score"] for r in results}
    assert by_id["c1"] > by_id["c2"]  # c1 mentions "revenue" 3x, c2 once


def test_ranking_order_matches_descending_score(tmp_path):
    db, table = _make_table(tmp_path)
    results = fts.fts_search(table, "revenue", limit=10).to_pylist()
    scores = [r["_score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_exact_term_query_matches_expected_documents(tmp_path):
    db, table = _make_table(tmp_path)
    results = fts.fts_search(table, "cybersecurity", limit=10).to_pylist()
    assert [r["chunk_id"] for r in results] == ["c4"]


# --------------------------------------------------------------- query sanitization / validation

def test_sanitize_fts_query_strips_only_ascii_double_quotes():
    assert fts.sanitize_fts_query('revenue "increased" now') == "revenue increased now"
    assert fts.sanitize_fts_query("no quotes here") == "no quotes here"
    assert fts.sanitize_fts_query("don't touch apostrophes") == "don't touch apostrophes"


def test_double_quote_query_would_error_without_sanitization(tmp_path):
    db, table = _make_table(tmp_path)
    with pytest.raises(ValueError):
        table.search('"revenue"', query_type="fts").limit(5).to_arrow()


def test_fts_search_sanitizes_double_quotes_and_does_not_raise(tmp_path):
    db, table = _make_table(tmp_path)
    results = fts.fts_search(table, '"revenue"', limit=10).to_pylist()
    assert len(results) >= 1


def test_fts_search_rejects_non_string_query(tmp_path):
    db, table = _make_table(tmp_path)
    with pytest.raises(fts.SparseIndexError):
        fts.fts_search(table, 12345, limit=10)


def test_fts_search_rejects_empty_and_whitespace_query(tmp_path):
    db, table = _make_table(tmp_path)
    with pytest.raises(fts.SparseIndexError):
        fts.fts_search(table, "", limit=10)
    with pytest.raises(fts.SparseIndexError):
        fts.fts_search(table, "   ", limit=10)


@pytest.mark.parametrize("bad_limit", [0, -1, True, 1.5, "10"])
def test_fts_search_rejects_bad_limit(tmp_path, bad_limit):
    db, table = _make_table(tmp_path)
    with pytest.raises(fts.SparseIndexError):
        fts.fts_search(table, "revenue", limit=bad_limit)


# --------------------------------------------------------------- special SEC lexical forms

def test_sec_style_and_unicode_queries_do_not_raise(tmp_path):
    db = fts.open_database(tmp_path / "sec_probe")
    data = pa.table({
        "chunk_id": ["c1"], "document_id": ["d1"],
        "text": ["Item 1A Risk Factors: R&D expenses grew 10.5% (fiscal 2020) - see 10-K/note 3/4."],
    })
    table = fts.create_sparse_table(db, data)
    fts.build_fts_index(table)
    for query in ["Item 1A", "10-K", "R&D", "10.5%", "(fiscal 2020)", "note 3/4",
                  "café naïve — unicode", "2020", "company's revenue"]:
        fts.fts_search(table, query, limit=10)  # must not raise


# --------------------------------------------------------------- identity

def test_sparse_index_identity_hash_deterministic():
    identity = fts.sparse_index_identity(
        chunk_schema_version=1, chunk_config_hash="a" * 64, lancedb_version="0.37.1",
    )
    h1 = fts.sparse_index_identity_hash(identity)
    h2 = fts.sparse_index_identity_hash(identity)
    assert h1 == h2
    assert len(h1) == 64


def test_sparse_index_identity_hash_changes_with_indexed_column():
    identity_a = fts.sparse_index_identity(
        chunk_schema_version=1, chunk_config_hash="a" * 64, lancedb_version="0.37.1", indexed_column="text",
    )
    identity_b = fts.sparse_index_identity(
        chunk_schema_version=1, chunk_config_hash="a" * 64, lancedb_version="0.37.1", indexed_column="body",
    )
    assert fts.sparse_index_identity_hash(identity_a) != fts.sparse_index_identity_hash(identity_b)


def test_sparse_index_identity_hash_changes_with_backend_config():
    identity_a = fts.sparse_index_identity(
        chunk_schema_version=1, chunk_config_hash="a" * 64, lancedb_version="0.37.1",
        fts_config={"stem": True},
    )
    identity_b = fts.sparse_index_identity(
        chunk_schema_version=1, chunk_config_hash="a" * 64, lancedb_version="0.37.1",
        fts_config={"stem": False},
    )
    assert fts.sparse_index_identity_hash(identity_a) != fts.sparse_index_identity_hash(identity_b)


def test_sparse_index_identity_hash_requires_all_fields():
    with pytest.raises(fts.SparseIndexError):
        fts.sparse_index_identity_hash({"chunk_config_hash": "a" * 64})


def test_sparse_index_identity_requires_valid_chunk_hash():
    with pytest.raises(Exception):
        fts.sparse_index_identity(
            chunk_schema_version=1, chunk_config_hash="not-a-hash", lancedb_version="0.37.1",
        )
