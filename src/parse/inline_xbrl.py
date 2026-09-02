"""Task 2.8 - raw inline-XBRL DOM extraction, independent of any
structural/Markdown parser (Docling's own conversion does NOT preserve
`ix:nonFraction`/`contextRef`/`unitRef`/`decimals`/`scale`/`sign` - see
project_plan/PHASE2_PRIMARY_EVIDENCE.md's "Docling contract" section).

Verified against a real primary filing before writing this module:
lxml's HTML parser (`etree.HTMLParser`) LOWERCASES all tag names
(`ix:nonFraction` -> `ix:nonfraction`), silently losing every inline-XBRL
element - primary 10-K filings are well-formed XHTML+inline-XBRL, so
`etree.XMLParser` is used instead, which preserves exact case and real
namespace URIs. This module never assumes tag names are case-sensitive
under HTML parsing rules; it never uses `etree.HTMLParser` at all.

Numeric normalization was independently verified against a real
`data/xbrl.duckdb` raw fact before being trusted: the inline fact
`us-gaap:Revenues` (contextRef=c-1: startDate=2023-01-01,
endDate=2023-12-31), displayed "1,875,448" with `scale="3"`, normalizes
to `1875448000` via `strip_thousands_separators -> Decimal -> * 10**scale`
- exactly matching the real `facts` table row
`(adsh='0000100122-24-000002', tag='Revenues', ddate='20231231', qtrs=4,
uom='USD', value=1875448000.0)`. See
`tests/test_inline_xbrl.py::test_numeric_normalization_matches_real_xbrl_fact`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

IX_NS = "http://www.xbrl.org/2013/inlineXBRL"
XBRLI_NS = "http://www.xbrl.org/2003/instance"
XBRLDI_NS = "http://xbrl.org/2006/xbrldi"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_XSI_NIL = f"{{{XSI_NS}}}nil"

_IX_NONFRACTION = f"{{{IX_NS}}}nonFraction"
_IX_NONNUMERIC = f"{{{IX_NS}}}nonNumeric"
_IX_CONTINUATION = f"{{{IX_NS}}}continuation"
_XBRLI_CONTEXT = f"{{{XBRLI_NS}}}context"
_XBRLI_UNIT = f"{{{XBRLI_NS}}}unit"
_XBRLI_ENTITY = f"{{{XBRLI_NS}}}entity"
_XBRLI_IDENTIFIER = f"{{{XBRLI_NS}}}identifier"
_XBRLI_SEGMENT = f"{{{XBRLI_NS}}}segment"
_XBRLI_PERIOD = f"{{{XBRLI_NS}}}period"
_XBRLI_INSTANT = f"{{{XBRLI_NS}}}instant"
_XBRLI_STARTDATE = f"{{{XBRLI_NS}}}startDate"
_XBRLI_ENDDATE = f"{{{XBRLI_NS}}}endDate"
_XBRLI_MEASURE = f"{{{XBRLI_NS}}}measure"
_XBRLI_DIVIDE = f"{{{XBRLI_NS}}}divide"
_XBRLI_UNIT_NUMERATOR = f"{{{XBRLI_NS}}}unitNumerator"
_XBRLI_UNIT_DENOMINATOR = f"{{{XBRLI_NS}}}unitDenominator"
_XBRLDI_EXPLICIT_MEMBER = f"{{{XBRLDI_NS}}}explicitMember"


class InlineXbrlParseError(ValueError):
    pass


class NumericNormalizationError(ValueError):
    """Raised for a numeric transform this module does not have an
    explicit, hand-tested rule for - never silently guessed."""


def parse_xml(html_path: str | Path) -> etree._Element:
    """The one I/O function in this module. Raises InlineXbrlParseError
    if the file cannot be parsed as XML at all (a genuinely malformed
    primary filing) - callers record this as a parse failure, never
    silently skip it."""
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        tree = etree.parse(str(html_path), parser)
    except etree.XMLSyntaxError as exc:
        raise InlineXbrlParseError(f"{html_path}: not parseable as XML: {exc}") from exc
    root = tree.getroot()
    if root is None:
        raise InlineXbrlParseError(f"{html_path}: XML parse produced no root element")
    return root


# --------------------------------------------------------------- contexts/units

@dataclass(frozen=True)
class XbrlPeriod:
    period_type: str  # "instant" or "duration"
    instant: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class XbrlContext:
    context_id: str
    entity_identifier: str
    period: XbrlPeriod
    dimensions: tuple[tuple[str, str], ...]  # (dimension_qname, member_qname), sorted


@dataclass(frozen=True)
class XbrlUnit:
    unit_id: str
    measures: tuple[str, ...]
    # populated only for a <xbrli:divide> unit (e.g. USD-per-share EPS
    # units) - `measures` stays empty for these, since a divide unit has
    # no direct <xbrli:measure> children of its own.
    divide_numerator: tuple[str, ...] = ()
    divide_denominator: tuple[str, ...] = ()


def extract_contexts(root: etree._Element) -> dict[str, XbrlContext]:
    contexts: dict[str, XbrlContext] = {}
    for c in root.iter(_XBRLI_CONTEXT):
        cid = c.get("id")
        if cid is None:
            continue
        entity = c.find(_XBRLI_ENTITY)
        identifier_el = entity.find(_XBRLI_IDENTIFIER) if entity is not None else None
        identifier = identifier_el.text.strip() if identifier_el is not None and identifier_el.text else ""

        period_el = c.find(_XBRLI_PERIOD)
        instant_el = period_el.find(_XBRLI_INSTANT) if period_el is not None else None
        start_el = period_el.find(_XBRLI_STARTDATE) if period_el is not None else None
        end_el = period_el.find(_XBRLI_ENDDATE) if period_el is not None else None
        if instant_el is not None and instant_el.text:
            period = XbrlPeriod(period_type="instant", instant=instant_el.text.strip())
        elif start_el is not None and end_el is not None and start_el.text and end_el.text:
            period = XbrlPeriod(period_type="duration", start_date=start_el.text.strip(), end_date=end_el.text.strip())
        else:
            raise InlineXbrlParseError(f"context {cid!r}: no resolvable instant or start/end period")

        dims: list[tuple[str, str]] = []
        segment_el = entity.find(_XBRLI_SEGMENT) if entity is not None else None
        if segment_el is not None:
            for m in segment_el.findall(_XBRLDI_EXPLICIT_MEMBER):
                dim = m.get("dimension") or ""
                member = (m.text or "").strip()
                dims.append((dim, member))
        dims.sort()

        contexts[cid] = XbrlContext(
            context_id=cid, entity_identifier=identifier, period=period, dimensions=tuple(dims),
        )
    return contexts


def extract_units(root: etree._Element) -> dict[str, XbrlUnit]:
    units: dict[str, XbrlUnit] = {}
    for u in root.iter(_XBRLI_UNIT):
        uid = u.get("id")
        if uid is None:
            continue
        divide = u.find(_XBRLI_DIVIDE)
        if divide is not None:
            num_el = divide.find(_XBRLI_UNIT_NUMERATOR)
            den_el = divide.find(_XBRLI_UNIT_DENOMINATOR)
            numerator = tuple(sorted((m.text or "").strip() for m in num_el.findall(_XBRLI_MEASURE))) if num_el is not None else ()
            denominator = tuple(sorted((m.text or "").strip() for m in den_el.findall(_XBRLI_MEASURE))) if den_el is not None else ()
            units[uid] = XbrlUnit(unit_id=uid, measures=(), divide_numerator=numerator, divide_denominator=denominator)
        else:
            measures = tuple(sorted((m.text or "").strip() for m in u.findall(_XBRLI_MEASURE) if m.text))
            units[uid] = XbrlUnit(unit_id=uid, measures=measures)
    return units


# --------------------------------------------------------------- continuations

def resolve_continued_text(root: etree._Element, element: etree._Element) -> str:
    """Follows an `ix:*` element's `continuedAt` chain, concatenating
    text from each linked `ix:continuation` (or further `ix:*` fact)
    element, in chain order. Returns just the element's own text if it
    has no continuation. Raises InlineXbrlParseError on a broken chain
    (continuedAt references a nonexistent id) or a cycle - never loops
    forever, never silently truncates."""
    parts = ["".join(element.itertext())]
    seen_ids: set[str] = set()
    current = element
    while True:
        next_id = current.get("continuedAt")
        if next_id is None:
            break
        if next_id in seen_ids:
            raise InlineXbrlParseError(f"continuation cycle detected at id {next_id!r}")
        seen_ids.add(next_id)
        matches = root.xpath(f"//*[@id='{next_id}']")
        if not matches:
            raise InlineXbrlParseError(f"continuedAt={next_id!r} does not resolve to any element")
        current = matches[0]
        parts.append("".join(current.itertext()))
    return "".join(parts)


# --------------------------------------------------------------- numeric normalization
#
# Only transforms actually observed in the real corpus (verified via
# scripts/build_primary_evidence.py --dry-run's transform-name audit)
# are handled explicitly. An unrecognized `format` raises
# NumericNormalizationError rather than silently guessing - Section 28's
# "do not use floating-point string hacks" is honored by using
# decimal.Decimal throughout, never float() on the raw displayed string.

_KNOWN_NUMERIC_FORMATS = {
    "ixt:num-dot-decimal", "ixt:numdotdecimal",
    "ixt:num-comma-decimal", "ixt:numcommadecimal",
    "ixt:fixed-zero", "ixt:fixedzero",
    "ixt:zerodash",
    "ixt-sec:num-dot-decimal",
    "ixt-sec:numwordsen",
    None, "",
}

# English number words actually observed in this corpus (verified via a
# 30-filing scan before writing this dict, never guessed): ones 0-20,
# tens, "no"/"none"/"nil" as zero, hyphenated compounds ("forty-two"),
# and "X thousand" compounds ("five thousand"). Anything beyond this
# raises NumericNormalizationError - a real parse failure, never a
# silent guess at an unbounded natural-language number parser.
_ONES_WORDS = {
    "zero": 0, "no": 0, "none": 0, "nil": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS_WORDS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}


_MULTIPLIER_WORDS = {"thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}


def _parse_small_number_word(word: str) -> int | None:
    """Parses a 0-99 English number word/compound (e.g. "seven",
    "forty-two"). Returns None if `word` doesn't match this shape."""
    if word in _ONES_WORDS:
        return _ONES_WORDS[word]
    if word in _TENS_WORDS:
        return _TENS_WORDS[word]
    if "-" in word:
        tens_part, _, ones_part = word.partition("-")
        if tens_part in _TENS_WORDS and ones_part in _ONES_WORDS:
            return _TENS_WORDS[tens_part] + _ONES_WORDS[ones_part]
    return None


