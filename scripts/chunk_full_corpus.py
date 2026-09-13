"""Task 4.2 - full-corpus chunking driver.

Scales the frozen Task 3.2 winner (fixed/256/0, chunk_config_hash
ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06) from the
1,493-document Phase 3 development corpus to the complete Task 4.1
full-corpus normalization output (91,086 documents). Reuses
src/chunk/fixed_window.py's tokenizer/window/offset logic and
src/chunk/metadata_schema.py's canonical Task 2.9 schema/identity
unmodified - this script only orchestrates I/O, sharding, and checkpointing.

Does NOT re-open the Phase 3 chunking decision, embed, index, retrieve, or
call an LLM. Read-only against the Task 4.1 artifact; writes only
artifacts/chunks_full/<phase_4_1_config_hash>/<chunk_config_hash>/
(git-ignored) and the small tracked config/result files.

Usage:
    python scripts/chunk_full_corpus.py --plan
    python scripts/chunk_full_corpus.py --pilot
    python scripts/chunk_full_corpus.py --run [--limit N]
    python scripts/chunk_full_corpus.py --status
    python scripts/chunk_full_corpus.py --verify-sample
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash, validate_sha256, ConfigHashError  # noqa: E402
from src.normalize.edgar_markdown import FULL_CORPUS_FRONTMATTER_KEYS  # noqa: E402
from src.chunk import metadata_schema as ms  # noqa: E402
from src.chunk.fixed_window import (  # noqa: E402
    parse_normalized_document,
    compute_token_windows,
    slice_chunk_text,
)

TASK = "phase_4_2_full_corpus_chunking"

CHUNK_CONFIG_PATH = REPO_ROOT / "configs" / "phase_3_2_chunk_A1.json"
EXPECTED_CHUNK_CONFIG_HASH = "ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06"

EXPECTED_PHASE_4_1_CONFIG_HASH = "754d9c898772c3326bfac21d7c508b37fd3dec6cb57320d081e024b0d653197f"
EXPECTED_PHASE_4_1_MANIFEST_SHA256 = "3ca76cfd6e789811012c60adb7ba7aa9c8c3d002547fbc5310da47481342f3f9"
EXPECTED_SOURCE_DOCUMENT_COUNT = 91086
EXPECTED_NORMALIZED_COUNT = 90239
EXPECTED_EMPTY_COUNT = 847

TARGET_ROWS_PER_SHARD = 200_000
PARQUET_COMPRESSION = "zstd"
MANIFEST_SCHEMA_VERSION = 1
PROGRESS_EVERY = 2000

CONFIG_RELATIVE_PATH = Path("configs") / "phase_4_2_full_corpus_chunking.json"
RESULT_RELATIVE_PATH = Path("results") / "phase_4_2_full_corpus_chunking.json"


class Task42Error(SystemExit):
    """Raised for a hard-stop condition - printed and exits nonzero."""


# --------------------------------------------------------------- provenance

def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


# --------------------------------------------------------------- Stage 3: frozen chunk semantics

def load_and_verify_chunk_config() -> dict:
    cfg = json.loads(CHUNK_CONFIG_PATH.read_text(encoding="utf-8"))
    recomputed = semantic_hash(cfg)
    if recomputed != EXPECTED_CHUNK_CONFIG_HASH:
        raise Task42Error(
            f"STOP - recomputed chunk_config_hash {recomputed} != frozen Task 3.2 winner "
            f"{EXPECTED_CHUNK_CONFIG_HASH}. The Phase 3 chunking decision must not change here."
        )
    if cfg["window_size_tokens"] != 256 or cfg["overlap_tokens"] != 0 or cfg["split_mode"] != "fixed":
        raise Task42Error("STOP - loaded config does not match the frozen 256/0/fixed winner")
    return cfg


def load_tokenizer(cfg: dict):
    from transformers import AutoTokenizer
    tk_cfg = cfg["tokenizer"]
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            tk_cfg["repo"], revision=tk_cfg["revision"], local_files_only=True,
        )
    except Exception as exc:
        raise Task42Error(
            f"STOP - frozen tokenizer {tk_cfg['repo']}@{tk_cfg['revision']} is not available "
            f"offline: {exc}. Never silently download a different revision."
        ) from exc
    if not tokenizer.is_fast:
        raise Task42Error("STOP - loaded tokenizer is not a fast tokenizer (offset mapping required)")
    return tokenizer


# --------------------------------------------------------------- Task 4.2 build identity

def build_phase_4_2_config(chunk_config_hash: str) -> dict:
    return {
        "task": TASK,
        "input_phase_4_1_config_hash": EXPECTED_PHASE_4_1_CONFIG_HASH,
        "input_phase_4_1_build_manifest_sha256": EXPECTED_PHASE_4_1_MANIFEST_SHA256,
        "normalizer_version": "phase1-minimal-v1",
        "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION,
        "chunk_config_hash": chunk_config_hash,
        "tokenizer_repository": "BAAI/bge-small-en-v1.5",
        "tokenizer_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        "output_format": "sharded Parquet, canonical Task 2.9 23-field schema (src.chunk.metadata_schema)",
        "shard_policy": {
            "target_rows_per_shard": TARGET_ROWS_PER_SHARD,
            "boundary_policy": "between documents only - one document's chunk sequence is never split across shards",
        },
        "parquet_compression": PARQUET_COMPRESSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "frontmatter_keys_source": "src.normalize.edgar_markdown.FULL_CORPUS_FRONTMATTER_KEYS",
        "section_metadata_policy": (
            "split_mode=fixed (non-section-aware) - section_id/section_title are always NULL; "
            "no unambiguous single-section mapping exists for a chunk that may cross Item boundaries"
        ),
        "offset_policy": (
            "char_start/char_end always populated for non-empty chunks, half-open [start, end), "
            "exact round-trip against the Task 4.1 normalized body text, verified per chunk "
            "(offset-mapping slicing, reused unmodified from Task 1.3/3.2)"
        ),
        "accession_period_filed_sic_policy": "always NULL for edgar_corpus - unchanged from Task 2.9",
        "company_policy": "reused verbatim from Task 4.1 frontmatter (nullable, never fabricated)",
    }


def phase_4_2_build_config_hash(cfg: dict) -> str:
    return semantic_hash(cfg)


# --------------------------------------------------------------- Stage 2: bind to Task 4.1

def verify_manifest_hash(data: bytes, expected: str) -> str:
    recomputed = hashlib.sha256(data).hexdigest()
    if recomputed != expected:
        raise Task42Error(
            f"STOP - Task 4.1 build manifest recomputes to {recomputed}, expected "
            f"{expected}. Task 4.1's input identity has changed."
        )
    return recomputed


def load_task41_manifest(storage) -> tuple[list[dict], str]:
    manifest_path = storage.normalized_dir_for_config(EXPECTED_PHASE_4_1_CONFIG_HASH) / "manifest.jsonl"
    storage.require_file(manifest_path)
    data = manifest_path.read_bytes()
    recomputed = verify_manifest_hash(data, EXPECTED_PHASE_4_1_MANIFEST_SHA256)
    entries = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    return entries, recomputed


def assert_task41_manifest_healthy(entries: list[dict]) -> None:
    if len(entries) != EXPECTED_SOURCE_DOCUMENT_COUNT:
        raise Task42Error(f"STOP - Task 4.1 manifest has {len(entries)} entries, expected {EXPECTED_SOURCE_DOCUMENT_COUNT}")
    ids = [e["document_id"] for e in entries]
    if len(set(ids)) != len(ids):
        raise Task42Error("STOP - duplicate document_id in Task 4.1 manifest")
    normalized = sum(1 for e in entries if e["status"] == "NORMALIZED")
    empty = sum(1 for e in entries if e["status"] == "VALID_EMPTY_SOURCE")
    failed = sum(1 for e in entries if e["status"] not in ("NORMALIZED", "VALID_EMPTY_SOURCE"))
    if normalized != EXPECTED_NORMALIZED_COUNT or empty != EXPECTED_EMPTY_COUNT or failed != 0:
        raise Task42Error(
            f"STOP - Task 4.1 outcome counts changed: normalized={normalized} (expected "
            f"{EXPECTED_NORMALIZED_COUNT}), empty={empty} (expected {EXPECTED_EMPTY_COUNT}), "
            f"non-accounted={failed} (expected 0)"
        )


def resolve_safe_input_path(root: Path, relative_path: str) -> Path:
    """Rejects path traversal outright - never silently sanitized."""
    if relative_path is None:
        raise Task42Error("STOP - manifest entry has no relative_output_path")
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise Task42Error(f"STOP - path traversal: {relative_path!r} escapes Task 4.1 artifact root")
    return candidate


# --------------------------------------------------------------- pilot sample

def select_pilot_sample(entries: list[dict]) -> list[str]:
    by_id = {e["document_id"]: e for e in entries}
    pilot_ids: set[str] = set()

    year_bands = ((1993, 1999), (2000, 2009), (2010, 2019), (2020, 2020))
    splits = ("train", "test", "validation")
    for split in splits:
        for lo, hi in year_bands:
            candidates = sorted(
                e["document_id"] for e in entries
                if e["status"] == "NORMALIZED" and e["source_split"] == split and lo <= e["fiscal_year"] <= hi
            )
            if candidates:
                pilot_ids.add(candidates[0])

    normalized_ids = sorted(e["document_id"] for e in entries if e["status"] == "NORMALIZED")
    empty_ids = sorted(e["document_id"] for e in entries if e["status"] == "VALID_EMPTY_SOURCE")
    pilot_ids.update(empty_ids[:5])

    return sorted(pilot_ids), by_id, normalized_ids


def pick_size_extremes(storage, normalized_ids: list[str], by_id: dict, root: Path, sample_cap: int = 4000) -> tuple[str, str]:
    """Largest/smallest normalized documents by on-disk byte size (a stat()
    call, never a full read) - sampled deterministically (every Nth id) when
    the corpus is large, to keep pilot selection itself cheap."""
    step = max(1, len(normalized_ids) // sample_cap)
    sampled = normalized_ids[::step]
    sized = []
    for doc_id in sampled:
        path = resolve_safe_input_path(root, by_id[doc_id]["relative_output_path"])
        sized.append((path.stat().st_size, doc_id))
    sized.sort()
    return sized[0][1], sized[-1][1]


# --------------------------------------------------------------- chunk one document

def chunk_one_document(*, document_id: str, fields: dict, body_text: str, tokenizer,
                        window_size: int, stride: int, chunk_config_hash: str,
                        chunk_schema_version: int) -> list[dict]:
    if not body_text:
        return []
    encoding = tokenizer(body_text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoding["offset_mapping"]
    windows = compute_token_windows(len(offsets), window_size=window_size, stride=stride)
    records: list[dict] = []
    for ordinal, (start_idx, end_idx) in enumerate(windows):
        char_start = offsets[start_idx][0]
        char_end = offsets[end_idx - 1][1]
        text = slice_chunk_text(body_text, offsets, start_idx, end_idx)
        if body_text[char_start:char_end] != text:
            raise ValueError(f"{document_id}: chunk {ordinal} offsets do not round-trip")
        chunk_local_id = ms.build_chunk_local_id(ordinal)
        chunk_uid = ms.build_chunk_uid(
            chunk_schema_version=chunk_schema_version, source="edgar_corpus", document_id=document_id,
            chunk_config_hash=chunk_config_hash, chunk_local_id=chunk_local_id,
        )
        record = {
            "chunk_schema_version": chunk_schema_version,
            "chunk_uid": chunk_uid,
            "chunk_local_id": chunk_local_id,
            "document_id": document_id,
            "accession": None,
            "cik": fields["cik"],
            "company": fields["company"],
            "form_type": fields["form_type"],
            "fiscal_year": fields["fiscal_year"],
            "period_end": None,
            "filed_date": None,
            "sic": None,
            "section_id": None,
            "section_title": None,
            "ordinal": ordinal,
            "char_start": char_start,
            "char_end": char_end,
            "content_type": "prose",
            "table_id": None,
            "source": "edgar_corpus",
            "text": text,
            "token_count": end_idx - start_idx,
            "chunk_config_hash": chunk_config_hash,
        }
        ms.validate_chunk_record(record)
        records.append(record)
    return records


def read_and_verify_document(root: Path, entry: dict) -> tuple[dict, str]:
    """Reads one Task 4.1 document, verifies its content hash against the
    frozen manifest, and returns (frontmatter_fields, body_text). Raises on
    any mismatch - a tampered/corrupted Task 4.1 file is never silently
    chunked."""
    path = resolve_safe_input_path(root, entry["relative_output_path"])
    data = path.read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != entry["content_sha256"]:
        raise ValueError(
            f"{entry['document_id']}: content hash mismatch (Task 4.1 manifest says "
            f"{entry['content_sha256']}, on-disk file hashes to {actual_hash})"
        )
    text = data.decode("utf-8")
    fields, body = parse_normalized_document(text, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    if fields["document_id"] != entry["document_id"]:
        raise ValueError(f"{entry['document_id']}: frontmatter document_id mismatch")
    return fields, body


# --------------------------------------------------------------- checkpoint

def checkpoint_path(out_dir: Path) -> Path:
    return out_dir / "build_state.jsonl"


def append_line(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()


def read_checkpoint(path: Path) -> tuple[dict | None, list[dict], dict[str, dict]]:
    """Returns (header, shard_records, doc_records_by_id). A malformed
    trailing line (a crash mid-append) is dropped, not accepted; a
    malformed non-trailing line is a hard corruption STOP."""
    if not path.exists():
        return None, [], {}
    lines = path.read_text(encoding="utf-8").splitlines()
    header = None
    shard_records: list[dict] = []
    doc_records: dict[str, dict] = {}
    for i, line in enumerate(lines):
        is_last = i == len(lines) - 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if is_last:
                break
            raise Task42Error(f"FATAL - checkpoint state appears corrupt at line {i + 1} of {path}")
        rt = obj.get("record_type")
        if rt == "header":
            header = obj
        elif rt == "shard":
            shard_records.append(obj)
        elif rt == "doc":
            doc_records[obj["document_id"]] = obj
        else:
            raise Task42Error(f"FATAL - checkpoint state appears corrupt (unknown record_type) at line {i + 1} of {path}")
    return header, shard_records, doc_records


def assert_checkpoint_resumable(header: dict | None, expected: dict, ckpt_path: Path) -> None:
    if header is None:
        return
    for key in ("phase_4_1_config_hash", "phase_4_1_build_manifest_sha256",
                "phase_4_2_build_config_hash", "chunk_schema_version", "chunk_config_hash"):
        if header.get(key) != expected[key]:
            raise Task42Error(
                f"FATAL - checkpoint at {ckpt_path} has {key}={header.get(key)!r}, "
                f"current build expects {expected[key]!r}. Refusing to resume under a different identity."
            )


def verify_shards(out_dir: Path, shard_records: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Re-hashes every shard file on disk before trusting it. Returns
    (valid_shards_by_id, completed_chunked_docs_by_id) - a corrupted or
    missing shard file invalidates every document it claims to contain,
    which will then be reprocessed rather than silently accepted."""
    valid_shards: dict[str, dict] = {}
    completed: dict[str, dict] = {}
    for rec in shard_records:
        path = out_dir / rec["relative_path"]
        if not path.is_file():
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != rec["sha256"]:
            continue
        valid_shards[rec["shard_id"]] = rec
        for d in rec["documents"]:
            completed[d["document_id"]] = {"shard_id": rec["shard_id"], "chunk_count": d["chunk_count"]}
    return valid_shards, completed


