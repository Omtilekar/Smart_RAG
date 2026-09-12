"""Task 3.7 - pure logic for CRAG-style confidence grading evaluation:
config-hash wrapper, rate aggregation (reusing Task 2.6's generic
`aggregate_rate` - never a second rate-computation implementation), and
the CRAG ablation-table row. No I/O, no model, no network, and - like
every other Phase 3 pure-logic module - no dependency on
`src.eval.test_access` anywhere in this module.

## Population (documented departure from the frozen 89-question retrieval scope)

Every other Phase 3 task (3.1-3.6) evaluates on the exact frozen
89-question `DEV/evaluable-subset` because they all measure RETRIEVAL
RANKING QUALITY against a known gold document - a metric that is
undefined for a question with no valid retrieval target. CRAG measures
something structurally different: whether the SYSTEM CORRECTLY DECIDES
TO ANSWER OR REFUSE, which requires examples of both. The frozen
89-question scope contains ONLY answerable, fully-covered questions
(Task 3.1's Option A definition) - it has no "should refuse" examples
at all, so it cannot calibrate or measure a refusal gate on its own.

This module's population is therefore two disjoint, independently
well-defined DEV subsets, neither newly invented nor requiring a new
coverage audit:

    should_answer: the exact frozen 89-question scope (unchanged, reused
                    verbatim - the same set Tasks 3.1-3.6 evaluate).
    should_refuse: every DEV question whose (category, subtype) is one
                    of `src.eval.phase3_baseline.NOT_APPLICABLE_SHAPES`
                    (unanswerable/year_outside_window,
                    adversarial/prompt_injection, adversarial/financial_advice,
                    adversarial/off_scope) - a fixed, already-defined
                    classification this project made in Task 3.1, reused
                    verbatim, never redefined here.

Deliberately EXCLUDED: DEV questions that are retrieval-applicable but
whose gold document is missing from the current (1,500-filing) Phase 1
corpus (the ~94% of DEV Task 3.1 excluded from the 89-question scope
because scoring them as retrieval misses would penalize the retriever
for a document that was never indexed). Whether that population is
usable CRAG evidence is a genuinely separate question this task does
not resolve - reusing it here would silently reopen Task 3.1's own
scope decision without review.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3
from src.eval.metrics import aggregate_rate

CRAG_TASK = "3.7"

# Single source of truth lives on `src.eval.phase3_baseline`.
ABLATION_TABLE_CRAG_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_CRAG_EXTRA_COLUMNS


class Phase3CragError(ValueError):
    """Raised for a malformed CRAG result build - never silently worked around."""


# --------------------------------------------------------------- config hash

def compute_crag_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` - never a second, independent
    hashing implementation."""
    return semantic_hash(config)


# --------------------------------------------------------------- rate aggregation

def crag_rates(*, should_answer_outcomes: Sequence[str], should_refuse_outcomes: Sequence[str]) -> dict:
    """`*_outcomes` are `classify_outcome()` results for each population.
    Reuses `src.eval.metrics.aggregate_rate` (Task 2.6) for every rate -
    never a second rate-computation implementation."""
    false_refusal = aggregate_rate([o == "false_refusal" for o in should_answer_outcomes])
    true_refusal = aggregate_rate([o == "true_refusal" for o in should_refuse_outcomes])
    missed_failure = aggregate_rate([o == "missed_failure" for o in should_refuse_outcomes])
    return {"false_refusal_rate": false_refusal, "true_refusal_rate": true_refusal, "missed_failure_rate": missed_failure}


# --------------------------------------------------------------- ablation row

