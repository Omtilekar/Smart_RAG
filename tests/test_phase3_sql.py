"""Task 3.10 - portable, pure-logic tests for src.eval.phase3_sql and
its interaction with the shared ablation-table freeze mechanisms. No
I/O, no DuckDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_sql as p3s

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sql_config_hash_deterministic():
    config = {"tags_indexed": ["Assets"]}
    assert p3s.compute_sql_config_hash(config) == p3s.compute_sql_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_10_xbrl_sql_path.json").read_text(encoding="utf-8"))
    assert "Assets" in config["tags_indexed"]
    assert config["generation_enabled"] is False


# --------------------------------------------------------------- rates

def test_sql_rates_hand_calculation():
    rates = p3s.sql_rates(
        attempted_flags=[True, True, False, True],       # 3/4
        found_flags=[True, False, True],                 # 2/3 (over attempted only)
        exact_match_flags=[True, False],                 # 1/2 (over found only)
        trap_leak_flags=[False, False, False],            # 0/3
    )
    assert rates["routing_coverage"] == {"value": pytest.approx(0.75), "numerator": 3, "denominator": 4}
    assert rates["sql_found_rate"] == {"value": pytest.approx(2 / 3), "numerator": 2, "denominator": 3}
    assert rates["sql_exact_match_rate"] == {"value": pytest.approx(0.5), "numerator": 1, "denominator": 2}
    assert rates["trap_leak_rate"] == {"value": 0.0, "numerator": 0, "denominator": 3}


def test_sql_rates_perfect_safety():
    rates = p3s.sql_rates(
        attempted_flags=[True] * 5, found_flags=[True] * 5, exact_match_flags=[True] * 5,
        trap_leak_flags=[False] * 10,
    )
    assert rates["trap_leak_rate"]["value"] == 0.0


def test_sql_rates_detects_a_leak():
    rates = p3s.sql_rates(
        attempted_flags=[True], found_flags=[True], exact_match_flags=[True],
        trap_leak_flags=[False, True, False],
    )
    assert rates["trap_leak_rate"]["value"] == pytest.approx(1 / 3)
    assert rates["trap_leak_rate"]["numerator"] == 1


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="xbrl_sql_path", config_hash="c" * 64):
    rates = p3s.sql_rates(
        attempted_flags=[True] * 1000 + [False] * 402, found_flags=[True] * 950 + [False] * 50,
        exact_match_flags=[True] * 900 + [False] * 50, trap_leak_flags=[False] * 139,
    )
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, corpus_document_count=100, chunk_count=323971,
        chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        xbrl_fact_question_count=1402, trap_question_count=139, rates=rates, notes="test row",
    )


def test_build_sql_ablation_row_shape_and_flags():
    row = p3s.build_sql_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is False
    assert row["xbrl_fact_question_count"] == 1402
    assert row["trap_question_count"] == 139
    assert row["trap_leak_rate"] == 0.0
    assert row["doc_recall_at_10"] == p3.NA
    # Later columns added additively by Task 3.11 (derived-calculation-only
    # fields) are correctly absent here - `_row_to_csv_dict()` defaults
    # them to NA.
    for col in set(p3.ABLATION_TABLE_COLUMNS) - set(p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS):
        assert col in row, f"missing ablation-table column {col!r} in SQL row"


def test_ablation_table_columns_extended_additively_for_sql():
    for col in p3s.ABLATION_TABLE_SQL_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_sql_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    filter_row = {"row_id": "metadata_prefilter", "phase3_config_hash": "y" * 64}
    rows = [row0, filter_row]
    sql_row = p3s.build_sql_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, sql_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == filter_row
    assert updated[2]["row_id"] == "xbrl_sql_path"


def test_upsert_row_refuses_to_overwrite_sql_row_with_different_hash():
    existing = p3s.build_sql_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3s.build_sql_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6",
                                     "crag_confidence", "rules_router", "metadata_prefilter"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
