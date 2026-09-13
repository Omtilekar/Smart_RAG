"""Task 2.9 - audits the canonical chunk metadata schema
(`src/chunk/metadata_schema.py`) against real, frozen artifacts:

    1. Phase 1's 162,357-row chunks.parquet (EDGAR-CORPUS, fixed-window)
    2. A deterministic sample of Task 2.8's real primary-document
       structural nodes (accession-known, section/table-aware)

Read-only throughout - never rewrites `artifacts/chunks/`, never
touches `data/`, never rechunks/embeds/indexes/retrieves. Writes
`results/phase_2_9_chunk_metadata_schema.json`.
"""

from __future__ import annotations

import hashlib
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

from src.chunk import metadata_schema as ms  # noqa: E402
from src.storage import get_storage, safe_component  # noqa: E402

PHASE1_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
PHASE1_CHUNKS_PATH = Path("artifacts") / "chunks" / PHASE1_CHUNK_CONFIG_HASH / "chunks.parquet"
XBRL_DB_PATH = Path("data") / "xbrl.duckdb"

# The one real primary-document parsed artifact used for the compatibility
# sample, produced read-only by Task 2.8's own build - never regenerated
# or rechunked here.
PRIMARY_SAMPLE_DOCUMENT_ID = "primary:100122:0000100122-24-000002"
PRIMARY_SAMPLE_ACCESSION = "0000100122-24-000002"
PRIMARY_SAMPLE_CIK = 100122

# Clearly-labeled synthetic hash for the audit's own demonstration
# records only - Task 2.9 does not build a real Phase 3 chunking
# configuration, so there is no genuine chunk_config_hash to reuse here.
AUDIT_DEMO_CHUNK_CONFIG_HASH = hashlib.sha256(b"task-2.9-primary-compatibility-audit-v1").hexdigest()

RESULT_PATH = Path("results") / "phase_2_9_chunk_metadata_schema.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


HISTORICAL_CHUNK_SCHEMA_VERSION = 1  # this audit's own frozen historical version -
# pinned as a literal, never ms.CHUNK_SCHEMA_VERSION's "current" default, so a
# future schema-semantics bump (e.g. Task 4.2's v1 -> v2) can never silently
# reinterpret this already-frozen Task 2.9 audit under a different version.


def audit_phase1() -> dict:
    table = pq.read_table(PHASE1_CHUNKS_PATH)
    rows = table.to_pylist()

    records = []
    for row in rows:
        local_id = ms.build_chunk_local_id(row["ordinal"])
        uid = ms.build_chunk_uid(
            chunk_schema_version=HISTORICAL_CHUNK_SCHEMA_VERSION, source="edgar_corpus",
            document_id=row["document_id"], chunk_config_hash=row["chunk_config_hash"],
            chunk_local_id=local_id,
        )
        records.append({
            "chunk_schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
            "chunk_uid": uid,
            "chunk_local_id": local_id,
            "document_id": row["document_id"],
            "accession": None,  # EDGAR-CORPUS has no reliable accession linkage - never fabricated
            "cik": row["cik"],
            "company": row["company"],
            "form_type": row["form_type"],
            "fiscal_year": row["fiscal_year"],
            "period_end": None,  # no accession/submission linkage available
            "filed_date": None,
            "sic": None,  # not resolvable without an accession linkage
            "section_id": None,  # fixed-window chunking is section-oblivious
            "section_title": None,
            "ordinal": row["ordinal"],
            "char_start": None,  # computed transiently during chunking, never persisted in the frozen artifact
            "char_end": None,
            "content_type": "prose",  # Phase 1 baseline is pure fixed-window prose, no tables
            "table_id": None,
            "source": "edgar_corpus",
            "text": row["text"],
            "token_count": row["token_count"],
            "chunk_config_hash": row["chunk_config_hash"],
        })

    result = ms.validate_chunk_table(records)

    return {
        "rows_audited": result.row_count,
        "unique_chunk_uids": result.unique_chunk_uids,
        "unique_local_ids": result.unique_local_ids_per_document_config,
        "all_uids_unique": result.unique_chunk_uids == result.row_count,
        "field_coverage": result.field_coverage,
        "source_artifact_modified": False,
    }


