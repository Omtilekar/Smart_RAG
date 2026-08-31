"""Task 1.9 - portable tests for src/eval/smoke_dataset.py.

Pure-logic tests only: small synthetic manifest/source_rows fixtures, no
network, no GPU, no DuckDB, no local data. Real-data integration coverage
lives in test_smoke_evaluation_real_dataset (local_data-marked, below).
"""

import pytest

from src.eval.smoke_dataset import (
    CATEGORY_ORDER,
    CATEGORY_SECTION_COLUMN,
    QUESTION_TEMPLATES,
    QUESTIONS_PER_CATEGORY,
    LABEL_GRANULARITY,
    RETRIEVAL_METRIC,
    TARGET_FORM_TYPE,
    is_eligible_section,
    selection_key,
    compute_source_section_sha256,
    render_question,
    build_category_candidates,
    select_for_category,
    select_all_categories,
    build_question_record,
    assign_question_ids,
    canonical_records_json,
    compute_smoke_eval_sha256,
)


def _row(doc_id, cik=1000, year=2018, company="ACME CORP", split="train"):
    return {
        "document_id": doc_id, "cik": cik, "year": year,
        "company_name": company, "source_filename": doc_id, "source_split": split,
    }


def _source(doc_id, **sections):
    base = {c: None for c in CATEGORY_SECTION_COLUMN.values()}
    base.update(sections)
    return {doc_id: base}


# ------------------------------------------------------- category/section mapping

def test_category_order_and_section_mapping_fixed():
    assert CATEGORY_ORDER == ("business", "risk_factors", "mdna", "market_risk", "financial_statements")
    assert CATEGORY_SECTION_COLUMN == {
        "business": "section_1", "risk_factors": "section_1A", "mdna": "section_7",
        "market_risk": "section_7A", "financial_statements": "section_8",
    }


# ------------------------------------------------------------- empty-section rejection

def test_eligible_requires_nonempty_nonwhitespace_string():
    assert is_eligible_section("real text") is True
    assert is_eligible_section("") is False
    assert is_eligible_section("   \n\t  ") is False
    assert is_eligible_section(None) is False
    assert is_eligible_section(123) is False


def test_build_category_candidates_excludes_empty_sections():
    filings = [_row("a.htm"), _row("b.htm"), _row("c.htm")]
    source_rows = {
        "a.htm": {"section_1": "real business text"},
        "b.htm": {"section_1": ""},
        "c.htm": {"section_1": "   "},
    }
    candidates = build_category_candidates("business", filings, source_rows)
    assert [r["document_id"] for r in candidates] == ["a.htm"]


# --------------------------------------------------------------- SHA-256 determinism

def test_selection_key_is_sha256_hex_deterministic():
    k1 = selection_key("business", "doc1.htm")
    k2 = selection_key("business", "doc1.htm")
    assert k1 == k2
    assert len(k1) == 64
    assert all(c in "0123456789abcdef" for c in k1)


def test_selection_key_is_category_sensitive():
    assert selection_key("business", "doc1.htm") != selection_key("risk_factors", "doc1.htm")


def test_source_section_sha256_deterministic():
    h1 = compute_source_section_sha256("some section text")
    h2 = compute_source_section_sha256("some section text")
    assert h1 == h2
    assert len(h1) == 64
    assert compute_source_section_sha256("different text") != h1


# ------------------------------------------------------------- used-document skipping

def test_select_for_category_skips_used_documents():
    candidates = [_row("a.htm"), _row("b.htm")]
    used = {"a.htm"}
    selected = select_for_category("business", candidates, used, per_category=1)
    assert [r["document_id"] for r in selected] == ["b.htm"]


def test_select_for_category_returns_fewer_when_pool_exhausted():
    candidates = [_row("a.htm")]
    selected = select_for_category("business", candidates, set(), per_category=5)
    assert len(selected) == 1


# ----------------------------------------------------------------- balanced selection

