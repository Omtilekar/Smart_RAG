"""Task 2.11 - reproducible evaluation run logging.

Central rule: "A metric without provenance is not an experiment result."

This module CONSUMES Task 2.10's identities; it never recomputes
chunk_config_hash/embedding identity/index identity independently
(`src.artifacts.versioning` owns canonical hashing and
`ArtifactCompatibility`/`assert_artifact_compatible`).

Relationship to `src.eval.eval_store` (Task 2.5): that module is a
local, GITIGNORED, DuckDB-backed experiment log
(`artifacts/eval/eval.duckdb`'s `eval_runs` table) built for iterative
local querying across many runs - it disappears if the local DuckDB file
is deleted and is never visible from a bare `git clone`. This module is
the complementary artifact: one small, individually IMMUTABLE, GIT-
TRACKED JSON record per execution, durable and citable indefinitely even
without the local DuckDB file. Task 2.11 does not modify
`src/eval/eval_store.py` or `src/eval/evaluation_schema.py`.

Task 2.10 answers: "Are these artifacts compatible?"
Task 2.11 answers: "What exactly produced this metric?"
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.artifacts.versioning import (
    ArtifactCompatibility,
    ArtifactCompatibilityError,
    ConfigHashError,
    semantic_hash,
)
from src.artifacts.versioning import validate_sha256 as _versioning_validate_sha256
from src.eval.evaluation_schema import VALID_SPLITS

EVALUATION_RUN_SCHEMA_VERSION = 1

# Exactly PROJECT_EXECUTION.md's Task 2.11 roadmap fields - never silently
# dropped even when a value is genuinely not applicable (e.g.
# generation_model=None for a retrieval-only run).
MANDATORY_ROADMAP_FIELDS: tuple[str, ...] = (
    "run_id", "git_sha", "chunk_config_hash", "embedding_model", "retrieval_config",
    "reranker_config", "generation_model", "split", "eval_set_version", "timestamp", "metrics",
)

DEFAULT_RUN_RECORDS_DIR = Path("results") / "eval_runs"

_UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

# Case-insensitive, separator-insensitive credential-key substrings
# (Section 35) - checked recursively through the entire record.
_SECRET_KEY_SUBSTRINGS: tuple[str, ...] = (
    "apikey", "password", "secret", "authorization", "bearer", "credential", "token",
)

# Deliberately matches src.artifacts.versioning.compute_embedding_identity()'s
# own real field names (Section 16: "use the actual existing identity field
# names where possible") plus `identity_hash`, which the identity dict
# itself does not carry (computed separately via
# src.artifacts.versioning.embedding_identity_hash() and added by the
# caller) - never a competing/renamed embedding-identity schema.
_REQUIRED_EMBEDDING_MODEL_FIELDS: tuple[str, ...] = (
    "model_repository", "model_revision", "embedding_dimension",
    "vector_dtype", "normalize_embeddings", "identity_hash",
)


class RunLogError(ValueError):
    """Base error for evaluation run logging."""


class RunLogValidationError(RunLogError):
    """A run record failed validation before being written/loaded."""


class RunRecordExistsError(RunLogError):
    """Refuses to overwrite an existing immutable run record."""


class RunRecordIntegrityError(RunLogError):
    """A loaded run record's run_record_sha256 does not match its
    recomputed content - the record may have been tampered with."""


# --------------------------------------------------------------- run id

def generate_run_id() -> str:
    """UUIDv4 - identifies one EXECUTION, never a semantic configuration.
    Running the same config twice must yield two different run_ids."""
    return str(uuid.uuid4())


def validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _UUID4_RE.match(run_id):
        raise RunLogValidationError(f"run_id is not a valid UUIDv4: {run_id!r}")


# --------------------------------------------------------------- timestamp

def current_utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def validate_timestamp(value: str) -> None:
    if not isinstance(value, str) or not _TIMESTAMP_RE.match(value):
        raise RunLogValidationError(
            f"timestamp must be UTC ISO-8601 with an explicit time, ending in 'Z', got {value!r}"
        )
    iso_value = value[:-1] + "+00:00"
    try:
        datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise RunLogValidationError(f"timestamp is not a valid UTC instant: {value!r}") from exc


# --------------------------------------------------------------- git provenance

def validate_sha256(value: str, field_name: str) -> None:
    """Wraps `src.artifacts.versioning.validate_sha256()` so every
    malformed-hash rejection in this module surfaces as
    `RunLogValidationError` (this module's own exception hierarchy)
    rather than `ConfigHashError` leaking across a module boundary."""
    try:
        _versioning_validate_sha256(value, field_name)
    except ConfigHashError as exc:
        raise RunLogValidationError(str(exc)) from exc


def validate_git_sha(git_sha: str) -> None:
    if not isinstance(git_sha, str) or not _GIT_SHA_RE.match(git_sha):
        raise RunLogValidationError(f"git_sha must be 40 lowercase hex characters, got {git_sha!r}")


def current_git_state(repo_root: Path | None = None) -> dict:
    """Resolves the REAL git_sha/git_dirty of the working tree. Fails
    loudly (RunLogError) if Git provenance cannot be resolved - never
    returns a placeholder like "unknown"/"HEAD"/"main" (Section 14)."""
    root = repo_root or Path(__file__).resolve().parents[2]
    try:
        sha_out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
        )
        status_out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True,
        )
    except Exception as exc:
        raise RunLogError(f"could not resolve git provenance: {exc}") from exc
    git_sha = sha_out.stdout.strip()
    validate_git_sha(git_sha)
    return {"git_sha": git_sha, "git_dirty": bool(status_out.stdout.strip())}


# --------------------------------------------------------------- secret safety

def _normalize_key(key: Any) -> str:
    return str(key).lower().replace("_", "").replace("-", "")


def _check_no_secrets(obj: Any, path: str = "") -> None:
    """Recursively rejects any dict key that looks credential-shaped -
    never redacts silently (Section 35). Never includes the offending
    VALUE in the raised message, only the field path."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            key_norm = _normalize_key(k)
            for pattern in _SECRET_KEY_SUBSTRINGS:
                if pattern in key_norm:
                    field_path = f"{path}.{k}" if path else str(k)
                    raise RunLogValidationError(
                        f"field {field_path!r} looks like a credential (matched pattern {pattern!r}) - refusing to log"
                    )
            _check_no_secrets(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            _check_no_secrets(item, f"{path}[{i}]")


# --------------------------------------------------------------- field validators

def validate_metrics(metrics: Mapping[str, Any]) -> None:
    if not isinstance(metrics, Mapping):
        raise RunLogValidationError(f"metrics must be a mapping, got {type(metrics)}")
    for name, value in metrics.items():
        if not isinstance(name, str) or not name.strip():
            raise RunLogValidationError(f"metric name must be a non-empty string, got {name!r}")
        if isinstance(value, bool):
            raise RunLogValidationError(f"metric {name!r} is a bool, not a numeric value: {value!r}")
        if not isinstance(value, (int, float)):
            raise RunLogValidationError(f"metric {name!r} must be int or float, got {type(value)}")
        if isinstance(value, float) and not math.isfinite(value):
            raise RunLogValidationError(f"metric {name!r} is not finite: {value!r}")


def validate_reranker_config(config: Mapping[str, Any]) -> None:
    if not isinstance(config, Mapping) or "enabled" not in config:
        raise RunLogValidationError("reranker_config must be a mapping with an explicit 'enabled' field")
    if not isinstance(config["enabled"], bool):
        raise RunLogValidationError(f"reranker_config['enabled'] must be a bool, got {type(config['enabled'])}")
    if config["enabled"]:
        missing = [f for f in ("model", "revision") if f not in config]
        if missing:
            raise RunLogValidationError(f"reranker_config enabled=true is missing required field(s): {missing}")


def validate_embedding_model(embedding_model: Mapping[str, Any]) -> None:
    if not isinstance(embedding_model, Mapping):
        raise RunLogValidationError(f"embedding_model must be a mapping, got {type(embedding_model)}")
    missing = [f for f in _REQUIRED_EMBEDDING_MODEL_FIELDS if f not in embedding_model]
    if missing:
        raise RunLogValidationError(f"embedding_model missing required field(s): {missing}")
    validate_sha256(embedding_model["identity_hash"], "embedding_model.identity_hash")


def validate_generation_model(generation_model: Mapping[str, Any] | None) -> None:
    if generation_model is None:
        return
    if not isinstance(generation_model, Mapping):
        raise RunLogValidationError(f"generation_model must be a mapping or null, got {type(generation_model)}")
    missing = [f for f in ("provider", "model") if f not in generation_model]
    if missing:
        raise RunLogValidationError(f"generation_model missing required field(s): {missing}")


def compute_config_semantic_hash(config: Mapping[str, Any]) -> str:
    """Reuses Task 2.10's canonical semantic-hash primitive - never a
    second independent hashing implementation. Suitable for an optional
    retrieval_config_hash/reranker_config_hash fingerprint. Semantic
    config only - never pass run_id/timestamp/git_sha/metrics in."""
    try:
        return semantic_hash(config)
    except ConfigHashError as exc:
        raise RunLogValidationError(f"config is not canonically hashable: {exc}") from exc


def compute_run_record_sha256(record: Mapping[str, Any]) -> str:
    """SHA-256 over the canonical JSON of the record with
    `run_record_sha256` itself excluded (Section 32) - detects accidental
    mutation, never a chunk/embedding/index/retrieval-config hash."""
    without_hash = {k: v for k, v in record.items() if k != "run_record_sha256"}
    return semantic_hash(without_hash)


# --------------------------------------------------------------- record

@dataclass(frozen=True)
class EvaluationRunRecord:
    """One immutable execution record. Field order below is the exact,
    stable JSON key order every written record uses."""
    run_schema_version: int
    run_id: str
    git_sha: str
    git_dirty: bool
    chunk_schema_version: int
    chunk_config_hash: str
    embedding_model: dict
    index_identity_hash: str | None
    retrieval_config: dict
    reranker_config: dict
    generation_model: dict | None
    split: str
    eval_set_version: str
    split_version: str
    split_sha256: str | None
    timestamp: str
    metrics: dict
    experiment_name: str | None
    run_kind: str | None
    notes: str | None
    record_origin: str
    run_record_sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_run_record(
    *,
    chunk_schema_version: int,
    chunk_config_hash: str,
    embedding_model: Mapping[str, Any],
    retrieval_config: Mapping[str, Any],
    reranker_config: Mapping[str, Any],
    generation_model: Mapping[str, Any] | None,
    split: str,
    eval_set_version: str,
    split_version: str,
    metrics: Mapping[str, Any],
    index_identity_hash: str | None = None,
    split_sha256: str | None = None,
    run_id: str | None = None,
    timestamp: str | None = None,
    git_state: Mapping[str, Any] | None = None,
    experiment_name: str | None = None,
    run_kind: str | None = None,
    notes: str | None = None,
    record_origin: str = "live",
    artifact_compatibility: ArtifactCompatibility | None = None,
) -> EvaluationRunRecord:
    """Constructs and fully validates one `EvaluationRunRecord`. Raises
    before returning anything - never a partially-valid record. Callers
    inject `run_id`/`timestamp`/`git_state` for deterministic tests;
    real invocations leave them None and get a fresh UUIDv4, the real
    current UTC instant, and the real resolved Git state."""
    run_id = run_id or generate_run_id()
    validate_run_id(run_id)

    timestamp = timestamp or current_utc_timestamp()
    validate_timestamp(timestamp)

    resolved_git_state = dict(git_state) if git_state is not None else current_git_state()
    validate_git_sha(resolved_git_state["git_sha"])

    validate_sha256(chunk_config_hash, "chunk_config_hash")
    validate_embedding_model(embedding_model)
    if index_identity_hash is not None:
        validate_sha256(index_identity_hash, "index_identity_hash")
    validate_reranker_config(reranker_config)
    validate_generation_model(generation_model)

    if split not in VALID_SPLITS:
        raise RunLogValidationError(f"split {split!r} not in {VALID_SPLITS}")
    if not isinstance(eval_set_version, str) or not eval_set_version.strip():
        raise RunLogValidationError("eval_set_version must be a non-empty string")
    if not isinstance(split_version, str) or not split_version.strip():
        raise RunLogValidationError("split_version must be a non-empty string")
    if split_sha256 is not None:
        validate_sha256(split_sha256, "split_sha256")

    validate_metrics(metrics)

    if artifact_compatibility is not None:
        _assert_matches_compatibility(
            artifact_compatibility, chunk_schema_version=chunk_schema_version,
            chunk_config_hash=chunk_config_hash, embedding_identity_hash=embedding_model.get("identity_hash"),
            index_identity_hash=index_identity_hash, eval_set_version=eval_set_version,
        )

    payload = {
        "run_schema_version": EVALUATION_RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "git_sha": resolved_git_state["git_sha"],
        "git_dirty": bool(resolved_git_state["git_dirty"]),
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "embedding_model": dict(embedding_model),
        "index_identity_hash": index_identity_hash,
        "retrieval_config": dict(retrieval_config),
        "reranker_config": dict(reranker_config),
        "generation_model": dict(generation_model) if generation_model is not None else None,
        "split": split,
        "eval_set_version": eval_set_version,
        "split_version": split_version,
        "split_sha256": split_sha256,
        "timestamp": timestamp,
        "metrics": dict(metrics),
        "experiment_name": experiment_name,
        "run_kind": run_kind,
        "notes": notes,
        "record_origin": record_origin,
    }

    _check_no_secrets(payload)

    payload["run_record_sha256"] = compute_run_record_sha256(payload)
    return EvaluationRunRecord(**payload)


def _assert_matches_compatibility(compatibility: ArtifactCompatibility, *, chunk_schema_version: int,
                                   chunk_config_hash: str, embedding_identity_hash: str | None,
                                   index_identity_hash: str | None, eval_set_version: str) -> None:
    if compatibility.chunk_schema_version != chunk_schema_version:
        raise ArtifactCompatibilityError(
            f"artifact_compatibility.chunk_schema_version={compatibility.chunk_schema_version} != "
            f"run chunk_schema_version={chunk_schema_version}"
        )
    if compatibility.chunk_config_hash != chunk_config_hash:
        raise ArtifactCompatibilityError(
            f"artifact_compatibility.chunk_config_hash={compatibility.chunk_config_hash} != "
            f"run chunk_config_hash={chunk_config_hash}"
        )
    if compatibility.embedding_identity_hash != embedding_identity_hash:
        raise ArtifactCompatibilityError(
            f"artifact_compatibility.embedding_identity_hash={compatibility.embedding_identity_hash} != "
            f"run embedding_model.identity_hash={embedding_identity_hash}"
        )
    if index_identity_hash is not None and compatibility.index_identity_hash != index_identity_hash:
        raise ArtifactCompatibilityError(
            f"artifact_compatibility.index_identity_hash={compatibility.index_identity_hash} != "
            f"run index_identity_hash={index_identity_hash}"
        )
    if compatibility.eval_set_version != eval_set_version:
        raise ArtifactCompatibilityError(
            f"artifact_compatibility.eval_set_version={compatibility.eval_set_version} != "
            f"run eval_set_version={eval_set_version}"
        )


# --------------------------------------------------------------- validation

def validate_run_record(record: "EvaluationRunRecord | Mapping[str, Any]") -> None:
    """Validates a complete record - either a live `EvaluationRunRecord`
    or a plain dict freshly parsed from JSON. Raises on the first
    violation; never silently coerces/repairs a malformed record."""
    data = record.to_dict() if isinstance(record, EvaluationRunRecord) else dict(record)

    missing = [f for f in MANDATORY_ROADMAP_FIELDS if f not in data]
    if missing:
        raise RunLogValidationError(f"run record missing mandatory field(s): {missing}")

    if data.get("run_schema_version") != EVALUATION_RUN_SCHEMA_VERSION:
        raise RunLogValidationError(f"unsupported run_schema_version {data.get('run_schema_version')!r}")

    validate_run_id(data["run_id"])
    validate_git_sha(data["git_sha"])
    validate_sha256(data["chunk_config_hash"], "chunk_config_hash")
    validate_embedding_model(data["embedding_model"])
    index_hash = data.get("index_identity_hash")
    if index_hash is not None:
        validate_sha256(index_hash, "index_identity_hash")
    validate_reranker_config(data["reranker_config"])
    validate_generation_model(data["generation_model"])

    if data["split"] not in VALID_SPLITS:
        raise RunLogValidationError(f"split {data['split']!r} not in {VALID_SPLITS}")
    if not isinstance(data["eval_set_version"], str) or not data["eval_set_version"].strip():
        raise RunLogValidationError("eval_set_version must be a non-empty string")
    split_sha256 = data.get("split_sha256")
    if split_sha256 is not None:
        validate_sha256(split_sha256, "split_sha256")

    validate_timestamp(data["timestamp"])
    validate_metrics(data["metrics"])

    _check_no_secrets({k: v for k, v in data.items() if k != "run_record_sha256"})

    if "run_record_sha256" in data:
        expected = compute_run_record_sha256(data)
        if data["run_record_sha256"] != expected:
            raise RunRecordIntegrityError(
                f"run_record_sha256 mismatch: stored {data['run_record_sha256']} != recomputed {expected} "
                f"- the record may have been tampered with"
            )


# --------------------------------------------------------------- persistence

def write_run_record(record: EvaluationRunRecord, *, directory: Path | None = None) -> Path:
    """Validates, then writes ONE new immutable file named by the
    record's own `run_id`. Refuses outright (`RunRecordExistsError`) if
    the target already exists - never overwrites a prior run."""
    validate_run_record(record)
    target_dir = Path(directory) if directory is not None else DEFAULT_RUN_RECORDS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{record.run_id}.json"
    text = json.dumps(record.to_dict(), indent=2) + "\n"
    try:
        with open(target, "x", encoding="utf-8") as f:
            f.write(text)
    except FileExistsError:
        raise RunRecordExistsError(f"run record already exists, refusing to overwrite: {target}")
    return target


def load_run_record(path: Path) -> EvaluationRunRecord:
    """Parses, validates, and integrity-checks a run record from disk.
    Rejects malformed JSON, a malformed schema, and a tampered
    `run_record_sha256` - never returns a record it has not fully
    validated."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunLogError(f"{path} is not valid JSON: {exc}") from exc
    validate_run_record(data)
    return EvaluationRunRecord(**data)


def list_run_records(directory: Path | None = None) -> list[Path]:
    """Deterministically sorted (by filename, i.e. by run_id) - never an
    implicit "latest"/"current"/"newest successful" selection. Callers
    pick a run explicitly."""
    target_dir = Path(directory) if directory is not None else DEFAULT_RUN_RECORDS_DIR
    if not target_dir.is_dir():
        return []
    return sorted(target_dir.glob("*.json"))
