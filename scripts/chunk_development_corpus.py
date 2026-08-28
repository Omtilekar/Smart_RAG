"""Task 1.3 - chunk the corrected Task 1.2 normalized corpus into
deterministic 512-token fixed windows.

Reads artifacts/normalized/phase1-minimal-v1/*.md (frozen input, never
modified) via the Task 1.1 manifest for canonical document order, tokenizes
each document's Markdown body offline with BAAI/bge-small-en-v1.5's
tokenizer, slices exact-source-text 512-token windows (zero overlap, final
partial window kept), and writes one Parquet file under
artifacts/chunks/<chunk_config_hash>/.

No embedding, no LanceDB, no retrieval, no network access. Pure
tokenizer/text-processing work only. All chunking-semantics decisions this
script encodes were explicitly user-approved (Task 1.3) - see
project_plan/PHASE1_CHUNKING.md for the full rationale of each.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

os.environ.setdefault("HF_HUB_OFFLINE", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from src.storage import get_storage  # noqa: E402
from src.chunk.fixed_window import (  # noqa: E402
    CHUNK_SCHEMA_FIELDS,
    WINDOW_SIZE_TOKENS,
    STRIDE_TOKENS,
    build_chunk_config,
    chunk_config_hash as compute_chunk_config_hash,
    compute_token_windows,
    make_chunk_id,
    parse_normalized_document,
    slice_chunk_text,
)
from src.normalize.edgar_markdown import output_filename  # noqa: E402

NORMALIZER_VERSION = "phase1-minimal-v1"
EXPECTED_MANIFEST_ROWS = 1500
EXPECTED_MANIFEST_SHA256 = "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b"
TOKENIZER_REPO = "BAAI/bge-small-en-v1.5"
TOKENIZER_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"

MANIFEST_RELATIVE_PATH = Path("results") / "phase_1_1_development_corpus.json"
NORMALIZATION_SUMMARY_PATH = Path("results") / "phase_1_2_normalization_summary.json"
NORMALIZATION_CONFIG_PATH = Path("configs") / "normalize_development_corpus.json"
CHUNK_CONFIG_PATH = Path("configs") / "chunk_development_corpus.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_3_chunking_summary.json"

# Task 1.2's own approved known-empty-source document set - Task 1.3 must
# see exactly these 7 produce 0 chunks, nothing more, nothing fewer.
EXPECTED_EMPTY_BODY_DOCUMENT_IDS: frozenset[str] = frozenset({
    "18498_2018.htm", "1324424_2018.htm", "71691_2016.htm",
    "1388410_2016.htm", "1388410_2018.htm", "883241_2017.htm",
    "1110803_2019.htm",
})


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def normalization_build_sha256(normalized_dir: Path) -> str:
    """Recomputes Task 1.2's documented procedure directly against the live
    artifacts/normalized/phase1-minimal-v1/ files, rather than trusting the
    value stored in results/phase_1_2_normalization_summary.json."""
    files = sorted(normalized_dir.glob("*.md"))
    lines = []
    for path in files:
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{path.name}:{file_hash}\n")
    combined = "".join(lines).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def verify_task_1_2_provenance(storage) -> dict:
    config_path = storage.repo_root / NORMALIZATION_CONFIG_PATH
    summary_path = storage.repo_root / NORMALIZATION_SUMMARY_PATH
    storage.require_file(config_path)
    storage.require_file(summary_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    for label, obj in (("config", config), ("summary", summary)):
        if obj.get("normalizer_version") != NORMALIZER_VERSION:
            raise SystemExit(
                f"BLOCKED — Task 1.2 normalizer-version correction has not been applied "
                f"({label} says {obj.get('normalizer_version')!r}, expected {NORMALIZER_VERSION!r})"
            )

    normalized_dir = storage.normalized_dir(NORMALIZER_VERSION)
    storage.require_dir(normalized_dir)
    recomputed = normalization_build_sha256(normalized_dir)
    stored = summary.get("normalization_build_sha256")
    if recomputed != stored:
        raise SystemExit(
            f"BLOCKED — normalization_build_sha256 mismatch: recomputed {recomputed} != "
            f"summary's stored {stored}. The normalized corpus may have changed."
        )

    doc_count = summary.get("document_count")
    if doc_count != EXPECTED_MANIFEST_ROWS:
        raise SystemExit(f"BLOCKED — normalized document_count {doc_count} != {EXPECTED_MANIFEST_ROWS}")

    return {
        "normalizer_version": NORMALIZER_VERSION,
        "normalized_dir": normalized_dir,
        "normalization_build_sha256": recomputed,
        "development_manifest_sha256": summary.get("development_manifest_sha256"),
    }


def load_and_verify_manifest(storage) -> dict:
    manifest_path = storage.repo_root / MANIFEST_RELATIVE_PATH
    storage.require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest["filings"]
    if len(filings) != EXPECTED_MANIFEST_ROWS:
        raise SystemExit(f"BLOCKED — manifest has {len(filings)} rows, expected {EXPECTED_MANIFEST_ROWS}")
    ids = [r["document_id"] for r in filings]
    if len(set(ids)) != len(ids):
        raise SystemExit("BLOCKED — manifest has duplicate document_id values")
    blob = json.dumps(filings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    recomputed = hashlib.sha256(blob).hexdigest()
    if recomputed != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"BLOCKED — development_manifest_sha256 mismatch: recomputed {recomputed} != "
            f"expected {EXPECTED_MANIFEST_SHA256}"
        )
    return manifest


def load_tokenizer():
    from huggingface_hub import try_to_load_from_cache
    for fname in ("tokenizer.json", "tokenizer_config.json", "vocab.txt", "special_tokens_map.json"):
        cached = try_to_load_from_cache(TOKENIZER_REPO, fname, revision=TOKENIZER_REVISION)
        if cached is None or not isinstance(cached, str):
            raise SystemExit(
                f"BLOCKED — required cached tokenizer asset missing: {TOKENIZER_REPO}/{fname} "
                f"(revision {TOKENIZER_REVISION}). Refusing to download - offline only."
            )
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_REPO, revision=TOKENIZER_REVISION, local_files_only=True,
    )
    if not tokenizer.is_fast:
        raise SystemExit("BLOCKED — loaded tokenizer is not a fast tokenizer; offset mappings unavailable")
    return tokenizer


def resolve_and_parse_documents(provenance: dict, filings: list[dict]) -> dict[str, tuple[dict, str]]:
    """document_id -> (frontmatter_fields, body_text), cross-validated
    against the manifest row. Canonical order is the manifest's own
    (document_id-sorted) order - not filesystem iteration order."""
    normalized_dir = provenance["normalized_dir"]
    out: dict[str, tuple[dict, str]] = {}
    for row in filings:
        doc_id = row["document_id"]
        fname = output_filename(doc_id)
        path = normalized_dir / fname
        if not path.is_file():
            raise SystemExit(f"FATAL: normalized document missing for manifest row: {doc_id} -> {fname}")
        text = path.read_text(encoding="utf-8")
        try:
            fields, body = parse_normalized_document(text)
        except ValueError as e:
            raise SystemExit(f"FATAL: malformed normalized document {fname}: {e}")

        if fields["document_id"] != doc_id or fields["source_filename"] != doc_id:
            raise SystemExit(f"FATAL: frontmatter document_id mismatch for {fname}")
        if fields["cik"] != row["cik"]:
            raise SystemExit(f"FATAL: frontmatter cik mismatch for {fname}")
        if fields["fiscal_year"] != row["year"]:
            raise SystemExit(f"FATAL: frontmatter fiscal_year mismatch for {fname}")
        if fields["source_split"] != row["source_split"]:
            raise SystemExit(f"FATAL: frontmatter source_split mismatch for {fname}")
        if fields["development_manifest_sha256"] != provenance["development_manifest_sha256"]:
            raise SystemExit(f"FATAL: frontmatter development_manifest_sha256 mismatch for {fname}")

        out[doc_id] = (fields, body)
    return out


def build_chunks(filings: list[dict], parsed_docs: dict, tokenizer, config: dict, hash_: str,
                  normalization_build_sha256_: str) -> list[dict]:
    chunks: list[dict] = []
    for row in filings:
        doc_id = row["document_id"]
        fields, body = parsed_docs[doc_id]

        if not body:
            if doc_id not in EXPECTED_EMPTY_BODY_DOCUMENT_IDS:
                raise SystemExit(f"FATAL: unexpected empty body for {doc_id} (not in approved empty-source set)")
            continue

        encoding = tokenizer(body, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
        offsets = encoding["offset_mapping"]
        num_tokens = len(offsets)
        if num_tokens == 0:
            raise SystemExit(f"FATAL: non-empty body tokenized to 0 tokens for {doc_id}")

        windows = compute_token_windows(num_tokens, WINDOW_SIZE_TOKENS, STRIDE_TOKENS)
        for ordinal, (start_idx, end_idx) in enumerate(windows):
            text = slice_chunk_text(body, offsets, start_idx, end_idx)
            if not text.strip():
                raise SystemExit(f"FATAL: empty chunk text produced for {doc_id} ordinal {ordinal}")
            chunks.append({
                "chunk_id": make_chunk_id(doc_id, ordinal),
                "document_id": doc_id,
                "cik": fields["cik"],
                "company": fields["company"],
                "form_type": fields["form_type"],
                "fiscal_year": fields["fiscal_year"],
                "source": fields["source"],
                "source_filename": fields["source_filename"],
                "source_split": fields["source_split"],
                "ordinal": ordinal,
                "text": text,
                "token_count": end_idx - start_idx,
                "chunk_config_hash": hash_,
                "normalizer_version": NORMALIZER_VERSION,
                "normalization_build_sha256": normalization_build_sha256_,
                "development_manifest_sha256": fields["development_manifest_sha256"],
            })

        if doc_id in EXPECTED_EMPTY_BODY_DOCUMENT_IDS:
            raise SystemExit(f"FATAL: approved empty-source document {doc_id} unexpectedly has non-empty body")

    return chunks


def validate_chunks(chunks: list[dict], hash_: str) -> None:
    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        raise SystemExit("FATAL: duplicate chunk_id detected")
    for c in chunks:
        if not c["chunk_id"] or not c["document_id"]:
            raise SystemExit(f"FATAL: missing identity fields: {c}")
        if c["ordinal"] < 0:
            raise SystemExit(f"FATAL: invalid ordinal: {c}")
        if not c["text"] or not c["text"].strip():
            raise SystemExit(f"FATAL: empty chunk text: {c['chunk_id']}")
        if c["token_count"] <= 0 or c["token_count"] > WINDOW_SIZE_TOKENS:
            raise SystemExit(f"FATAL: invalid token_count {c['token_count']} for {c['chunk_id']}")
        if c["chunk_config_hash"] != hash_:
            raise SystemExit(f"FATAL: chunk_config_hash mismatch for {c['chunk_id']}")
        if not isinstance(c["cik"], int) or not isinstance(c["fiscal_year"], int):
            raise SystemExit(f"FATAL: cik/fiscal_year not int for {c['chunk_id']}")


def write_parquet(storage, chunks: list[dict], hash_: str) -> Path:
    out_dir = storage.chunks_dir(hash_)
    storage.ensure_dir(out_dir)
    out_path = out_dir / "chunks.parquet"

    if out_path.exists():
        existing = pq.read_table(out_path)
        if existing.num_rows != len(chunks):
            raise SystemExit(
                f"FATAL: {out_path} already exists with {existing.num_rows} rows, "
                f"current build produced {len(chunks)} - refusing to silently overwrite a "
                f"conflicting build. STOP AND ASK before proceeding."
            )
        # Same chunk_config_hash + same row count: content is deterministically
        # identical by construction (the hash encodes every semantic decision).
        # Safe, idempotent rewrite - not a conflicting build.

    schema = pa.schema([
        ("chunk_id", pa.string()),
        ("document_id", pa.string()),
        ("cik", pa.int64()),
        ("company", pa.string()),
        ("form_type", pa.string()),
        ("fiscal_year", pa.int32()),
        ("source", pa.string()),
        ("source_filename", pa.string()),
        ("source_split", pa.string()),
        ("ordinal", pa.int32()),
        ("text", pa.string()),
        ("token_count", pa.int32()),
        ("chunk_config_hash", pa.string()),
        ("normalizer_version", pa.string()),
        ("normalization_build_sha256", pa.string()),
        ("development_manifest_sha256", pa.string()),
    ])
    columns = {field: [c[field] for c in chunks] for field in CHUNK_SCHEMA_FIELDS}
    table = pa.table(columns, schema=schema)
    pq.write_table(table, out_path)
    return out_path


def pct(sorted_vals, p):
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def main() -> int:
    start_time = time.monotonic()
    storage = get_storage()

    provenance = verify_task_1_2_provenance(storage)

    manifest = load_and_verify_manifest(storage)
    filings = manifest["filings"]

    tokenizer = load_tokenizer()

    parsed_docs = resolve_and_parse_documents(provenance, filings)

    config = build_chunk_config(
        normalizer_version=provenance["normalizer_version"],
        normalization_build_sha256=provenance["normalization_build_sha256"],
        development_manifest_sha256=provenance["development_manifest_sha256"],
        tokenizer_repo=TOKENIZER_REPO,
        tokenizer_revision=TOKENIZER_REVISION,
    )
    hash_ = compute_chunk_config_hash(config)

    chunks = build_chunks(
        filings, parsed_docs, tokenizer, config, hash_,
        normalization_build_sha256_=provenance["normalization_build_sha256"],
    )
    validate_chunks(chunks, hash_)

    doc_ids_with_chunks = {c["document_id"] for c in chunks}
    zero_chunk_docs = [row["document_id"] for row in filings if row["document_id"] not in doc_ids_with_chunks]
    if set(zero_chunk_docs) != EXPECTED_EMPTY_BODY_DOCUMENT_IDS:
        raise SystemExit(
            f"FATAL: zero-chunk document set {sorted(zero_chunk_docs)} does not match the "
            f"approved empty-source set {sorted(EXPECTED_EMPTY_BODY_DOCUMENT_IDS)}"
        )

    out_path = write_parquet(storage, chunks, hash_)

    config_path = storage.repo_root / CHUNK_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    runtime_s = time.monotonic() - start_time

    chunks_per_doc: dict[str, int] = {}
    for c in chunks:
        chunks_per_doc[c["document_id"]] = chunks_per_doc.get(c["document_id"], 0) + 1
    cpd_sorted = sorted(chunks_per_doc.values())
    tokens_sorted = sorted(c["token_count"] for c in chunks)
    full_chunks = sum(1 for c in chunks if c["token_count"] == WINDOW_SIZE_TOKENS)
    partial_chunks = len(chunks) - full_chunks
    total_tokens = sum(c["token_count"] for c in chunks)
    artifact_size = out_path.stat().st_size

    summary = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "input_normalizer_version": provenance["normalizer_version"],
        "input_normalization_build_sha256": provenance["normalization_build_sha256"],
        "development_manifest_sha256": provenance["development_manifest_sha256"],
        "chunk_config_hash": hash_,
        "tokenizer": config["tokenizer"],
        "window_size_tokens": WINDOW_SIZE_TOKENS,
        "stride_tokens": STRIDE_TOKENS,
        "overlap_tokens": 0,
        "partial_window_policy": "keep",
        "frontmatter_body_policy": "body_only_frontmatter_to_metadata",
        "chunk_count": len(chunks),
        "documents_total": len(filings),
        "documents_with_chunks": len(doc_ids_with_chunks),
        "documents_without_chunks": len(zero_chunk_docs),
        "empty_source_document_ids": sorted(EXPECTED_EMPTY_BODY_DOCUMENT_IDS),
        "chunks_per_document": {
            "min": cpd_sorted[0], "median": median(cpd_sorted),
            "p95": pct(cpd_sorted, 0.95), "max": cpd_sorted[-1],
        } if cpd_sorted else None,
        "tokens_per_chunk": {
            "min": tokens_sorted[0], "median": median(tokens_sorted),
            "p95": pct(tokens_sorted, 0.95), "max": tokens_sorted[-1],
        } if tokens_sorted else None,
        "full_chunks": full_chunks,
        "partial_chunks": partial_chunks,
        "total_emitted_tokens": total_tokens,
        "artifact_path": str((Path("artifacts") / "chunks" / hash_ / "chunks.parquet").as_posix()),
        "artifact_size_bytes": artifact_size,
        "build_runtime_seconds": round(runtime_s, 2),
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"chunk_config_hash: {hash_}")
    print(f"Documents: {len(filings)} total, {len(doc_ids_with_chunks)} with chunks, "
          f"{len(zero_chunk_docs)} without (approved empty-source)")
    print(f"Chunks written: {len(chunks)} -> {out_path}")
    print(f"Full/partial: {full_chunks}/{partial_chunks}, total tokens: {total_tokens}")
    print(f"Runtime: {runtime_s:.2f}s")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
