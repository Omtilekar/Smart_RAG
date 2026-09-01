"""Task 2.5 - the authoritative evaluation-result storage API.

Every later Phase 3+ retrieval/generation/router/CRAG/reranking
experiment must persist its results through this module, never through
ad-hoc SQL scattered across scripts. `initialize_schema()` safely extends
`artifacts/eval/eval.duckdb` (created by Task 2.4 for `test_access_log`)
with the Task 2.5 tables - it is idempotent and never touches
`test_access_log`.

Run lifecycle:

    start_run(...)               -> status="running", writes eval_runs row
    record_question_result(...)  -> one row per (run_id, question_id)
    record_retrieved_items(...)  -> ranked candidates for one question
    record_metric(...)           -> one aggregate metric observation
    record_stage_timing(...)     -> one per-question per-stage latency
    complete_run(...)            -> validates persisted count, status="complete"
    fail_run(...)                -> status="failed", records error_type/message

A run that crashes mid-write without either complete_run() or
fail_run() being called stays status="running" forever - this is
deliberate (Section 39/43): it is never silently reported as complete,
and its provenance/question rows remain exactly as far as they got,
available for post-mortem inspection. There is no automatic "mark stale
running runs as failed" sweep in this module - see
project_plan/PHASE2_EVALUATION_SCHEMA.md's migration/immutability policy
section for why that is a deliberate scope boundary, not an oversight.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import duckdb

from src.eval import evaluation_schema as schema
from src.storage import get_storage

_storage = get_storage()
EVAL_DB_PATH = _storage.artifacts_root / "eval" / "eval.duckdb"


class RunNotFoundError(ValueError):
    pass


class RunNotRunningError(ValueError):
    """Raised when attempting to write to, complete, or fail a run that
    is not currently status='running' - completed runs are immutable
    (Section 43)."""


class DuplicateResultError(ValueError):
    pass


class RunCompletenessError(ValueError):
    """Raised by complete_run() when the persisted question-result count
    does not match expected_question_count and partial=False."""


class TestAccessLinkageError(ValueError):
    """Raised when a split='test' run is started without a valid,
    already-logged test_access_log evaluation_access reference."""


def connect(db_path=None) -> duckdb.DuckDBPyConnection:
    path = db_path or EVAL_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def initialize_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Idempotent: creates every Task 2.5 table if missing, never touches
    test_access_log, never drops/recreates an existing table."""
    for table in schema.ALL_TABLES:
        con.execute(table.create_sql())

    existing_version = con.execute(
        "SELECT schema_version FROM eval_schema_metadata WHERE schema_version = ?",
        [schema.EVALUATION_SCHEMA_VERSION],
    ).fetchone()
    if existing_version is None:
        con.execute(
            "INSERT INTO eval_schema_metadata VALUES (?, ?, ?)",
            [schema.EVALUATION_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(), 1],
        )

    for row in schema.metric_definitions_rows():
        existing = con.execute(
            "SELECT level, description, higher_is_better, required_gold_type, applicable_categories, "
            "parameters, implemented, available_for_current_gold FROM metric_definitions "
            "WHERE metric_name = ? AND metric_version = ?",
            [row["metric_name"], row["metric_version"]],
        ).fetchone()
        values = [
            row["metric_name"], row["metric_version"], row["level"], row["description"],
            row["higher_is_better"], row["required_gold_type"], row["applicable_categories"],
            row["parameters"], row["implemented"], row["available_for_current_gold"],
        ]
        if existing is None:
            con.execute("INSERT INTO metric_definitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
        elif tuple(existing) != tuple(values[2:]):
            # Registry metadata (implemented/available_for_current_gold/
            # description/...) is code-owned and safely re-synced on
            # every initialize_schema() call - this never touches
            # run-scoped evidence (eval_metrics), only the shared
            # definitions table, and the metric_name+metric_version
            # identity (the actual formula/semantics contract) never
            # changes here.
            con.execute(
                "UPDATE metric_definitions SET level=?, description=?, higher_is_better=?, "
                "required_gold_type=?, applicable_categories=?, parameters=?, implemented=?, "
                "available_for_current_gold=? WHERE metric_name=? AND metric_version=?",
                values[2:] + [row["metric_name"], row["metric_version"]],
            )


def start_run(
    con: duckdb.DuckDBPyConnection,
    *,
    split: str,
    eval_set_version: str,
    source_dataset_sha256: str,
    split_version: str,
    split_assignment_sha256: str,
    question_set_sha256: str,
    question_count: int,
    expected_question_count: int,
    git_sha: str | None = None,
    test_access_id: str | None = None,
    **provenance,
) -> str:
    schema.validate_split(split)
    if split == "test":
        if not test_access_id:
            raise TestAccessLinkageError("split='test' requires a test_access_id from src.eval.test_access.load_test_set()")
        row = con.execute(
            "SELECT 1 FROM test_access_log WHERE access_id = ? AND kind = 'evaluation_access'",
            [test_access_id],
        ).fetchone()
        if row is None:
            raise TestAccessLinkageError(
                f"test_access_id {test_access_id!r} does not reference a logged evaluation_access row"
            )

    run_id = str(uuid.uuid4())
    known_fields = {c.name for c in schema.EVAL_RUNS.columns}
    extra_fields = {
        "git_sha": git_sha, "test_access_id": test_access_id,
        "chunk_config_hash": None, "index_config_hash": None, "retrieval_config_hash": None,
        "embed_model": None, "embed_model_revision": None,
        "rerank_model": None, "rerank_model_revision": None, "rerank_config_hash": None, "rerank_k": None,
        "generation_provider": None, "generation_requested_model": None, "generation_response_model": None,
        "generation_prompt_version": None, "generation_temperature": None,
        "router_version": None, "router_config_hash": None, "crag_enabled": None, "crag_config_hash": None,
        "error_type": None, "error_message": None, "completed_at_utc": None,
    }
    extra_fields.update(provenance)
    unknown = set(provenance) - known_fields
    if unknown:
        raise ValueError(f"unknown eval_runs provenance field(s): {sorted(unknown)}")

    values = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "eval_set_version": eval_set_version,
        "source_dataset_sha256": source_dataset_sha256,
        "split_version": split_version,
        "split_assignment_sha256": split_assignment_sha256,
        "question_set_sha256": question_set_sha256,
        "question_count": question_count,
        "expected_question_count": expected_question_count,
        "metric_schema_version": schema.EVALUATION_SCHEMA_VERSION,
        "status": "running",
        **extra_fields,
    }
    columns = [c.name for c in schema.EVAL_RUNS.columns]
    ordered_values = [values.get(c) for c in columns]
    placeholders = ", ".join("?" for _ in columns)
    con.execute(f"INSERT INTO eval_runs ({', '.join(columns)}) VALUES ({placeholders})", ordered_values)
    return run_id


