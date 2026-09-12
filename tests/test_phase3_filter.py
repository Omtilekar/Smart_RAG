"""Task 3.9 - portable, pure-logic tests for src.eval.phase3_filter and
its interaction with the shared ablation-table freeze mechanisms and
Task 3.2/3.3's reused selection rule. No I/O, no LanceDB, no model, no
network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_ablation as p3a
from src.eval import phase3_baseline as p3
from src.eval import phase3_filter as p3f

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_filter_config_hash_deterministic():
    config = {"candidate_k": 50}
    assert p3f.compute_filter_config_hash(config) == p3f.compute_filter_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_9_metadata_prefiltering.json").read_text(encoding="utf-8"))
    assert config["chunk_config_hash"] == "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
    assert config["candidate_k"] == 50
    assert config["question_count"] == 89
    assert config["generation_enabled"] is False


def test_filtered_tiebreak_prefers_baseline():
    key_baseline = p3f.filtered_tiebreak_key({"row_id": "baseline"})
    key_filtered = p3f.filtered_tiebreak_key({"row_id": "filtered"})
    assert key_baseline < key_filtered


# --------------------------------------------------------------- reused selection rule integration

def test_select_round_winner_picks_baseline_on_practical_tie():
    candidates = [
        {"row_id": "baseline", "doc_recall_at_50": 1.0, "doc_mrr": 0.92, "doc_ndcg_at_10": 0.94, "doc_recall_at_10": 0.99},
        {"row_id": "filtered", "doc_recall_at_50": 1.0, "doc_mrr": 0.925, "doc_ndcg_at_10": 0.941, "doc_recall_at_10": 0.99},
    ]
    selection = p3a.select_round_winner(
        reference_row_id="baseline", candidates=candidates,
        bootstrap_vs_reference={"filtered": {"recall50_hit_delta": 0, "mrr_ci": (-0.01, 0.01), "ndcg_ci": (-0.01, 0.01)}},
        tiebreak_key_fn=p3f.filtered_tiebreak_key,
    )
    assert selection.winner_row_id == "baseline"


def test_select_round_winner_picks_filtered_on_credible_improvement():
    candidates = [
        {"row_id": "baseline", "doc_recall_at_50": 0.95, "doc_mrr": 0.85, "doc_ndcg_at_10": 0.88, "doc_recall_at_10": 0.90},
        {"row_id": "filtered", "doc_recall_at_50": 0.99, "doc_mrr": 0.95, "doc_ndcg_at_10": 0.96, "doc_recall_at_10": 0.97},
    ]
    selection = p3a.select_round_winner(
        reference_row_id="baseline", candidates=candidates,
        bootstrap_vs_reference={"filtered": {"recall50_hit_delta": 4, "mrr_ci": (0.05, 0.15), "ndcg_ci": (0.03, 0.12)}},
        tiebreak_key_fn=p3f.filtered_tiebreak_key,
    )
    assert selection.winner_row_id == "filtered"


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="metadata_prefilter", config_hash="c" * 64):
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, question_count=89, corpus_document_count=100,
        chunk_count=323971, chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64, candidate_k=50,
        metrics={"doc_recall_at_10": 0.99, "doc_recall_at_50": 1.0, "doc_mrr": 0.93, "doc_ndcg_at_10": 0.94},
        deltas={"recall10": 0.0, "recall50": 0.0, "mrr": 0.005, "ndcg10": 0.003},
        filtered_question_count=80, fallback_question_count=9,
        retrieval_latency_p50_ms=5.0, retrieval_latency_p95_ms=10.0, selected="metadata_prefilter", notes="test row",
    )


def test_build_filter_ablation_row_shape_and_flags():
    row = p3f.build_filter_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is True
    assert row["filtered_question_count"] == 80
    assert row["fallback_question_count"] == 9
    assert row["selected"] == "metadata_prefilter"
    # Later columns added additively by Task 3.10 (SQL-path-only fields)
    # are correctly absent here - `_row_to_csv_dict()` defaults them to NA.
    later_task_columns = set(p3.ABLATION_TABLE_SQL_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS)
    for col in set(p3.ABLATION_TABLE_COLUMNS) - later_task_columns:
        assert col in row, f"missing ablation-table column {col!r} in filter row"


def test_ablation_table_columns_extended_additively_for_filter():
    for col in p3f.ABLATION_TABLE_FILTER_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_filter_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    router_row = {"row_id": "rules_router", "phase3_config_hash": "y" * 64}
    rows = [row0, router_row]
    filter_row = p3f.build_filter_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, filter_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == router_row
    assert updated[2]["row_id"] == "metadata_prefilter"


def test_upsert_row_refuses_to_overwrite_filter_row_with_different_hash():
    existing = p3f.build_filter_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3f.build_filter_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6",
                                     "crag_confidence", "rules_router"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
