"""Task 4.9 - production output-guardrail boundary.

Answers exactly one deterministic question per request, after a
provider response exists but before it is released publicly:

    Can this generated answer be released to the user under the
    project's frozen output contract?

Never re-answers "was the input acceptable" (Task 4.7, src.guards.input)
or "was retrieved context structurally safe/provenance-complete" (Task
4.8, src.guards.context) - see project_plan/PHASE4_OUTPUT_GUARDRAILS.md
for the full boundary separation.

Authoritative scope is PROJECT_EXECUTION.md's Task 4.9 checklist (6
items):

    - Verify cited chunk IDs exist.
    - Verify citations refer to provided evidence.
    - Add groundedness checks.
    - Validate numeric provenance for structured answers.
    - Refuse unsupported financial advice.
    - Avoid unsupported claims.

Documented item collapsing (not silently done):

    - Items 1+2 collapse into ONE check: every citation must be among
      the chunk_ids actually SUPPLIED to this generation call - never
      validated against "exists somewhere in the global corpus" (this
      project's own explicit precedent: "the relevant set is the
      evidence supplied to the answer," see
      project_plan/PHASE4_CONTEXT_GUARDRAILS.md and Task 1.8's own
      citation-integrity design).
    - Items 3+6 ("groundedness"/"avoid unsupported claims") reduce to
      the same citation-validity check for whatever citations ARE
      present. A ZERO-citation answer is never blocked for "missing
      citation" - the project's frozen abstention semantics take
      precedence (do not require a citation for a legitimate abstention
      unless the roadmap explicitly says otherwise - it does not), and
      there is no deterministic, non-LLM way to distinguish a
      legitimate abstention from a hallucinated uncited claim using the
      answer text alone (introducing one would mean either an LLM judge
      or an invented heuristic threshold, both explicitly out of scope).
    - Item 4 ("numeric provenance for structured answers") is satisfied
      by re-exporting Task 4.8's `check_xbrl_context()` UNCHANGED -
      Task 4.8 already established the structured/XBRL route has no
      generation-prompt orchestrator, so there is no separate
      "generation step" between context and output for that route; the
      same provenance check already IS the release gate.
    - Item 5 reuses `src.router.rules.ADVICE_KEYWORDS` (Task 3.8/4.7's
      frozen list) against the generated answer text - never a new,
      independently-decided keyword set.

Failure policy: ANY citation problem (unknown citation, malformed
citation marker) fails the WHOLE answer - never a partial strip-and-
keep. This reuses `src.eval.citation_integrity.evaluate_citation_
integrity`'s own established "PASS iff zero failure reasons" precedent
(Task 1.8), applied here as a live release gate instead of an offline
evaluation, rather than inventing a new redact-vs-reject policy.

No network call, no model inference, no LLM judge, no randomness, no
time-dependent policy anywhere in this module - verified by a dedicated
AST-based static-safety test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.eval.citation_integrity import detect_citation_attempts
from src.guards.context import check_xbrl_context
from src.logging_utils import get_logger, log_event
from src.router.rules import ADVICE_KEYWORDS

log = get_logger(__name__)

REASON_CODES: tuple[str, ...] = ("malformed_citation", "unknown_citation", "unsupported_advice")

# Task 4.9's structured-route check is Task 4.8's check_xbrl_context(),
# re-exported verbatim under the name PROJECT_EXECUTION.md's own
# checklist item uses ("validate numeric provenance for structured
# answers") - never a second implementation. Reuses "missing_provenance"
# from src.guards.context.REASON_CODES, not a new reason code.
check_structured_numeric_output = check_xbrl_context


@dataclass(frozen=True)
class OutputGuardDecision:
    allowed: bool
    reason_code: str | None
    detail: str | None


def _decision(allowed: bool, reason_code: str | None, detail: str | None, *,
              citation_count: int, unknown_citation_count: int) -> OutputGuardDecision:
    decision = OutputGuardDecision(allowed=allowed, reason_code=reason_code, detail=detail)
    log_event(
        log, logging.INFO, "output_guard_decision",
        allowed=decision.allowed, reason_code=decision.reason_code,
        citation_count=citation_count, unknown_citation_count=unknown_citation_count,
    )
    return decision


def check_dense_output(answer_text: str, citations: list[str], *, supplied_chunk_ids) -> OutputGuardDecision:
    """`answer_text` is the raw candidate text from `ProviderResponse.text`;
    `citations` is `src.generation.citations.parse_citations(answer_text)`
    (the frozen Task 1.7 parser - never re-derived here); `supplied_chunk_ids`
    is the set of `chunk_id`s actually retrieved and supplied to this
    specific generation call (never the whole corpus/index)."""
    attempts = detect_citation_attempts(answer_text)
    malformed = [a for a in attempts if not a.strict_valid]
    if malformed:
        return _decision(
            False, "malformed_citation",
            f"answer contains {len(malformed)} malformed citation marker(s) "
            f"(e.g. fullwidth brackets or a truncated/repaired-looking chunk id)",
            citation_count=len(citations), unknown_citation_count=0,
        )

    unknown = [c for c in citations if c not in supplied_chunk_ids]
    if unknown:
        return _decision(
            False, "unknown_citation",
            f"answer cites {len(unknown)} chunk_id(s) not present in the evidence "
            f"supplied to this generation call",
            citation_count=len(citations), unknown_citation_count=len(unknown),
        )

    if any(kw in answer_text.lower() for kw in ADVICE_KEYWORDS):
        return _decision(
            False, "unsupported_advice",
            "answer contains personalized financial/investment advice language",
            citation_count=len(citations), unknown_citation_count=0,
        )

    return _decision(True, None, None, citation_count=len(citations), unknown_citation_count=0)


__all__ = [
    "OutputGuardDecision", "REASON_CODES",
    "check_dense_output", "check_structured_numeric_output",
]