def _get_run_status(con: duckdb.DuckDBPyConnection, run_id: str) -> str:
    row = con.execute("SELECT status FROM eval_runs WHERE run_id = ?", [run_id]).fetchone()
    if row is None:
        raise RunNotFoundError(f"no such run_id {run_id!r}")
    return row[0]


def _require_running(con: duckdb.DuckDBPyConnection, run_id: str) -> None:
    status = _get_run_status(con, run_id)
    if status != "running":
        raise RunNotRunningError(f"run {run_id!r} is status={status!r}, not 'running' - completed/failed runs are immutable")


def record_question_result(con: duckdb.DuckDBPyConnection, *, run_id: str, question_id: str, category: str, status: str, **fields) -> None:
    schema.validate_question_result_status(status)
    _require_running(con, run_id)
    known_fields = {c.name for c in schema.EVAL_QUESTION_RESULTS.columns}
    unknown = set(fields) - known_fields
    if unknown:
        raise ValueError(f"unknown eval_question_results field(s): {sorted(unknown)}")
    values = {"run_id": run_id, "question_id": question_id, "category": category, "status": status, **fields}
    columns = [c.name for c in schema.EVAL_QUESTION_RESULTS.columns]
    ordered_values = [values.get(c) for c in columns]
    placeholders = ", ".join("?" for _ in columns)
    existing = con.execute(
        "SELECT 1 FROM eval_question_results WHERE run_id = ? AND question_id = ?", [run_id, question_id]
    ).fetchone()
    if existing is not None:
        raise DuplicateResultError(f"result already recorded for run_id={run_id!r} question_id={question_id!r}")
    con.execute(f"INSERT INTO eval_question_results ({', '.join(columns)}) VALUES ({placeholders})", ordered_values)


def record_retrieved_items(con: duckdb.DuckDBPyConnection, *, run_id: str, question_id: str, items: list[dict]) -> None:
    _require_running(con, run_id)
    seen_ranks: set[int] = set()
    for item in items:
        rank = item["rank"]
        schema.validate_rank(rank)
        if rank in seen_ranks:
            raise ValueError(f"duplicate rank {rank} for run_id={run_id!r} question_id={question_id!r}")
        seen_ranks.add(rank)

    known_fields = {c.name for c in schema.EVAL_RETRIEVED_ITEMS.columns}
    columns = [c.name for c in schema.EVAL_RETRIEVED_ITEMS.columns]
    for item in items:
        unknown = set(item) - known_fields - {"run_id", "question_id"}
        if unknown:
            raise ValueError(f"unknown eval_retrieved_items field(s): {sorted(unknown)}")
        values = {"run_id": run_id, "question_id": question_id, **item}
        ordered_values = [values.get(c) for c in columns]
        placeholders = ", ".join("?" for _ in columns)
        con.execute(f"INSERT INTO eval_retrieved_items ({', '.join(columns)}) VALUES ({placeholders})", ordered_values)


