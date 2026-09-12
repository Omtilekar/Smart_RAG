"""Task 4.1 - full-corpus normalization driver.

Scales Task 1.2's minimal EDGAR-CORPUS -> Markdown normalizer
(src/normalize/edgar_markdown.py, body-rendering logic completely
unmodified) from the 1,500-filing Phase 1 development corpus to the
complete, frozen 91,086-filing EDGAR-CORPUS.

Does NOT chunk, tokenize for chunking, embed, index, retrieve, or call an
LLM. Read-only against data/ (edgar_corpus/*.parquet, xbrl.duckdb). Writes
only under artifacts/normalized_full/<phase_4_1_config_hash>/ (git-ignored)
and the small tracked results/configs files listed below.

Usage:
    python scripts/normalize_full_corpus.py --plan
    python scripts/normalize_full_corpus.py --pilot
    python scripts/normalize_full_corpus.py --run [--limit N]
    python scripts/normalize_full_corpus.py --status
    python scripts/normalize_full_corpus.py --verify-sample
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402
from src.artifacts.versioning import semantic_hash, validate_sha256  # noqa: E402
from src.normalize.edgar_markdown import (  # noqa: E402
    SECTION_COLUMNS,
    FULL_CORPUS_FRONTMATTER_KEYS,
    render_document,
    output_filename,
    count_item_headings,
    is_all_sections_empty,
    normalize_newlines,
)

TASK = "phase_4_1_full_corpus_normalization"
NORMALIZER_VERSION = "phase1-minimal-v1"
SOURCE_SPLITS = ("train", "test", "validation")
EXPECTED_SOURCE_DOCUMENT_COUNT = 91086
EXPECTED_SOURCE_CIK_COUNT = 25937
EXPECTED_YEAR_MIN = 1993
EXPECTED_YEAR_MAX = 2020
FETCH_BATCH_SIZE = 500
PROGRESS_EVERY = 2000

CONFIG_RELATIVE_PATH = Path("configs") / "phase_4_1_full_corpus_normalization.json"
RESULT_RELATIVE_PATH = Path("results") / "phase_4_1_full_corpus_normalization.json"

FORM_TYPE_CONSTANT = "10-K"
SOURCE_CONSTANT = "edgar_corpus"


# --------------------------------------------------------------- provenance

def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


# --------------------------------------------------------------- config

def build_config() -> dict:
    """Every field here is semantic (affects output bytes or identity) -
    no timestamps, no git SHA, no machine-specific value. Hashed as-is via
    semantic_hash() to produce phase_4_1_config_hash."""
    return {
        "task": TASK,
        "normalizer_version": NORMALIZER_VERSION,
        "body_rendering_source": (
            "src.normalize.edgar_markdown render_body/normalize_newlines/"
            "output_filename - unmodified from Task 1.2"
        ),
        "source_dataset": SOURCE_CONSTANT,
        "source_files": sorted(f"data/edgar_corpus/{s}.parquet" for s in SOURCE_SPLITS),
        "source_identity_field": "filename",
        "expected_source_document_count": EXPECTED_SOURCE_DOCUMENT_COUNT,
        "expected_source_cik_count": EXPECTED_SOURCE_CIK_COUNT,
        "expected_source_year_min": EXPECTED_YEAR_MIN,
        "expected_source_year_max": EXPECTED_YEAR_MAX,
        "section_columns": list(SECTION_COLUMNS),
        "section_ordering_policy": (
            "fixed SEC Item order, taken directly from source parquet column "
            "order - unchanged from Task 1.2"
        ),
        "newline_policy": "CRLF/CR -> LF; exactly one trailing newline; UTF-8",
        "empty_section_policy": (
            "null/empty/whitespace-only section omitted entirely - no heading, "
            "no body - unchanged from Task 1.2"
        ),
        "empty_document_policy": (
            "a filing where all 20 section_* columns are null/empty/"
            "whitespace-only is written as a frontmatter-only document (empty "
            "body, zero Item headings) - the general programmatic form of "
            "Task 1.2's hand-curated KNOWN_EMPTY_BODY_DOCUMENT_IDS allowlist"
        ),
        "frontmatter_schema_version": "phase_4_1-full-corpus-v1",
        "frontmatter_keys": list(FULL_CORPUS_FRONTMATTER_KEYS),
        "cik_type": "int64 (python int, cast from source VARCHAR)",
        "fiscal_year_type": "int32 (python int, cast from source VARCHAR)",
        "form_type_constant": FORM_TYPE_CONSTANT,
        "document_id_policy": (
            "reuse EDGAR-CORPUS filename verbatim (e.g. 1005817_2016.htm) - "
            "never row number, array position, UUID, or invented accession"
        ),
        "output_filename_policy": (
            "extension replaced only, 1:1 - unchanged from Task 1.2 "
            "(src.normalize.edgar_markdown.output_filename)"
        ),
        "company_name_policy": {
            "source_table": "data/xbrl.duckdb submissions (frozen, read-only)",
            "match_key": "cik only - no accession/period join (EDGAR-CORPUS carries no accession)",
            "tie_break_on_multiple_names": "row with maximum `filed` (YYYYMMDD string, lexicographically well-ordered)",
            "missing_value_policy": "null - never fabricated, never guessed from filename/ticker heuristics",
            "measured_coverage_2026_09_12": {
                "ciks_covered": 6877, "ciks_total": 25937,
                "rows_covered": 31047, "rows_total": 91086,
            },
            "policy_decision": (
                "user-approved 2026-09-12: nullable company, over drop-field/"
                "scope-restriction alternatives"
            ),
        },
        "accession_policy": "always null for edgar_corpus - no reliable accession linkage exists",
        "build_manifest_schema_version": 1,
        "checkpoint_unit": "one source row (document_id) per unit",
        "processing_order_policy": (
            "deterministic stratified pilot sample first (Stage 6), then "
            "ascending sorted document_id for the remainder"
        ),
    }


def config_hash(config: dict) -> str:
    return semantic_hash(config)


# --------------------------------------------------------------- source audit

def connect_source(storage) -> duckdb.DuckDBPyConnection:
    edgar_root = storage.edgar_corpus_root
    storage.require_dir(edgar_root)
    con = duckdb.connect()
    con.execute("PRAGMA disable_progress_bar")
    union_sql = " UNION ALL ".join(
        f"SELECT '{s}' AS split, * FROM read_parquet('{(edgar_root / f'{s}.parquet').as_posix()}')"
        for s in SOURCE_SPLITS
    )
    # A VIEW, not a materialized TABLE - read_parquet() stays lazy with
    # projection/filter pushdown, so a batched WHERE filename IN (...)
    # query never pulls the full ~26 GB corpus into process memory at
    # once (Stage 5's "do not build the entire output into RAM").
    con.execute(f"CREATE TEMP VIEW edgar AS SELECT * FROM ({union_sql})")
    return con


def audit_source(con: duckdb.DuckDBPyConnection) -> dict:
    total = con.execute("SELECT count(*) FROM edgar").fetchone()[0]
    dup_id = con.execute(
        "SELECT count(*) FROM (SELECT filename, count(*) c FROM edgar GROUP BY filename HAVING c>1)"
    ).fetchone()[0]
    dup_cy = con.execute(
        "SELECT count(*) FROM (SELECT cik, year, count(*) c FROM edgar GROUP BY cik, year HAVING c>1)"
    ).fetchone()[0]
    nulls = con.execute(
        "SELECT sum(CASE WHEN filename IS NULL OR trim(filename)='' THEN 1 ELSE 0 END), "
        "sum(CASE WHEN cik IS NULL OR trim(cik)='' THEN 1 ELSE 0 END), "
        "sum(CASE WHEN year IS NULL OR trim(year)='' THEN 1 ELSE 0 END) FROM edgar"
    ).fetchone()
    ciks = con.execute("SELECT count(DISTINCT cik) FROM edgar").fetchone()[0]
    year_min, year_max = con.execute("SELECT min(year), max(year) FROM edgar").fetchone()
    return {
        "total_rows": total,
        "duplicate_filename_groups": dup_id,
        "duplicate_cik_year_groups": dup_cy,
        "null_or_empty_filename": nulls[0],
        "null_or_empty_cik": nulls[1],
        "null_or_empty_year": nulls[2],
        "distinct_ciks": ciks,
        "year_min": int(year_min), "year_max": int(year_max),
    }


def assert_source_healthy(audit: dict) -> None:
    problems = []
    if audit["total_rows"] != EXPECTED_SOURCE_DOCUMENT_COUNT:
        problems.append(f"total_rows={audit['total_rows']} != expected {EXPECTED_SOURCE_DOCUMENT_COUNT}")
    if audit["duplicate_filename_groups"] != 0:
        problems.append(f"duplicate_filename_groups={audit['duplicate_filename_groups']} != 0")
    if audit["null_or_empty_filename"] != 0:
        problems.append(f"null_or_empty_filename={audit['null_or_empty_filename']} != 0")
    if audit["distinct_ciks"] != EXPECTED_SOURCE_CIK_COUNT:
        problems.append(f"distinct_ciks={audit['distinct_ciks']} != expected {EXPECTED_SOURCE_CIK_COUNT}")
    if problems:
        raise SystemExit("STOP — source identity audit failed: " + "; ".join(problems))


def load_row_metadata(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Lightweight metadata for ALL rows (id/split/cik/year/total_len) -
    never the full section text for all rows at once (that would be the
    ~26 GB full-corpus text held in RAM simultaneously)."""
    length_expr = " + ".join(f"coalesce(length(trim({c})), 0)" for c in SECTION_COLUMNS)
    rows = con.execute(
        f"SELECT filename, split, cik, year, ({length_expr}) AS total_len FROM edgar"
    ).fetchall()
    return [
        {"document_id": r[0], "split": r[1], "cik": int(r[2]), "year": int(r[3]), "total_len": int(r[4])}
        for r in rows
    ]


