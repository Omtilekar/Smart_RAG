"""Task 3.11 - portable, pure-logic tests for src.sql.derived. Fake
XbrlFactIndex-like objects - no real DuckDB, no model, no network."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.sql.derived import compute_difference, compute_greater_than
from src.sql.xbrl_lookup import XbrlLookupResult


@dataclass
class _FakeIndex:
    facts: dict  # (cik, fiscal_year, tag) -> XbrlLookupResult

    def lookup(self, *, cik, fiscal_year, tag):
        key = (cik, fiscal_year, tag)
        if key in self.facts:
            return self.facts[key]
        return XbrlLookupResult(outcome="not_found", cik=cik, fiscal_year=fiscal_year, tag=tag)


def _found(cik, fiscal_year, tag, value, company="C", unit="USD"):
    return XbrlLookupResult(outcome="found", cik=cik, fiscal_year=fiscal_year, tag=tag,
                             value=value, unit=unit, adsh="a", company=company)


# --------------------------------------------------------------- compute_difference

def test_difference_hand_calculation():
    index = _FakeIndex({
        (1, 2019, "Assets"): _found(1, 2019, "Assets", 4919642000.0),
        (1, 2020, "Assets"): _found(1, 2020, "Assets", 5314677000.0),
    })
    result = compute_difference(index, cik=1, tag="Assets", fiscal_year_a=2019, fiscal_year_b=2020)
    assert result.outcome == "computed"
    assert result.value == pytest.approx(395035000.0)


def test_difference_operand_a_missing():
    index = _FakeIndex({(1, 2020, "Assets"): _found(1, 2020, "Assets", 100.0)})
    result = compute_difference(index, cik=1, tag="Assets", fiscal_year_a=2019, fiscal_year_b=2020)
    assert result.outcome == "operand_a_unavailable"
    assert result.value is None


def test_difference_operand_b_missing():
    index = _FakeIndex({(1, 2019, "Assets"): _found(1, 2019, "Assets", 100.0)})
    result = compute_difference(index, cik=1, tag="Assets", fiscal_year_a=2019, fiscal_year_b=2020)
    assert result.outcome == "operand_b_unavailable"


def test_difference_negative_change():
    index = _FakeIndex({
        (1, 2019, "Assets"): _found(1, 2019, "Assets", 200.0),
        (1, 2020, "Assets"): _found(1, 2020, "Assets", 150.0),
    })
    result = compute_difference(index, cik=1, tag="Assets", fiscal_year_a=2019, fiscal_year_b=2020)
    assert result.value == pytest.approx(-50.0)


def test_difference_unsupported_tag_propagates():
    index = _FakeIndex({
        (1, 2019, "Foo"): XbrlLookupResult(outcome="unsupported_tag", cik=1, fiscal_year=2019, tag="Foo"),
        (1, 2020, "Foo"): XbrlLookupResult(outcome="unsupported_tag", cik=1, fiscal_year=2020, tag="Foo"),
    })
    result = compute_difference(index, cik=1, tag="Foo", fiscal_year_a=2019, fiscal_year_b=2020)
    assert result.outcome == "operand_a_unavailable"


# --------------------------------------------------------------- compute_greater_than

def test_greater_than_hand_calculation():
    index = _FakeIndex({
        (1, 2016, "Assets"): _found(1, 2016, "Assets", 12738062000.0, company="HILLTOP HOLDINGS INC."),
        (2, 2016, "Assets"): _found(2, 2016, "Assets", 6734632.0, company="INRAD OPTICS, INC."),
    })
    result = compute_greater_than(index, cik_a=1, cik_b=2, tag="Assets", fiscal_year=2016)
    assert result.outcome == "computed"
    assert result.winner_cik == 1
    assert result.winner_company == "HILLTOP HOLDINGS INC."


def test_greater_than_order_independent():
    index = _FakeIndex({
        (1, 2016, "Assets"): _found(1, 2016, "Assets", 100.0, company="A"),
        (2, 2016, "Assets"): _found(2, 2016, "Assets", 200.0, company="B"),
    })
    r1 = compute_greater_than(index, cik_a=1, cik_b=2, tag="Assets", fiscal_year=2016)
    r2 = compute_greater_than(index, cik_a=2, cik_b=1, tag="Assets", fiscal_year=2016)
    assert r1.winner_cik == r2.winner_cik == 2


def test_greater_than_tie():
    index = _FakeIndex({
        (1, 2016, "Assets"): _found(1, 2016, "Assets", 100.0, company="A"),
        (2, 2016, "Assets"): _found(2, 2016, "Assets", 100.0, company="B"),
    })
    result = compute_greater_than(index, cik_a=1, cik_b=2, tag="Assets", fiscal_year=2016)
    assert result.outcome == "tie"
    assert result.winner_cik is None


def test_greater_than_operand_missing():
    index = _FakeIndex({(1, 2016, "Assets"): _found(1, 2016, "Assets", 100.0)})
    result = compute_greater_than(index, cik_a=1, cik_b=2, tag="Assets", fiscal_year=2016)
    assert result.outcome == "operand_b_unavailable"
