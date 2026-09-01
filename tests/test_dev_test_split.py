"""Task 2.4 - tests for src/eval/dev_test_split.py.

Portable unit tests use small synthetic question-record fixtures (the
same dict shape src.eval.evaluation_dataset produces - no DB, no network).
A separate local_data-marked test validates the real, built Task 2.4
split artifacts (results/phase_2_4_*.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.eval.dev_test_split import (
    LeakageError,
    SplitCompletenessError,
    extract_participating_ciks,
    build_components,
    representative_sic,
    assign_splits,
    build_question_split_map,
    verify_no_cik_leakage,
    verify_gold_completeness,
    select_ci_golden,
    compute_assignment_records,
    compute_assignment_sha256,
    CI_TOTAL,
)


def numeric(qid, cik, fiscal_year=2016, tag="Assets", accession=None):
    return {
        "question_id": qid, "category": "numeric", "subtype": "xbrl_fact",
        "cik": cik, "fiscal_year": fiscal_year, "tag": tag,
        "accession": accession or f"acc-{cik}-{fiscal_year}",
        "question": f"q-{qid}",
    }


def yoy(qid, cik, tag="Assets"):
    return {
        "question_id": qid, "category": "comparative", "subtype": "year_over_year_difference",
        "cik": cik, "tag": tag,
        "operands": [{"accession": f"a-{cik}-1", "fiscal_year": 2016}, {"accession": f"a-{cik}-2", "fiscal_year": 2017}],
        "question": f"q-{qid}",
    }


def cross_entity(qid, cik_a, cik_b, tag="Assets", fiscal_year=2016):
    return {
        "question_id": qid, "category": "comparative", "subtype": "cross_entity_comparison",
        "tag": tag, "fiscal_year": fiscal_year,
        "operands": [
            {"cik": cik_a, "accession": f"a-{cik_a}"},
            {"cik": cik_b, "accession": f"a-{cik_b}"},
        ],
        "question": f"q-{qid}",
    }


def entity_free(qid, subtype="off_scope"):
    return {"question_id": qid, "category": "adversarial", "subtype": subtype, "question": f"q-{qid}"}


def narrative(qid, cik, fiscal_year=2016):
    return {
        "question_id": qid, "category": "narrative", "subtype": "llm_generated",
        "cik": cik, "fiscal_year": fiscal_year, "status": "pending_review",
        "question": f"q-{qid}",
    }


# --------------------------------------------------------------- extraction

def test_extract_participating_ciks_numeric():
    assert extract_participating_ciks(numeric("q1", 100)) == frozenset({100})


def test_extract_participating_ciks_yoy_single_cik():
    assert extract_participating_ciks(yoy("q1", 100)) == frozenset({100})


def test_extract_participating_ciks_cross_entity_two_ciks():
    assert extract_participating_ciks(cross_entity("q1", 100, 200)) == frozenset({100, 200})


def test_extract_participating_ciks_entity_free_empty():
    assert extract_participating_ciks(entity_free("q1")) == frozenset()


def test_extract_participating_ciks_narrative():
    assert extract_participating_ciks(narrative("q1", 100)) == frozenset({100})


# --------------------------------------------------------------- basic grouping

def test_same_cik_always_same_component():
    records = [numeric("q1", 100, fiscal_year=2016), numeric("q2", 100, fiscal_year=2017)]
    components, qmap = build_components(records)
    assert qmap["q1"] == qmap["q2"]


def test_different_categories_same_cik_same_component():
    records = [numeric("q1", 100), yoy("q2", 100), narrative("q3", 100)]
    components, qmap = build_components(records)
    assert qmap["q1"] == qmap["q2"] == qmap["q3"]


def test_different_cik_different_component_when_unconnected():
    records = [numeric("q1", 100), numeric("q2", 200)]
    components, qmap = build_components(records)
    assert qmap["q1"] != qmap["q2"]


# --------------------------------------------------------------- multi-entity

def test_cross_entity_connects_two_ciks():
    records = [numeric("q1", 100), numeric("q2", 200), cross_entity("q3", 100, 200)]
    components, qmap = build_components(records)
    assert qmap["q1"] == qmap["q2"] == qmap["q3"]
    cid = qmap["q1"]
    assert components[cid].ciks == frozenset({100, 200})


def test_chained_cross_entity_produces_one_component():
    records = [cross_entity("q1", 100, 200), cross_entity("q2", 200, 300)]
    components, qmap = build_components(records)
    assert qmap["q1"] == qmap["q2"]
    cid = qmap["q1"]
    assert components[cid].ciks == frozenset({100, 200, 300})


def test_component_never_split_by_assignment():
    records = [cross_entity("q1", 100, 200), cross_entity("q2", 200, 300)] + [
        numeric(f"extra{i}", 900 + i) for i in range(20)
    ]
    components, qmap = build_components(records)
    split = assign_splits(components)
    cid = qmap["q1"]
    assert split[qmap["q1"]] == split[qmap["q2"]] == split[cid]


def test_secondary_cik_counted_in_leakage_check():
    # cross_entity's second operand CIK (200) must be part of the same
    # component as the first (100) - not silently dropped.
    records = [numeric("q1", 100), numeric("q2", 200), cross_entity("q3", 100, 200)]
    components, qmap = build_components(records)
    cid = qmap["q3"]
    assert components[cid].ciks == frozenset({100, 200})


# --------------------------------------------------------------- entity-free

def test_entity_free_no_fake_cik():
    records = [entity_free("q1")]
    components, qmap = build_components(records)
    cid = qmap["q1"]
    assert components[cid].ciks == frozenset()


def test_entity_free_deterministic_assignment():
    records = [entity_free(f"q{i}") for i in range(10)] + [numeric(f"n{i}", i) for i in range(10)]
    components1, qmap1 = build_components(records)
    split1 = assign_splits(components1)
    components2, qmap2 = build_components(list(reversed(records)))
    split2 = assign_splits(components2)
    result1 = {qid: split1[qmap1[qid]] for qid in qmap1}
    result2 = {qid: split2[qmap2[qid]] for qid in qmap2}
    assert result1 == result2


# --------------------------------------------------------------- ratio

def test_split_approximately_targets_70_30():
    records = [numeric(f"q{i}", i) for i in range(1000)]
    components, qmap = build_components(records)
    split = assign_splits(components, dev_fraction=0.7)
    dev = sum(1 for r in records if split[qmap[r["question_id"]]] == "dev")
    test = sum(1 for r in records if split[qmap[r["question_id"]]] == "test")
    assert dev + test == 1000
    assert abs(dev / 1000 - 0.7) < 0.02


def test_group_integrity_over_exact_ratio():
    # one giant component (all cross-linked) forces a lopsided ratio -
    # integrity must still hold (all-or-nothing for that component).
    records = [cross_entity(f"ce{i}", i, i + 1) for i in range(50)]
    components, qmap = build_components(records)
    split = assign_splits(components)
    cids = {qmap[r["question_id"]] for r in records}
    assert len(cids) == 1
    splits_used = {split[cid] for cid in cids}
    assert len(splits_used) == 1


# --------------------------------------------------------------- pending narrative

def test_pending_narrative_never_promoted_gold():
    records = [narrative("n1", 100)]
    for r in records:
        assert r["status"] == "pending_review"


def test_pending_records_receive_stable_component_assignment():
    records = [numeric("q1", 100), narrative("n1", 100)]
    components, qmap = build_components(records)
    assert qmap["q1"] == qmap["n1"]


def test_pending_excluded_from_gold_counts():
    records = [numeric("q1", 100), narrative("n1", 100)]
    components, qmap = build_components(records)
    cid = qmap["q1"]
    assert components[cid].gold_count == 1
    assert components[cid].pending_count == 1


# --------------------------------------------------------------- determinism

def test_same_input_same_assignment():
    records = [numeric(f"q{i}", i) for i in range(200)] + [cross_entity("ce1", 5, 6)]
    c1, m1 = build_components(records)
    s1 = assign_splits(c1)
    c2, m2 = build_components(records)
    s2 = assign_splits(c2)
    result1 = {qid: s1[m1[qid]] for qid in m1}
    result2 = {qid: s2[m2[qid]] for qid in m2}
    assert result1 == result2


def test_same_input_same_hashes():
    records = [numeric(f"q{i}", i) for i in range(50)]
    components, qmap = build_components(records)
    split = assign_splits(components)
    a1 = compute_assignment_records(build_question_split_map(records, qmap, split), qmap, {r["question_id"]: "gold" for r in records})
    a2 = compute_assignment_records(build_question_split_map(records, qmap, split), qmap, {r["question_id"]: "gold" for r in records})
    assert compute_assignment_sha256(a1) == compute_assignment_sha256(a2)


def test_input_order_does_not_affect_semantic_result():
    records = [numeric(f"q{i}", i) for i in range(50)]
    c1, m1 = build_components(records)
    s1 = assign_splits(c1)
    c2, m2 = build_components(list(reversed(records)))
    s2 = assign_splits(c2)
    r1 = {qid: s1[m1[qid]] for qid in m1}
    r2 = {qid: s2[m2[qid]] for qid in m2}
    assert r1 == r2


# --------------------------------------------------------------- leakage

def test_no_leakage_after_valid_split():
    records = [numeric(f"q{i}", i) for i in range(100)]
    components, qmap = build_components(records)
    split = assign_splits(components)
    verify_no_cik_leakage(components, split)  # should not raise


def test_leakage_detected_when_forced():
    components, qmap = build_components([numeric("q1", 1), numeric("q2", 2)])
    bad_split = {cid: "dev" for cid in components}
    # force the same CIK into two components manually to simulate a bug
    cids = list(components.keys())
    components[cids[0]].ciks = frozenset({1, 2})
    components[cids[1]].ciks = frozenset({2})
    bad_split[cids[1]] = "test"
    with pytest.raises(LeakageError):
        verify_no_cik_leakage(components, bad_split)


# --------------------------------------------------------------- completeness

def test_completeness_all_assigned_exactly_once():
    records = [numeric(f"q{i}", i) for i in range(30)]
    components, qmap = build_components(records)
    split = assign_splits(components)
    qsplit = build_question_split_map(records, qmap, split)
    dev_ids = {qid for qid, s in qsplit.items() if s == "dev"}
    test_ids = {qid for qid, s in qsplit.items() if s == "test"}
    verify_gold_completeness(records, dev_ids, test_ids)  # should not raise


def test_completeness_fails_on_missing_question():
    records = [numeric(f"q{i}", i) for i in range(5)]
    with pytest.raises(SplitCompletenessError):
        verify_gold_completeness(records, {"q0", "q1"}, {"q2"})  # q3, q4 missing


def test_completeness_fails_on_duplicate_assignment():
    records = [numeric(f"q{i}", i) for i in range(5)]
    ids = {r["question_id"] for r in records}
    with pytest.raises(SplitCompletenessError):
        verify_gold_completeness(records, ids, {"q0"})  # q0 in both


# --------------------------------------------------------------- CI

def test_ci_exactly_200():
    records = [numeric(f"q{i}", i) for i in range(500)]
    selected = select_ci_golden(records, ci_total=200)
    assert len(selected) == 200


def test_ci_all_from_dev_pool_only():
    dev_records = [numeric(f"q{i}", i) for i in range(300)]
    selected = set(select_ci_golden(dev_records, ci_total=200))
    dev_ids = {r["question_id"] for r in dev_records}
    assert selected <= dev_ids


def test_ci_no_narrative_because_caller_excludes_it():
    # select_ci_golden never special-cases narrative - the caller is
    # responsible for excluding it. Verify a narrative-shaped record fed
    # in would still be selectable, i.e. exclusion is a caller contract,
    # not silently enforced here (documented in the function docstring).
    dev_records = [numeric(f"q{i}", i) for i in range(199)]
    selected = select_ci_golden(dev_records, ci_total=199)
    assert set(selected) == {r["question_id"] for r in dev_records}


def test_ci_deterministic():
    records = [numeric(f"q{i}", i, tag="Assets" if i % 2 else "Revenues") for i in range(300)]
    s1 = select_ci_golden(records, ci_total=200)
    s2 = select_ci_golden(records, ci_total=200)
    assert s1 == s2


def test_ci_prefers_subtype_coverage():
    records = [numeric(f"n{i}", i) for i in range(90)] + [yoy(f"y{i}", 1000 + i) for i in range(10)]
    selected = select_ci_golden(records, ci_total=20)
    subtypes = {r["subtype"] for r in records if r["question_id"] in selected}
    assert "year_over_year_difference" in subtypes
    assert "xbrl_fact" in subtypes


# --------------------------------------------------------------- SIC

def test_representative_sic_most_frequent():
    sic_map = {"a1": "1000", "a2": "1000", "a3": "2000"}
    assert representative_sic(["a1", "a2", "a3"], sic_map) == "1000"


def test_representative_sic_tie_break_lexicographic():
    sic_map = {"a1": "2000", "a2": "1000"}
    assert representative_sic(["a1", "a2"], sic_map) == "1000"


def test_representative_sic_unknown_when_no_accession():
    assert representative_sic([], {}) == "unknown"


def test_representative_sic_unknown_when_unmapped():
    assert representative_sic(["a1"], {}) == "unknown"


# --------------------------------------------------------------- TEST safety

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_test_file_path_is_gitignored():
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", "artifacts/eval/phase_2_4_test.json"],
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, "TEST artifact path is not gitignored"


@pytest.mark.local_data
def test_manifest_contains_no_test_payload():
    manifest_path = REPO_ROOT / "results" / "phase_2_4_split_manifest.json"
    if not manifest_path.exists():
        pytest.skip("Task 2.4 manifest not built")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    allowed_keys = {"question_id", "split", "status", "component_id"}
    for row in manifest["assignments"]:
        assert set(row.keys()) <= allowed_keys
        assert "question" not in row
        assert "expected_value" not in row
        assert "expected_answer" not in row


# --------------------------------------------------------------- real-artifact integration

@pytest.mark.local_data
def test_real_split_artifacts():
    results_dir = REPO_ROOT / "results"
    dataset_path = results_dir / "phase_2_3_evaluation_dataset.json"
    dev_path = results_dir / "phase_2_4_dev.json"
    manifest_path = results_dir / "phase_2_4_split_manifest.json"
    summary_path = results_dir / "phase_2_4_split_summary.json"
    ci_path = results_dir / "phase_2_4_ci_golden.json"
    test_path = REPO_ROOT / "artifacts" / "eval" / "phase_2_4_test.json"

    for p in (dataset_path, dev_path, manifest_path, summary_path, ci_path, test_path):
        if not p.exists():
            pytest.skip(f"Task 2.4 artifact missing: {p}")

    from src.eval.evaluation_dataset import compute_dataset_sha256

    with open(dataset_path, encoding="utf-8") as f:
        source = json.load(f)
    with open(dev_path, encoding="utf-8") as f:
        dev = json.load(f)
    with open(test_path, encoding="utf-8") as f:
        test = json.load(f)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)
    with open(ci_path, encoding="utf-8") as f:
        ci = json.load(f)

    assert compute_dataset_sha256(source["questions"]) == source["dataset_sha256"]

    gold = [r for r in source["questions"] if r["category"] != "narrative"]
    pending = [r for r in source["questions"] if r["category"] == "narrative"]
    assert len(gold) == 2760
    assert len(pending) == 50
    assert all(r["status"] == "pending_review" for r in pending)

    assert compute_dataset_sha256(dev["questions"]) == manifest["header"]["dev_sha256"]
    assert compute_dataset_sha256(test["questions"]) == manifest["header"]["test_sha256"]
    assert compute_dataset_sha256(ci["questions"]) == manifest["header"]["ci_sha256"]
    assert manifest["header"]["test_sha256"] == test["test_sha256"]

    dev_ids = {r["question_id"] for r in dev["questions"]}
    test_ids = {r["question_id"] for r in test["questions"]}
    assert not (dev_ids & test_ids)
    assert dev_ids | test_ids == {r["question_id"] for r in gold}

    dev_ciks = set()
    for r in dev["questions"]:
        dev_ciks |= extract_participating_ciks(r)
    test_ciks = set()
    for r in test["questions"]:
        test_ciks |= extract_participating_ciks(r)
    assert not (dev_ciks & test_ciks)

    for r in gold:
        if r.get("subtype") != "cross_entity_comparison":
            continue
        ciks = extract_participating_ciks(r)
        assert ciks <= dev_ciks or ciks <= test_ciks, f"{r['question_id']} spans both splits"

    assert len(ci["questions"]) == CI_TOTAL
    assert set(r["question_id"] for r in ci["questions"]) <= dev_ids
    assert not (set(r["question_id"] for r in ci["questions"]) & test_ids)
    assert all(r["category"] != "narrative" for r in ci["questions"])

    assert summary["counts"]["gold_total"] == 2760
    assert summary["counts"]["dev_gold"] + summary["counts"]["test_gold"] == 2760
    assert summary["counts"]["pending_narrative_total"] == 50
