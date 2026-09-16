"""Task 4.4 - build the full-corpus (10,487,096-row) exact-cosine LanceDB
vector index from Task 4.3's frozen full-corpus embedding artifact.

Reads the 54 sharded `*.embeddings.parquet` files under
`storage.embeddings_dir_full(...)` (frozen input, never modified),
verifies each shard's SHA-256/row-count against Task 4.3's own
`final/embedding_manifest.json` (including that manifest's own
self-referential `manifest_sha256` field, recomputed using this
project's established canonical-JSON-then-SHA-256 convention -
`src.artifacts.versioning.semantic_hash` - never assumed to be a raw
file-byte hash), then ingests every shard into a single LanceDB table
named "chunks" under `storage.index_dir_full(...)`.

No ANN/vector index is created (Phase 3 never validated a quantization
strategy - see project_plan/SERVING_FEASIBILITY.md). Two scalar BTREE
indexes (cik, fiscal_year - Task 3.9's validated discriminative
pre-filter dimensions) are built for production filtered-scan
performance. No BM25/FTS production index is built - see
project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md for why this
intentionally departs from PROJECT_EXECUTION.md's generic Phase 4.4
checklist wording.

Shard-level resumable: a `_build_state.json` checkpoint (config/source-
identity-bound, like Task 4.1/4.2's checkpoints) records which shard IDs
have been successfully ingested, so an interrupted run can be restarted
without re-ingesting completed shards.

No embedding model is loaded. No query embedding is implemented here.
"""

from __future__ import annotations

import hashlib
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
from src.artifacts.versioning import semantic_hash, compute_index_identity, compute_index_identity_hash  # noqa: E402
from src.embeddings.model_registry import QWEN3_EMBEDDING  # noqa: E402
from src.index.lancedb_index import exact_cosine_search  # noqa: E402
from src.index.lancedb_index_full import (  # noqa: E402
    DISTANCE_METRIC,
    EMBEDDING_DIMENSION,
    EXPECTED_COLUMNS,
    INDEX_TYPE,
    SCALAR_INDEX_COLUMNS,
    TABLE_NAME,
    VectorIndexFullError,
    build_scalar_indexes,
    create_chunk_table,
    open_chunk_table,
    open_database,
    validate_chunk_table,
    validate_scalar_indexes,
    validate_shard_schema,
)

PHASE_4_1_CONFIG_HASH = "754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f"
CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"
CHUNK_SCHEMA_VERSION = 2
MODEL_REPO = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
EXPECTED_SHARD_COUNT = 54
EXPECTED_ROW_COUNT = 10_487_096
EXPECTED_MANIFEST_SHA256 = "a4d1421bb287ea6aa21398f1fca99f1e11650b7c0d49979077140bb17456fbc8"

DIAGNOSTIC_TOP_K = 5
DIAGNOSTIC_WARMUP_QUERIES = 2
DIAGNOSTIC_QUERY_COUNT = 5   # kept small deliberately - measured directly on
                             # this machine, one exact-flat search over the
                             # real 10,487,096 x 1024-dim table took ~31s
                             # (disk-bound full-column scan; contrast Task
                             # 3.14's 554.7ms p50 @ 323,971 rows - see
                             # project_plan/SERVING_FEASIBILITY.md). This is
                             # a smoke diagnostic, not a latency benchmark -
                             # query count is deliberately small so the whole
                             # build stays survivable on a shared dev machine.
SELF_RETRIEVAL_SAMPLE_SHARDS = (0, 10, 20, 30, 40, 53)
SELF_RETRIEVAL_SAMPLES_PER_SHARD = 2  # 12 total queries - same rationale as above

