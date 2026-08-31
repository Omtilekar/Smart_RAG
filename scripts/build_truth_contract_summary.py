"""Task 2.1 - real-data diagnostic summary for the XBRL truth contract.

Reads data/xbrl.duckdb read-only, applies src.eval.truth_contract's single
authoritative eligibility contract for the 10 tags whose qtrs semantics are
currently resolved, and writes a small tracked diagnostic summary. Never
writes to the frozen database. Never stores the full eligible population -
only counts/diagnostics.

Rejection-reason counts are independent diagnostics, not a mutually
exclusive partition - a single row can fail more than one rule
simultaneously (e.g. wrong unit AND wrong period), so counts may overlap
and must not be summed to reconstruct the total rejected count.
"""

from __future__ import annotations

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

from src.eval.truth_contract import (  # noqa: E402
    QTRS_BY_TAG,
    UNRESOLVED_CANDIDATE_TAGS,
    SUPPORTED_FORM,
    SUPPORTED_FISCAL_YEAR_MIN,
    SUPPORTED_FISCAL_YEAR_MAX,
    TAXONOMY_PREFIX,
    MONETARY_UOM,
    eligible_facts,
    build_contract_config,
    compute_contract_config_hash,
)

SCHEMA_VERSION = "1.0"
XBRL_DB_PATH = Path("data") / "xbrl.duckdb"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_2_1_truth_contract_summary.json"


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return None


