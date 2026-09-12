"""Task 3.10 - portable tests for src.sql.xbrl_lookup. Synthetic
in-memory DuckDB database whose facts/submissions schema mirrors the
real data/xbrl.duckdb schema (same convention as tests/test_truth_contract.py) -
never touches the real frozen database."""

from __future__ import annotations

import duckdb

from src.sql.xbrl_lookup import XbrlFactIndex

FACTS_COLUMNS = "adsh, cik, company, form, fiscal_year, fp, tag, version, ddate, qtrs, uom, coreg, segments, value"
SUBMISSIONS_COLUMNS = "adsh, cik, name, form, fiscal_year, fp, period, filed"


def _con():
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE facts (
            adsh VARCHAR, cik BIGINT, company VARCHAR, form VARCHAR, fiscal_year INTEGER,
            fp VARCHAR, tag VARCHAR, version VARCHAR, ddate VARCHAR, qtrs INTEGER,
            uom VARCHAR, coreg VARCHAR, segments VARCHAR, value DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE submissions (
            adsh VARCHAR, cik BIGINT, name VARCHAR, form VARCHAR, fiscal_year INTEGER,
            fp VARCHAR, period VARCHAR, filed VARCHAR
        )
    """)
    return con


def _insert_fact(con, **kwargs):
    defaults = dict(
        adsh="0000000000-20-000001", cik=1000, company="ACME CORP", form="10-K",
        fiscal_year=2018, fp="FY", tag="Assets", version="us-gaap/2018", ddate="20181231",
        qtrs=0, uom="USD", coreg=None, segments=None, value=1000.0,
    )
    defaults.update(kwargs)
    con.execute(
        "INSERT INTO facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [defaults[c.strip()] for c in FACTS_COLUMNS.split(",")],
    )


def _insert_submission(con, **kwargs):
    defaults = dict(
        adsh="0000000000-20-000001", cik=1000, name="ACME CORP", form="10-K",
        fiscal_year=2018, fp="FY", period="20181231", filed="20190215",
    )
    defaults.update(kwargs)
    con.execute(
        "INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?)",
        [defaults[c.strip()] for c in SUBMISSIONS_COLUMNS.split(",")],
    )


def _baseline(con):
    _insert_submission(con)
    _insert_fact(con)


# --------------------------------------------------------------- lookup outcomes

def test_lookup_found():
    con = _con()
    _baseline(con)
    index = XbrlFactIndex(con, ["Assets"])
    result = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
    assert result.outcome == "found"
    assert result.value == 1000.0
    assert result.unit == "USD"
    assert result.adsh == "0000000000-20-000001"
    assert result.company == "ACME CORP"


def test_lookup_not_found_wrong_cik():
    con = _con()
    _baseline(con)
    index = XbrlFactIndex(con, ["Assets"])
    result = index.lookup(cik=9999, fiscal_year=2018, tag="Assets")
    assert result.outcome == "not_found"


def test_lookup_not_found_wrong_fiscal_year():
    con = _con()
    _baseline(con)
    index = XbrlFactIndex(con, ["Assets"])
    result = index.lookup(cik=1000, fiscal_year=2019, tag="Assets")
    assert result.outcome == "not_found"


def test_lookup_unsupported_tag_never_answered():
    con = _con()
    _baseline(con)
    # The tag itself is requested from the index (mirroring a real
    # router-extracted concept the registry does not support) - the
    # registry's own TruthContractError is caught and recorded, never
    # silently treated as an ordinary "not indexed" miss.
    index = XbrlFactIndex(con, ["Assets", "DepreciationDepletionAndAmortization"])
    result = index.lookup(cik=1000, fiscal_year=2018, tag="DepreciationDepletionAndAmortization")
    assert result.outcome == "unsupported_tag"
    assert result.value is None


def test_lookup_unsupported_tag_raised_by_registry():
    con = _con()
    _baseline(con)
    # Construct the index while asking for a genuinely-unsupported tag directly.
    index = XbrlFactIndex(con, ["Assets", "NotARealTag"])
    result = index.lookup(cik=1000, fiscal_year=2018, tag="NotARealTag")
    assert result.outcome == "unsupported_tag"
    # The supported tag in the same index still works.
    ok = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
    assert ok.outcome == "found"


def test_lookup_ambiguous_on_conflicting_cross_filing_values():
    con = _con()
    _insert_submission(con, adsh="0000000000-20-000001")
    _insert_fact(con, adsh="0000000000-20-000001", value=1000.0)
    _insert_submission(con, adsh="0000000000-21-000002", filed="20200301")
    _insert_fact(con, adsh="0000000000-21-000002", value=1200.0, ddate="20181231")
    index = XbrlFactIndex(con, ["Assets"])
    result = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
    assert result.outcome == "ambiguous"
    assert result.candidate_count == 2


def test_lookup_not_ambiguous_when_values_agree_across_filings():
    con = _con()
    _insert_submission(con, adsh="0000000000-20-000001")
    _insert_fact(con, adsh="0000000000-20-000001", value=1000.0)
    _insert_submission(con, adsh="0000000000-21-000002", filed="20200301")
    _insert_fact(con, adsh="0000000000-21-000002", value=1000.0, ddate="20181231")
    index = XbrlFactIndex(con, ["Assets"])
    result = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
    assert result.outcome == "found"
    assert result.value == 1000.0


def test_lookup_never_confidently_answers_a_fact_never_indexed():
    # A trap-style question about a tag the index was never built for
    # must never return "found" - the hard safety invariant.
    con = _con()
    _baseline(con)
    index = XbrlFactIndex(con, ["Liabilities"])  # Assets never indexed here
    result = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
    assert result.outcome != "found"


def test_index_builds_once_per_tag_not_once_per_lookup():
    con = _con()
    _baseline(con)
    index = XbrlFactIndex(con, ["Assets"])
    # Multiple lookups against the same pre-built index - no new query per call.
    for _ in range(5):
        result = index.lookup(cik=1000, fiscal_year=2018, tag="Assets")
        assert result.outcome == "found"
