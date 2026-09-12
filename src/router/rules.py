"""Task 3.8 - rules-first query router. Deterministic keyword/regex/
gazetteer classification of a natural-language question into one of the
six intents this project's frozen DEV corpus (`results/phase_2_4_dev.json`)
actually has labeled examples for: `xbrl_fact`, `numeric_derived`,
`cross_entity`, `unanswerable`, `out_of_scope`, `advice`.

Scope note (user-approved, 2026-09-12): PROJECT_EXECUTION.md's Task 3.8
lists 10 target intents, but the entire 1,932-question DEV corpus has
ZERO examples of `numeric_narrative`, `narrative`, or `section_summary`
(verified by exhaustively counting every `(category, subtype)` shape
present) - `src.eval.evaluation_dataset.build_narrative_record()` exists
in code but every narrative record it could produce stays
`status="pending_review"` and was never promoted into the frozen eval
set. Building/evaluating a router for intents with no real labeled
example anywhere would require fabricating new eval data - a decision
on the scale of Task 2.3's original question generation, not a router
sub-task. This module and its evaluation are scoped to the six intents
with real ground truth; the other four are documented as designed-but-
unevaluated, not silently dropped.

No I/O, no model, no network - takes plain question text plus an
already-loaded company gazetteer and XBRL tag registry, returns a
`RoutingDecision`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

from src.eval.tag_registry import TagRegistry
from src.eval.truth_contract import SUPPORTED_FISCAL_YEAR_MAX, SUPPORTED_FISCAL_YEAR_MIN

INTENTS: tuple[str, ...] = (
    "xbrl_fact", "numeric_derived", "cross_entity", "unanswerable", "out_of_scope", "advice",
)

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_FORM_TYPE_RE = re.compile(r"\b(10-K/?A?|10-Q/?A?|8-K/?A?|20-F|S-1|DEF 14A)\b", re.IGNORECASE)

# Deterministic keyword cues, kept intentionally small and generalizable
# (never a memorized copy of `src.eval.evaluation_dataset.ADVERSARIAL_TEMPLATES`'s
# exact template strings - a rules-first router must generalize past the
# 60 fixed templates that happened to generate the eval set).
_INJECTION_KEYWORDS: tuple[str, ...] = (
    "ignore all previous", "ignore the", "disregard", "system prompt", "developer mode",
    "system override", "act as an unfiltered", "act as a", "roleplay as", "no restrictions",
    "hidden instructions", "raw configuration", "base64", "confidential leak", "jailbreak",
    "pretend the retrieved", "forget the filing context", "new instructions from the developer",
    "the text above this line is fake", "end the citation-integrity check",
)
_ADVICE_KEYWORDS: tuple[str, ...] = (
    "should i buy", "should i sell", "should i invest", "should i short", "should i take out a loan",
    "should i put my", "good time to invest", "guarantee me", "will beat earnings", "go up next quarter",
    "go bankrupt", "price target", "maximum profit", "personally invest", "stock going to crash",
    "bet my house", "confident prediction", "better investment than",
)
_COMPARATIVE_KEYWORDS: tuple[str, ...] = (
    "which company", "compare", "higher", "lower", "greater than", "less than", "versus", " vs ",
)
_DERIVED_KEYWORDS: tuple[str, ...] = (
    "change from", "changed from", "difference between", "how much did", "year-over-year",
    "year over year", "increase from", "decrease from", "grew from", "grow from",
)


@dataclass(frozen=True)
class RoutingDecision:
    intent: str
    resolved_ciks: tuple[int, ...]
    fiscal_years: tuple[int, ...]
    concept: str | None
    form_type: str | None
    matched_rule: str
    extra: dict = field(default_factory=dict)


class CompanyGazetteer:
    """Case-insensitive exact-substring company-name -> CIK lookup.
    `entries` is a plain `{company_name: cik}` mapping - the router
    itself never decides where that mapping came from (see
    `configs/phase_3_8_rules_first_router.json`'s `gazetteer_source`
    for this task's documented source)."""

    def __init__(self, entries: Mapping[str, int]):
        # Longest name first so "SIX FLAGS ENTERTAINMENT CORP" matches
        # before a shorter accidental substring of another entry would.
        self._entries = sorted(((name.upper(), cik) for name, cik in entries.items()),
                                key=lambda kv: -len(kv[0]))

    def resolve(self, text: str) -> list[tuple[str, int]]:
        upper = text.upper()
        matches: list[tuple[str, int]] = []
        matched_spans: list[tuple[int, int]] = []
        for name, cik in self._entries:
            idx = upper.find(name)
            if idx == -1:
                continue
            span = (idx, idx + len(name))
            if any(not (span[1] <= s[0] or span[0] >= s[1]) for s in matched_spans):
                continue  # already covered by a longer match
            matches.append((name, cik))
            matched_spans.append(span)
        return matches


def extract_fiscal_years(text: str) -> tuple[int, ...]:
    return tuple(int(m.group(0)) for m in _YEAR_RE.finditer(text))


def extract_form_type(text: str) -> str | None:
    m = _FORM_TYPE_RE.search(text)
    return m.group(0).upper() if m else None


def resolve_xbrl_concept(text: str, registry: TagRegistry) -> str | None:
    """Matches a tag's human-readable `label` (e.g. "Total assets") as a
    case-insensitive substring of the question text - the frozen Task
    2.2 registry is the ONLY source of concept names; never a second,
    independently-maintained keyword list."""
    lowered = text.lower()
    for tag_name, spec in registry.tags.items():
        if spec.label and spec.label.lower() in lowered:
            return tag_name
    return None


def _contains_any(lowered: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in lowered for kw in keywords)


def classify_intent(question: str, *, gazetteer: CompanyGazetteer, registry: TagRegistry) -> RoutingDecision:
    lowered = question.lower()

    if _contains_any(lowered, _INJECTION_KEYWORDS):
        return RoutingDecision(intent="out_of_scope", resolved_ciks=(), fiscal_years=(), concept=None,
                                form_type=None, matched_rule="prompt_injection_keyword")

    if _contains_any(lowered, _ADVICE_KEYWORDS):
        return RoutingDecision(intent="advice", resolved_ciks=(), fiscal_years=(), concept=None,
                                form_type=None, matched_rule="financial_advice_keyword")

    companies = gazetteer.resolve(question)
    ciks = tuple(cik for _, cik in companies)
    fiscal_years = extract_fiscal_years(question)
    concept = resolve_xbrl_concept(question, registry)
    form_type = extract_form_type(question)

    if not ciks and not fiscal_years and concept is None:
        return RoutingDecision(intent="out_of_scope", resolved_ciks=(), fiscal_years=(), concept=None,
                                form_type=form_type, matched_rule="no_resolvable_financial_signal")

    if _contains_any(lowered, _COMPARATIVE_KEYWORDS) and len(set(ciks)) >= 2:
        return RoutingDecision(intent="cross_entity", resolved_ciks=ciks, fiscal_years=fiscal_years,
                                concept=concept, form_type=form_type, matched_rule="comparative_two_companies")

    if _contains_any(lowered, _DERIVED_KEYWORDS) and len(set(fiscal_years)) >= 2:
        return RoutingDecision(intent="numeric_derived", resolved_ciks=ciks, fiscal_years=fiscal_years,
                                concept=concept, form_type=form_type, matched_rule="derived_two_fiscal_years")

    if any(y < SUPPORTED_FISCAL_YEAR_MIN or y > SUPPORTED_FISCAL_YEAR_MAX for y in fiscal_years):
        return RoutingDecision(intent="unanswerable", resolved_ciks=ciks, fiscal_years=fiscal_years,
                                concept=concept, form_type=form_type, matched_rule="fiscal_year_outside_window")

    if concept is None:
        return RoutingDecision(intent="unanswerable", resolved_ciks=ciks, fiscal_years=fiscal_years,
                                concept=None, form_type=form_type, matched_rule="no_known_concept_matched")

    return RoutingDecision(intent="xbrl_fact", resolved_ciks=ciks, fiscal_years=fiscal_years,
                            concept=concept, form_type=form_type, matched_rule="default_xbrl_fact")


__all__ = [
    "INTENTS", "RoutingDecision", "CompanyGazetteer",
    "extract_fiscal_years", "extract_form_type", "resolve_xbrl_concept", "classify_intent",
]