CONFIG_RELATIVE_PATH = Path("configs") / "phase_4_4_full_corpus_vector_index.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_4_4_full_corpus_vector_index_summary.json"
CHECKPOINT_FILENAME = "_build_state.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def load_and_verify_manifest(storage) -> tuple[Path, list[dict]]:
    root = storage.embeddings_dir_full(PHASE_4_1_CONFIG_HASH, CHUNK_CONFIG_HASH, MODEL_REPO, MODEL_REVISION)
    storage.require_dir(root)
    manifest_path = root / "final" / "embedding_manifest.json"
    validation_path = root / "final" / "validation_summary.json"
    storage.require_file(manifest_path)
    storage.require_file(validation_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    stated_hash = manifest.get("manifest_sha256")
    manifest_minus_hash = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    recomputed_hash = semantic_hash(manifest_minus_hash)
    if recomputed_hash != stated_hash:
        raise SystemExit(
            f"FATAL: embedding_manifest.json's own manifest_sha256 field "
            f"({stated_hash}) does not reproduce under canonical-JSON "
            f"SHA-256 of the manifest minus that field ({recomputed_hash})"
        )
    if stated_hash != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(f"FATAL: manifest_sha256 {stated_hash} != frozen Task 4.3 value {EXPECTED_MANIFEST_SHA256}")

    if manifest.get("model") != MODEL_REPO or manifest.get("model_revision") != MODEL_REVISION:
        raise SystemExit(f"FATAL: unexpected model/revision in manifest: {manifest.get('model')!r} / {manifest.get('model_revision')!r}")
    if manifest.get("embedding_dimension") != EMBEDDING_DIMENSION:
        raise SystemExit(f"FATAL: unexpected embedding_dimension in manifest: {manifest.get('embedding_dimension')!r}")
    if manifest.get("shard_count") != EXPECTED_SHARD_COUNT:
        raise SystemExit(f"FATAL: unexpected shard_count in manifest: {manifest.get('shard_count')!r}")

    if validation.get("status") != "PASS":
        raise SystemExit(f"FATAL: Task 4.3 validation_summary.json status is {validation.get('status')!r}, expected PASS")
    if validation.get("embeddings_actual") != EXPECTED_ROW_COUNT or validation.get("embeddings_expected") != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: unexpected embeddings_actual/expected in validation_summary.json: {validation}")
    if validation.get("shards_actual") != EXPECTED_SHARD_COUNT or validation.get("shards_expected") != EXPECTED_SHARD_COUNT:
        raise SystemExit(f"FATAL: unexpected shards_actual/expected in validation_summary.json: {validation}")
    if validation.get("missing_shards") or validation.get("duplicate_shards"):
        raise SystemExit(f"FATAL: Task 4.3 validation_summary.json reports missing/duplicate shards: {validation}")

    shards = sorted(manifest["shards"], key=lambda s: s["shard_id"])
    shard_ids = [s["shard_id"] for s in shards]
    if shard_ids != list(range(EXPECTED_SHARD_COUNT)):
        raise SystemExit(f"FATAL: shard IDs are not exactly 0..{EXPECTED_SHARD_COUNT - 1}: {shard_ids}")

    total_rows = sum(s["rows"] for s in shards)
    if total_rows != EXPECTED_ROW_COUNT:
        raise SystemExit(f"FATAL: sum(shard rows) {total_rows} != expected {EXPECTED_ROW_COUNT}")

    for shard in shards:
        if shard["model"] != MODEL_REPO or shard["model_revision"] != MODEL_REVISION:
            raise SystemExit(f"FATAL: shard {shard['shard_id']} has unexpected model/revision")
        if shard["embedding_dimension"] != EMBEDDING_DIMENSION:
            raise SystemExit(f"FATAL: shard {shard['shard_id']} has unexpected embedding_dimension")
        if shard["vector_dtype"] != "float32":
            raise SystemExit(f"FATAL: shard {shard['shard_id']} has unexpected vector_dtype")

    return root, shards


def read_and_verify_shard(root: Path, shard: dict) -> pa.Table:
    fp = root / shard["relative_output_path"]
    if not fp.is_file():
        raise SystemExit(f"FATAL: shard {shard['shard_id']} file not found: {fp}")
    raw = fp.read_bytes()
    if len(raw) != shard["bytes"]:
        raise SystemExit(f"FATAL: shard {shard['shard_id']} size {len(raw)} != manifest {shard['bytes']}")
    digest = sha256_bytes(raw)
    if digest != shard["sha256"]:
        raise SystemExit(f"FATAL: shard {shard['shard_id']} sha256 {digest} != manifest {shard['sha256']}")
    table = pq.read_table(pa.BufferReader(raw))
    if table.num_rows != shard["rows"]:
        raise SystemExit(f"FATAL: shard {shard['shard_id']} row count {table.num_rows} != manifest {shard['rows']}")
    return table


def load_checkpoint(checkpoint_path: Path) -> dict | None:
    if not checkpoint_path.is_file():
        return None
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


def checkpoint_identity() -> dict:
    return {
        "phase_4_1_config_hash": PHASE_4_1_CONFIG_HASH,
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "expected_row_count": EXPECTED_ROW_COUNT,
        "expected_shard_count": EXPECTED_SHARD_COUNT,
    }


def write_checkpoint(checkpoint_path: Path, completed_shard_ids: set[int]) -> None:
    payload = dict(checkpoint_identity())
    payload["completed_shard_ids"] = sorted(completed_shard_ids)
    tmp_path = checkpoint_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(checkpoint_path)


def ingest_shards(storage, root: Path, shards: list[dict], db_path: Path) -> tuple[object, dict]:
    checkpoint_path = db_path / CHECKPOINT_FILENAME
    checkpoint = load_checkpoint(checkpoint_path)
    identity = checkpoint_identity()

    if checkpoint is not None:
        for key, value in identity.items():
            if checkpoint.get(key) != value:
                raise SystemExit(
                    f"FATAL: existing checkpoint at {checkpoint_path} was built under a "
                    f"different identity ({key}={checkpoint.get(key)!r} != {value!r}) - "
                    f"refusing to resume onto a mismatched build."
                )
        completed = set(checkpoint["completed_shard_ids"])
    else:
        completed = set()

    db_exists = db_path.exists() and any(db_path.iterdir()) if db_path.exists() else False
    table = None
    if db_exists:
        db = open_database(db_path)
        existing_names = db.list_tables().tables
        if existing_names == [TABLE_NAME]:
            table = open_chunk_table(db)
            if checkpoint is None and table.count_rows() > 0:
                raise SystemExit(
                    f"FATAL: table '{TABLE_NAME}' at {db_path} already has "
                    f"{table.count_rows()} rows but no checkpoint exists - refusing to "
                    f"guess which shards it contains. Investigate manually."
                )
        elif existing_names:
            raise SystemExit(f"FATAL: {db_path} contains unexpected tables {existing_names} - refusing to proceed.")
    else:
        storage.ensure_dir(db_path)
        db = open_database(db_path)

    reference_schema = None
    if table is not None and table.count_rows() > 0:
        reference_schema = table.schema

    for shard in shards:
        shard_id = shard["shard_id"]
        if shard_id in completed:
            continue
        shard_table = read_and_verify_shard(root, shard)
        if reference_schema is None:
            reference_schema = shard_table.schema
        else:
            validate_shard_schema(shard_table, reference_schema=reference_schema)

        if table is None:
            table = create_chunk_table(db, shard_table)
        else:
            table.add(shard_table)

        completed.add(shard_id)
        write_checkpoint(checkpoint_path, completed)
        print(f"  ingested shard {shard_id:02d} ({shard['rows']:,} rows) - "
              f"{len(completed)}/{EXPECTED_SHARD_COUNT} shards, {table.count_rows():,} rows total")
        del shard_table

    return table, checkpoint_identity()


def deterministic_self_retrieval_samples(root: Path, shards_by_id: dict) -> list[tuple[str, np.ndarray]]:
    samples: list[tuple[str, np.ndarray]] = []
    for shard_id in SELF_RETRIEVAL_SAMPLE_SHARDS:
        shard = shards_by_id[shard_id]
        fp = root / shard["relative_output_path"]
        tbl = pq.read_table(fp, columns=["chunk_uid", "vector"])
        n = tbl.num_rows
        count = min(SELF_RETRIEVAL_SAMPLES_PER_SHARD, n)
        step = max(1, n // count)
        indices = list(range(0, n, step))[:count]
        uids = tbl.column("chunk_uid").to_pylist()
        vectors = tbl.column("vector").combine_chunks().values.to_numpy(zero_copy_only=False).reshape(-1, EMBEDDING_DIMENSION)
        for i in indices:
            samples.append((uids[i], vectors[i]))
    return samples


TIE_DISTANCE_TOLERANCE = 1e-6  # float32 epsilon (~1.19e-7) plus headroom


def self_retrieval_check(table, samples: list[tuple[str, np.ndarray]]) -> dict:
    """Self-retrieval at 10.5M rows can hit a GENUINE floating-point tie:
    two different chunk_uids with byte-identical text (verbatim boilerplate
    shared across affiliated filings - e.g. exhibit-index text repeated
    across a utility holding company's subsidiary 10-Ks) produce vectors
    that are float32-rounding-identical, so their cosine distance to the
    query is tied at exactly float32 epsilon (verified directly: observed
    ties were exactly +-1.1920928955078125e-07). Per this project's
    established convention ("if a genuine vector tie occurs, document it
    rather than silently weakening the test" - see
    project_plan/PHASE1_VECTOR_INDEX.md/Task 1.5 Step 27), such a tie
    counts as a PASS (the expected chunk_uid IS among the tied nearest
    neighbors - the mapping is not broken, duplicate content is), but is
    recorded explicitly in `anomalies` rather than silently absorbed into
    an undifferentiated pass count."""
    checked = 0
    passed = 0
    tied_pass_count = 0
    self_distances = []
    anomalies = []
    for expected_uid, vector in samples:
        checked += 1
        query_start = time.perf_counter()
        result = exact_cosine_search(table, vector, limit=5, expected_dimension=EMBEDDING_DIMENSION)
        print(f"  self-retrieval query {checked}/{len(samples)} "
              f"({time.perf_counter() - query_start:.1f}s)", flush=True)
        if result.num_rows == 0:
            anomalies.append({"chunk_uid": expected_uid, "issue": "no results"})
            continue
        uids = result.column("chunk_uid").to_pylist()
        dists = result.column("_distance").to_pylist()
        top_uid, top_dist = uids[0], dists[0]
        self_distances.append(top_dist)
        if top_uid == expected_uid:
            passed += 1
            continue
        tied_uids = {u for u, d in zip(uids, dists) if abs(d - top_dist) <= TIE_DISTANCE_TOLERANCE}
        if expected_uid in tied_uids:
            passed += 1
            tied_pass_count += 1
            anomalies.append({
                "chunk_uid": expected_uid,
                "note": "genuine floating-point tie with duplicate-text chunk(s) - PASS",
                "tied_with": sorted(tied_uids - {expected_uid}),
                "distance": top_dist,
            })
        else:
            anomalies.append({"chunk_uid": expected_uid, "got": top_uid, "distance": top_dist})
    return {
        "checked": checked,
        "passed": passed,
        "tied_duplicate_passes": tied_pass_count,
        "anomalies": anomalies,
        "self_distance_min": min(self_distances) if self_distances else None,
        "self_distance_max": max(self_distances) if self_distances else None,
    }


def search_latency_diagnostic(samples: list[tuple[str, np.ndarray]], table) -> dict:
    total_needed = DIAGNOSTIC_WARMUP_QUERIES + DIAGNOSTIC_QUERY_COUNT
    pool = samples[:total_needed] if len(samples) >= total_needed else samples
    for i, (_, vector) in enumerate(pool[:DIAGNOSTIC_WARMUP_QUERIES]):
        exact_cosine_search(table, vector, limit=DIAGNOSTIC_TOP_K, expected_dimension=EMBEDDING_DIMENSION)
        print(f"  diagnostic warm-up {i + 1}/{DIAGNOSTIC_WARMUP_QUERIES}", flush=True)

    latencies_ms = []
    for i, (_, vector) in enumerate(pool[DIAGNOSTIC_WARMUP_QUERIES:]):
        start = time.perf_counter()
        exact_cosine_search(table, vector, limit=DIAGNOSTIC_TOP_K, expected_dimension=EMBEDDING_DIMENSION)
        latencies_ms.append((time.perf_counter() - start) * 1000)
        print(f"  diagnostic query {i + 1}/{DIAGNOSTIC_QUERY_COUNT} ({latencies_ms[-1] / 1000:.1f}s)", flush=True)

    latencies_ms.sort()
    return {
        "label": "Phase 4.4 smoke diagnostic - not a production benchmark",
        "query_count": len(latencies_ms),
        "top_k": DIAGNOSTIC_TOP_K,
        "p50_ms": round(statistics.median(latencies_ms), 1) if latencies_ms else None,
        "p95_ms": round(latencies_ms[int(0.95 * (len(latencies_ms) - 1))], 1) if latencies_ms else None,
        "min_ms": round(min(latencies_ms), 1) if latencies_ms else None,
        "max_ms": round(max(latencies_ms), 1) if latencies_ms else None,
    }


def main() -> int:
    build_start = time.monotonic()
    storage = get_storage()

    print("Verifying Task 4.3 embedding manifest/validation...")
    root, shards = load_and_verify_manifest(storage)
    shards_by_id = {s["shard_id"]: s for s in shards}
    print(f"  manifest OK: {len(shards)} shards, {EXPECTED_ROW_COUNT:,} rows, manifest_sha256 verified")

    db_path = storage.index_dir_full(PHASE_4_1_CONFIG_HASH, CHUNK_CONFIG_HASH, MODEL_REPO, MODEL_REVISION)
    print(f"Ingesting into {db_path} ...")
    table, _ = ingest_shards(storage, root, shards, db_path)

    print("Validating table (row count, schema, no vector/ANN index)...")
    validate_chunk_table(table, expected_row_count=EXPECTED_ROW_COUNT)

    print("Building scalar indexes on cik/fiscal_year...")
    built = build_scalar_indexes(table)
    validate_scalar_indexes(table)
    print(f"  built: {built or '(already present)'}")

    build_time_s = time.monotonic() - build_start

    print("Running deterministic self-retrieval checks...")
    samples = deterministic_self_retrieval_samples(root, shards_by_id)
    self_retrieval = self_retrieval_check(table, samples)
    if self_retrieval["passed"] != self_retrieval["checked"]:
        raise SystemExit(
            f"FATAL: self-retrieval failed for "
            f"{self_retrieval['checked'] - self_retrieval['passed']} of {self_retrieval['checked']} "
            f"chunks: {self_retrieval['anomalies']}"
        )

    print("Running smoke search-latency diagnostic (exact-flat over 10.5M rows - expect multi-second queries)...")
    diagnostic = search_latency_diagnostic(samples, table)

    db_size_bytes = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())

    embedding_identity = QWEN3_EMBEDDING.embedding_identity()
    from src.artifacts.versioning import embedding_identity_hash as compute_embedding_identity_hash_value  # noqa: E402
    embedding_identity_hash_value = compute_embedding_identity_hash_value(embedding_identity)
    index_identity = compute_index_identity(
        chunk_schema_version=CHUNK_SCHEMA_VERSION, chunk_config_hash=CHUNK_CONFIG_HASH,
        embedding_identity_hash=embedding_identity_hash_value, distance_metric=DISTANCE_METRIC,
        index_type=INDEX_TYPE, table_name=TABLE_NAME,
    )
    index_identity_hash_value = compute_index_identity_hash(index_identity)

    config = {
        "schema_version": "1.0",
        "phase_4_1_config_hash": PHASE_4_1_CONFIG_HASH,
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "vector_dtype": "float32",
        "normalize_embeddings": True,
        "database_backend": "lancedb",
        "search_mode": "exact",
        "distance_metric": DISTANCE_METRIC,
        "table_name": TABLE_NAME,
        "column_policy": "all_24_columns",
        "scalar_index_columns": list(SCALAR_INDEX_COLUMNS),
        "scalar_index_type": "BTree",
        "no_ann_index": True,
        "no_quantization": True,
        "no_fts_bm25_production_index": True,
        "index_identity": index_identity,
        "index_identity_hash": index_identity_hash_value,
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "phase_4_1_config_hash": PHASE_4_1_CONFIG_HASH,
        "chunk_config_hash": CHUNK_CONFIG_HASH,
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "task_4_3_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "embedding_model": MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "embedding_identity_hash": embedding_identity_hash_value,
        "index_identity_hash": index_identity_hash_value,
        "vector_count": table.count_rows(),
        "vector_dimension": EMBEDDING_DIMENSION,
        "vector_dtype": "float32",
        "normalize_embeddings": True,
        "backend": "lancedb",
        "lancedb_version": __import__("lancedb").__version__,
        "search_mode": "exact",
        "distance_metric": DISTANCE_METRIC,
        "table_name": TABLE_NAME,
        "column_count": len(EXPECTED_COLUMNS),
        "shard_count_ingested": EXPECTED_SHARD_COUNT,
        "database_path": str(db_path.relative_to(storage.repo_root).as_posix()),
        "database_size_bytes": db_size_bytes,
        "build_runtime_seconds": round(build_time_s, 2),
        "vector_ann_indexes_created": 0,
        "scalar_indexes_created": sorted(SCALAR_INDEX_COLUMNS),
        "self_retrieval": self_retrieval,
        "search_diagnostic": diagnostic,
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Table '{TABLE_NAME}' at {db_path}: {table.count_rows():,} rows, "
          f"0 vector/ANN indexes, scalar indexes on {sorted(SCALAR_INDEX_COLUMNS)}")
    print(f"Self-retrieval: {self_retrieval['passed']}/{self_retrieval['checked']} passed")
    if diagnostic["query_count"]:
        print(f"Search diagnostic (top-{diagnostic['top_k']}, n={diagnostic['query_count']}): "
              f"p50={diagnostic['p50_ms']}ms p95={diagnostic['p95_ms']}ms")
    print(f"Build runtime: {build_time_s:.2f}s, database size: {db_size_bytes:,} bytes")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