def test_select_all_categories_balanced_and_unique():
    filings = []
    source_rows = {}
    for i in range(50):
        doc_id = f"doc{i}.htm"
        filings.append(_row(doc_id, cik=i))
        source_rows[doc_id] = {col: "text" for col in CATEGORY_SECTION_COLUMN.values()}
    selected_by_category, candidate_counts = select_all_categories(filings, source_rows, per_category=10)
    total_selected = sum(len(v) for v in selected_by_category.values())
    assert total_selected == 50
    all_ids = [r["document_id"] for cat in CATEGORY_ORDER for r in selected_by_category[cat]]
    assert len(set(all_ids)) == 50
    for cat in CATEGORY_ORDER:
        assert len(selected_by_category[cat]) == 10
        assert candidate_counts[cat] == 50


def test_select_all_categories_raises_when_insufficient_candidates():
    filings = [_row("a.htm")]
    source_rows = {"a.htm": {col: "text" for col in CATEGORY_SECTION_COLUMN.values()}}
    with pytest.raises(ValueError):
        select_all_categories(filings, source_rows, per_category=2)


# --------------------------------------------------------------- target-document uniqueness

def test_no_document_selected_twice_across_categories():
    filings = [_row(f"doc{i}.htm") for i in range(len(CATEGORY_ORDER))]
    source_rows = {
        f"doc{i}.htm": {col: "text" for col in CATEGORY_SECTION_COLUMN.values()}
        for i in range(len(CATEGORY_ORDER))
    }
    selected_by_category, _ = select_all_categories(filings, source_rows, per_category=1)
    ids = [r["document_id"] for cat in CATEGORY_ORDER for r in selected_by_category[cat]]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------- template rendering

def test_render_question_uses_frozen_template():
    q = render_question("business", "ACME CORP", 2019)
    assert q == "What does ACME CORP report about its business in its fiscal year 2019 10-K?"


def test_render_question_never_exposes_document_id():
    q = render_question("risk_factors", "ACME CORP", 2019)
    assert "doc" not in q.lower() or "document" not in q.lower()
    assert ".htm" not in q


def test_all_five_categories_have_templates():
    assert set(QUESTION_TEMPLATES.keys()) == set(CATEGORY_ORDER)


# ------------------------------------------------------------- question-ID determinism

def test_assign_question_ids_deterministic_and_ordered():
    records = [
        {"category": "risk_factors", "target_document_id": "b.htm"},
        {"category": "business", "target_document_id": "z.htm"},
        {"category": "business", "target_document_id": "a.htm"},
    ]
    out = assign_question_ids(records)
    ids = [r["question_id"] for r in out]
    assert ids == ["phase1-smoke-0001", "phase1-smoke-0002", "phase1-smoke-0003"]
    # category order (business before risk_factors), then target_document_id ascending
    assert [r["target_document_id"] for r in out] == ["a.htm", "z.htm", "b.htm"]


def test_assign_question_ids_repeat_call_identical():
    records = [{"category": "mdna", "target_document_id": f"{i}.htm"} for i in range(5)]
    out1 = assign_question_ids(records)
    out2 = assign_question_ids(records)
    assert [r["question_id"] for r in out1] == [r["question_id"] for r in out2]


# ------------------------------------------------------------------ dataset ordering

def test_dataset_ordering_groups_by_category_then_document_id():
    records = [
        {"category": "financial_statements", "target_document_id": "x.htm"},
        {"category": "business", "target_document_id": "y.htm"},
        {"category": "business", "target_document_id": "x.htm"},
    ]
    out = assign_question_ids(records)
    categories = [r["category"] for r in out]
    assert categories == ["business", "business", "financial_statements"]


# ------------------------------------------------------------- dataset hash determinism

def test_compute_smoke_eval_sha256_deterministic_and_order_sensitive():
    records = [{"question_id": "phase1-smoke-0001", "target_document_id": "a.htm"}]
    h1 = compute_smoke_eval_sha256(records)
    h2 = compute_smoke_eval_sha256(records)
    assert h1 == h2
    assert len(h1) == 64


