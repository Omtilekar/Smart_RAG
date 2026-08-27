"""Task 1.1 - Select the Phase 1 development corpus.

Reads frozen `data/edgar_corpus/*.parquet` and `data/xbrl.duckdb`
(read-only, never mutated), independently reconstructs the authoritative
EDGAR-CORPUS <-> XBRL 10-K 2016-2020 alignment defined in
`src/ingest/audit_data.py`'s `check2_10k_alignment()` (see
`DATA_READINESS_REPORT.md`, "Check 2"), validates the reconstruction against
the frozen 5,646 / 6,950 = 81.24% figure, and deterministically selects
1,500 filings from the aligned population.

User-approved decisions this script encodes (Task 1.1 stopped and asked
before implementing any of these three, since no existing documentation
resolved them):

1. XBRL duplicate 10-K accessions: 29 of the 5,646 aligned (cik, fiscal_year)
   pairs in 2016-2020 have more than one candidate 10-K `adsh` sharing that
   fiscal year. No canonical accession is chosen for these - matching the
   audited Check-2 methodology, which only proves alignment EXISTS and never
   picks one. Each manifest row instead records `xbrl_10k_candidate_count`.
2. Selection rule: SHA-256 over each eligible filing's stable EDGAR-CORPUS
   `filename` identity, ascending, first 1,500 - no seed to lose, no RNG
   version dependency.
3. Manifest location: `results/phase_1_1_development_corpus.json` (tracked
   in Git, per REPOSITORY_STRUCTURE.md's existing results/*.json exception).

This script does not normalize, chunk, embed, or index anything - it only
selects and records which 1,500 filings later Phase 1 tasks will consume.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.storage import get_storage  # noqa: E402

MANIFEST_SCHEMA_VERSION = "1.0"
ELIGIBLE_YEAR_MIN = 2016
ELIGIBLE_YEAR_MAX = 2020
SELECTION_COUNT = 1500
MANIFEST_RELATIVE_PATH = Path("results") / "phase_1_1_development_corpus.json"


# --------------------------------------------------------------------------
# Pure, deterministic logic (unit-testable without touching frozen data)
# --------------------------------------------------------------------------

def selection_hash(document_id: str) -> str:
    """SHA-256 hex digest over a filing's stable document identity.
    This is the sort key for deterministic selection (user-approved
    Option A) - not a security hash, just a deterministic shuffle."""
    return hashlib.sha256(document_id.encode("utf-8")).hexdigest()


def select_top_n(eligible_rows: list[dict], n: int) -> list[dict]:
    """Deterministically select `n` rows from `eligible_rows` by ascending
    SHA-256(document_id). No replacement. Raises if fewer than `n` rows are
    available or if any document_id is duplicated."""
    ids = [r["document_id"] for r in eligible_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("eligible_rows contains duplicate document_id values")
    if len(eligible_rows) < n:
        raise ValueError(f"only {len(eligible_rows)} eligible rows, need {n}")
    ordered = sorted(eligible_rows, key=lambda r: selection_hash(r["document_id"]))
    return ordered[:n]


def canonical_sort(rows: list[dict]) -> list[dict]:
    """Canonical storage order for the final manifest: ascending by
    document_id. This is purely for on-disk readability/diffability and is
    independent of (and does not affect) which rows were selected above."""
    return sorted(rows, key=lambda r: r["document_id"])


def manifest_checksum(filings: list[dict]) -> str:
    """SHA-256 over the canonical JSON serialization of the `filings` array
    only (sorted keys, no whitespace) - not the whole manifest document, so
    the hash is not self-referential. Named `development_manifest_sha256`
    to avoid confusion with `chunk_config_hash` (a later, unrelated
    concept)."""
    blob = json.dumps(filings, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def filings_per_entity_stats(rows: list[dict], key: str = "cik") -> dict:
    counts: dict[int, int] = {}
    for r in rows:
        counts[r[key]] = counts.get(r[key], 0) + 1
    values = sorted(counts.values())
    if not values:
        return {"unique": 0, "min": None, "median": None, "p95": None, "max": None}
    p95_idx = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
    return {
        "unique": len(values),
        "min": values[0],
        "median": median(values),
        "p95": values[p95_idx],
        "max": values[-1],
    }


def year_distribution(rows: list[dict]) -> dict:
    total = len(rows)
    counts: dict[int, int] = {}
    for r in rows:
        counts[r["year"]] = counts.get(r["year"], 0) + 1
    return {
        str(y): {"count": counts.get(y, 0), "pct": round(100.0 * counts.get(y, 0) / total, 2) if total else 0.0}
        for y in range(ELIGIBLE_YEAR_MIN, ELIGIBLE_YEAR_MAX + 1)
    }


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


# --------------------------------------------------------------------------
# Large-data reconstruction (reads frozen data/, read-only)
# --------------------------------------------------------------------------

def build_edgar_union_sql(edgar_corpus_root: Path) -> tuple[str, dict[str, Path]]:
    splits = {s: edgar_corpus_root / f"{s}.parquet" for s in ("train", "test", "validation")}
    existing = {s: p for s, p in splits.items() if p.exists()}
    if not existing:
        raise SystemExit(f"FATAL: no EDGAR-CORPUS split parquet files found under {edgar_corpus_root}")
    parts = [
        f"SELECT '{s}' AS split, * FROM read_parquet('{p.as_posix()}')" for s, p in existing.items()
    ]
    return " UNION ALL ".join(parts), existing


def reconstruct_eligible_population(con: duckdb.DuckDBPyConnection, edgar_union_sql: str) -> dict:
    """Reproduces src/ingest/audit_data.py's check2_10k_alignment() exactly:
    EDGAR (cik, year) restricted to 2016-2020, matched against XBRL 10-K
    submissions where fiscal_year == EDGAR year (the chosen semantic
    alignment field, per DATA_READINESS_REPORT.md 'Check 2', Step 2A/2C).
    """
    con.execute("""
        CREATE OR REPLACE TEMP VIEW xbrl_10k AS
        SELECT DISTINCT cik, adsh, fiscal_year AS fy, name
        FROM xbrl.submissions WHERE form = '10-K'
    """)
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW edgar_rows AS
        SELECT split, filename, TRY_CAST(cik AS BIGINT) AS cik, TRY_CAST(year AS INTEGER) AS yr
        FROM ({edgar_union_sql})
        WHERE TRY_CAST(cik AS BIGINT) IS NOT NULL AND TRY_CAST(year AS INTEGER) IS NOT NULL
    """)

    rejected = con.execute(f"""
        SELECT count(*) FROM ({edgar_union_sql})
        WHERE TRY_CAST(cik AS BIGINT) IS NULL OR TRY_CAST(year AS INTEGER) IS NULL
    """).fetchone()[0]

    dup_cik_year = con.execute("""
        SELECT count(*) FROM (
            SELECT cik, yr FROM edgar_rows GROUP BY cik, yr HAVING count(DISTINCT filename) > 1
        )
    """).fetchone()[0]
    if dup_cik_year:
        raise SystemExit(
            f"FATAL: {dup_cik_year} EDGAR-CORPUS (cik, year) pairs map to more than one "
            f"filename - no approved duplicate-resolution rule exists for this case. STOP."
        )

    total_denom = con.execute(
        "SELECT count(*) FROM edgar_rows WHERE yr BETWEEN ? AND ?",
        [ELIGIBLE_YEAR_MIN, ELIGIBLE_YEAR_MAX],
    ).fetchone()[0]

    matched = con.execute("""
        WITH e AS (SELECT * FROM edgar_rows WHERE yr BETWEEN ? AND ?)
        SELECT e.split, e.filename, e.cik, e.yr,
               count(DISTINCT x.adsh) AS xbrl_10k_candidate_count,
               min(x.name) AS company_name
        FROM e JOIN xbrl_10k x ON e.cik = x.cik AND x.fy = e.yr
        GROUP BY e.split, e.filename, e.cik, e.yr
    """, [ELIGIBLE_YEAR_MIN, ELIGIBLE_YEAR_MAX]).fetchall()

    dup_xbrl_candidates = sum(1 for row in matched if row[4] > 1)

    eligible_rows = [
        {
            "document_id": filename,
            "cik": int(cik),
            "year": int(yr),
            "source": "edgar_corpus",
            "source_split": split,
            "source_filename": filename,
            "company_name": company_name,
            "xbrl_alignment_year_field": "fy",
            "xbrl_10k_candidate_count": int(candidate_count),
        }
        for split, filename, cik, yr, candidate_count, company_name in matched
    ]

    return {
        "eligible_rows": eligible_rows,
        "eligible_count": len(eligible_rows),
        "eligible_denominator": total_denom,
        "rejected_type_conversion_rows": rejected,
        "dup_edgar_cik_year_pairs": dup_cik_year,
        "dup_xbrl_10k_candidate_pairs_in_window": dup_xbrl_candidates,
    }


