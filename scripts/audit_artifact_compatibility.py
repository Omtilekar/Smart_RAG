"""Task 2.10 - real-artifact compatibility audit.

Verifies the chunk -> embedding -> index chain for the real, frozen
Phase 1 baseline using Task 2.10's new centralized identity/manifest
contract (src.artifacts.versioning), entirely read-only: no Parquet/
LanceDB content is rewritten, no chunking/embedding/indexing is rerun,
no model is loaded, no GPU is touched.

The only writes this script performs are small, deterministic
`manifest.json` sidecars placed next to the existing Phase 1 artifact
directories (never inside/over the Parquet or LanceDB data itself),
explicitly labeled "verified historical artifact provenance" - these did
not exist at original Phase 1 build time and are not claimed to have.

Writes results/phase_2_10_artifact_versioning.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.artifacts.versioning import (  # noqa: E402
    ArtifactCompatibility,
    ArtifactCompatibilityError,
    ArtifactManifestError,
    assert_artifact_compatible,
    build_chunk_manifest,
    build_embedding_manifest,
    build_index_manifest,
    compute_chunk_config_hash,
    compute_index_identity_hash,
    embedding_identity_hash as compute_embedding_identity_hash,
    validate_artifact_manifest,
)
from src.chunk.metadata_schema import CHUNK_SCHEMA_VERSION  # noqa: E402
from src.embeddings.bge import MODEL_REPO, embedding_identity  # noqa: E402
from src.index.lancedb_index import (  # noqa: E402
    TABLE_NAME,
    index_identity,
    open_chunk_table,
    open_database,
)
from src.storage import get_storage  # noqa: E402

EXPECTED_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
EXPECTED_ROW_COUNT = 162_357
CHUNK_CONFIG_PATH = Path("configs") / "chunk_development_corpus.json"

RESULT_PATH = Path("results") / "phase_2_10_artifact_versioning.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def audit_chunk_hash() -> dict:
    config = json.loads((REPO_ROOT / CHUNK_CONFIG_PATH).read_text(encoding="utf-8"))
    recomputed = compute_chunk_config_hash(config)
    legacy_pass = recomputed == EXPECTED_CHUNK_CONFIG_HASH
    return {
        "historical_hash": EXPECTED_CHUNK_CONFIG_HASH,
        "recomputed_hash": recomputed,
        "legacy_compatibility": "PASS" if legacy_pass else "FAIL",
        "config": config,
    }


def audit_chunk_artifact(storage, chunk_config: dict, chunk_config_hash: str) -> dict:
    chunk_dir = storage.chunks_dir(chunk_config_hash)
    chunk_path = chunk_dir / "chunks.parquet"
    storage.require_file(chunk_path)
    table = pq.read_table(chunk_path)
    row_count = table.num_rows
    if row_count != EXPECTED_ROW_COUNT:
        raise SystemExit(f"STOP: chunks.parquet has {row_count} rows, expected {EXPECTED_ROW_COUNT}")
    hashes = set(table.column("chunk_config_hash").to_pylist())
    if hashes != {chunk_config_hash}:
        raise SystemExit(f"STOP: unexpected chunk_config_hash values in chunks.parquet: {hashes}")

    manifest = build_chunk_manifest(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_config_hash,
        chunk_config=chunk_config, row_count=row_count,
        created_at_utc=datetime.now(timezone.utc).isoformat(), git_sha=git_sha(),
        verified_historical=True,
    )
    validate_artifact_manifest(manifest, "chunks")
    manifest_path = chunk_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {"directory": str(chunk_dir), "row_count": row_count, "manifest_path": str(manifest_path), "manifest": manifest}


def audit_embedding_artifact(storage, chunk_config_hash: str) -> dict:
    identity = embedding_identity()
    identity_hash = compute_embedding_identity_hash(identity)

    emb_dir = storage.embeddings_dir(chunk_config_hash, MODEL_REPO)
    emb_path = emb_dir / "embeddings.parquet"
    storage.require_file(emb_path)
    table = pq.read_table(emb_path)
    row_count = table.num_rows
    if row_count != EXPECTED_ROW_COUNT:
        raise SystemExit(f"STOP: embeddings.parquet has {row_count} rows, expected {EXPECTED_ROW_COUNT}")
    hashes = set(table.column("chunk_config_hash").to_pylist())
    if hashes != {chunk_config_hash}:
        raise SystemExit(f"STOP: unexpected chunk_config_hash values in embeddings.parquet: {hashes}")

    manifest = build_embedding_manifest(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_config_hash,
        embedding_identity=identity, embedding_identity_hash_value=identity_hash, row_count=row_count,
        created_at_utc=datetime.now(timezone.utc).isoformat(), git_sha=git_sha(),
        verified_historical=True,
    )
    validate_artifact_manifest(manifest, "embeddings")
    manifest_path = emb_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "directory": str(emb_dir), "row_count": row_count, "embedding_identity": identity,
        "embedding_identity_hash": identity_hash, "manifest_path": str(manifest_path), "manifest": manifest,
    }


def audit_index_artifact(storage, chunk_config_hash: str, embedding_identity_hash_value: str) -> dict:
    idx_identity = index_identity(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_config_hash,
        embedding_identity_hash_value=embedding_identity_hash_value,
    )
    idx_identity_hash = compute_index_identity_hash(idx_identity)

    db_path = storage.index_dir(chunk_config_hash, MODEL_REPO)
    storage.require_dir(db_path)
    db = open_database(db_path)
    if db.list_tables().tables != [TABLE_NAME]:
        raise SystemExit(f"STOP: unexpected tables at {db_path}: {db.list_tables().tables}")
    table = open_chunk_table(db)
    row_count = table.count_rows()
    if row_count != EXPECTED_ROW_COUNT:
        raise SystemExit(f"STOP: index table has {row_count} rows, expected {EXPECTED_ROW_COUNT}")
    ann_indexes = len(table.list_indices())
    if ann_indexes != 0:
        raise SystemExit(f"STOP: expected 0 ANN indexes, found {ann_indexes}")

    manifest = build_index_manifest(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_config_hash,
        embedding_identity_hash_value=embedding_identity_hash_value, index_identity=idx_identity,
        index_identity_hash_value=idx_identity_hash, row_count=row_count,
        created_at_utc=datetime.now(timezone.utc).isoformat(), git_sha=git_sha(),
        verified_historical=True,
    )
    validate_artifact_manifest(manifest, "index")
    manifest_path = db_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "directory": str(db_path), "row_count": row_count, "ann_indexes": ann_indexes,
        "index_identity": idx_identity, "index_identity_hash": idx_identity_hash,
        "manifest_path": str(manifest_path), "manifest": manifest,
    }


def audit_eval_set_version() -> dict:
    """Reads only already-frozen, already-tracked hash/version metadata
    from results/*.json - never opens the protected TEST question
    payload."""
    dataset_summary = json.loads((REPO_ROOT / "results" / "phase_2_3_evaluation_dataset_summary.json").read_text(encoding="utf-8"))
    split_summary = json.loads((REPO_ROOT / "results" / "phase_2_4_split_summary.json").read_text(encoding="utf-8"))
    return {
        "eval_set_version": dataset_summary["eval_set_version"],
        "dataset_sha256": dataset_summary["dataset_sha256"],
        "split_version": split_summary["split_version"],
        "dev_sha256": split_summary["dev_sha256"],
        "test_sha256": split_summary["test_sha256"],
        "ci_sha256": split_summary["ci_sha256"],
        "test_payload_opened": False,
        "note": "TEST hash is a frozen digest already committed in phase_2_4_split_summary.json - reading it here does not materialize or access the protected TEST question corpus.",
    }


def audit_test_access_discipline() -> dict:
    con = duckdb.connect(str(REPO_ROOT / "artifacts" / "eval" / "eval.duckdb"), read_only=True)
    try:
        rows = con.execute("SELECT kind, run_number FROM test_access_log").fetchall()
    finally:
        con.close()
    official_runs = sum(1 for kind, run_number in rows if run_number is not None)
    return {"total_access_log_rows": len(rows), "official_test_runs_used": official_runs, "budget": 3}


def run_negative_self_checks(chunk_manifest: dict, embedding_manifest: dict, index_manifest: dict,
                              compatibility: ArtifactCompatibility) -> dict:
    """Proves ArtifactCompatibilityError actually fires for tampered
    copies of the real manifests just built - never mutates the real
    manifests/artifacts themselves."""
    results = {}

    def _expect_fail(name, fn):
        try:
            fn()
            results[name] = "FAIL (no exception raised)"
        except (ArtifactCompatibilityError, ArtifactManifestError):
            results[name] = "PASS"

    tampered_chunk = dict(chunk_manifest, chunk_config_hash="0" * 64)
    _expect_fail("stale_chunk_hash_rejected", lambda: assert_artifact_compatible(compatibility, chunk_manifest=tampered_chunk))

    tampered_emb = dict(embedding_manifest, embedding_identity_hash="0" * 64)
    _expect_fail("stale_embedding_identity_rejected", lambda: assert_artifact_compatible(compatibility, embedding_manifest=tampered_emb))

    tampered_idx = dict(index_manifest, index_identity_hash="0" * 64)
    _expect_fail("stale_index_identity_rejected", lambda: assert_artifact_compatible(compatibility, index_manifest=tampered_idx))

    tampered_schema = dict(chunk_manifest, chunk_schema_version=999)
    _expect_fail("schema_version_mismatch_rejected", lambda: assert_artifact_compatible(compatibility, chunk_manifest=tampered_schema))

    _expect_fail("eval_version_mismatch_rejected", lambda: assert_artifact_compatible(compatibility, manifest_eval_set_version="not-the-real-version"))

    return results


def main() -> None:
    print("=== Task 2.10 artifact compatibility audit ===")
    storage = get_storage()

    hash_audit = audit_chunk_hash()
    print(f"Chunk config hash legacy compatibility: {hash_audit['legacy_compatibility']}")
    if hash_audit["legacy_compatibility"] != "PASS":
        raise SystemExit("STOP: centralized hash utility cannot reproduce the frozen Phase 1 chunk_config_hash")
    chunk_hash = hash_audit["recomputed_hash"]

    chunk_artifact = audit_chunk_artifact(storage, hash_audit["config"], chunk_hash)
    print(f"Chunk artifact: {chunk_artifact['row_count']} rows, manifest written to {chunk_artifact['manifest_path']}")

    embedding_artifact = audit_embedding_artifact(storage, chunk_hash)
    print(f"Embedding artifact: {embedding_artifact['row_count']} rows, identity_hash={embedding_artifact['embedding_identity_hash']}")

    index_artifact = audit_index_artifact(storage, chunk_hash, embedding_artifact["embedding_identity_hash"])
    print(f"Index artifact: {index_artifact['row_count']} rows, {index_artifact['ann_indexes']} ANN indexes, identity_hash={index_artifact['index_identity_hash']}")

    eval_meta = audit_eval_set_version()
    print(f"Eval set version: {eval_meta['eval_set_version']} / split {eval_meta['split_version']}")

    test_discipline = audit_test_access_discipline()
    print(f"Official TEST runs used: {test_discipline['official_test_runs_used']}/{test_discipline['budget']}")
    if test_discipline["official_test_runs_used"] != 0:
        raise SystemExit("STOP: official TEST runs consumed is not 0 - refusing to proceed")

    compatibility = ArtifactCompatibility(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=chunk_hash,
        embedding_identity_hash=embedding_artifact["embedding_identity_hash"],
        index_identity_hash=index_artifact["index_identity_hash"],
        eval_set_version=eval_meta["eval_set_version"],
    )
    assert_artifact_compatible(
        compatibility, chunk_manifest=chunk_artifact["manifest"],
        embedding_manifest=embedding_artifact["manifest"], index_manifest=index_artifact["manifest"],
        manifest_eval_set_version=eval_meta["eval_set_version"],
    )
    print("Valid chain compatibility: PASS")

    negative_checks = run_negative_self_checks(
        chunk_artifact["manifest"], embedding_artifact["manifest"], index_artifact["manifest"], compatibility,
    )
    for name, outcome in negative_checks.items():
        print(f"  {name}: {outcome}")
    if any(v != "PASS" for v in negative_checks.values()):
        raise SystemExit(f"STOP: a negative compatibility self-check did not fail as expected: {negative_checks}")

    summary = {
        "artifact_manifest_version": 1,
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "chunk_config_hash": {
            "historical": hash_audit["historical_hash"], "recomputed": hash_audit["recomputed_hash"],
            "legacy_compatibility": hash_audit["legacy_compatibility"],
        },
        "chunk_artifact": {"directory": chunk_artifact["directory"], "row_count": chunk_artifact["row_count"]},
        "embedding_artifact": {
            "directory": embedding_artifact["directory"], "row_count": embedding_artifact["row_count"],
            "embedding_identity": embedding_artifact["embedding_identity"],
            "embedding_identity_hash": embedding_artifact["embedding_identity_hash"],
        },
        "index_artifact": {
            "directory": index_artifact["directory"], "row_count": index_artifact["row_count"],
            "ann_indexes": index_artifact["ann_indexes"], "index_identity": index_artifact["index_identity"],
            "index_identity_hash": index_artifact["index_identity_hash"],
        },
        "eval_set_version": eval_meta,
        "test_access_discipline": test_discipline,
        "chain_compatibility": "PASS",
        "negative_self_checks": negative_checks,
        "historical_artifacts_modified": False,
        "note": "manifest.json sidecars written next to each Phase 1 artifact directory are new files only - chunks.parquet, embeddings.parquet, and the LanceDB table data were never rewritten. Labeled 'verified historical artifact provenance' - they did not exist at original build time.",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Written: {RESULT_PATH}")


if __name__ == "__main__":
    main()
