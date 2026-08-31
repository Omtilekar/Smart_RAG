"""Task 2.1/2.2 - tests for src/eval/truth_contract.py.

Portable unit tests use a synthetic in-memory DuckDB database whose
facts/submissions schema exactly mirrors the real data/xbrl.duckdb schema
(verified directly against the real database before writing this file -
see project_plan/PHASE2_TRUTH_CONTRACT.md), together with the real,
tracked `configs/eval_tags.yaml` registry (a small versioned config file,
not frozen local data - loading it in a portable test is no different
from any other test reading a tracked repo file). A separate
local_data-marked integration test (bottom of file) exercises the real
frozen XBRL database.
"""

from __future__ import annotations

import duckdb
import pytest

from src.eval.truth_contract import (
    TruthContractError,
    EligibleFact,
    eligible_facts,
    build_contract_config,
    compute_contract_config_hash,
)
from src.eval.tag_registry import get_registry

PREVIOUSLY_UNRESOLVED_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "OperatingExpenses",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "IncomeTaxExpenseBenefit",
)

FACTS_COLUMNS = (
    "adsh, cik, company, form, fiscal_year, fp, tag, version, ddate, qtrs, uom, coreg, segments, value"
)
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
    """One clean, fully-eligible Assets fact + its submission."""
    _insert_submission(con)
    _insert_fact(con)


# ------------------------------------------------------------------ consolidation

def test_coreg_null_accepted():
    con = _con()
    _baseline(con)
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_coreg_blank_string_accepted():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, coreg="")
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_coreg_populated_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, coreg="SubsidiaryLP")
    assert len(eligible_facts(con, ["Assets"])) == 0


def test_segments_null_accepted():
    con = _con()
    _baseline(con)
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_segments_populated_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, segments="EquityComponents=RetainedEarnings;")
    assert len(eligible_facts(con, ["Assets"])) == 0


# ---------------------------------------------------------------------- taxonomy

def test_us_gaap_taxonomy_accepted():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, version="us-gaap/2020")
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_custom_taxonomy_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, version="0001287750-24-000054")
    assert len(eligible_facts(con, ["Assets"])) == 0


def test_literal_us_gaap_without_slash_rejected():
    # real data never has this, but the rule must be LIKE 'us-gaap/%', not '= us-gaap'
    con = _con()
    _insert_submission(con)
    _insert_fact(con, version="us-gaap")
    assert len(eligible_facts(con, ["Assets"])) == 0


# ------------------------------------------------------------------------- units

def test_usd_monetary_fact_accepted():
    con = _con()
    _baseline(con)
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_wrong_monetary_unit_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, uom="CAD")
    assert len(eligible_facts(con, ["Assets"])) == 0


# -------------------------------------------------------------------------- qtrs

def test_instant_tag_with_qtrs_0_accepted():
    con = _con()
    _baseline(con)  # Assets, qtrs=0
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_instant_tag_with_qtrs_4_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, qtrs=4)
    assert len(eligible_facts(con, ["Assets"])) == 0


def test_annual_duration_tag_with_qtrs_4_accepted():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, tag="Revenues", qtrs=4)
    assert len(eligible_facts(con, ["Revenues"])) == 1


def test_annual_duration_tag_with_qtrs_0_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, tag="Revenues", qtrs=0)
    assert len(eligible_facts(con, ["Revenues"])) == 0


def test_unknown_unregistered_tag_raises():
    con = _con()
    _baseline(con)
    with pytest.raises(TruthContractError):
        eligible_facts(con, ["SomeUnregisteredTag"])


def test_previously_unresolved_tags_now_supported():
    """Task 2.2 resolved all five tags Task 2.1 left unresolved - they
    must now work with eligible_facts(), not raise."""
    registry = get_registry()
    supported = set(registry.supported_tags())
    for tag in PREVIOUSLY_UNRESOLVED_TAGS:
        assert tag in supported
        spec = registry.get(tag)
        assert spec.period_type == "duration"
        assert spec.qtrs == 4
        con = _con()
        _insert_submission(con)
        _insert_fact(con, tag=tag, qtrs=4)
        assert len(eligible_facts(con, [tag])) == 1


# ---------------------------------------------------------------- period alignment

def test_ddate_matching_period_accepted():
    con = _con()
    _insert_submission(con, period="20181231")
    _insert_fact(con, ddate="20181231")
    assert len(eligible_facts(con, ["Assets"])) == 1


