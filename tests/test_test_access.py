"""Task 2.4 - tests for src/eval/test_access.py, the controlled TEST-set
loader and access log. Uses monkeypatched paths pointed at tmp_path - never
touches the real artifacts/eval/eval.duckdb or the real TEST content."""

from __future__ import annotations

import json

import pytest

from src.eval import test_access as ta
from src.eval.evaluation_dataset import compute_dataset_sha256


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    test_path = tmp_path / "phase_2_4_test.json"
    db_path = tmp_path / "eval.duckdb"
    manifest_path = tmp_path / "phase_2_4_split_manifest.json"

    questions = [{"question_id": f"q{i}", "category": "numeric", "question": f"q-{i}"} for i in range(5)]
    test_sha256 = compute_dataset_sha256(questions)
    with open(test_path, "w", encoding="utf-8") as f:
        json.dump({"test_sha256": test_sha256, "questions": questions}, f)

    header = {
        "eval_set_version": "phase2-v1",
        "source_dataset_sha256": "s" * 64,
        "split_version": "phase2-split-v1",
        "test_sha256": test_sha256,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"header": header, "assignments": []}, f)

    monkeypatch.setattr(ta, "TEST_PATH", test_path)
    monkeypatch.setattr(ta, "EVAL_DB_PATH", db_path)
    monkeypatch.setattr(ta, "MANIFEST_PATH", manifest_path)
    return {"test_sha256": test_sha256, "questions": questions}


def test_load_test_set_valid_purpose_succeeds(sandbox):
    records = ta.load_test_set("baseline_rerank")
    assert records == sandbox["questions"]


def test_load_test_set_unknown_purpose_raises(sandbox):
    with pytest.raises(ta.TestAccessError):
        ta.load_test_set("not_a_real_purpose")


def test_load_test_set_hash_mismatch_raises(sandbox, tmp_path):
    corrupted = {"test_sha256": sandbox["test_sha256"], "questions": [{"question_id": "tampered", "category": "numeric", "question": "x"}]}
    with open(ta.TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(corrupted, f)
    with pytest.raises(ta.TestAccessError):
        ta.load_test_set("baseline_rerank")


def test_run_budget_enforced(sandbox):
    ta.load_test_set("baseline_rerank")
    ta.load_test_set("router_crag")
    ta.load_test_set("final")
    with pytest.raises(ta.TestAccessError):
        ta.load_test_set("final")


def test_run_budget_override_allows_fourth_run(sandbox):
    ta.load_test_set("baseline_rerank")
    ta.load_test_set("router_crag")
    ta.load_test_set("final")
    records = ta.load_test_set("final", allow_override=True)
    assert records == sandbox["questions"]


def test_build_validation_does_not_count_toward_budget(sandbox):
    ta.record_build_validation(
        eval_set_version="phase2-v1", source_dataset_sha256="s" * 64,
        split_version="phase2-split-v1", test_sha256=sandbox["test_sha256"],
    )
    ta.record_build_validation(
        eval_set_version="phase2-v1", source_dataset_sha256="s" * 64,
        split_version="phase2-split-v1", test_sha256=sandbox["test_sha256"],
    )
    ta.load_test_set("baseline_rerank")
    ta.load_test_set("router_crag")
    ta.load_test_set("final")
    # exactly 3 evaluation_access rows should have been logged despite the
    # 2 build_validation rows preceding them
    con = ta._open_db()
    try:
        assert ta.count_evaluation_runs(con) == 3
    finally:
        con.close()


def test_access_log_records_required_fields(sandbox):
    ta.load_test_set("baseline_rerank")
    con = ta._open_db()
    try:
        row = con.execute("SELECT * FROM test_access_log").fetchone()
    finally:
        con.close()
    assert row is not None
    # access_id, timestamp_utc, git_sha, eval_set_version, source_dataset_sha256,
    # split_version, test_sha256, kind, purpose, run_number
    assert row[7] == "evaluation_access"
    assert row[8] == "baseline_rerank"
    assert row[9] == 1