def main() -> int:
    db_path = REPO_ROOT / XBRL_DB_PATH
    if not db_path.is_file():
        raise SystemExit(f"FATAL: XBRL database not found at {db_path}")

    con = duckdb.connect(str(db_path), read_only=True)
    tags = sorted(QTRS_BY_TAG.keys())
    tags_sql = ",".join(f"'{t}'" for t in tags)
    qtrs_case_sql = " ".join(f"WHEN '{t}' THEN {QTRS_BY_TAG[t]}" for t in tags)

    source_fact_count = con.execute(f"SELECT count(*) FROM facts WHERE tag IN ({tags_sql})").fetchone()[0]

    t0 = time.perf_counter()
    facts = eligible_facts(con, tags)
    runtime_s = time.perf_counter() - t0
    eligible_count = len(facts)

    # Independent diagnostic rejection counts - NOT a partition, may overlap.
    def count_where(extra_where: str) -> int:
        return con.execute(f"SELECT count(*) FROM facts WHERE tag IN ({tags_sql}) AND {extra_where}").fetchone()[0]

    rejected_by = {
        "coreg": count_where("coreg IS NOT NULL AND coreg != ''"),
        "segments": count_where("segments IS NOT NULL AND segments != ''"),
        "taxonomy": count_where(f"version NOT LIKE '{TAXONOMY_PREFIX}%'"),
        "unit": count_where(f"uom != '{MONETARY_UOM}'"),
        "qtrs": count_where(f"qtrs != CASE tag {qtrs_case_sql} END"),
        "form": count_where(f"form != '{SUPPORTED_FORM}'"),
        "fiscal_year_window": count_where(
            f"(fiscal_year < {SUPPORTED_FISCAL_YEAR_MIN} OR fiscal_year > {SUPPORTED_FISCAL_YEAR_MAX})"
        ),
        "null_value": count_where("value IS NULL"),
    }
    # Period-alignment rejection requires the join - counted separately.
    rejected_by["date_period_alignment"] = con.execute(f"""
        SELECT count(*) FROM facts f
        WHERE f.tag IN ({tags_sql})
        AND NOT EXISTS (SELECT 1 FROM submissions s WHERE s.adsh = f.adsh AND s.period = f.ddate)
    """).fetchone()[0]

    eligible_by_tag: dict[str, int] = {}
    eligible_by_year: dict[str, int] = {}
    eligible_by_qtrs: dict[str, int] = {}
    unique_adsh = set()
    unique_cik = set()
    for f in facts:
        eligible_by_tag[f.tag] = eligible_by_tag.get(f.tag, 0) + 1
        eligible_by_year[str(f.fiscal_year)] = eligible_by_year.get(str(f.fiscal_year), 0) + 1
        eligible_by_qtrs[str(f.qtrs)] = eligible_by_qtrs.get(str(f.qtrs), 0) + 1
        unique_adsh.add(f.adsh)
        unique_cik.add(f.cik)

    # Cross-filing value-revision diagnostic, Check 1's exact methodology,
    # applied to THIS contract's 10-tag registry - NOT forced to match the
    # frozen 7.87%/10.39% figures, which use a different (15-tag or all-tag)
    # population. Grain: (cik, tag, ddate, qtrs, uom). Cross-filing repeat:
    # >1 distinct adsh (same-accession duplicates collapsed first - already
    # true of `facts`, since eligible_facts() itself raises on genuine
    # same-accession conflicts and this diagnostic reuses its output).
    revision_groups: dict[tuple, set] = {}
    for f in facts:
        key = (f.cik, f.tag, f.ddate, f.qtrs, f.uom)
        revision_groups.setdefault(key, set()).add((f.adsh, f.value))

    cross_filing_repeated_groups = 0
    cross_filing_revision_groups = 0
    for key, adsh_value_pairs in revision_groups.items():
        distinct_adsh = {a for a, _ in adsh_value_pairs}
        if len(distinct_adsh) > 1:
            cross_filing_repeated_groups += 1
            distinct_values = {v for _, v in adsh_value_pairs}
            if len(distinct_values) > 1:
                cross_filing_revision_groups += 1

    cross_filing_value_revision_rate = (
        cross_filing_revision_groups / cross_filing_repeated_groups if cross_filing_repeated_groups else None
    )

    config = build_contract_config(tags)
    config_hash = compute_contract_config_hash(config)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "truth_contract_config_hash": config_hash,
        "resolved_tags": tags,
        "unresolved_candidate_tags": list(UNRESOLVED_CANDIDATE_TAGS),
        "source_fact_count": source_fact_count,
        "eligible_fact_count": eligible_count,
        "rejected_count": source_fact_count - eligible_count,
        "rejected_by_reason_independent_diagnostics": rejected_by,
        "eligible_counts_by_tag": eligible_by_tag,
        "eligible_counts_by_year": eligible_by_year,
        "eligible_counts_by_qtrs": eligible_by_qtrs,
        "unique_accessions": len(unique_adsh),
        "unique_ciks": len(unique_cik),
        "same_accession_duplicates_encountered": 0,
        "cross_filing_comparable_groups": cross_filing_repeated_groups,
        "cross_filing_value_revision_groups": cross_filing_revision_groups,
        "cross_filing_value_revision_rate": cross_filing_value_revision_rate,
        "cross_filing_value_revision_note": (
            "Computed on THIS contract's 10-tag registry (2016-2020, 10-K only) - "
            "NOT the same population as DATA_READINESS_REPORT.md's frozen 7.87%/8.00%/10.39% "
            "figures (all-tags / standard-tags / 15-tag registry, no fiscal-year-window "
            "restriction). Never call this a 'restatement rate' - see module docstring."
        ),
        "runtime_seconds": round(runtime_s, 3),
    }
    summary_path = REPO_ROOT / SUMMARY_RELATIVE_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"source facts (10-tag registry, any filter): {source_fact_count}")
    print(f"eligible facts: {eligible_count}")
    print(f"rejected: {source_fact_count - eligible_count}")
    print(f"unique accessions: {len(unique_adsh)}")
    print(f"unique CIKs: {len(unique_cik)}")
    print(f"cross-filing value-revision rate (this registry): {cross_filing_value_revision_rate}")
    print(f"truth_contract_config_hash: {config_hash}")
    print(f"runtime: {runtime_s:.3f}s")
    print(f"Summary written to: {summary_path}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
