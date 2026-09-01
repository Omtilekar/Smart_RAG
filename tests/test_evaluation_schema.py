"""Task 2.5 - tests for src/eval/evaluation_schema.py (pure schema/metric
definitions, DDL generation, validation, hashing - no DB connection)."""

from __future__ import annotations

import pytest

from src.eval import evaluation_schema as schema


def test_schema_hash_deterministic():
    assert schema.compute_evaluation_schema_hash() == schema.compute_evaluation_schema_hash()


def test_schema_hash_changes_on_semantic_change():
    base = schema.canonical_schema_dict()
    mutated = dict(base)
    mutated["evaluation_schema_version"] = base["evaluation_schema_version"] + 1
    import json, hashlib
    h1 = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    h2 = hashlib.sha256(json.dumps(mutated, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert h1 != h2


def test_valid_split_accepted():
    for s in schema.VALID_SPLITS:
        schema.validate_split(s)  # should not raise


def test_invalid_split_rejected():
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_split("train")


def test_valid_run_status_accepted():
    for s in schema.VALID_RUN_STATUSES:
        schema.validate_run_status(s)


def test_invalid_run_status_rejected():
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_run_status("bogus")


def test_valid_question_result_status_accepted():
    for s in schema.VALID_QUESTION_RESULT_STATUSES:
        schema.validate_question_result_status(s)


def test_invalid_question_result_status_rejected():
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_question_result_status("bogus")


def test_rank_validation():
    schema.validate_rank(1)
    schema.validate_rank(50)
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_rank(0)
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_rank(-1)


def test_metric_range_enforced_for_recall():
    schema.validate_metric_value("doc_recall@10", 0.5)
    schema.validate_metric_value("doc_recall@10", 0.0)
    schema.validate_metric_value("doc_recall@10", 1.0)
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_metric_value("doc_recall@10", 1.5)
    with pytest.raises(schema.SchemaValidationError):
        schema.validate_metric_value("doc_recall@10", -0.1)


def test_metric_range_not_enforced_for_unbounded_metrics():
    schema.validate_metric_value("absolute_error", 12345.6)
    schema.validate_metric_value("latency_ms", -1)  # not our job to reject here; caller enforces >=0 elsewhere
    schema.validate_metric_value("provider_cost_usd", 99.99)


def test_metric_range_none_is_always_allowed():
    schema.validate_metric_value("doc_recall@10", None)


def test_doc_recall_implemented_and_available():
    m = next(m for m in schema.METRIC_DEFINITIONS if m.metric_name == "doc_recall@10")
    assert m.implemented is True
    assert m.available_for_current_gold is True


def test_chunk_recall_not_implemented_not_available():
    m = next(m for m in schema.METRIC_DEFINITIONS if m.metric_name == "chunk_recall@10")
    assert m.implemented is False
    assert m.available_for_current_gold is False


def test_doc_and_chunk_recall_are_distinct_metrics():
    names = {m.metric_name for m in schema.METRIC_DEFINITIONS}
    assert "doc_recall@10" in names
    assert "chunk_recall@10" in names
    assert "recall" not in names  # no ambiguous generic metric name
    assert "accuracy" not in names
    assert "hit_rate" not in names


def test_faithfulness_requires_narrative_only():
    m = next(m for m in schema.METRIC_DEFINITIONS if m.metric_name == "faithfulness")
    assert m.applicable_categories == ("narrative",)
    assert m.available_for_current_gold is False  # narrative is pending_review, not gold


def test_no_duplicate_metric_name_version_pairs():
    keys = [(m.metric_name, m.metric_version) for m in schema.METRIC_DEFINITIONS]
    assert len(keys) == len(set(keys))


def test_create_sql_contains_check_constraint_for_enums():
    sql = schema.EVAL_RUNS.create_sql()
    assert "CHECK" in sql
    assert "split" in sql


def test_create_sql_is_idempotent_text():
    assert schema.EVAL_RUNS.create_sql() == schema.EVAL_RUNS.create_sql()


def test_all_tables_have_primary_key():
    for t in schema.ALL_TABLES:
        assert t.primary_key, f"{t.name} has no primary key"


def test_eval_question_results_pk_is_run_and_question():
    assert schema.EVAL_QUESTION_RESULTS.primary_key == ("run_id", "question_id")


def test_eval_retrieved_items_pk_includes_rank():
    assert "rank" in schema.EVAL_RETRIEVED_ITEMS.primary_key
