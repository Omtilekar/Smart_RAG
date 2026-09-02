"""Task 2.8 - tests for src/parse/evidence_alignment.py. Uses an
in-memory DuckDB `facts` table shaped like the real schema - never the
real 7GB data/xbrl.duckdb for portable tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import duckdb
import pytest

from src.parse.evidence_alignment import (
    FactIdentity,
    bare_tag_name,
    unit_measure_to_uom,
    unit_to_uom,
    match_against_raw_facts,
    check_eligibility_dimensions,
    is_fully_eligible,
    determine_alignment_status,
    find_candidate_nodes,
    build_evidence_id,
)


@pytest.fixture
def con():
    connection = duckdb.connect(":memory:")
    connection.execute("""
        CREATE TABLE facts (
            adsh VARCHAR, cik BIGINT, tag VARCHAR, ddate VARCHAR, qtrs INTEGER,
            uom VARCHAR, value DOUBLE, coreg VARCHAR, segments VARCHAR
        )
    """)
    yield connection
    connection.close()


def insert_fact(con, **kwargs):
    defaults = {"adsh": "acc-1", "cik": 100, "tag": "Assets", "ddate": "20231231", "qtrs": 0, "uom": "USD", "value": 1000.0, "coreg": None, "segments": None}
    defaults.update(kwargs)
    con.execute(
        "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [defaults[k] for k in ("adsh", "cik", "tag", "ddate", "qtrs", "uom", "value", "coreg", "segments")],
    )


# --------------------------------------------------------------- bare_tag_name / units

def test_bare_tag_name_with_namespace():
    assert bare_tag_name("us-gaap:Assets") == ("us-gaap", "Assets")


def test_bare_tag_name_without_namespace():
    assert bare_tag_name("Assets") == (None, "Assets")


def test_unit_measure_usd():
    assert unit_measure_to_uom(["iso4217:USD"]) == "USD"


def test_unit_measure_shares():
    assert unit_measure_to_uom(["xbrli:shares"]) == "shares"


def test_unit_measure_compound_returns_none():
    assert unit_measure_to_uom(["iso4217:USD", "xbrli:shares"]) is None


def test_unit_measure_unknown_namespace_returns_none():
    assert unit_measure_to_uom(["custom:widget"]) is None


def test_unit_to_uom_simple_measure():
    from src.parse.inline_xbrl import XbrlUnit
    u = XbrlUnit(unit_id="usd", measures=("iso4217:USD",))
    assert unit_to_uom(u) == "USD"


def test_unit_to_uom_eps_divide_unit_maps_to_numerator_currency():
    # verified against real data: Amazon's EarningsPerShareDiluted inline
    # fact uses a USD/shares divide unit, but the real facts table row
    # for the same accession stores uom='USD' - SEC's own pipeline
    # strips the per-share denominator for storage (Task 2.2's registry
    # decision).
    from src.parse.inline_xbrl import XbrlUnit
    u = XbrlUnit(unit_id="usdPerShare", measures=(), divide_numerator=("iso4217:USD",), divide_denominator=("xbrli:shares",))
    assert unit_to_uom(u) == "USD"


def test_unit_to_uom_divide_unit_non_shares_denominator_returns_none():
    from src.parse.inline_xbrl import XbrlUnit
    u = XbrlUnit(unit_id="usdPerSqft", measures=(), divide_numerator=("iso4217:USD",), divide_denominator=("utr:sqft",))
    assert unit_to_uom(u) is None


def test_unit_to_uom_divide_unit_compound_numerator_returns_none():
    from src.parse.inline_xbrl import XbrlUnit
    u = XbrlUnit(unit_id="weird", measures=(), divide_numerator=("iso4217:USD", "iso4217:EUR"), divide_denominator=("xbrli:shares",))
    assert unit_to_uom(u) is None


# --------------------------------------------------------------- raw fact matching (accession-first)

def test_exact_raw_match(con):
    insert_fact(con, adsh="acc-1", tag="Assets", value=1000.0)
    identity = FactIdentity(accession="acc-1", cik=100, tag="Assets", ddate="20231231", qtrs=0, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1000"))
    assert result.status == "exact"


def test_raw_match_restricted_to_accession_first(con):
    # same tag/value under a DIFFERENT accession must never match -
    # Section 34: accession-first, never a global search.
    insert_fact(con, adsh="acc-OTHER", tag="Assets", value=1000.0)
    identity = FactIdentity(accession="acc-1", cik=100, tag="Assets", ddate="20231231", qtrs=0, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1000"))
    assert result.status == "unmatched"


def test_raw_match_unmatched_when_no_row(con):
    identity = FactIdentity(accession="acc-1", cik=100, tag="Assets", ddate="20231231", qtrs=0, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1000"))
    assert result.status == "unmatched"


def test_raw_match_ambiguous_on_conflicting_values(con):
    insert_fact(con, adsh="acc-1", tag="Assets", value=1000.0, coreg=None, segments=None)
    insert_fact(con, adsh="acc-1", tag="Assets", value=2000.0, coreg=None, segments=None)
    identity = FactIdentity(accession="acc-1", cik=100, tag="Assets", ddate="20231231", qtrs=0, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1000"))
    assert result.status == "ambiguous"


def test_raw_match_ignores_dimensional_duplicate(con):
    # blank-segment row is the real value; a dimensional duplicate for
    # the same grain must never be picked up instead (this is the exact
    # bug found against real data - see module docstring).
    insert_fact(con, adsh="acc-1", tag="Revenues", qtrs=4, value=1875448000.0, coreg=None, segments=None)
    insert_fact(con, adsh="acc-1", tag="Revenues", qtrs=4, value=39000000.0, coreg=None, segments="SomeAxis=SomeMember;")
    identity = FactIdentity(accession="acc-1", cik=100, tag="Revenues", ddate="20231231", qtrs=4, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1875448000"))
    assert result.status == "exact"


def test_raw_match_value_mismatch_is_unmatched(con):
    insert_fact(con, adsh="acc-1", tag="Assets", value=999.0)
    identity = FactIdentity(accession="acc-1", cik=100, tag="Assets", ddate="20231231", qtrs=0, uom="USD")
    result = match_against_raw_facts(con, identity, Decimal("1000"))
    assert result.status == "unmatched"


# --------------------------------------------------------------- eligibility dimensions

def test_eligibility_non_us_gaap_namespace_unsupported():
    check = check_eligibility_dimensions(tag="SomeExtension", namespace="tep", uom="USD", qtrs=4, has_dimensions=False, fiscal_year=2018)
    assert check.tag_supported is False


def test_eligibility_year_in_window():
    check = check_eligibility_dimensions(tag="Assets", namespace="us-gaap", uom="USD", qtrs=0, has_dimensions=False, fiscal_year=2018)
    assert check.year_in_window is True


def test_eligibility_year_outside_window():
    check = check_eligibility_dimensions(tag="Assets", namespace="us-gaap", uom="USD", qtrs=0, has_dimensions=False, fiscal_year=2023)
    assert check.year_in_window is False


def test_eligibility_dimension_free():
    check = check_eligibility_dimensions(tag="Assets", namespace="us-gaap", uom="USD", qtrs=0, has_dimensions=True, fiscal_year=2018)
    assert check.dimension_free is False


def test_eligibility_real_registry_supported_tag():
    # Assets is a real Task 2.2 supported tag - qtrs=0, unit=USD
    check = check_eligibility_dimensions(tag="Assets", namespace="us-gaap", uom="USD", qtrs=0, has_dimensions=False, fiscal_year=2018)
    assert check.tag_supported is True
    assert check.unit_matches_registry is True
    assert check.qtrs_matches_registry is True
    assert is_fully_eligible(check) is True


def test_eligibility_real_registry_wrong_qtrs():
    check = check_eligibility_dimensions(tag="Assets", namespace="us-gaap", uom="USD", qtrs=4, has_dimensions=False, fiscal_year=2018)
    assert check.qtrs_matches_registry is False
    assert is_fully_eligible(check) is False


def test_eligibility_unknown_us_gaap_tag_unsupported():
    check = check_eligibility_dimensions(tag="SomeRandomConceptNotInRegistry", namespace="us-gaap", uom="USD", qtrs=4, has_dimensions=False, fiscal_year=2018)
    assert check.tag_supported is False


# --------------------------------------------------------------- alignment status priority

def test_status_unsupported_tag_before_dimensional():
    from src.parse.evidence_alignment import EligibilityCheck
    check = EligibilityCheck(tag_supported=False, unit_matches_registry=None, qtrs_matches_registry=None, dimension_free=False, year_in_window=True, fiscal_year=2018)
    status = determine_alignment_status(raw_match=None, eligibility=check, node_ids=[])
    assert status == "unsupported_tag"


def test_status_ineligible_dimensional():
    from src.parse.evidence_alignment import EligibilityCheck
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=False, year_in_window=True, fiscal_year=2018)
    status = determine_alignment_status(raw_match=None, eligibility=check, node_ids=[])
    assert status == "ineligible_dimensional"


def test_status_ambiguous(con):
    from src.parse.evidence_alignment import EligibilityCheck, RawMatchResult
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=True, fiscal_year=2018)
    raw = RawMatchResult(status="ambiguous", matched_values=(Decimal(1), Decimal(2)))
    assert determine_alignment_status(raw_match=raw, eligibility=check, node_ids=[]) == "ambiguous"


def test_status_unmatched():
    from src.parse.evidence_alignment import EligibilityCheck, RawMatchResult
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=True, fiscal_year=2018)
    raw = RawMatchResult(status="unmatched", matched_values=())
    assert determine_alignment_status(raw_match=raw, eligibility=check, node_ids=[]) == "unmatched"


def test_status_ineligible_year_window():
    from src.parse.evidence_alignment import EligibilityCheck, RawMatchResult
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=False, fiscal_year=2023)
    raw = RawMatchResult(status="exact", matched_values=(Decimal(1),))
    assert determine_alignment_status(raw_match=raw, eligibility=check, node_ids=["n1"]) == "ineligible_year_window"


def test_status_exact_no_node():
    from src.parse.evidence_alignment import EligibilityCheck, RawMatchResult
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=True, fiscal_year=2018)
    raw = RawMatchResult(status="exact", matched_values=(Decimal(1),))
    assert determine_alignment_status(raw_match=raw, eligibility=check, node_ids=[]) == "exact_no_node"


def test_status_exact_with_node():
    from src.parse.evidence_alignment import EligibilityCheck, RawMatchResult
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=True, fiscal_year=2018)
    raw = RawMatchResult(status="exact", matched_values=(Decimal(1),))
    assert determine_alignment_status(raw_match=raw, eligibility=check, node_ids=["n1"]) == "exact"


def test_raw_match_none_after_confirmed_non_dimensional_raises():
    from src.parse.evidence_alignment import EligibilityCheck
    check = EligibilityCheck(tag_supported=True, unit_matches_registry=True, qtrs_matches_registry=True, dimension_free=True, year_in_window=True, fiscal_year=2018)
    with pytest.raises(ValueError):
        determine_alignment_status(raw_match=None, eligibility=check, node_ids=[])


# --------------------------------------------------------------- candidate node matching

@dataclass
class _FakeNode:
    node_id: str
    text: str


def test_find_candidate_nodes_single_match():
    nodes = [_FakeNode("n1", "Total assets were 1,234,567 dollars."), _FakeNode("n2", "Unrelated text.")]
    assert find_candidate_nodes("1,234,567", nodes) == ["n1"]


def test_find_candidate_nodes_multiple_occurrences_all_returned():
    # Section 44: the same value appearing in a summary table AND a
    # financial statement must return BOTH nodes, never just the first.
    nodes = [_FakeNode("n1", "Summary: 1,234,567"), _FakeNode("n2", "Statement: 1,234,567"), _FakeNode("n3", "other")]
    assert find_candidate_nodes("1,234,567", nodes) == ["n1", "n2"]


def test_find_candidate_nodes_whitespace_normalized():
    nodes = [_FakeNode("n1", "Total   assets\nwere  1,000")]
    assert find_candidate_nodes("1,000", nodes) == ["n1"]


def test_find_candidate_nodes_empty_text_matches_nothing():
    nodes = [_FakeNode("n1", "anything")]
    assert find_candidate_nodes("", nodes) == []


def test_find_candidate_nodes_no_match():
    nodes = [_FakeNode("n1", "unrelated")]
    assert find_candidate_nodes("42", nodes) == []


# --------------------------------------------------------------- evidence ID

def test_build_evidence_id_with_element_id():
    assert build_evidence_id("primary:1:acc-1", "f-42", 5) == "primary:1:acc-1#fact-f-42"


def test_build_evidence_id_without_element_id():
    assert build_evidence_id("primary:1:acc-1", None, 5) == "primary:1:acc-1#fact-order-00005"
