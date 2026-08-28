"""Task 1.4 - embed all Task 1.3 chunks with BAAI/bge-small-en-v1.5 on CUDA.

Reads artifacts/chunks/<chunk_config_hash>/chunks.parquet (frozen input,
never modified), embeds every chunk's `text` column using the passage
convention (raw text, no instruction, normalize_embeddings=True), and
writes one self-contained Parquet file (all 16 chunk columns + a 384-dim
float32 vector column) under
artifacts/embeddings/<chunk_config_hash>/<embedding_model>/.

No LanceDB, no retrieval, no model ablation, no quantization. All
embedding-contract decisions this script encodes were explicitly
user-approved (Task 1.4) - see project_plan/PHASE1_EMBEDDINGS.md.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
import torch  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.embeddings.bge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    EMBEDDING_DIMENSION,
    MODEL_REPO,
    MODEL_REVISION,
    QUERY_INSTRUCTION,
    VECTOR_DTYPE,
    encode_passages,
    load_model,
    validate_vectors,
)

EXPECTED_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
EXPECTED_CHUNK_COUNT = 162357
CHUNK_ARTIFACT_PATH = (
    Path("artifacts") / "chunks" / EXPECTED_CHUNK_CONFIG_HASH / "chunks.parquet"
)
CHUNK_SCHEMA_FIELDS: tuple[str, ...] = (
    "chunk_id", "document_id", "cik", "company", "form_type", "fiscal_year",
    "source", "source_filename", "source_split", "ordinal", "text",
    "token_count", "chunk_config_hash", "normalizer_version",
    "normalization_build_sha256", "development_manifest_sha256",
)

CONFIG_RELATIVE_PATH = Path("configs") / "embed_development_corpus.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_4_embedding_summary.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def verify_chunk_input(storage) -> pa.Table:
    chunk_path = storage.repo_root / CHUNK_ARTIFACT_PATH
    storage.require_file(chunk_path)
    table = pq.read_table(chunk_path)

    if table.num_rows != EXPECTED_CHUNK_COUNT:
        raise SystemExit(f"FATAL: chunks.parquet has {table.num_rows} rows, expected {EXPECTED_CHUNK_COUNT}")
    if list(table.schema.names) != list(CHUNK_SCHEMA_FIELDS):
        raise SystemExit(f"FATAL: unexpected chunk schema: {table.schema.names}")

    ids = table.column("chunk_id").to_pylist()
    if len(set(ids)) != len(ids):
        raise SystemExit("FATAL: duplicate chunk_id in chunks.parquet")

    hashes = set(table.column("chunk_config_hash").to_pylist())
    if hashes != {EXPECTED_CHUNK_CONFIG_HASH}:
        raise SystemExit(f"FATAL: unexpected chunk_config_hash values: {hashes}")

    texts = table.column("text").to_pylist()
    if any(not t or not t.strip() for t in texts):
        raise SystemExit("FATAL: chunks.parquet contains an empty text row")

    return table


def encode_with_oom_fallback(model, texts: list[str], initial_batch_size: int) -> tuple[np.ndarray, list[int]]:
    """Encodes `texts` in one call at `initial_batch_size`. On CUDA OOM,
    halves the batch size and retries (recording every batch size actually
    used) rather than silently continuing under the original provenance or
    falling back to CPU - per Task 1.4's approved OOM policy."""
    batch_sizes_used: list[int] = []
    batch_size = initial_batch_size
    while True:
        try:
            torch.cuda.empty_cache()
            vectors = encode_passages(model, texts, batch_size=batch_size)
            batch_sizes_used.append(batch_size)
            return vectors, batch_sizes_used
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size <= 1:
                raise
            batch_size = max(1, batch_size // 2)
            print(f"CUDA OOM - retrying with batch_size={batch_size}", file=sys.stderr)


def main() -> int:
    total_start = time.monotonic()
    storage = get_storage()

    chunk_table = verify_chunk_input(storage)
    development_manifest_sha256 = chunk_table.column("development_manifest_sha256")[0].as_py()
    normalization_build_sha256 = chunk_table.column("normalization_build_sha256")[0].as_py()
    normalizer_version = chunk_table.column("normalizer_version")[0].as_py()

    load_start = time.monotonic()
    model = load_model(device="cuda")
    load_time_s = time.monotonic() - load_start

    torch.cuda.reset_peak_memory_stats()

    texts = chunk_table.column("text").to_pylist()

    embed_start = time.monotonic()
    vectors, batch_sizes_used = encode_with_oom_fallback(model, texts, DEFAULT_BATCH_SIZE)
    embed_time_s = time.monotonic() - embed_start

    validate_vectors(vectors)
    if vectors.shape[0] != chunk_table.num_rows:
        raise SystemExit(f"FATAL: {vectors.shape[0]} vectors for {chunk_table.num_rows} chunks")

    peak_allocated_bytes = torch.cuda.max_memory_allocated()
    peak_reserved_bytes = torch.cuda.max_memory_reserved()

    write_start = time.monotonic()
    columns = {field: chunk_table.column(field) for field in CHUNK_SCHEMA_FIELDS}
    vector_type = pa.list_(pa.float32(), EMBEDDING_DIMENSION)
    vector_array = pa.FixedSizeListArray.from_arrays(
        pa.array(vectors.reshape(-1), type=pa.float32()), EMBEDDING_DIMENSION,
    )
    schema_fields = [chunk_table.schema.field(f) for f in CHUNK_SCHEMA_FIELDS]
    schema_fields.append(pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIMENSION)))
    schema = pa.schema(schema_fields)
    out_table = pa.table({**columns, "vector": vector_array}, schema=schema)

    out_dir = storage.embeddings_dir(EXPECTED_CHUNK_CONFIG_HASH, MODEL_REPO)

    if out_dir.exists():
        existing_files = list(out_dir.glob("*.parquet"))
        if existing_files:
            existing = pq.read_table(existing_files[0])
            if existing.num_rows != out_table.num_rows:
                raise SystemExit(
                    f"FATAL: {out_dir} already contains an embeddings artifact with "
                    f"{existing.num_rows} rows, current build produced {out_table.num_rows} - "
                    f"refusing to silently overwrite a conflicting build."
                )

    storage.ensure_dir(out_dir)
    out_path = out_dir / "embeddings.parquet"
    pq.write_table(out_table, out_path)
    write_time_s = time.monotonic() - write_start

    total_time_s = time.monotonic() - total_start
    artifact_size = out_path.stat().st_size

    config = {
        "schema_version": "1.0",
        "input_chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
        "input_chunk_artifact": str(CHUNK_ARTIFACT_PATH.as_posix()),
        "model_repository": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "passage_convention": "raw text, no instruction prefix",
        "query_convention": f"prepend QUERY_INSTRUCTION exactly once: {QUERY_INSTRUCTION!r}",
        "normalize_embeddings": True,
        "vector_dtype": str(np.dtype(VECTOR_DTYPE)),
        "device": "cuda",
        "batch_size": DEFAULT_BATCH_SIZE,
        "precision_policy": "full FP32 (no autocast)",
        "oom_fallback_policy": "halve batch size and retry, recording actual batch size(s) used",
        "artifact_format": "single Parquet file: 16 chunk columns + fixed_size_list<float32,384> vector column",
        "metadata_policy": "full self-contained copy of all 16 Task 1.3 chunk columns",
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    token_counts = chunk_table.column("token_count").to_pylist()
    total_tokens = sum(token_counts)
    chunks_per_sec = len(texts) / embed_time_s if embed_time_s > 0 else None
    tokens_per_sec = total_tokens / embed_time_s if embed_time_s > 0 else None

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "input_chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
        "input_row_count": chunk_table.num_rows,
        "development_manifest_sha256": development_manifest_sha256,
        "normalization_build_sha256": normalization_build_sha256,
        "normalizer_version": normalizer_version,
        "model_repository": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "query_convention": f"prepend: {QUERY_INSTRUCTION!r}",
        "passage_convention": "raw text, no instruction",
        "normalize_embeddings": True,
        "vector_dtype": str(np.dtype(VECTOR_DTYPE)),
        "batch_size_requested": DEFAULT_BATCH_SIZE,
        "batch_sizes_used": batch_sizes_used,
        "precision_policy": "full FP32",
        "device": "cuda",
        "gpu_name": torch.cuda.get_device_name(0),
        "vector_count": int(vectors.shape[0]),
        "artifact_path": str((Path("artifacts") / "embeddings" / EXPECTED_CHUNK_CONFIG_HASH
                               / MODEL_REPO.replace("/", "--") / "embeddings.parquet").as_posix()),
        "artifact_size_bytes": artifact_size,
        "performance": {
            "model_load_seconds": round(load_time_s, 2),
            "embedding_inference_seconds": round(embed_time_s, 2),
            "artifact_write_seconds": round(write_time_s, 2),
            "total_wall_seconds": round(total_time_s, 2),
            "chunks_per_second": round(chunks_per_sec, 2) if chunks_per_sec else None,
            "tokens_per_second": round(tokens_per_sec, 2) if tokens_per_sec else None,
        },
        "gpu_memory": {
            "peak_allocated_bytes": int(peak_allocated_bytes),
            "peak_reserved_bytes": int(peak_reserved_bytes),
        },
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Chunks embedded: {vectors.shape[0]}")
    print(f"Batch sizes used: {batch_sizes_used}")
    print(f"Model load: {load_time_s:.2f}s, embed: {embed_time_s:.2f}s, write: {write_time_s:.2f}s, "
          f"total: {total_time_s:.2f}s")
    print(f"Throughput: {chunks_per_sec:.1f} chunks/s" if chunks_per_sec else "")
    print(f"Peak GPU allocated: {peak_allocated_bytes/1e6:.1f} MB, reserved: {peak_reserved_bytes/1e6:.1f} MB")
    print(f"Artifact: {out_path} ({artifact_size:,} bytes)")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
