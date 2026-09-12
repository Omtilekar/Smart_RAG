"""Task 3.11 - portable, pure-logic tests for src.eval.phase3_derived
and its interaction with the shared ablation-table freeze mechanisms.
No I/O, no DuckDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_derived as p3d

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_derived_config_hash_deterministic():
    config = {"operations": ["difference"]}
    assert p3d.compute_derived_config_hash(config) == p3d.compute_derived_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_11_derived_calculations.json").read_text(encoding="utf-8"))
    assert "difference" in config["operations"]
    assert "greater_than" in config["operations"]
    assert config["generation_enabled"] is False


def test_derived_rates_hand_calculation():
    rates = p3d.derived_rates(
        attempted_flags=[True, True, False, True], computed_flags=[True, False, True], exact_match_flags=[True, False],
    )
    assert rates["routing_coverage"] == {"value": pytest.approx(0.75), "numerator": 3, "denominator": 4}
    assert rates["computed_rate"] == {"value": pytest.approx(2 / 3), "numerator": 2, "denominator": 3}
    assert rates["exact_match_rate"] == {"value": pytest.approx(0.5), "numerator": 1, "denominator": 2}


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="derived_calculations", config_hash="c" * 64):
    diff_rates = p3d.derived_rates(attempted_flags=[True] * 200 + [False] * 44,
                                    computed_flags=[True] * 190 + [False] * 10, exact_match_flags=[True] * 185 + [False] * 15)
    cmp_rates = p3d.derived_rates(attempted_flags=[True] * 80 + [False] * 25,
                                   computed_flags=[True] * 78 + [False] * 2, exact_match_flags=[True] * 77 + [False] * 3)
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, corpus_document_count=100, chunk_count=323971,
        chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        difference_question_count=244, greater_than_question_count=105,
        difference_rates=diff_rates, greater_than_rates=cmp_rates, notes="test row",
    )


def test_build_derived_ablation_row_shape_and_flags():
    row = p3d.build_derived_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is False
    assert row["difference_question_count"] == 244
    assert row["greater_than_question_count"] == 105
    assert row["question_count"] == 349
    assert row["doc_recall_at_10"] == p3.NA
    for col in p3.ABLATION_TABLE_COLUMNS:
        assert col in row, f"missing ablation-table column {col!r} in derived-calculations row"


def test_ablation_table_columns_extended_additively_for_derived():
    for col in p3d.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_derived_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    sql_row = {"row_id": "xbrl_sql_path", "phase3_config_hash": "y" * 64}
    rows = [row0, sql_row]
    derived_row = p3d.build_derived_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, derived_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == sql_row
    assert updated[2]["row_id"] == "derived_calculations"


def test_upsert_row_refuses_to_overwrite_derived_row_with_different_hash():
    existing = p3d.build_derived_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3d.build_derived_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6",
                                     "crag_confidence", "rules_router", "metadata_prefilter", "xbrl_sql_path"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
