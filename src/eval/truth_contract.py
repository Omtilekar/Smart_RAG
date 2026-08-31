"""Task 2.1/2.2 - the project's single authoritative XBRL fact-eligibility
contract.

A raw XBRL `facts` row being technically valid does not mean it is safe
evaluation ground truth: the same (company, tag, year) can carry
consolidated facts, segment/dimensional breakdowns, co-registrant
(subsidiary) facts, mismatched units, instant-vs-duration confusion,
custom taxonomy extensions, comparative/prior-period columns embedded in
the same filing, and cross-filing value revisions. This module defines
exactly which rows are permitted to become Phase 2 evaluation ground
truth - nothing about *which* questions get generated from them (that is
later Phase 2 work).

Read-only against `data/xbrl.duckdb` - `eligible_facts()` never writes,
never mutates, never touches the frozen database.

## Terminology (do not regress this)

Earlier project analysis called a diagnostic "23.56% restatement rate."
That number was independently re-audited and found to measure the wrong
population (it left in segment/dimensional facts, ignored unit
mismatches, and never collapsed same-accession duplicates before
comparing values). The corrected, stricter figure - 7.87% (all tags),
8.00% (standard non-abstract tags), 10.39% (the data-readiness audit's
own 15-tag candidate set) - is called the **cross-filing value-revision
rate**, never "restatement rate": the data alone cannot prove a formal
accounting restatement occurred. See `DATA_READINESS_REPORT.md`, "Check
1", and `project_plan/PHASE2_TRUTH_CONTRACT.md` for the full derivation.
This module's `eligible_facts()` never collapses or canonicalizes
cross-filing values - it preserves every filing's own `adsh` so a later
value-revision diagnostic (or a specific-filing-anchored evaluation
question) can still distinguish them.

## Tag registry ownership (Task 2.2)

Per-tag `qtrs`/`unit`/`enabled`/`period_type` semantics live in exactly
one place: `configs/eval_tags.yaml`, loaded and validated by
`src.eval.tag_registry`. This module never hardcodes a second,
independently-maintained qtrs/unit mapping - `eligible_facts()` asks the
registry for each requested tag's semantics and raises
`TruthContractError` if a tag is unknown or disabled. See
`project_plan/PHASE2_TAG_REGISTRY.md` for the real-data evidence behind
every frozen tag decision, including the five tags Task 2.1 originally
left unresolved (all five are now `SUPPORTED` in the frozen registry).

## Materiality is deliberately out of scope here

`PROJECT_EXECUTION.md`'s own Task 2.1 checklist item states: "Keep
materiality/sampling policy separate from truth validity." A magnitude
threshold is a later question-generation/sampling concern, not a truth-
validity rule, so `eligible_facts()` takes no `min_magnitude` parameter -
a deliberate deviation from an earlier illustrative sketch of this
module's API, resolved by the authoritative roadmap document itself. Task
2.2 does not revisit this decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

from src.eval.tag_registry import get_registry

CONTRACT_VERSION = "2.0"

# "Restrict to intended filing types" (PROJECT_EXECUTION.md Task 2.1) -
# matches Task 1.1's own established EDGAR<->XBRL alignment precedent
# (submissions.form = '10-K' only, never 10-Q/10-K-A/20-F/etc). Applies
# uniformly to every tag - not part of the per-tag registry.
SUPPORTED_FORM = "10-K"

# "Restrict to the supported evaluation window" - the same 2016-2020
# window Task 1.1 aligned the development corpus to, using the same
# semantically-chosen `fiscal_year` field (DATA_READINESS_REPORT.md,
# "Check 2": fy chosen over period-year/filed-year because it is the
# semantically correct fiscal-year field, not because it maximizes match
# rate). Applies uniformly to every tag.
SUPPORTED_FISCAL_YEAR_MIN = 2016
SUPPORTED_FISCAL_YEAR_MAX = 2020

# version is stored as e.g. "us-gaap/2015" - never the literal string
# "us-gaap" (verified directly: 0 rows match `version = 'us-gaap'`,
# 84,101,557 rows match `version LIKE 'us-gaap/%'`). Custom-taxonomy
# extensions (accession-numbered "versions", "invest/...", "srt/...",
# "us-gaap-sup/...") are excluded. Applies uniformly to every tag.
TAXONOMY_PREFIX = "us-gaap/"


class TruthContractError(ValueError):
    """Raised for a caller error against the truth contract - e.g. a tag
    the registry does not know about or has disabled. Never raised for an
    ordinary data-quality rejection, which is simply an excluded row, not
    an error."""


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
    registry = get_registry()
    supported = set(registry.supported_tags())
    unsupported = sorted(set(tags) - supported)
    if unsupported:
        raise TruthContractError(
            f"tag(s) {unsupported} are not SUPPORTED in configs/eval_tags.yaml (either unknown "
            f"or explicitly disabled) - the truth contract refuses to guess semantics for a tag "
            f"outside the frozen registry. Supported tags: {sorted(supported)}"
        )
    return tags


def _escape(value: str) -> str:
    return value.replace("'", "''")


def build_contract_config(tags: Sequence[str]) -> dict:
    """Deterministic, timestamp-free provenance for the contract as
    applied to a specific `tags` selection. Never hash this dict with a
    timestamp mixed in - see compute_contract_config_hash(). Embeds the
    tag registry's own version/hash so a result can never identify which
    truth-contract code ran without also identifying which tag-registry
    semantics were in effect."""
    tags = _validate_tags(tags)
    registry = get_registry()
    from src.eval.tag_registry import compute_registry_hash
    sorted_tags = sorted(tags)
    return {
        "contract_version": CONTRACT_VERSION,
        "tag_registry_version": registry.version,
        "tag_registry_hash": compute_registry_hash(registry),
        "tags": sorted_tags,
        "qtrs_by_tag": {t: registry.get(t).qtrs for t in sorted_tags},
        "unit_by_tag": {t: registry.get(t).unit for t in sorted_tags},
        "period_type_by_tag": {t: registry.get(t).period_type for t in sorted_tags},
        "form_rule": f"form = '{SUPPORTED_FORM}'",
        "fiscal_year_window_rule": f"fiscal_year BETWEEN {SUPPORTED_FISCAL_YEAR_MIN} AND {SUPPORTED_FISCAL_YEAR_MAX}",
        "coreg_rule": "coreg IS NULL OR coreg = '' (consolidated entity only, no co-registrant/subsidiary rows)",
        "segments_rule": "segments IS NULL OR segments = '' (no segment/dimensional breakdowns)",
        "taxonomy_rule": f"version LIKE '{TAXONOMY_PREFIX}%' (standard us-gaap taxonomy only, no custom extensions)",
        "unit_rule": "per-tag, from configs/eval_tags.yaml (see unit_by_tag) - never a single global unit assumption",
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
            "if this invariant is ever violated"
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
    ground truth, per the frozen contract above. `con` is an already-open
    DuckDB connection (read-only recommended) against `data/xbrl.duckdb` -
    this function issues one SELECT, never a write.

    Deterministic: identical (`con`'s underlying database, `tags`,
    `configs/eval_tags.yaml`) always produces the same rows in the same
    order (explicit ORDER BY, never DuckDB's incidental physical row
    order).

    Raises `TruthContractError` if `tags` contains anything not SUPPORTED
    in the frozen tag registry - never guesses a qtrs/unit value. Raises
    `RuntimeError` if a same-accession grain duplicate with a differing
    value is found after every other filter has already been applied -
    never silently picks one of several conflicting rows.
    """
    tags = _validate_tags(tags)
    if not tags:
        return []

    registry = get_registry()
    tags_sql = ",".join(f"'{_escape(t)}'" for t in tags)
    qtrs_case_sql = " ".join(f"WHEN '{_escape(t)}' THEN {registry.get(t).qtrs}" for t in tags)
    unit_case_sql = " ".join(f"WHEN '{_escape(t)}' THEN '{_escape(registry.get(t).unit)}'" for t in tags)

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
          AND f.value IS NOT NULL
          AND NOT isnan(f.value)
          AND NOT isinf(f.value)
          AND f.qtrs = CASE f.tag {qtrs_case_sql} END
          AND f.uom = CASE f.tag {unit_case_sql} END
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
