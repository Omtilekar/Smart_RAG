"""Task 4.7 - production input-guardrail boundary.

Answers exactly one deterministic question per request, before any
routing/retrieval/generation work begins:

    Can this user input enter the RAG pipeline?

Never answers "is the retrieved context safe" (Task 4.8) or "is the
generated answer safe" (Task 4.9) - those are separate, later guardrail
layers with separate modules, by design (see
project_plan/PHASE4_INPUT_GUARDRAILS.md).

`PROJECT_EXECUTION.md`'s Task 4.7 checklist ("Add: request length
limits, scope enforcement, advice detection/refusal, PII checks
appropriate to the SEC use case, injection-pattern handling, rate
limiting strategy") is the authoritative scope - materially broader than
an earlier draft prompt that only mentioned generic structural
validation and optional injection detection. All six items are
addressed here except rate limiting, which `PROJECT_SPEC.md`'s own
"## 8. Guardrails" table assigns to infrastructure ("Rate limiting |
API Gateway"), not application code - see RATE_LIMITING_STRATEGY below
and the project doc for the full explanation of that decision (a
2026-09-16 explicit user decision, not invented silently).

No network call, no model inference, no randomness, no time-dependent
policy anywhere in this module - verified by a dedicated AST-based
static-safety test (tests/test_input_guards_static_safety.py).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from src.logging_utils import get_logger, log_event
from src.router.rules import ADVICE_KEYWORDS, INJECTION_KEYWORDS, extract_fiscal_years, extract_form_type

log = get_logger(__name__)

# PROJECT_SPEC.md assigns rate limiting to infrastructure ("API Gateway"),
# not this application-layer guard module - Task 4.7 does not build the
# FastAPI/serving layer (explicit non-goal), so there is no request
# boundary yet for an in-process limiter to sit behind. This constant
# documents the decision for a future Task 4.10 integrator; no
# rate-limit reason code exists below because no check implements one.
RATE_LIMITING_STRATEGY = "delegated_to_api_gateway"

REASON_CODES: tuple[str, ...] = (
    "invalid_type",
    "empty_input",
    "input_too_long",
    "disallowed_control_character",
    "prompt_injection_detected",
    "advice_request_detected",
    "pii_detected",
    "out_of_scope",
)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason_code: str | None
    detail: str | None


class GuardConfigError(ValueError):
    """Raised for an invalid guard configuration (e.g. a non-positive
    max_length) - distinct from an ordinary input rejection (GuardDecision)
    and from an unexpected internal bug (propagates normally)."""


# --------------------------------------------------------------- structural

# Unicode category "Cc" (control) covers NUL and other C0/C1 control
# characters; tab/newline/carriage-return are explicitly exempted since a
# pasted multi-line question is ordinary input, not an attack.
_ALLOWED_CONTROL_CHARS = frozenset("\t\n\r")


def _has_disallowed_control_character(text: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROL_CHARS for ch in text)


# --------------------------------------------------------------- PII (regex-only)
#
# 2026-09-16 explicit user decision: PROJECT_SPEC.md names Presidio (a
# real NLP library requiring spaCy + a language-model download - a new,
# heavy dependency) as the eventual tool. This task implements a
# deterministic regex-only baseline instead - zero new dependencies,
# fully offline, appropriate to catch a user accidentally pasting their
# own personal information into a question. Presidio (or an equivalent)
# remains a documented future upgrade, not silently adopted here.

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b(?:\+?1[-.\s])?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")

_PII_PATTERNS: tuple[re.Pattern, ...] = (_SSN_RE, _CREDIT_CARD_RE, _EMAIL_RE, _PHONE_RE)


def _contains_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII_PATTERNS)


# --------------------------------------------------------------- scope enforcement (loose deny-list)
#
# 2026-09-16 explicit user decision: a "loose deny-list" - reject only
# inputs with ZERO financial/SEC-domain signal at all. Deliberately does
# NOT require a resolvable CIK/XBRL-concept the way
# src.router.rules.classify_intent()'s "no_resolvable_financial_signal"
# rule does - that rule is tuned for structured xbrl_fact-shaped
# questions (Task 3.8's own documented scope) and would wrongly reject
# legitimate narrative-only questions (e.g. "What are the main risk
# factors described in this filing?", one of Task 1.7's own smoke
# questions - it has no CIK/fiscal_year/XBRL-concept at all). This is a
# different, narrower job than routing: only screening out inputs with
# no plausible connection to SEC filings/financial topics at all.

_DOMAIN_KEYWORDS: tuple[str, ...] = (
    # SEC filing / document vocabulary
    "10-k", "10-q", "8-k", "20-f", "s-1", "def 14a", "annual report", "quarterly report",
    "sec filing", "filing", "filings", "prospectus", "proxy statement", "edgar",
    # financial statement / accounting vocabulary
    "revenue", "earnings", "net income", "net loss", "profit", "assets", "liabilities",
    "stockholders equity", "shareholders equity", "cash flow", "balance sheet",
    "income statement", "eps", "earnings per share", "gross margin", "gross profit",
    "operating income", "operating expense", "expenses", "dividend", "shares outstanding",
    "market cap", "stock price", "cost of revenue", "tax expense",
    # corporate / business vocabulary
    "company", "corporation", "fiscal year", "quarter", "ceo", "cfo", "board of directors",
    "shareholders", "stockholders", "subsidiary", "merger", "acquisition", "10k", "10q",
    # risk / narrative vocabulary
    "risk factor", "risk factors", "litigation", "competition", "regulatory", "compliance",
    # generic finance vocabulary
    "financial", "finance", "investment", "investor", "stock", "shares",
)


def _has_domain_signal(lowered: str) -> bool:
    if any(kw in lowered for kw in _DOMAIN_KEYWORDS):
        return True
    if extract_form_type(lowered) is not None:
        return True
    if extract_fiscal_years(lowered):
        return True
    return False


# --------------------------------------------------------------- injection / advice
#
# Reuses src.router.rules's frozen keyword lists directly (public
# aliases added for exactly this reuse) - never a second,
# independently-maintained keyword set ("do not create two competing
# guardrail APIs").


def _contains_any(lowered: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in lowered for kw in keywords)


# --------------------------------------------------------------- public API

def check_input(question, *, max_length: int) -> GuardDecision:
    """Deterministic input-boundary check. `max_length` is required
    explicitly (no hidden default here) so callers always thread it
    through from `src.config.get_settings().input_guard_max_length` -
    see `src.guards.input.check_input_with_settings` for the convenience
    wrapper.

    Order (first violation wins, same "return on first violated
    invariant" convention as `src.index.lancedb_index.validate_chunk_table`):
    type -> empty -> length -> control characters -> injection -> advice
    -> PII -> scope. Cheapest/most-structural checks run first.
    """
    if max_length <= 0:
        raise GuardConfigError(f"max_length must be positive, got {max_length}")

    if not isinstance(question, str):
        decision = GuardDecision(allowed=False, reason_code="invalid_type",
                                  detail=f"expected str, got {type(question).__name__}")
        _log_decision(decision, input_length=None)
        return decision

    input_length = len(question)

    if not question.strip():
        decision = GuardDecision(allowed=False, reason_code="empty_input", detail="input is empty or whitespace-only")
        _log_decision(decision, input_length=input_length)
        return decision

    if input_length > max_length:
        decision = GuardDecision(
            allowed=False, reason_code="input_too_long",
            detail=f"input length {input_length} exceeds max_length {max_length}",
        )
        _log_decision(decision, input_length=input_length)
        return decision

    if _has_disallowed_control_character(question):
        decision = GuardDecision(allowed=False, reason_code="disallowed_control_character",
                                  detail="input contains a disallowed Unicode control character")
        _log_decision(decision, input_length=input_length)
        return decision

    lowered = question.lower()

    if _contains_any(lowered, INJECTION_KEYWORDS):
        decision = GuardDecision(allowed=False, reason_code="prompt_injection_detected",
                                  detail="input matched a known prompt-injection pattern")
        _log_decision(decision, input_length=input_length)
        return decision

    if _contains_any(lowered, ADVICE_KEYWORDS):
        decision = GuardDecision(allowed=False, reason_code="advice_request_detected",
                                  detail="input requests personalized financial/investment advice")
        _log_decision(decision, input_length=input_length)
        return decision

    if _contains_pii(question):
        decision = GuardDecision(allowed=False, reason_code="pii_detected",
                                  detail="input appears to contain personally identifiable information")
        _log_decision(decision, input_length=input_length)
        return decision

    if not _has_domain_signal(lowered):
        decision = GuardDecision(allowed=False, reason_code="out_of_scope",
                                  detail="input has no discernible connection to SEC filings/financial topics")
        _log_decision(decision, input_length=input_length)
        return decision

    decision = GuardDecision(allowed=True, reason_code=None, detail=None)
    _log_decision(decision, input_length=input_length)
    return decision


def check_input_with_settings(question, settings=None) -> GuardDecision:
    """Convenience wrapper reading `max_length` from
    `src.config.get_settings().input_guard_max_length`."""
    if settings is None:
        from src.config import get_settings
        settings = get_settings()
    return check_input(question, max_length=settings.input_guard_max_length)


def _log_decision(decision: GuardDecision, *, input_length: int | None) -> None:
    log_event(
        log, logging.INFO, "input_guard_decision",
        allowed=decision.allowed, reason_code=decision.reason_code, input_length=input_length,
    )


__all__ = [
    "GuardDecision", "GuardConfigError", "REASON_CODES", "RATE_LIMITING_STRATEGY",
    "check_input", "check_input_with_settings",
]
