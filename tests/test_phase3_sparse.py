"""Task 3.4 - portable, pure-logic tests for src.eval.phase3_sparse and
its interaction with the shared src.eval.phase3_baseline/phase3_ablation
freeze mechanisms. No I/O, no LanceDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_ablation as p3a
from src.eval import phase3_sparse as p3s

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------- config hash

def test_sparse_config_hash_is_deterministic():
    config = {"a": 1, "b": [1, 2, 3]}
    assert p3s.compute_sparse_config_hash(config) == p3s.compute_sparse_config_hash(config)


def test_sparse_config_hash_changes_with_indexed_column():
    base = {"indexed_column": "text", "sparse_backend": "lancedb_native_fts"}
    changed = {"indexed_column": "body", "sparse_backend": "lancedb_native_fts"}
    assert p3s.compute_sparse_config_hash(base) != p3s.compute_sparse_config_hash(changed)


def test_sparse_config_hash_changes_with_backend():
    base = {"sparse_backend": "lancedb_native_fts"}
    changed = {"sparse_backend": "elasticsearch"}
    assert p3s.compute_sparse_config_hash(base) != p3s.compute_sparse_config_hash(changed)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_4_bm25_fts_baseline.json").read_text(encoding="utf-8"))
    assert config["chunk_config_hash"] == "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
    assert config["window_size_tokens"] == 256
    assert config["overlap_tokens"] == 0
    assert config["candidate_k"] == 50
    assert config["generation_enabled"] is False
    assert config["reranker_enabled"] is False
    assert config["metadata_prefilter_enabled"] is False
    assert config["sparse_backend"] == "lancedb_native_fts"
    assert config["question_count"] == 89


# --------------------------------------------------------------- complementarity

@pytest.mark.parametrize("dense_hit,sparse_hit,expected", [
    (True, True, "both"),
    (True, False, "dense_only"),
    (False, True, "sparse_only"),
    (False, False, "neither"),
])
def test_classify_hit_complementarity(dense_hit, sparse_hit, expected):
    assert p3s.classify_hit_complementarity(dense_hit, sparse_hit) == expected


def test_complementarity_table_counts_and_ids():
    dense = {"q1": {"hit10": True}, "q2": {"hit10": True}, "q3": {"hit10": False}, "q4": {"hit10": False}}
    sparse = {"q1": {"hit10": True}, "q2": {"hit10": False}, "q3": {"hit10": True}, "q4": {"hit10": False}}
    table = p3s.complementarity_table(dense, sparse, ["q1", "q2", "q3", "q4"], hit_field="hit10")
    assert table["both"] == 1
    assert table["dense_only"] == 1
    assert table["sparse_only"] == 1
    assert table["neither"] == 1
    assert table["dense_only_question_ids"] == ["q2"]
    assert table["sparse_only_question_ids"] == ["q3"]


def test_complementarity_table_raises_on_missing_question_id():
    with pytest.raises(p3s.Phase3SparseError):
        p3s.complementarity_table({"q1": {"hit10": True}}, {}, ["q1"], hit_field="hit10")


# --------------------------------------------------------------- first-hit-rank comparison

@pytest.mark.parametrize("dense_rank,sparse_rank,expected", [
    (1, 2, "dense_better"),
    (5, 1, "sparse_better"),
    (3, 3, "same"),
    (None, None, "same"),
    (None, 4, "sparse_better"),
    (4, None, "dense_better"),
])
def test_first_hit_rank_comparison(dense_rank, sparse_rank, expected):
    assert p3s.first_hit_rank_comparison(dense_rank, sparse_rank) == expected


def test_first_hit_rank_comparison_counts_aggregates_correctly():
    dense = {"q1": {"rank10": 1}, "q2": {"rank10": None}, "q3": {"rank10": 2}}
    sparse = {"q1": {"rank10": 2}, "q2": {"rank10": 1}, "q3": {"rank10": 2}}
    counts = p3s.first_hit_rank_comparison_counts(dense, sparse, ["q1", "q2", "q3"], rank_field="rank10")
    # q1: dense=1, sparse=2 -> dense_better; q2: dense=None, sparse=1 -> sparse_better; q3: 2==2 -> same
    assert counts == {"sparse_better": 1, "dense_better": 1, "same": 1}


# --------------------------------------------------------------- ablation row

def _sample_row_kwargs(row_id="bm25_fts", config_hash="c" * 64):
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, question_count=89, corpus_document_count=100,
        chunk_count=323971, chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, sparse_index_identity_hash_value="f" * 64,
        candidate_k=50, metrics={"doc_recall_at_10": 0.5, "doc_recall_at_50": 0.6, "doc_mrr": 0.4, "doc_ndcg_at_10": 0.45},
        deltas={"recall10": -0.1, "recall50": -0.2, "mrr": -0.3, "ndcg10": -0.25},
        complementarity10={"both": 1, "dense_only": 2, "sparse_only": 3, "neither": 4},
        complementarity50={"both": 5, "dense_only": 6, "sparse_only": 7, "neither": 8},
        lancedb_version="0.37.1", fts_indexed_column="text", fts_build_seconds=12.3, fts_index_size_bytes=1000,
        retrieval_latency_p50_ms=5.0, retrieval_latency_p95_ms=10.0, notes="test row",
    )


def test_build_sparse_ablation_row_shape_and_flags():
    row = p3s.build_sparse_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is False
    assert row["retrieval_mode"] == "sparse_only"
    assert row["sparse_backend"] == "lancedb_native_fts"
    assert row["precision_at_5"] == p3.NA
    assert row["refusal_metric"] == p3.NA
    assert row["dense_only_hits_at_10"] == 2
    assert row["sparse_only_hits_at_10"] == 3
    assert row["dense_only_hits_at_50"] == 6
    assert row["sparse_only_hits_at_50"] == 7
    assert row["delta_vs_qwen_dense_mrr"] == -0.3
    # Every column Task 3.4 itself owns must be present. Later columns added
    # additively by Task 3.5/3.6/3.7 (hybrid-only/rerank-only/CRAG-only
    # fields) are correctly absent here - `_row_to_csv_dict()` defaults
    # them to NA when writing this row to CSV.
    later_task_columns = (
        set(p3.ABLATION_TABLE_HYBRID_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_RERANK_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_CRAG_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_ROUTER_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_FILTER_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_SQL_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_NAV_EXTRA_COLUMNS)
    )
    for col in set(p3.ABLATION_TABLE_COLUMNS) - later_task_columns:
        assert col in row, f"missing ablation-table column {col!r} in sparse row"


def test_na_is_not_zero():
    row = p3s.build_sparse_ablation_row(**_sample_row_kwargs())
    assert row["precision_at_5"] != 0
    assert row["precision_at_5"] == "N/A"


# --------------------------------------------------------------- ablation table columns / freeze mechanism

def test_ablation_table_columns_extended_additively():
    for col in p3s.SPARSE_ABLATION_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS
    # base (pre-Task-3.4) columns still present and in original relative order
    base = ["row_id", "configuration", "status", "doc_recall_at_10", "notes"]
    positions = [p3.ABLATION_TABLE_COLUMNS.index(c) for c in base]
    assert positions == sorted(positions)


def test_upsert_row_appends_new_sparse_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64, "doc_recall_at_10": 0.9}
    rows = [row0]
    sparse_row = p3s.build_sparse_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, sparse_row)
    assert len(updated) == 2
    assert updated[0] == row0  # untouched, byte-for-byte
    assert updated[1]["row_id"] == "bm25_fts"


def test_upsert_row_is_idempotent_for_identical_config_hash():
    sparse_row = p3s.build_sparse_ablation_row(**_sample_row_kwargs())
    rows = [sparse_row]
    updated = p3.upsert_row(rows, sparse_row)
    assert updated == rows


def test_upsert_row_refuses_to_overwrite_row_with_different_config_hash():
    existing = p3s.build_sparse_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3s.build_sparse_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


def test_row_zero_cannot_be_overwritten_with_different_hash():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    conflicting_row0 = {"row_id": 0, "phase3_config_hash": "y" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([row0], conflicting_row0)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding"])
def test_prior_task_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


# --------------------------------------------------------------- scope / split guards (reused, not reimplemented)

def test_frozen_scope_mismatch_is_rejected():
    with pytest.raises(p3a.Phase3AblationError):
        p3a.assert_frozen_scope(["q1", "q2"], ["q1", "q3"])


def test_frozen_scope_exact_match_passes():
    p3a.assert_frozen_scope(["q1", "q2"], ["q2", "q1"])


def test_test_split_is_rejected():
    with pytest.raises(p3a.Phase3AblationError):
        p3a.assert_dev_split("test")


def test_dev_split_is_accepted():
    p3a.assert_dev_split("dev")


# --------------------------------------------------------------- bootstrap determinism (reused, not reimplemented)

def test_paired_bootstrap_deterministic_with_seed_42():
    cand = [1.0, 0.0, 1.0, 1.0, 0.0]
    base = [0.0, 0.0, 1.0, 0.0, 0.0]
    r1 = p3a.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=1000)
    r2 = p3a.paired_bootstrap_delta_ci(cand, base, seed=42, iterations=1000)
    assert r1.ci_lo == r2.ci_lo
    assert r1.ci_hi == r2.ci_hi
    assert r1.point_estimate == r2.point_estimate
