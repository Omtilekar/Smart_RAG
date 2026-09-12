"""Task 3.5 - portable tests for src.retrieval.hybrid.HybridRetriever.
Uses fake injected dense/sparse retrievers - no real LanceDB, no GPU, no
model, no network."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.retrieval.hybrid import HybridRetriever

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeParentRetriever:
    def __init__(self, results):
        self._results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question, k):
        self.calls.append((question, k))
        return self._results


class _R:
    def __init__(self, chunk_id, rank, **extra):
        self.chunk_id, self.rank = chunk_id, rank
        for key, val in extra.items():
            setattr(self, key, val)


COMMON = dict(document_id="d1", text="t", cik=1, company="C", form_type="10-K", fiscal_year=2020,
              source="s", source_filename="f", source_split="dev", ordinal=0, token_count=1,
              chunk_config_hash="h" * 64)


class _FailingRetriever:
    def retrieve(self, question, k):
        raise RuntimeError("parent retrieval failed")


# --------------------------------------------------------------- composition

def test_dense_and_sparse_retrievers_each_called_exactly_once():
    dense = _FakeParentRetriever([_R("A", 1, **COMMON)])
    sparse = _FakeParentRetriever([_R("B", 1, sparse_score=1.0, **COMMON)])
    hybrid = HybridRetriever(dense, sparse, rrf_k=60, dense_k=50, sparse_k=50)

    hybrid.retrieve("some question", k=10)

    assert dense.calls == [("some question", 50)]
    assert sparse.calls == [("some question", 50)]


def test_hybrid_retrieve_returns_fused_results():
    dense = _FakeParentRetriever([_R("A", 1, **COMMON)])
    sparse = _FakeParentRetriever([_R("A", 1, sparse_score=1.0, **COMMON)])
    hybrid = HybridRetriever(dense, sparse)
    results = hybrid.retrieve("q", k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "A"
    assert results[0].in_dense and results[0].in_sparse


def test_requested_candidate_depths_are_passed_to_each_parent():
    dense = _FakeParentRetriever([_R("A", 1, **COMMON)])
    sparse = _FakeParentRetriever([_R("B", 1, sparse_score=1.0, **COMMON)])
    hybrid = HybridRetriever(dense, sparse, rrf_k=60, dense_k=30, sparse_k=20)
    hybrid.retrieve("q", k=10)
    assert dense.calls == [("q", 30)]
    assert sparse.calls == [("q", 20)]


# --------------------------------------------------------------- validation

def test_retrieve_rejects_empty_question():
    hybrid = HybridRetriever(_FakeParentRetriever([]), _FakeParentRetriever([]))
    with pytest.raises(ValueError):
        hybrid.retrieve("")


def test_retrieve_rejects_non_string_question():
    hybrid = HybridRetriever(_FakeParentRetriever([]), _FakeParentRetriever([]))
    with pytest.raises(TypeError):
        hybrid.retrieve(123)


@pytest.mark.parametrize("bad_k", [0, -1, True, 1.5])
def test_retrieve_rejects_bad_k(bad_k):
    hybrid = HybridRetriever(_FakeParentRetriever([]), _FakeParentRetriever([]))
    with pytest.raises((TypeError, ValueError)):
        hybrid.retrieve("q", k=bad_k)


# --------------------------------------------------------------- parent failure behavior

def test_dense_parent_failure_propagates_and_does_not_silently_degrade():
    hybrid = HybridRetriever(_FailingRetriever(), _FakeParentRetriever([_R("B", 1, sparse_score=1.0, **COMMON)]))
    with pytest.raises(RuntimeError, match="parent retrieval failed"):
        hybrid.retrieve("q", k=5)


def test_sparse_parent_failure_propagates_and_does_not_silently_degrade():
    hybrid = HybridRetriever(_FakeParentRetriever([_R("A", 1, **COMMON)]), _FailingRetriever())
    with pytest.raises(RuntimeError, match="parent retrieval failed"):
        hybrid.retrieve("q", k=5)


# --------------------------------------------------------------- static guards: no rerank/generation/router/crag/prefilter

_FORBIDDEN_SUBSTRINGS = ("rerank", "router", "crag", "generation", "llm_judge", "test_access", "prefilter")


def _imported_module_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


@pytest.mark.parametrize("relative_path", ["src/retrieval/hybrid.py", "src/retrieval/fusion.py"])
def test_module_never_imports_forbidden_components(relative_path):
    tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        lowered = module.lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, f"{relative_path} unexpectedly imports {module!r}"


@pytest.mark.parametrize("relative_path", ["src/retrieval/hybrid.py", "src/retrieval/fusion.py"])
def test_module_never_calls_lancedb_or_a_model_directly(relative_path):
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    assert "import lancedb" not in source
    assert "sentence_transformers" not in source
    assert "torch" not in source
