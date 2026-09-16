"""Task 4.10 - thin orchestration facade composing already-existing,
already-frozen pipeline components. Owns zero business logic of its
own: no retrieval, no routing heuristics, no SQL fact selection, no
generation, no citation parsing, no guardrail logic is implemented
here - all of that is imported and called exactly as Tasks 1.6-4.9 froze
it ("Keep retrieval/generation logic outside FastAPI" -
PROJECT_EXECUTION.md's own Task 4.10 bullet).

Route coverage (documented, not overclaimed - same honest-scoping
precedent as Tasks 4.8/4.9): this task's own "Frozen Production Stack"
section names exactly two routes for API exposure - "structured SQL/
XBRL route" and "tree-navigation route." Tree-navigation has no live
question -> routing decision anywhere in this codebase (`classify_intent()`'s
own 6-intent taxonomy has no navigation intent; `extract_item_reference()`
was never wired into it) - wiring one now would mean inventing new
routing logic, explicitly forbidden ("do NOT reopen ... routing ...
decisions"). So only two routes are wired here:

    1. structured_xbrl - `classify_intent()` -> `XbrlFactIndex.lookup()`,
       for the `xbrl_fact` intent only (the single-fact-lookup shape
       Task 3.10 built and evaluated). `numeric_derived`/`cross_entity`
       intents have a real, precedented text->answer composition
       pattern too (see `scripts/run_phase3_derived.py`), but were
       deliberately not wired here to keep this task's scope
       proportionate to its own 3-bullet checklist and to the "Frozen
       Production Stack" section's own naming (only "structured SQL/
       XBRL route" is named, not "derived calculations" or "cross-
       entity comparison") - documented as a real, available future
       enhancement, not a gap discovered by accident.
    2. dense - `classify_intent()` intent anything else (including
       `out_of_scope`/`unanswerable`/`advice`, and a `xbrl_fact` lookup
       that didn't resolve to `outcome="found"`) falls back to
       `MinimalGenerator.answer()` - the same dense retrieval+generation
       path Task 1.6/1.7 established, already carrying Task 4.8/4.9's
       context/output guards internally.

Guard-rejection status: only Task 4.7's input guard (run directly here,
before routing) produces `status="rejected"`. A context/output-guard-
triggered abstention inside the dense route is NOT re-labeled
"rejected" - `MinimalGenerator.answer()`'s frozen public contract already
represents that as an ordinary `GenerationResult` (an abstention-shaped
answer with empty citations), and this facade does not reach into its
non-public `_answer_with_diagnostics()` to invent a second exposure of
internal guard mechanics ("do not add new guard behavior merely because
an HTTP API now exists").
"""

from __future__ import annotations

from dataclasses import dataclass

from src.guards.input import check_input
from src.guards.output import check_structured_numeric_output
from src.router.rules import CompanyGazetteer, classify_intent
from src.sql.xbrl_lookup import XbrlFactIndex

ROUTE_DENSE = "dense"
ROUTE_STRUCTURED_XBRL = "structured_xbrl"


@dataclass(frozen=True)
class QueryOutcome:
    status: str  # "answered" | "rejected"
    answer: str | None
    citations: list[str]
    route: str | None
    reason_code: str | None


def _resolved_single_cik_and_year(decision) -> tuple[int, int] | None:
    ciks = set(decision.resolved_ciks)
    years = set(decision.fiscal_years)
    if len(ciks) == 1 and len(years) == 1:
        return next(iter(ciks)), next(iter(years))
    return None


def _try_structured_xbrl_route(question: str, *, gazetteer: CompanyGazetteer, registry,
                                xbrl_index: XbrlFactIndex) -> QueryOutcome | None:
    """Returns a QueryOutcome if the structured route fully resolved and
    passed its provenance guard; None if the caller should fall back to
    the dense route (incomplete routing signal, fact not found/ambiguous/
    unsupported, or - defensively - a provenance-guard rejection, which
    is never expected with real eligible facts per Task 2.1/2.2's truth
    contract, but is never silently trusted either)."""
    decision = classify_intent(question, gazetteer=gazetteer, registry=registry)
    if decision.intent != "xbrl_fact" or decision.concept is None:
        return None
    resolved = _resolved_single_cik_and_year(decision)
    if resolved is None:
        return None
    cik, fiscal_year = resolved

    result = xbrl_index.lookup(cik=cik, fiscal_year=fiscal_year, tag=decision.concept)
    if result.outcome != "found":
        return None

    guard = check_structured_numeric_output(result)
    if not guard.allowed:
        return None

    answer = (
        f"{decision.concept} for {result.company} (CIK {result.cik}), "
        f"fiscal year {result.fiscal_year}: {result.value} {result.unit}."
    )
    return QueryOutcome(
        status="answered", answer=answer, citations=[result.adsh],
        route=ROUTE_STRUCTURED_XBRL, reason_code=None,
    )


def handle_query(question, *, max_length: int, generator, gazetteer: CompanyGazetteer,
                  registry, xbrl_index: XbrlFactIndex) -> QueryOutcome:
    """The one live entry point composing Task 4.7's input guard, Task
    3.8's router, Task 3.10's structured lookup, and Task 1.7/4.8/4.9's
    dense generation pipeline (context/output guards already inside
    `generator.answer()`). Never calls a provider/model/network itself -
    everything expensive is deferred to the already-existing components
    passed in."""
    guard_decision = check_input(question, max_length=max_length)
    if not guard_decision.allowed:
        return QueryOutcome(
            status="rejected", answer=None, citations=[], route=None,
            reason_code=guard_decision.reason_code,
        )

    structured_outcome = _try_structured_xbrl_route(
        question, gazetteer=gazetteer, registry=registry, xbrl_index=xbrl_index,
    )
    if structured_outcome is not None:
        return structured_outcome

    result = generator.answer(question)
    return QueryOutcome(
        status="answered", answer=result.answer, citations=list(result.citations),
        route=ROUTE_DENSE, reason_code=None,
    )


__all__ = ["QueryOutcome", "ROUTE_DENSE", "ROUTE_STRUCTURED_XBRL", "handle_query"]
