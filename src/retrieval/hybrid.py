"""Task 3.5 - the hybrid retriever boundary: composes Task 1.6/3.3's
dense retriever and Task 3.4's sparse retriever, then fuses their
candidate lists with Task 3.5's pure `rrf_fuse()`. Does not implement
fusion math itself (see `src.retrieval.fusion`) and does not implement
retrieval itself (see `src.retrieval.baseline.BaselineRetriever` and
`src.retrieval.sparse.SparseRetriever`) - this module only composes the
two.

No reranking, no generation, no metadata pre-filtering, and neither
parent index is modified here. A parent retriever failure (dense OR
sparse) is never silently swallowed into a one-arm result - it
propagates so a formal run fails clearly rather than being mislabeled
"hybrid" (Stage 5's "Parent failure behavior").
"""

from __future__ import annotations

from src.retrieval.fusion import DEFAULT_LIMIT, DEFAULT_RRF_K, FusedRetrievalResult, rrf_fuse


def _validate_question(question) -> None:
    if not isinstance(question, str):
        raise TypeError(f"question must be a str, got {type(question).__name__}")
    if not question.strip():
        raise ValueError("question must not be empty or whitespace-only")


def _validate_k(k) -> None:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")


class HybridRetriever:
    """`dense_retriever`/`sparse_retriever` are any object exposing
    `.retrieve(question, k) -> list[result]` with `.chunk_id`/`.rank`
    (Task 1.6's `BaselineRetriever` and Task 3.4's `SparseRetriever`
    satisfy this without modification - neither is subclassed or
    monkeypatched here)."""

    def __init__(self, dense_retriever, sparse_retriever, *,
                 rrf_k: int = DEFAULT_RRF_K, dense_k: int = DEFAULT_LIMIT, sparse_k: int = DEFAULT_LIMIT):
        self._dense_retriever = dense_retriever
        self._sparse_retriever = sparse_retriever
        self._rrf_k = rrf_k
        self._dense_k = dense_k
        self._sparse_k = sparse_k

    def retrieve(self, question: str, k: int = DEFAULT_LIMIT) -> list[FusedRetrievalResult]:
        _validate_question(question)
        _validate_k(k)

        dense_results = self._dense_retriever.retrieve(question, k=self._dense_k)
        sparse_results = self._sparse_retriever.retrieve(question, k=self._sparse_k)

        return rrf_fuse(dense_results, sparse_results, rrf_k=self._rrf_k, limit=k)


__all__ = ["HybridRetriever"]
