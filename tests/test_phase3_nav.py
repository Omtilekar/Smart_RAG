"""Task 3.12 - portable, pure-logic tests for src.eval.phase3_nav and
its interaction with the shared ablation-table freeze mechanisms. No
I/O, no DuckDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_nav as p3n

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_nav_config_hash_deterministic():
    config = {"pipeline": "structural_navigation"}
    assert p3n.compute_nav_config_hash(config) == p3n.compute_nav_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_12_tree_section_navigation.json").read_text(encoding="utf-8"))
    assert config["generation_enabled"] is False
    assert "scope_decision" in config


def test_nav_rates_hand_calculation():
    rates = p3n.nav_rates(
        resolution_flags=[True, True, False, True],
        section_found_flags=[True, False, True],
        leak_flags=[False, False, False],
    )
    assert rates["filing_resolution_rate"] == {"value": pytest.approx(0.75), "numerator": 3, "denominator": 4}
    assert rates["section_found_rate"] == {"value": pytest.approx(2 / 3), "numerator": 2, "denominator": 3}
    assert rates["scope_leak_rate"] == {"value": 0.0, "numerator": 0, "denominator": 3}


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="tree_section_navigation", config_hash="c" * 64):
    rates = p3n.nav_rates(
        resolution_flags=[True] * 95 + [False] * 5,
        section_found_flags=[True] * 900 + [False] * 100,
        leak_flags=[False] * 900,
    )
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, corpus_document_count=1493, chunk_count=323971,
        chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        parsed_document_count=990, navigation_attempt_count=1000, rates=rates, notes="test row",
    )


def test_build_nav_ablation_row_shape_and_flags():
    row = p3n.build_nav_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is False
    assert row["nav_parsed_document_count"] == 990
    assert row["nav_navigation_attempt_count"] == 1000
    assert row["question_count"] == 1000
    assert row["doc_recall_at_10"] == p3.NA
    for col in p3.ABLATION_TABLE_COLUMNS:
        assert col in row, f"missing ablation-table column {col!r} in nav row"


def test_ablation_table_columns_extended_additively_for_nav():
    for col in p3n.ABLATION_TABLE_NAV_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_nav_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    derived_row = {"row_id": "derived_calculations", "phase3_config_hash": "y" * 64}
    rows = [row0, derived_row]
    nav_row = p3n.build_nav_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, nav_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == derived_row
    assert updated[2]["row_id"] == "tree_section_navigation"


def test_upsert_row_refuses_to_overwrite_nav_row_with_different_hash():
    existing = p3n.build_nav_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3n.build_nav_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6",
                                     "crag_confidence", "rules_router", "metadata_prefilter", "xbrl_sql_path",
                                     "derived_calculations"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
