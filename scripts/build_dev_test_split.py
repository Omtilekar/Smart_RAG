"""Task 2.4 - build the company-disjoint DEV/TEST split of the frozen
Task 2.3 evaluation dataset.

Reads `results/phase_2_3_evaluation_dataset.json` read-only, verifies its
hash against the value recorded when Task 2.3 was built (STOPs rather
than splitting a dataset whose identity changed), and never writes back
to any Task 2.3 artifact.

Deterministic and fully local - no network, no LLM, no GPU, no SEC
downloads. The only extra read is `data/raw/xbrl/*.zip`'s `sub.txt`
member (already-frozen source data) for accession-level SIC codes, which
are not persisted in `data/xbrl.duckdb`.

Outputs:
    results/phase_2_4_dev.json                    (tracked - DEV gold, inspectable)
    results/phase_2_4_ci_golden.json               (tracked - 200-question CI subset of DEV)
    results/phase_2_4_split_manifest.json          (tracked - question_id/split/status/component_id only)
    results/phase_2_4_split_summary.json           (tracked - distributions, hashes, no question content)
    results/phase_2_4_pending_review_assignments.json  (tracked - narrative split inheritance, no question text)
    configs/phase_2_4_dev_test_split.json          (tracked - semantic build config)
    artifacts/eval/phase_2_4_test.json             (gitignored - full TEST content)
    artifacts/eval/eval.duckdb                     (gitignored - TEST access log)
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.eval import dev_test_split as dts  # noqa: E402
from src.eval import evaluation_dataset as ed  # noqa: E402
from src.eval import test_access  # noqa: E402

SCHEMA_VERSION = "1.0"
SOURCE_DATASET_PATH = Path("results") / "phase_2_3_evaluation_dataset.json"
EXPECTED_SOURCE_DATASET_SHA256 = "bf85e1a12ac70645d906a75fa79563c06dbb7620d6e870d4eb29505a326f922a"

DEV_PATH = Path("results") / "phase_2_4_dev.json"
CI_GOLDEN_PATH = Path("results") / "phase_2_4_ci_golden.json"
MANIFEST_PATH = Path("results") / "phase_2_4_split_manifest.json"
SUMMARY_PATH = Path("results") / "phase_2_4_split_summary.json"
PENDING_ASSIGNMENTS_PATH = Path("results") / "phase_2_4_pending_review_assignments.json"
CONFIG_PATH = Path("configs") / "phase_2_4_dev_test_split.json"
TEST_PATH = Path("artifacts") / "eval" / "phase_2_4_test.json"

RAW_XBRL_DIR = Path("data") / "raw" / "xbrl"


def git_sha() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:
        return None


def build_sic_map() -> dict[str, str]:
    """adsh -> sic, read directly from the frozen SEC quarterly financial
    statement datasets' sub.txt member. Read-only: never extracts to
    disk, never modifies data/raw/xbrl/."""
    sic_map: dict[str, str] = {}
    for zpath in sorted(RAW_XBRL_DIR.glob("*.zip")):
        with zipfile.ZipFile(zpath) as z:
            if "sub.txt" not in z.namelist():
                continue
            with z.open("sub.txt") as f:
                header = f.readline().decode("utf-8", errors="replace").rstrip("\n").split("\t")
                adsh_idx = header.index("adsh")
                sic_idx = header.index("sic")
                for raw_line in f:
                    fields = raw_line.decode("utf-8", errors="replace").rstrip("\n").split("\t")
                    if len(fields) <= max(adsh_idx, sic_idx):
                        continue
                    adsh = fields[adsh_idx]
                    sic = fields[sic_idx].strip()
                    if adsh and adsh not in sic_map:
                        sic_map[adsh] = sic if sic else "unknown"
    return sic_map


def independent_leakage_check(dev_records: list[dict], test_records: list[dict]) -> None:
    """Section 38: a separate one-off check that does NOT call
    dev_test_split.verify_no_cik_leakage - re-derives everything from the
    DEV/TEST record lists themselves."""
    dev_ciks: set[int] = set()
    for r in dev_records:
        dev_ciks |= dts.extract_participating_ciks(r)
    test_ciks: set[int] = set()
    for r in test_records:
        test_ciks |= dts.extract_participating_ciks(r)
    overlap = dev_ciks & test_ciks
    if overlap:
        raise dts.LeakageError(f"independent check: CIK(s) {sorted(overlap)} appear in both DEV and TEST")


def counts_by(records: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        key = str(r.get(field))
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def component_summary(components: dict[str, dts.Component], component_split: dict[str, str], split: str) -> dict:
    members = [c for c in components.values() if component_split[c.component_id] == split]
    sizes = [len(c.ciks) for c in members if c.ciks]
    return {
        "component_count": len(members),
        "largest_component": max(sizes) if sizes else 0,
        "median_component_size": sorted(sizes)[len(sizes) // 2] if sizes else 0,
        "entity_free_count": sum(1 for c in members if not c.ciks),
    }


def sic_distribution(components: dict[str, dts.Component], component_split: dict[str, str], component_sic: dict[str, str], split: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in components.values():
        if component_split[c.component_id] != split:
            continue
        sic = component_sic[c.component_id]
        out[sic] = out.get(sic, 0) + c.gold_count
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def main() -> None:
    started = datetime.now(timezone.utc)

    with open(SOURCE_DATASET_PATH, encoding="utf-8") as f:
        source = json.load(f)
    all_records = source["questions"]
    recomputed_hash = ed.compute_dataset_sha256(all_records)
    stored_hash = source["dataset_sha256"]
    if recomputed_hash != stored_hash or stored_hash != EXPECTED_SOURCE_DATASET_SHA256:
        print(
            f"STOP: Task 2.3 dataset hash mismatch - stored={stored_hash} "
            f"recomputed={recomputed_hash} expected={EXPECTED_SOURCE_DATASET_SHA256}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    gold_records = [r for r in all_records if r["category"] != dts.NARRATIVE_CATEGORY]
    narrative_records = [r for r in all_records if r["category"] == dts.NARRATIVE_CATEGORY]
    assert all(r.get("status") == "pending_review" for r in narrative_records)

    sic_map = build_sic_map()

    components, question_component_map = dts.build_components(all_records)
    component_split = dts.assign_splits(components, dev_fraction=dts.DEV_FRACTION)

    component_sic = {cid: dts.representative_sic(c.accessions, sic_map) for cid, c in components.items()}

    question_split_map = dts.build_question_split_map(gold_records, question_component_map, component_split)
    narrative_split_map = dts.build_question_split_map(narrative_records, question_component_map, component_split)

    dev_ids = {qid for qid, split in question_split_map.items() if split == "dev"}
    test_ids = {qid for qid, split in question_split_map.items() if split == "test"}

    dts.verify_no_cik_leakage(components, component_split)
    dts.verify_cross_entity_integrity(gold_records, question_split_map)
    dts.verify_gold_completeness(gold_records, dev_ids, test_ids)

    dev_records = [r for r in gold_records if r["question_id"] in dev_ids]
    test_records = [r for r in gold_records if r["question_id"] in test_ids]
    independent_leakage_check(dev_records, test_records)

    # Section 38 (part 2): every gold question appears exactly once.
    seen = [r["question_id"] for r in dev_records] + [r["question_id"] for r in test_records]
    assert len(seen) == len(set(seen)) == len(gold_records)

    ci_ids = set(dts.select_ci_golden(dev_records, ci_total=dts.CI_TOTAL))
    assert len(ci_ids) == dts.CI_TOTAL
    assert ci_ids <= dev_ids
    assert not (ci_ids & test_ids)
    ci_records = [r for r in dev_records if r["question_id"] in ci_ids]

    dev_hash = ed.compute_dataset_sha256(dev_records)
    test_hash = ed.compute_dataset_sha256(test_records)
    ci_hash = ed.compute_dataset_sha256(ci_records)

    status_by_id = {r["question_id"]: r.get("status", "gold") for r in all_records}
    all_question_split_map = {**question_split_map, **narrative_split_map}
    all_question_component_map = {
        r["question_id"]: question_component_map[r["question_id"]] for r in all_records
    }
    assignment_records = dts.compute_assignment_records(all_question_split_map, all_question_component_map, status_by_id)
    assignment_hash = dts.compute_assignment_sha256(assignment_records)

    split_config = {
        "split_version": dts.SPLIT_VERSION,
        "dev_fraction": dts.DEV_FRACTION,
        "test_fraction": round(1 - dts.DEV_FRACTION, 10),
        "grouping": {
            "entity_key": "cik",
            "multi_entity_component_policy": "connected component over CIKs co-occurring in a cross_entity_comparison question; never split",
        },
        "stratification": {
            "sic": "derived from data/raw/xbrl/*.zip sub.txt, most-frequent-among-component-accessions with (count desc, sic asc) tie-break; unknown if no accession resolves",
            "fiscal_year": "measured, not forced - components assigned by deterministic greedy balance on gold_count only",
            "category": "measured, not forced",
            "subtype": "measured, not forced",
        },
        "pending_review_policy": "narrative pending_review records inherit their company's component split; never promoted to gold; excluded from gold DEV/TEST counts and ratio target",
        "entity_free_policy": "prompt_injection/off_scope/financial_advice carry no structured cik field - each entity-free question is its own singleton pseudo-component with zero leakage risk, assigned after all CIK-based components via the same deterministic greedy balance",
        "tie_break_algorithm": "SHA-256 (src.eval.evaluation_dataset.selection_key) over canonical component/question identity; never Python hash()",
        "source_dataset_version": source["eval_set_version"],
        "source_dataset_sha256": stored_hash,
    }
    split_config_hash = __import__("hashlib").sha256(
        json.dumps(split_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({**split_config, "split_config_hash": split_config_hash}, indent=2) + "\n")

    DEV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEV_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "split_version": dts.SPLIT_VERSION,
                "eval_set_version": source["eval_set_version"],
                "source_dataset_sha256": stored_hash,
                "created_at_utc": started.isoformat(),
                "git_sha": git_sha(),
                "dev_sha256": dev_hash,
                "question_count": len(dev_records),
                "questions": dev_records,
            },
            f,
            indent=None,
        )

    with open(CI_GOLDEN_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "ci_set_version": dts.CI_SET_VERSION,
                "source_dev_hash": dev_hash,
                "ci_sha256": ci_hash,
                "reportable_benchmark": False,
                "note": "CI regression set - may be overfit through repeated CI exposure; never a headline result",
                "question_count": len(ci_records),
                "questions": ci_records,
            },
            f,
            indent=None,
        )

    TEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_version": SCHEMA_VERSION,
                "split_version": dts.SPLIT_VERSION,
                "eval_set_version": source["eval_set_version"],
                "source_dataset_sha256": stored_hash,
                "created_at_utc": started.isoformat(),
                "git_sha": git_sha(),
                "test_sha256": test_hash,
                "question_count": len(test_records),
                "questions": test_records,
            },
            f,
            indent=None,
        )

    pending_assignments = [
        {
            "question_id": r["question_id"],
            "component_id": all_question_component_map[r["question_id"]],
            "assigned_split": narrative_split_map[r["question_id"]],
            "status": "pending_review",
        }
        for r in narrative_records
    ]
    with open(PENDING_ASSIGNMENTS_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({"schema_version": SCHEMA_VERSION, "split_version": dts.SPLIT_VERSION, "assignments": pending_assignments}, indent=2) + "\n")

    manifest_header = {
        "schema_version": SCHEMA_VERSION,
        "split_version": dts.SPLIT_VERSION,
        "eval_set_version": source["eval_set_version"],
        "source_dataset_sha256": stored_hash,
        "created_at_utc": started.isoformat(),
        "git_sha": git_sha(),
        "split_config_hash": split_config_hash,
        "split_assignment_sha256": assignment_hash,
        "dev_sha256": dev_hash,
        "test_sha256": test_hash,
        "ci_sha256": ci_hash,
        "dev_count": len(dev_records),
        "test_count": len(test_records),
        "ci_count": len(ci_records),
        "pending_narrative_count": len(narrative_records),
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps({"header": manifest_header, "assignments": assignment_records}, indent=2) + "\n")

    dev_component_stats = component_summary(components, component_split, "dev")
    test_component_stats = component_summary(components, component_split, "test")
    cross_entity_records = [r for r in gold_records if r.get("subtype") == "cross_entity_comparison"]
    unique_cik_edges = {tuple(sorted(dts.extract_participating_ciks(r))) for r in cross_entity_records}

    summary = {
        "schema_version": SCHEMA_VERSION,
        "split_version": dts.SPLIT_VERSION,
        "created_at_utc": started.isoformat(),
        "git_sha": git_sha(),
        "source_dataset_sha256": stored_hash,
        "split_config_hash": split_config_hash,
        "split_assignment_sha256": assignment_hash,
        "dev_sha256": dev_hash,
        "test_sha256": test_hash,
        "ci_sha256": ci_hash,
        "counts": {
            "gold_total": len(gold_records),
            "dev_gold": len(dev_records),
            "test_gold": len(test_records),
            "dev_fraction_actual": round(len(dev_records) / len(gold_records), 4),
            "test_fraction_actual": round(len(test_records) / len(gold_records), 4),
            "pending_narrative_total": len(narrative_records),
            "pending_narrative_dev": sum(1 for s in narrative_split_map.values() if s == "dev"),
            "pending_narrative_test": sum(1 for s in narrative_split_map.values() if s == "test"),
            "ci_golden": len(ci_records),
        },
        "dev": {
            "category": counts_by(dev_records, "category"),
            "subtype": counts_by(dev_records, "subtype"),
            "fiscal_year": counts_by(dev_records, "fiscal_year"),
            "sic": sic_distribution(components, component_split, component_sic, "dev"),
            "unique_ciks": len({c for r in dev_records for c in dts.extract_participating_ciks(r)}),
            "unique_accessions": len({r["accession"] for r in dev_records if r.get("accession")}
                                      | {op["accession"] for r in dev_records for op in r.get("operands", []) if op.get("accession")}),
            **dev_component_stats,
        },
        "test": {
            "category": counts_by(test_records, "category"),
            "subtype": counts_by(test_records, "subtype"),
            "fiscal_year": counts_by(test_records, "fiscal_year"),
            "sic": sic_distribution(components, component_split, component_sic, "test"),
            "unique_ciks": len({c for r in test_records for c in dts.extract_participating_ciks(r)}),
            "unique_accessions": len({r["accession"] for r in test_records if r.get("accession")}
                                      | {op["accession"] for r in test_records for op in r.get("operands", []) if op.get("accession")}),
            **test_component_stats,
        },
        "cross_entity": {
            "question_count": len(cross_entity_records),
            "unique_cik_edges": len(unique_cik_edges),
            "connected_components_total": sum(1 for c in components.values() if c.ciks),
            "largest_connected_component": max((len(c.ciks) for c in components.values() if c.ciks), default=0),
        },
        "ci": {
            "category": counts_by(ci_records, "category"),
            "subtype": counts_by(ci_records, "subtype"),
        },
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(summary, indent=2) + "\n")

    test_access.record_build_validation(
        eval_set_version=source["eval_set_version"],
        source_dataset_sha256=stored_hash,
        split_version=dts.SPLIT_VERSION,
        test_sha256=test_hash,
    )

    print("PHASE 2.4 build complete")
    print(f"gold_total={len(gold_records)} dev={len(dev_records)} test={len(test_records)} ci={len(ci_records)}")
    print(f"dataset_sha256(source)={stored_hash}")
    print(f"split_config_hash={split_config_hash}")
    print(f"split_assignment_sha256={assignment_hash}")
    print(f"dev_sha256={dev_hash}")
    print(f"test_sha256={test_hash}")
    print(f"ci_sha256={ci_hash}")


if __name__ == "__main__":
    main()