def fetch_full_rows(con: duckdb.DuckDBPyConnection, document_ids: list[str]) -> dict[str, dict]:
    """Fetches full section text for exactly the given document_ids - the
    only place full filing text is materialized, and only for one batch at
    a time."""
    if not document_ids:
        return {}
    placeholders = ", ".join("?" for _ in document_ids)
    section_cols_sql = ", ".join(SECTION_COLUMNS)
    rows = con.execute(
        f"SELECT filename, split, cik, year, {section_cols_sql} FROM edgar WHERE filename IN ({placeholders})",
        document_ids,
    ).fetchall()
    col_names = [d[0] for d in con.description]
    return {dict(zip(col_names, r))["filename"]: dict(zip(col_names, r)) for r in rows}


# --------------------------------------------------------------- company lookup

def build_company_lookup(xbrl_db_path: Path) -> dict[int, str]:
    """cik -> name, tie-broken by max(filed) when a CIK has multiple
    distinct historical names. Read-only against the frozen submissions
    table; never writes to data/."""
    con = duckdb.connect(str(xbrl_db_path), read_only=True)
    rows = con.execute(
        "SELECT cik, name, filed FROM submissions WHERE name IS NOT NULL AND filed IS NOT NULL"
    ).fetchall()
    con.close()
    best: dict[int, tuple[str, str]] = {}
    for cik, name, filed in rows:
        cik = int(cik)
        current = best.get(cik)
        if current is None or filed > current[1]:
            best[cik] = (name, filed)
    return {cik: name for cik, (name, _filed) in best.items()}


