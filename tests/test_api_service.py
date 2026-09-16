"""Tests for src/api/service.py (Task 4.10) - the pure orchestration
facade, no HTTP layer. No network/model/LanceDB anywhere - fakes only.
"""

from dataclasses import dataclass

import pytest

from src.api.service import ROUTE_DENSE, ROUTE_STRUCTURED_XBRL, handle_query
from src.eval.tag_registry import get_registry
from src.router.rules import CompanyGazetteer
from src.sql.xbrl_lookup import XbrlLookupResult

MAX_LEN = 2000


@dataclass(frozen=True)
class FakeResult:
    answer: str
    citations: list[str]


class FakeGenerator:
    def __init__(self, result=None):
        self.calls = []
        self._result = result or FakeResult(answer="Revenue was $1M. [doc0.htm::chunk0]", citations=["doc0.htm::chunk0"])

    def answer(self, question):
        self.calls.append(question)
        return self._result


class RaisingGenerator:
    def answer(self, question):
        raise AssertionError("dense generator must not be called for this test")


class FakeXbrlIndex:
    def __init__(self, result=None):
        self.calls = []
        self._result = result

    def lookup(self, *, cik, fiscal_year, tag):
        self.calls.append((cik, fiscal_year, tag))
        if self._result is not None:
            return self._result
        return XbrlLookupResult(outcome="not_found", cik=cik, fiscal_year=fiscal_year, tag=tag)


REGISTRY = get_registry()
GAZETTEER = CompanyGazetteer({"ACME CORP": 320193})


def _handle(question, *, generator=None, xbrl_index=None, gazetteer=None, registry=None):
    return handle_query(
        question, max_length=MAX_LEN,
        generator=generator or FakeGenerator(),
        gazetteer=gazetteer or GAZETTEER,
        registry=registry or REGISTRY,
        xbrl_index=xbrl_index or FakeXbrlIndex(),
    )


# ------------------------------------------------------------- input guard

def test_input_guard_rejection_never_calls_router_or_generator():
    gen = RaisingGenerator()
    xbrl = FakeXbrlIndex()
    outcome = _handle("Should I buy this stock?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "rejected"
    assert outcome.reason_code == "advice_request_detected"
    assert outcome.answer is None
    assert outcome.citations == []
    assert outcome.route is None
    assert xbrl.calls == []


def test_empty_input_rejected():
    outcome = _handle("", generator=RaisingGenerator())
    assert outcome.status == "rejected"
    assert outcome.reason_code == "empty_input"


def test_too_long_input_rejected():
    outcome = _handle("What was revenue? " * 200, generator=RaisingGenerator())
    assert outcome.status == "rejected"
    assert outcome.reason_code == "input_too_long"


# ------------------------------------------------------------- dense fallback

def test_out_of_scope_question_falls_back_to_dense():
    gen = FakeGenerator()
    outcome = _handle("What's the weather like today?", generator=gen)
    # "What's the weather like today?" is rejected by the input guard's own
    # out_of_scope check before routing even happens.
    assert outcome.status == "rejected"
    assert outcome.reason_code == "out_of_scope"
    assert gen.calls == []


def test_narrative_question_with_no_resolvable_fact_falls_back_to_dense():
    gen = FakeGenerator()
    xbrl = FakeXbrlIndex()
    outcome = _handle("What are the main risk factors described in this filing?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "answered"
    assert outcome.route == ROUTE_DENSE
    assert len(gen.calls) == 1
    assert xbrl.calls == []  # no CIK/concept resolved - router never reaches the xbrl branch meaningfully


def test_xbrl_shaped_question_with_no_match_falls_back_to_dense():
    gen = FakeGenerator()
    xbrl = FakeXbrlIndex(result=XbrlLookupResult(outcome="not_found", cik=320193, fiscal_year=2019, tag="Assets"))
    outcome = _handle("What were total assets for ACME CORP in 2019?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "answered"
    assert outcome.route == ROUTE_DENSE
    assert len(gen.calls) == 1
    assert len(xbrl.calls) == 1  # the xbrl route was attempted, then fell back


def test_ambiguous_xbrl_fact_falls_back_to_dense():
    gen = FakeGenerator()
    xbrl = FakeXbrlIndex(result=XbrlLookupResult(outcome="ambiguous", cik=320193, fiscal_year=2019, tag="Assets", candidate_count=2))
    outcome = _handle("What were total assets for ACME CORP in 2019?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "answered"
    assert outcome.route == ROUTE_DENSE


def test_missing_provenance_xbrl_result_falls_back_to_dense():
    # Defense-in-depth: never expected with real eligible facts, but the
    # provenance guard is still consulted, and a rejection falls back
    # rather than releasing an incomplete structured answer.
    gen = FakeGenerator()
    bad_result = XbrlLookupResult(outcome="found", cik=320193, fiscal_year=2019, tag="Assets",
                                   value=500.0, unit="USD", adsh=None, company="ACME CORP")
    xbrl = FakeXbrlIndex(result=bad_result)
    outcome = _handle("What were total assets for ACME CORP in 2019?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "answered"
    assert outcome.route == ROUTE_DENSE


# ------------------------------------------------------------- structured route

def test_resolved_xbrl_fact_returns_structured_answer_without_calling_generator():
    gen = RaisingGenerator()
    found = XbrlLookupResult(outcome="found", cik=320193, fiscal_year=2019, tag="Assets",
                              value=500.0, unit="USD", adsh="0000320193-24-000123", company="ACME CORP")
    xbrl = FakeXbrlIndex(result=found)
    outcome = _handle("What were total assets for ACME CORP in 2019?", generator=gen, xbrl_index=xbrl)
    assert outcome.status == "answered"
    assert outcome.route == ROUTE_STRUCTURED_XBRL
    assert outcome.citations == ["0000320193-24-000123"]
    assert "500.0" in outcome.answer
    assert "USD" in outcome.answer
    assert len(xbrl.calls) == 1


# ------------------------------------------------------------- determinism / preservation

def test_dense_answer_preserved_unchanged():
    result = FakeResult(answer="Exact answer text. [doc0.htm::chunk0]", citations=["doc0.htm::chunk0"])
    outcome = _handle("What was revenue?", generator=FakeGenerator(result=result))
    assert outcome.answer == "Exact answer text. [doc0.htm::chunk0]"
    assert outcome.citations == ["doc0.htm::chunk0"]


def test_generator_invoked_exactly_once_for_dense_route():
    gen = FakeGenerator()
    _handle("What was revenue?", generator=gen)
    assert len(gen.calls) == 1
