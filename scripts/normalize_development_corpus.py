"""Task 1.2 - normalize the frozen Task 1.1 development corpus to Markdown.

Reads results/phase_1_1_development_corpus.json (the frozen 1,500-filing
manifest) and data/edgar_corpus/*.parquet (frozen, read-only), renders one
deterministic Markdown document per filing via src/normalize/edgar_markdown.py,
and writes them under artifacts/normalized/<NORMALIZER_VERSION>/ (git-ignored
generated pipeline state, per src/storage.py's Task 0.7 contract).

Does not reselect, resample, or modify the Task 1.1 manifest. Does not
tokenize, chunk, embed, or index. Whole normalized filings only.

User-approved decisions this script encodes:

1. normalizer_version = "phase1-minimal-v1" (asked - no prior naming
   convention existed; originally built as "v1", corrected to
   "phase1-minimal-v1" before Task 1.3 started per an explicit follow-up
   decision - see Progress.md's "Phase 1.2 Correction" entry).
2. 7 of the 1,500 manifest filings have all 20 EDGAR-CORPUS section_*
   columns present but empty-string (verified against live data, not a
   join bug) - asked how to handle them; approved answer: normalize as
   frontmatter-only documents (empty body, zero Item headings), explicitly
   documented as a known exception to the "at least one heading" output
   check, rather than silently dropping/replacing/substituting them (the
   Task 1.1 manifest is frozen).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402
from src.normalize.edgar_markdown import (  # noqa: E402
    SECTION_COLUMNS,
    render_document,
    output_filename,
    count_item_headings,
)

NORMALIZER_VERSION = "phase1-minimal-v1"
SCHEMA_VERSION = "1.0"
EXPECTED_MANIFEST_ROWS = 1500
EXPECTED_MANIFEST_SHA256 = "d470364920c3c0529ecc77d6923742b48db89668b2684726f0edc81b5218ce3b"
MANIFEST_RELATIVE_PATH = Path("results") / "phase_1_1_development_corpus.json"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_1_2_normalization_summary.json"
CONFIG_RELATIVE_PATH = Path("configs") / "normalize_development_corpus.json"

# The 7 manifest filings verified (Step 9/10 of Task 1.2) to have all 20
# EDGAR-CORPUS section_* columns present but empty-string in the source
# data itself - not a join/resolution bug. User-approved: normalize as
# frontmatter-only documents. See project_plan/PHASE1_NORMALIZATION.md.
KNOWN_EMPTY_BODY_DOCUMENT_IDS: frozenset[str] = frozenset({
    "18498_2018.htm",
    "1324424_2018.htm",
    "71691_2016.htm",
    "1388410_2016.htm",
    "1388410_2018.htm",
    "883241_2017.htm",
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


def load_and_verify_manifest(storage) -> dict:
    manifest_path = storage.repo_root / MANIFEST_RELATIVE_PATH
    storage.require_file(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest["filings"]

    if len(filings) != EXPECTED_MANIFEST_ROWS:
        raise SystemExit(
            f"BLOCKED — Task 1.1 development manifest changed unexpectedly: "
            f"expected {EXPECTED_MANIFEST_ROWS} rows, found {len(filings)}"
        )

    ids = [r["document_id"] for r in filings]
    if len(set(ids)) != len(ids):
        raise SystemExit("BLOCKED — Task 1.1 development manifest changed unexpectedly: duplicate document_id")

    blob = json.dumps(filings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    recomputed = hashlib.sha256(blob).hexdigest()
    if recomputed != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"BLOCKED — Task 1.1 development manifest changed unexpectedly: "
            f"recomputed development_manifest_sha256={recomputed} != expected {EXPECTED_MANIFEST_SHA256}"
        )
    stored = manifest.get("development_manifest_sha256")
    if stored != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"BLOCKED — Task 1.1 development manifest changed unexpectedly: "
            f"stored checksum {stored} != expected {EXPECTED_MANIFEST_SHA256}"
        )

    return manifest


def resolve_source_rows(storage, filings: list[dict]) -> dict[str, dict]:
    """Resolve exactly the manifest's document_ids against frozen EDGAR-CORPUS
    parquet, read-only. Raises if any manifest row maps to zero or more than
    one EDGAR source row, or if cik/year/split identity disagrees."""
    edgar_root = storage.edgar_corpus_root
    storage.require_dir(edgar_root)
    splits = {s: edgar_root / f"{s}.parquet" for s in ("train", "test", "validation")}
    existing = {s: p for s, p in splits.items() if p.exists()}
    if not existing:
        raise SystemExit("FATAL: no EDGAR-CORPUS split parquet files found")

    con = duckdb.connect()
    con.execute("PRAGMA disable_progress_bar")
    union_sql = " UNION ALL ".join(
        f"SELECT '{s}' AS split, * FROM read_parquet('{p.as_posix()}')" for s, p in existing.items()
    )
    con.execute(f"CREATE TEMP TABLE edgar AS SELECT * FROM ({union_sql})")
    con.execute("CREATE TEMP TABLE manifest_ids (document_id VARCHAR)")
    con.executemany("INSERT INTO manifest_ids VALUES (?)", [(r["document_id"],) for r in filings])

    match_counts = con.execute("""
        SELECT mi.document_id, count(e.filename) AS n
        FROM manifest_ids mi LEFT JOIN edgar e ON e.filename = mi.document_id
        GROUP BY mi.document_id HAVING count(e.filename) != 1
    """).fetchall()
    if match_counts:
        raise SystemExit(
            f"FATAL: {len(match_counts)} manifest rows do not map to exactly one EDGAR source row: "
            f"{match_counts[:5]}"
        )

    section_cols_sql = ", ".join(SECTION_COLUMNS)
    rows = con.execute(f"""
        SELECT e.filename, e.split, e.cik, e.year, {section_cols_sql}
        FROM edgar e JOIN manifest_ids mi ON e.filename = mi.document_id
    """).fetchall()
    col_names = [d[0] for d in con.description]
    con.close()

    by_id: dict[str, dict] = {}
    for row in rows:
        record = dict(zip(col_names, row))
        by_id[record["filename"]] = record

    for r in filings:
        src = by_id.get(r["document_id"])
        if src is None:
            raise SystemExit(f"FATAL: manifest document_id not resolved: {r['document_id']}")
        if src["split"] != r["source_split"]:
            raise SystemExit(f"FATAL: split mismatch for {r['document_id']}: {src['split']} != {r['source_split']}")
        if int(src["cik"]) != r["cik"]:
            raise SystemExit(f"FATAL: cik mismatch for {r['document_id']}")
        if int(src["year"]) != r["year"]:
            raise SystemExit(f"FATAL: year mismatch for {r['document_id']}")

    return by_id


def build_frontmatter_fields(manifest: dict, row: dict) -> dict:
    return {
        "cik": row["cik"],
        "company": row["company_name"],
        "form_type": "10-K",
        "fiscal_year": row["year"],
        "source": "edgar_corpus",
        "source_filename": row["source_filename"],
        "document_id": row["document_id"],
        "source_split": row["source_split"],
        "development_manifest_sha256": manifest["development_manifest_sha256"],
    }


def render_all(manifest: dict, source_rows: dict[str, dict]) -> dict[str, str]:
    """Returns {output_filename: markdown_text}, one per manifest row."""
    out: dict[str, str] = {}
    for row in manifest["filings"]:
        src = source_rows[row["document_id"]]
        sections = {col: src[col] for col in SECTION_COLUMNS}
        fields = build_frontmatter_fields(manifest, row)
        markdown_text = render_document(fields, sections)
        fname = output_filename(row["document_id"])
        if fname in out:
            raise SystemExit(f"FATAL: output filename collision: {fname}")
        out[fname] = markdown_text
    return out


def validate_outputs(rendered: dict[str, str], manifest_by_output: dict[str, dict]) -> None:
    for fname, text in rendered.items():
        if not text.startswith("---\n"):
            raise SystemExit(f"FATAL: {fname} missing frontmatter open delimiter")
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            raise SystemExit(f"FATAL: {fname} missing frontmatter close delimiter")
        row = manifest_by_output[fname]
        fm_text = parts[1]
        for required in ("cik:", "company:", "form_type:", "fiscal_year:", "source:",
                          "source_filename:", "document_id:", "source_split:",
                          "development_manifest_sha256:"):
            if required not in fm_text:
                raise SystemExit(f"FATAL: {fname} missing frontmatter field {required!r}")
        if '"10-K"' not in fm_text:
            raise SystemExit(f"FATAL: {fname} form_type != 10-K")
        if '"edgar_corpus"' not in fm_text:
            raise SystemExit(f"FATAL: {fname} source != edgar_corpus")
        if row["document_id"] not in fm_text or row["source_filename"] not in fm_text:
            raise SystemExit(f"FATAL: {fname} source identity mismatch in frontmatter")

        body = parts[2]
        is_known_empty = row["document_id"] in KNOWN_EMPTY_BODY_DOCUMENT_IDS
        headings = count_item_headings(text)
        if is_known_empty:
            if body.strip():
                raise SystemExit(f"FATAL: {fname} expected empty body (known-empty filing) but has content")
        else:
            if not body.strip():
                raise SystemExit(f"FATAL: {fname} has empty body and is not a known-empty filing")
            if headings < 1:
                raise SystemExit(f"FATAL: {fname} has no Item heading rendered")
        if not text.endswith("\n") or text.endswith("\n\n"):
            raise SystemExit(f"FATAL: {fname} does not end with exactly one trailing newline")
        text.encode("utf-8")  # raises on invalid encoding


def normalization_build_sha256(rendered: dict[str, str]) -> str:
    """Documented procedure: sort relative output filenames; for each, hash
    the exact UTF-8 bytes of the file; combine "relpath:filehash\n" lines in
    sorted order; hash that combined stream. Not called chunk_config_hash -
    unrelated later concept."""
    lines = []
    for fname in sorted(rendered.keys()):
        file_bytes = rendered[fname].encode("utf-8")
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        lines.append(f"{fname}:{file_hash}\n")
    combined = "".join(lines).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def write_config(storage) -> None:
    config = {
        "schema_version": SCHEMA_VERSION,
        "normalizer_version": NORMALIZER_VERSION,
        "input_manifest": str(MANIFEST_RELATIVE_PATH.as_posix()),
        "input_development_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "source": "edgar_corpus",
        "section_ordering_policy": (
            "Fixed SEC Item order, taken directly from the source parquet "
            "column order (verified, not assumed): " + ", ".join(SECTION_COLUMNS)
        ),
        "empty_section_policy": (
            "Null/empty/whitespace-only sections are omitted entirely - no heading, "
            "no body. If ALL sections for a filing are empty, the document is written "
            "as frontmatter-only (empty body, zero Item headings) rather than dropped, "
            "replaced, or substituted - see known_empty_body_document_ids."
        ),
        "known_empty_body_document_ids": sorted(KNOWN_EMPTY_BODY_DOCUMENT_IDS),
        "newline_policy": "CRLF/CR normalized to LF; exactly one trailing newline per file; UTF-8 encoding.",
        "frontmatter_schema_version": "1.0",
        "frontmatter_keys": [
            "cik", "company", "form_type", "fiscal_year", "source",
            "source_filename", "document_id", "source_split",
            "development_manifest_sha256",
        ],
    }
    config_path = storage.repo_root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def write_normalized_corpus(storage, rendered: dict[str, str]) -> Path:
    out_dir = storage.normalized_dir(NORMALIZER_VERSION)
    storage.ensure_dir(out_dir)

    existing_files = {p.name for p in out_dir.glob("*.md")}
    expected_files = set(rendered.keys())
    unexpected_existing = existing_files - expected_files
    if unexpected_existing:
        raise SystemExit(
            f"FATAL: {out_dir} already contains {len(unexpected_existing)} files not part of the "
            f"current build (e.g. {sorted(unexpected_existing)[:5]}) - refusing to silently overwrite "
            f"a conflicting build. STOP AND ASK before proceeding."
        )

    for fname, text in rendered.items():
        (out_dir / fname).write_bytes(text.encode("utf-8"))

    on_disk = {p.name for p in out_dir.glob("*.md")}
    if on_disk != expected_files:
        raise SystemExit(f"FATAL: on-disk file set does not match expected output after write")

    return out_dir


def main() -> int:
    storage = get_storage()
    manifest = load_and_verify_manifest(storage)
    filings = manifest["filings"]

    source_rows = resolve_source_rows(storage, filings)
    rendered = render_all(manifest, source_rows)

    if len(rendered) != EXPECTED_MANIFEST_ROWS:
        raise SystemExit(f"FATAL: rendered {len(rendered)} documents, expected {EXPECTED_MANIFEST_ROWS}")

    manifest_by_output = {output_filename(r["document_id"]): r for r in filings}
    validate_outputs(rendered, manifest_by_output)

    build_sha256 = normalization_build_sha256(rendered)
    out_dir = write_normalized_corpus(storage, rendered)
    write_config(storage)

    total_bytes = sum(len(t.encode("utf-8")) for t in rendered.values())
    char_counts = sorted(len(t) for t in rendered.values())
    n = len(char_counts)
    nonempty_section_counts = []
    for r in filings:
        src = source_rows[r["document_id"]]
        cnt = sum(1 for c in SECTION_COLUMNS if src[c] and src[c].strip())
        nonempty_section_counts.append(cnt)
    nonempty_section_counts.sort()

    section_coverage = {}
    for col in SECTION_COLUMNS:
        present = sum(1 for r in filings if source_rows[r["document_id"]][col] and source_rows[r["document_id"]][col].strip())
        section_coverage[col] = {"count": present, "pct": round(100.0 * present / n, 2)}

    def pct(sorted_vals, p):
        if not sorted_vals:
            return None
        idx = min(len(sorted_vals) - 1, int(round(p * (len(sorted_vals) - 1))))
        return sorted_vals[idx]

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "normalizer_version": NORMALIZER_VERSION,
        "input_manifest": str(MANIFEST_RELATIVE_PATH.as_posix()),
        "development_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "git_sha": git_sha(),
        "document_count": len(rendered),
        "total_normalized_bytes": total_bytes,
        "character_count": {
            "min": char_counts[0], "median": char_counts[n // 2],
            "p95": pct(char_counts, 0.95), "max": char_counts[-1],
        },
        "nonempty_section_count": {
            "min": nonempty_section_counts[0], "median": nonempty_section_counts[n // 2],
            "p95": pct(nonempty_section_counts, 0.95), "max": nonempty_section_counts[-1],
        },
        "section_coverage": section_coverage,
        "known_empty_body_document_count": len(KNOWN_EMPTY_BODY_DOCUMENT_IDS),
        "normalization_build_sha256": build_sha256,
        "generated_artifact_relative_path": str((Path("artifacts") / "normalized" / NORMALIZER_VERSION).as_posix()),
    }
    summary_path = storage.repo_root / SUMMARY_RELATIVE_PATH
    storage.ensure_dir(summary_path.parent)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Manifest verified: {len(filings)} rows, checksum OK")
    print(f"Source rows resolved: {len(source_rows)}")
    print(f"Normalized documents written: {len(rendered)} -> {out_dir}")
    print(f"normalization_build_sha256: {build_sha256}")
    print(f"Summary written to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
