"""Task 3.5 - portable, pure-logic tests for src.eval.phase3_hybrid and
its interaction with the shared src.eval.phase3_baseline/phase3_ablation
freeze mechanisms. No I/O, no LanceDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_ablation as p3a
from src.eval import phase3_hybrid as p3h

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- config hash

def test_hybrid_config_hash_is_deterministic():
    config = {"rrf_k": 60, "final_candidate_k": 50}
    assert p3h.compute_hybrid_config_hash(config) == p3h.compute_hybrid_config_hash(config)


def test_hybrid_config_hash_changes_with_rrf_k():
    a = p3h.compute_hybrid_config_hash({"rrf_k": 60})
    b = p3h.compute_hybrid_config_hash({"rrf_k": 30})
    assert a != b


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_5_rrf_hybrid_fusion.json").read_text(encoding="utf-8"))
    assert config["chunk_config_hash"] == "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
    assert config["fusion"]["rrf_k"] == 60
    assert config["fusion"]["dense_candidate_k"] == 50
    assert config["fusion"]["sparse_candidate_k"] == 50
    assert config["fusion"]["final_candidate_k"] == 50
    assert config["fusion"]["fusion_union_key"] == "chunk_id"
    assert config["generation_enabled"] is False
    assert config["reranker_enabled"] is False
    assert config["metadata_prefilter_enabled"] is False
    assert config["question_count"] == 89


# --------------------------------------------------------------- gain/loss

@pytest.mark.parametrize("before,after,expected", [
    (False, True, "gained"), (True, False, "lost"), (True, True, "unchanged"), (False, False, "unchanged"),
])
def test_classify_gain_loss(before, after, expected):
    assert p3h.classify_gain_loss(before, after) == expected


def test_gain_loss_counts_aggregates_correctly():
    before = {"q1": {"hit10": False}, "q2": {"hit10": True}, "q3": {"hit10": True}, "q4": {"hit10": False}}
    after = {"q1": {"hit10": True}, "q2": {"hit10": False}, "q3": {"hit10": True}, "q4": {"hit10": False}}
    counts = p3h.gain_loss_counts(before, after, ["q1", "q2", "q3", "q4"], hit_field="hit10")
    assert counts == {"gained": 1, "lost": 1, "unchanged": 2}


def test_gain_loss_counts_raises_on_missing_question_id():
    with pytest.raises(p3h.Phase3HybridError):
        p3h.gain_loss_counts({"q1": {"hit10": True}}, {}, ["q1"], hit_field="hit10")


# --------------------------------------------------------------- rank movement

@pytest.mark.parametrize("before,after,expected", [
    (1, 2, "worsened"), (5, 1, "improved"), (3, 3, "unchanged"),
    (None, None, "unchanged"), (None, 4, "improved"), (4, None, "worsened"),
])
def test_rank_movement(before, after, expected):
    assert p3h.rank_movement(before, after) == expected


def test_rank_movement_counts_aggregates_correctly():
    before = {"q1": {"rank10": 1}, "q2": {"rank10": None}, "q3": {"rank10": 2}}
    after = {"q1": {"rank10": 2}, "q2": {"rank10": 1}, "q3": {"rank10": 2}}
    counts = p3h.rank_movement_counts(before, after, ["q1", "q2", "q3"], rank_field="rank10")
    assert counts == {"improved": 1, "worsened": 1, "unchanged": 1}


# --------------------------------------------------------------- fusion composition

def test_fusion_composition_counts():
    entries = [
        {"in_dense": True, "in_sparse": True}, {"in_dense": True, "in_sparse": False},
        {"in_dense": False, "in_sparse": True}, {"in_dense": True, "in_sparse": True},
    ]
    counts = p3h.fusion_composition_counts(entries)
    assert counts == {"both": 2, "dense_only": 1, "sparse_only": 1}


def test_fusion_composition_counts_rejects_neither_flag_set():
    with pytest.raises(p3h.Phase3HybridError):
        p3h.fusion_composition_counts([{"in_dense": False, "in_sparse": False}])


# --------------------------------------------------------------- selection rule (Stage 9)

DENSE_METRICS = {"doc_recall_at_10": 0.9888, "doc_recall_at_50": 1.0, "doc_mrr": 0.9251, "doc_ndcg_at_10": 0.9407}


def test_selection_gate1_rejects_hybrid_that_drops_below_dense_r50_ceiling():
    hybrid_metrics = {"doc_recall_at_50_hits": 88, "doc_recall_at_10": 0.99, "doc_mrr": 0.99, "doc_ndcg_at_10": 0.99}
    result = p3h.select_hybrid_configuration(
        hybrid_metrics=hybrid_metrics, dense_metrics=DENSE_METRICS, question_count=89,
        recall10_hit_delta=5, mrr_ci=(0.01, 0.05), ndcg_ci=(0.01, 0.05),
    )
    assert result.selected == "dense_only"
    assert result.eligible is False
    assert not result.flagged_for_user_decision


def test_selection_practical_tie_prefers_dense_only():
    hybrid_metrics = {"doc_recall_at_50_hits": 89, "doc_recall_at_10": 0.99, "doc_mrr": 0.93, "doc_ndcg_at_10": 0.945}
    result = p3h.select_hybrid_configuration(
        hybrid_metrics=hybrid_metrics, dense_metrics=DENSE_METRICS, question_count=89,
        recall10_hit_delta=0, mrr_ci=(-0.01, 0.02), ndcg_ci=(-0.01, 0.02),
    )
    assert result.selected == "dense_only"
    assert result.eligible is True
    assert not result.flagged_for_user_decision


def test_selection_picks_hybrid_on_credible_mrr_improvement():
    hybrid_metrics = {"doc_recall_at_50_hits": 89, "doc_recall_at_10": 0.99, "doc_mrr": 0.95, "doc_ndcg_at_10": 0.945}
    result = p3h.select_hybrid_configuration(
        hybrid_metrics=hybrid_metrics, dense_metrics=DENSE_METRICS, question_count=89,
        recall10_hit_delta=3, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.001, 0.01),
    )
    assert result.selected == "hybrid"
    assert not result.flagged_for_user_decision


def test_selection_flags_trade_off_for_user_decision():
    hybrid_metrics = {"doc_recall_at_50_hits": 89, "doc_recall_at_10": 0.99, "doc_mrr": 0.95, "doc_ndcg_at_10": 0.90}
    result = p3h.select_hybrid_configuration(
        hybrid_metrics=hybrid_metrics, dense_metrics=DENSE_METRICS, question_count=89,
        recall10_hit_delta=3, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.06, -0.01),
    )
    assert result.selected is None
    assert result.eligible is True
    assert result.flagged_for_user_decision
    assert result.flag_reason


def test_selection_dense_only_when_hybrid_improves_nothing():
    hybrid_metrics = {"doc_recall_at_50_hits": 89, "doc_recall_at_10": 0.95, "doc_mrr": 0.90, "doc_ndcg_at_10": 0.90}
    result = p3h.select_hybrid_configuration(
        hybrid_metrics=hybrid_metrics, dense_metrics=DENSE_METRICS, question_count=89,
        recall10_hit_delta=-4, mrr_ci=(-0.05, -0.01), ndcg_ci=(-0.05, -0.01),
    )
    assert result.selected == "dense_only"
    assert not result.flagged_for_user_decision


def test_is_practical_tie_hybrid_uses_recall10_not_recall50():
    assert p3h.is_practical_tie_hybrid(recall10_hit_delta=1, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.01, 0.01))
    assert not p3h.is_practical_tie_hybrid(recall10_hit_delta=2, mrr_ci=(-0.01, 0.01), ndcg_ci=(-0.01, 0.01))
    assert not p3h.is_practical_tie_hybrid(recall10_hit_delta=1, mrr_ci=(0.01, 0.05), ndcg_ci=(-0.01, 0.01))


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="hybrid_rrf", config_hash="c" * 64):
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, question_count=89, corpus_document_count=100,
        chunk_count=323971, chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        sparse_index_identity_hash_value="f" * 64, rrf_k=60, dense_candidate_k=50, sparse_candidate_k=50,
        final_candidate_k=50,
        metrics={"doc_recall_at_10": 0.99, "doc_recall_at_50": 1.0, "doc_mrr": 0.93, "doc_ndcg_at_10": 0.94},
        deltas_vs_dense={"recall10": 0.001, "recall50": 0.0, "mrr": 0.005, "ndcg10": 0.003},
        deltas_vs_sparse={"recall10": 0.02, "recall50": 0.01, "mrr": 0.05, "ndcg10": 0.04},
        hit_gain_loss_10={"gained": 2, "lost": 1, "unchanged": 86},
        hit_gain_loss_50={"gained": 0, "lost": 0, "unchanged": 89},
        composition_top10={"both": 8, "dense_only": 1, "sparse_only": 1},
        composition_top50={"both": 40, "dense_only": 8, "sparse_only": 2},
        dense_latency_p50_ms=20.0, sparse_latency_p50_ms=6.0, fusion_latency_p50_ms=0.1,
        hybrid_latency_p50_ms=26.5, hybrid_latency_p95_ms=35.0, selected="hybrid", notes="test row",
    )


def test_build_hybrid_ablation_row_shape_and_flags():
    row = p3h.build_hybrid_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is True
    assert row["retrieval_mode"] == "hybrid"
    assert row["fusion_method"] == "rrf"
    assert row["rrf_k"] == 60
    assert row["selected"] == "hybrid"
    assert row["precision_at_5"] == p3.NA
    assert row["hit10_gained_vs_dense"] == 2
    assert row["hit10_lost_vs_dense"] == 1
    # Later columns added additively by Task 3.6/3.7 (rerank-only/CRAG-only
    # fields) are correctly absent here - `_row_to_csv_dict()` defaults
    # them to NA.
    later_task_columns = (
        set(p3.ABLATION_TABLE_RERANK_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_CRAG_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_ROUTER_EXTRA_COLUMNS)
    )
    for col in set(p3.ABLATION_TABLE_COLUMNS) - later_task_columns:
        assert col in row, f"missing ablation-table column {col!r} in hybrid row"


def test_ablation_table_columns_extended_additively_for_hybrid():
    for col in p3h.ABLATION_TABLE_HYBRID_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_hybrid_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64, "doc_recall_at_10": 0.9}
    sparse_row = {"row_id": "bm25_fts", "phase3_config_hash": "y" * 64, "doc_recall_at_10": 0.96}
    rows = [row0, sparse_row]
    hybrid_row = p3h.build_hybrid_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, hybrid_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == sparse_row
    assert updated[2]["row_id"] == "hybrid_rrf"


def test_upsert_row_refuses_to_overwrite_hybrid_row_with_different_hash():
    existing = p3h.build_hybrid_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3h.build_hybrid_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


# --------------------------------------------------------------- scope / split / bootstrap (reused, not reimplemented)

def test_frozen_scope_mismatch_is_rejected():
    with pytest.raises(p3a.Phase3AblationError):
        p3a.assert_frozen_scope(["q1", "q2"], ["q1", "q3"])


def test_test_split_is_rejected():
    with pytest.raises(p3a.Phase3AblationError):
        p3a.assert_dev_split("test")


def test_paired_bootstrap_deterministic_with_seed_42():
    cand = [1.0, 0.0, 1.0, 1.0, 0.0]
    base = [0.0, 0.0, 1.0, 0.0, 0.0]
    r1 = p3a.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=1000)
    r2 = p3a.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=1000)
    assert r1.ci_lo == r2.ci_lo and r1.ci_hi == r2.ci_hi and r1.point_estimate == r2.point_estimate