def build_manifest(storage, con: duckdb.DuckDBPyConnection) -> dict:
    edgar_union_sql, existing_splits = build_edgar_union_sql(storage.edgar_corpus_root)
    result = reconstruct_eligible_population(con, edgar_union_sql)

    eligible_count = result["eligible_count"]
    eligible_denominator = result["eligible_denominator"]
    if eligible_count != 5646 or eligible_denominator != 6950:
        raise SystemExit(
            f"FATAL: eligible population reconstruction does not match the frozen authoritative "
            f"figure. Expected 5,646 / 6,950 = 81.24%; observed {eligible_count:,} / "
            f"{eligible_denominator:,} = {eligible_count / eligible_denominator:.2%}. "
            f"STOP - do not proceed to selection. Investigate before adjusting filters."
        )

    eligible_rows = result["eligible_rows"]
    for row in eligible_rows:
        if not (ELIGIBLE_YEAR_MIN <= row["year"] <= ELIGIBLE_YEAR_MAX):
            raise SystemExit(f"FATAL: eligible row outside year window: {row}")

    selected_rows = select_top_n(eligible_rows, SELECTION_COUNT)
    if len(selected_rows) != SELECTION_COUNT:
        raise SystemExit(f"FATAL: selected {len(selected_rows)} rows, expected {SELECTION_COUNT}")
    selected_ids = {r["document_id"] for r in selected_rows}
    if len(selected_ids) != SELECTION_COUNT:
        raise SystemExit("FATAL: duplicate document_id among selected rows")
    eligible_ids = {r["document_id"] for r in eligible_rows}
    if not selected_ids.issubset(eligible_ids):
        raise SystemExit("FATAL: a selected row is not a member of the eligible population")

    filings = canonical_sort(selected_rows)
    dev_manifest_sha256 = manifest_checksum(filings)

    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "phase_1.1_select_development_corpus",
        "git_sha": git_sha(),
        "source_datasets": {
            "edgar_corpus": {
                "root": "data/edgar_corpus",
                "splits_present": sorted(existing_splits.keys()),
                "distinct_filings_total": 91086,
            },
            "xbrl": {
                "db": "data/xbrl.duckdb",
                "restricted_form": "10-K",
            },
        },
        "eligible_window_years": [ELIGIBLE_YEAR_MIN, ELIGIBLE_YEAR_MAX],
        "alignment_definition": {
            "reference": (
                "src/ingest/audit_data.py check2_10k_alignment(); "
                "DATA_READINESS_REPORT.md 'Check 2'"
            ),
            "edgar_fields": ["cik", "year", "filename", "split"],
            "xbrl_fields": ["cik", "form='10-K'", "fiscal_year (fy)", "adsh", "name"],
            "year_semantic_field": "fy",
            "cik_normalization": "TRY_CAST(cik AS BIGINT) on both sides; unconvertible rows rejected, not coerced",
            "year_normalization": "TRY_CAST(year AS INTEGER); unconvertible rows rejected, not coerced",
            "join_grain": "(cik, year): eligible if a 10-K submission for that cik has fiscal_year == EDGAR year",
            "rejected_type_conversion_rows": result["rejected_type_conversion_rows"],
            "duplicate_edgar_cik_year_pairs": result["dup_edgar_cik_year_pairs"],
            "duplicate_xbrl_10k_candidates_in_window": result["dup_xbrl_10k_candidate_pairs_in_window"],
            "duplicate_resolution_policy": (
                "User-approved (Task 1.1): no canonical XBRL adsh is chosen when a (cik, fy) pair "
                "has multiple candidate 10-K accessions - this matches the audited Check-2 "
                "methodology, which only proves alignment EXISTS. xbrl_10k_candidate_count records "
                "the ambiguity per row instead of fabricating a resolution."
            ),
            "accession_limitation": (
                "EDGAR-CORPUS carries no accession-number field and none can be reliably "
                "reconstructed from it (DATA_READINESS_REPORT.md 'Check 2', Step 2E). No EDGAR "
                "accession is fabricated anywhere in this manifest. XBRL adsh values are alignment "
                "evidence only, never labeled as an EDGAR accession."
            ),
        },
        "eligible_count": eligible_count,
        "eligible_denominator": eligible_denominator,
        "eligible_coverage_pct": round(100.0 * eligible_count / eligible_denominator, 2),
        "selection_count": SELECTION_COUNT,
        "selection_method": (
            "User-approved Option A: SHA-256(document_id=EDGAR filename), ascending, first "
            f"{SELECTION_COUNT}. No replacement. No seed (deterministic hash order, not a PRNG)."
        ),
        "seed": None,
        "storage_sort_rule": (
            "The 'filings' array below is stored canonically sorted by document_id ascending, "
            "for readability/diffability. This is NOT the selection order (which is ascending "
            "SHA-256(document_id)) and does not affect which rows were selected."
        ),
        "development_manifest_sha256": dev_manifest_sha256,
        "eligible_population_distribution": {
            "count": eligible_count,
            "unique_ciks": filings_per_entity_stats(eligible_rows)["unique"],
            "by_year": year_distribution(eligible_rows),
            "filings_per_cik": filings_per_entity_stats(eligible_rows),
        },
        "selected_corpus_distribution": {
            "count": len(filings),
            "unique_ciks": filings_per_entity_stats(filings)["unique"],
            "unique_company_names": len({r["company_name"] for r in filings if r["company_name"]}),
            "by_year": year_distribution(filings),
            "filings_per_cik": filings_per_entity_stats(filings),
        },
        "filings": filings,
    }
    return manifest


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------

