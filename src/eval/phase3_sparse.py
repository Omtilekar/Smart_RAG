"""Task 3.4 - pure logic for the LanceDB-native BM25/FTS sparse baseline:
config-hash wrapper, dense-vs-sparse hit complementarity, first-hit-rank
comparison, and the sparse ablation-table row. No I/O, no LanceDB, no
model loading, no network, and - like every other Phase 3 pure-logic
module - no dependency on `src.eval.test_access` anywhere in this module.

Reuses `src.eval.phase3_baseline`/`src.eval.phase3_ablation` for scope
assertions (`assert_dev_split`, `assert_frozen_scope`), the ablation-table
freeze/upsert mechanism, and the paired bootstrap
(`paired_bootstrap_delta_ci`) - none of that is reimplemented here. This
module only answers three questions specific to Task 3.4:

    1. What is the frozen sparse-contract config hash (`compute_sparse_config_hash`)?
    2. For one question, is a dense/sparse hit "both" / "dense_only" /
       "sparse_only" / "neither" (`classify_hit_complementarity`), and in
       aggregate over the frozen scope (`complementarity_table`)?
    3. Given per-question `per_question` dicts already carrying rank10 (the
       Task 3.1-3.3 `per_question` schema - never reshaped here), what is
       the frozen ablation-table row for this sparse baseline
       (`build_sparse_ablation_row`)?
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3

SPARSE_TASK = "3.4"
SPARSE_BACKEND = "lancedb_native_fts"

# Single source of truth lives on `src.eval.phase3_baseline` (which owns
# `ABLATION_TABLE_COLUMNS` itself) - re-exported here under this module's
# own name only for callers that only import `src.eval.phase3_sparse`.
SPARSE_ABLATION_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_SPARSE_EXTRA_COLUMNS


class Phase3SparseError(ValueError):
    """Raised for a malformed complementarity input or an ablation-row
    build that is missing required upstream fields - never silently
    worked around."""


# --------------------------------------------------------------- config hash

def compute_sparse_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` over the frozen Task 3.4
    sparse contract dict - never a second, independent hashing
    implementation."""
    return semantic_hash(config)


# --------------------------------------------------------------- complementarity

_COMPLEMENTARITY_CLASSES: tuple[str, ...] = ("both", "dense_only", "sparse_only", "neither")


def classify_hit_complementarity(dense_hit: bool, sparse_hit: bool) -> str:
    if dense_hit and sparse_hit:
        return "both"
    if dense_hit and not sparse_hit:
        return "dense_only"
    if sparse_hit and not dense_hit:
        return "sparse_only"
    return "neither"


def complementarity_table(dense_per_question: Mapping[str, Mapping], sparse_per_question: Mapping[str, Mapping],
                           question_ids: Sequence[str], *, hit_field: str) -> dict:
    """Aggregate dense-vs-sparse complementarity over the frozen scope for
    one hit field (`"hit10"` or `"hit50"`). Raises if a question_id is
    missing from either per_question mapping - never silently skips a
    question."""
    counts = {c: 0 for c in _COMPLEMENTARITY_CLASSES}
    dense_only_ids: list[str] = []
    sparse_only_ids: list[str] = []
    for qid in question_ids:
        if qid not in dense_per_question or qid not in sparse_per_question:
            raise Phase3SparseError(f"question_id {qid!r} missing from dense/sparse per_question mapping")
        dense_hit = bool(dense_per_question[qid][hit_field])
        sparse_hit = bool(sparse_per_question[qid][hit_field])
        cls = classify_hit_complementarity(dense_hit, sparse_hit)
        counts[cls] += 1
        if cls == "dense_only":
            dense_only_ids.append(qid)
        elif cls == "sparse_only":
            sparse_only_ids.append(qid)
    return {
        **counts,
        "dense_only_question_ids": dense_only_ids,
        "sparse_only_question_ids": sparse_only_ids,
    }


# --------------------------------------------------------------- first-hit-rank comparison

