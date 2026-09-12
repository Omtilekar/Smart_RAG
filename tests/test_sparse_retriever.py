"""Task 3.4 - portable tests for src.retrieval.sparse.SparseRetriever.
Uses a tiny disposable synthetic LanceDB FTS table (or a fake injected
`search_fn`) - no real corpus, no GPU, no network, no model download."""

from __future__ import annotations

import ast
from pathlib import Path

import pyarrow as pa
import pytest

from src.index import lancedb_fts as fts
from src.retrieval.sparse import SparseRetriever, SparseRetrievalResult

REPO_ROOT = Path(__file__).resolve().parents[1]


def _real_table(tmp_path):
    db = fts.open_database(tmp_path / "probe")
    rows = {
        "chunk_id": ["c1", "c2", "c3"],
        "document_id": ["d1", "d1", "d2"],
        "text": ["revenue revenue increased", "revenue increased", "net income decreased"],
        "cik": [1, 1, 2],
        "company": ["Acme", "Acme", "Beta"],
        "form_type": ["10-K", "10-K", "10-K"],
        "fiscal_year": [2020, 2020, 2019],
        "source": ["edgar_corpus"] * 3,
        "source_filename": ["a.htm", "a.htm", "b.htm"],
        "source_split": ["dev"] * 3,
        "ordinal": [0, 1, 0],
        "token_count": [4, 3, 3],
        "chunk_config_hash": ["h" * 64] * 3,
        "normalizer_version": ["v1"] * 3,
        "normalization_build_sha256": ["n" * 64] * 3,
        "development_manifest_sha256": ["m" * 64] * 3,
    }
    table = fts.create_sparse_table(db, pa.table(rows))
    fts.build_fts_index(table)
    return table


# --------------------------------------------------------------- validation

def test_retrieve_rejects_empty_question(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    with pytest.raises(ValueError):
        retriever.retrieve("")


def test_retrieve_rejects_whitespace_question(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    with pytest.raises(ValueError):
        retriever.retrieve("   ")


def test_retrieve_rejects_non_string_question(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    with pytest.raises(TypeError):
        retriever.retrieve(12345)


@pytest.mark.parametrize("bad_k", [0, -1, True, 1.5, "10"])
def test_retrieve_rejects_bad_k(tmp_path, bad_k):
    retriever = SparseRetriever(_real_table(tmp_path))
    with pytest.raises((TypeError, ValueError)):
        retriever.retrieve("revenue", k=bad_k)


# --------------------------------------------------------------- schema / score contract

def test_retrieve_returns_stable_schema_and_faithful_native_score(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    results = retriever.retrieve("revenue", k=10)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, SparseRetrievalResult)
        assert r.score == r.sparse_score
        assert r.distance == 0.0  # documented sentinel, never a fake transform
    assert results[0].chunk_id == "c1"  # "revenue" appears twice in c1, once in c2
    assert results[0].sparse_score > results[1].sparse_score


def test_retrieve_does_not_expose_internal_index_object(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    results = retriever.retrieve("revenue", k=10)
    for r in results:
        assert not hasattr(r, "table")
        assert not hasattr(r, "_table")


def test_rank_is_one_based_and_matches_return_order(tmp_path):
    retriever = SparseRetriever(_real_table(tmp_path))
    results = retriever.retrieve("revenue", k=10)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))


def test_retrieve_uses_injected_search_fn_without_touching_real_table():
    calls = []

    def fake_search(table, question, k):
        calls.append((question, k))
        return pa.table({
            "chunk_id": ["x"], "document_id": ["y"], "text": ["z"], "cik": [1], "company": ["C"],
            "form_type": ["10-K"], "fiscal_year": [2020], "source": ["edgar_corpus"], "source_filename": ["f"],
            "source_split": ["dev"], "ordinal": [0], "token_count": [1], "chunk_config_hash": ["h" * 64],
            "normalizer_version": ["v1"], "normalization_build_sha256": ["n" * 64],
            "development_manifest_sha256": ["m" * 64], "_score": [1.23],
        })

    retriever = SparseRetriever(table=None, search_fn=fake_search)
    results = retriever.retrieve("some question", k=7)
    assert calls == [("some question", 7)]
    assert results[0].sparse_score == 1.23


# --------------------------------------------------------------- static guards: no dense/generation/rerank/router/crag

_FORBIDDEN_SUBSTRINGS = (
    "embeddings", "sentence_transformers", "torch", "generation", "llm_judge",
    "rerank", "router", "crag", "test_access",
)


def _imported_module_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("relative_path", [
    "src/retrieval/sparse.py",
    "src/index/lancedb_fts.py",
])
def test_module_never_imports_dense_generation_rerank_router_crag_or_test_access(relative_path):
    tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        lowered = module.lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, f"{relative_path} unexpectedly imports {module!r} (matches {forbidden!r})"
