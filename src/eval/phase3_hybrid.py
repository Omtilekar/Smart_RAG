"""Task 3.5 - pure logic for RRF hybrid fusion evaluation: config-hash
wrapper, hybrid-vs-dense/hybrid-vs-sparse gain/loss classification,
first-gold-hit-rank movement, fusion-source composition, the frozen
selection rule, and the hybrid ablation-table row. No I/O, no LanceDB,
no model loading, no network, and - like every other Phase 3 pure-logic
module - no dependency on `src.eval.test_access` anywhere in this module.

Reuses `src.eval.phase3_baseline`/`src.eval.phase3_ablation` for scope
assertions and the ablation-table freeze/upsert mechanism, and
`src.eval.phase3_ablation.paired_bootstrap_delta_ci` for uncertainty -
none of that is reimplemented here. Task 3.5's practical-tie rule is
deliberately NOT `src.eval.phase3_ablation.is_practical_tie()`: that
function is frozen around a Recall@50 hit delta, which is structurally
uninformative here (Task 3.3's dense parent already sits at the 89/89
ceiling, so Gate 1 requires hybrid to match it exactly before Gate 2 is
even evaluated) - Stage 9 of the Task 3.5 roadmap explicitly defines a
DIFFERENT practical-tie test keyed on the Recall@10 hit delta instead,
so a new, correctly-scoped function is defined here rather than
silently reusing a rule built for a different quantity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3

SPARSE_TASK = "3.5"
FUSION_METHOD = "rrf"

# Single source of truth lives on `src.eval.phase3_baseline` (which owns
# `ABLATION_TABLE_COLUMNS` itself) - re-exported here under this module's
# own name only for callers that only import `src.eval.phase3_hybrid`.
ABLATION_TABLE_HYBRID_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_HYBRID_EXTRA_COLUMNS


class Phase3HybridError(ValueError):
    """Raised for a malformed gain/loss/composition input or an
    ablation-row build missing required upstream fields - never
    silently worked around."""


# --------------------------------------------------------------- config hash

def compute_hybrid_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` over the frozen Task 3.5
    RRF contract dict - never a second, independent hashing
    implementation."""
    return semantic_hash(config)


# --------------------------------------------------------------- gain/loss (2-way, one comparison arm)

def classify_gain_loss(before_hit: bool, after_hit: bool) -> str:
    if not before_hit and after_hit:
        return "gained"
    if before_hit and not after_hit:
        return "lost"
    return "unchanged"


def gain_loss_counts(before_per_question: Mapping[str, Mapping], after_per_question: Mapping[str, Mapping],
                      question_ids: Sequence[str], *, hit_field: str) -> dict:
    counts = {"gained": 0, "lost": 0, "unchanged": 0}
    for qid in question_ids:
        if qid not in before_per_question or qid not in after_per_question:
            raise Phase3HybridError(f"question_id {qid!r} missing from before/after per_question mapping")
        cls = classify_gain_loss(bool(before_per_question[qid][hit_field]), bool(after_per_question[qid][hit_field]))
        counts[cls] += 1
    return counts


# --------------------------------------------------------------- first-gold-hit-rank movement

def rank_movement(before_rank: int | None, after_rank: int | None) -> str:
    """`before_rank`/`after_rank` are the first gold-document hit rank
    (1-based, `None` if no hit) - a LOWER rank is better. A miss-to-hit
    move is `"improved"`, a hit-to-miss move is `"worsened"`; equal
    ranks (including both-miss) are `"unchanged"`."""
    if before_rank is None and after_rank is None:
        return "unchanged"
    if before_rank is None:
        return "improved"
    if after_rank is None:
        return "worsened"
    if after_rank < before_rank:
        return "improved"
    if after_rank > before_rank:
        return "worsened"
    return "unchanged"


def rank_movement_counts(before_per_question: Mapping[str, Mapping], after_per_question: Mapping[str, Mapping],
                          question_ids: Sequence[str], *, rank_field: str = "rank10") -> dict:
    counts = {"improved": 0, "worsened": 0, "unchanged": 0}
    for qid in question_ids:
        if qid not in before_per_question or qid not in after_per_question:
            raise Phase3HybridError(f"question_id {qid!r} missing from before/after per_question mapping")
        cls = rank_movement(before_per_question[qid][rank_field], after_per_question[qid][rank_field])
        counts[cls] += 1
    return counts


# --------------------------------------------------------------- fusion-source composition

def fusion_composition_counts(entries: Sequence[Mapping]) -> dict:
    """`entries` is a flat sequence of `{"in_dense": bool, "in_sparse": bool}`
    mappings (typically every fused chunk in the top-10 or top-50 window,
    across every question) - counts how many final candidates came from
    both parents, dense only, or sparse only. Direct evidence of whether
    hybrid actually uses sparse evidence or merely reproduces dense order."""
    counts = {"both": 0, "dense_only": 0, "sparse_only": 0}
    for e in entries:
        in_dense, in_sparse = bool(e["in_dense"]), bool(e["in_sparse"])
        if in_dense and in_sparse:
            counts["both"] += 1
        elif in_dense:
            counts["dense_only"] += 1
        elif in_sparse:
            counts["sparse_only"] += 1
        else:
            raise Phase3HybridError("fused entry has neither in_dense nor in_sparse set")
    return counts


