"""Task 3.8 - portable, pure-logic tests for src.eval.phase3_router and
its interaction with the shared ablation-table freeze mechanisms. No
I/O, no LanceDB, no model, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval import phase3_baseline as p3
from src.eval import phase3_router as p3rt

REPO_ROOT = Path(__file__).resolve().parents[1]

CLASSES = ["xbrl_fact", "numeric_derived", "cross_entity", "unanswerable", "out_of_scope", "advice"]


def test_router_config_hash_deterministic():
    config = {"classifier": "rules_v1"}
    assert p3rt.compute_router_config_hash(config) == p3rt.compute_router_config_hash(config)


def test_frozen_config_file_matches_documented_contract():
    config = json.loads((REPO_ROOT / "configs" / "phase_3_8_rules_first_router.json").read_text(encoding="utf-8"))
    assert "xbrl_fact" in config["scope_decision"]
    assert config["generation_enabled"] is False


# --------------------------------------------------------------- confusion matrix

def test_confusion_matrix_hand_calculation():
    true_labels = ["a", "a", "b", "b", "b"]
    predicted = ["a", "b", "b", "b", "a"]
    confusion = p3rt.build_confusion_matrix(true_labels, predicted, ["a", "b"])
    assert confusion == {"a": {"a": 1, "b": 1}, "b": {"a": 1, "b": 2}}


def test_confusion_matrix_full_shape_even_with_zero_observations():
    confusion = p3rt.build_confusion_matrix(["a"], ["a"], ["a", "b", "c"])
    assert confusion == {"a": {"a": 1, "b": 0, "c": 0}, "b": {"a": 0, "b": 0, "c": 0}, "c": {"a": 0, "b": 0, "c": 0}}


def test_confusion_matrix_rejects_length_mismatch():
    with pytest.raises(p3rt.Phase3RouterError):
        p3rt.build_confusion_matrix(["a"], ["a", "b"], ["a", "b"])


def test_confusion_matrix_rejects_unknown_label():
    with pytest.raises(p3rt.Phase3RouterError):
        p3rt.build_confusion_matrix(["z"], ["a"], ["a", "b"])


# --------------------------------------------------------------- per-class metrics

def test_per_class_metrics_hand_calculation():
    # a: TP=1,FP=1(from b predicted a),FN=1(a predicted b) -> P=0.5,R=0.5,F1=0.5
    # b: TP=2,FP=1,FN=1 -> P=2/3,R=2/3,F1=2/3
    confusion = {"a": {"a": 1, "b": 1}, "b": {"a": 1, "b": 2}}
    metrics = p3rt.per_class_metrics(confusion, ["a", "b"])
    assert metrics["a"]["precision"] == pytest.approx(0.5)
    assert metrics["a"]["recall"] == pytest.approx(0.5)
    assert metrics["a"]["f1"] == pytest.approx(0.5)
    assert metrics["a"]["support"] == 2
    assert metrics["b"]["precision"] == pytest.approx(2 / 3)
    assert metrics["b"]["recall"] == pytest.approx(2 / 3)
    assert metrics["b"]["support"] == 3


def test_per_class_metrics_zero_denominator_gives_zero_not_error():
    confusion = {"a": {"a": 0, "b": 0}, "b": {"a": 0, "b": 0}}
    metrics = p3rt.per_class_metrics(confusion, ["a", "b"])
    assert metrics["a"]["precision"] == 0.0
    assert metrics["a"]["recall"] == 0.0
    assert metrics["a"]["f1"] == 0.0


def test_overall_accuracy_hand_calculation():
    confusion = {"a": {"a": 1, "b": 1}, "b": {"a": 1, "b": 2}}
    accuracy = p3rt.overall_accuracy(confusion, ["a", "b"])
    assert accuracy == {"value": pytest.approx(3 / 5), "numerator": 3, "denominator": 5}


def test_overall_accuracy_rejects_zero_observations():
    with pytest.raises(p3rt.Phase3RouterError):
        p3rt.overall_accuracy({"a": {"a": 0}}, ["a"])


def test_macro_f1_hand_calculation():
    per_class = {"a": {"f1": 0.5}, "b": {"f1": 1.0}}
    assert p3rt.macro_f1(per_class, ["a", "b"]) == pytest.approx(0.75)


def test_macro_f1_rejects_empty_classes():
    with pytest.raises(p3rt.Phase3RouterError):
        p3rt.macro_f1({}, [])


# --------------------------------------------------------------- ablation row / columns

def _sample_row_kwargs(row_id="rules_router", config_hash="c" * 64):
    return dict(
        row_id=row_id, config_hash=config_hash, run_id="00000000-0000-4000-8000-000000000000",
        git_sha="a" * 40, eval_scope_sha256="e" * 64, corpus_document_count=100, chunk_count=323971,
        chunk_config_hash="ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06",
        dense_repository="Qwen/Qwen3-Embedding-0.6B", dense_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        dense_embedding_identity_hash="d" * 64, dense_index_identity_hash="i" * 64,
        question_count=1932, gazetteer_size=1500, concept_registry_size=15,
        router_accuracy=0.85, router_macro_f1=0.7, notes="test row",
    )


def test_build_router_ablation_row_shape_and_flags():
    row = p3rt.build_router_ablation_row(**_sample_row_kwargs())
    assert row["dense_used_in_this_row"] is False
    assert row["router_accuracy"] == 0.85
    assert row["router_macro_f1"] == 0.7
    assert row["gazetteer_size"] == 1500
    assert row["doc_recall_at_10"] == p3.NA
    # Later columns added additively by Task 3.9 (filter-only fields) are
    # correctly absent here - `_row_to_csv_dict()` defaults them to NA.
    later_task_columns = (
        set(p3.ABLATION_TABLE_FILTER_EXTRA_COLUMNS) | set(p3.ABLATION_TABLE_SQL_EXTRA_COLUMNS)
        | set(p3.ABLATION_TABLE_DERIVED_EXTRA_COLUMNS)
    )
    for col in set(p3.ABLATION_TABLE_COLUMNS) - later_task_columns:
        assert col in row, f"missing ablation-table column {col!r} in router row"


def test_ablation_table_columns_extended_additively_for_router():
    for col in p3rt.ABLATION_TABLE_ROUTER_EXTRA_COLUMNS:
        assert col in p3.ABLATION_TABLE_COLUMNS


def test_upsert_row_appends_router_row_without_touching_existing_rows():
    row0 = {"row_id": 0, "phase3_config_hash": "x" * 64}
    crag_row = {"row_id": "crag_confidence", "phase3_config_hash": "y" * 64}
    rows = [row0, crag_row]
    router_row = p3rt.build_router_ablation_row(**_sample_row_kwargs())
    updated = p3.upsert_row(rows, router_row)
    assert len(updated) == 3
    assert updated[0] == row0
    assert updated[1] == crag_row
    assert updated[2]["row_id"] == "rules_router"


def test_upsert_row_refuses_to_overwrite_router_row_with_different_hash():
    existing = p3rt.build_router_ablation_row(**_sample_row_kwargs(config_hash="c" * 64))
    conflicting = p3rt.build_router_ablation_row(**_sample_row_kwargs(config_hash="d" * 64))
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)


@pytest.mark.parametrize("row_id", ["A1", "bge_small", "qwen3_embedding", "bm25_fts", "hybrid_rrf", "ce_minilm_l6", "crag_confidence"])
def test_prior_rows_cannot_be_rewritten_with_different_hash(row_id):
    existing = {"row_id": row_id, "phase3_config_hash": "x" * 64}
    conflicting = {"row_id": row_id, "phase3_config_hash": "z" * 64}
    with pytest.raises(p3.Phase3BaselineError):
        p3.upsert_row([existing], conflicting)
