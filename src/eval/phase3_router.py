"""Task 3.8 - pure logic for rules-first router evaluation: config-hash
wrapper, confusion-matrix / per-class precision-recall-F1 computation
(a genuinely new metric family - Task 2.6's `src.eval.metrics` is
retrieval-ranking/refusal-rate shaped, not multi-class-classification
shaped, so this is not a duplicate of anything there), and the router
ablation-table row. No I/O, no model, no network, and - like every
other Phase 3 pure-logic module - no dependency on `src.eval.test_access`
anywhere in this module.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from src.artifacts.versioning import semantic_hash
from src.eval import phase3_baseline as p3

ROUTER_TASK = "3.8"

# Single source of truth lives on `src.eval.phase3_baseline`.
ABLATION_TABLE_ROUTER_EXTRA_COLUMNS: tuple[str, ...] = p3.ABLATION_TABLE_ROUTER_EXTRA_COLUMNS


class Phase3RouterError(ValueError):
    """Raised for malformed confusion-matrix input or an ablation-row
    build missing required fields - never silently worked around."""


# --------------------------------------------------------------- config hash

def compute_router_config_hash(config: Mapping) -> str:
    """Task 2.10's canonical `semantic_hash()` - never a second,
    independent hashing implementation."""
    return semantic_hash(config)


# --------------------------------------------------------------- confusion matrix / per-class metrics

def build_confusion_matrix(true_labels: Sequence[str], predicted_labels: Sequence[str],
                            classes: Sequence[str]) -> dict[str, dict[str, int]]:
    """`confusion[true_class][predicted_class] = count`. Every class in
    `classes` gets a full row/column even if it has zero observations -
    never a sparse/partial matrix a caller has to guess the shape of."""
    if len(true_labels) != len(predicted_labels):
        raise Phase3RouterError(
            f"true_labels and predicted_labels must be the same length, got {len(true_labels)} != {len(predicted_labels)}"
        )
    class_set = set(classes)
    confusion = {c: {c2: 0 for c2 in classes} for c in classes}
    for t, p in zip(true_labels, predicted_labels):
        if t not in class_set:
            raise Phase3RouterError(f"true label {t!r} is not in the declared class set {sorted(class_set)}")
        if p not in class_set:
            raise Phase3RouterError(f"predicted label {p!r} is not in the declared class set {sorted(class_set)}")
        confusion[t][p] += 1
    return confusion


def per_class_metrics(confusion: Mapping[str, Mapping[str, int]], classes: Sequence[str]) -> dict[str, dict]:
    """Precision/recall/F1/support per class, computed directly from the
    confusion matrix (standard definitions: precision = TP/(TP+FP),
    recall = TP/(TP+FN), F1 = harmonic mean; 0.0 when a denominator is 0,
    never a division error or a fabricated 1.0)."""
    result = {}
    for c in classes:
        tp = confusion[c][c]
        fp = sum(confusion[other][c] for other in classes if other != c)
        fn = sum(confusion[c][other] for other in classes if other != c)
        support = sum(confusion[c][other] for other in classes)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        result[c] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    return result


def overall_accuracy(confusion: Mapping[str, Mapping[str, int]], classes: Sequence[str]) -> dict:
    correct = sum(confusion[c][c] for c in classes)
    total = sum(confusion[c][c2] for c in classes for c2 in classes)
    if total == 0:
        raise Phase3RouterError("cannot compute accuracy over zero observations")
    return {"value": correct / total, "numerator": correct, "denominator": total}


def macro_f1(per_class: Mapping[str, Mapping[str, float]], classes: Sequence[str]) -> float:
    if not classes:
        raise Phase3RouterError("macro_f1 requires at least one class")
    return sum(per_class[c]["f1"] for c in classes) / len(classes)


# --------------------------------------------------------------- ablation row

def build_router_ablation_row(
    *, row_id: str, config_hash: str, run_id: str, git_sha: str, eval_scope_sha256: str,
    corpus_document_count: int, chunk_count: int, chunk_config_hash: str,
    dense_repository: str, dense_revision: str, dense_embedding_identity_hash: str, dense_index_identity_hash: str,
    question_count: int, gazetteer_size: int, concept_registry_size: int, router_accuracy: float,
    router_macro_f1: float, notes: str,
) -> dict:
    return {
        "row_id": row_id, "configuration": "rules_first_router", "status": "phase3_8_rules_first_router",
        "run_id": run_id, "git_sha": git_sha, "phase3_config_hash": config_hash,
        "eval_split": "dev", "eval_scope_kind": p3.PHASE3_DEV_SCOPE_KIND, "eval_scope_sha256": eval_scope_sha256,
        "question_count": question_count, "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count, "chunk_config_hash": chunk_config_hash,
        "embedding_model": dense_repository, "embedding_revision": dense_revision,
        "embedding_identity": dense_embedding_identity_hash, "index_identity": dense_index_identity_hash,
        "retrieval": "dense_only_downstream_of_router", "candidate_k": 50,
        "doc_recall_at_10": p3.NA, "doc_recall_at_50": p3.NA, "doc_mrr": p3.NA, "doc_ndcg_at_10": p3.NA,
        "precision_at_5": p3.NA, "refusal_metric": p3.NA,
        "retrieval_latency_p50_ms": p3.NA, "retrieval_latency_p95_ms": p3.NA,
        "query_embedding_latency_p50_ms": p3.NA, "search_latency_p50_ms": p3.NA, "index_size_bytes": p3.NA,
        "retrieval_mode": "dense_only", "sparse_backend": p3.NA, "lancedb_version": p3.NA,
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
        "gazetteer_size": gazetteer_size, "concept_registry_size": concept_registry_size,
        "router_accuracy": router_accuracy, "router_macro_f1": router_macro_f1,
        "notes": notes,
    }


__all__ = [
    "ROUTER_TASK", "ABLATION_TABLE_ROUTER_EXTRA_COLUMNS", "Phase3RouterError",
    "compute_router_config_hash", "build_confusion_matrix", "per_class_metrics",
    "overall_accuracy", "macro_f1", "build_router_ablation_row",
]