# --------------------------------------------------------------- selection rule (Stage 9)

def is_practical_tie_hybrid(*, recall10_hit_delta: int, mrr_ci: tuple[float, float], ndcg_ci: tuple[float, float]) -> bool:
    """Task 3.5's own practical-tie rule (Stage 9): hybrid and dense are
    practically tied iff Recall@10 differs by at most 1 question out of
    89 AND both the paired MRR delta's and paired nDCG@10 delta's 95%
    bootstrap intervals include 0. Deliberately distinct from
    `phase3_ablation.is_practical_tie()` (see module docstring)."""
    return (
        abs(recall10_hit_delta) <= 1
        and mrr_ci[0] <= 0.0 <= mrr_ci[1]
        and ndcg_ci[0] <= 0.0 <= ndcg_ci[1]
    )


@dataclass(frozen=True)
class HybridSelectionResult:
    selected: str | None  # "hybrid" | "dense_only" | None (flagged)
    eligible: bool
    flagged_for_user_decision: bool
    flag_reason: str | None
    rationale: str

    def to_dict(self) -> dict:
        return {
            "selected": self.selected, "eligible": self.eligible,
            "flagged_for_user_decision": self.flagged_for_user_decision,
            "flag_reason": self.flag_reason, "rationale": self.rationale,
        }


def select_hybrid_configuration(
    *, hybrid_metrics: Mapping, dense_metrics: Mapping, question_count: int,
    recall10_hit_delta: int, mrr_ci: tuple[float, float], ndcg_ci: tuple[float, float],
) -> HybridSelectionResult:
    """Applies the frozen Stage 9 decision rule. Gate 1 (candidate-recall
    preservation) is checked first and is absolute - hybrid is never
    selected if it drops below dense's `doc_recall@50` ceiling, no
    matter how good its ranking metrics look. Gate 2 only compares
    doc_mrr/doc_ndcg@10/doc_recall@10 (Recall@50 is already at ceiling
    for both and cannot distinguish an improvement)."""
    if hybrid_metrics["doc_recall_at_50_hits"] != question_count:
        return HybridSelectionResult(
            selected="dense_only", eligible=False, flagged_for_user_decision=False, flag_reason=None,
            rationale=(
                f"Gate 1 failed: hybrid doc_recall@50={hybrid_metrics['doc_recall_at_50_hits']}/{question_count} "
                f"does not preserve dense's {question_count}/{question_count} ceiling - hybrid is not eligible."
            ),
        )

    if is_practical_tie_hybrid(recall10_hit_delta=recall10_hit_delta, mrr_ci=mrr_ci, ndcg_ci=ndcg_ci):
        return HybridSelectionResult(
            selected="dense_only", eligible=True, flagged_for_user_decision=False, flag_reason=None,
            rationale=(
                f"hybrid is practically tied with dense (Recall@10 hit delta={recall10_hit_delta}, "
                f"MRR/nDCG@10 95% CIs include 0) - dense-only preferred: simpler, avoids a second "
                f"retrieval path at query time. Hybrid did not earn its extra complexity."
            ),
        )

    hybrid_better_mrr = hybrid_metrics["doc_mrr"] > dense_metrics["doc_mrr"]
    hybrid_better_ndcg = hybrid_metrics["doc_ndcg_at_10"] > dense_metrics["doc_ndcg_at_10"]
    hybrid_better_recall10 = hybrid_metrics["doc_recall_at_10"] > dense_metrics["doc_recall_at_10"]
    credible_mrr_regression = mrr_ci[1] < 0.0
    credible_ndcg_regression = ndcg_ci[1] < 0.0

    if hybrid_better_mrr and credible_ndcg_regression:
        return HybridSelectionResult(
            selected=None, eligible=True, flagged_for_user_decision=True,
            flag_reason=(
                "hybrid improves doc_mrr over dense but shows a credible doc_ndcg@10 regression "
                "(95% CI entirely below 0) - this trade-off requires a user decision, not an automatic pick."
            ),
            rationale="",
        )
    if hybrid_better_ndcg and not hybrid_better_mrr and credible_mrr_regression:
        return HybridSelectionResult(
            selected=None, eligible=True, flagged_for_user_decision=True,
            flag_reason=(
                "hybrid improves doc_ndcg@10 over dense but shows a credible doc_mrr regression "
                "(95% CI entirely below 0) - this trade-off requires a user decision, not an automatic pick."
            ),
            rationale="",
        )

    if hybrid_better_mrr or hybrid_better_ndcg or hybrid_better_recall10:
        return HybridSelectionResult(
            selected="hybrid", eligible=True, flagged_for_user_decision=False, flag_reason=None,
            rationale=(
                "hybrid is a credible ranking improvement over dense on the frozen priority order "
                "(doc_mrr > doc_ndcg@10 > doc_recall@10) with no regression-protection violation."
            ),
        )

    return HybridSelectionResult(
        selected="dense_only", eligible=True, flagged_for_user_decision=False, flag_reason=None,
        rationale="hybrid does not improve any ranking metric over dense on the frozen priority order.",
    )


