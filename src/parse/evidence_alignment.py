"""Task 2.8 - deterministic alignment of inline-XBRL facts to structural
evidence nodes and to the frozen Task 2.1 truth contract / Task 2.2 tag
registry.

Reuses `src.eval.truth_contract` and `src.eval.tag_registry` directly -
this module never reimplements XBRL eligibility rules and never creates
a competing truth contract (Section 31/32). It reads the raw `facts`
table (not just `eligible_facts()`) for one purpose only: independently
verifying that an extracted, normalized inline value matches a real row
in the authoritative source-of-truth database, for ANY fiscal year -
this is a correctness check on the alignment MECHANISM, never a
promotion to Phase 2 gold (see EXTRACTED/ELIGIBLE/GOLD state machine
below).

Maintains the three explicit states Section 30 requires - never
collapsed:

    EXTRACTED            - the fact was parsed from raw HTML at all
    TRUTH-CONTRACT ELIGIBLE - the fact matches src.eval.truth_contract's
                              full eligibility rule set (form, window,
                              coreg, segments, registry qtrs/unit, taxonomy)
    EVIDENCE-ALIGNED GOLD - eligible AND exactly aligned to one or more
                              structural nodes

All 990 primary filings in this corpus are fiscal_year 2021-2024 -
independently verified (0/990 fall inside the frozen 2016-2020 window) -
so EVIDENCE-ALIGNED GOLD is 0 for this population under the current,
unmodified Task 2.1 truth contract. This is a real, structural
population mismatch (Section 33), not a parser or alignment defect -
see project_plan/PHASE2_PRIMARY_EVIDENCE.md. Per explicit user decision,
this module still verifies raw-value correctness against the real
`facts` table (any year) and reports every other eligibility dimension
(registry support, dimension-free, unit/qtrs match) so the alignment
mechanism's correctness is provable independent of the year gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from src.eval.tag_registry import get_registry
from src.eval.truth_contract import SUPPORTED_FISCAL_YEAR_MIN, SUPPORTED_FISCAL_YEAR_MAX, SUPPORTED_FORM

EVIDENCE_SCHEMA_VERSION = "1.0"

ALIGNMENT_STATUSES = (
    "exact",
    "exact_no_node",
    "ambiguous",
    "unmatched",
    "unsupported_tag",
    "ineligible_dimensional",
    "ineligible_year_window",
    "parse_error",
)

_WS_RE = re.compile(r"\s+")


def _normalize_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


@dataclass(frozen=True)
class FactIdentity:
    """The canonical grain used to look up a candidate raw truth-contract
    row - accession-first, per Section 34 (never a global numeric
    search)."""
    accession: str
    cik: int
    tag: str  # bare (namespace-stripped) concept name
    ddate: str
    qtrs: int
    uom: str


def bare_tag_name(concept_qname: str) -> tuple[str | None, str]:
    """Splits "us-gaap:Revenues" into ("us-gaap", "Revenues"). Returns
    (None, original) for a QName with no namespace prefix."""
    if ":" not in concept_qname:
        return None, concept_qname
    ns, _, local = concept_qname.partition(":")
    return ns, local


def unit_to_uom(unit) -> str | None:
    """Maps a full XbrlUnit (simple OR divide) to the canonical uom
    string the truth contract/raw facts table uses.

    A `<xbrli:divide>` unit with numerator=iso4217:X and
    denominator=xbrli:shares (the standard XBRL representation of a
    per-share EPS unit) maps to canonical uom=X - verified against a
    real raw fact: Amazon's inline `us-gaap:EarningsPerShareDiluted`
    fact uses a USD/shares divide unit, and `data/xbrl.duckdb`'s real
    `facts` row for the same accession/tag stores `uom='USD'` (SEC's own
    processing pipeline strips the per-share denominator for storage -
    confirmed directly, matching Task 2.2's registry decision that EPS
    tags use plain "USD", never a compound "USD/shares"). Any other
    divide unit shape (a denominator other than shares) returns None
    rather than guessing."""
    if unit.divide_numerator or unit.divide_denominator:
        if (len(unit.divide_numerator) == 1 and len(unit.divide_denominator) == 1
                and unit.divide_denominator[0].split(":")[-1].lower() == "shares"):
            return unit_measure_to_uom(unit.divide_numerator)
        return None
    return unit_measure_to_uom(unit.measures)


def unit_measure_to_uom(measures: Sequence[str]) -> str | None:
    """Maps an inline unit's measure(s) to the canonical uom string the
    truth contract/raw facts table uses. Only single-measure monetary
    (iso4217:*) and simple share/pure units are mapped explicitly -
    anything else (compound/divide units) returns None rather than
    guessing (Section 27: no currency conversion, no invented mapping)."""
    if len(measures) != 1:
        return None
    measure = measures[0]
    if ":" in measure:
        ns, _, local = measure.partition(":")
        if ns.lower() == "iso4217":
            return local.upper()
        if ns.lower() in ("xbrli", "utr") and local.lower() in ("shares", "pure"):
            return local.lower()
        return None
    return measure


@dataclass(frozen=True)
class RawMatchResult:
    status: str  # "exact" | "ambiguous" | "unmatched"
    matched_values: tuple[Decimal, ...]


def match_against_raw_facts(con, identity: FactIdentity, normalized_value: Decimal) -> RawMatchResult:
    """Queries the RAW `facts` table (not `eligible_facts()`) restricted
    first by accession (Section 34), then by the full fact-identity
    grain. This is the correctness check against the real source-of-
    truth database for ANY fiscal year - never itself a gold-eligibility
    decision."""
    # coreg/segments blank matches src.eval.truth_contract's own grain
    # exactly - without it, a dimensional duplicate row for the same
    # (adsh,tag,ddate,qtrs,uom) grain (very common - see Section 37) can
    # be picked up instead of the real non-dimensional value. Callers
    # only invoke this for non-dimensional facts (see
    # determine_alignment_status/"ineligible_dimensional") - a
    # dimensional inline fact is never raw-matched here at all.
    rows = con.execute(
        """
        SELECT value FROM facts
        WHERE adsh = ? AND cik = ? AND tag = ? AND ddate = ? AND qtrs = ? AND uom = ?
          AND (coreg IS NULL OR coreg = '') AND (segments IS NULL OR segments = '')
        """,
        [identity.accession, identity.cik, identity.tag, identity.ddate, identity.qtrs, identity.uom],
    ).fetchall()
    values = tuple(Decimal(str(r[0])) for r in rows)
    distinct = set(values)
    if not distinct:
        return RawMatchResult(status="unmatched", matched_values=())
    if len(distinct) > 1:
        return RawMatchResult(status="ambiguous", matched_values=values)
    matched = distinct.pop()
    # tolerance: source facts table stores float64; our normalized value
    # is an exact Decimal from the inline display text. Compare via the
    # float64 round-trip so a genuinely identical value never spuriously
    # mismatches on Decimal-vs-float64 representation noise.
    if float(matched) == float(normalized_value):
        return RawMatchResult(status="exact", matched_values=(matched,))
    return RawMatchResult(status="unmatched", matched_values=(matched,))


@dataclass(frozen=True)
class EligibilityCheck:
    tag_supported: bool
    unit_matches_registry: bool | None  # None if tag unsupported
    qtrs_matches_registry: bool | None
    dimension_free: bool
    year_in_window: bool
    fiscal_year: int


def check_eligibility_dimensions(*, tag: str, namespace: str | None, uom: str | None, qtrs: int,
                                  has_dimensions: bool, fiscal_year: int) -> EligibilityCheck:
    """Evaluates every Task 2.1/2.2 eligibility dimension independently
    (never re-deriving the rules - only calling the frozen registry) so
    a diagnostic report can show WHICH rule(s) block eligibility, not
    just a final yes/no (Section 60-65)."""
    if namespace != "us-gaap":
        return EligibilityCheck(
            tag_supported=False, unit_matches_registry=None, qtrs_matches_registry=None,
            dimension_free=not has_dimensions, year_in_window=SUPPORTED_FISCAL_YEAR_MIN <= fiscal_year <= SUPPORTED_FISCAL_YEAR_MAX,
            fiscal_year=fiscal_year,
        )
    registry = get_registry()
    spec = registry.tags.get(tag)  # dict.get(), never TagRegistry.get() which raises on unknown tags
    tag_supported = spec is not None and spec.enabled
    unit_matches = (uom == spec.unit) if tag_supported else None
    qtrs_matches = (qtrs == spec.qtrs) if tag_supported else None
    return EligibilityCheck(
        tag_supported=tag_supported,
        unit_matches_registry=unit_matches,
        qtrs_matches_registry=qtrs_matches,
        dimension_free=not has_dimensions,
        year_in_window=SUPPORTED_FISCAL_YEAR_MIN <= fiscal_year <= SUPPORTED_FISCAL_YEAR_MAX,
        fiscal_year=fiscal_year,
    )


def is_fully_eligible(check: EligibilityCheck) -> bool:
    return bool(
        check.tag_supported and check.unit_matches_registry and check.qtrs_matches_registry
        and check.dimension_free and check.year_in_window
    )


def determine_alignment_status(*, raw_match: RawMatchResult | None, eligibility: EligibilityCheck, node_ids: Sequence[str]) -> str:
    """Explicit status per Section 42 - never a fabricated confidence
    score. Dimensional facts are classified before any raw-value match
    is even attempted (Section 37) - `raw_match` is expected to be None
    for them, since a coreg/segments-blank raw query is a category
    mismatch for a dimensional fact, not a genuine "unmatched" result."""
    if not eligibility.tag_supported:
        return "unsupported_tag"
    if not eligibility.dimension_free:
        return "ineligible_dimensional"
    if raw_match is None:
        raise ValueError("raw_match is required once a fact is confirmed non-dimensional and tag-supported")
    if raw_match.status == "ambiguous":
        return "ambiguous"
    if raw_match.status == "unmatched":
        return "unmatched"
    if not eligibility.year_in_window:
        return "ineligible_year_window"
    if not node_ids:
        return "exact_no_node"
    return "exact"


def find_candidate_nodes(raw_display_text: str, nodes: Sequence) -> list[str]:
    """Content-based structural correlation (Section 45/46): every node
    whose text contains `raw_display_text` (whitespace-normalized) is a
    valid candidate evidence node - ALL are returned, in source order,
    never collapsed to one (Section 44: multiple visible occurrences are
    a legitimate outcome, not deduplicated away). An empty
    `raw_display_text` never matches anything (a nil/empty fact has no
    textual evidence to align to)."""
    needle = _normalize_ws(raw_display_text)
    if not needle:
        return []
    matches = []
    for node in nodes:
        if needle in _normalize_ws(node.text):
            matches.append(node.node_id)
    return matches


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_schema_version: str
    evidence_id: str

    document_id: str
    cik: int
    accession: str
    fiscal_year: int

    section_id: str | None
    section_title: str | None

    node_ids: tuple[str, ...]
    content_type: str | None  # "table" | "narrative" | None

    concept_name: str
    concept_namespace: str | None
    context_ref: str
    unit_ref: str | None

    raw_display_value: str
    normalized_value: str | None  # repr(Decimal) or None
    canonical_unit: str | None

    alignment_status: str
    eligible_for_gold: bool

    truth_contract_version: str
    truth_contract_hash: str
    tag_registry_version: int
    tag_registry_hash: str


def build_evidence_id(document_id: str, element_id: str | None, source_order: int) -> str:
    suffix = element_id or f"order-{source_order:05d}"
    return f"{document_id}#fact-{suffix}"