# --------------------------------------------------------------- pilot sample

def select_pilot_sample(metadata: list[dict]) -> list[str]:
    """Deterministic stratified sample covering Stage 6's requirements:
    early/middle/late years, all splits, largest/smallest documents, and
    empty-source documents."""
    pilot_ids: set[str] = set()
    year_bands = ((1993, 1999), (2000, 2009), (2010, 2019), (2020, 2020))
    for split in SOURCE_SPLITS:
        for lo, hi in year_bands:
            candidates = sorted(
                r["document_id"] for r in metadata
                if r["split"] == split and lo <= r["year"] <= hi
            )
            if candidates:
                pilot_ids.add(candidates[0])
    by_len = sorted(metadata, key=lambda r: (r["total_len"], r["document_id"]))
    if by_len:
        pilot_ids.add(by_len[0]["document_id"])
        pilot_ids.add(by_len[-1]["document_id"])
    empties = sorted(r["document_id"] for r in metadata if r["total_len"] == 0)
    pilot_ids.update(empties[:5])
    return sorted(pilot_ids)


def build_processing_order(metadata: list[dict]) -> list[str]:
    pilot = select_pilot_sample(metadata)
    pilot_set = set(pilot)
    remainder = sorted(r["document_id"] for r in metadata if r["document_id"] not in pilot_set)
    return pilot + remainder


