"""Task 3.6 - portable tests for src.retrieval.reranked.RerankedRetriever.
Fake base retriever + fake score function - no real LanceDB, no GPU, no
model, no network."""

from __future__ import annotations

import numpy as np
import pytest

from src.retrieval.reranked import RerankedResult, RerankedRetriever


class _R:
    def __init__(self, chunk_id, rank, text, document_id="d1"):
        self.chunk_id, self.rank, self.text, self.document_id = chunk_id, rank, text, document_id
        self.score, self.distance = 0.5, 0.5


class _FakeBaseRetriever:
    def __init__(self, results):
        self._results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, question, k):
        self.calls.append((question, k))
        return self._results[:k]


def _fake_score_fn_reverses_order(model, question, texts):
    # Assigns HIGHER scores to LATER items - deterministically reverses order.
    n = len(texts)
    return np.array([float(i) for i in range(n)], dtype=np.float32)


def test_reranker_reverses_order_when_scores_favor_later_items():
    base = [_R("A", 1, "first"), _R("B", 2, "second"), _R("C", 3, "third")]
    retriever = RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=3, score_fn=_fake_score_fn_reverses_order)
    results = retriever.retrieve("q", k=3)
    assert [r.chunk_id for r in results] == ["C", "B", "A"]
    assert [r.rank for r in results] == [1, 2, 3]


def test_reranked_result_preserves_base_rank():
    base = [_R("A", 1, "first"), _R("B", 2, "second")]
    retriever = RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=2, score_fn=_fake_score_fn_reverses_order)
    results = retriever.retrieve("q", k=2)
    top = results[0]
    assert top.chunk_id == "B"
    assert top.base_rank == 2  # was rank 2 in the base list, promoted to rank 1


def test_reranked_result_delegates_metadata_to_base():
    base = [_R("A", 1, "hello", document_id="docX")]
    retriever = RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=1, score_fn=lambda m, q, t: np.array([1.0], dtype=np.float32))
    results = retriever.retrieve("q", k=1)
    assert results[0].document_id == "docX"
    assert results[0].text == "hello"
    assert isinstance(results[0], RerankedResult)


def test_reranker_truncates_to_requested_k():
    base = [_R(f"c{i}", i, f"text{i}") for i in range(1, 6)]
    retriever = RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=5,
                                   score_fn=lambda m, q, t: np.array([float(i) for i in range(5)], dtype=np.float32))
    results = retriever.retrieve("q", k=2)
    assert len(results) == 2


def test_base_results_not_mutated():
    base = [_R("A", 1, "first"), _R("B", 2, "second")]
    ranks_before = [r.rank for r in base]
    RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=2, score_fn=_fake_score_fn_reverses_order).retrieve("q", k=2)
    assert [r.rank for r in base] == ranks_before


# --------------------------------------------------------------- validation

def test_retrieve_rejects_empty_question():
    retriever = RerankedRetriever(_FakeBaseRetriever([]), model=None)
    with pytest.raises(ValueError):
        retriever.retrieve("")


def test_retrieve_rejects_non_string_question():
    retriever = RerankedRetriever(_FakeBaseRetriever([]), model=None)
    with pytest.raises(TypeError):
        retriever.retrieve(123)


@pytest.mark.parametrize("bad_k", [0, -1, True, 1.5])
def test_retrieve_rejects_bad_k(bad_k):
    retriever = RerankedRetriever(_FakeBaseRetriever([]), model=None)
    with pytest.raises((TypeError, ValueError)):
        retriever.retrieve("q", k=bad_k)


def test_k_exceeding_base_k_rejected():
    retriever = RerankedRetriever(_FakeBaseRetriever([_R("A", 1, "t")]), model=None, base_k=1)
    with pytest.raises(ValueError):
        retriever.retrieve("q", k=5)


# --------------------------------------------------------------- score validation surfaces

def test_score_count_mismatch_raises():
    base = [_R("A", 1, "t"), _R("B", 2, "t")]
    retriever = RerankedRetriever(_FakeBaseRetriever(base), model=None, base_k=2,
                                   score_fn=lambda m, q, t: np.array([1.0], dtype=np.float32))
    with pytest.raises(ValueError):
        retriever.retrieve("q", k=2)


# --------------------------------------------------------------- base retriever called exactly once

def test_base_retriever_called_exactly_once():
    base = [_R("A", 1, "t")]
    fake = _FakeBaseRetriever(base)
    retriever = RerankedRetriever(fake, model=None, base_k=1, score_fn=lambda m, q, t: np.array([1.0], dtype=np.float32))
    retriever.retrieve("some question", k=1)
    assert fake.calls == [("some question", 1)]