def publish_shard(out_dir: Path, shard_index: int, rows: list[dict]) -> dict:
    shard_id = f"part-{shard_index:05d}"
    relative_path = f"shards/{shard_id}.parquet"
    final_path = out_dir / relative_path
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(".parquet.tmp")

    table = pa.Table.from_pylist(rows, schema=ms.canonical_pyarrow_schema())
    pq.write_table(table, tmp_path, compression=PARQUET_COMPRESSION)
    sha256 = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
    os.replace(tmp_path, final_path)

    doc_chunk_counts: dict[str, int] = {}
    for r in rows:
        doc_chunk_counts[r["document_id"]] = doc_chunk_counts.get(r["document_id"], 0) + 1
    documents = [{"document_id": d, "chunk_count": c} for d, c in doc_chunk_counts.items()]

    return {
        "record_type": "shard",
        "shard_id": shard_id,
        "relative_path": relative_path,
        "row_count": len(rows),
        "sha256": sha256,
        "first_document_id": rows[0]["document_id"],
        "last_document_id": rows[-1]["document_id"],
        "chunk_config_hash": rows[0]["chunk_config_hash"],
        "chunk_schema_version": rows[0]["chunk_schema_version"],
        "documents": documents,
    }


# --------------------------------------------------------------- main run

def run(storage, entries: list[dict], out_dir: Path, expected_identity: dict, tokenizer,
        window_size: int, stride: int, chunk_config_hash: str, chunk_schema_version: int,
        task41_root: Path, limit: int | None) -> dict:
    storage.ensure_dir(out_dir)
    ckpt_path = checkpoint_path(out_dir)

    header, shard_records, doc_records = read_checkpoint(ckpt_path)
    assert_checkpoint_resumable(header, expected_identity, ckpt_path)
    if header is None:
        header = {"record_type": "header", "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **expected_identity}
        append_line(ckpt_path, header)

    valid_shards, chunked_completed = verify_shards(out_dir, shard_records)
    next_shard_index = len(shard_records)  # monotonic - even an invalidated shard's index is never reused

    completed: set[str] = set(chunked_completed.keys())
    for doc_id, rec in doc_records.items():
        if rec["status"] == "VALID_EMPTY_SOURCE":
            completed.add(doc_id)
        # FAILED is never treated as completed - always retried.

    pending = [e for e in entries if e["document_id"] not in completed]
    if limit is not None:
        pending = pending[:limit]

    try:
        import psutil
        proc = psutil.Process()
        peak_rss = proc.memory_info().rss
    except Exception:
        proc = None
        peak_rss = None

    start = time.monotonic()
    processed_this_run = 0
    failures_this_run = 0
    chunks_this_run = 0
    total_done = len(completed)
    total_units = len(entries)

    buffer: list[dict] = []

    def flush_shard():
        nonlocal next_shard_index, buffer
        if not buffer:
            return
        shard_rec = publish_shard(out_dir, next_shard_index, buffer)
        append_line(ckpt_path, shard_rec)
        next_shard_index += 1
        buffer = []

    for entry in pending:
        doc_id = entry["document_id"]
        if entry["status"] == "VALID_EMPTY_SOURCE":
            try:
                _fields, body = read_and_verify_document(task41_root, entry)
                if body:
                    raise ValueError(f"{doc_id}: manifest says VALID_EMPTY_SOURCE but body is non-empty")
                append_line(ckpt_path, {"record_type": "doc", "document_id": doc_id, "status": "VALID_EMPTY_SOURCE",
                                         "shard_id": None, "chunk_count": 0, "error_class": None, "error_summary": None})
            except Exception as exc:
                append_line(ckpt_path, {"record_type": "doc", "document_id": doc_id, "status": "FAILED",
                                         "shard_id": None, "chunk_count": None,
                                         "error_class": type(exc).__name__, "error_summary": str(exc)[:300]})
                failures_this_run += 1
            processed_this_run += 1
            total_done += 1 if entry["status"] == "VALID_EMPTY_SOURCE" else 0
        else:
            try:
                fields, body = read_and_verify_document(task41_root, entry)
                if not body:
                    raise ValueError(f"{doc_id}: manifest says NORMALIZED but body is empty")
                records = chunk_one_document(
                    document_id=doc_id, fields=fields, body_text=body, tokenizer=tokenizer,
                    window_size=window_size, stride=stride, chunk_config_hash=chunk_config_hash,
                    chunk_schema_version=chunk_schema_version,
                )
                if not records:
                    raise ValueError(f"{doc_id}: NORMALIZED document produced zero chunks")
                buffer.extend(records)
                chunks_this_run += len(records)
                total_done += 1
                if len(buffer) >= TARGET_ROWS_PER_SHARD:
                    flush_shard()
            except Exception as exc:
                append_line(ckpt_path, {"record_type": "doc", "document_id": doc_id, "status": "FAILED",
                                         "shard_id": None, "chunk_count": None,
                                         "error_class": type(exc).__name__, "error_summary": str(exc)[:300]})
                failures_this_run += 1
            processed_this_run += 1

        if proc is not None and processed_this_run % 200 == 0:
            try:
                peak_rss = max(peak_rss, proc.memory_info().rss)
            except Exception:
                pass

        if processed_this_run % PROGRESS_EVERY == 0 or processed_this_run == len(pending):
            elapsed = time.monotonic() - start
            rate = processed_this_run / elapsed if elapsed > 0 else 0.0
            remaining = total_units - total_done
            eta = remaining / rate if rate > 0 else float("inf")
            print(
                f"[CHUNK] documents: {total_done:>7,} / {total_units:,} ({100.0 * total_done / total_units:6.2f}%)   "
                f"chunks_this_run={chunks_this_run:,}   docs/s={rate:6.2f}   "
                f"elapsed={elapsed:8.1f}s   ETA={eta:8.1f}s   failures_this_run={failures_this_run}"
            )

    flush_shard()  # publish the final partial shard, if any

    return {
        "processed_this_run": processed_this_run,
        "failures_this_run": failures_this_run,
        "chunks_this_run": chunks_this_run,
        "elapsed_seconds_this_run": time.monotonic() - start,
        "peak_rss_bytes": peak_rss,
        "total_units": total_units,
        "total_done_after_run": total_done,
    }


def summarize_final(out_dir: Path, entries: list[dict]) -> dict:
    _header, shard_records, doc_records = read_checkpoint(checkpoint_path(out_dir))
    valid_shards, chunked_completed = verify_shards(out_dir, shard_records)

    all_ids = {e["document_id"] for e in entries}
    empty_completed = {d for d, r in doc_records.items() if r["status"] == "VALID_EMPTY_SOURCE"}
    failed_ids = sorted(
        d for d, r in doc_records.items()
        if r["status"] == "FAILED" and d not in chunked_completed and d not in empty_completed
    )
    accounted = set(chunked_completed.keys()) | empty_completed | set(failed_ids)
    missing = sorted(all_ids - accounted)

    total_chunks = sum(v["row_count"] for v in valid_shards.values())
    return {
        "documents_with_chunks": len(chunked_completed),
        "documents_without_chunks": len(empty_completed),
        "failed_count": len(failed_ids),
        "failed_sample": failed_ids[:10],
        "missing_count": len(missing),
        "missing_sample": missing[:10],
        "total_chunk_count": total_chunks,
        "shard_count": len(valid_shards),
    }


# --------------------------------------------------------------- Stage 8: full-corpus validation

def validate_full_corpus(out_dir: Path, entries: list[dict]) -> dict:
    """Streams every shard exactly once (never all 10M+ rows in RAM at
    once as a single table) and checks every global invariant Stage 8
    requires. Returns a dict of violation counts - all must be 0 for the
    build to be COMPLETE."""
    _header, shard_records, doc_records = read_checkpoint(checkpoint_path(out_dir))
    valid_shards, chunked_completed = verify_shards(out_dir, shard_records)
    empty_completed = {d for d, r in doc_records.items() if r["status"] == "VALID_EMPTY_SOURCE"}

    all_manifest_ids = {e["document_id"] for e in entries}
    by_id = {e["document_id"]: e for e in entries}

    seen_chunk_uids: set[str] = set()
    duplicate_chunk_uid_count = 0
    wrong_chunk_config_hash_rows = 0
    wrong_schema_version_rows = 0
    wrong_source_rows = 0
    token_count_gt_256 = 0
    token_count_le_0 = 0
    non_contiguous_ordinal_docs = 0
    extra_document_ids: set[str] = set()
    computed_doc_chunk_counts: dict[str, int] = {}

    for shard_id in sorted(valid_shards.keys()):
        rec = valid_shards[shard_id]
        table = pq.read_table(out_dir / rec["relative_path"])
        rows = table.to_pylist()
        by_doc: dict[str, list[dict]] = {}
        for r in rows:
            by_doc.setdefault(r["document_id"], []).append(r)
            uid = r["chunk_uid"]
            if uid in seen_chunk_uids:
                duplicate_chunk_uid_count += 1
            seen_chunk_uids.add(uid)
            if r["chunk_config_hash"] != EXPECTED_CHUNK_CONFIG_HASH:
                wrong_chunk_config_hash_rows += 1
            if r["chunk_schema_version"] != ms.CHUNK_SCHEMA_VERSION:
                wrong_schema_version_rows += 1
            if r["source"] != "edgar_corpus":
                wrong_source_rows += 1
            if r["token_count"] > 256:
                token_count_gt_256 += 1
            if r["token_count"] <= 0:
                token_count_le_0 += 1
            if r["document_id"] not in all_manifest_ids:
                extra_document_ids.add(r["document_id"])

        for doc_id, doc_rows in by_doc.items():
            computed_doc_chunk_counts[doc_id] = computed_doc_chunk_counts.get(doc_id, 0) + len(doc_rows)
            ordinals = sorted(r["ordinal"] for r in doc_rows)
            if ordinals != list(range(len(ordinals))):
                non_contiguous_ordinal_docs += 1

    unexpected_zero_chunk = 0
    missing_from_manifest = []
    for e in entries:
        doc_id = e["document_id"]
        if e["status"] == "NORMALIZED":
            if computed_doc_chunk_counts.get(doc_id, 0) <= 0:
                unexpected_zero_chunk += 1
        elif e["status"] == "VALID_EMPTY_SOURCE":
            if computed_doc_chunk_counts.get(doc_id, 0) != 0:
                unexpected_zero_chunk += 1
        if doc_id not in computed_doc_chunk_counts and doc_id not in empty_completed:
            missing_from_manifest.append(doc_id)

    sum_shard_row_counts = sum(v["row_count"] for v in valid_shards.values())
    sum_document_chunk_counts = sum(computed_doc_chunk_counts.values())

    return {
        "source_documents": len(entries),
        "documents_accounted_for": len(computed_doc_chunk_counts) + len(empty_completed),
        "expected_valid_empty_documents": EXPECTED_EMPTY_COUNT,
        "valid_empty_documents_found": len(empty_completed),
        "unexpected_zero_chunk_document_count": unexpected_zero_chunk,
        "failed_document_count": sum(1 for r in doc_records.values() if r["status"] == "FAILED"),
        "duplicate_chunk_uid_count": duplicate_chunk_uid_count,
        "duplicate_document_id_count": 0,  # entries themselves already asserted unique at load time
        "wrong_chunk_config_hash_rows": wrong_chunk_config_hash_rows,
        "wrong_schema_version_rows": wrong_schema_version_rows,
        "wrong_source_rows": wrong_source_rows,
        "token_count_gt_256": token_count_gt_256,
        "token_count_le_0": token_count_le_0,
        "non_contiguous_ordinal_docs": non_contiguous_ordinal_docs,
        "extra_document_id_count": len(extra_document_ids),
        "missing_from_manifest_count": len(missing_from_manifest),
        "missing_from_manifest_sample": missing_from_manifest[:10],
        "total_unique_chunk_uids": len(seen_chunk_uids),
        "sum_shard_row_counts": sum_shard_row_counts,
        "sum_document_chunk_counts": sum_document_chunk_counts,
        "row_counts_reconcile": sum_shard_row_counts == sum_document_chunk_counts,
        "shard_hash_mismatch_count": len(shard_records) - len(valid_shards),
    }


# --------------------------------------------------------------- Stage 9: sample quality inspection

def sample_quality_inspection(storage, out_dir: Path, entries: list[dict], task41_root: Path,
                               doc_manifest_path: Path) -> dict:
    """Traces a deterministic sample end-to-end: Task 4.1 manifest entry ->
    normalized file/body -> selected chunk rows -> chunk_local_id/chunk_uid
    -> char offsets -> Task 4.2 document manifest -> shard manifest."""
    pilot_ids, by_id, normalized_ids = select_pilot_sample(entries)
    smallest, largest = pick_size_extremes(storage, normalized_ids, by_id, task41_root)
    company_populated = next((d for d in normalized_ids if by_id[d].get("cik") and True), None)
    sample_ids = sorted(set(pilot_ids) | {smallest, largest})

    doc_manifest = pq.read_table(doc_manifest_path).to_pylist()
    doc_manifest_by_id = {r["document_id"]: r for r in doc_manifest}

    _header, shard_records, _doc_records = read_checkpoint(checkpoint_path(out_dir))
    valid_shards, _completed = verify_shards(out_dir, shard_records)
    shard_table_cache: dict[str, list[dict]] = {}

    failures = []
    checked = 0
    for doc_id in sample_ids:
        entry = by_id[doc_id]
        checked += 1
        try:
            dm_row = doc_manifest_by_id.get(doc_id)
            if dm_row is None:
                raise ValueError("missing from document_manifest")
            if entry["status"] == "VALID_EMPTY_SOURCE":
                if dm_row["status"] != "VALID_EMPTY_SOURCE" or dm_row["chunk_count"] != 0:
                    raise ValueError(f"empty-source document manifest mismatch: {dm_row}")
                continue
            if dm_row["status"] != "CHUNKED" or not dm_row["chunk_count"]:
                raise ValueError(f"non-empty document has no chunks in document_manifest: {dm_row}")
            shard_id = dm_row["shard_id"]
            if shard_id not in valid_shards:
                raise ValueError(f"document's shard {shard_id!r} is not a currently-valid shard")
            if shard_id not in shard_table_cache:
                shard_table_cache[shard_id] = pq.read_table(out_dir / valid_shards[shard_id]["relative_path"]).to_pylist()
            doc_rows = [r for r in shard_table_cache[shard_id] if r["document_id"] == doc_id]
            if len(doc_rows) != dm_row["chunk_count"]:
                raise ValueError(f"shard row count for {doc_id} ({len(doc_rows)}) != document_manifest chunk_count ({dm_row['chunk_count']})")
            doc_rows.sort(key=lambda r: r["ordinal"])

            fields, body = read_and_verify_document(task41_root, entry)
            for r in doc_rows:
                expected_local_id = ms.build_chunk_local_id(r["ordinal"])
                if r["chunk_local_id"] != expected_local_id:
                    raise ValueError(f"chunk_local_id mismatch at ordinal {r['ordinal']}")
                expected_uid = ms.build_chunk_uid(
                    chunk_schema_version=r["chunk_schema_version"], source=r["source"], document_id=doc_id,
                    chunk_config_hash=r["chunk_config_hash"], chunk_local_id=r["chunk_local_id"],
                )
                if r["chunk_uid"] != expected_uid:
                    raise ValueError(f"chunk_uid mismatch at ordinal {r['ordinal']}")
                if body[r["char_start"]:r["char_end"]] != r["text"]:
                    raise ValueError(f"char offset round-trip failed at ordinal {r['ordinal']}")
        except Exception as exc:
            failures.append({"document_id": doc_id, "error": str(exc)[:300]})

    return {"sample_check_count": checked, "sample_check_failures": failures, "sample_ids": sample_ids}


# --------------------------------------------------------------- Stage 10: frozen manifests

def build_document_manifest(out_dir: Path, entries: list[dict]) -> tuple[Path, str]:
    _header, shard_records, doc_records = read_checkpoint(checkpoint_path(out_dir))
    valid_shards, chunked_completed = verify_shards(out_dir, shard_records)
    empty_completed = {d for d, r in doc_records.items() if r["status"] == "VALID_EMPTY_SOURCE"}

    rows = []
    for e in sorted(entries, key=lambda x: x["document_id"]):
        doc_id = e["document_id"]
        if doc_id in chunked_completed:
            info = chunked_completed[doc_id]
            rows.append({"document_id": doc_id, "status": "CHUNKED", "shard_id": info["shard_id"], "chunk_count": info["chunk_count"]})
        elif doc_id in empty_completed:
            rows.append({"document_id": doc_id, "status": "VALID_EMPTY_SOURCE", "shard_id": None, "chunk_count": 0})
        else:
            rows.append({"document_id": doc_id, "status": "PENDING_OR_FAILED", "shard_id": None, "chunk_count": None})

    path = out_dir / "document_manifest.parquet"
    schema = pa.schema([
        pa.field("document_id", pa.string(), nullable=False),
        pa.field("status", pa.string(), nullable=False),
        pa.field("shard_id", pa.string(), nullable=True),
        pa.field("chunk_count", pa.int64(), nullable=True),
    ])
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression=PARQUET_COMPRESSION)
    doc_manifest_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, doc_manifest_sha256