# --------------------------------------------------------------- rendering / one unit

def build_frontmatter_fields(row: dict, company_lookup: dict[int, str]) -> dict:
    cik = int(row["cik"])
    return {
        "cik": cik,
        "company": company_lookup.get(cik),
        "form_type": FORM_TYPE_CONSTANT,
        "fiscal_year": int(row["year"]),
        "source": SOURCE_CONSTANT,
        "source_filename": row["filename"],
        "document_id": row["filename"],
        "source_split": row["split"],
    }


def validate_full_corpus_output(fname: str, text: str, row: dict) -> None:
    if not text.startswith("---\n"):
        raise ValueError(f"{fname}: missing frontmatter open delimiter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{fname}: missing frontmatter close delimiter")
    fm_text = parts[1]
    for required in ("cik:", "company:", "form_type:", "fiscal_year:", "source:",
                      "source_filename:", "document_id:", "source_split:"):
        if required not in fm_text:
            raise ValueError(f"{fname}: missing frontmatter field {required!r}")
    if '"10-K"' not in fm_text:
        raise ValueError(f"{fname}: form_type != 10-K")
    if '"edgar_corpus"' not in fm_text:
        raise ValueError(f"{fname}: source != edgar_corpus")
    if json.dumps(row["filename"], ensure_ascii=False) not in fm_text:
        raise ValueError(f"{fname}: source identity mismatch in frontmatter")

    body = parts[2]
    sections = {col: row[col] for col in SECTION_COLUMNS}
    empty_source = is_all_sections_empty(sections)
    headings = count_item_headings(text)
    if empty_source:
        if body.strip():
            raise ValueError(f"{fname}: expected empty body (empty-source filing) but has content")
    else:
        if not body.strip():
            raise ValueError(f"{fname}: has empty body and is not an empty-source filing")
        if headings < 1:
            raise ValueError(f"{fname}: has no Item heading rendered")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise ValueError(f"{fname}: does not end with exactly one trailing newline")
    text.encode("utf-8")


def render_unit(row: dict, company_lookup: dict[int, str]) -> tuple[str, str, str]:
    """Returns (output_filename, markdown_text, outcome). Raises on a real
    normalization defect - caller records FAILED, never aborts the batch."""
    fields = build_frontmatter_fields(row, company_lookup)
    sections = {col: row[col] for col in SECTION_COLUMNS}
    text = render_document(fields, sections, frontmatter_keys=FULL_CORPUS_FRONTMATTER_KEYS)
    fname = output_filename(row["filename"])
    validate_full_corpus_output(fname, text, row)
    outcome = "VALID_EMPTY_SOURCE" if is_all_sections_empty(sections) else "NORMALIZED"
    return fname, text, outcome


# --------------------------------------------------------------- checkpoint

def atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(text.encode("utf-8"))
    import os
    os.replace(tmp_path, path)


def checkpoint_path(out_dir: Path) -> Path:
    return out_dir / "build_state.jsonl"