def first_hit_rank_comparison(dense_rank: int | None, sparse_rank: int | None) -> str:
    """`dense_rank`/`sparse_rank` are the first gold-document hit rank
    (1-based, `None` if no hit within the compared window) - a lower rank
    is better. A hit beats a miss; equal ranks (including both-miss) are
    `"same"`."""
    if dense_rank is None and sparse_rank is None:
        return "same"
    if dense_rank is None:
        return "sparse_better"
    if sparse_rank is None:
        return "dense_better"
    if sparse_rank < dense_rank:
        return "sparse_better"
    if dense_rank < sparse_rank:
        return "dense_better"
    return "same"


def first_hit_rank_comparison_counts(dense_per_question: Mapping[str, Mapping], sparse_per_question: Mapping[str, Mapping],
                                      question_ids: Sequence[str], *, rank_field: str = "rank10") -> dict:
    counts = {"sparse_better": 0, "dense_better": 0, "same": 0}
    for qid in question_ids:
        if qid not in dense_per_question or qid not in sparse_per_question:
            raise Phase3SparseError(f"question_id {qid!r} missing from dense/sparse per_question mapping")
        cls = first_hit_rank_comparison(dense_per_question[qid][rank_field], sparse_per_question[qid][rank_field])
        counts[cls] += 1
    return counts


# --------------------------------------------------------------- ablation row

def build_sparse_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    question_count: int, corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str,
    sparse_index_identity_hash_value: str, candidate_k: int, metrics: Mapping, deltas: Mapping,
    complementarity10: Mapping, complementarity50: Mapping, lancedb_version: str, fts_indexed_column: str,
    fts_build_seconds: float, fts_index_size_bytes: int, retrieval_latency_p50_ms: float,
    retrieval_latency_p95_ms: float, notes: str,
) -> dict:
    """The Task 3.4 ablation-table row. `dense_used_in_this_row` is always
    `False` - the frozen Task 3.3 Qwen identity is recorded for provenance
    only, never used to compute a sparse score."""
    return {
        "row_id": row_id, "configuration": "sparse_lancedb_fts_baseline",
        "status": "phase3_4_bm25_fts_baseline", "run_id": run_id, "git_sha": git_sha,
        "phase3_config_hash": config_hash, "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": eval_scope_sha256, "question_count": question_count,
        "corpus_document_count": corpus_document_count, "chunk_count": chunk_count,
        "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": sparse_index_identity_hash_value,
        "retrieval": SPARSE_BACKEND, "candidate_k": candidate_k,
        "doc_recall_at_10": metrics["doc_recall_at_10"], "doc_recall_at_50": metrics["doc_recall_at_50"],
        "doc_mrr": metrics["doc_mrr"], "doc_ndcg_at_10": metrics["doc_ndcg_at_10"],
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": retrieval_latency_p50_ms, "retrieval_latency_p95_ms": retrieval_latency_p95_ms,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": retrieval_latency_p50_ms,
        "index_size_bytes": fts_index_size_bytes,
        "retrieval_mode": "sparse_only", "sparse_backend": SPARSE_BACKEND, "lancedb_version": lancedb_version,
        "fts_indexed_column": fts_indexed_column, "dense_used_in_this_row": False,
        "delta_vs_qwen_dense_recall10": deltas["recall10"], "delta_vs_qwen_dense_recall50": deltas["recall50"],
        "delta_vs_qwen_dense_mrr": deltas["mrr"], "delta_vs_qwen_dense_ndcg10": deltas["ndcg10"],
        "dense_only_hits_at_10": complementarity10["dense_only"], "sparse_only_hits_at_10": complementarity10["sparse_only"],
        "dense_only_hits_at_50": complementarity50["dense_only"], "sparse_only_hits_at_50": complementarity50["sparse_only"],
        "fts_build_seconds": fts_build_seconds, "fts_index_size_bytes": fts_index_size_bytes,
        "fts_search_latency_p50_ms": retrieval_latency_p50_ms, "fts_search_latency_p95_ms": retrieval_latency_p95_ms,
        "notes": notes,
    }


__all__ = [
    "SPARSE_TASK", "SPARSE_BACKEND", "SPARSE_ABLATION_EXTRA_COLUMNS", "Phase3SparseError",
    "compute_sparse_config_hash",
    "classify_hit_complementarity", "complementarity_table",
    "first_hit_rank_comparison", "first_hit_rank_comparison_counts",
    "build_sparse_ablation_row",
]
