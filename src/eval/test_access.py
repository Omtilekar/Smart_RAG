"""Task 2.4 - controlled access to the frozen Phase 2 TEST benchmark.

TEST (`artifacts/eval/phase_2_4_test.json`, gitignored) is never read
directly by evaluation code. `load_test_set()` is the only sanctioned
entry point: it verifies the loaded file's hash against the frozen
manifest before returning anything, and it logs every access - including
this module's own construction-time validation - to `eval.duckdb`.

Two kinds of access exist:

    build_validation  - Task 2.4 construction/validation itself, plus any
                         future schema/hash check. Never counts toward the
                         run budget.
    evaluation_access  - a real model-evaluation pass against TEST. Capped
                         at `MAX_EVALUATION_RUNS` (3) for the project's
                         documented three-run policy (baseline+rerank,
                         router+CRAG, final) - see
                         `project_plan/PHASE2_DEV_TEST_SPLIT.md`. A fourth
                         run raises unless the caller passes
                         `allow_override=True` explicitly.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone

import duckdb

from src.storage import get_storage

_storage = get_storage()
TEST_PATH = _storage.artifacts_root / "eval" / "phase_2_4_test.json"
EVAL_DB_PATH = _storage.artifacts_root / "eval" / "eval.duckdb"
MANIFEST_PATH = _storage.results_root / "phase_2_4_split_manifest.json"

VALID_EVALUATION_PURPOSES = ("baseline_rerank", "router_crag", "final")
MAX_EVALUATION_RUNS = 3


class TestAccessError(RuntimeError):
    """Raised when TEST cannot be safely loaded (hash mismatch, run-budget
    exceeded, unknown purpose)."""


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_storage.repo_root, text=True
        ).strip()
    except Exception:
        return "unknown"


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS test_access_log (
            access_id VARCHAR,
            timestamp_utc VARCHAR,
            git_sha VARCHAR,
            eval_set_version VARCHAR,
            source_dataset_sha256 VARCHAR,
            split_version VARCHAR,
            test_sha256 VARCHAR,
            kind VARCHAR,
            purpose VARCHAR,
            run_number INTEGER
        )
        """
    )


def _open_db() -> duckdb.DuckDBPyConnection:
    EVAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(EVAL_DB_PATH))
    _ensure_schema(con)
    return con


def _load_manifest_header() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest["header"]


def count_evaluation_runs(con: duckdb.DuckDBPyConnection) -> int:
    row = con.execute("SELECT COUNT(*) FROM test_access_log WHERE kind = 'evaluation_access'").fetchone()
    return int(row[0])


def log_access(
    con: duckdb.DuckDBPyConnection,
    *,
    kind: str,
    purpose: str | None,
    eval_set_version: str,
    source_dataset_sha256: str,
    split_version: str,
    test_sha256: str,
    run_number: int | None,
) -> str:
    access_id = str(uuid.uuid4())
    con.execute(
        """
        INSERT INTO test_access_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            access_id,
            datetime.now(timezone.utc).isoformat(),
            _git_sha(),
            eval_set_version,
            source_dataset_sha256,
            split_version,
            test_sha256,
            kind,
            purpose,
            run_number,
        ],
    )
    return access_id


def record_build_validation(*, eval_set_version: str, source_dataset_sha256: str, split_version: str, test_sha256: str) -> str:
    """Logs Task 2.4's own construction/validation access. Never counts
    toward MAX_EVALUATION_RUNS."""
    con = _open_db()
    try:
        return log_access(
            con,
            kind="build_validation",
            purpose=None,
            eval_set_version=eval_set_version,
            source_dataset_sha256=source_dataset_sha256,
            split_version=split_version,
            test_sha256=test_sha256,
            run_number=None,
        )
    finally:
        con.close()


def load_test_set(purpose: str, *, allow_override: bool = False) -> list[dict]:
    """The only sanctioned way to read TEST. Verifies the on-disk file's
    hash against the tracked manifest, enforces the three-evaluation-run
    budget, and logs the access before returning any question content."""
    if purpose not in VALID_EVALUATION_PURPOSES:
        raise TestAccessError(f"unknown evaluation purpose {purpose!r}; expected one of {VALID_EVALUATION_PURPOSES}")

    header = _load_manifest_header()
    test_sha256 = header["test_sha256"]

    with open(TEST_PATH, encoding="utf-8") as f:
        test_payload = json.load(f)
    records = test_payload["questions"]
    actual = compute_test_sha256(records)
    if actual != test_sha256:
        raise TestAccessError(
            f"TEST file hash {actual} does not match frozen manifest hash {test_sha256} - refusing to load"
        )

    con = _open_db()
    try:
        already_run = count_evaluation_runs(con)
        if already_run >= MAX_EVALUATION_RUNS and not allow_override:
            raise TestAccessError(
                f"evaluation run budget exhausted ({already_run}/{MAX_EVALUATION_RUNS}); "
                "pass allow_override=True to proceed anyway"
            )
        run_number = already_run + 1
        log_access(
            con,
            kind="evaluation_access",
            purpose=purpose,
            eval_set_version=header["eval_set_version"],
            source_dataset_sha256=header["source_dataset_sha256"],
            split_version=header["split_version"],
            test_sha256=test_sha256,
            run_number=run_number,
        )
    finally:
        con.close()

    return records


def compute_test_sha256(records: list[dict]) -> str:
    from src.eval.evaluation_dataset import compute_dataset_sha256

    return compute_dataset_sha256(records)