def _lookup_submission(con) -> dict:
    row = con.execute(
        "SELECT name, form, fiscal_year, period, filed FROM submissions WHERE adsh = ?",
        [PRIMARY_SAMPLE_ACCESSION],
    ).fetchone()
    if row is None:
        raise SystemExit(f"STOP: submission not found for {PRIMARY_SAMPLE_ACCESSION!r}")
    name, form, fiscal_year, period, filed = row
    return {
        "company": name, "form_type": form, "fiscal_year": int(fiscal_year),
        "period_end": f"{period[0:4]}-{period[4:6]}-{period[6:8]}",
        "filed_date": f"{filed[0:4]}-{filed[4:6]}-{filed[6:8]}",
    }


def _lookup_sic(accession: str) -> int | None:
    """Read-only SIC lookup from the frozen SEC quarterly datasets'
    sub.txt member - same source Task 2.4's dev_test_split.py uses,
    never data/xbrl.duckdb (which has no sic column) and never a new
    download."""
    import zipfile

    raw_xbrl_dir = get_storage().raw_xbrl_root
    for zpath in sorted(raw_xbrl_dir.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            if "sub.txt" not in z.namelist():
                continue
            with z.open("sub.txt") as f:
                header = f.readline().decode("utf-8", errors="replace").rstrip("\n").split("\t")
                try:
                    adsh_idx = header.index("adsh")
                    sic_idx = header.index("sic")
                except ValueError:
                    continue
                for raw_line in f:
                    fields = raw_line.decode("utf-8", errors="replace").rstrip("\n").split("\t")
                    if len(fields) <= max(adsh_idx, sic_idx):
                        continue
                    if fields[adsh_idx] == accession:
                        sic = fields[sic_idx].strip()
                        return int(sic) if sic else None
    return None


def audit_primary_sample(con) -> dict:
    doc_key = safe_component(PRIMARY_SAMPLE_DOCUMENT_ID)
    parsed_path = Path("artifacts") / "primary_docs" / "parsed" / f"{doc_key}.json"
    if not parsed_path.exists():
        raise SystemExit(f"STOP: expected Task 2.8 parsed artifact not found: {parsed_path}")
    with open(parsed_path, encoding="utf-8") as f:
        nodes = json.load(f)

    submission = _lookup_submission(con)
    sic = _lookup_sic(PRIMARY_SAMPLE_ACCESSION)

    narrative_nodes = [n for n in nodes if n["content_type"] == "narrative"][:5]
    table_nodes = [n for n in nodes if n["content_type"] == "table"][:5]
    sample_nodes = narrative_nodes + table_nodes

    records = []
    for node in sample_nodes:
        canonical_content_type = "prose" if node["content_type"] == "narrative" else "table"
        local_id = ms.build_chunk_local_id(node["source_order"], section_id=node["section_id"])
        uid = ms.build_chunk_uid(
            chunk_schema_version=HISTORICAL_CHUNK_SCHEMA_VERSION, source="primary",
            document_id=PRIMARY_SAMPLE_DOCUMENT_ID, chunk_config_hash=AUDIT_DEMO_CHUNK_CONFIG_HASH,
            chunk_local_id=local_id,
        )
        # word-count approximation for this schema-compatibility
        # demonstration only - NOT a real tokenizer count (Section 33 -
        # the real token_count must follow the eventual chunking
        # configuration's own tokenizer, which Task 2.9 does not build).
        approx_token_count = max(1, len(node["text"].split()))

        records.append({
            "chunk_schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
            "chunk_uid": uid,
            "chunk_local_id": local_id,
            "document_id": PRIMARY_SAMPLE_DOCUMENT_ID,
            "accession": PRIMARY_SAMPLE_ACCESSION,
            "cik": PRIMARY_SAMPLE_CIK,
            "company": submission["company"],
            "form_type": submission["form_type"],
            "fiscal_year": submission["fiscal_year"],
            "period_end": submission["period_end"],
            "filed_date": submission["filed_date"],
            "sic": sic,
            "section_id": node["section_id"],
            "section_title": node["section_title"],
            "ordinal": node["source_order"],
            "char_start": None,  # Docling's HTML backend has no byte/char provenance (Task 2.8's documented limitation)
            "char_end": None,
            "content_type": canonical_content_type,
            "table_id": node["table_id"],
            "source": "primary",
            "text": node["text"] if node["text"] else "(empty)",
            "token_count": approx_token_count,
            "chunk_config_hash": AUDIT_DEMO_CHUNK_CONFIG_HASH,
        })

    result = ms.validate_chunk_table(records)

    return {
        "samples_audited": result.row_count,
        "narrative_samples": len(narrative_nodes),
        "table_samples": len(table_nodes),
        "unique_chunk_uids": result.unique_chunk_uids,
        "all_uids_unique": result.unique_chunk_uids == result.row_count,
        "accession_populated": all(r["accession"] is not None for r in records),
        "period_end_populated": all(r["period_end"] is not None for r in records),
        "filed_date_populated": all(r["filed_date"] is not None for r in records),
        "sic_populated": sic is not None,
        "field_coverage": result.field_coverage,
        "source_artifact_modified": False,
        "note": "chunk_config_hash and token_count in this sample are audit-only placeholders (Task 2.9 does not build a real Phase 3 chunking configuration or tokenizer pipeline) - see project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md.",
    }


def cross_source_uid_isolation_check() -> bool:
    """Section 51: the same document_id under two different sources must
    never collide."""
    local_id = ms.build_chunk_local_id(0)
    uid_a = ms.build_chunk_uid(chunk_schema_version=1, source="edgar_corpus", document_id="X", chunk_config_hash="a" * 64, chunk_local_id=local_id)
    uid_b = ms.build_chunk_uid(chunk_schema_version=1, source="primary", document_id="X", chunk_config_hash="a" * 64, chunk_local_id=local_id)
    return uid_a != uid_b


def main() -> None:
    print("=== Task 2.9 chunk metadata schema audit ===")

    phase1_result = audit_phase1()
    print(f"Phase 1: {phase1_result['rows_audited']} rows, {phase1_result['unique_chunk_uids']} unique UIDs, all unique: {phase1_result['all_uids_unique']}")

    con = duckdb.connect(str(XBRL_DB_PATH), read_only=True)
    try:
        primary_result = audit_primary_sample(con)
    finally:
        con.close()
    print(f"Primary sample: {primary_result['samples_audited']} nodes audited, all unique UIDs: {primary_result['all_uids_unique']}")

    isolation_ok = cross_source_uid_isolation_check()
    print(f"Cross-source UID isolation: {'PASS' if isolation_ok else 'FAIL'}")
    if not isolation_ok:
        raise SystemExit("STOP: cross-source chunk_uid collision detected")

    summary = {
        # matches every individual record's own "chunk_schema_version" above -
        # this audit's historical data was built under v1, pinned as a literal.
        "chunk_schema_version": HISTORICAL_CHUNK_SCHEMA_VERSION,
        "canonical_fields": [
            {"name": f.name, "type": str(f.pa_type), "nullable": f.nullable, "description": f.description}
            for f in ms.CANONICAL_FIELDS
        ],
        "content_types": list(ms.CONTENT_TYPES),
        "source_values": list(ms.SOURCE_VALUES),
        "chunk_uid_algorithm": "SHA-256 over canonical JSON of {chunk_schema_version, source, document_id, chunk_config_hash, chunk_local_id}",
        "chunk_local_id_contract": "document-local, computable without cross-document information; format \"chunk{ordinal:06d}\" or \"{section_id}:chunk{ordinal:06d}\"",
        "offset_contract": "zero-based, half-open [char_start, char_end); both-NULL or both-populated; NULL when no defensible contiguous span exists",
        "phase1_compatibility": phase1_result,
        "primary_compatibility": primary_result,
        "cross_source_uid_isolation": isolation_ok,
        "known_limitations": [
            "Phase 1 chunks: char_start/char_end were computed transiently during chunking but never persisted in the frozen artifact - honestly NULL, not re-derived by rechunking.",
            "Phase 1 chunks: section_id is NULL (fixed-window chunking is section-oblivious) and accession/period_end/filed_date/sic are NULL (no accession linkage exists for EDGAR-CORPUS).",
            "Primary sample: char_start/char_end are NULL - Docling's HTML backend has no byte/char source provenance (documented in Task 2.8).",
            "Primary sample: chunk_config_hash and token_count are audit-only placeholders, not a real Phase 3 chunking configuration/tokenizer.",
            "Task 2.8's 45,769 would-be-gold evidence facts remain status quo - Task 2.9 does not promote them; chunk_recall@10/chunk_mrr's available_for_current_gold remain false.",
        ],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2) + "\n")

    print(f"Written: {RESULT_PATH}")


if __name__ == "__main__":
    main()
