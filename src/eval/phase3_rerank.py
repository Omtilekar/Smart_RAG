"""Task 3.6 - pure logic for cross-encoder reranking evaluation:
config-hash wrapper, the frozen selection rule, and the reranking
ablation-table row. No I/O, no model loading, no network, and - like
every other Phase 3 pure-logic module - no dependency on
`src.eval.test_access` anywhere in this module.

Reuses `src.eval.phase3_baseline`/`src.eval.phase3_ablation` for scope
assertions and the ablation-table freeze/upsert mechanism,
`src.eval.phase3_ablation.paired_bootstrap_delta_ci` for uncertainty,
and `src.eval.phase3_hybrid.classify_gain_loss`/`gain_loss_counts`
(fully generic before/after hit-flag comparisons, not actually hybrid-
specific) - none of that is reimplemented here.

Reranking never changes the candidate SET, only its order - Task 3.6's
`doc_recall@50` is therefore mathematically identical before and after
reranking and cannot serve as a Gate-1-style eligibility guard the way
it did for Task 3.5's hybrid fusion (a different candidate set). This
module's `is_practical_tie_rerank()` is accordingly keyed on the
Recall@5 hit delta (the primary depth this task's Precision@5/Recall@5
metrics operate at), never on Recall@50.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3

RERANK_TASK = "3.6"

# Single source of truth lives on `src.eval.phase3_baseline` (which owns
# `ABLATION_TABLE_COLUMNS` itself) - re-exported here under this module's
# own name only for callers that only import `src.eval.phase3_rerank`.
ABLATION_TABLE_RERANK_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_RERANK_EXTRA_COLUMNS


class Phase3RerankError(ValueError):
    """Raised for a malformed rerank-ablation-row build or an internal
    consistency violation (e.g. reranking changed the candidate-set
    Recall@50, which should be mathematically impossible) - never
    silently worked around."""


# --------------------------------------------------------------- config hash

def compute_rerank_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` over the frozen Task 3.6
    reranker contract dict - never a second, independent hashing
    implementation."""
    return semantic_hash(config)


# --------------------------------------------------------------- candidate-set recall integrity

def assert_candidate_set_recall_unchanged(reranked_recall_at_50: float, base_recall_at_50: float) -> None:
    """Reranking reorders a fixed candidate pool - it can never change
    which chunks are IN that pool, so doc_recall@50 computed over the
    reranked list must equal the base (pre-rerank) value exactly. A
    mismatch means the reranked list was built over a different/smaller
    candidate set than the base retriever produced - a real bug, not a
    fusion effect."""
    if abs(reranked_recall_at_50 - base_recall_at_50) > 1e-12:
        raise Phase3RerankError(
            f"reranked doc_recall@50={reranked_recall_at_50} != base doc_recall@50={base_recall_at_50} - "
            f"reranking must never change the candidate set, only its order."
        )


# --------------------------------------------------------------- selection rule

def is_practical_tie_rerank(*, recall5_hit_delta: int, mrr_ci: tuple[float, float], ndcg_ci: tuple[float, float]) -> bool:
    """Task 3.6's own practical-tie rule: reranked and no-rerank are
    practically tied iff Recall@5 differs by at most 1 question out of
    89 AND both the paired MRR delta's and paired nDCG@10 delta's 95%
    bootstrap intervals include 0. Deliberately distinct from
    `phase3_ablation.is_practical_tie()` (Recall@50-keyed, not
    applicable here) and from `phase3_hybrid.is_practical_tie_hybrid()`
    (Recall@10-keyed, a different depth than this task's primary
    Precision@5/Recall@5 metrics)."""
    return (
        abs(recall5_hit_delta) <= 1
        and mrr_ci[0] <= 0.0 <= mrr_ci[1]
        and ndcg_ci[0] <= 0.0 <= ndcg_ci[1]
    )


@dataclass(frozen=True)
class RerankSelectionResult:
    selected: str | None  # "reranked" | "no_rerank" | None (flagged)
    flagged_for_user_decision: bool
    flag_reason: str | None
    rationale: str

    def to_dict(self) -> dict:
        return {
            "selected": self.selected, "flagged_for_user_decision": self.flagged_for_user_decision,
            "flag_reason": self.flag_reason, "rationale": self.rationale,
        }


