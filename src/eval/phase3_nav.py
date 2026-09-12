"""Task 3.12 - pure logic for tree/section-navigation evaluation:
config-hash wrapper, rate aggregation (reusing Task 2.6's
`aggregate_rate` unmodified), and the navigation ablation row. No I/O,
no DuckDB, no model, no network, and - like every other Phase 3
pure-logic module - no dependency on `src.eval.test_access` anywhere in
this module.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3
from src.eval.metrics import aggregate_rate

NAV_TASK = "3.12"

# Single source of truth lives on `src.eval.phase3_baseline`.
ABLATION_TABLE_NAV_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_NAV_EXTRA_COLUMNS


class Phase3NavError(ValueError):
    """Raised for a malformed navigation evaluation result - never
    silently worked around."""


def compute_nav_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` - never a second,
    independent hashing implementation."""
    return semantic_hash(config)


def nav_rates(*, resolution_flags: Sequence[bool], section_found_flags: Sequence[bool],
              leak_flags: Sequence[bool]) -> dict:
    """`resolution_flags` is over every parsed (cik, fiscal_year)
    document (did resolve_filing_document_id() round-trip back to the
    correct document_id?); `section_found_flags` is over every
    (document, detected-item) navigation attempt (did navigate_to_section()
    return outcome='found'?); `leak_flags` is over every attempt with a
    result (did any returned node's section_id NOT equal the requested
    item, or did node_count == total_document_node_count, i.e. an
    unrestricted/global read?). Reuses `src.eval.metrics.aggregate_rate`
    (Task 2.6) for every rate - never a second rate-computation
    implementation."""
    return {
        "filing_resolution_rate": aggregate_rate(resolution_flags),
        "section_found_rate": aggregate_rate(section_found_flags),
        "scope_leak_rate": aggregate_rate(leak_flags),
    }


def build_nav_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    parsed_document_count: int, navigation_attempt_count: int, rates: Mapping, notes: str,
) -> dict:
    return {
        "row_id": row_id, "configuration": "tree_section_navigation",
        "status": "phase3_12_tree_section_navigation", "run_id": run_id, "git_sha": git_sha,
        "phase3_config_hash": config_hash, "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": eval_scope_sha256, "question_count": navigation_attempt_count,
        "corpus_document_count": corpus_document_count, "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "structural_section_navigation_no_retrieval", "candidate_k": p3.NA,
        "doc_recall_at_10": p3.NA, "doc_recall_at_50": p3.NA, "doc_mrr": p3.NA, "doc_ndcg_at_10": p3.NA,
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": p3.NA, "retrieval_latency_p95_ms": p3.NA,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA, "index_size_bytes": p3.NA,
        "retrieval_mode": "structural_navigation", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
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
        "difference_question_count": p3.NA, "greater_than_question_count": p3.NA,
        "difference_routing_coverage": p3.NA, "difference_exact_match_rate": p3.NA,
        "greater_than_routing_coverage": p3.NA, "greater_than_exact_match_rate": p3.NA,
        "nav_parsed_document_count": parsed_document_count, "nav_navigation_attempt_count": navigation_attempt_count,
        "nav_filing_resolution_rate": rates["filing_resolution_rate"]["value"],
        "nav_section_found_rate": rates["section_found_rate"]["value"],
        "nav_scope_leak_rate": rates["scope_leak_rate"]["value"],
        "notes": notes,
    }


__all__ = [
    "NAV_TASK", "ABLATION_TABLE_NAV_EXTRA_COLUMNS", "Phase3NavError",
    "compute_nav_config_hash", "nav_rates", "build_nav_ablation_row",
]
