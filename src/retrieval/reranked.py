"""Task 3.6 - the reranked retriever boundary: composes a base retriever
(Task 1.6/3.3's dense retriever, in the Task 3.5-selected dense-only
configuration) with Task 3.6's cross-encoder reranker. Does not
implement scoring itself (see `src.rerank.cross_encoder`) and does not
implement retrieval itself (see `src.retrieval.baseline`) - this module
only composes the two.

Reranking never changes the candidate SET (`base_k` chunks in, the same
`base_k` chunks out, just reordered) - only their order. Candidate-set
recall (e.g. doc_recall@50 over the unreranked base_k pool) is therefore
identical before and after reranking by construction; only reranked
top-k quality (MRR/nDCG@10/Precision@5/Recall@5) can change. This module
never conflates the two.

No embedding is recomputed, no LanceDB index is touched, no generation
happens here. A base-retriever failure propagates rather than being
silently swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.rerank.cross_encoder import score_pairs, validate_scores

DEFAULT_BASE_K = 50


def _validate_question(question) -> None:
    if not isinstance(question, str):
        raise TypeError(f"question must be a str, got {type(question).__name__}")
    if not question.strip():
        raise ValueError("question must not be empty or whitespace-only")


def _validate_k(k, name: str = "k") -> None:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"{name} must be an int, got {type(k).__name__}")
    if k <= 0:
        raise ValueError(f"{name} must be positive, got {k}")


@dataclass(frozen=True)
class RerankedResult:
    """Wraps one base result with its reranker score and new rank.
    `base_rank` (the pre-rerank position) is preserved for provenance -
    never dropped."""
    rank: int
    reranker_score: float
    base_rank: int
    base: object  # the original base-retriever result object, untouched

    def __getattr__(self, item):
        # Delegates chunk_id/document_id/text/metadata access to the
        # wrapped base result - never copies/mutates it.
        return getattr(self.base, item)


class RerankedRetriever:
    """`base_retriever` is any object exposing `.retrieve(question, k) ->
    list[result]` with `.chunk_id`/`.rank` (Task 1.6's `BaselineRetriever`
    satisfies this without modification). `model` is a loaded
    `sentence_transformers.CrossEncoder`-compatible model (see
    `src.rerank.cross_encoder.load_model`)."""

    def __init__(self, base_retriever, model, *, base_k: int = DEFAULT_BASE_K, score_fn=score_pairs):
        self._base_retriever = base_retriever
        self._model = model
        self._base_k = base_k
        self._score_fn = score_fn

    def retrieve(self, question: str, k: int = DEFAULT_BASE_K) -> list[RerankedResult]:
        _validate_question(question)
        _validate_k(k)
        if k > self._base_k:
            raise ValueError(f"k={k} exceeds base_k={self._base_k} - cannot rerank beyond the retrieved candidate pool")

        base_results = self._base_retriever.retrieve(question, k=self._base_k)
        texts = [r.text for r in base_results]
        scores = self._score_fn(self._model, question, texts)
        validate_scores(scores, expected_count=len(base_results))

        order = np.argsort(-scores, kind="stable")
        reranked = [
            RerankedResult(rank=new_rank + 1, reranker_score=float(scores[i]),
                            base_rank=base_results[i].rank, base=base_results[i])
            for new_rank, i in enumerate(order)
        ]
        return reranked[:k]


__all__ = ["DEFAULT_BASE_K", "RerankedResult", "RerankedRetriever"]