def select_rerank_configuration(
    *, reranked_metrics: Mapping, base_metrics: Mapping,
    recall5_hit_delta: int, mrr_ci: tuple[float, float], ndcg_ci: tuple[float, float],
) -> RerankSelectionResult:
    """Priority order: doc_mrr > doc_ndcg@10 > doc_precision_at_5 >
    doc_recall_at_5 (mirrors Task 3.2/3.3's own MRR-first priority
    convention). Practical tie prefers `no_rerank` (simpler, avoids the
    reranker's extra query-time latency/model). A win on one metric with
    a credible (95% CI entirely below 0) regression on MRR or nDCG@10 is
    flagged for a user decision, never auto-resolved - mirrors Task
    3.5's regression-protection pattern."""
    if is_practical_tie_rerank(recall5_hit_delta=recall5_hit_delta, mrr_ci=mrr_ci, ndcg_ci=ndcg_ci):
        return RerankSelectionResult(
            selected="no_rerank", flagged_for_user_decision=False, flag_reason=None,
            rationale=(
                f"reranked is practically tied with no-rerank (Recall@5 hit delta={recall5_hit_delta}, "
                f"MRR/nDCG@10 95% CIs include 0) - no_rerank preferred: simpler, avoids the reranker's "
                f"extra query-time model call. Reranking did not earn its extra complexity."
            ),
        )

    reranked_better_mrr = reranked_metrics["doc_mrr"] > base_metrics["doc_mrr"]
    reranked_better_ndcg = reranked_metrics["doc_ndcg_at_10"] > base_metrics["doc_ndcg_at_10"]
    reranked_better_precision5 = reranked_metrics["doc_precision_at_5"] > base_metrics["doc_precision_at_5"]
    reranked_better_recall5 = reranked_metrics["doc_recall_at_5"] > base_metrics["doc_recall_at_5"]
    credible_mrr_regression = mrr_ci[1] < 0.0
    credible_ndcg_regression = ndcg_ci[1] < 0.0

    if reranked_better_mrr and credible_ndcg_regression:
        return RerankSelectionResult(
            selected=None, flagged_for_user_decision=True,
            flag_reason=(
                "reranking improves doc_mrr over no-rerank but shows a credible doc_ndcg@10 regression "
                "(95% CI entirely below 0) - this trade-off requires a user decision, not an automatic pick."
            ),
            rationale="",
        )
    if reranked_better_ndcg and not reranked_better_mrr and credible_mrr_regression:
        return RerankSelectionResult(
            selected=None, flagged_for_user_decision=True,
            flag_reason=(
                "reranking improves doc_ndcg@10 over no-rerank but shows a credible doc_mrr regression "
                "(95% CI entirely below 0) - this trade-off requires a user decision, not an automatic pick."
            ),
            rationale="",
        )

    if reranked_better_mrr or reranked_better_ndcg or reranked_better_precision5 or reranked_better_recall5:
        return RerankSelectionResult(
            selected="reranked", flagged_for_user_decision=False, flag_reason=None,
            rationale=(
                "reranked is a credible ranking improvement over no-rerank on the frozen priority order "
                "(doc_mrr > doc_ndcg@10 > doc_precision@5 > doc_recall@5) with no regression-protection violation."
            ),
        )

    return RerankSelectionResult(
        selected="no_rerank", flagged_for_user_decision=False, flag_reason=None,
        rationale="reranking does not improve any ranking metric over no-rerank on the frozen priority order.",
    )


# --------------------------------------------------------------- ablation row