def test_wrong_period_fact_rejected():
    con = _con()
    _insert_submission(con, period="20181231")
    _insert_fact(con, ddate="20171231")  # a comparative prior-year column
    assert len(eligible_facts(con, ["Assets"])) == 0


# --------------------------------------------------------------------- fiscal year window

def test_year_outside_window_rejected():
    con = _con()
    _insert_submission(con, fiscal_year=2015, period="20151231")
    _insert_fact(con, fiscal_year=2015, ddate="20151231")
    assert len(eligible_facts(con, ["Assets"])) == 0


def test_form_not_10k_rejected():
    con = _con()
    _insert_submission(con, form="10-Q")
    _insert_fact(con, form="10-Q")
    assert len(eligible_facts(con, ["Assets"])) == 0


# --------------------------------------------------------------------------- values

def test_null_value_rejected():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=None)
    assert len(eligible_facts(con, ["Assets"])) == 0


def test_valid_positive_value_accepted():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=500.0)
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 1 and facts[0].value == 500.0


def test_valid_negative_value_accepted():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, tag="NetIncomeLoss", qtrs=4, value=-250.0)
    facts = eligible_facts(con, ["NetIncomeLoss"])
    assert len(facts) == 1 and facts[0].value == -250.0
    # never silently normalized to positive
    assert facts[0].value < 0


def test_zero_value_not_silently_discarded():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=0.0)
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 1 and facts[0].value == 0.0


# ----------------------------------------------------------------------- materiality

def test_no_materiality_filter_small_value_still_eligible():
    """Materiality is deliberately out of scope for truth validity
    (PROJECT_EXECUTION.md Task 2.1 checklist) - a tiny value must still
    be returned."""
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=1.0)
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 1 and facts[0].value == 1.0


def test_eligible_facts_has_no_min_magnitude_parameter():
    import inspect
    sig = inspect.signature(eligible_facts)
    assert "min_magnitude" not in sig.parameters


# ------------------------------------------------------------------- filing identity

def test_different_adsh_values_remain_distinguishable():
    con = _con()
    _insert_submission(con, adsh="0000000000-20-000001", period="20181231")
    _insert_submission(con, adsh="0000000000-21-000002", period="20181231")
    _insert_fact(con, adsh="0000000000-20-000001", ddate="20181231", value=100.0)
    _insert_fact(con, adsh="0000000000-21-000002", ddate="20181231", value=150.0)
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 2
    adsh_values = {f.adsh: f.value for f in facts}
    assert adsh_values == {"0000000000-20-000001": 100.0, "0000000000-21-000002": 150.0}


def test_cross_filing_revisions_not_silently_collapsed():
    con = _con()
    _insert_submission(con, adsh="A", period="20181231")
    _insert_submission(con, adsh="B", period="20181231")
    _insert_fact(con, adsh="A", ddate="20181231", value=100.0)
    _insert_fact(con, adsh="B", ddate="20181231", value=999.0)  # a later revision
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 2  # both preserved, no canonical value chosen


# --------------------------------------------------------------------- duplicate handling

def test_same_accession_identical_duplicate_collapsed():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=100.0)
    _insert_fact(con, value=100.0)  # exact duplicate row, same value
    facts = eligible_facts(con, ["Assets"])
    assert len(facts) == 1


def test_same_accession_conflicting_duplicate_raises():
    con = _con()
    _insert_submission(con)
    _insert_fact(con, value=100.0)
    _insert_fact(con, value=200.0)  # same grain, genuinely conflicting value
    with pytest.raises(RuntimeError):
        eligible_facts(con, ["Assets"])


# ------------------------------------------------------------------------ determinism

def test_same_inputs_same_rows():
    con = _con()
    _insert_submission(con, adsh="A", period="20181231")
    _insert_submission(con, adsh="B", period="20181231")
    _insert_fact(con, adsh="B", ddate="20181231", value=1.0)
    _insert_fact(con, adsh="A", ddate="20181231", value=2.0)
    r1 = eligible_facts(con, ["Assets"])
    r2 = eligible_facts(con, ["Assets"])
    assert r1 == r2


