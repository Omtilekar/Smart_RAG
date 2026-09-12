"""Task 3.11 - deterministic derived calculations built on top of Task
3.10's structured XBRL fact lookup. Frozen project principle (
PROJECT_EXECUTION.md Task 3.11): "Retrieve facts with models/rules;
calculate facts with deterministic code." Every operand is fetched via
Task 3.10's `src.sql.xbrl_lookup.XbrlFactIndex` (itself built on Task
2.1/2.2's frozen truth contract) - this module performs arithmetic on
already-eligible facts only, never a second fact-eligibility rule.

Scope (verified against the real DEV corpus before implementation):
PROJECT_EXECUTION.md's Task 3.11 examples list "growth" and "percentage
of revenue" alongside "difference between years" and "cross-company
comparisons" - but the entire 1,932-question DEV corpus has exactly two
`operation` values (`difference`: 244 questions, `greater_than`: 105
questions) and zero examples of a growth-rate or percentage-of-revenue
calculation anywhere. Implemented: `difference` (year-over-year) and
`greater_than` (cross-company comparison) - the two operations with
real DEV ground truth. Growth/percentage-of-revenue are designed-but-
unevaluated pending new eval data, the same documented scope pattern
already established for Task 3.8's router intents.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.sql.xbrl_lookup import XbrlFactIndex, XbrlLookupResult

OPERATIONS: tuple[str, ...] = ("difference", "greater_than")


@dataclass(frozen=True)
class DerivedResult:
    outcome: str  # "computed" | "operand_a_unavailable" | "operand_b_unavailable" | "tie"
    operation: str
    operand_a: XbrlLookupResult
    operand_b: XbrlLookupResult
    value: float | None = None          # difference only: operand_b.value - operand_a.value
    winner_cik: int | None = None       # greater_than only
    winner_company: str | None = None   # greater_than only


def compute_difference(index: XbrlFactIndex, *, cik: int, tag: str,
                        fiscal_year_a: int, fiscal_year_b: int) -> DerivedResult:
    """`fiscal_year_a` is the earlier ("from") year, `fiscal_year_b` the
    later ("to") year - the caller (see `src.router.rules.extract_fiscal_years`,
    which preserves the order years appear in the question's own text)
    is responsible for that ordering; this function only subtracts.
    `value = fact_b.value - fact_a.value` (verified against real DEV
    ground truth: "change from fiscal year 2019 to fiscal year 2020" ->
    `expected_numeric_answer = value_2020 - value_2019`)."""
    operand_a = index.lookup(cik=cik, fiscal_year=fiscal_year_a, tag=tag)
    operand_b = index.lookup(cik=cik, fiscal_year=fiscal_year_b, tag=tag)
    if operand_a.outcome != "found":
        return DerivedResult(outcome="operand_a_unavailable", operation="difference",
                              operand_a=operand_a, operand_b=operand_b)
    if operand_b.outcome != "found":
        return DerivedResult(outcome="operand_b_unavailable", operation="difference",
                              operand_a=operand_a, operand_b=operand_b)
    return DerivedResult(outcome="computed", operation="difference", operand_a=operand_a,
                          operand_b=operand_b, value=operand_b.value - operand_a.value)


def compute_greater_than(index: XbrlFactIndex, *, cik_a: int, cik_b: int, tag: str,
                          fiscal_year: int) -> DerivedResult:
    """Compares the same tag/fiscal_year fact across two companies.
    Operand order does not affect correctness - the winner is whichever
    fetched fact has the larger value, by company name/CIK, never by
    which operand happened to be labeled "a" or "b" in the question text."""
    operand_a = index.lookup(cik=cik_a, fiscal_year=fiscal_year, tag=tag)
    operand_b = index.lookup(cik=cik_b, fiscal_year=fiscal_year, tag=tag)
    if operand_a.outcome != "found":
        return DerivedResult(outcome="operand_a_unavailable", operation="greater_than",
                              operand_a=operand_a, operand_b=operand_b)
    if operand_b.outcome != "found":
        return DerivedResult(outcome="operand_b_unavailable", operation="greater_than",
                              operand_a=operand_a, operand_b=operand_b)
    if operand_a.value == operand_b.value:
        return DerivedResult(outcome="tie", operation="greater_than", operand_a=operand_a, operand_b=operand_b)
    winner = operand_a if operand_a.value > operand_b.value else operand_b
    return DerivedResult(outcome="computed", operation="greater_than", operand_a=operand_a, operand_b=operand_b,
                          winner_cik=winner.cik, winner_company=winner.company)


__all__ = ["OPERATIONS", "DerivedResult", "compute_difference", "compute_greater_than"]
