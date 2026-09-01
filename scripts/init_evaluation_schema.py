"""Task 2.5 - safely initialize the Task 2.5 evaluation-schema tables in
the real `artifacts/eval/eval.duckdb`, created by Task 2.4 for
`test_access_log`.

Sequence (never skipped):

    1. copy the real DB to a temp location
    2. record the existing test_access_log rows exactly
    3. run initialize_schema() on the COPY, twice (idempotency check)
    4. run a synthetic CI-split evaluation run end-to-end on the COPY
       (never against the real DB - no fake evaluation evidence is ever
       written to artifacts/eval/eval.duckdb)
    5. only after all of the above passes, initialize_schema() on the
       REAL database
    6. verify test_access_log rows are byte-identical before/after
    7. write results/phase_2_5_evaluation_schema.json

No network, no LLM, no GPU. Does not call
`src.eval.test_access.load_test_set()` - this script consumes 0/3 TEST
evaluation runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from src.eval import eval_store as es  # noqa: E402
from src.eval import evaluation_schema as schema  # noqa: E402

REAL_DB_PATH = es.EVAL_DB_PATH
SCHEMA_SNAPSHOT_PATH = REPO_ROOT / "results" / "phase_2_5_evaluation_schema.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def read_test_access_rows(db_path: Path) -> list[tuple]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        if "test_access_log" not in tables:
            return []
        return con.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
    finally:
        con.close()


def run_synthetic_ci_evaluation(con: duckdb.DuckDBPyConnection) -> None:
    """A deterministic, fully synthetic run - never touches TEST, never
    touches real evaluation content."""
    run_id = es.start_run(
        con, split="ci", eval_set_version="phase2-v1", source_dataset_sha256="s" * 64,
        split_version="phase2-split-v1", split_assignment_sha256="a" * 64, question_set_sha256="q" * 64,
        question_count=2, expected_question_count=2, git_sha="synthetic",
    )
    es.record_question_result(con, run_id=run_id, question_id="synthetic-q1", category="numeric", status="success", latency_ms=10.0, exact_match=True)
    es.record_question_result(con, run_id=run_id, question_id="synthetic-q2", category="numeric", status="success", latency_ms=12.0, exact_match=False)
    es.record_retrieved_items(con, run_id=run_id, question_id="synthetic-q1", items=[
        {"rank": 1, "chunk_id": "chunk-1", "document_id": "doc-1", "cik": 1, "retrieval_score": 0.9},
        {"rank": 2, "chunk_id": "chunk-2", "document_id": "doc-1", "cik": 1, "retrieval_score": 0.7},
    ])
    es.record_stage_timing(con, run_id=run_id, question_id="synthetic-q1", stage="retrieval", latency_ms=4.0)
    es.record_stage_timing(con, run_id=run_id, question_id="synthetic-q1", stage="generation", latency_ms=6.0)
    es.record_metric(con, run_id=run_id, metric_name="doc_recall@10", metric_version="1.0", scope="overall", value=1.0, numerator=2, denominator=2)
    es.complete_run(con, run_id=run_id)
    run = es.get_run(con, run_id)
    assert run["status"] == "complete"


def main() -> None:
    if not REAL_DB_PATH.exists():
        print(f"STOP: expected existing eval.duckdb at {REAL_DB_PATH} (created by Task 2.4) - not found", file=sys.stderr)
        raise SystemExit(1)

    before_rows = read_test_access_rows(REAL_DB_PATH)
    print(f"real DB test_access_log rows before: {len(before_rows)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        copy_path = Path(tmpdir) / "eval_copy.duckdb"
        shutil.copyfile(REAL_DB_PATH, copy_path)

        copy_rows_before = read_test_access_rows(copy_path)
        assert copy_rows_before == before_rows, "copy diverged from real DB before migration"

        con = duckdb.connect(str(copy_path))
        try:
            es.initialize_schema(con)
            es.initialize_schema(con)  # idempotency check
            tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
            expected_tables = {t.name for t in schema.ALL_TABLES} | {"test_access_log"}
            missing = expected_tables - tables
            assert not missing, f"missing tables after migration: {missing}"

            copy_rows_after_init = con.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
            assert copy_rows_after_init == before_rows, "test_access_log rows changed during schema init on copy"

            run_synthetic_ci_evaluation(con)

            copy_rows_after_run = con.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
            assert copy_rows_after_run == before_rows, "test_access_log rows changed during synthetic run on copy"
        finally:
            con.close()

    print("copy-based migration test PASSED - initializing real database")

    real_con = duckdb.connect(str(REAL_DB_PATH))
    try:
        es.initialize_schema(real_con)
        es.initialize_schema(real_con)  # idempotency check on the real DB too
        after_rows = real_con.execute("SELECT * FROM test_access_log ORDER BY access_id").fetchall()
        assert after_rows == before_rows, "REAL test_access_log rows changed during migration - this must never happen"
        real_tables = {r[0] for r in real_con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    finally:
        real_con.close()

    print(f"real DB test_access_log rows after: {len(after_rows)} (unchanged: {after_rows == before_rows})")

    table_rows = {}
    for t in schema.ALL_TABLES:
        table_rows[t.name] = {
            "columns": [
                {"name": c.name, "type": c.sql_type, "nullable": c.nullable, "check": c.check} for c in t.columns
            ],
            "primary_key": list(t.primary_key),
        }

    snapshot = {
        "evaluation_schema_version": schema.EVALUATION_SCHEMA_VERSION,
        "evaluation_schema_hash": schema.compute_evaluation_schema_hash(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "database_path": "artifacts/eval/eval.duckdb",
        "tables": table_rows,
        "existing_tables_preserved": ["test_access_log"],
        "metric_definitions": schema.metric_definitions_rows(),
        "valid_splits": list(schema.VALID_SPLITS),
        "valid_run_statuses": list(schema.VALID_RUN_STATUSES),
        "valid_question_result_statuses": list(schema.VALID_QUESTION_RESULT_STATUSES),
        "valid_stages": list(schema.VALID_STAGES),
        "test_access_log_rows_preserved": len(after_rows),
    }
    SCHEMA_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEMA_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, indent=2) + "\n")

    print(f"evaluation_schema_hash={snapshot['evaluation_schema_hash']}")
    print(f"tables in real DB: {sorted(real_tables)}")
    print("Task 2.5 schema initialization complete")


if __name__ == "__main__":
    main()