def test_same_inputs_same_ordering():
    con = _con()
    _insert_submission(con, adsh="Z", period="20181231")
    _insert_submission(con, adsh="A", period="20181231")
    _insert_fact(con, adsh="Z", ddate="20181231", value=1.0)
    _insert_fact(con, adsh="A", ddate="20181231", value=2.0)
    facts = eligible_facts(con, ["Assets"])
    assert [f.adsh for f in facts] == ["A", "Z"]


def test_same_semantic_config_same_hash():
    h1 = compute_contract_config_hash(build_contract_config(["Assets", "Revenues"]))
    h2 = compute_contract_config_hash(build_contract_config(["Revenues", "Assets"]))
    assert h1 == h2  # order-independent (sorted internally)
    assert len(h1) == 64


def test_different_tag_selection_different_hash():
    h1 = compute_contract_config_hash(build_contract_config(["Assets"]))
    h2 = compute_contract_config_hash(build_contract_config(["Assets", "Revenues"]))
    assert h1 != h2


def test_build_contract_config_rejects_unknown_tag():
    with pytest.raises(TruthContractError):
        build_contract_config(["NotARealOrRegisteredTag"])


def test_build_contract_config_embeds_tag_registry_hash():
    from src.eval.tag_registry import compute_registry_hash
    config = build_contract_config(["Assets"])
    assert config["tag_registry_hash"] == compute_registry_hash(get_registry())
    assert config["tag_registry_version"] == get_registry().version


def test_empty_tag_list_returns_empty():
    con = _con()
    _baseline(con)
    assert eligible_facts(con, []) == []


# --------------------------------------------------------------------- security / mutation

def test_eligible_facts_performs_no_writes():
    con = _con()
    _baseline(con)
    before_facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
    before_subs = con.execute("SELECT count(*) FROM submissions").fetchone()[0]
    eligible_facts(con, ["Assets"])
    after_facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
    after_subs = con.execute("SELECT count(*) FROM submissions").fetchone()[0]
    assert before_facts == after_facts
    assert before_subs == after_subs


# =================================================================== real-data (local_data)

REAL_DB_PATH = "data/xbrl.duckdb"


@pytest.mark.local_data
def test_real_eligible_facts_full_registry():
    import os
    if not os.path.isfile(REAL_DB_PATH):
        pytest.skip(f"real XBRL database not present at {REAL_DB_PATH}")

    registry = get_registry()
    tags = registry.supported_tags()
    assert len(tags) == 15  # the full frozen Task 2.2 registry

    con = duckdb.connect(REAL_DB_PATH, read_only=True)
    try:
        facts = eligible_facts(con, tags)

        assert len(facts) > 0
        assert {f.tag for f in facts}.issubset(set(tags))

        for f in facts:
            spec = registry.get(f.tag)
            assert spec.qtrs == f.qtrs
            assert spec.unit == f.uom
            assert 2016 <= f.fiscal_year <= 2020
            assert f.adsh and f.cik and f.company
            assert f.value == f.value  # not NaN

        # Independently re-verify a sample of the exact returned rows directly
        # against the real table - never trust eligible_facts() to prove itself.
        import random
        random.seed(13)
        sample = random.sample(facts, min(30, len(facts)))
        for f in sample:
            spec = registry.get(f.tag)
            row = con.execute(
                "SELECT coreg, segments, version, uom, qtrs, value FROM facts "
                "WHERE adsh = ? AND tag = ? AND ddate = ? AND qtrs = ? AND uom = ? "
                "AND (coreg IS NULL OR coreg = '') AND (segments IS NULL OR segments = '')",
                [f.adsh, f.tag, f.ddate, f.qtrs, f.uom],
            ).fetchone()
            assert row is not None
            coreg, segments, version, uom, qtrs, value = row
            assert coreg is None or coreg == ""
            assert segments is None or segments == ""
            assert version.startswith("us-gaap/")
            assert uom == spec.unit
            assert qtrs == spec.qtrs
            assert value == f.value

        # all previously-unresolved tags are now actually present in the eligible set
        eligible_tags = {f.tag for f in facts}
        for tag in PREVIOUSLY_UNRESOLVED_TAGS:
            assert tag in eligible_tags

        # deterministic ordering: a second call returns identical rows in
        # identical order (never DuckDB's incidental physical row order)
        facts_again = eligible_facts(con, tags)
        assert facts == facts_again
        keys = [(f.adsh, f.tag, f.ddate, f.qtrs, f.uom) for f in facts]
        assert keys == sorted(keys)
    finally:
        con.close()