def record_metric(
    con: duckdb.DuckDBPyConnection, *, run_id: str, metric_name: str, metric_version: str, scope: str,
    value: float | None = None, numerator: int | None = None, denominator: int | None = None,
    category: str | None = None, subtype: str | None = None, tag: str | None = None,
    year: int | None = None, intent: str | None = None, k: int | None = None, notes: str | None = None,
) -> str:
    if scope not in ("overall", "category", "subtype", "tag", "year", "intent"):
        raise ValueError(f"invalid metric scope {scope!r}")
    schema.validate_metric_value(metric_name, value)
    definition = con.execute(
        "SELECT 1 FROM metric_definitions WHERE metric_name = ? AND metric_version = ?", [metric_name, metric_version]
    ).fetchone()
    if definition is None:
        raise ValueError(f"metric {metric_name!r} version {metric_version!r} is not registered in metric_definitions")
    if numerator is not None and denominator is not None:
        if denominator < 0 or numerator < 0 or numerator > denominator:
            raise ValueError(f"invalid numerator/denominator: {numerator}/{denominator}")

    existing = con.execute(
        """
        SELECT 1 FROM eval_metrics
        WHERE run_id = ? AND metric_name = ? AND metric_version = ? AND scope = ?
          AND category IS NOT DISTINCT FROM ? AND subtype IS NOT DISTINCT FROM ?
          AND tag IS NOT DISTINCT FROM ? AND year IS NOT DISTINCT FROM ? AND intent IS NOT DISTINCT FROM ?
          AND k IS NOT DISTINCT FROM ?
        """,
        [run_id, metric_name, metric_version, scope, category, subtype, tag, year, intent, k],
    ).fetchone()
    if existing is not None:
        raise DuplicateResultError(f"metric {metric_name!r} already recorded for this run/scope/dimension/k combination")

    metric_id = str(uuid.uuid4())
    con.execute(
        "INSERT INTO eval_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [metric_id, run_id, metric_name, metric_version, scope, category, subtype, tag, year, intent, k, value, numerator, denominator, notes],
    )
    return metric_id


def record_stage_timing(con: duckdb.DuckDBPyConnection, *, run_id: str, question_id: str, stage: str, latency_ms: float) -> None:
    schema.validate_stage(stage)
    if latency_ms < 0:
        raise ValueError(f"latency_ms must be >= 0, got {latency_ms!r}")
    _require_running(con, run_id)
    existing = con.execute(
        "SELECT 1 FROM eval_stage_timings WHERE run_id = ? AND question_id = ? AND stage = ?",
        [run_id, question_id, stage],
    ).fetchone()
    if existing is not None:
        raise DuplicateResultError(f"stage timing already recorded for run_id={run_id!r} question_id={question_id!r} stage={stage!r}")
    con.execute("INSERT INTO eval_stage_timings VALUES (?, ?, ?, ?)", [run_id, question_id, stage, latency_ms])


def complete_run(con: duckdb.DuckDBPyConnection, *, run_id: str, partial: bool = False) -> None:
    _require_running(con, run_id)
    row = con.execute("SELECT expected_question_count FROM eval_runs WHERE run_id = ?", [run_id]).fetchone()
    expected = row[0]
    actual = con.execute("SELECT COUNT(*) FROM eval_question_results WHERE run_id = ?", [run_id]).fetchone()[0]
    if actual != expected and not partial:
        raise RunCompletenessError(
            f"run {run_id!r}: persisted {actual} question results, expected {expected} - "
            "pass partial=True to explicitly complete an incomplete run"
        )
    status = "partial" if actual != expected else "complete"
    con.execute(
        "UPDATE eval_runs SET status = ?, completed_at_utc = ? WHERE run_id = ?",
        [status, datetime.now(timezone.utc).isoformat(), run_id],
    )


def fail_run(con: duckdb.DuckDBPyConnection, *, run_id: str, error_type: str, error_message: str) -> None:
    _require_running(con, run_id)
    con.execute(
        "UPDATE eval_runs SET status = 'failed', error_type = ?, error_message = ?, completed_at_utc = ? WHERE run_id = ?",
        [error_type, error_message, datetime.now(timezone.utc).isoformat(), run_id],
    )


def get_run(con: duckdb.DuckDBPyConnection, run_id: str) -> dict:
    columns = [c.name for c in schema.EVAL_RUNS.columns]
    row = con.execute(f"SELECT {', '.join(columns)} FROM eval_runs WHERE run_id = ?", [run_id]).fetchone()
    if row is None:
        raise RunNotFoundError(f"no such run_id {run_id!r}")
    return dict(zip(columns, row))
