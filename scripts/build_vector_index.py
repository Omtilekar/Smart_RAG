"""Task 1.5 - build the exact-cosine LanceDB vector index from Task 1.4's
embedding artifact.

Reads artifacts/embeddings/<chunk_config_hash>/<embedding_model>/embeddings.parquet
(frozen input, never modified), creates a single LanceDB table named
"chunks" under artifacts/indexes/<chunk_config_hash>/<embedding_model>/
(the existing src.storage.index_dir() contract), ingests all 162,357 rows
with all 17 columns retained, creates NO ANN index, validates schema/row
count/metadata/vector integrity, runs real-corpus self-retrieval checks,
and records a small Phase 1 smoke search-latency diagnostic.

No embedding model is loaded. No query embedding is implemented here -
Task 1.6 owns that. Vector-only, exact search only - see
project_plan/PHASE1_VECTOR_INDEX.md for the full frozen contract.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.index.lancedb_index import (  # noqa: E402
    DISTANCE_METRIC,
    EXPECTED_COLUMNS,
    TABLE_NAME,
    create_chunk_table,
    exact_cosine_search,
    open_database,
    open_chunk_table,
    validate_chunk_table,
)

EXPECTED_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
EXPECTED_ROW_COUNT = 162357
EMBEDDING_ARTIFACT_PATH = (
    Path("artifacts") / "embeddings" / EXPECTED_CHUNK_CONFIG_HASH
    / MODEL_REPO.replace("/", "--") / "embeddings.parquet"
)

# Reuses PROJECT_EXECUTION.md's already-frozen "top-5 context for
# generation" Phase 1 baseline constant for the smoke search diagnostic,
# rather than inventing a new arbitrary top-k contract.
DIAGNOSTIC_TOP_K = 5
DIAGNOSTIC_WARMUP_QUERIES = 5
DIAGNOSTIC_QUERY_COUNT = 50
SELF_RETRIEVAL_SAMPLE_COUNT = 40

CONFIG_RELATIVE_PATH = Path("configs") / "build_vector_index.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_5_vector_index_summary.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def verify_embedding_input(storage):
    path = storage.repo_root / EMBEDDING_ARTIFACT_PATH
    storage.require_file(path)
    table = pq.read_table(path)

    if table.num_rows != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: embeddings.parquet has {table.num_rows} rows, expected {EXPECTED_ROW_COUNT}")
    if set(table.schema.names) != set(EXPECTED_COLUMNS):
        raise SystemExit(f"FATAL: unexpected embedding schema: {table.schema.names}")

    ids = table.column("chunk_id").to_pylist()
    if len(set(ids)) != len(ids):
        raise SystemExit("FATAL: duplicate chunk_id in embeddings.parquet")

    hashes = set(table.column("chunk_config_hash").to_pylist())
    if hashes != {EXPECTED_CHUNK_CONFIG_HASH}:
        raise SystemExit(f"FATAL: unexpected chunk_config_hash values: {hashes}")

    vector_field = table.schema.field("vector").type
    if not pa.types.is_fixed_size_list(vector_field) or vector_field.list_size != 384:
        raise SystemExit(f"FATAL: unexpected vector field type: {vector_field}")

    flat = table.column("vector").combine_chunks().values.to_numpy(zero_copy_only=False)
    if flat.dtype != np.float32:
        raise SystemExit(f"FATAL: vector dtype {flat.dtype} != float32")
    if not np.isfinite(flat).all():
        raise SystemExit("FATAL: embeddings.parquet contains non-finite vector values")

    return table


def full_metadata_integrity(source_table, indexed_table) -> None:
    """Compares every non-vector column, full corpus, not sampled."""
    indexed_arrow = indexed_table.to_arrow()
    if indexed_arrow.num_rows != source_table.num_rows:
        raise SystemExit(f"FATAL: indexed row count {indexed_arrow.num_rows} != source {source_table.num_rows}")

    source_by_id = {cid: i for i, cid in enumerate(source_table.column("chunk_id").to_pylist())}
    indexed_ids = indexed_arrow.column("chunk_id").to_pylist()
    if len(set(indexed_ids)) != len(indexed_ids):
        raise SystemExit("FATAL: duplicate chunk_id in indexed table")
    if set(indexed_ids) != set(source_by_id.keys()):
        raise SystemExit("FATAL: indexed chunk_id set differs from source chunk_id set")

    check_fields = [c for c in EXPECTED_COLUMNS if c != "vector"]
    indexed_by_field = {f: indexed_arrow.column(f).to_pylist() for f in check_fields}
    source_by_field = {f: source_table.column(f).to_pylist() for f in check_fields}

    # Re-order indexed rows to source row order (chunk_id keyed) before comparing,
    # since Task 1.5 does not assert physical row order is preserved.
    indexed_pos_by_id = {cid: pos for pos, cid in enumerate(indexed_ids)}
    for field in check_fields:
        reordered = [indexed_by_field[field][indexed_pos_by_id[cid]] for cid in source_table.column("chunk_id").to_pylist()]
        if reordered != source_by_field[field]:
            raise SystemExit(f"FATAL: metadata mismatch in field {field!r} between indexed table and source")


def vector_integrity_check(source_table, indexed_table, sample_size: int = 200) -> dict:
    """Compares stored vectors against source vectors for a deterministic
    subset (indices evenly spaced across the corpus)."""
    n = source_table.num_rows
    step = max(1, n // sample_size)
    sample_indices = list(range(0, n, step))[:sample_size]

    source_ids = source_table.column("chunk_id").to_pylist()
    source_vectors = source_table.column("vector").combine_chunks().values.to_numpy(
        zero_copy_only=False
    ).reshape(-1, 384)

    indexed_arrow = indexed_table.to_arrow()
    indexed_ids = indexed_arrow.column("chunk_id").to_pylist()
    indexed_pos_by_id = {cid: pos for pos, cid in enumerate(indexed_ids)}
    indexed_vectors_flat = indexed_arrow.column("vector").combine_chunks().values.to_numpy(zero_copy_only=False)
    indexed_vectors = indexed_vectors_flat.reshape(-1, 384)

    max_abs_diff = 0.0
    exact_matches = 0
    for i in sample_indices:
        cid = source_ids[i]
        src_vec = source_vectors[i]
        idx_vec = indexed_vectors[indexed_pos_by_id[cid]]
        if np.array_equal(src_vec, idx_vec):
            exact_matches += 1
        diff = float(np.abs(src_vec - idx_vec).max())
        max_abs_diff = max(max_abs_diff, diff)

    if max_abs_diff > 1e-6:
        raise SystemExit(f"FATAL: stored vectors differ materially from source (max abs diff {max_abs_diff})")

    return {
        "sample_size": len(sample_indices),
        "exact_matches": exact_matches,
        "max_abs_diff": max_abs_diff,
    }


def self_retrieval_check(source_table, table, sample_count: int = SELF_RETRIEVAL_SAMPLE_COUNT) -> dict:
    n = source_table.num_rows
    step = max(1, n // sample_count)
    sample_indices = list(range(0, n, step))[:sample_count]

    ids = source_table.column("chunk_id").to_pylist()
    vectors = source_table.column("vector").combine_chunks().values.to_numpy(
        zero_copy_only=False
    ).reshape(-1, 384)

    checked = 0
    passed = 0
    self_distances = []
    anomalies = []
    for i in sample_indices:
        expected_id = ids[i]
        query_vec = vectors[i]
        result = exact_cosine_search(table, query_vec, limit=1)
        checked += 1
        if result.num_rows == 0:
            anomalies.append({"chunk_id": expected_id, "issue": "no results"})
            continue
        top_id = result.column("chunk_id")[0].as_py()
        top_dist = result.column("_distance")[0].as_py()
        self_distances.append(top_dist)
        if top_id == expected_id:
            passed += 1
        else:
            anomalies.append({"chunk_id": expected_id, "got": top_id, "distance": top_dist})

    return {
        "checked": checked,
        "passed": passed,
        "anomalies": anomalies,
        "self_distance_min": min(self_distances) if self_distances else None,
        "self_distance_max": max(self_distances) if self_distances else None,
    }


def search_latency_diagnostic(source_table, table) -> dict:
    n = source_table.num_rows
    vectors = source_table.column("vector").combine_chunks().values.to_numpy(
        zero_copy_only=False
    ).reshape(-1, 384)

    total_needed = DIAGNOSTIC_WARMUP_QUERIES + DIAGNOSTIC_QUERY_COUNT
    step = max(1, n // total_needed)
    sample_indices = list(range(0, n, step))[:total_needed]

    for i in sample_indices[:DIAGNOSTIC_WARMUP_QUERIES]:
        exact_cosine_search(table, vectors[i], limit=DIAGNOSTIC_TOP_K)

    latencies_ms = []
    for i in sample_indices[DIAGNOSTIC_WARMUP_QUERIES:]:
        start = time.perf_counter()
        exact_cosine_search(table, vectors[i], limit=DIAGNOSTIC_TOP_K)
        latencies_ms.append((time.perf_counter() - start) * 1000)

    latencies_ms.sort()
    return {
        "label": "Phase 1 smoke diagnostic - not a production benchmark",
        "query_count": len(latencies_ms),
        "top_k": DIAGNOSTIC_TOP_K,
        "p50_ms": round(statistics.median(latencies_ms), 3),
        "p95_ms": round(latencies_ms[int(0.95 * (len(latencies_ms) - 1))], 3),
    }


def main() -> int:
    build_start = time.monotonic()
    storage = get_storage()

    source_table = verify_embedding_input(storage)
    development_manifest_sha256 = source_table.column("development_manifest_sha256")[0].as_py()
    normalization_build_sha256 = source_table.column("normalization_build_sha256")[0].as_py()
    normalizer_version = source_table.column("normalizer_version")[0].as_py()

    db_path = storage.index_dir(EXPECTED_CHUNK_CONFIG_HASH, MODEL_REPO)

    if db_path.exists():
        db = open_database(db_path)
        existing_names = db.list_tables().tables
        if existing_names == [TABLE_NAME]:
            existing = open_chunk_table(db)
            if existing.count_rows() == EXPECTED_ROW_COUNT:
                print(f"Existing table '{TABLE_NAME}' at {db_path} already has {EXPECTED_ROW_COUNT} rows - reusing.")
                table = existing
            else:
                raise SystemExit(
                    f"FATAL: existing table '{TABLE_NAME}' at {db_path} has "
                    f"{existing.count_rows()} rows, expected {EXPECTED_ROW_COUNT} - "
                    f"refusing to silently overwrite a conflicting index."
                )
        elif existing_names:
            raise SystemExit(f"FATAL: {db_path} contains unexpected tables {existing_names} - refusing to proceed.")
        else:
            table = create_chunk_table(db, source_table)
    else:
        storage.ensure_dir(db_path)
        db = open_database(db_path)
        table = create_chunk_table(db, source_table)

    validate_chunk_table(table, expected_row_count=EXPECTED_ROW_COUNT)
    full_metadata_integrity(source_table, table)
    vector_check = vector_integrity_check(source_table, table)

    build_time_s = time.monotonic() - build_start

    self_retrieval = self_retrieval_check(source_table, table)
    if self_retrieval["passed"] != self_retrieval["checked"]:
        raise SystemExit(
            f"FATAL: self-retrieval failed for {self_retrieval['checked'] - self_retrieval['passed']} "
            f"of {self_retrieval['checked']} chunks: {self_retrieval['anomalies']}"
        )

    diagnostic = search_latency_diagnostic(source_table, table)

    db_size_bytes = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())

    config = {
        "schema_version": "1.0",
        "input_embedding_artifact": str(EMBEDDING_ARTIFACT_PATH.as_posix()),
        "input_chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "embedding_dimension": 384,
        "vector_dtype": "float32",
        "normalize_embeddings": True,
        "database_backend": "lancedb",
        "search_mode": "exact",
        "distance_metric": DISTANCE_METRIC,
        "table_name": TABLE_NAME,
        "column_policy": "all_17_columns",
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "input_embedding_artifact": str(EMBEDDING_ARTIFACT_PATH.as_posix()),
        "input_chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
        "development_manifest_sha256": development_manifest_sha256,
        "normalization_build_sha256": normalization_build_sha256,
        "normalizer_version": normalizer_version,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "vector_count": table.count_rows(),
        "vector_dimension": 384,
        "vector_dtype": "float32",
        "normalize_embeddings": True,
        "backend": "lancedb",
        "lancedb_version": __import__("lancedb").__version__,
        "search_mode": "exact",
        "distance_metric": DISTANCE_METRIC,
        "table_name": TABLE_NAME,
        "column_count": len(EXPECTED_COLUMNS),
        "database_path": str((Path("artifacts") / "indexes" / EXPECTED_CHUNK_CONFIG_HASH
                               / MODEL_REPO.replace("/", "--")).as_posix()),
        "database_size_bytes": db_size_bytes,
        "build_runtime_seconds": round(build_time_s, 2),
        "ann_indexes_created": len(table.list_indices()),
        "vector_integrity_check": vector_check,
        "self_retrieval": self_retrieval,
        "search_diagnostic": diagnostic,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Table '{TABLE_NAME}' at {db_path}: {table.count_rows()} rows, "
          f"{len(table.list_indices())} ANN indexes")
    print(f"Self-retrieval: {self_retrieval['passed']}/{self_retrieval['checked']} passed")
    print(f"Search diagnostic (top-{diagnostic['top_k']}, n={diagnostic['query_count']}): "
          f"p50={diagnostic['p50_ms']}ms p95={diagnostic['p95_ms']}ms")
    print(f"Build runtime: {build_time_s:.2f}s, database size: {db_size_bytes:,} bytes")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
