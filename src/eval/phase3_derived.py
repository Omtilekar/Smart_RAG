"""Task 3.11 - pure logic for deterministic derived-calculation
evaluation: config-hash wrapper, rate aggregation (reusing Task 2.6's
`aggregate_rate` unmodified), and the derived-calculation ablation row.
No I/O, no DuckDB, no model, no network, and - like every other Phase 3
pure-logic module - no dependency on `src.eval.test_access` anywhere in
this module.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3
from src.eval.metrics import aggregate_rate

DERIVED_TASK = "3.11"

# Single source of truth lives on `src.eval.phase3_baseline`.
ABLATION_TABLE_DERIVED_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS


class Phase3DerivedError(ValueError):
    """Raised for a malformed derived-calculation evaluation result -
    never silently worked around."""


def compute_derived_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` - never a second,
    independent hashing implementation."""
    return semantic_hash(config)


def derived_rates(*, attempted_flags: Sequence[bool], computed_flags: Sequence[bool],
                   exact_match_flags: Sequence[bool]) -> dict:
    """`attempted_flags` is over the full target population for one
    operation (was it routed with complete extraction?);
    `computed_flags`/`exact_match_flags` are over attempted questions
    only. Reuses `src.eval.metrics.aggregate_rate` (Task 2.6) for every
    rate - never a second rate-computation implementation."""
    return {
        "routing_coverage": aggregate_rate(attempted_flags),
        "computed_rate": aggregate_rate(computed_flags),
        "exact_match_rate": aggregate_rate(exact_match_flags),
    }


def build_derived_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    difference_question_count: int, greater_than_question_count: int,
    difference_rates: Mapping, greater_than_rates: Mapping, notes: str,
) -> dict:
    return {
        "row_id": row_id, "configuration": "deterministic_derived_calculations",
        "status": "phase3_11_derived_calculations", "run_id": run_id, "git_sha": git_sha,
        "phase3_config_hash": config_hash, "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": eval_scope_sha256, "question_count": difference_question_count + greater_than_question_count,
        "corpus_document_count": corpus_document_count, "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "structured_sql_derived_no_retrieval", "candidate_k": p3.NA,
        "doc_recall_at_10": p3.NA, "doc_recall_at_50": p3.NA, "doc_mrr": p3.NA, "doc_ndcg_at_10": p3.NA,
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": p3.NA, "retrieval_latency_p95_ms": p3.NA,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA, "index_size_bytes": p3.NA,
        "retrieval_mode": "structured_sql", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
        "fts_indexed_column": p3.NA, "dense_used_in_this_row": False,
        "delta_vs_qwen_dense_recall10": p3.NA, "delta_vs_qwen_dense_recall50": p3.NA,
        "delta_vs_qwen_dense_mrr": p3.NA, "delta_vs_qwen_dense_ndcg10": p3.NA,
        "dense_only_hits_at_10": p3.NA, "sparse_only_hits_at_10": p3.NA,
        "dense_only_hits_at_50": p3.NA, "sparse_only_hits_at_50": p3.NA,
        "fts_build_seconds": p3.NA, "fts_index_size_bytes": p3.NA,
        "fts_search_latency_p50_ms": p3.NA, "fts_search_latency_p95_ms": p3.NA,
        "fusion_method": p3.NA, "rrf_k": p3.NA, "dense_candidate_k": p3.NA, "sparse_candidate_k": p3.NA,
        "final_candidate_k": p3.NA, "sparse_index_identity": p3.NA,
        "delta_vs_sparse_recall10": p3.NA, "delta_vs_sparse_recall50": p3.NA,
        "delta_vs_sparse_mrr": p3.NA, "delta_vs_sparse_ndcg10": p3.NA,
        "hit10_gained_vs_dense": p3.NA, "hit10_lost_vs_dense": p3.NA,
        "hit50_gained_vs_dense": p3.NA, "hit50_lost_vs_dense": p3.NA,
        "hybrid_both_parent_top10": p3.NA, "hybrid_dense_only_top10": p3.NA, "hybrid_sparse_only_top10": p3.NA,
        "hybrid_both_parent_top50": p3.NA, "hybrid_dense_only_top50": p3.NA, "hybrid_sparse_only_top50": p3.NA,
        "dense_latency_p50_ms": p3.NA, "sparse_latency_p50_ms": p3.NA, "fusion_latency_p50_ms": p3.NA,
        "selected": p3.NA, "reranker_model": p3.NA, "reranker_revision": p3.NA, "reranker_identity": p3.NA,
        "rerank_base_k": p3.NA, "doc_recall_at_5": p3.NA, "doc_recall_at_5_hits": p3.NA,
        "delta_vs_no_rerank_mrr": p3.NA, "delta_vs_no_rerank_ndcg10": p3.NA,
        "delta_vs_no_rerank_precision5": p3.NA, "delta_vs_no_rerank_recall5": p3.NA,
        "hit5_gained_vs_no_rerank": p3.NA, "hit5_lost_vs_no_rerank": p3.NA,
        "reranker_latency_p50_ms": p3.NA, "reranker_latency_p95_ms": p3.NA,
        "crag_feature": p3.NA, "crag_threshold": p3.NA, "crag_calibration_method": p3.NA,
        "should_answer_count": p3.NA, "should_refuse_count": p3.NA,
        "true_refusal_rate": p3.NA, "false_refusal_rate": p3.NA, "missed_failure_rate": p3.NA, "crag_youden_j": p3.NA,
        "gazetteer_size": p3.NA, "concept_registry_size": p3.NA, "router_accuracy": p3.NA, "router_macro_f1": p3.NA,
        "filtered_question_count": p3.NA, "fallback_question_count": p3.NA,
        "xbrl_fact_question_count": p3.NA, "trap_question_count": p3.NA,
        "routing_coverage": p3.NA, "sql_found_rate": p3.NA, "sql_exact_match_rate": p3.NA, "trap_leak_rate": p3.NA,
        "difference_question_count": difference_question_count, "greater_than_question_count": greater_than_question_count,
        "difference_routing_coverage": difference_rates["routing_coverage"]["value"],
        "difference_exact_match_rate": difference_rates["exact_match_rate"]["value"],
        "greater_than_routing_coverage": greater_than_rates["routing_coverage"]["value"],
        "greater_than_exact_match_rate": greater_than_rates["exact_match_rate"]["value"],
        "notes": notes,
    }


__all__ = [
    "DERIVED_TASK", "ABLATION_TABLE_DERIVED_EXTRA_COLUMNS", "Phase3DerivedError",
    "compute_derived_config_hash", "derived_rates", "build_derived_ablation_row",
]