def build_shard_manifest(out_dir: Path) -> tuple[Path, str]:
    _header, shard_records, _doc_records = read_checkpoint(checkpoint_path(out_dir))
    valid_shards, _ = verify_shards(out_dir, shard_records)
    shards = []
    for shard_id in sorted(valid_shards.keys()):
        rec = valid_shards[shard_id]
        shards.append({
            "shard_id": rec["shard_id"], "relative_path": rec["relative_path"], "row_count": rec["row_count"],
            "sha256": rec["sha256"], "first_document_id": rec["first_document_id"],
            "last_document_id": rec["last_document_id"], "chunk_config_hash": rec["chunk_config_hash"],
            "chunk_schema_version": rec["chunk_schema_version"],
        })
    payload = {"manifest_schema_version": MANIFEST_SCHEMA_VERSION, "shards": shards}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path = out_dir / "shard_manifest.json"
    data = text.encode("utf-8")
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def write_tracked_config(storage, cfg: dict, cfg_hash: str) -> Path:
    path = storage.repo_root / CONFIG_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"phase_4_2_build_config_hash": cfg_hash, "config": cfg}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_tracked_result(storage, *, cfg_hash: str, out_dir: Path, entries: list[dict],
                          summary: dict, run_stats: dict, doc_manifest_sha256: str,
                          shard_manifest_sha256: str, validation: dict, sample_check: dict) -> Path:
    validation_ok = (
        validation["duplicate_chunk_uid_count"] == 0
        and validation["missing_from_manifest_count"] == 0
        and validation["extra_document_id_count"] == 0
        and validation["unexpected_zero_chunk_document_count"] == 0
        and validation["token_count_gt_256"] == 0
        and validation["token_count_le_0"] == 0
        and validation["wrong_chunk_config_hash_rows"] == 0
        and validation["wrong_schema_version_rows"] == 0
        and validation["wrong_source_rows"] == 0
        and validation["non_contiguous_ordinal_docs"] == 0
        and validation["row_counts_reconcile"]
        and validation["shard_hash_mismatch_count"] == 0
    )
    complete = summary["missing_count"] == 0 and summary["failed_count"] == 0 and validation_ok
    result = {
        "task": TASK,
        "status": "COMPLETE" if complete else "IN_PROGRESS",
        "git_sha": git_sha(),
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

        "input": {
            "phase_4_1_config_hash": EXPECTED_PHASE_4_1_CONFIG_HASH,
            "phase_4_1_build_manifest_sha256": EXPECTED_PHASE_4_1_MANIFEST_SHA256,
            "normalizer_version": "phase1-minimal-v1",
            "source_document_count": len(entries),
            "normalized_nonempty_count": EXPECTED_NORMALIZED_COUNT,
            "valid_empty_source_count": EXPECTED_EMPTY_COUNT,
        },
        "chunking": {
            "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION,
            "chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
            "split_mode": "fixed", "window_size_tokens": 256, "overlap_tokens": 0, "stride_tokens": 256,
            "tokenizer_repository": "BAAI/bge-small-en-v1.5",
            "tokenizer_revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        },
        "build": {
            "phase_4_2_build_config_hash": cfg_hash,
            "artifact_root": str(out_dir.relative_to(storage.repo_root).as_posix()),
            "shard_count": summary["shard_count"],
            "target_rows_per_shard": TARGET_ROWS_PER_SHARD,
            "parquet_compression": PARQUET_COMPRESSION,
            "document_manifest_sha256": doc_manifest_sha256,
            "shard_manifest_sha256": shard_manifest_sha256,
            "total_chunk_count": summary["total_chunk_count"],
            "documents_with_chunks": summary["documents_with_chunks"],
            "documents_without_chunks": summary["documents_without_chunks"],
            "failed_document_count": summary["failed_count"],
            "elapsed_seconds_last_run": run_stats.get("elapsed_seconds_this_run"),
            "documents_per_second_last_run": (
                run_stats["processed_this_run"] / run_stats["elapsed_seconds_this_run"]
                if run_stats.get("elapsed_seconds_this_run") else None
            ),
            "peak_rss_bytes_last_run": run_stats.get("peak_rss_bytes"),
        },
        "validation": {
            "duplicate_chunk_uid_count": validation["duplicate_chunk_uid_count"],
            "missing_document_count": validation["missing_from_manifest_count"],
            "extra_document_count": validation["extra_document_id_count"],
            "unexpected_zero_chunk_document_count": validation["unexpected_zero_chunk_document_count"],
            "token_count_violation_count": validation["token_count_gt_256"] + validation["token_count_le_0"],
            "schema_violation_count": (
                validation["wrong_chunk_config_hash_rows"] + validation["wrong_schema_version_rows"]
                + validation["wrong_source_rows"] + validation["non_contiguous_ordinal_docs"]
            ),
            "shard_hash_mismatch_count": validation["shard_hash_mismatch_count"],
            "row_counts_reconcile": validation["row_counts_reconcile"],
            "total_unique_chunk_uids": validation["total_unique_chunk_uids"],
            "sample_check_count": sample_check["sample_check_count"],
            "sample_check_failures": sample_check["sample_check_failures"],
        },
        "protected_test": {"opened": False, "official_runs_used": 0},
        "paid_api_calls": 0,
        "gpu_used": False,
    }
    path = storage.repo_root / RESULT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------- CLI

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--verify-sample", action="store_true")
    args = parser.parse_args()

    storage = get_storage()

    chunk_cfg = load_and_verify_chunk_config()
    print(f"[STAGE 3/11] chunk_config_hash verified: {EXPECTED_CHUNK_CONFIG_HASH}")

    entries, manifest_hash = load_task41_manifest(storage)
    assert_task41_manifest_healthy(entries)
    print(f"[STAGE 2/11] Task 4.1 manifest verified: {len(entries)} entries, hash={manifest_hash}")

    p42_cfg = build_phase_4_2_config(EXPECTED_CHUNK_CONFIG_HASH)
    p42_hash = phase_4_2_build_config_hash(p42_cfg)
    print(f"phase_4_2_build_config_hash: {p42_hash}")

    out_dir = storage.chunks_dir_full(EXPECTED_PHASE_4_1_CONFIG_HASH, EXPECTED_CHUNK_CONFIG_HASH)
    print(f"output_dir: {out_dir}")

    config_path = write_tracked_config(storage, p42_cfg, p42_hash)
    print(f"tracked config written: {config_path}")

    if args.plan:
        return 0

    task41_root = storage.normalized_dir_for_config(EXPECTED_PHASE_4_1_CONFIG_HASH)
    expected_identity = {
        "phase_4_1_config_hash": EXPECTED_PHASE_4_1_CONFIG_HASH,
        "phase_4_1_build_manifest_sha256": EXPECTED_PHASE_4_1_MANIFEST_SHA256,
        "phase_4_2_build_config_hash": p42_hash,
        "chunk_schema_version": ms.CHUNK_SCHEMA_VERSION,
        "chunk_config_hash": EXPECTED_CHUNK_CONFIG_HASH,
    }

    if args.status:
        storage.ensure_dir(out_dir)
        print(json.dumps(summarize_final(out_dir, entries), indent=2, sort_keys=True))
        return 0

    tokenizer = load_tokenizer(chunk_cfg)
    window_size = chunk_cfg["window_size_tokens"]
    stride = chunk_cfg["stride_tokens"]

    if args.pilot:
        pilot_ids, by_id, normalized_ids = select_pilot_sample(entries)
        smallest, largest = pick_size_extremes(storage, normalized_ids, by_id, task41_root)
        pilot_ids = sorted(set(pilot_ids) | {smallest, largest})
        pilot_entries = [by_id[d] for d in pilot_ids]
        result = run(storage, pilot_entries, out_dir, expected_identity, tokenizer, window_size, stride,
                     EXPECTED_CHUNK_CONFIG_HASH, ms.CHUNK_SCHEMA_VERSION, task41_root, limit=None)
        print(json.dumps(result, indent=2, sort_keys=True))
        print("pilot document ids:", pilot_ids)
        return 0

    if args.run:
        run_stats = run(storage, entries, out_dir, expected_identity, tokenizer, window_size, stride,
                         EXPECTED_CHUNK_CONFIG_HASH, ms.CHUNK_SCHEMA_VERSION, task41_root, limit=args.limit)
        print(json.dumps(run_stats, indent=2, sort_keys=True))
        summary = summarize_final(out_dir, entries)
        print(json.dumps(summary, indent=2, sort_keys=True))
        _doc_path, doc_hash = build_document_manifest(out_dir, entries)
        _shard_path, shard_hash = build_shard_manifest(out_dir)

        print("[STAGE 8/11] validating full chunk corpus...")
        validation = validate_full_corpus(out_dir, entries)
        print(json.dumps(validation, indent=2, sort_keys=True))

        print("[STAGE 9/11] sample-checking production chunk quality...")
        sample_check = sample_quality_inspection(storage, out_dir, entries, task41_root, _doc_path)
        print(json.dumps(sample_check, indent=2, sort_keys=True))

        result_path = write_tracked_result(
            storage, cfg_hash=p42_hash, out_dir=out_dir, entries=entries, summary=summary,
            run_stats=run_stats, doc_manifest_sha256=doc_hash, shard_manifest_sha256=shard_hash,
            validation=validation, sample_check=sample_check,
        )
        print(f"tracked result written: {result_path}")
        return 0

    if args.verify_sample:
        pilot_ids, by_id, normalized_ids = select_pilot_sample(entries)
        _header, shard_records, doc_records = read_checkpoint(checkpoint_path(out_dir))
        _valid_shards, chunked_completed = verify_shards(out_dir, shard_records)
        mismatches = []
        for doc_id in pilot_ids:
            entry = by_id[doc_id]
            if entry["status"] != "NORMALIZED":
                continue
            fields, body = read_and_verify_document(task41_root, entry)
            records = chunk_one_document(
                document_id=doc_id, fields=fields, body_text=body, tokenizer=tokenizer,
                window_size=window_size, stride=stride, chunk_config_hash=EXPECTED_CHUNK_CONFIG_HASH,
                chunk_schema_version=ms.CHUNK_SCHEMA_VERSION,
            )
            if doc_id not in chunked_completed or chunked_completed[doc_id]["chunk_count"] != len(records):
                mismatches.append(doc_id)
        print(json.dumps({"sample_size": len(pilot_ids), "mismatches": mismatches}, indent=2))
        return 1 if mismatches else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
