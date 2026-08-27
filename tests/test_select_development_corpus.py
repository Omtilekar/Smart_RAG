"""Tests for the deterministic helper logic in
scripts/select_development_corpus.py.

Deliberately does NOT re-run the full eligible-population reconstruction
against the 5.77 GB EDGAR-CORPUS parquet / xbrl.duckdb on every test - that
integration check is scripts/select_development_corpus.py's own real run
(Task 1.1 Step 34), not a unit test. Only the pure, cheap helper functions
(selection hashing, top-n selection, checksum, distribution stats) are
tested here, using small synthetic fixtures, per Task 1.1 Step 33.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "select_development_corpus.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("select_development_corpus", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sdc = _load_module()


def _make_rows(n, year=2018, cik_start=1000):
    return [
        {
            "document_id": f"{cik_start + i}_{year}.htm",
            "cik": cik_start + i,
            "year": year,
            "source": "edgar_corpus",
            "source_split": "train",
            "source_filename": f"{cik_start + i}_{year}.htm",
            "company_name": f"COMPANY {i}",
            "xbrl_alignment_year_field": "fy",
            "xbrl_10k_candidate_count": 1,
        }
        for i in range(n)
    ]


# ---------------------------------------------------------- selection_hash

def test_selection_hash_deterministic():
    assert sdc.selection_hash("1000_2018.htm") == sdc.selection_hash("1000_2018.htm")


def test_selection_hash_differs_for_different_ids():
    assert sdc.selection_hash("1000_2018.htm") != sdc.selection_hash("1001_2018.htm")


# ------------------------------------------------------------- select_top_n

def test_select_top_n_exact_count():
    rows = _make_rows(50)
    selected = sdc.select_top_n(rows, 10)
    assert len(selected) == 10


def test_select_top_n_no_duplicates():
    rows = _make_rows(50)
    selected = sdc.select_top_n(rows, 10)
    ids = [r["document_id"] for r in selected]
    assert len(ids) == len(set(ids))


def test_select_top_n_subset_of_eligible():
    rows = _make_rows(50)
    eligible_ids = {r["document_id"] for r in rows}
    selected = sdc.select_top_n(rows, 10)
    assert {r["document_id"] for r in selected}.issubset(eligible_ids)


def test_select_top_n_deterministic_same_input():
    rows = _make_rows(50)
    a = sdc.select_top_n(rows, 10)
    b = sdc.select_top_n(list(reversed(rows)), 10)  # input order must not matter
    assert [r["document_id"] for r in a] == [r["document_id"] for r in b]


def test_select_top_n_different_pool_changes_selection():
    rows_a = _make_rows(50, cik_start=1000)
    rows_b = _make_rows(50, cik_start=5000)
    sel_a = {r["document_id"] for r in sdc.select_top_n(rows_a, 10)}
    sel_b = {r["document_id"] for r in sdc.select_top_n(rows_b, 10)}
    assert sel_a.isdisjoint(sel_b)


def test_select_top_n_raises_on_insufficient_rows():
    rows = _make_rows(5)
    with pytest.raises(ValueError):
        sdc.select_top_n(rows, 10)


def test_select_top_n_raises_on_duplicate_document_id():
    rows = _make_rows(5)
    rows[1]["document_id"] = rows[0]["document_id"]
    with pytest.raises(ValueError):
        sdc.select_top_n(rows, 3)


# ------------------------------------------------------------ canonical_sort

def test_canonical_sort_is_deterministic_regardless_of_input_order():
    rows = _make_rows(20)
    a = sdc.canonical_sort(rows)
    b = sdc.canonical_sort(list(reversed(rows)))
    assert [r["document_id"] for r in a] == [r["document_id"] for r in b]
    assert [r["document_id"] for r in a] == sorted(r["document_id"] for r in rows)


# --------------------------------------------------------- manifest_checksum

def test_manifest_checksum_deterministic():
    rows = sdc.canonical_sort(_make_rows(20))
    assert sdc.manifest_checksum(rows) == sdc.manifest_checksum(rows)


def test_manifest_checksum_differs_for_different_content():
    rows_a = sdc.canonical_sort(_make_rows(20, cik_start=1000))
    rows_b = sdc.canonical_sort(_make_rows(20, cik_start=2000))
    assert sdc.manifest_checksum(rows_a) != sdc.manifest_checksum(rows_b)


def test_manifest_checksum_independent_of_list_order_input_but_not_dict_order():
    # canonical_sort output order matters (row order is part of the hashed
    # content) - this test documents that explicitly rather than assuming it.
    rows = sdc.canonical_sort(_make_rows(20))
    reversed_rows = list(reversed(rows))
    assert sdc.manifest_checksum(rows) != sdc.manifest_checksum(reversed_rows)


# -------------------------------------------------------- distribution stats

def test_filings_per_entity_stats_basic():
    rows = _make_rows(10, cik_start=1)
    rows += [dict(rows[0])]  # duplicate cik=1 entry (second filing, same cik)
    rows[-1]["document_id"] = "dup_doc.htm"
    stats = sdc.filings_per_entity_stats(rows, key="cik")
    assert stats["max"] == 2
    assert stats["min"] == 1


def test_filings_per_entity_stats_empty():
    stats = sdc.filings_per_entity_stats([], key="cik")
    assert stats["unique"] == 0
    assert stats["min"] is None


def test_year_distribution_covers_all_five_years_even_if_absent():
    rows = _make_rows(10, year=2018)
    dist = sdc.year_distribution(rows)
    assert set(dist.keys()) == {"2016", "2017", "2018", "2019", "2020"}
    assert dist["2018"]["count"] == 10
    assert dist["2016"]["count"] == 0


def test_year_distribution_percentages_sum_to_100():
    rows = _make_rows(4, year=2016) + _make_rows(6, year=2020, cik_start=9000)
    dist = sdc.year_distribution(rows)
    total_pct = sum(v["pct"] for v in dist.values())
    assert abs(total_pct - 100.0) < 0.01
