"""Task 2.2 - real-data audit of the frozen Phase 2 evaluation tag
registry (configs/eval_tags.yaml).

Reads data/xbrl.duckdb read-only, applies src.eval.truth_contract's
eligibility contract driven by the registry, and writes a small tracked
diagnostic summary plus a before/after comparison against Task 2.1's
10-tag baseline (185,506 eligible facts / 28,859 accessions / 7,809
CIKs). Never writes to the frozen database. Never stores the full
eligible population - only counts/diagnostics.
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

from src.eval.tag_registry import get_registry, compute_registry_hash  # noqa: E402
from src.eval.truth_contract import (  # noqa: E402
    eligible_facts,
    build_contract_config,
    compute_contract_config_hash,
    SUPPORTED_FORM,
    SUPPORTED_FISCAL_YEAR_MIN,
    SUPPORTED_FISCAL_YEAR_MAX,
)

SCHEMA_VERSION = "1.0"
XBRL_DB_PATH = Path("data") / "xbrl.duckdb"
SUMMARY_RELATIVE_PATH = Path("results") / "phase_2_2_tag_registry_summary.json"

# Task 2.1's frozen 10-tag baseline (results/phase_2_1_truth_contract_summary.json).
TASK_2_1_BASELINE = {
    "tags": 10,
    "eligible_facts": 185506,
    "unique_accessions": 28859,
    "unique_ciks": 7809,
}


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

    registry = get_registry()
    registry_hash = compute_registry_hash(registry)
    all_tags = list(registry.tags.keys())
    supported = registry.supported_tags()
    excluded = registry.excluded_tags()

    con = duckdb.connect(str(db_path), read_only=True)

    per_tag: dict[str, dict] = {}
    for tag in all_tags:
        spec = registry.get(tag)
        raw_rows = con.execute("SELECT count(*) FROM facts WHERE tag = ?", [tag]).fetchone()[0]
        rows_10k = con.execute(
            "SELECT count(*) FROM facts WHERE tag = ? AND form = ?", [tag, SUPPORTED_FORM]
        ).fetchone()[0]
        rows_window = con.execute(
            "SELECT count(*) FROM facts WHERE tag = ? AND form = ? AND fiscal_year BETWEEN ? AND ?",
            [tag, SUPPORTED_FORM, SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX],
        ).fetchone()[0]
        qtrs_dist = dict(con.execute(
            "SELECT qtrs, count(*) FROM facts WHERE tag = ? AND form = ? AND fiscal_year BETWEEN ? AND ? "
            "GROUP BY 1 ORDER BY 1",
            [tag, SUPPORTED_FORM, SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX],
        ).fetchall())
        unit_dist = dict(con.execute(
            "SELECT uom, count(*) FROM facts WHERE tag = ? AND form = ? AND fiscal_year BETWEEN ? AND ? "
            "GROUP BY 1 ORDER BY 2 DESC",
            [tag, SUPPORTED_FORM, SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX],
        ).fetchall())
        own_period_matched = con.execute(
            "SELECT count(*) FROM facts f JOIN submissions s ON f.adsh = s.adsh "
            "WHERE f.tag = ? AND f.form = ? AND f.ddate = s.period",
            [tag, SUPPORTED_FORM],
        ).fetchone()[0]
        own_period_total = con.execute(
            "SELECT count(*) FROM facts f WHERE f.tag = ? AND f.form = ?", [tag, SUPPORTED_FORM]
        ).fetchone()[0]

        eligible_rows = 0
        unique_ciks = 0
        unique_accessions = 0
        if spec.enabled:
            tag_facts = eligible_facts(con, [tag])
            eligible_rows = len(tag_facts)
            unique_ciks = len({f.cik for f in tag_facts})
            unique_accessions = len({f.adsh for f in tag_facts})

        per_tag[tag] = {
            "enabled": spec.enabled,
            "period_type": spec.period_type,
            "qtrs": spec.qtrs,
            "unit": spec.unit,
            "raw_rows": raw_rows,
            "10k_rows": rows_10k,
            "2016_2020_rows": rows_window,
            "qtrs_distribution": {str(k): v for k, v in qtrs_dist.items()},
            "unit_distribution": unit_dist,
            "eligible_rows": eligible_rows,
            "unique_ciks": unique_ciks,
            "unique_accessions": unique_accessions,
            "own_period_alignment_rate": round(own_period_matched / own_period_total, 4) if own_period_total else None,
        }

    t0 = time.perf_counter()
    all_eligible = eligible_facts(con, supported)
    runtime_s = time.perf_counter() - t0
    total_unique_ciks = len({f.cik for f in all_eligible})
    total_unique_accessions = len({f.adsh for f in all_eligible})

    config = build_contract_config(supported)
    truth_contract_hash = compute_contract_config_hash(config)

    after = {
        "tags": len(supported),
        "eligible_facts": len(all_eligible),
        "unique_accessions": total_unique_accessions,
        "unique_ciks": total_unique_ciks,
    }
    delta = {k: after[k] - TASK_2_1_BASELINE[k] for k in after}

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "registry_version": registry.version,
        "registry_hash": registry_hash,
        "truth_contract_hash": truth_contract_hash,
        "candidate_tag_count": len(all_tags),
        "supported_tag_count": len(supported),
        "excluded_tag_count": len(excluded),
        "supported_tags": supported,
        "excluded_tags": excluded,
        "per_tag": per_tag,
        "total_eligible_facts": len(all_eligible),
        "total_unique_ciks": total_unique_ciks,
        "total_unique_accessions": total_unique_accessions,
        "before_after": {
            "before": TASK_2_1_BASELINE,
            "after": after,
            "delta": delta,
            "explanation": (
                "Delta is driven entirely by the 5 newly-resolved tags "
                "(RevenueFromContractWithCustomerExcludingAssessedTax, OperatingExpenses, "
                "EarningsPerShareBasic, EarningsPerShareDiluted, IncomeTaxExpenseBenefit) "
                "becoming eligible - Task 2.1's original 10-tag rules (form/window/coreg/"
                "segments/taxonomy/period-alignment/dedup) were not weakened to produce this "
                "increase; see project_plan/PHASE2_TAG_REGISTRY.md for full evidence."
            ),
        },
        "runtime_seconds": round(runtime_s, 3),
    }
    summary_path = REPO_ROOT / SUMMARY_RELATIVE_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"candidate tags: {len(all_tags)}  supported: {len(supported)}  excluded: {len(excluded)}")
    print(f"total eligible facts: {len(all_eligible)}")
    print(f"unique CIKs: {total_unique_ciks}  unique accessions: {total_unique_accessions}")
    print(f"before: {TASK_2_1_BASELINE}")
    print(f"after:  {after}")
    print(f"delta:  {delta}")
    print(f"registry_hash: {registry_hash}")
    print(f"truth_contract_hash: {truth_contract_hash}")
    print(f"runtime: {runtime_s:.3f}s")
    print(f"Summary written to: {summary_path}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
