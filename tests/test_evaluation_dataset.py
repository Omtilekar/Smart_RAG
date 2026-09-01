"""Task 2.3 - tests for src/eval/evaluation_dataset.py.

Portable unit tests use small synthetic EligibleFact-shaped fixtures (duck
typed - only .adsh/.cik/.company/.tag/.fiscal_year/.ddate/.qtrs/.uom/.value
are required) and a fixed Provenance - no DB, no network. A separate
local_data(+model+gpu for narrative)-marked test validates the real
tracked dataset artifact.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.eval.evaluation_dataset import (
    Provenance,
    LeakageError,
    DuplicateQuestionError,
    selection_key,
    render_numeric_question,
    render_yoy_question,
    render_cross_entity_question,
    build_numeric_record,
    build_yoy_record,
    build_cross_entity_record,
    build_unanswerable_year_record,
    build_unanswerable_tag_record,
    build_adversarial_record,
    build_narrative_record,
    assign_question_ids,
    canonical_records_json,
    compute_dataset_sha256,
    check_no_duplicate_questions,
    check_no_leakage,
    CATEGORY_ORDER,
    SUPPORTED_FISCAL_YEAR_MIN,
    SUPPORTED_FISCAL_YEAR_MAX,
    ADVERSARIAL_TEMPLATES,
    ADVERSARIAL_EXPECTED_BEHAVIOR,
    UNSUPPORTED_TAG_CANDIDATES,
)

PROV = Provenance(
    registry_version=1, registry_hash="r" * 64,
    truth_contract_version="2.0", truth_contract_hash="t" * 64,
)


@dataclass(frozen=True)
class FakeFact:
    adsh: str
    cik: int
    company: str
    tag: str
    fiscal_year: int
    ddate: str
    qtrs: int
    uom: str
    value: float


def _fact(adsh="0001-20-000001", cik=1000, company="ACME CORP", tag="Assets", fiscal_year=2018, ddate="20181231", qtrs=0, uom="USD", value=1000.0):
    return FakeFact(adsh, cik, company, tag, fiscal_year, ddate, qtrs, uom, value)


# ------------------------------------------------------------------ selection key

def test_selection_key_deterministic():
    assert selection_key("a", "b") == selection_key("a", "b")
    assert len(selection_key("a", "b")) == 64


def test_selection_key_sensitive_to_parts():
    assert selection_key("a", "b") != selection_key("b", "a")


# ------------------------------------------------------------------- templates

def test_render_numeric_question_instant():
    q = render_numeric_question(tag="Assets", label="Total assets", period_type="instant", company="ACME CORP", fiscal_year=2019)
    assert "ACME CORP" in q
    assert "2019" in q
    assert "at the end of fiscal year" in q


def test_render_numeric_question_duration():
    q = render_numeric_question(tag="Revenues", label="Total revenues", period_type="duration", company="ACME CORP", fiscal_year=2019)
    assert "for fiscal year 2019" in q


def test_render_numeric_question_eps_phrasing():
    q = render_numeric_question(tag="EarningsPerShareDiluted", label="Earnings per share, diluted", period_type="duration", company="ACME CORP", fiscal_year=2019)
    assert "diluted earnings per share" in q
    assert "ACME CORP" in q


def test_render_numeric_question_never_leaks_tag_name():
    q = render_numeric_question(tag="Assets", label="Total assets", period_type="instant", company="ACME CORP", fiscal_year=2019)
    assert "Assets" not in q  # internal XBRL tag name (capitalized concept ID) not in question


def test_render_yoy_question():
    q = render_yoy_question(tag="Revenues", label="Total revenues", company="ACME CORP", year_a=2018, year_b=2019)
    assert "ACME CORP" in q and "2018" in q and "2019" in q


def test_render_cross_entity_question():
    q = render_cross_entity_question(tag="Assets", label="Total assets", company_a="A CORP", company_b="B CORP", fiscal_year=2019)
    assert "A CORP" in q and "B CORP" in q and "2019" in q


# ------------------------------------------------------------------ numeric record

def test_build_numeric_record_fields():
    fact = _fact(value=12345.0)
    r = build_numeric_record(fact=fact, label="Total assets", period_type="instant", prov=PROV)
    assert r["category"] == "numeric"
    assert r["cik"] == fact.cik
    assert r["accession"] == fact.adsh
    assert r["tag"] == "Assets"
    assert r["expected_value"] == repr(12345.0)
    assert r["expected_unit"] == "USD"
    assert r["registry_hash"] == PROV.registry_hash
    assert r["truth_contract_hash"] == PROV.truth_contract_hash


def test_numeric_record_preserves_negative_value():
    fact = _fact(tag="NetIncomeLoss", value=-500.0)
    r = build_numeric_record(fact=fact, label="Net income (loss)", period_type="duration", prov=PROV)
    assert r["expected_value"] == repr(-500.0)


def test_numeric_record_preserves_zero_value():
    fact = _fact(value=0.0)
    r = build_numeric_record(fact=fact, label="Total assets", period_type="instant", prov=PROV)
    assert r["expected_value"] == repr(0.0)


# --------------------------------------------------------------- comparative

def test_build_yoy_record_arithmetic():
    fact_a = _fact(adsh="A", tag="Revenues", fiscal_year=2018, value=100.0, qtrs=4)
    fact_b = _fact(adsh="B", tag="Revenues", fiscal_year=2019, value=150.0, qtrs=4)
    r = build_yoy_record(tag="Revenues", label="Total revenues", company="ACME CORP", cik=1000, fact_a=fact_a, fact_b=fact_b, prov=PROV)
    assert r["operation"] == "difference"
    assert r["expected_numeric_answer"] == repr(50.0)
    assert len(r["operands"]) == 2
    assert r["operands"][0]["accession"] == "A"
    assert r["operands"][1]["accession"] == "B"


def test_build_yoy_record_negative_difference():
    fact_a = _fact(adsh="A", fiscal_year=2018, value=200.0)
    fact_b = _fact(adsh="B", fiscal_year=2019, value=150.0)
    r = build_yoy_record(tag="Assets", label="Total assets", company="ACME CORP", cik=1000, fact_a=fact_a, fact_b=fact_b, prov=PROV)
    assert r["expected_numeric_answer"] == repr(-50.0)


def test_build_cross_entity_record_picks_greater():
    fact_a = _fact(adsh="A", cik=1, company="A CORP", value=100.0)
    fact_b = _fact(adsh="B", cik=2, company="B CORP", value=200.0)
    r = build_cross_entity_record(tag="Assets", label="Total assets", fact_a=fact_a, fact_b=fact_b, prov=PROV)
    assert r["expected_answer"] == "B CORP"
    assert r["operation"] == "greater_than"


def test_build_cross_entity_record_tie_picks_first():
    fact_a = _fact(adsh="A", cik=1, company="A CORP", value=100.0)
    fact_b = _fact(adsh="B", cik=2, company="B CORP", value=100.0)
    r = build_cross_entity_record(tag="Assets", label="Total assets", fact_a=fact_a, fact_b=fact_b, prov=PROV)
    assert r["expected_answer"] == "A CORP"


def test_comparative_never_compares_across_units():
    # both operands always carry the SAME tag's registry unit by construction -
    # verify the record structurally cannot express differing units silently
    fact_a = _fact(adsh="A", uom="USD", value=1.0)
    fact_b = _fact(adsh="B", uom="USD", value=2.0)
    r = build_yoy_record(tag="Assets", label="Total assets", company="ACME CORP", cik=1000, fact_a=fact_a, fact_b=fact_b, prov=PROV)
    units = {op["unit"] for op in r["operands"]}
    assert units == {"USD"}


# --------------------------------------------------------------- unanswerable

def test_unanswerable_year_rejects_in_window_year():
    with pytest.raises(ValueError):
        build_unanswerable_year_record(tag="Assets", label="Total assets", period_type="instant", company="ACME CORP", cik=1, out_of_window_year=2018, prov=PROV)


def test_unanswerable_year_record():
    r = build_unanswerable_year_record(tag="Assets", label="Total assets", period_type="instant", company="ACME CORP", cik=1, out_of_window_year=2014, prov=PROV)
    assert r["expected_behavior"] == "refuse_insufficient_evidence"
    assert r["fiscal_year"] == 2014
    assert "2014" in r["reason"]


def test_unanswerable_tag_record():
    r = build_unanswerable_tag_record(unsupported_tag="GoodwillImpairmentLoss", phrase="goodwill impairment loss", company="ACME CORP", cik=1, fiscal_year=2018, prov=PROV)
    assert r["expected_behavior"] == "refuse_insufficient_evidence"
    assert "GoodwillImpairmentLoss" not in r["question"]
    assert "goodwill impairment loss" in r["question"]


def test_unsupported_tag_candidates_are_not_in_a_registry_naming_the_real_15():
    # sanity: none of the 5 candidates match the 15 real supported tag names
    from src.eval.tag_registry import get_registry
    supported = set(get_registry().supported_tags())
    for tag, _ in UNSUPPORTED_TAG_CANDIDATES:
        assert tag not in supported


# ---------------------------------------------------------------- adversarial

def test_adversarial_record_no_company_placeholder_left():
    template = ADVERSARIAL_TEMPLATES["financial_advice"][0]
    r = build_adversarial_record(subtype="financial_advice", template=template, company="ACME CORP", prov=PROV)
    assert "{company}" not in r["question"]
    assert "ACME CORP" in r["question"]


def test_adversarial_expected_behavior_explicit():
    for subtype in ("prompt_injection", "financial_advice", "off_scope"):
        template = ADVERSARIAL_TEMPLATES[subtype][0]
        r = build_adversarial_record(subtype=subtype, template=template, company="ACME CORP" if "{company}" in template else None, prov=PROV)
        assert r["expected_behavior"] == ADVERSARIAL_EXPECTED_BEHAVIOR[subtype]
        assert r["answer_type"] == "adversarial"


def test_adversarial_templates_all_distinct_within_subtype():
    for subtype, templates in ADVERSARIAL_TEMPLATES.items():
        assert len(templates) == len(set(templates)), f"duplicate template text in {subtype}"


# ------------------------------------------------------------------- narrative

def test_narrative_record_always_pending_review():
    r = build_narrative_record(
        question="What did the company report about its main products?",
        cik=1, company="ACME CORP", fiscal_year=2018, document_id="1_2018.htm",
        source_section_column="section_1", source_section_sha256="s" * 64,
        provider="openrouter", requested_model="openai/gpt-oss-20b", response_model="openai/gpt-oss-20b",
        prompt_version="1.0", prov=PROV,
    )
    assert r["status"] == "pending_review"
    assert r["category"] == "narrative"


# --------------------------------------------------------------------- question IDs

def test_assign_question_ids_format_and_order():
    records = [
        {"category": "adversarial", "subtype": "off_scope", "question": "z"},
        {"category": "numeric", "subtype": "xbrl_fact", "tag": "Assets", "cik": 2, "fiscal_year": 2018, "question": "a"},
        {"category": "numeric", "subtype": "xbrl_fact", "tag": "Assets", "cik": 1, "fiscal_year": 2018, "question": "b"},
    ]
    out = assign_question_ids(records)
    assert [r["question_id"] for r in out] == ["phase2-eval-000001", "phase2-eval-000002", "phase2-eval-000003"]
    assert out[0]["category"] == "numeric"  # numeric sorts before adversarial
    assert out[2]["category"] == "adversarial"


def test_assign_question_ids_deterministic():
    records = [{"category": "numeric", "subtype": "xbrl_fact", "tag": "Assets", "cik": i, "fiscal_year": 2018, "question": f"q{i}"} for i in range(10)]
    out1 = assign_question_ids(records)
    out2 = assign_question_ids(records)
    assert [r["question_id"] for r in out1] == [r["question_id"] for r in out2]


# ------------------------------------------------------------------------ hashing

def test_dataset_hash_deterministic():
    records = [{"question_id": "phase2-eval-000001", "question": "a"}]
    assert compute_dataset_sha256(records) == compute_dataset_sha256(records)


def test_dataset_hash_64_hex():
    h = compute_dataset_sha256([{"question_id": "phase2-eval-000001"}])
    assert len(h) == 64


def test_canonical_json_sorted_keys():
    assert canonical_records_json([{"b": 1, "a": 2}]) == b'[{"a":2,"b":1}]'


def test_dataset_hash_changes_with_content():
    h1 = compute_dataset_sha256([{"question_id": "phase2-eval-000001", "question": "a"}])
    h2 = compute_dataset_sha256([{"question_id": "phase2-eval-000001", "question": "b"}])
    assert h1 != h2


# ----------------------------------------------------------------------- leakage

def test_leakage_detects_accession_in_question():
    r = {"question_id": "q1", "question": "What was Acme's revenue per accession 0001234567-20-000001?", "accession": "0001234567-20-000001"}
    with pytest.raises(LeakageError):
        check_no_leakage([r])


def test_leakage_detects_tag_name_in_question():
    r = {"question_id": "q1", "question": "What was the AccountsReceivableNetCurrent value?", "tag": "AccountsReceivableNetCurrent"}
    with pytest.raises(LeakageError):
        check_no_leakage([r])


def test_leakage_detects_expected_value_in_question():
    r = {"question_id": "q1", "question": "Is the answer 12345.0?", "expected_value": "12345.0"}
    with pytest.raises(LeakageError):
        check_no_leakage([r])


def test_leakage_clean_record_passes():
    r = {"question_id": "q1", "question": "What was ACME CORP's total assets for fiscal year 2019?", "accession": "0001-19-000001", "tag": "Assets", "expected_value": "1000.0"}
    check_no_leakage([r])  # should not raise


def test_leakage_detects_operand_accession():
    r = {"question_id": "q1", "question": "See accession 0001-19-000001 for details.",
         "operands": [{"accession": "0001-19-000001"}]}
    with pytest.raises(LeakageError):
        check_no_leakage([r])


# --------------------------------------------------------------------- duplicates

def test_duplicate_question_text_rejected():
    records = [
        {"question_id": "q1", "question": "same text", "category": "numeric"},
        {"question_id": "q2", "question": "same text", "category": "numeric"},
    ]
    with pytest.raises(DuplicateQuestionError):
        check_no_duplicate_questions(records)


def test_duplicate_semantic_numeric_rejected():
    records = [
        {"question_id": "q1", "question": "a", "category": "numeric", "subtype": "xbrl_fact", "cik": 1, "accession": "A", "tag": "Assets", "fiscal_year": 2018},
        {"question_id": "q2", "question": "b", "category": "numeric", "subtype": "xbrl_fact", "cik": 1, "accession": "A", "tag": "Assets", "fiscal_year": 2018},
    ]
    with pytest.raises(DuplicateQuestionError):
        check_no_duplicate_questions(records)


def test_no_false_duplicate_for_different_yoy_year_pairs():
    records = [
        {"question_id": "q1", "question": "a", "category": "comparative", "subtype": "year_over_year_difference", "cik": 1, "tag": "Assets", "operands": [{"fiscal_year": 2016}, {"fiscal_year": 2017}]},
        {"question_id": "q2", "question": "b", "category": "comparative", "subtype": "year_over_year_difference", "cik": 1, "tag": "Assets", "operands": [{"fiscal_year": 2018}, {"fiscal_year": 2019}]},
    ]
    check_no_duplicate_questions(records)  # should not raise


def test_no_false_duplicate_for_different_cross_entity_pairs():
    records = [
        {"question_id": "q1", "question": "a", "category": "comparative", "subtype": "cross_entity_comparison", "tag": "Assets", "fiscal_year": 2018, "operands": [{"cik": 1}, {"cik": 2}]},
        {"question_id": "q2", "question": "b", "category": "comparative", "subtype": "cross_entity_comparison", "tag": "Assets", "fiscal_year": 2018, "operands": [{"cik": 3}, {"cik": 4}]},
    ]
    check_no_duplicate_questions(records)  # should not raise


# ---------------------------------------------------------------------- category order

def test_category_order_fixed():
    assert CATEGORY_ORDER == ("numeric", "comparative", "narrative", "unanswerable", "adversarial")


def test_fiscal_year_window_constants():
    assert SUPPORTED_FISCAL_YEAR_MIN == 2016
    assert SUPPORTED_FISCAL_YEAR_MAX == 2020


# =================================================================== real-data (local_data)

DATASET_PATH = "results/phase_2_3_evaluation_dataset.json"


@pytest.mark.local_data
def test_real_dataset_schema_and_provenance():
    import json
    import os
    if not os.path.isfile(DATASET_PATH):
        pytest.skip(f"real evaluation dataset not present at {DATASET_PATH}")

    from src.eval.tag_registry import get_registry, compute_registry_hash
    from src.eval.truth_contract import build_contract_config, compute_contract_config_hash

    d = json.load(open(DATASET_PATH, encoding="utf-8"))
    questions = d["questions"]
    assert len(questions) == d["question_count"]

    ids = [q["question_id"] for q in questions]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids)

    registry = get_registry()
    expected_registry_hash = compute_registry_hash(registry)
    supported = set(registry.supported_tags())

    numeric_qs = [q for q in questions if q["category"] == "numeric"]
    assert len(numeric_qs) > 0
    for q in numeric_qs:
        assert q["tag"] in supported
        assert q["registry_hash"] == expected_registry_hash
        spec = registry.get(q["tag"])
        assert q["expected_unit"] == spec.unit
        assert q["qtrs"] == spec.qtrs

    narrative_qs = [q for q in questions if q["category"] == "narrative"]
    for q in narrative_qs:
        assert q["status"] == "pending_review"

    recomputed_hash = compute_dataset_sha256(questions)
    assert recomputed_hash == d["dataset_sha256"]

    check_no_leakage(questions)
    check_no_duplicate_questions(questions)
