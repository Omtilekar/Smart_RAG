"""Task 3.9 - portable tests for src.retrieval.filtered. Fake encode/
search functions - no real LanceDB, no GPU, no model, no network."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest

from src.retrieval.filtered import FilterError, MetadataFilteredRetriever, build_predicate


class _FakeSpec:
    dimension = 4


def _fake_encode(spec, model, texts, batch_size):
    return np.zeros((len(texts), 4), dtype=np.float32)


def _fake_result_table(tag: str) -> pa.Table:
    return pa.table({
        "chunk_id": [f"{tag}::c1"], "document_id": [f"{tag}.htm"], "cik": [1], "company": ["C"],
        "form_type": ["10-K"], "fiscal_year": [2019], "source": ["s"], "source_filename": ["f"],
        "source_split": ["dev"], "ordinal": [0], "text": ["t"], "token_count": [1],
        "chunk_config_hash": ["h" * 64], "normalizer_version": ["v1"],
        "normalization_build_sha256": ["n" * 64], "development_manifest_sha256": ["m" * 64],
        "_distance": [0.1],
    })


# --------------------------------------------------------------- build_predicate

def test_build_predicate_both_none():
    assert build_predicate(None, None) is None


def test_build_predicate_cik_only():
    assert build_predicate(12345, None) == "cik = 12345"


def test_build_predicate_fiscal_year_only():
    assert build_predicate(None, 2019) == "fiscal_year = 2019"


def test_build_predicate_both():
    assert build_predicate(12345, 2019) == "cik = 12345 AND fiscal_year = 2019"


def test_build_predicate_rejects_non_int_cik():
    with pytest.raises(FilterError):
        build_predicate("12345", None)


def test_build_predicate_rejects_bool_cik():
    with pytest.raises(FilterError):
        build_predicate(True, None)


# --------------------------------------------------------------- MetadataFilteredRetriever

def test_retriever_uses_unfiltered_search_fn_when_no_filter_given():
    calls = {"unfiltered": 0, "filtered": 0}

    def unfiltered_fn(table, qvec, limit, expected_dimension):
        calls["unfiltered"] += 1
        return _fake_result_table("unfiltered")

    def filtered_fn(table, qvec, limit, where, expected_dimension):
        calls["filtered"] += 1
        return _fake_result_table("filtered")

    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None,
                                           encode_fn=_fake_encode, filtered_search_fn=filtered_fn,
                                           unfiltered_search_fn=unfiltered_fn)
    results = retriever.retrieve("question", k=10)
    assert calls == {"unfiltered": 1, "filtered": 0}
    assert results[0].chunk_id == "unfiltered::c1"
    assert retriever.last_stats.filtered is False
    assert retriever.last_stats.predicate is None


def test_retriever_uses_filtered_search_fn_when_cik_and_year_given():
    calls = {"unfiltered": 0, "filtered": 0}
    seen_where = {}

    def unfiltered_fn(table, qvec, limit, expected_dimension):
        calls["unfiltered"] += 1
        return _fake_result_table("unfiltered")

    def filtered_fn(table, qvec, limit, where, expected_dimension):
        calls["filtered"] += 1
        seen_where["where"] = where
        return _fake_result_table("filtered")

    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None,
                                           encode_fn=_fake_encode, filtered_search_fn=filtered_fn,
                                           unfiltered_search_fn=unfiltered_fn)
    results = retriever.retrieve("question", k=10, cik=12345, fiscal_year=2019)
    assert calls == {"unfiltered": 0, "filtered": 1}
    assert seen_where["where"] == "cik = 12345 AND fiscal_year = 2019"
    assert results[0].chunk_id == "filtered::c1"
    assert retriever.last_stats.filtered is True


def test_retriever_partial_filter_cik_only_still_filters():
    def filtered_fn(table, qvec, limit, where, expected_dimension):
        assert where == "cik = 42"
        return _fake_result_table("filtered")

    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None,
                                           encode_fn=_fake_encode, filtered_search_fn=filtered_fn,
                                           unfiltered_search_fn=lambda *a, **k: _fake_result_table("unfiltered"))
    retriever.retrieve("q", k=5, cik=42)
    assert retriever.last_stats.filtered is True


def test_retriever_rejects_empty_question():
    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None, encode_fn=_fake_encode)
    with pytest.raises(ValueError):
        retriever.retrieve("")


def test_retriever_rejects_non_string_question():
    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None, encode_fn=_fake_encode)
    with pytest.raises(TypeError):
        retriever.retrieve(123)


@pytest.mark.parametrize("bad_k", [0, -1, True, 1.5])
def test_retriever_rejects_bad_k(bad_k):
    retriever = MetadataFilteredRetriever(_FakeSpec(), model=None, table=None, encode_fn=_fake_encode)
    with pytest.raises((TypeError, ValueError)):
        retriever.retrieve("q", k=bad_k)
