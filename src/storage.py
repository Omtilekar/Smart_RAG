"""One authoritative map of where things live.

    from src.storage import get_storage, StorageError

    storage = get_storage()
    storage.xbrl_db                              # frozen input, Path
    storage.chunks_dir("a1b2c3d4")                # generated output, deterministic
    storage.index_dir("a1b2c3d4", "BAAI/bge-small-en-v1.5")

Frozen inputs (data/*, from Data Preparation) are read-only - this module
never deletes, renames, moves, truncates, overwrites, or downloads into
them. Generated outputs live under a separate `artifacts/` root and are
never created implicitly - importing this module or calling get_storage()
performs no filesystem writes; only `ensure_dir()` does, and only inside
`artifacts/`/`results/`.

Backend: local filesystem only. No S3/cloud backend exists - see
project_plan/STORAGE.md for the documented future-compatibility boundary.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.config import get_settings
from src.logging_utils import get_logger, log_event

log = get_logger(__name__)

_DRIVE_QUALIFIED_RE = re.compile(r"^[A-Za-z]:[\\/]")
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class StorageError(ValueError):
    """Raised for a missing required frozen input, or an unsafe/malformed
    generated-artifact path component."""


def safe_component(value: str) -> str:
    """Deterministic, portable conversion of an identifier (e.g. an
    embedding model name) into exactly one safe path component.

    Two different behaviors, both intentional:
      - Legitimate multi-segment identifiers (containing "/", ":", or
        whitespace - e.g. "BAAI/bge-small-en-v1.5") are NORMALIZED:
        "/" and "\\" become "--" between segments, ":" and whitespace
        become "-". Result: "BAAI--bge-small-en-v1.5".
      - Path-traversal or absolute-path-shaped input (".." as a distinct
        segment, a leading "/" or "\\", a drive-qualified prefix like
        "C:\\", or the bare strings "." / "..") is REJECTED outright by
        raising StorageError - never silently sanitized into something
        technically-harmless-but-suspicious.
    """
    if not isinstance(value, str):
        raise StorageError(f"path component must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if stripped == "":
        raise StorageError("path component must not be empty")
    if stripped in (".", ".."):
        raise StorageError(f"unsafe path component: {value!r}")
    if stripped.startswith("/") or stripped.startswith("\\"):
        raise StorageError(f"unsafe path component (absolute path): {value!r}")
    if _DRIVE_QUALIFIED_RE.match(stripped):
        raise StorageError(f"unsafe path component (drive-qualified path): {value!r}")

    segments = [seg.strip() for seg in re.split(r"[\\/]+", stripped) if seg.strip() != ""]
    for seg in segments:
        if seg in (".", ".."):
            raise StorageError(f"unsafe path component (traversal segment in {value!r})")
    if not segments:
        raise StorageError(f"unsafe path component: {value!r}")

    normalized = "--".join(segments)
    normalized = re.sub(r"\s+", "-", normalized)
    normalized = normalized.replace(":", "-")

    if normalized in ("", ".", "..") or not _SAFE_COMPONENT_RE.match(normalized):
        raise StorageError(f"unsafe path component after normalization: {value!r} -> {normalized!r}")
    return normalized


@dataclass(frozen=True)
class StoragePaths:
    repo_root: Path
    data_root: Path
    artifacts_root: Path
    results_root: Path

    # ---------------------------------------------------- frozen inputs
    # data/*, from Data Preparation. Read-only - never written by this class.

    @property
    def msmarco_root(self) -> Path:
        return self.data_root / "msmarco"

    @property
    def edgar_corpus_root(self) -> Path:
        return self.data_root / "edgar_corpus"

    @property
    def raw_xbrl_root(self) -> Path:
        return self.data_root / "raw" / "xbrl"

    @property
    def primary_docs_root(self) -> Path:
        return self.data_root / "raw" / "primary"

    @property
    def xbrl_db(self) -> Path:
        return self.data_root / "xbrl.duckdb"

    @property
    def financebench_root(self) -> Path:
        """Task 2.12 - frozen third-party FinanceBench source (JSONL +
        referenced PDFs), isolated from the internal SEC corpus roots
        above. Read-only once acquired, exactly like the other frozen-
        input roots on this class."""
        return self.data_root / "financebench"

    def benchmark_artifacts_dir(self, benchmark_name: str, benchmark_config_hash: str) -> Path:
        """Task 2.12 - isolated generated-output namespace for an
        external benchmark's derived parse/chunk/embedding/index
        artifacts. Never shares a directory with the SEC
        chunks_dir()/embeddings_dir()/index_dir() family above."""
        return self.artifacts_root / "benchmark" / safe_component(benchmark_name) / safe_component(benchmark_config_hash)

    # ------------------------------------------------- generated outputs
    # Deterministic, versioned locations under artifacts_root. Same input
    # always maps to the same path; different input always maps elsewhere.

    def normalized_dir(self, version: str) -> Path:
        return self.artifacts_root / "normalized" / safe_component(version)

    def normalized_dir_for_config(self, config_hash: str) -> Path:
        """Task 4.1 - full-corpus normalization output, keyed by the full
        `phase_4_1_config_hash` rather than the bare `normalizer_version`
        string. `normalized_dir(version)` alone is not sufficient identity
        here: the full-corpus frontmatter contract (nullable `company`, no
        `development_manifest_sha256`) differs from Task 1.2's dev-corpus
        contract while `normalizer_version` stays the same
        (`phase1-minimal-v1`, per repository decision) - reusing
        `normalized_dir()` would silently collide two different contracts
        into one directory. Mirrors `chunks_dir(chunk_config_hash)`'s
        existing pattern."""
        from src.artifacts.versioning import validate_sha256
        validate_sha256(config_hash, "phase_4_1_config_hash")
        return self.artifacts_root / "normalized_full" / safe_component(config_hash)

    def chunks_dir(self, chunk_config_hash: str) -> Path:
        """Task 0.7 only consumes an already-computed chunk_config_hash -
        it does not compute one. Hashing the chunking config is the future
        chunker implementation's job."""
        return self.artifacts_root / "chunks" / safe_component(chunk_config_hash)

    def chunks_dir_full(self, phase_4_1_config_hash: str, chunk_config_hash: str) -> Path:
        """Task 4.2 - full-corpus production chunk output, keyed by BOTH
        the Task 4.1 normalization-input identity and the Task 3.2 chunk
        semantic identity. Deliberately a different root (`chunks_full/`,
        not `chunks/`) from `chunks_dir()`'s existing dev/Phase 3 ablation
        artifacts (which key on chunk_config_hash alone) - the full
        91,086-document corpus must never collide with or be mistaken for
        the 1,500/1,493-document development chunk artifact that already
        lives at `chunks_dir(chunk_config_hash)` for this exact same
        chunk_config_hash (Task 3.2's winner is reused unchanged, not
        recomputed - see project_plan/PHASE4_FULL_CORPUS_CHUNKING.md)."""
        from src.artifacts.versioning import validate_sha256
        validate_sha256(phase_4_1_config_hash, "phase_4_1_config_hash")
        validate_sha256(chunk_config_hash, "chunk_config_hash")
        return (
            self.artifacts_root / "chunks_full"
            / safe_component(phase_4_1_config_hash) / safe_component(chunk_config_hash)
        )

    def index_dir(self, chunk_config_hash: str, embedding_model: str) -> Path:
        """Identity is (chunk_config_hash, embedding_model) together - the
        same chunks may be embedded with several models in Phase 3, so
        neither alone is a sufficient key."""
        return (
            self.artifacts_root
            / "indexes"
            / safe_component(chunk_config_hash)
            / safe_component(embedding_model)
        )

    def embeddings_dir(self, chunk_config_hash: str, embedding_model: str) -> Path:
        """Task 1.4's raw embedding artifact (vectors + metadata Parquet) -
        distinct from index_dir(), which is Task 1.5's LanceDB index built
        from these embeddings. Same (chunk_config_hash, embedding_model)
        compound-key rationale as index_dir(): neither alone is sufficient
        identity once Phase 3 benchmarks multiple embedding models against
        the same chunks."""
        return (
            self.artifacts_root
            / "embeddings"
            / safe_component(chunk_config_hash)
            / safe_component(embedding_model)
        )

    def eval_dir(self, eval_version: str) -> Path:
        return self.artifacts_root / "eval" / safe_component(eval_version)

    # ------------------------------------- Task 2.10 identity-hash-keyed paths
    # `embeddings_dir`/`index_dir` above key on a raw model-name string,
    # which is a real (Section 18) collision risk: the same model
    # repository reused with a different revision/dimension/normalization
    # would resolve to the same directory. These new methods key on the
    # full embedding_identity_hash instead (collision-proof by
    # construction) for any NEW artifact built under Task 2.10's identity
    # contract, while `embeddings_dir`/`index_dir` themselves are left
    # untouched so the existing Phase 1 on-disk layout stays readable
    # (Section 28 - no destructive migration of the Phase 1 baseline).

    def embeddings_dir_for_identity(self, chunk_config_hash: str, embedding_identity_hash: str) -> Path:
        from src.artifacts.versioning import validate_sha256
        validate_sha256(chunk_config_hash, "chunk_config_hash")
        validate_sha256(embedding_identity_hash, "embedding_identity_hash")
        return (
            self.artifacts_root / "embeddings"
            / safe_component(chunk_config_hash) / safe_component(embedding_identity_hash)
        )

    def index_dir_for_identity(self, chunk_config_hash: str, embedding_identity_hash: str) -> Path:
        from src.artifacts.versioning import validate_sha256
        validate_sha256(chunk_config_hash, "chunk_config_hash")
        validate_sha256(embedding_identity_hash, "embedding_identity_hash")
        return (
            self.artifacts_root / "indexes"
            / safe_component(chunk_config_hash) / safe_component(embedding_identity_hash)
        )

    # ------------------------------------------- frozen-input existence

    def require_file(self, path: Path) -> Path:
        """Existence/type check only - no content validation. Raises
        StorageError with a clear message if `path` is not a file."""
        if not path.is_file():
            raise StorageError(f"expected file not found: {path}")
        return path

    def require_dir(self, path: Path) -> Path:
        if not path.is_dir():
            raise StorageError(f"expected directory not found: {path}")
        return path

    # ------------------------------------- explicit generated-output I/O

    def ensure_dir(self, path: Path) -> Path:
        """Create `path` (and parents) if it doesn't exist. Idempotent -
        safe to call repeatedly. Restricted to artifacts_root/results_root:
        raises StorageError rather than creating anything outside those
        roots, so this can never be pointed at a frozen-input location by
        mistake."""
        resolved = path.resolve()
        allowed_roots = (self.artifacts_root.resolve(), self.results_root.resolve())
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            raise StorageError(
                f"refusing to create directory outside artifacts_root/results_root: {resolved}"
            )
        already_existed = resolved.is_dir()
        resolved.mkdir(parents=True, exist_ok=True)
        if not already_existed:
            log_event(log, logging.INFO, "artifact_dir_created", path=str(resolved))
        return resolved


@lru_cache(maxsize=1)
def get_storage() -> StoragePaths:
    """Cached StoragePaths singleton, built from src.config's Settings.
    Cheap - no filesystem writes, no existence checks, no data scanning.
    Tests that change STORAGE_ROOT at runtime should call
    get_storage.cache_clear() (and get_settings.cache_clear()) first."""
    settings = get_settings()
    return StoragePaths(
        repo_root=settings.repo_root,
        data_root=settings.storage_root,
        artifacts_root=settings.repo_root / "artifacts",
        results_root=settings.repo_root / "results",
    )