# --------------------------------------------------------------- ablation row

def build_hybrid_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    question_count: int, corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    sparse_index_identity_hash_value: str, rrf_k: int, dense_candidate_k: int, sparse_candidate_k: int,
    final_candidate_k: int, metrics: Mapping, deltas_vs_dense: Mapping, deltas_vs_sparse: Mapping,
    hit_gain_loss_10: Mapping, hit_gain_loss_50: Mapping, composition_top10: Mapping, composition_top50: Mapping,
    dense_latency_p50_ms: float, sparse_latency_p50_ms: float, fusion_latency_p50_ms: float,
    hybrid_latency_p50_ms: float, hybrid_latency_p95_ms: float, selected: str | None, notes: str,
) -> dict:
    """The Task 3.5 ablation-table row. `dense_used_in_this_row=True` -
    unlike Task 3.4's sparse-only row, hybrid genuinely uses dense scores
    (via RRF rank fusion, never raw-score combination)."""
    return {
        "row_id": row_id, "configuration": "rrf_hybrid_fusion", "status": "phase3_5_rrf_hybrid_fusion",
        "run_id": run_id, "git_sha": git_sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": question_count, "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": FUSION_METHOD, "candidate_k": final_candidate_k,
        "doc_recall_at_10": metrics["doc_recall_at_10"], "doc_recall_at_50": metrics["doc_recall_at_50"],
        "doc_mrr": metrics["doc_mrr"], "doc_ndcg_at_10": metrics["doc_ndcg_at_10"],
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": hybrid_latency_p50_ms, "retrieval_latency_p95_ms": hybrid_latency_p95_ms,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA,
        "index_size_bytes": p3.NA,
        "retrieval_mode": "hybrid", "sparse_backend": "lancedb_native_fts", "lancedb_version": p3.NA,
        "fts_indexed_column": "text", "dense_used_in_this_row": True,
        "delta_vs_qwen_dense_recall10": deltas_vs_dense["recall10"], "delta_vs_qwen_dense_recall50": deltas_vs_dense["recall50"],
        "delta_vs_qwen_dense_mrr": deltas_vs_dense["mrr"], "delta_vs_qwen_dense_ndcg10": deltas_vs_dense["ndcg10"],
        "dense_only_hits_at_10": p3.NA, "sparse_only_hits_at_10": p3.NA,
        "dense_only_hits_at_50": p3.NA, "sparse_only_hits_at_50": p3.NA,
        "fts_build_seconds": p3.NA, "fts_index_size_bytes": p3.NA,
        "fts_search_latency_p50_ms": sparse_latency_p50_ms, "fts_search_latency_p95_ms": p3.NA,
        "fusion_method": FUSION_METHOD, "rrf_k": rrf_k, "dense_candidate_k": dense_candidate_k,
        "sparse_candidate_k": sparse_candidate_k, "final_candidate_k": final_candidate_k,
        "sparse_index_identity": sparse_index_identity_hash_value,
        "delta_vs_sparse_recall10": deltas_vs_sparse["recall10"], "delta_vs_sparse_recall50": deltas_vs_sparse["recall50"],
        "delta_vs_sparse_mrr": deltas_vs_sparse["mrr"], "delta_vs_sparse_ndcg10": deltas_vs_sparse["ndcg10"],
        "hit10_gained_vs_dense": hit_gain_loss_10["gained"], "hit10_lost_vs_dense": hit_gain_loss_10["lost"],
        "hit50_gained_vs_dense": hit_gain_loss_50["gained"], "hit50_lost_vs_dense": hit_gain_loss_50["lost"],
        "hybrid_both_parent_top10": composition_top10["both"], "hybrid_dense_only_top10": composition_top10["dense_only"],
        "hybrid_sparse_only_top10": composition_top10["sparse_only"],
        "hybrid_both_parent_top50": composition_top50["both"], "hybrid_dense_only_top50": composition_top50["dense_only"],
        "hybrid_sparse_only_top50": composition_top50["sparse_only"],
        "dense_latency_p50_ms": dense_latency_p50_ms, "sparse_latency_p50_ms": sparse_latency_p50_ms,
        "fusion_latency_p50_ms": fusion_latency_p50_ms, "selected": selected, "notes": notes,
    }


__all__ = [
    "SPARSE_TASK", "FUSION_METHOD", "ABLATION_TABLE_HYBRID_EXTRA_COLUMNS", "Phase3HybridError",
    "compute_hybrid_config_hash",
    "classify_gain_loss", "gain_loss_counts",
    "rank_movement", "rank_movement_counts",
    "fusion_composition_counts",
    "is_practical_tie_hybrid", "HybridSelectionResult", "select_hybrid_configuration",
    "build_hybrid_ablation_row",
]
