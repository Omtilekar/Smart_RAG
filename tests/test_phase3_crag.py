"""Task 3.7 - portable, pure-logic tests for src.eval.phase3_crag and its
interaction with the shared ablation-table freeze mechanisms. No I/O, no
LanceDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_crag as p3c

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_crag_config_hash_deterministic():
    config = {"crag_feature": "top1_score"}
    assert p3c.compute_crag_config_hash(config) == p3c.compute_crag_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_7_crag_confidence_grading.json").read_text(encoding="utf-8"))
    assert config["chunk_config_hash"] == "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
    assert config["should_answer_scope"]["question_count"] == 89
    assert config["calibration_method"] == "youden_j"
    assert config["generation_enabled"] is False
    shapes = {tuple(s) for s in config["should_refuse_scope"]["shapes"]}
    assert shapes == p3.NOT_APPLICABLE_SHAPES


def test_crag_rates_hand_calculation():
    # should_answer: 3 correct_answer, 1 false_refusal -> false_refusal_rate = 1/4
    should_answer_outcomes = ["correct_answer", "correct_answer", "correct_answer", "false_refusal"]
    # should_refuse: 2 true_refusal, 1 missed_failure -> true_refusal_rate=2/3, missed_failure_rate=1/3
    should_refuse_outcomes = ["true_refusal", "true_refusal", "missed_failure"]
    rates = p3c.crag_rates(should_answer_outcomes=should_answer_outcomes, should_refuse_outcomes=should_refuse_outcomes)
    assert rates["false_refusal_rate"]["value"] == pytest.approx(0.25)
    assert rates["false_refusal_rate"]["numerator"] == 1
    assert rates["false_refusal_rate"]["denominator"] == 4
    assert rates["true_refusal_rate"]["value"] == pytest.approx(2 / 3)
    assert rates["missed_failure_rate"]["value"] == pytest.approx(1 / 3)
    # true_refusal_rate + missed_failure_rate must sum to 1 (complementary over should_refuse)
    assert rates["true_refusal_rate"]["value"] + rates["missed_failure_rate"]["value"] == pytest.approx(1.0)


def test_crag_rates_perfect_gate():
    rates = p3c.crag_rates(
        should_answer_outcomes=["correct_answer"] * 5,
        should_refuse_outcomes=["true_refusal"] * 5,
    )
    assert rates["false_refusal_rate"]["value"] == 0.0
    assert rates["true_refusal_rate"]["value"] == 1.0
    assert rates["missed_failure_rate"]["value"] == 0.0


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="crag_confidence", config_hash="c" * 64):
    rates = p3c.crag_rates(
        should_answer_outcomes=["correct_answer"] * 85 + ["false_refusal"] * 4,
        should_refuse_outcomes=["true_refusal"] * 90 + ["missed_failure"] * 23,
    )
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, corpus_document_count=100, chunk_count=323971,
        chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        should_answer_count=89, should_refuse_count=113, crag_feature="top1_score", crag_threshold=0.42,
        crag_youden_j=0.6, rates=rates, retrieval_latency_p50_ms=20.0, retrieval_latency_p95_ms=35.0,
        notes="test row",
    )


def test_build_crag_ablation_row_shape_and_flags():
    row = p3c.build_crag_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is True
    assert row["crag_feature"] == "top1_score"
    assert row["crag_threshold"] == 0.42
    assert row["should_answer_count"] == 89
    assert row["should_refuse_count"] == 113
    assert row["question_count"] == 89 + 113
    assert row["refusal_metric"] == row["missed_failure_rate"]
    assert row["doc_recall_at_10"] == p3.NA  # no ranking metric computed in this task
    # Later columns added additively by Task 3.8 (router-only fields) are
    # correctly absent here - `_row_to_csv_dict()` defaults them to NA.
    later_task_columns = (
        set(p3.ABLATION_TABLE_ROUTER_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_FILTER_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_SQL_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS)
    )
    for col in set(p3.ABLATION_TABLE_COLUMNS) - later_task_columns:
        assert col in row, f"missing ablation-table column {col!r} in CRAG row"


def test_ablation_table_columns_extended_additively_for_crag():
    for col in p3c.ABLATION_TABLE_CRAG_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_crag_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    rerank_row = {"row_id": "ce_minilm_l6", "phase3_config_hash": "y" * 64}
    rows = [row0, rerank_row]
    crag_row = p3c.build_crag_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, crag_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == rerank_row
    assert updated[2]["row_id"] == "crag_confidence"


def test_upsert_row_refuses_to_overwrite_crag_row_with_different_hash():
    existing = p3c.build_crag_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3c.build_crag_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


# --------------------------------------------------------------- N/A discipline

def test_na_is_not_zero_in_crag_row():
    row = p3c.build_crag_ablation_row(**_sample_row_kwargs())
    assert row["doc_mrr"] != 0
    assert row["doc_mrr"] == p3.NA
