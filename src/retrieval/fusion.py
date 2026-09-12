"""Task 3.5 - pure Reciprocal Rank Fusion (RRF) over two already-ranked
parent result streams (Task 3.3's dense exact-cosine retriever and Task
3.4's sparse LanceDB-native FTS retriever). No I/O, no LanceDB, no model
loading, no network - takes plain ranked result objects in, returns
plain fused result objects out.

    RRF(d) = dense_contribution(d) + sparse_contribution(d)

    dense_contribution(d)  = 1 / (rrf_k + dense_rank(d))  if d in dense candidates, else 0
    sparse_contribution(d) = 1 / (rrf_k + sparse_rank(d)) if d in sparse candidates, else 0

Ranks are 1-based. Fusion uses ranks only - dense cosine distances and
sparse `_score` values are preserved on the fused result for provenance
but are NEVER normalized, scaled, or added into `rrf_score`. Fusion
happens at the `chunk_id` level, never `document_id` - document-level
deduplication belongs only to the evaluation metric logic already frozen
in Tasks 3.1/2.6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

DEFAULT_RRF_K = 60
DEFAULT_LIMIT = 50

# Every parent metadata field preserved on the fused result, beyond the
# fusion-specific fields (rank/chunk_id/document_id/text/rrf_score/
# dense_*/sparse_*/in_dense/in_sparse) themselves.
PROVENANCE_FIELDS: tuple[str, ...] = (
    "cik", "company", "form_type", "fiscal_year", "source", "source_filename",
    "source_split", "ordinal", "token_count", "chunk_config_hash",
)


class FusionError(ValueError):
    """Raised for invalid rrf_k/limit, a duplicate chunk_id within one
    parent stream, or a malformed parent result - never silently
    worked around."""


@dataclass(frozen=True)
class FusedRetrievalResult:
    rank: int
    chunk_id: str
    document_id: str
    text: str
    rrf_score: float
    dense_rank: int | None
    dense_distance: float | None
    dense_score: float | None
    sparse_rank: int | None
    sparse_score: float | None
    in_dense: bool
    in_sparse: bool
    cik: int
    company: str
    form_type: str
    fiscal_year: int
    source: str
    source_filename: str
    source_split: str
    ordinal: int
    token_count: int
    chunk_config_hash: str


def _validate_rrf_k(rrf_k: Any) -> None:
    if isinstance(rrf_k, bool) or not isinstance(rrf_k, int):
        raise FusionError(f"rrf_k must be an int, got {type(rrf_k).__name__}")
    if rrf_k <= 0:
        raise FusionError(f"rrf_k must be positive, got {rrf_k}")


def _validate_limit(limit: Any) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise FusionError(f"limit must be an int, got {type(limit).__name__}")
    if limit <= 0:
        raise FusionError(f"limit must be positive, got {limit}")


def _validate_rank(rank: Any, *, stream: str, chunk_id: str) -> int:
    if isinstance(rank, bool) or not isinstance(rank, int):
        raise FusionError(f"{stream} result {chunk_id!r} has a non-int rank: {rank!r}")
    if rank < 1:
        raise FusionError(f"{stream} result {chunk_id!r} has rank {rank} (< 1) - ranks are 1-based")
    return rank


def _index_by_chunk_id(results: Sequence[Any], *, stream: str) -> dict[str, Any]:
    by_id: dict[str, Any] = {}
    for r in results:
        cid = r.chunk_id
        _validate_rank(r.rank, stream=stream, chunk_id=cid)
        if cid in by_id:
            raise FusionError(f"duplicate chunk_id {cid!r} within the {stream} parent stream")
        by_id[cid] = r
    return by_id


def _metadata_from(r: Any) -> dict:
    return {field: getattr(r, field) for field in ("document_id", "text", *PROVENANCE_FIELDS)}


def _tiebreak_key(entry: dict) -> tuple:
    """Frozen Stage 3 deterministic tie-break: higher rrf_score -> lower
    best_parent_rank -> lower dense_rank (missing = infinity) -> lower
    sparse_rank (missing = infinity) -> lexical chunk_id ascending. Only
    ever changes the ORDER of exact-score ties."""
    dense_rank = entry["dense_rank"] if entry["dense_rank"] is not None else math.inf
    sparse_rank = entry["sparse_rank"] if entry["sparse_rank"] is not None else math.inf
    best_parent_rank = min(dense_rank, sparse_rank)
    return (-entry["rrf_score"], best_parent_rank, dense_rank, sparse_rank, entry["chunk_id"])


def rrf_fuse(dense_results: Sequence[Any], sparse_results: Sequence[Any], *,
             rrf_k: int = DEFAULT_RRF_K, limit: int = DEFAULT_LIMIT) -> list[FusedRetrievalResult]:
    """Fuses two parent result streams by `chunk_id`. Never mutates
    `dense_results`/`sparse_results` (only reads attributes off them).
    Deterministic: identical inputs always produce an identical output
    order, including tie order."""
    _validate_rrf_k(rrf_k)
    _validate_limit(limit)

    dense_by_id = _index_by_chunk_id(dense_results, stream="dense")
    sparse_by_id = _index_by_chunk_id(sparse_results, stream="sparse")

    union_ids = set(dense_by_id) | set(sparse_by_id)

    entries: list[dict] = []
    for cid in union_ids:
        dense_r = dense_by_id.get(cid)
        sparse_r = sparse_by_id.get(cid)

        dense_rank = dense_r.rank if dense_r is not None else None
        sparse_rank = sparse_r.rank if sparse_r is not None else None

        dense_contribution = 1.0 / (rrf_k + dense_rank) if dense_rank is not None else 0.0
        sparse_contribution = 1.0 / (rrf_k + sparse_rank) if sparse_rank is not None else 0.0

        metadata_source = dense_r if dense_r is not None else sparse_r
        entries.append({
            "chunk_id": cid,
            "rrf_score": dense_contribution + sparse_contribution,
            "dense_rank": dense_rank,
            "dense_distance": getattr(dense_r, "distance", None) if dense_r is not None else None,
            "dense_score": getattr(dense_r, "score", None) if dense_r is not None else None,
            "sparse_rank": sparse_rank,
            "sparse_score": getattr(sparse_r, "sparse_score", None) if sparse_r is not None else None,
            "in_dense": dense_r is not None,
            "in_sparse": sparse_r is not None,
            **_metadata_from(metadata_source),
        })

    entries.sort(key=_tiebreak_key)

    fused = [
        FusedRetrievalResult(rank=i + 1, **entry)
        for i, entry in enumerate(entries[:limit])
    ]
    return fused


__all__ = [
    "DEFAULT_RRF_K", "DEFAULT_LIMIT", "PROVENANCE_FIELDS", "FusionError",
    "FusedRetrievalResult", "rrf_fuse",
]