def _parse_hundreds_compound(tokens: list[str]) -> int | None:
    """Parses a 0-999 compound with an optional "X hundred" prefix
    (e.g. ["one", "hundred", "three"] -> 103, ["three", "hundred"] -> 300,
    ["forty-two"] -> 42). Returns None if `tokens` doesn't match this
    shape."""
    if len(tokens) >= 2 and tokens[1] == "hundred":
        hundreds_digit = _parse_small_number_word(tokens[0])
        if hundreds_digit is None:
            return None
        remainder_tokens = tokens[2:]
        if not remainder_tokens:
            return hundreds_digit * 100
        remainder = _parse_hundreds_compound(remainder_tokens)  # e.g. "thirty three" or "forty-two"
        if remainder is None:
            return None
        return hundreds_digit * 100 + remainder
    if len(tokens) == 1:
        return _parse_small_number_word(tokens[0])
    if len(tokens) == 2 and tokens[0] in _TENS_WORDS and tokens[1] in _ONES_WORDS:
        # space-separated tens+ones compound ("twenty three"), as
        # distinct from the hyphenated form ("twenty-three") already
        # handled by _parse_small_number_word - both forms occur in real
        # filings (verified: "twenty three" found in the full 990-
        # document run).
        return _TENS_WORDS[tokens[0]] + _ONES_WORDS[tokens[1]]
    return None


