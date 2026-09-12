"""Task 3.9 - pure logic for metadata-pre-filtering evaluation:
config-hash wrapper and the filtering ablation-table row. No I/O, no
model, no network.

Selection reuses `src.eval.phase3_ablation.select_round_winner` /
`is_practical_tie` / `paired_bootstrap_delta_ci` UNMODIFIED - unlike
Tasks 3.5/3.6 (whose candidate-set-recall was structurally locked and
made the Recall@50-keyed practical-tie rule meaningless), Task 3.9's
baseline and filtered arms search the SAME embeddings/index and can
have genuinely different Recall@50 (a narrower, correctly-filtered pool
can raise it; a wrongly-filtered pool can lower it) - the original
Task 3.2/3.3 rule applies exactly as designed. Only the tie-break is
new (`filtered_tiebreak_key`): prefer the simpler unfiltered baseline on
a practical tie, since a metadata filter's benefit depends on the
router's extraction accuracy holding at query time - the same
"simpler wins ties" principle Tasks 3.5/3.6 already established.
"""

from __future__ import annotations

from typing import Mapping

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3

FILTER_TASK = "3.9"

# Single source of truth lives on `src.eval.phase3_baseline`.
ABLATION_TABLE_FILTER_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_FILTER_EXTRA_COLUMNS


def compute_filter_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` - never a second,
    independent hashing implementation."""
    return semantic_hash(config)


def filtered_tiebreak_key(candidate: Mapping) -> tuple:
    """`0` for the unfiltered baseline, `1` for the filtered candidate -
    ascending sort puts baseline first, so `apply_tiebreak()` picks it
    on a practical tie (simpler, no dependency on router extraction
    accuracy at query time)."""
    return (0 if candidate["row_id"] == "baseline" else 1,)


def build_filter_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    question_count: int, corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    candidate_k: int, metrics: Mapping, deltas: Mapping, filtered_question_count: int,
    fallback_question_count: int, retrieval_latency_p50_ms: float, retrieval_latency_p95_ms: float,
    selected: str | None, notes: str,
) -> dict:
    return {
        "row_id": row_id, "configuration": "metadata_prefiltered_dense", "status": "phase3_9_metadata_prefiltering",
        "run_id": run_id, "git_sha": git_sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": question_count, "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "dense_exact_cosine_prefiltered", "candidate_k": candidate_k,
        "doc_recall_at_10": metrics["doc_recall_at_10"], "doc_recall_at_50": metrics["doc_recall_at_50"],
        "doc_mrr": metrics["doc_mrr"], "doc_ndcg_at_10": metrics["doc_ndcg_at_10"],
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": retrieval_latency_p50_ms, "retrieval_latency_p95_ms": retrieval_latency_p95_ms,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA, "index_size_bytes": p3.NA,
        "retrieval_mode": "dense_only", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
        "fts_indexed_column": p3.NA, "dense_used_in_this_row": True,
        "delta_vs_qwen_dense_recall10": deltas["recall10"], "delta_vs_qwen_dense_recall50": deltas["recall50"],
        "delta_vs_qwen_dense_mrr": deltas["mrr"], "delta_vs_qwen_dense_ndcg10": deltas["ndcg10"],
        "dense_only_hits_at_10": p3.NA, "sparse_only_hits_at_10": p3.NA,
        "dense_only_hits_at_50": p3.NA, "sparse_only_hits_at_50": p3.NA,
        "fts_build_seconds": p3.NA, "fts_index_size_bytes": p3.NA,
        "fts_search_latency_p50_ms": p3.NA, "fts_search_latency_p95_ms": p3.NA,
        "fusion_method": p3.NA, "rrf_k": p3.NA, "dense_candidate_k": candidate_k, "sparse_candidate_k": p3.NA,
        "final_candidate_k": candidate_k, "sparse_index_identity": p3.NA,
        "delta_vs_sparse_recall10": p3.NA, "delta_vs_sparse_recall50": p3.NA,
        "delta_vs_sparse_mrr": p3.NA, "delta_vs_sparse_ndcg10": p3.NA,
        "hit10_gained_vs_dense": p3.NA, "hit10_lost_vs_dense": p3.NA,
        "hit50_gained_vs_dense": p3.NA, "hit50_lost_vs_dense": p3.NA,
        "hybrid_both_parent_top10": p3.NA, "hybrid_dense_only_top10": p3.NA, "hybrid_sparse_only_top10": p3.NA,
        "hybrid_both_parent_top50": p3.NA, "hybrid_dense_only_top50": p3.NA, "hybrid_sparse_only_top50": p3.NA,
        "dense_latency_p50_ms": p3.NA, "sparse_latency_p50_ms": p3.NA, "fusion_latency_p50_ms": p3.NA,
        "selected": selected, "reranker_model": p3.NA, "reranker_revision": p3.NA, "reranker_identity": p3.NA,
        "rerank_base_k": p3.NA, "doc_recall_at_5": p3.NA, "doc_recall_at_5_hits": p3.NA,
        "delta_vs_no_rerank_mrr": p3.NA, "delta_vs_no_rerank_ndcg10": p3.NA,
        "delta_vs_no_rerank_precision5": p3.NA, "delta_vs_no_rerank_recall5": p3.NA,
        "hit5_gained_vs_no_rerank": p3.NA, "hit5_lost_vs_no_rerank": p3.NA,
        "reranker_latency_p50_ms": p3.NA, "reranker_latency_p95_ms": p3.NA,
        "crag_feature": p3.NA, "crag_threshold": p3.NA, "crag_calibration_method": p3.NA,
        "should_answer_count": p3.NA, "should_refuse_count": p3.NA,
        "true_refusal_rate": p3.NA, "false_refusal_rate": p3.NA, "missed_failure_rate": p3.NA, "crag_youden_j": p3.NA,
        "gazetteer_size": p3.NA, "concept_registry_size": p3.NA, "router_accuracy": p3.NA, "router_macro_f1": p3.NA,
        "filtered_question_count": filtered_question_count, "fallback_question_count": fallback_question_count,
        "notes": notes,
    }


__all__ = [
    "FILTER_TASK", "ABLATION_TABLE_FILTER_EXTRA_COLUMNS", "compute_filter_config_hash",
    "filtered_tiebreak_key", "build_filter_ablation_row",
]