def build_rerank_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    question_count: int, corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    reranker_repository: str, reranker_revision: str, reranker_identity_hash: str, rerank_base_k: int,
    metrics: Mapping, deltas: Mapping, hit_gain_loss_5: Mapping, reranker_latency_p50_ms: float,
    reranker_latency_p95_ms: float, retrieval_latency_p50_ms: float, retrieval_latency_p95_ms: float,
    selected: str | None, notes: str,
) -> dict:
    """The Task 3.6 ablation-table row. `dense_used_in_this_row=True` -
    reranking operates over the dense candidate pool."""
    return {
        "row_id": row_id, "configuration": "cross_encoder_reranking", "status": "phase3_6_cross_encoder_reranking",
        "run_id": run_id, "git_sha": git_sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": question_count, "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "cross_encoder_rerank", "candidate_k": rerank_base_k,
        "doc_recall_at_10": metrics["doc_recall_at_10"], "doc_recall_at_50": metrics["doc_recall_at_50"],
        "doc_mrr": metrics["doc_mrr"], "doc_ndcg_at_10": metrics["doc_ndcg_at_10"],
        "precision_at_5": metrics["doc_precision_at_5"], "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": retrieval_latency_p50_ms, "retrieval_latency_p95_ms": retrieval_latency_p95_ms,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA,
        "index_size_bytes": p3.NA,
        "retrieval_mode": "dense_only", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
        "fts_indexed_column": p3.NA, "dense_used_in_this_row": True,
        "delta_vs_qwen_dense_recall10": deltas["recall10"], "delta_vs_qwen_dense_recall50": deltas["recall50"],
        "delta_vs_qwen_dense_mrr": deltas["mrr"], "delta_vs_qwen_dense_ndcg10": deltas["ndcg10"],
        "dense_only_hits_at_10": p3.NA, "sparse_only_hits_at_10": p3.NA,
        "dense_only_hits_at_50": p3.NA, "sparse_only_hits_at_50": p3.NA,
        "fts_build_seconds": p3.NA, "fts_index_size_bytes": p3.NA,
        "fts_search_latency_p50_ms": p3.NA, "fts_search_latency_p95_ms": p3.NA,
        "fusion_method": p3.NA, "rrf_k": p3.NA, "dense_candidate_k": rerank_base_k,
        "sparse_candidate_k": p3.NA, "final_candidate_k": rerank_base_k, "sparse_index_identity": p3.NA,
        "delta_vs_sparse_recall10": p3.NA, "delta_vs_sparse_recall50": p3.NA,
        "delta_vs_sparse_mrr": p3.NA, "delta_vs_sparse_ndcg10": p3.NA,
        "hit10_gained_vs_dense": p3.NA, "hit10_lost_vs_dense": p3.NA,
        "hit50_gained_vs_dense": p3.NA, "hit50_lost_vs_dense": p3.NA,
        "hybrid_both_parent_top10": p3.NA, "hybrid_dense_only_top10": p3.NA, "hybrid_sparse_only_top10": p3.NA,
        "hybrid_both_parent_top50": p3.NA, "hybrid_dense_only_top50": p3.NA, "hybrid_sparse_only_top50": p3.NA,
        "dense_latency_p50_ms": p3.NA, "sparse_latency_p50_ms": p3.NA, "fusion_latency_p50_ms": p3.NA,
        "reranker_model": reranker_repository, "reranker_revision": reranker_revision,
        "reranker_identity": reranker_identity_hash, "rerank_base_k": rerank_base_k,
        "doc_recall_at_5": metrics["doc_recall_at_5"], "doc_recall_at_5_hits": metrics["doc_recall_at_5_hits"],
        "delta_vs_no_rerank_mrr": deltas["mrr"], "delta_vs_no_rerank_ndcg10": deltas["ndcg10"],
        "delta_vs_no_rerank_precision5": deltas["precision5"], "delta_vs_no_rerank_recall5": deltas["recall5"],
        "hit5_gained_vs_no_rerank": hit_gain_loss_5["gained"], "hit5_lost_vs_no_rerank": hit_gain_loss_5["lost"],
        "reranker_latency_p50_ms": reranker_latency_p50_ms, "reranker_latency_p95_ms": reranker_latency_p95_ms,
        "selected": selected, "notes": notes,
    }


__all__ = [
    "RERANK_TASK", "ABLATION_TABLE_RERANK_EXTRA_COLUMNS", "Phase3RerankError",
    "compute_rerank_config_hash", "assert_candidate_set_recall_unchanged",
    "is_practical_tie_rerank", "RerankSelectionResult", "select_rerank_configuration",
    "build_rerank_ablation_row",
]