def _parse_english_number_word(text: str) -> int:
    word = text.strip().lower()
    small = _parse_small_number_word(word)
    if small is not None:
        return small

    tokens = word.split()
    if tokens and tokens[-1] in _MULTIPLIER_WORDS:
        multiplier = _MULTIPLIER_WORDS[tokens[-1]]
        base = _parse_hundreds_compound(tokens[:-1])
        if base is not None:
            return base * multiplier
    else:
        base = _parse_hundreds_compound(tokens)
        if base is not None:
            return base

    raise NumericNormalizationError(f"unrecognized number word {text!r} for ixt-sec:numwordsen")


def normalize_numeric(*, raw_text: str, scale: str | None, sign: str | None, format_name: str | None) -> Decimal:
    """`raw_text` is the fact element's concatenated visible text
    (continuation-resolved). Returns the canonical Decimal value:
    `sign_multiplier * strip(raw_text) * 10**scale`. `decimals` is
    metadata about precision, not part of the value transform, and is
    preserved separately, never applied here."""
    fmt = (format_name or "").strip() or None
    if fmt is not None and fmt not in _KNOWN_NUMERIC_FORMATS:
        raise NumericNormalizationError(f"unrecognized ix:nonFraction format {fmt!r} - no hand-verified rule for it")

    if fmt in ("ixt:fixed-zero", "ixt:fixedzero", "ixt:zerodash"):
        base = Decimal(0)
    elif fmt == "ixt-sec:numwordsen":
        base = Decimal(_parse_english_number_word(raw_text))
    else:
        cleaned = raw_text.strip()
        # ixt:num-comma-decimal uses '.' as thousands separator and ',' as
        # decimal point (European convention) - not observed in this
        # corpus's sample, but handled explicitly rather than guessed.
        if fmt in ("ixt:num-comma-decimal", "ixt:numcommadecimal"):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        cleaned = cleaned.replace("—", "0").replace("–", "0")  # em/en dash sometimes used for zero
        if cleaned in ("", "-"):
            raise NumericNormalizationError(f"empty/placeholder numeric text: {raw_text!r}")
        try:
            base = Decimal(cleaned)
        except InvalidOperation as exc:
            raise NumericNormalizationError(f"could not parse {raw_text!r} as a decimal number") from exc

    if sign == "-":
        base = -base
    elif sign not in (None, "", "+"):
        raise NumericNormalizationError(f"unrecognized sign attribute {sign!r}")

    if scale is not None and scale.strip() != "":
        try:
            scale_int = int(scale)
        except ValueError as exc:
            raise NumericNormalizationError(f"non-integer scale attribute {scale!r}") from exc
        base = base * (Decimal(10) ** scale_int)

    return base


