"""Task 2.11 - evaluation run logging audit.

Verifies the run-record schema/validation/persistence/security contract
using synthetic data only - no real retrieval, no real evaluation, no
model load, no GPU, no network. Reads real Task 2.4 split metadata
(read-only, already-frozen hashes) to confirm eval_set_version/
split_version/split hash availability without opening the protected
TEST question payload.

Writes results/phase_2_11_evaluation_run_logging.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from src.artifacts.versioning import ArtifactCompatibility, ArtifactCompatibilityError  # noqa: E402
from src.chunk.metadata_schema import CHUNK_SCHEMA_VERSION  # noqa: E402
from src.eval import run_logging as rl  # noqa: E402
from src.eval.evaluation_schema import VALID_SPLITS  # noqa: E402

RESULT_PATH = Path("results") / "phase_2_11_evaluation_run_logging.json"

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
GIT_SHA_STUB = "d" * 40


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def _synthetic_embedding_model(**overrides) -> dict:
    base = dict(model_repository="BAAI/bge-small-en-v1.5", model_revision="x" * 40, embedding_dimension=384,
                vector_dtype="float32", normalize_embeddings=True, identity_hash=HASH_A)
    base.update(overrides)
    return base


def _build(**overrides) -> rl.EvaluationRunRecord:
    kwargs = dict(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_B,
        embedding_model=_synthetic_embedding_model(), retrieval_config={"method": "vector", "top_k": 10},
        reranker_config={"enabled": False}, generation_model=None, split="dev",
        eval_set_version="phase2-v1", split_version="phase2-split-v1", metrics={"doc_recall@10": 0.97},
        index_identity_hash=HASH_C, git_state={"git_sha": GIT_SHA_STUB, "git_dirty": False},
    )
    kwargs.update(overrides)
    return rl.build_run_record(**kwargs)


def audit_schema() -> dict:
    return {
        "run_schema_version": rl.EVALUATION_RUN_SCHEMA_VERSION,
        "mandatory_field_count": len(rl.MANDATORY_ROADMAP_FIELDS),
        "mandatory_fields": list(rl.MANDATORY_ROADMAP_FIELDS),
    }


def audit_task_2_10_integration() -> dict:
    compat = ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_B,
                                    embedding_identity_hash=HASH_A, index_identity_hash=HASH_C,
                                    eval_set_version="phase2-v1")
    results = {}
    _build(artifact_compatibility=compat)
    results["compatible_snapshot_builds"] = "PASS"

    for name, bad_compat in (
        ("chunk_mismatch", ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_C,
                                                  embedding_identity_hash=HASH_A, index_identity_hash=HASH_C,
                                                  eval_set_version="phase2-v1")),
        ("embedding_mismatch", ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_B,
                                                      embedding_identity_hash=HASH_C, index_identity_hash=HASH_C,
                                                      eval_set_version="phase2-v1")),
        ("index_mismatch", ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_B,
                                                  embedding_identity_hash=HASH_A, index_identity_hash=HASH_B,
                                                  eval_set_version="phase2-v1")),
        ("eval_version_mismatch", ArtifactCompatibility(chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=HASH_B,
                                                         embedding_identity_hash=HASH_A, index_identity_hash=HASH_C,
                                                         eval_set_version="phase2-v2")),
    ):
        try:
            _build(artifact_compatibility=bad_compat)
            results[name] = "FAIL (no exception raised)"
        except ArtifactCompatibilityError:
            results[name] = "PASS"
    return results


def audit_secret_rejection() -> dict:
    results = {}
    cases = {
        "api_key": lambda: _build(retrieval_config={"api_key": "sk-x"}),
        "authorization": lambda: _build(retrieval_config={"nested": {"Authorization": "Bearer x"}}),
        "password": lambda: _build(reranker_config={"enabled": False, "password": "x"}),
        "token": lambda: _build(generation_model={"provider": "x", "model": "y", "access_token": "z"}),
    }
    for name, fn in cases.items():
        try:
            fn()
            results[name] = "FAIL (no exception raised)"
        except rl.RunLogValidationError:
            results[name] = "PASS"
    return results


def audit_tamper_detection() -> str:
    record = _build()
    data = record.to_dict()
    data["metrics"] = {"doc_recall@10": 0.01}
    try:
        rl.validate_run_record(data)
        return "FAIL (no exception raised)"
    except rl.RunRecordIntegrityError:
        return "PASS"


def audit_duplicate_run_id() -> str:
    with tempfile.TemporaryDirectory() as d:
        directory = Path(d)
        record = _build(run_id="33333333-3333-4333-8333-333333333333")
        rl.write_run_record(record, directory=directory)
        try:
            rl.write_run_record(record, directory=directory)
            return "FAIL (no exception raised)"
        except rl.RunRecordExistsError:
            return "PASS"


def audit_write_read_round_trip() -> str:
    with tempfile.TemporaryDirectory() as d:
        directory = Path(d)
        record = _build()
        path = rl.write_run_record(record, directory=directory)
        loaded = rl.load_run_record(path)
        return "PASS" if loaded == record else "FAIL"


def audit_tracked_path_behavior() -> dict:
    """Confirms results/eval_runs/*.json is actually trackable, not
    silently swallowed by .gitignore's results/* blanket rule. Uses
    `git add -n` (dry run) as the ground truth rather than
    `git check-ignore`'s exit code, since `check-ignore -v` reports the
    deciding pattern (0) even when that pattern is a negation - matching
    a `!pattern` line does not mean the path is ignored."""
    probe_dir = REPO_ROOT / "results" / "eval_runs"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe_path = probe_dir / "_gitignore_probe.json"
    probe_path.write_text("{}\n", encoding="utf-8")
    try:
        rel_path = probe_path.relative_to(REPO_ROOT).as_posix()
        out = subprocess.run(
            ["git", "add", "-n", str(probe_path)], cwd=REPO_ROOT, capture_output=True, text=True,
        )
        trackable = f"add '{rel_path}'" in out.stdout
    finally:
        probe_path.unlink(missing_ok=True)
    return {"directory": str(probe_dir.relative_to(REPO_ROOT)), "trackable": trackable}


def audit_eval_split_metadata() -> dict:
    dataset_summary = json.loads((REPO_ROOT / "results" / "phase_2_3_evaluation_dataset_summary.json").read_text(encoding="utf-8"))
    split_summary = json.loads((REPO_ROOT / "results" / "phase_2_4_split_summary.json").read_text(encoding="utf-8"))
    return {
        "eval_set_version": dataset_summary["eval_set_version"],
        "split_version": split_summary["split_version"],
        "dev_sha256_present": bool(split_summary.get("dev_sha256")),
        "ci_sha256_present": bool(split_summary.get("ci_sha256")),
        "test_sha256_present": bool(split_summary.get("test_sha256")),
        "test_payload_opened": False,
        "valid_splits": list(VALID_SPLITS),
    }


def audit_test_access_discipline() -> dict:
    con = duckdb.connect(str(REPO_ROOT / "artifacts" / "eval" / "eval.duckdb"), read_only=True)
    try:
        rows = con.execute("SELECT run_number FROM test_access_log").fetchall()
    finally:
        con.close()
    official_runs = sum(1 for (run_number,) in rows if run_number is not None)
    return {"official_test_runs_used": official_runs, "budget": 3}


def main() -> None:
    print("=== Task 2.11 evaluation run logging audit ===")

    schema = audit_schema()
    print(f"Run schema version: {schema['run_schema_version']}, mandatory fields: {schema['mandatory_field_count']}/11")

    integration = audit_task_2_10_integration()
    for name, outcome in integration.items():
        print(f"  {name}: {outcome}")
    if any(v != "PASS" for v in integration.values()):
        raise SystemExit(f"STOP: a Task 2.10 integration check did not behave as expected: {integration}")

    secrets = audit_secret_rejection()
    for name, outcome in secrets.items():
        print(f"  secret_rejection[{name}]: {outcome}")
    if any(v != "PASS" for v in secrets.values()):
        raise SystemExit(f"STOP: a secret-rejection check did not behave as expected: {secrets}")

    tamper = audit_tamper_detection()
    print(f"Tamper detection: {tamper}")
    if tamper != "PASS":
        raise SystemExit("STOP: tamper detection did not fire")

    duplicate = audit_duplicate_run_id()
    print(f"Duplicate run_id rejection: {duplicate}")
    if duplicate != "PASS":
        raise SystemExit("STOP: duplicate run_id was not rejected")

    round_trip = audit_write_read_round_trip()
    print(f"Write/read round trip: {round_trip}")
    if round_trip != "PASS":
        raise SystemExit("STOP: write/read round trip failed")

    tracked_path = audit_tracked_path_behavior()
    print(f"results/eval_runs/*.json trackable: {tracked_path['trackable']}")
    if not tracked_path["trackable"]:
        raise SystemExit(f"STOP: {tracked_path['directory']} is still git-ignored - fix .gitignore before proceeding")

    eval_meta = audit_eval_split_metadata()
    print(f"Eval set version: {eval_meta['eval_set_version']} / split {eval_meta['split_version']}")

    test_discipline = audit_test_access_discipline()
    print(f"Official TEST runs used: {test_discipline['official_test_runs_used']}/{test_discipline['budget']}")
    if test_discipline["official_test_runs_used"] != 0:
        raise SystemExit("STOP: official TEST runs consumed is not 0 - refusing to proceed")

    summary = {
        "run_schema_version": schema["run_schema_version"],
        "mandatory_field_count": schema["mandatory_field_count"],
        "mandatory_fields": schema["mandatory_fields"],
        "storage_contract": "results/eval_runs/<run_id>.json - one immutable file per run, create-once",
        "task_2_10_integration": integration,
        "artifact_compatibility_enforced": all(v == "PASS" for v in integration.values()),
        "eval_set_version": eval_meta["eval_set_version"],
        "split_version": eval_meta["split_version"],
        "test_payload_accessed": False,
        "official_test_runs_used": test_discipline["official_test_runs_used"],
        "secret_rejection_tests": secrets,
        "tamper_detection": tamper,
        "duplicate_run_id_detection": duplicate,
        "tracked_path_behavior": tracked_path,
        "real_experiment_runs_created": 0,
        "note": "No real SEC evaluation run was executed or logged - results/eval_runs/ is intentionally left empty until an honest future experiment exists (Section 42: an empty trusted ledger is better than a fake historical record).",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Written: {RESULT_PATH}")


if __name__ == "__main__":
    main()
