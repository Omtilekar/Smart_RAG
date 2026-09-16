"""Task 4.8 - production context-guardrail boundary.

Answers exactly one deterministic question per request, after evidence
acquisition and before generation:

    Is the context that is about to be supplied to generation safe,
    well-formed, provenance-preserving, and acceptable under the frozen
    retrieval/routing contract?

Never re-answers "was the original user question acceptable" (Task
4.7's job, src.guards.input) or "is the generated answer safe" (a later
output-guardrail task) - see project_plan/PHASE4_CONTEXT_GUARDRAILS.md
for the full boundary separation.

Authoritative scope is `PROJECT_EXECUTION.md`'s Task 4.8 checklist
(materially narrower than an earlier elaborate draft prompt - reported,
not silently expanded):

    - Treat retrieved content as untrusted data.
    - Clearly delimit retrieved evidence.
    - Preserve raw evidence for provenance.
    - Plant adversarial/instruction-shaped retrieval examples.
    - Test that retrieved text cannot override system instructions.

This module implements the first three as deterministic checks/
formatting and the last two as test fixtures/assertions living in
tests/test_context_guards.py - "plant adversarial examples" and "test
retrieved text cannot override instructions" are testing activities, not
production guard logic, and are treated as such rather than invented
into a new runtime check with no roadmap basis.

No network call, no model inference, no randomness, no time-dependent
policy anywhere in this module - verified by a dedicated AST-based
static-safety test (tests/test_context_guards_static_safety.py). The
guard consumes already-retrieved evidence; it never fetches new evidence
or calls a retrieval/embedding/generation API itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.logging_utils import get_logger, log_event

log = get_logger(__name__)

REASON_CODES: tuple[str, ...] = ("missing_provenance",)

# The one, explicit, documented delimiter contract for "clearly delimit
# retrieved evidence" - deliberately NOT square brackets around the
# chunk_id label: Task 1.7a found the model imitating a "[chunk_id: X]"
# label shape as its own (wrong) citation format, and
# src/generation/minimal.py's SYSTEM_PROMPT instructs bare "[chunk_id]"
# citations - reusing "[...]" here would reintroduce exactly that
# regression. This exact marker text is verified (by test) never to
# appear in ordinary chunk content by coincidence.
EVIDENCE_BEGIN_MARKER = "<<<BEGIN_RETRIEVED_EVIDENCE"
EVIDENCE_END_MARKER = "<<<END_RETRIEVED_EVIDENCE>>>"


@dataclass(frozen=True)
class ContextGuardDecision:
    allowed: bool
    reason_code: str | None
    detail: str | None


def _decision(allowed: bool, reason_code: str | None, detail: str | None, *, route: str,
              context_items: int) -> ContextGuardDecision:
    decision = ContextGuardDecision(allowed=allowed, reason_code=reason_code, detail=detail)
    log_event(
        log, logging.INFO, "context_guard_decision",
        allowed=decision.allowed, reason_code=decision.reason_code, route=route, context_items=context_items,
    )
    return decision


# --------------------------------------------------------------- dense retrieval

def check_dense_context(results) -> ContextGuardDecision:
    """`results` is a list of `src.retrieval.baseline.RetrievalResult` (or
    anything duck-typed the same way). Requires every result to carry a
    non-empty `chunk_id`, `document_id`, and `text` - the three fields
    the existing citation contract (`src.generation.citations`) and
    provenance display (`src.generation.minimal._format_context`)
    already depend on. Never fabricates a missing field; rejects
    instead."""
    for r in results:
        if not r.chunk_id or not r.document_id or not r.text:
            return _decision(
                False, "missing_provenance",
                f"dense retrieval result missing required provenance field "
                f"(chunk_id={bool(r.chunk_id)}, document_id={bool(r.document_id)}, text={bool(r.text)})",
                route="dense", context_items=len(results),
            )
    return _decision(True, None, None, route="dense", context_items=len(results))


# --------------------------------------------------------------- structured XBRL

def check_xbrl_context(result) -> ContextGuardDecision:
    """`result` is a `src.sql.xbrl_lookup.XbrlLookupResult`. Only a
    `outcome="found"` result carries real evidence to guard - the other
    three outcomes (`not_found`/`ambiguous`/`unsupported_tag`) carry no
    fact at all, so there is nothing for a context guard to reject
    (this is not an empty-context/abstention policy decision, which is
    out of this task's authoritative scope - see module docstring)."""
    if result.outcome != "found":
        return _decision(True, None, None, route="xbrl", context_items=0)
    required = (result.adsh, result.cik, result.fiscal_year, result.tag, result.unit)
    if any(v is None or v == "" for v in required) or result.value is None:
        return _decision(
            False, "missing_provenance",
            "xbrl_fact result outcome=found but missing a required provenance field "
            "(adsh/cik/fiscal_year/tag/unit/value)",
            route="xbrl", context_items=1,
        )
    return _decision(True, None, None, route="xbrl", context_items=1)


# --------------------------------------------------------------- tree navigation

def check_navigation_context(result) -> ContextGuardDecision:
    """`result` is a `src.nav.section_navigation.SectionNavigationResult`.
    Only `outcome="found"` carries real evidence to guard, same rationale
    as check_xbrl_context()."""
    if result.outcome != "found":
        return _decision(True, None, None, route="navigation", context_items=0)
    if not result.document_id or not result.item or not result.node_texts:
        return _decision(
            False, "missing_provenance",
            "section_navigation result outcome=found but missing a required provenance field "
            "(document_id/item/node_texts)",
            route="navigation", context_items=0,
        )
    return _decision(True, None, None, route="navigation", context_items=len(result.node_texts))


# --------------------------------------------------------------- evidence delimiting

def format_evidence_block(*, chunk_id: str, company: str, fiscal_year, document_id: str, text: str) -> str:
    """"Clearly delimit retrieved evidence" (PROJECT_EXECUTION.md's Task
    4.8 checklist, item 2). Wraps one piece of untrusted retrieved text
    in explicit, machine-unambiguous boundary markers, so downstream
    processing (and a human reading the raw prompt) can always tell
    exactly where retrieved content starts and ends - even if the
    retrieved `text` itself contains phrases shaped like instructions,
    markers, or a fake second evidence block. The evidence's own content
    is never altered, reordered, or truncated here - only wrapped.

    Deliberately reuses the existing "Chunk ID: ...\\nCompany: ... |
    Fiscal Year: ... | Document: ..." provenance line verbatim (Task 1.7/
    1.7a's own frozen label form - `[chunk_id: X]` was already tried and
    found to cause the model to imitate that bracketed shape as its own
    citation, Task 1.7a's documented finding) - this function only adds
    an outer boundary, it does not redesign the provenance line itself.
    """
    return (
        f"{EVIDENCE_BEGIN_MARKER} chunk_id={chunk_id!r}>>>\n"
        f"Chunk ID: {chunk_id}\n"
        f"Company: {company} | Fiscal Year: {fiscal_year} | Document: {document_id}\n"
        f"{text}\n"
        f"{EVIDENCE_END_MARKER}"
    )


__all__ = [
    "ContextGuardDecision", "REASON_CODES",
    "EVIDENCE_BEGIN_MARKER", "EVIDENCE_END_MARKER",
    "check_dense_context", "check_xbrl_context", "check_navigation_context",
    "format_evidence_block",
]
