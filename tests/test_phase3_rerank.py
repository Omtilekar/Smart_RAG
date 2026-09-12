"""Task 3.6 - portable, pure-logic tests for src.eval.phase3_rerank and
its interaction with the shared ablation-table freeze mechanisms. No
I/O, no LanceDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_rerank as p3r

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- config hash

def test_rerank_config_hash_is_deterministic():
    config = {"rerank_base_k": 50}
    assert p3r.compute_rerank_config_hash(config) == p3r.compute_rerank_config_hash(config)


def test_rerank_config_hash_changes_with_model():
    a = p3r.compute_rerank_config_hash({"model": "ce_minilm_l6"})
    b = p3r.compute_rerank_config_hash({"model": "other"})
    assert a != b


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_6_cross_encoder_reranking.json").read_text(encoding="utf-8"))
    assert config["chunk_config_hash"] == "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
    assert config["rerank_base_k"] == 50
    assert config["reranker"]["model_repository"] == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert config["reranker"]["score_activation"] == "raw_logit"
    assert config["generation_enabled"] is False
    assert config["question_count"] == 89


# --------------------------------------------------------------- candidate-set recall integrity

def test_candidate_set_recall_unchanged_passes_for_equal_values():
    p3r.assert_candidate_set_recall_unchanged(0.9887640449438202, 0.9887640449438202)


def test_candidate_set_recall_unchanged_rejects_drift():
    with pytest.raises(p3r.Phase3RerankError):
        p3r.assert_candidate_set_recall_unchanged(0.98, 0.99)


# --------------------------------------------------------------- selection rule

BASE_METRICS = {"doc_mrr": 0.9251, "doc_ndcg_at_10": 0.9407, "doc_precision_at_5": 0.20, "doc_recall_at_5": 0.95}


def test_is_practical_tie_rerank_uses_recall5():
    assert p3r.is_practical_tie_rerank(recall5_hit_delta=1, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.01, 0.01))
    assert not p3r.is_practical_tie_rerank(recall5_hit_delta=2, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.01, 0.01))
    assert not p3r.is_practical_tie_rerank(recall5_hit_delta=1, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.01, 0.01))


def test_selection_practical_tie_prefers_no_rerank():
    reranked = {"doc_mrr": 0.93, "doc_ndcg_at_10": 0.945, "doc_precision_at_5": 0.205, "doc_recall_at_5": 0.955}
    result = p3r.select_rerank_configuration(
        reranked_metrics=reranked, base_metrics=BASE_METRICS,
        recall5_hit_delta=0, mrr_ci=(-0.005, 0.01), ndcg_ci=(-0.005, 0.01),
    )
    assert result.selected == "no_rerank"
    assert not result.flagged_for_user_decision


def test_selection_picks_reranked_on_credible_mrr_improvement():
    reranked = {"doc_mrr": 0.95, "doc_ndcg_at_10": 0.945, "doc_precision_at_5": 0.21, "doc_recall_at_5": 0.96}
    result = p3r.select_rerank_configuration(
        reranked_metrics=reranked, base_metrics=BASE_METRICS,
        recall5_hit_delta=3, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.001, 0.01),
    )
    assert result.selected == "reranked"
    assert not result.flagged_for_user_decision


def test_selection_flags_trade_off():
    reranked = {"doc_mrr": 0.95, "doc_ndcg_at_10": 0.88, "doc_precision_at_5": 0.19, "doc_recall_at_5": 0.94}
    result = p3r.select_rerank_configuration(
        reranked_metrics=reranked, base_metrics=BASE_METRICS,
        recall5_hit_delta=3, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.08, -0.01),
    )
    assert result.selected is None
    assert result.flagged_for_user_decision


def test_selection_no_rerank_when_nothing_improves():
    reranked = {"doc_mrr": 0.90, "doc_ndcg_at_10": 0.90, "doc_precision_at_5": 0.18, "doc_recall_at_5": 0.92}
    result = p3r.select_rerank_configuration(
        reranked_metrics=reranked, base_metrics=BASE_METRICS,
        recall5_hit_delta=-3, mrr_ci=(-0.05, -0.01), ndcg_ci=(-0.05, -0.01),
    )
    assert result.selected == "no_rerank"
    assert not result.flagged_for_user_decision


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="ce_minilm_l6", config_hash="c" * 64):
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, question_count=89, corpus_document_count=100,
        chunk_count=323971, chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        reranker_repository="cross-encoder/ms-marco-MiniLM-L6-v2", reranker_revision="233902d25c440f23af6f7d6e94d2946bac0bee0a",
        reranker_identity_hash="r" * 64, rerank_base_k=50,
        metrics={"doc_recall_at_10": 0.99, "doc_recall_at_50": 1.0, "doc_mrr": 0.93, "doc_ndcg_at_10": 0.94,
                 "doc_precision_at_5": 0.20, "doc_recall_at_5": 0.96, "doc_recall_at_5_hits": 85},
        deltas={"recall10": 0.0, "recall50": 0.0, "mrr": 0.005, "ndcg10": 0.003, "precision5": 0.01, "recall5": 0.01},
        hit_gain_loss_5={"gained": 2, "lost": 1, "unchanged": 86},
        reranker_latency_p50_ms=15.0, reranker_latency_p95_ms=25.0,
        retrieval_latency_p50_ms=35.0, retrieval_latency_p95_ms=50.0, selected="reranked", notes="test row",
    )


def test_build_rerank_ablation_row_shape_and_flags():
    row = p3r.build_rerank_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is True
    assert row["reranker_model"] == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert row["rerank_base_k"] == 50
    assert row["precision_at_5"] == 0.20
    assert row["doc_recall_at_5"] == 0.96
    assert row["selected"] == "reranked"
    for col in p3.ABLATION_TABLE_COLUMNS:
        assert col in row, f"missing ablation-table column {col!r} in rerank row"


def test_ablation_table_columns_extended_additively_for_rerank():
    for col in p3r.ABLATION_TABLE_RERANK_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_rerank_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    hybrid_row = {"row_id": "hybrid_rrf", "phase3_config_hash": "y" * 64}
    rows = [row0, hybrid_row]
    rerank_row = p3r.build_rerank_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, rerank_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == hybrid_row
    assert updated[2]["row_id"] == "ce_minilm_l6"


def test_upsert_row_refuses_to_overwrite_rerank_row_with_different_hash():
    existing = p3r.build_rerank_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3r.build_rerank_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