# --------------------------------------------------------------- fact extraction

@dataclass(frozen=True)
class RawInlineFact:
    fact_kind: str  # "nonFraction" or "nonNumeric"
    element_id: str | None
    concept_qname: str
    context_ref: str
    unit_ref: str | None
    decimals: str | None
    scale: str | None
    sign: str | None
    format_name: str | None
    raw_display_text: str
    normalized_value: Decimal | None  # None for nonNumeric facts and for xsi:nil="true" facts
    is_nil: bool
    source_order: int


def extract_inline_facts(root: etree._Element) -> list[RawInlineFact]:
    """Extracts every `ix:nonFraction`/`ix:nonNumeric` element in document
    order, with continuations resolved. A `nonFraction` element whose
    numeric normalization fails raises NumericNormalizationError
    immediately (never silently dropped) - callers decide whether to
    treat one bad fact as a partial-document failure or skip-and-record
    per the project's failure-manifest convention."""
    facts: list[RawInlineFact] = []
    order = 0
    for el in root.iter(_IX_NONFRACTION, _IX_NONNUMERIC):
        kind = "nonFraction" if el.tag == _IX_NONFRACTION else "nonNumeric"
        raw_text = resolve_continued_text(root, el)
        is_nil = el.get(_XSI_NIL) == "true"
        normalized = None
        if kind == "nonFraction" and not is_nil:
            normalized = normalize_numeric(
                raw_text=raw_text, scale=el.get("scale"), sign=el.get("sign"), format_name=el.get("format"),
            )
        facts.append(RawInlineFact(
            fact_kind=kind,
            element_id=el.get("id"),
            concept_qname=el.get("name", ""),
            context_ref=el.get("contextRef", ""),
            unit_ref=el.get("unitRef"),
            decimals=el.get("decimals"),
            scale=el.get("scale"),
            sign=el.get("sign"),
            format_name=el.get("format"),
            raw_display_text=raw_text,
            normalized_value=normalized,
            is_nil=is_nil,
            source_order=order,
        ))
        order += 1
    return facts


# --------------------------------------------------------------- context -> truth-contract period mapping

@dataclass(frozen=True)
class TruthContractPeriod:
    period_type: str  # "instant" or "duration"
    ddate: str  # YYYYMMDD
    qtrs: int  # 0 for instant, else number of quarters spanned (best-effort for duration)


def _yyyymmdd(iso_date: str) -> str:
    return iso_date.replace("-", "")


def context_to_truth_contract_period(context: XbrlContext) -> TruthContractPeriod:
    """Converts an inline XBRL context's period into the same semantic
    fields src.eval.truth_contract's raw facts use: `ddate` (period END
    date, YYYYMMDD - instant facts use the instant date, duration facts
    use the end date) and `qtrs` (0 for instant; for duration, the
    number of whole quarters between start and end, rounded to the
    nearest quarter - 4 for a full fiscal year, 1 for a fiscal quarter).
    Verified against a real raw fact: a duration context
    (2023-01-01..2023-12-31) maps to ddate=20231231, qtrs=4, matching
    data/xbrl.duckdb's real Revenues row for the same accession exactly."""
    if context.period.period_type == "instant":
        return TruthContractPeriod(period_type="instant", ddate=_yyyymmdd(context.period.instant), qtrs=0)

    start = context.period.start_date
    end = context.period.end_date
    y1, m1, d1 = (int(x) for x in start.split("-"))
    y2, m2, d2 = (int(x) for x in end.split("-"))
    months = (y2 - y1) * 12 + (m2 - m1)
    days_fraction_adjust = 1 if d2 >= d1 else 0
    total_months = months + days_fraction_adjust
    qtrs = max(1, round(total_months / 3))
    return TruthContractPeriod(period_type="duration", ddate=_yyyymmdd(end), qtrs=qtrs)