def test_canonical_records_json_uses_sorted_keys_and_stable_separators():
    records = [{"b": 1, "a": 2}]
    blob = canonical_records_json(records)
    assert blob == b'[{"a":2,"b":1}]'


# ---------------------------------------------------------- document-level metric labels

def test_build_question_record_has_document_level_labels():
    row = _row("a.htm")
    source_rows = {"a.htm": {"section_1": "business text"}}
    record = build_question_record(
        "business", row, source_rows,
        development_manifest_sha256="x" * 64,
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="y" * 64,
    )
    assert record["label_granularity"] == LABEL_GRANULARITY == "document"
    assert record["retrieval_metric"] == RETRIEVAL_METRIC == "doc_recall@10"
    assert record["target_form_type"] == TARGET_FORM_TYPE == "10-K"


# ----------------------------------------------------- absence of target_chunk_id / accession

def test_build_question_record_never_fabricates_chunk_or_accession_fields():
    row = _row("a.htm")
    source_rows = {"a.htm": {"section_1": "business text"}}
    record = build_question_record(
        "business", row, source_rows,
        development_manifest_sha256="x" * 64,
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="y" * 64,
    )
    for forbidden in ("target_chunk_id", "accession", "expected_answer", "answer_span"):
        assert forbidden not in record


# ----------------------------------------------------- source_section_sha256 determinism

def test_build_question_record_source_section_sha256_matches_exact_text():
    row = _row("a.htm")
    source_rows = {"a.htm": {"section_1": "exact source text"}}
    record = build_question_record(
        "business", row, source_rows,
        development_manifest_sha256="x" * 64,
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="y" * 64,
    )
    assert record["source_section_sha256"] == compute_source_section_sha256("exact source text")


# ----------------------------------------------------- real-data integration (local_data)

DATASET_PATH = "results/phase_1_9_smoke_evaluation.json"
MANIFEST_PATH = "results/phase_1_1_development_corpus.json"
KNOWN_EMPTY_SOURCE_DOCUMENT_IDS = frozenset({
    "18498_2018.htm", "1324424_2018.htm", "71691_2016.htm", "1388410_2016.htm",
    "1388410_2018.htm", "883241_2017.htm", "1110803_2019.htm",
})


@pytest.mark.local_data
def test_real_smoke_evaluation_dataset():
    import json
    from pathlib import Path
    from src.storage import get_storage

    storage = get_storage()
    dataset_path = storage.repo_root / DATASET_PATH
    manifest_path = storage.repo_root / MANIFEST_PATH
    if not dataset_path.is_file():
        pytest.skip(f"Task 1.9 dataset not present at {dataset_path}")
    if not manifest_path.is_file():
        pytest.skip(f"Task 1.1 manifest not present at {manifest_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    qs = dataset["questions"]
    manifest_by_id = {r["document_id"]: r for r in manifest["filings"]}

    assert len(qs) == 200
    assert len({q["question_id"] for q in qs}) == 200
    assert len({q["question"] for q in qs}) == 200
    assert len({q["target_document_id"] for q in qs}) == 200

    counts = {}
    for q in qs:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    for category in CATEGORY_ORDER:
        assert counts.get(category) == 40, f"{category} has {counts.get(category)}, expected 40"

    for q in qs:
        doc_id = q["target_document_id"]
        assert doc_id in manifest_by_id, f"{doc_id} missing from Task 1.1 manifest"
        assert doc_id not in KNOWN_EMPTY_SOURCE_DOCUMENT_IDS
        m = manifest_by_id[doc_id]
        assert q["target_cik"] == m["cik"]
        assert q["target_fiscal_year"] == m["year"]
        assert q["target_fiscal_year"] in (2016, 2017, 2018, 2019, 2020)
        assert q["target_source_split"] == m["source_split"]
        assert q["target_form_type"] == "10-K"
        assert q["label_granularity"] == "document"
        assert q["retrieval_metric"] == "doc_recall@10"
