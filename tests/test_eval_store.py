"""Task 2.5 - tests for src/eval/eval_store.py. Portable tests use
in-memory/tmp_path DuckDB connections - never the real
artifacts/eval/eval.duckdb. A separate local_data-marked test performs a
controlled migration against a COPY of the real database."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pytest

from src.eval import eval_store as es
from src.eval import evaluation_schema as schema


@pytest.fixture
def con():
    connection = duckdb.connect(":memory:")
    es.initialize_schema(connection)
    yield connection
    connection.close()


def start(con, split="dev", **overrides):
    defaults = dict(
        split=split, eval_set_version="phase2-v1", source_dataset_sha256="a" * 64,
        split_version="phase2-split-v1", split_assignment_sha256="b" * 64,
        question_set_sha256="c" * 64, question_count=2, expected_question_count=2,
    )
    defaults.update(overrides)
    return es.start_run(con, **defaults)


# --------------------------------------------------------------- initialization

def test_fresh_db_initializes():
    c = duckdb.connect(":memory:")
    es.initialize_schema(c)
    tables = {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    expected = {t.name for t in schema.ALL_TABLES}
    assert expected <= tables


def test_initialization_twice_is_safe(con):
    es.initialize_schema(con)
    es.initialize_schema(con)  # should not raise or duplicate metadata rows
    count = con.execute("SELECT COUNT(*) FROM eval_schema_metadata").fetchone()[0]
    assert count == 1


def test_existing_test_access_log_preserved():
    c = duckdb.connect(":memory:")
    c.execute("CREATE TABLE test_access_log (access_id VARCHAR, kind VARCHAR)")
    c.execute("INSERT INTO test_access_log VALUES ('x1', 'build_validation')")
    es.initialize_schema(c)
    rows = c.execute("SELECT * FROM test_access_log").fetchall()
    assert rows == [("x1", "build_validation")]


def test_metric_definitions_seeded(con):
    count = con.execute("SELECT COUNT(*) FROM metric_definitions").fetchone()[0]
    assert count == len(schema.METRIC_DEFINITIONS)


def test_metric_definitions_resynced_on_reinit_without_duplicating(con):
    # Simulate a Task-2.6-style registry content update (implemented
    # flag changed) between two initialize_schema() calls on the SAME
    # database - the row must be updated in place, never duplicated,
    # and run-scoped eval_metrics rows must be untouched.
    con.execute(
        "UPDATE metric_definitions SET implemented = false WHERE metric_name = 'doc_recall@10'"
    )
    es.initialize_schema(con)  # should resync back to the real registry value
    row = con.execute(
        "SELECT implemented FROM metric_definitions WHERE metric_name = 'doc_recall@10'"
    ).fetchone()
    real_definition = next(m for m in schema.METRIC_DEFINITIONS if m.metric_name == "doc_recall@10")
    assert row[0] == real_definition.implemented
    count = con.execute(
        "SELECT COUNT(*) FROM metric_definitions WHERE metric_name = 'doc_recall@10'"
    ).fetchone()[0]
    assert count == 1  # never duplicated


# --------------------------------------------------------------- run lifecycle

def test_start_run_returns_unique_ids(con):
    r1 = start(con)
    r2 = start(con)
    assert r1 != r2


def test_complete_run(con):
    run_id = start(con)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    es.record_question_result(con, run_id=run_id, question_id="q2", category="numeric", status="success")
    es.complete_run(con, run_id=run_id)
    assert es.get_run(con, run_id)["status"] == "complete"


def test_fail_run(con):
    run_id = start(con)
    es.fail_run(con, run_id=run_id, error_type="retrieval_error", error_message="boom")
    run = es.get_run(con, run_id)
    assert run["status"] == "failed"
    assert run["error_type"] == "retrieval_error"


def test_cannot_complete_nonexistent_run(con):
    with pytest.raises(es.RunNotFoundError):
        es.complete_run(con, run_id="does-not-exist")


def test_cannot_write_to_completed_run(con):
    run_id = start(con, question_count=1, expected_question_count=1)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    es.complete_run(con, run_id=run_id)
    with pytest.raises(es.RunNotRunningError):
        es.record_question_result(con, run_id=run_id, question_id="q2", category="numeric", status="success")


def test_cannot_overwrite_completed_run_status(con):
    run_id = start(con, question_count=1, expected_question_count=1)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    es.complete_run(con, run_id=run_id)
    with pytest.raises(es.RunNotRunningError):
        es.fail_run(con, run_id=run_id, error_type="x", error_message="y")


# --------------------------------------------------------------- provenance

def test_required_provenance_enforced_missing_field_raises(con):
    with pytest.raises(TypeError):
        es.start_run(con, split="dev")  # missing required provenance kwargs


def test_valid_split_enforced(con):
    with pytest.raises(schema.SchemaValidationError):
        start(con, split="train")


def test_eval_set_identity_preserved(con):
    run_id = start(con, eval_set_version="phase2-v1", source_dataset_sha256="z" * 64)
    run = es.get_run(con, run_id)
    assert run["eval_set_version"] == "phase2-v1"
    assert run["source_dataset_sha256"] == "z" * 64


def test_config_hashes_preserved(con):
    run_id = start(con, chunk_config_hash="ch1", index_config_hash="ix1", retrieval_config_hash="rc1")
    run = es.get_run(con, run_id)
    assert run["chunk_config_hash"] == "ch1"
    assert run["index_config_hash"] == "ix1"
    assert run["retrieval_config_hash"] == "rc1"


def test_unknown_provenance_field_rejected(con):
    with pytest.raises(ValueError):
        start(con, not_a_real_field="x")


# --------------------------------------------------------------- question results

def test_one_row_per_run_question(con):
    run_id = start(con)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    count = con.execute("SELECT COUNT(*) FROM eval_question_results WHERE run_id=?", [run_id]).fetchone()[0]
    assert count == 1


def test_duplicate_run_question_rejected(con):
    run_id = start(con)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    with pytest.raises(es.DuplicateResultError):
        es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")


def test_unknown_run_rejected(con):
    with pytest.raises(es.RunNotFoundError):
        es.record_question_result(con, run_id="ghost", question_id="q1", category="numeric", status="success")


def test_valid_status_accepted(con):
    run_id = start(con)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="retrieval_error")


def test_invalid_status_rejected(con):
    run_id = start(con)
    with pytest.raises(schema.SchemaValidationError):
        es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="bogus")


# --------------------------------------------------------------- retrieval results

def test_rank_starts_at_one(con):
    run_id = start(con)
    with pytest.raises(schema.SchemaValidationError):
        es.record_retrieved_items(con, run_id=run_id, question_id="q1", items=[{"rank": 0, "chunk_id": "c"}])


def test_duplicate_rank_rejected(con):
    run_id = start(con)
    with pytest.raises(ValueError):
        es.record_retrieved_items(con, run_id=run_id, question_id="q1", items=[
            {"rank": 1, "chunk_id": "a"}, {"rank": 1, "chunk_id": "b"},
        ])


def test_document_chunk_ids_nullable(con):
    run_id = start(con)
    es.record_retrieved_items(con, run_id=run_id, question_id="q1", items=[{"rank": 1}])
    row = con.execute("SELECT chunk_id, document_id FROM eval_retrieved_items WHERE run_id=?", [run_id]).fetchone()
    assert row == (None, None)


def test_scores_retain_precision(con):
    run_id = start(con)
    es.record_retrieved_items(con, run_id=run_id, question_id="q1", items=[{"rank": 1, "retrieval_score": 0.123456789}])
    row = con.execute("SELECT retrieval_score FROM eval_retrieved_items WHERE run_id=?", [run_id]).fetchone()
    assert row[0] == pytest.approx(0.123456789)


# --------------------------------------------------------------- metrics

def test_metric_must_be_registered(con):
    run_id = start(con)
    with pytest.raises(ValueError):
        es.record_metric(con, run_id=run_id, metric_name="not_a_real_metric", metric_version="1.0", scope="overall", value=0.5)


def test_metric_version_required_and_checked(con):
    run_id = start(con)
    with pytest.raises(ValueError):
        es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="99.9", scope="overall", value=0.5)


def test_numerator_denominator_consistency(con):
    run_id = start(con)
    with pytest.raises(ValueError):
        es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", numerator=5, denominator=2)


def test_rate_range_validation(con):
    run_id = start(con)
    with pytest.raises(schema.SchemaValidationError):
        es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=2.0)


def test_non_applicable_metric_remains_absent(con):
    run_id = start(con, question_count=1, expected_question_count=1)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    row = con.execute("SELECT chunk_first_hit_rank FROM eval_question_results WHERE run_id=?", [run_id]).fetchone()
    assert row[0] is None  # never fabricated as 0


def test_duplicate_metric_scope_rejected(con):
    run_id = start(con)
    es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=0.5)
    with pytest.raises(es.DuplicateResultError):
        es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=0.6)


def test_metric_different_scope_allowed(con):
    run_id = start(con)
    es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=0.5)
    es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="category", category="numeric", value=0.6)


# --------------------------------------------------------------- doc vs chunk

def test_doc_metric_cannot_masquerade_as_chunk_metric(con):
    run_id = start(con)
    es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=0.9)
    row = con.execute(
        "SELECT m.level FROM metric_definitions m WHERE m.metric_name='doc_recall@10'"
    ).fetchone()
    assert row[0] == "document"


def test_chunk_metric_requires_available_gold_flag():
    m = next(m for m in schema.METRIC_DEFINITIONS if m.metric_name == "chunk_recall@10")
    assert m.available_for_current_gold is False


# --------------------------------------------------------------- CI

def test_ci_accepted_as_split(con):
    run_id = start(con, split="ci")
    assert es.get_run(con, run_id)["split"] == "ci"


def test_ci_marked_non_reportable_in_ci_golden_artifact():
    import json
    path = Path("results") / "phase_2_4_ci_golden.json"
    if not path.exists():
        pytest.skip("Task 2.4 CI golden artifact not present")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["reportable_benchmark"] is False


# --------------------------------------------------------------- TEST

def test_test_run_requires_access_linkage(con):
    with pytest.raises(es.TestAccessLinkageError):
        start(con, split="test")


def test_test_access_log_untouched_by_dev_run(con):
    con.execute("CREATE TABLE IF NOT EXISTS test_access_log (access_id VARCHAR, kind VARCHAR)")
    con.execute("INSERT INTO test_access_log VALUES ('preexisting', 'build_validation')")
    start(con, split="dev")
    rows = con.execute("SELECT * FROM test_access_log").fetchall()
    assert rows == [("preexisting", "build_validation")]


def test_no_fourth_run_budget_bypass_introduced(con):
    # eval_store never imports src.eval.test_access and never writes to
    # test_access_log itself - only src.eval.test_access owns that budget.
    import inspect
    from src.eval import eval_store as mod
    import_lines = [l.strip() for l in inspect.getsource(mod).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("test_access" in l for l in import_lines)
    assert "INSERT INTO test_access_log" not in inspect.getsource(mod)


# --------------------------------------------------------------- determinism

def test_same_schema_same_hash():
    assert schema.compute_evaluation_schema_hash() == schema.compute_evaluation_schema_hash()


# --------------------------------------------------------------- transactions

def test_partial_failure_cannot_leave_run_marked_complete(con):
    run_id = start(con, question_count=5, expected_question_count=5)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    with pytest.raises(es.RunCompletenessError):
        es.complete_run(con, run_id=run_id)
    assert es.get_run(con, run_id)["status"] == "running"


def test_explicit_partial_completion_marks_partial_not_complete(con):
    run_id = start(con, question_count=5, expected_question_count=5)
    es.record_question_result(con, run_id=run_id, question_id="q1", category="numeric", status="success")
    es.complete_run(con, run_id=run_id, partial=True)
    assert es.get_run(con, run_id)["status"] == "partial"


# --------------------------------------------------------------- real-DB migration (local_data)

@pytest.mark.local_data
def test_real_db_migration_on_copy(tmp_path):
    real_db = es.EVAL_DB_PATH
    if not real_db.exists():
        pytest.skip("real artifacts/eval/eval.duckdb not present")

    copy_path = tmp_path / "eval_copy.duckdb"
    shutil.copyfile(real_db, copy_path)

    before = duckdb.connect(str(copy_path), read_only=True)
    before_rows = before.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
    before.close()

    c = duckdb.connect(str(copy_path))
    try:
        es.initialize_schema(c)
        es.initialize_schema(c)  # idempotent
        after_rows = c.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
        assert after_rows == before_rows

        tables = {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        assert {t.name for t in schema.ALL_TABLES} <= tables

        # synthetic run on the COPY only
        run_id = es.start_run(
            c, split="ci", eval_set_version="phase2-v1", source_dataset_sha256="s" * 64,
            split_version="phase2-split-v1", split_assignment_sha256="a" * 64,
            question_set_sha256="q" * 64, question_count=1, expected_question_count=1,
        )
        es.record_question_result(c, run_id=run_id, question_id="synthetic-q", category="numeric", status="success")
        es.complete_run(c, run_id=run_id)

        final_access_rows = c.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
        assert final_access_rows == before_rows
    finally:
        c.close()


@pytest.mark.local_data
def test_real_db_has_task25_tables_and_preserved_access_log():
    real_db = es.EVAL_DB_PATH
    if not real_db.exists():
        pytest.skip("real artifacts/eval/eval.duckdb not present")
    con = duckdb.connect(str(real_db), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        if not ({t.name for t in schema.ALL_TABLES} <= tables):
            pytest.skip("Task 2.5 schema not yet initialized in real DB")
        assert "test_access_log" in tables
        eval_runs_count = con.execute("SELECT COUNT(*) FROM eval_runs").fetchone()[0]
        assert eval_runs_count == 0  # no fake evaluation runs ever written to the real DB
    finally:
        con.close()