def build_crag_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    should_answer_count: int, should_refuse_count: int, crag_feature: str, crag_threshold: float,
    crag_youden_j: float, rates: Mapping, retrieval_latency_p50_ms: float, retrieval_latency_p95_ms: float,
    notes: str,
) -> dict:
    return {
        "row_id": row_id, "configuration": "crag_confidence_grading", "status": "phase3_7_crag_confidence_grading",
        "run_id": run_id, "git_sha": git_sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": should_answer_count + should_refuse_count, "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "dense_only_crag_gated", "candidate_k": 50,
        "doc_recall_at_10": p3.NA, "doc_recall_at_50": p3.NA, "doc_mrr": p3.NA, "doc_ndcg_at_10": p3.NA,
        "precision_at_5": p3.NA, "refusal_metric": rates["missed_failure_rate"]["value"],
        "retrieval_latency_p50_ms": retrieval_latency_p50_ms, "retrieval_latency_p95_ms": retrieval_latency_p95_ms,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA, "index_size_bytes": p3.NA,
        "retrieval_mode": "dense_only", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
        "fts_indexed_column": p3.NA, "dense_used_in_this_row": True,
        "delta_vs_qwen_dense_recall10": p3.NA, "delta_vs_qwen_dense_recall50": p3.NA,
        "delta_vs_qwen_dense_mrr": p3.NA, "delta_vs_qwen_dense_ndcg10": p3.NA,
        "dense_only_hits_at_10": p3.NA, "sparse_only_hits_at_10": p3.NA,
        "dense_only_hits_at_50": p3.NA, "sparse_only_hits_at_50": p3.NA,
        "fts_build_seconds": p3.NA, "fts_index_size_bytes": p3.NA,
        "fts_search_latency_p50_ms": p3.NA, "fts_search_latency_p95_ms": p3.NA,
        "fusion_method": p3.NA, "rrf_k": p3.NA, "dense_candidate_k": 50, "sparse_candidate_k": p3.NA,
        "final_candidate_k": 50, "sparse_index_identity": p3.NA,
        "delta_vs_sparse_recall10": p3.NA, "delta_vs_sparse_recall50": p3.NA,
        "delta_vs_sparse_mrr": p3.NA, "delta_vs_sparse_ndcg10": p3.NA,
        "hit10_gained_vs_dense": p3.NA, "hit10_lost_vs_dense": p3.NA,
        "hit50_gained_vs_dense": p3.NA, "hit50_lost_vs_dense": p3.NA,
        "hybrid_both_parent_top10": p3.NA, "hybrid_dense_only_top10": p3.NA, "hybrid_sparse_only_top10": p3.NA,
        "hybrid_both_parent_top50": p3.NA, "hybrid_dense_only_top50": p3.NA, "hybrid_sparse_only_top50": p3.NA,
        "dense_latency_p50_ms": p3.NA, "sparse_latency_p50_ms": p3.NA, "fusion_latency_p50_ms": p3.NA,
        "selected": "no_rerank", "reranker_model": p3.NA, "reranker_revision": p3.NA, "reranker_identity": p3.NA,
        "rerank_base_k": p3.NA, "doc_recall_at_5": p3.NA, "doc_recall_at_5_hits": p3.NA,
        "delta_vs_no_rerank_mrr": p3.NA, "delta_vs_no_rerank_ndcg10": p3.NA,
        "delta_vs_no_rerank_precision5": p3.NA, "delta_vs_no_rerank_recall5": p3.NA,
        "hit5_gained_vs_no_rerank": p3.NA, "hit5_lost_vs_no_rerank": p3.NA,
        "reranker_latency_p50_ms": p3.NA, "reranker_latency_p95_ms": p3.NA,
        "crag_feature": crag_feature, "crag_threshold": crag_threshold, "crag_calibration_method": "youden_j",
        "should_answer_count": should_answer_count, "should_refuse_count": should_refuse_count,
        "true_refusal_rate": rates["true_refusal_rate"]["value"], "false_refusal_rate": rates["false_refusal_rate"]["value"],
        "missed_failure_rate": rates["missed_failure_rate"]["value"], "crag_youden_j": crag_youden_j,
        "notes": notes,
    }


__all__ = [
    "CRAG_TASK", "ABLATION_TABLE_CRAG_EXTRA_COLUMNS", "Phase3CragError",
    "compute_crag_config_hash", "crag_rates", "build_crag_ablation_row",
]
