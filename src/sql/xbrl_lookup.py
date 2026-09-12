"""Task 3.10 - structured XBRL SQL path for `xbrl_fact`-routed questions:

    question -> [Task 3.8 router] -> (cik, fiscal_year, tag) -> [this module] -> value + unit + filing provenance

Reuses Task 2.1/2.2's frozen `src.eval.truth_contract.eligible_facts()`
UNMODIFIED as the production fact selector - never a second,
independently-decided qtrs/unit/eligibility rule. A tag outside the
frozen `configs/eval_tags.yaml` registry (an "unsupported numeric
narrative" concept, in PROJECT_EXECUTION.md's own Task 3.10 wording)
always resolves to `outcome="unsupported_tag"` here - it is never
silently answered, matching the frozen registry's own refusal
semantics used throughout Task 2.1-2.2.

Read-only against `data/xbrl.duckdb` - this module never writes.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.truth_contract import EligibleFact, TruthContractError, eligible_facts

OUTCOMES: tuple[str, ...] = ("found", "not_found", "ambiguous", "unsupported_tag")


@dataclass(frozen=True)
class XbrlLookupResult:
    outcome: str
    cik: int
    fiscal_year: int
    tag: str
    value: float | None = None
    unit: str | None = None
    adsh: str | None = None
    company: str | None = None
    candidate_count: int = 0


class XbrlFactIndex:
    """Eagerly builds a `(tag, cik, fiscal_year) -> [EligibleFact]` index
    from `eligible_facts()` for a fixed set of tags - one query per tag,
    never one query per question. `con` is an already-open, read-only
    DuckDB connection against `data/xbrl.duckdb`."""

    def __init__(self, con, tags):
        self._by_key: dict[tuple[str, int, int], list[EligibleFact]] = {}
        self._unsupported_tags: set[str] = set()
        for tag in tags:
            try:
                facts = eligible_facts(con, [tag])
            except TruthContractError:
                self._unsupported_tags.add(tag)
                continue
            for fact in facts:
                self._by_key.setdefault((fact.tag, fact.cik, fact.fiscal_year), []).append(fact)

    def lookup(self, *, cik: int, fiscal_year: int, tag: str) -> XbrlLookupResult:
        if tag in self._unsupported_tags:
            return XbrlLookupResult(outcome="unsupported_tag", cik=cik, fiscal_year=fiscal_year, tag=tag)

        matches = self._by_key.get((tag, cik, fiscal_year), [])
        if not matches:
            return XbrlLookupResult(outcome="not_found", cik=cik, fiscal_year=fiscal_year, tag=tag)

        distinct_values = {m.value for m in matches}
        if len(distinct_values) > 1:
            # Multiple eligible filings disagree on this fact (a genuine
            # cross-filing value revision - see truth_contract.py's own
            # terminology note) - never silently pick one.
            return XbrlLookupResult(outcome="ambiguous", cik=cik, fiscal_year=fiscal_year, tag=tag,
                                     candidate_count=len(matches))

        m = matches[0]
        return XbrlLookupResult(
            outcome="found", cik=cik, fiscal_year=fiscal_year, tag=tag,
            value=m.value, unit=m.uom, adsh=m.adsh, company=m.company, candidate_count=len(matches),
        )


__all__ = ["OUTCOMES", "XbrlLookupResult", "XbrlFactIndex"]