def main() -> int:
    storage = get_storage()
    storage.require_dir(storage.edgar_corpus_root)
    storage.require_file(storage.xbrl_db)

    con = duckdb.connect()
    con.execute(f"ATTACH '{storage.xbrl_db.as_posix()}' AS xbrl (READ_ONLY)")
    try:
        manifest = build_manifest(storage, con)
    finally:
        con.close()

    manifest_path = storage.repo_root / MANIFEST_RELATIVE_PATH
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_hash = existing.get("development_manifest_sha256")
        new_hash = manifest["development_manifest_sha256"]
        if existing_hash != new_hash:
            print(
                f"FATAL: an existing manifest at {manifest_path} has a different checksum "
                f"({existing_hash}) than the freshly reconstructed selection ({new_hash}). "
                f"Refusing to overwrite a prior frozen development-corpus manifest silently. "
                f"STOP AND ASK before proceeding.",
                file=sys.stderr,
            )
            return 1
        print(f"Existing manifest checksum matches recomputed selection ({new_hash}); rewriting (idempotent).")

    storage.ensure_dir(manifest_path.parent)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Eligible population: {manifest['eligible_count']:,} / {manifest['eligible_denominator']:,} "
          f"= {manifest['eligible_coverage_pct']:.2f}%")
    print(f"Selected: {manifest['selection_count']:,} filings")
    print(f"Unique CIKs selected: {manifest['selected_corpus_distribution']['unique_ciks']:,}")
    print(f"development_manifest_sha256: {manifest['development_manifest_sha256']}")
    print(f"Manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
