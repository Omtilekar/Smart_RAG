"""Task 2.8 - primary-document parsing + inline-XBRL evidence alignment
orchestration.

    python scripts/build_primary_evidence.py --dry-run
    python scripts/build_primary_evidence.py --pilot
    python scripts/build_primary_evidence.py --full

Reuses:
    src/parse/source_identity.py    - deterministic source identity
    src/parse/primary_html.py       - Docling-based structural parsing
    src/parse/inline_xbrl.py        - raw inline-XBRL DOM extraction
    src/parse/evidence_alignment.py - alignment against the frozen
                                       Task 2.1 truth contract / Task 2.2
                                       tag registry (never reimplemented)

Never writes to data/raw/primary/, data/xbrl.duckdb, or any other frozen
source. All derived artifacts live under artifacts/primary_docs/
(GITIGNORED). Resumable: a document is only re-parsed if its
source_sha256 or the current parser_config_hash no longer matches the
manifest's recorded value for it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import duckdb  # noqa: E402

from src.storage import get_storage, safe_component  # noqa: E402
from src.eval.tag_registry import get_registry, compute_registry_hash  # noqa: E402
from src.eval.truth_contract import (  # noqa: E402
    CONTRACT_VERSION, build_contract_config, compute_contract_config_hash,
    SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX,
)
from src.parse import source_identity as sid  # noqa: E402
from src.parse import primary_html as ph  # noqa: E402
from src.parse import inline_xbrl as ix  # noqa: E402
from src.parse import evidence_alignment as ea  # noqa: E402

PARSER_NAME = "docling"
PARSER_VERSION = "1.0"
TABLE_SERIALIZATION = "markdown"

_storage = get_storage()
PRIMARY_DOCS_ROOT = _storage.primary_docs_root
XBRL_DB_PATH = _storage.repo_root / "data" / "xbrl.duckdb"

EVIDENCE_ROOT = _storage.artifacts_root / "primary_docs"
PARSED_DIR = EVIDENCE_ROOT / "parsed"
INLINE_XBRL_DIR = EVIDENCE_ROOT / "inline_xbrl"
EVIDENCE_DIR = EVIDENCE_ROOT / "evidence"
FAILURES_PATH = EVIDENCE_ROOT / "failures" / "failures.json"
MANIFEST_PATH = EVIDENCE_ROOT / "manifest.json"

CONFIG_PATH = Path("configs") / "phase_2_8_primary_evidence.json"
SUMMARY_PATH = Path("results") / "phase_2_8_primary_evidence_summary.json"

# Deterministic pilot selection (Section 55) - diverse by file size,
# picked from the sorted source list by fixed rank/index rather than
# hand-picked "easy" filings.
PILOT_SIZE = 20


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def build_config() -> dict:
    return {
        "parser_name": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "table_serialization": TABLE_SERIALIZATION,
        "table_row_group_size": ph.TABLE_ROW_GROUP_SIZE,
        "section_detection_policy": "last-occurrence-of-canonical-Item-heading-regex",
        "node_id_scheme": "{document_id}#node-{ordinal:05d}",
        "inline_xbrl_extraction_version": "1.1",  # 1.1: divide-unit (EPS) support added
        "numeric_normalization_version": "1.1",  # 1.1: hundred/thousand/million number-word compounds, "no"/"none"/"nil" zero synonyms
        "alignment_version": "1.2",  # 1.2: tag-support checked before requiring a resolved unit (unsupported-tag/non-monetary-count facts no longer misreported as parse_error)
        "evidence_schema_version": ea.EVIDENCE_SCHEMA_VERSION,
        "truth_contract_version": CONTRACT_VERSION,
        "tag_registry_source": "configs/eval_tags.yaml",
    }


def compute_config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_doc_key(document_id: str) -> str:
    return safe_component(document_id)


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"not JSON serializable: {type(obj)}")


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"documents": {}}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    tmp.replace(MANIFEST_PATH)


def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, default=_decimal_default)
    tmp.replace(path)


def select_pilot(all_docs: list[sid.SourceDocument], n: int = PILOT_SIZE) -> list[sid.SourceDocument]:
    """Deterministic diverse pilot: sort by source_size_bytes, take
    evenly-spaced rank positions (smallest, largest, and points in
    between) - never a hand-picked "easy" subset (Section 55)."""
    by_size = sorted(all_docs, key=lambda d: (d.source_size_bytes, d.document_id))
    if len(by_size) <= n:
        return by_size
    step = (len(by_size) - 1) / (n - 1)
    indices = sorted({round(i * step) for i in range(n)})
    return [by_size[i] for i in indices]


def process_document(doc: sid.SourceDocument, config_hash: str, con, registry_hash: str,
                      truth_contract_hash: str) -> dict:
    """Parses one document end to end. Returns a summary dict with
    counts for aggregation. Any exception here is the caller's
    responsibility to catch and record as a failure - this function
    itself does not catch (never silently swallow a real bug)."""
    doc_key = _safe_doc_key(doc.document_id)

    docling_doc = ph.convert_document(doc.source_path)
    nodes = ph.build_structural_nodes(doc.document_id, docling_doc)
    atomic_write_json(PARSED_DIR / f"{doc_key}.json", [asdict(n) for n in nodes])

    root = ix.parse_xml(doc.source_path)
    contexts = ix.extract_contexts(root)
    units = ix.extract_units(root)
    raw_facts = ix.extract_inline_facts(root)
    atomic_write_json(INLINE_XBRL_DIR / f"{doc_key}.json", {
        "contexts": {cid: asdict(c) for cid, c in contexts.items()},
        "units": {uid: asdict(u) for uid, u in units.items()},
        "facts": [asdict(f) for f in raw_facts],
    })

    fiscal_year_row = con.execute("SELECT fiscal_year FROM submissions WHERE adsh = ?", [doc.accession]).fetchone()
    fiscal_year = int(fiscal_year_row[0]) if fiscal_year_row else None

    evidence_records = []
    status_counts: dict[str, int] = {}
    for fact in raw_facts:
        if fact.fact_kind != "nonFraction" or fact.normalized_value is None:
            continue  # nonNumeric/nil facts extracted but not evaluated for numeric alignment
        context = contexts.get(fact.context_ref)
        if context is None:
            status_counts["parse_error"] = status_counts.get("parse_error", 0) + 1
            continue
        namespace, tag = ea.bare_tag_name(fact.concept_qname)
        period = ix.context_to_truth_contract_period(context)
        unit = units.get(fact.unit_ref) if fact.unit_ref else None
        uom = ea.unit_to_uom(unit) if unit else None

        if fiscal_year is None:
            status = "parse_error"
            eligible = False
            node_ids: list[str] = []
        else:
            # tag-support is checked before requiring a resolved unit -
            # a tag outside the registry (the overwhelming majority of
            # inline facts: property/loan/segment counts, extension
            # concepts, etc.) is "unsupported_tag" regardless of whether
            # its unit could be mapped to a canonical uom. Only a
            # registry-supported tag with an unresolvable unit is a
            # genuine parse_error.
            eligibility = ea.check_eligibility_dimensions(
                tag=tag, namespace=namespace, uom=uom, qtrs=period.qtrs,
                has_dimensions=bool(context.dimensions), fiscal_year=fiscal_year,
            )
            if eligibility.tag_supported and uom is None:
                status = "parse_error"
                eligible = False
                node_ids = []
            else:
                raw_match = None
                if eligibility.tag_supported and eligibility.dimension_free:
                    # only attempt the coreg/segments-blank raw match once
                    # the fact is confirmed non-dimensional - a dimensional
                    # fact never matches that grain and would be
                    # miscategorized as "unmatched" rather than
                    # "ineligible_dimensional".
                    identity = ea.FactIdentity(
                        accession=doc.accession, cik=doc.cik, tag=tag,
                        ddate=period.ddate, qtrs=period.qtrs, uom=uom,
                    )
                    raw_match = ea.match_against_raw_facts(con, identity, fact.normalized_value)
                node_ids = ea.find_candidate_nodes(fact.raw_display_text, nodes) if raw_match and raw_match.status == "exact" else []
                status = ea.determine_alignment_status(raw_match=raw_match, eligibility=eligibility, node_ids=node_ids)
                eligible = ea.is_fully_eligible(eligibility) and status == "exact"

        status_counts[status] = status_counts.get(status, 0) + 1

        matched_node = next((n for n in nodes if n.node_id == node_ids[0]), None) if node_ids else None
        evidence_records.append(asdict(ea.EvidenceRecord(
            evidence_schema_version=ea.EVIDENCE_SCHEMA_VERSION,
            evidence_id=ea.build_evidence_id(doc.document_id, fact.element_id, fact.source_order),
            document_id=doc.document_id, cik=doc.cik, accession=doc.accession,
            fiscal_year=fiscal_year or 0,
            section_id=matched_node.section_id if matched_node else None,
            section_title=matched_node.section_title if matched_node else None,
            node_ids=tuple(node_ids), content_type=matched_node.content_type if matched_node else None,
            concept_name=tag, concept_namespace=namespace,
            context_ref=fact.context_ref, unit_ref=fact.unit_ref,
            raw_display_value=fact.raw_display_text,
            normalized_value=str(fact.normalized_value) if fact.normalized_value is not None else None,
            canonical_unit=uom,
            alignment_status=status, eligible_for_gold=eligible,
            truth_contract_version=CONTRACT_VERSION, truth_contract_hash=truth_contract_hash,
            tag_registry_version=get_registry().version, tag_registry_hash=registry_hash,
        )))

    atomic_write_json(EVIDENCE_DIR / f"{doc_key}.json", evidence_records)

    return {
        "document_id": doc.document_id,
        "node_count": len(nodes),
        "table_count": len({n.table_id for n in nodes if n.table_id}),
        "inline_fact_count": len(raw_facts),
        "nonfraction_count": sum(1 for f in raw_facts if f.fact_kind == "nonFraction"),
        "nonnumeric_count": sum(1 for f in raw_facts if f.fact_kind == "nonNumeric"),
        "context_count": len(contexts),
        "unit_count": len(units),
        "status_counts": status_counts,
        "gold_evidence_count": sum(1 for r in evidence_records if r["eligible_for_gold"]),
    }


def cmd_dry_run() -> None:
    print("=== Primary evidence dry run ===")
    docs = sid.enumerate_primary_documents(PRIMARY_DOCS_ROOT)
    total_bytes = sum(d.source_size_bytes for d in docs)
    print(f"source documents: {len(docs)}")
    print(f"source bytes: {total_bytes:,} ({total_bytes / 1e9:.2f} GB)")
    print(f"unique CIKs: {len({d.cik for d in docs})}")
    print(f"unique accessions: {len({d.accession for d in docs})}")

    config = build_config()
    config_hash = compute_config_hash(config)
    print(f"parser_config_hash: {config_hash}")

    registry = get_registry()
    registry_hash = compute_registry_hash(registry)
    contract_config = build_contract_config(registry.supported_tags())
    truth_contract_hash = compute_contract_config_hash(contract_config)
    print(f"tag_registry_hash: {registry_hash}")
    print(f"truth_contract_hash: {truth_contract_hash}")
    print(f"supported fiscal year window: {SUPPORTED_FISCAL_YEAR_MIN}-{SUPPORTED_FISCAL_YEAR_MAX}")

    free = shutil.disk_usage(REPO_ROOT.anchor or "/").free
    print(f"free disk: {free / 1e9:.2f} GB")
    print(f"output root: {EVIDENCE_ROOT}")

    manifest = load_manifest()
    resumable = sum(1 for d in docs if manifest["documents"].get(d.document_id, {}).get("source_sha256") == d.source_sha256
                     and manifest["documents"].get(d.document_id, {}).get("parser_config_hash") == config_hash
                     and manifest["documents"].get(d.document_id, {}).get("status") == "success")
    print(f"already-resumable documents: {resumable}/{len(docs)}")
    print("DRY RUN OK")


def _run(docs: list[sid.SourceDocument], label: str) -> None:
    started = time.time()
    config = build_config()
    config_hash = compute_config_hash(config)

    con = duckdb.connect(str(XBRL_DB_PATH), read_only=True)
    registry = get_registry()
    registry_hash = compute_registry_hash(registry)
    contract_config = build_contract_config(registry.supported_tags())
    truth_contract_hash = compute_contract_config_hash(contract_config)

    manifest = load_manifest()
    failures = []
    if FAILURES_PATH.exists():
        with open(FAILURES_PATH, encoding="utf-8") as f:
            failures = json.load(f)

    aggregate = {
        "parsed": 0, "failed": 0, "skipped_resumed": 0,
        "node_count": 0, "table_count": 0, "inline_fact_count": 0,
        "nonfraction_count": 0, "nonnumeric_count": 0,
        "context_count": 0, "unit_count": 0,
        "status_counts": {}, "gold_evidence_count": 0,
    }

    for i, doc in enumerate(docs, start=1):
        existing = manifest["documents"].get(doc.document_id)
        if (existing and existing.get("source_sha256") == doc.source_sha256
                and existing.get("parser_config_hash") == config_hash
                and existing.get("status") == "success"):
            aggregate["skipped_resumed"] += 1
            for k in ("node_count", "table_count", "inline_fact_count", "nonfraction_count", "nonnumeric_count", "context_count", "unit_count", "gold_evidence_count"):
                aggregate[k] += existing.get(k, 0)
            for status, count in existing.get("status_counts", {}).items():
                aggregate["status_counts"][status] = aggregate["status_counts"].get(status, 0) + count
            continue

        try:
            result = process_document(doc, config_hash, con, registry_hash, truth_contract_hash)
            manifest["documents"][doc.document_id] = {
                "status": "success", "source_sha256": doc.source_sha256,
                "parser_config_hash": config_hash, **result,
            }
            aggregate["parsed"] += 1
            for k in ("node_count", "table_count", "inline_fact_count", "nonfraction_count", "nonnumeric_count", "context_count", "unit_count", "gold_evidence_count"):
                aggregate[k] += result.get(k, 0)
            for status, count in result.get("status_counts", {}).items():
                aggregate["status_counts"][status] = aggregate["status_counts"].get(status, 0) + count
        except Exception as exc:
            manifest["documents"][doc.document_id] = {
                "status": "failed", "source_sha256": doc.source_sha256, "parser_config_hash": config_hash,
            }
            failures.append({
                "document_id": doc.document_id, "cik": doc.cik, "accession": doc.accession,
                "source_path": doc.source_path, "error_type": type(exc).__name__,
                "error": str(exc)[:500], "stage": "process_document",
            })
            aggregate["failed"] += 1

        save_manifest(manifest)
        atomic_write_json(FAILURES_PATH, failures)

        if i % 5 == 0 or i == len(docs):
            print(f"[{label}] {i}/{len(docs)} documents processed ({time.time() - started:.1f}s elapsed)")

    con.close()

    elapsed = time.time() - started
    print(f"[{label}] complete: {aggregate['parsed']} parsed, {aggregate['failed']} failed, "
          f"{aggregate['skipped_resumed']} resumed, {elapsed:.1f}s")
    print(json.dumps(aggregate, indent=2))


def cmd_pilot() -> None:
    print(f"=== Primary evidence PILOT ({PILOT_SIZE} filings, PILOT ONLY) ===")
    all_docs = sid.enumerate_primary_documents(PRIMARY_DOCS_ROOT)
    pilot_docs = select_pilot(all_docs, PILOT_SIZE)
    print("pilot documents:", [d.document_id for d in pilot_docs])
    _run(pilot_docs, "PILOT")


def cmd_full() -> None:
    print("=== Primary evidence FULL RUN (990 filings) ===")
    all_docs = sid.enumerate_primary_documents(PRIMARY_DOCS_ROOT)
    _run(all_docs, "FULL")

    config = build_config()
    config_hash = compute_config_hash(config)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({**config, "parser_config_hash": config_hash}, indent=2) + "\n")

    manifest = load_manifest()
    docs_summary = manifest["documents"]
    successful = [d for d in docs_summary.values() if d.get("status") == "success"]

    registry = get_registry()
    registry_hash = compute_registry_hash(registry)
    contract_config = build_contract_config(registry.supported_tags())
    truth_contract_hash = compute_contract_config_hash(contract_config)

    total_status_counts: dict[str, int] = {}
    for d in successful:
        for status, count in d.get("status_counts", {}).items():
            total_status_counts[status] = total_status_counts.get(status, 0) + count

    summary = {
        "evidence_schema_version": ea.EVIDENCE_SCHEMA_VERSION,
        "parser_config_hash": config_hash,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha(),
        "source_document_count": len(sid.enumerate_primary_documents(PRIMARY_DOCS_ROOT)),
        "parsed_document_count": len(successful),
        "parse_failure_count": sum(1 for d in docs_summary.values() if d.get("status") == "failed"),
        "table_count": sum(d.get("table_count", 0) for d in successful),
        "inline_fact_count": sum(d.get("inline_fact_count", 0) for d in successful),
        "eligible_fact_count": total_status_counts.get("exact", 0) + total_status_counts.get("exact_no_node", 0),
        "exact_alignment_count": total_status_counts.get("exact", 0),
        "ambiguous_count": total_status_counts.get("ambiguous", 0),
        "unmatched_count": total_status_counts.get("unmatched", 0),
        "gold_evidence_count": sum(d.get("gold_evidence_count", 0) for d in successful),
        "status_counts": total_status_counts,
        "truth_contract_version": CONTRACT_VERSION,
        "truth_contract_hash": truth_contract_hash,
        "tag_registry_version": registry.version,
        "tag_registry_hash": registry_hash,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        cmd_dry_run()
    elif args.pilot:
        cmd_pilot()
    elif args.full:
        cmd_full()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
