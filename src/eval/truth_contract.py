"""Task 2.1 - the project's single authoritative XBRL fact-eligibility
contract.

A raw XBRL `facts` row being technically valid does not mean it is safe
evaluation ground truth: the same (company, tag, year) can carry
consolidated facts, segment/dimensional breakdowns, co-registrant
(subsidiary) facts, mismatched units, instant-vs-duration confusion,
custom taxonomy extensions, comparative/prior-period columns embedded in
the same filing, and cross-filing value revisions. This module defines
exactly which rows are permitted to become Phase 2 evaluation ground
truth - nothing about *which* questions get generated from them (that is
later Phase 2 work: Task 2.2's tag-registry freeze, Task 2.3's ~3,000-
question generation).

Read-only against `data/xbrl.duckdb` - `eligible_facts()` never writes,
never mutates, never touches the frozen database.

## Terminology (do not regress this)

Earlier project analysis called a diagnostic "23.56% restatement rate."
That number was independently re-audited and found to measure the wrong
population (it left in segment/dimensional facts, ignored unit
mismatches, and never collapsed same-accession duplicates before
comparing values). The corrected, stricter figure - 7.87% (all tags),
8.00% (standard non-abstract tags), 10.39% (this module's own 10-tag
registry) - is called the **cross-filing value-revision rate**, never
"restatement rate": the data alone cannot prove a formal accounting
restatement occurred. See `DATA_READINESS_REPORT.md`, "Check 1", and
`project_plan/PHASE2_TRUTH_CONTRACT.md` for the full derivation. This
module's `eligible_facts()` never collapses or canonicalizes cross-filing
values - it preserves every filing's own `adsh` so a later value-revision
diagnostic (or a specific-filing-anchored evaluation question) can still
distinguish them.

## Tag / qtrs registry - what is and is not resolved here

`PROJECT_EXECUTION.md`'s Task 2.2 ("Freeze supported tag registry")
explicitly owns validating and freezing the ~15-concept evaluation
registry (tag, label, expected unit, expected `iord`, **expected qtrs**,
coverage, allowed question templates) into `configs/eval_tags.yaml`. Task
2.1 does not pre-empt that. `QTRS_BY_TAG` below contains exactly the 10
tags whose qtrs semantics are already explicitly resolved by Task 2.1's
own frozen instructions (4 instant tags at qtrs=0, 6 annual-duration tags
at qtrs=4). Five further tags appear as *candidates* in
`src.ingest.audit_data.CANDIDATE_TAGS` / `DATA_READINESS_REPORT.md`'s
15-tag table (`RevenueFromContractWithCustomerExcludingAssessedTax`,
`OperatingExpenses`, `EarningsPerShareBasic`, `EarningsPerShareDiluted`,
`IncomeTaxExpenseBenefit`) but have no approved qtrs mapping anywhere in
current authoritative documentation - `UNRESOLVED_CANDIDATE_TAGS` records
them explicitly rather than silently guessing (e.g. qtrs=4 by pattern-
matching their `iord=D` classification), per this task's explicit
instruction not to invent an unresolved project decision.
`eligible_facts()` raises `TruthContractError` - never silently proceeds
- if asked for a tag outside `QTRS_BY_TAG`.

## Materiality is deliberately out of scope here

`PROJECT_EXECUTION.md`'s own Task 2.1 checklist item states: "Keep
materiality/sampling policy separate from truth validity." A magnitude
threshold is a later question-generation/sampling concern, not a truth-
validity rule, so `eligible_facts()` takes no `min_magnitude` parameter -
a deliberate deviation from an earlier illustrative sketch of this
module's API, resolved by the authoritative roadmap document itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

CONTRACT_VERSION = "1.0"

# Resolved directly from this task's own frozen instructions - 4 instant
# concepts (qtrs=0) and 6 annual-duration concepts (qtrs=4). Verified
# against the real data (src/eval/truth_contract.py's own integration
# tests) rather than assumed.
QTRS_BY_TAG: dict[str, int] = {
    "Assets": 0,
    "Liabilities": 0,
    "StockholdersEquity": 0,
    "CashAndCashEquivalentsAtCarryingValue": 0,
    "Revenues": 4,
    "ResearchAndDevelopmentExpense": 4,
    "NetIncomeLoss": 4,
    "OperatingIncomeLoss": 4,
    "CostOfRevenue": 4,
    "GrossProfit": 4,
}

# Seen in src.ingest.audit_data.CANDIDATE_TAGS / DATA_READINESS_REPORT.md's
# 15-tag table, but with NO approved qtrs mapping anywhere in current
# authoritative documentation. Not usable with eligible_facts() until
# Task 2.2 freezes their qtrs semantics in configs/eval_tags.yaml.
UNRESOLVED_CANDIDATE_TAGS: tuple[str, ...] = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "OperatingExpenses",
    "EarningsPerShareBasic",
    "EarningsPerShareDiluted",
    "IncomeTaxExpenseBenefit",
)

# "Restrict to intended filing types" (PROJECT_EXECUTION.md Task 2.1) -
# matches Task 1.1's own established EDGAR<->XBRL alignment precedent
# (submissions.form = '10-K' only, never 10-Q/10-K-A/20-F/etc).
SUPPORTED_FORM = "10-K"

# "Restrict to the supported evaluation window" - the same 2016-2020
# window Task 1.1 aligned the development corpus to, using the same
# semantically-chosen `fiscal_year` field (DATA_READINESS_REPORT.md,
# "Check 2": fy chosen over period-year/filed-year because it is the
# semantically correct fiscal-year field, not because it maximizes match
# rate).
SUPPORTED_FISCAL_YEAR_MIN = 2016
SUPPORTED_FISCAL_YEAR_MAX = 2020

# version is stored as e.g. "us-gaap/2015" - never the literal string
# "us-gaap" (verified directly: 0 rows match `version = 'us-gaap'`,
# 84,101,557 rows match `version LIKE 'us-gaap/%'`). Custom-taxonomy
# extensions (accession-numbered "versions", "invest/...", "srt/...",
# "us-gaap-sup/...") are excluded.
TAXONOMY_PREFIX = "us-gaap/"

# All 15 candidate tags (10 resolved + 5 unresolved-qtrs) are monetary or
# per-share-in-USD figures in this dataset - verified directly, no
# non-USD unit branch is needed for this registry.
MONETARY_UOM = "USD"


class TruthContractError(ValueError):
    """Raised for a caller error against the truth contract - e.g. a tag
    with no approved qtrs mapping. Never raised for an ordinary data-
    quality rejection, which is simply an excluded row, not an error."""


@dataclass(frozen=True)
class EligibleFact:
    """One XBRL fact permitted to become Phase 2 evaluation ground truth.
    Preserves `adsh` (filing/accession identity) so cross-filing value
    revisions are never silently canonicalized away."""
    adsh: str
    cik: int
    company: str
    tag: str
    fiscal_year: int
    ddate: str
    qtrs: int
    uom: str
    value: float


def _validate_tags(tags: Sequence[str]) -> list[str]:
    tags = list(tags)
    unknown = sorted(set(tags) - set(QTRS_BY_TAG))
    if unknown:
        raise TruthContractError(
            f"no approved qtrs mapping for tag(s) {unknown} - Task 2.2 ('Freeze supported tag "
            f"registry', configs/eval_tags.yaml) owns resolving this; Task 2.1's contract "
            f"refuses to guess. Approved tags: {sorted(QTRS_BY_TAG)}"
        )
    return tags


def _escape(value: str) -> str:
    return value.replace("'", "''")


def build_contract_config(tags: Sequence[str]) -> dict:
    """Deterministic, timestamp-free provenance for the contract as
    applied to a specific `tags` selection. Never hash this dict with a
    timestamp mixed in - see compute_contract_config_hash()."""
    tags = _validate_tags(tags)
    sorted_tags = sorted(tags)
    return {
        "contract_version": CONTRACT_VERSION,
        "tags": sorted_tags,
        "qtrs_by_tag": {t: QTRS_BY_TAG[t] for t in sorted_tags},
        "form_rule": f"form = '{SUPPORTED_FORM}'",
        "fiscal_year_window_rule": f"fiscal_year BETWEEN {SUPPORTED_FISCAL_YEAR_MIN} AND {SUPPORTED_FISCAL_YEAR_MAX}",
        "coreg_rule": "coreg IS NULL OR coreg = '' (consolidated entity only, no co-registrant/subsidiary rows)",
        "segments_rule": "segments IS NULL OR segments = '' (no segment/dimensional breakdowns)",
        "taxonomy_rule": f"version LIKE '{TAXONOMY_PREFIX}%' (standard us-gaap taxonomy only, no custom extensions)",
        "unit_rule": f"uom = '{MONETARY_UOM}'",
        "value_rule": "value IS NOT NULL, finite, sign preserved (never normalized to positive)",
        "period_alignment_rule": (
            "ddate = submissions.period for the fact's own adsh - the fact must be the "
            "filing's own current-period figure, excluding comparative/prior-period columns "
            "also present in the same filing (verified directly against real data: only "
            "~44% of a 10-K's Assets facts and ~37% of its Revenues facts satisfy this, the "
            "rest being comparative prior-period columns)"
        ),
        "materiality_rule": (
            "none - deliberately excluded from truth validity per PROJECT_EXECUTION.md's own "
            "Task 2.1 checklist item ('Keep materiality/sampling policy separate from truth "
            "validity'); materiality/sampling belongs to later question-generation work"
        ),
        "dedup_rule": (
            "grain (adsh, tag, ddate, qtrs, uom) must be unique after every other filter; "
            "eligible_facts() raises rather than silently choosing between conflicting rows "
            "if this invariant is ever violated (verified empirically: 0 grain duplicates "
            "found for the resolved 10-tag registry in the 2016-2020/10-K window)"
        ),
        "ordering": "adsh, tag, ddate, qtrs, uom - ascending, explicit ORDER BY, never physical row order",
        "cross_filing_policy": (
            "no cross-filing canonicalization - every eligible adsh's own value is preserved; "
            "see cross-filing value-revision terminology note in this module's docstring"
        ),
    }


def compute_contract_config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def eligible_facts(con, tags: Sequence[str]) -> list[EligibleFact]:
    """Returns only XBRL facts permitted to become Phase 2 evaluation
    ground truth, per the frozen Task 2.1 contract above. `con` is an
    already-open DuckDB connection (read-only recommended) against
    `data/xbrl.duckdb` - this function issues one SELECT, never a write.

    Deterministic: identical (`con`'s underlying database, `tags`) always
    produces the same rows in the same order (explicit ORDER BY, never
    DuckDB's incidental physical row order).

    Raises `TruthContractError` if `tags` contains anything outside
    `QTRS_BY_TAG` - never guesses a qtrs value. Raises `RuntimeError` if a
    same-accession grain duplicate with a differing value is found after
    every other filter has already been applied - never silently picks
    one of several conflicting rows.
    """
    tags = _validate_tags(tags)
    if not tags:
        return []

    tags_sql = ",".join(f"'{_escape(t)}'" for t in tags)
    qtrs_case_sql = " ".join(f"WHEN '{_escape(t)}' THEN {QTRS_BY_TAG[t]}" for t in tags)

    query = f"""
        SELECT f.adsh, f.cik, f.company, f.tag, f.fiscal_year, f.ddate, f.qtrs, f.uom, f.value
        FROM facts f
        JOIN submissions s ON f.adsh = s.adsh AND f.ddate = s.period
        WHERE f.tag IN ({tags_sql})
          AND f.form = '{SUPPORTED_FORM}'
          AND f.fiscal_year BETWEEN {SUPPORTED_FISCAL_YEAR_MIN} AND {SUPPORTED_FISCAL_YEAR_MAX}
          AND (f.coreg IS NULL OR f.coreg = '')
          AND (f.segments IS NULL OR f.segments = '')
          AND f.version LIKE '{TAXONOMY_PREFIX}%'
          AND f.uom = '{MONETARY_UOM}'
          AND f.value IS NOT NULL
          AND NOT isnan(f.value)
          AND NOT isinf(f.value)
          AND f.qtrs = CASE f.tag {qtrs_case_sql} END
        ORDER BY f.adsh, f.tag, f.ddate, f.qtrs, f.uom
    """
    rows = con.execute(query).fetchall()

    seen: dict[tuple, float] = {}
    results: list[EligibleFact] = []
    for adsh, cik, company, tag, fiscal_year, ddate, qtrs, uom, value in rows:
        key = (adsh, tag, ddate, qtrs, uom)
        if key in seen:
            if seen[key] != value:
                raise RuntimeError(
                    f"conflicting same-accession duplicate values for grain {key}: "
                    f"{seen[key]!r} vs {value!r} - no repository policy resolves this; "
                    f"the truth contract refuses to silently choose one"
                )
            continue
        seen[key] = value
        results.append(EligibleFact(
            adsh=adsh, cik=int(cik), company=company, tag=tag,
            fiscal_year=int(fiscal_year), ddate=ddate, qtrs=int(qtrs),
            uom=uom, value=float(value),
        ))
    return results