def read_checkpoint(path: Path) -> tuple[dict | None, dict[str, dict]]:
    """Returns (header, {document_id: latest_record}). A malformed trailing
    line (a crash mid-append) is dropped, not accepted; a malformed
    non-trailing line is a hard corruption STOP."""
    if not path.exists():
        return None, {}
    lines = path.read_text(encoding="utf-8").splitlines()
    header = None
    records: dict[str, dict] = {}
    for i, line in enumerate(lines):
        is_last = i == len(lines) - 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            if is_last:
                break  # partial trailing write - safely dropped, unit will be reprocessed
            raise SystemExit(f"FATAL — checkpoint state appears corrupt at line {i + 1} of {path}")
        if obj.get("record_type") == "header":
            header = obj
        elif obj.get("record_type") == "unit":
            records[obj["document_id"]] = obj
        else:
            raise SystemExit(f"FATAL — checkpoint state appears corrupt (unknown record_type) at line {i + 1} of {path}")
    return header, records


def write_header(path: Path, header: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(header, sort_keys=True) + "\n")


def append_record(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()


def verify_completed_units(out_dir: Path, records: dict[str, dict]) -> dict[str, dict]:
    """Detects corrupted/missing completed units - never silently trusts
    the checkpoint log alone. Returns only the subset that re-verifies
    against real files on disk."""
    verified: dict[str, dict] = {}
    for doc_id, rec in records.items():
        if rec["outcome"] not in ("NORMALIZED", "VALID_EMPTY_SOURCE"):
            continue  # FAILED units are always retried, never treated as complete
        rel = rec.get("output_relpath")
        if not rel:
            continue
        p = out_dir / rel
        if not p.is_file():
            continue
        actual_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual_hash != rec.get("content_sha256"):
            continue  # corrupted unit - will be silently reprocessed, not silently accepted
        verified[doc_id] = rec
    return verified


def compute_source_ids_sha256(metadata: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(sorted(r["document_id"] for r in metadata), separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def assert_checkpoint_resumable(header: dict | None, cfg_hash: str, source_ids_sha256: str, ckpt_path: Path) -> None:
    """Config/source identity mismatch must refuse resume (Stage 5
    requirement) - raises SystemExit rather than silently rebuilding or
    silently reusing a stale checkpoint. A missing header (no prior
    checkpoint) is not a mismatch."""
    if header is None:
        return
    if header["phase_4_1_config_hash"] != cfg_hash:
        raise SystemExit(
            f"FATAL — checkpoint at {ckpt_path} was built under config hash "
            f"{header['phase_4_1_config_hash']}, current config hashes to {cfg_hash}. "
            f"Refusing to resume under a different config identity."
        )
    if header["source_document_ids_sha256"] != source_ids_sha256:
        raise SystemExit(
            f"FATAL — checkpoint at {ckpt_path} was built against a different source "
            f"document-id set. Refusing to resume."
        )


# --------------------------------------------------------------- main run

def run(storage, con, cfg: dict, cfg_hash: str, out_dir: Path, limit: int | None,
        company_lookup: dict[int, str], metadata: list[dict]) -> dict:
    storage.ensure_dir(out_dir)
    ckpt_path = checkpoint_path(out_dir)

    source_ids_sha256 = compute_source_ids_sha256(metadata)

    header, records = read_checkpoint(ckpt_path)
    assert_checkpoint_resumable(header, cfg_hash, source_ids_sha256, ckpt_path)
    if header is None:
        header = {
            "record_type": "header",
            "phase_4_1_config_hash": cfg_hash,
            "source_document_ids_sha256": source_ids_sha256,
            "source_document_count": len(metadata),
            "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        write_header(ckpt_path, header)

    completed = verify_completed_units(out_dir, records)

    order = build_processing_order(metadata)
    pending = [d for d in order if d not in completed]
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
    bytes_written_this_run = 0
    total_done = len(completed)
    total_units = len(metadata)

    for batch_start in range(0, len(pending), FETCH_BATCH_SIZE):
        batch_ids = pending[batch_start:batch_start + FETCH_BATCH_SIZE]
        rows_by_id = fetch_full_rows(con, batch_ids)
        for doc_id in batch_ids:
            row = rows_by_id.get(doc_id)
            record: dict
            if row is None:
                record = {
                    "record_type": "unit", "document_id": doc_id,
                    "outcome": "FAILED", "output_relpath": None, "content_sha256": None, "bytes": None,
                    "error_class": "SourceRowMissing", "error_summary": "row not found in source query batch",
                }
            else:
                try:
                    fname, text, outcome = render_unit(row, company_lookup)
                    rel = fname
                    atomic_write_text(out_dir / rel, text)
                    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    nbytes = len(text.encode("utf-8"))
                    record = {
                        "record_type": "unit", "document_id": doc_id, "outcome": outcome,
                        "output_relpath": rel, "content_sha256": content_hash, "bytes": nbytes,
                        "error_class": None, "error_summary": None,
                    }
                    bytes_written_this_run += nbytes
                except Exception as exc:  # noqa: BLE001 - per-unit isolation is required by the spec
                    record = {
                        "record_type": "unit", "document_id": doc_id, "outcome": "FAILED",
                        "output_relpath": None, "content_sha256": None, "bytes": None,
                        "error_class": type(exc).__name__, "error_summary": str(exc)[:300],
                    }
                    failures_this_run += 1
            append_record(ckpt_path, record)
            processed_this_run += 1
            total_done += 1 if record["outcome"] != "FAILED" else 0

            if proc is not None and processed_this_run % 200 == 0:
                try:
                    rss = proc.memory_info().rss
                    peak_rss = max(peak_rss, rss)
                except Exception:
                    pass

            if processed_this_run % PROGRESS_EVERY == 0 or processed_this_run == len(pending):
                elapsed = time.monotonic() - start
                rate = processed_this_run / elapsed if elapsed > 0 else 0.0
                print(
                    f"[NORMALIZE] {total_done:>7,} / {total_units:,} "
                    f"{100.0 * total_done / total_units:6.2f}%   "
                    f"elapsed={elapsed:8.1f}s   docs/s={rate:7.2f}   "
                    f"written_GB_this_run={bytes_written_this_run / 1e9:6.3f}   "
                    f"failures_this_run={failures_this_run}"
                )

    elapsed_total = time.monotonic() - start
    return {
        "processed_this_run": processed_this_run,
        "failures_this_run": failures_this_run,
        "bytes_written_this_run": bytes_written_this_run,
        "elapsed_seconds_this_run": elapsed_total,
        "peak_rss_bytes": peak_rss,
        "total_units": total_units,
        "total_done_after_run": total_done,
    }


def summarize_final(out_dir: Path, metadata: list[dict]) -> dict:
    _header, records = read_checkpoint(checkpoint_path(out_dir))
    verified = verify_completed_units(out_dir, records)
    normalized = sum(1 for r in verified.values() if r["outcome"] == "NORMALIZED")
    empty = sum(1 for r in verified.values() if r["outcome"] == "VALID_EMPTY_SOURCE")
    all_ids = {r["document_id"] for r in metadata}
    verified_ids = set(verified.keys())
    failed_ids = sorted(
        doc_id for doc_id, rec in records.items()
        if rec["outcome"] == "FAILED" and doc_id not in verified_ids
    )
    # "missing" = accounted for by NEITHER a verified completion NOR an
    # explicit FAILED record - i.e. never attempted at all, or a unit whose
    # every attempt is still sitting in a not-yet-processed state. A
    # verified-failed row is explained (Stage 8's "unexplained failures = 0"
    # requirement), not silently vanished, so it must not double-count here.
    missing = sorted(all_ids - verified_ids - set(failed_ids))
    total_bytes = sum(r["bytes"] for r in verified.values())
    return {
        "normalized_count": normalized,
        "valid_empty_source_count": empty,
        "completed_count": len(verified),
        "missing_count": len(missing),
        "missing_sample": missing[:10],
        "failed_count": len(failed_ids),
        "failed_sample": failed_ids[:10],
        "total_bytes": total_bytes,
    }


def build_manifest_and_hash(out_dir: Path, metadata: list[dict]) -> tuple[Path, str]:
    """Full per-document manifest (git-ignored, lives under artifacts/) plus
    its deterministic sha256 (tracked in the small results summary)."""
    _header, records = read_checkpoint(checkpoint_path(out_dir))
    verified = verify_completed_units(out_dir, records)
    by_id = {r["document_id"]: r for r in metadata}
    manifest_path = out_dir / "manifest.jsonl"
    lines = []
    for doc_id in sorted(by_id.keys()):
        meta = by_id[doc_id]
        rec = verified.get(doc_id)
        entry = {
            "document_id": doc_id,
            "source_split": meta["split"],
            "cik": meta["cik"],
            "fiscal_year": meta["year"],
            "relative_output_path": rec["output_relpath"] if rec else None,
            "content_sha256": rec["content_sha256"] if rec else None,
            # "PENDING" (never attempted) is only legitimate mid-build; the
            # Stage 7 contract (NORMALIZED | VALID_EMPTY_SOURCE | FAILED, no
            # fourth state) is enforced by the caller before treating this
            # manifest as the final Stage 9 build manifest.
            "status": rec["outcome"] if rec else "PENDING",
        }
        lines.append(json.dumps(entry, sort_keys=True, separators=(",", ":")))
    manifest_text = "\n".join(lines) + "\n"
    manifest_bytes = manifest_text.encode("utf-8")
    # write_bytes, not write_text - write_text applies platform newline
    # translation (Windows: \n -> \r\n), which would desync the on-disk
    # bytes from manifest_sha256 (hashed from manifest_bytes below).
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    return manifest_path, manifest_sha256


# --------------------------------------------------------------- tracked outputs

def write_tracked_config(storage, cfg: dict, cfg_hash: str) -> Path:
    path = storage.repo_root / CONFIG_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"phase_4_1_config_hash": cfg_hash, "config": cfg}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_tracked_result(storage, *, cfg_hash: str, out_dir: Path, audit: dict,
                          company_lookup_size: int, metadata: list[dict],
                          manifest_sha256: str, run_stats: dict, summary: dict) -> Path:
    complete = summary["missing_count"] == 0
    result = {
        "task": TASK,
        "status": "COMPLETE" if complete else "IN_PROGRESS",
        "git_sha": git_sha(),
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),

        "source_dataset": SOURCE_CONSTANT,
        "source_row_count": audit["total_rows"],
        "unique_document_count": len(metadata),
        "cik_count": audit["distinct_ciks"],
        "year_range": [audit["year_min"], audit["year_max"]],

        "normalizer_version": NORMALIZER_VERSION,
        "phase_4_1_config_hash": cfg_hash,
        "company_name_lookup_ciks_resolved": company_lookup_size,

        "output_location_logical_key": f"artifacts/normalized_full/{cfg_hash}",
        "output_format": "one *.md file per filing (frontmatter + body), flat directory",

        "normalized_document_count": summary["normalized_count"],
        "valid_empty_source_count": summary["valid_empty_source_count"],
        "failed_count": summary["failed_count"],
        "failed_sample": summary["failed_sample"],
        "missing_count": summary["missing_count"],

        "total_normalized_bytes": summary["total_bytes"],
        "build_elapsed_seconds_last_run": run_stats.get("elapsed_seconds_this_run"),
        "documents_per_second_last_run": (
            run_stats["processed_this_run"] / run_stats["elapsed_seconds_this_run"]
            if run_stats.get("elapsed_seconds_this_run") else None
        ),
        "peak_rss_bytes_last_run": run_stats.get("peak_rss_bytes"),

        "build_manifest_sha256": manifest_sha256,
        "determinism_verification_method": (
            "phase_4_1_config_hash (semantic_hash over the frozen config) + "
            "deterministic sorted-document_id processing order/manifest + "
            "per-document content_sha256 recorded in build_state.jsonl and "
            "manifest.jsonl + idempotent resume (re-running --run against a "
            "complete checkpoint reprocesses 0 units) + --verify-sample "
            "(re-renders the Stage 6 pilot sample in memory and diffs "
            "content_sha256 against the manifest)"
        ),

        "protected_test_status": {"opened": False, "official_runs_used": 0, "official_runs_budget": 3},
        "paid_api_calls": 0,
    }
    path = storage.repo_root / RESULT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------- CLI

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", action="store_true", help="audit source + print config hash, no writes")
    parser.add_argument("--pilot", action="store_true", help="process only the deterministic pilot sample")
    parser.add_argument("--run", action="store_true", help="process the full remaining corpus (resumes)")
    parser.add_argument("--limit", type=int, default=None, help="cap units processed this invocation")
    parser.add_argument("--status", action="store_true", help="print checkpoint status only, no writes")
    parser.add_argument("--verify-sample", action="store_true", help="re-render a deterministic sample in-memory and diff hashes against the manifest")
    args = parser.parse_args()

    storage = get_storage()
    con = connect_source(storage)
    audit = audit_source(con)
    assert_source_healthy(audit)

    cfg = build_config()
    cfg_hash = config_hash(cfg)
    validate_sha256(cfg_hash, "phase_4_1_config_hash")
    out_dir = storage.normalized_dir_for_config(cfg_hash)

    print(f"[STAGE 1-2] source audit: {json.dumps(audit, sort_keys=True)}")
    print(f"phase_4_1_config_hash: {cfg_hash}")
    print(f"output_dir: {out_dir}")

    config_path = write_tracked_config(storage, cfg, cfg_hash)
    print(f"tracked config written: {config_path}")

    if args.plan:
        return 0

    metadata = load_row_metadata(con)
    company_lookup = build_company_lookup(storage.xbrl_db)
    print(f"company_lookup: {len(company_lookup)} CIKs with a resolvable name")

    if args.status:
        storage.ensure_dir(out_dir)
        summary = summarize_final(out_dir, metadata)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.pilot:
        pilot_ids = select_pilot_sample(metadata)
        result = run(storage, con, cfg, cfg_hash, out_dir, limit=len(pilot_ids),
                      company_lookup=company_lookup, metadata=metadata)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.run:
        run_stats = run(storage, con, cfg, cfg_hash, out_dir, limit=args.limit,
                         company_lookup=company_lookup, metadata=metadata)
        print(json.dumps(run_stats, indent=2, sort_keys=True))
        summary = summarize_final(out_dir, metadata)
        print(json.dumps(summary, indent=2, sort_keys=True))
        _manifest_path, manifest_sha256 = build_manifest_and_hash(out_dir, metadata)
        result_path = write_tracked_result(
            storage, cfg_hash=cfg_hash, out_dir=out_dir, audit=audit,
            company_lookup_size=len(company_lookup), metadata=metadata,
            manifest_sha256=manifest_sha256, run_stats=run_stats, summary=summary,
        )
        print(f"tracked result written: {result_path} (status={'COMPLETE' if summary['missing_count'] == 0 else 'IN_PROGRESS'})")
        return 0

    if args.verify_sample:
        sample_ids = select_pilot_sample(metadata)
        _header, records = read_checkpoint(checkpoint_path(out_dir))
        mismatches = []
        rows_by_id = fetch_full_rows(con, sample_ids)
        for doc_id in sample_ids:
            row = rows_by_id.get(doc_id)
            if row is None:
                continue
            fname, text, _outcome = render_unit(row, company_lookup)
            recomputed_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            rec = records.get(doc_id)
            if rec is None or rec.get("content_sha256") != recomputed_hash:
                mismatches.append(doc_id)
        print(json.dumps({"sample_size": len(sample_ids), "mismatches": mismatches}, indent=2))
        return 1 if mismatches else 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
