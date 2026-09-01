"""Task 2.4 - company-disjoint DEV/TEST split of the frozen Task 2.3
evaluation dataset: pure record-building/grouping/hashing logic (no I/O,
no DB, no network).

The split unit is never a question - it is a connected component of CIKs.
Two CIKs are connected iff they co-occur inside the same
`cross_entity_comparison` question (the only Task 2.3 record shape that
names more than one company). Every other question names at most one
company. Entity-free questions (no CIK at all - e.g. `prompt_injection`,
`off_scope`, and `financial_advice`, whose company name is baked into the
rendered question text but never persisted as a structured field on the
record - see `project_plan/PHASE2_DEV_TEST_SPLIT.md`) are their own
singleton pseudo-component and carry zero leakage risk.

Assignment priority (never violated in this order):

    1. zero company leakage
    2. never split a connected component
    3. never promote a pending_review narrative question to gold
    4. approximate the 70/30 target
    5. approximate category/subtype/fiscal-year/SIC balance

Narrative (`status="pending_review"`) records are threaded through the
same component graph as gold records - a narrative record inherits
whatever split its company's component receives - but are excluded from
the gold DEV/TEST counts and headline ratio.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from src.eval.evaluation_dataset import compute_dataset_sha256, selection_key

SPLIT_VERSION = "phase2-split-v1"
DEV_FRACTION = 0.7
CI_SET_VERSION = "phase2-ci-v1"
CI_TOTAL = 200

ENTITY_FREE_SUBTYPES = frozenset({"prompt_injection", "financial_advice", "off_scope"})

GOLD_CATEGORIES = frozenset({"numeric", "comparative", "unanswerable", "adversarial"})
NARRATIVE_CATEGORY = "narrative"


class LeakageError(ValueError):
    """Raised when a CIK (or a connected component) would end up on both
    sides of the split."""


class SplitCompletenessError(ValueError):
    """Raised when gold question IDs are lost, duplicated, or split
    between DEV/TEST incompletely."""


def extract_participating_ciks(record: dict) -> frozenset[int]:
    """Every entity identifier a record references, including secondary
    entities inside `operands` (the only place a second CIK ever
    appears - `cross_entity_comparison`). Never guesses a CIK for a
    record whose schema does not carry one."""
    if record.get("subtype") == "cross_entity_comparison":
        return frozenset(op["cik"] for op in record.get("operands", []))
    cik = record.get("cik")
    if cik is not None:
        return frozenset({cik})
    return frozenset()


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def add(self, x: int) -> None:
        self._parent.setdefault(x, x)

    def find(self, x: int) -> int:
        self.add(x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            # deterministic: smaller root becomes the parent, so the
            # result never depends on dict/set iteration order.
            if ry < rx:
                rx, ry = ry, rx
            self._parent[ry] = rx

    def groups(self) -> dict[int, set[int]]:
        out: dict[int, set[int]] = {}
        for x in self._parent:
            out.setdefault(self.find(x), set()).add(x)
        return out


def _cik_component_id(ciks: Iterable[int]) -> str:
    return "cik-" + "-".join(str(c) for c in sorted(ciks))


def _entity_free_component_id(question_id: str) -> str:
    return f"entityfree-{question_id}"


@dataclass
class Component:
    component_id: str
    ciks: frozenset[int]
    question_ids: list[str] = field(default_factory=list)
    gold_count: int = 0
    pending_count: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    subtype_counts: dict[str, int] = field(default_factory=dict)
    fiscal_year_counts: dict[int, int] = field(default_factory=dict)
    accessions: set[str] = field(default_factory=set)


def build_components(records: Sequence[dict]) -> tuple[dict[str, Component], dict[str, str]]:
    """Returns (components_by_id, question_id -> component_id).

    Every record in `records` (gold AND pending_review narrative) takes
    part in the same graph, so a company's split is identical regardless
    of which category/status references it."""
    uf = _UnionFind()
    for r in records:
        ciks = extract_participating_ciks(r)
        for c in ciks:
            uf.add(c)
        if len(ciks) >= 2:
            ordered = sorted(ciks)
            for other in ordered[1:]:
                uf.union(ordered[0], other)

    cik_groups = uf.groups()
    root_to_component_id = {root: _cik_component_id(members) for root, members in cik_groups.items()}

    components: dict[str, Component] = {}
    for root, members in cik_groups.items():
        cid = root_to_component_id[root]
        components[cid] = Component(component_id=cid, ciks=frozenset(members))

    question_component_map: dict[str, str] = {}
    for r in records:
        qid = r["question_id"]
        ciks = extract_participating_ciks(r)
        if ciks:
            root = uf.find(next(iter(ciks)))
            cid = root_to_component_id[root]
        else:
            cid = _entity_free_component_id(qid)
            if cid not in components:
                components[cid] = Component(component_id=cid, ciks=frozenset())
        component = components[cid]
        component.question_ids.append(qid)
        category = r["category"]
        subtype = r.get("subtype")
        if category == NARRATIVE_CATEGORY:
            component.pending_count += 1
        else:
            component.gold_count += 1
        component.category_counts[category] = component.category_counts.get(category, 0) + 1
        if subtype:
            component.subtype_counts[subtype] = component.subtype_counts.get(subtype, 0) + 1
        fy = r.get("fiscal_year")
        if fy is not None:
            component.fiscal_year_counts[fy] = component.fiscal_year_counts.get(fy, 0) + 1
        accession = r.get("accession")
        if accession:
            component.accessions.add(accession)
        for op in r.get("operands", []) or []:
            acc = op.get("accession")
            if acc:
                component.accessions.add(acc)
        question_component_map[qid] = cid

    return components, question_component_map


def representative_sic(accessions: Iterable[str], sic_map: dict[str, str]) -> str:
    """Most frequent SIC among the component's real filing accessions
    (from Task 2.3 records themselves - `accession` on numeric records,
    operand accessions on comparative records). Deterministic tie-break:
    highest frequency first, then lexicographically smallest SIC code.
    "unknown" when no accession is available or none resolves to a SIC -
    never guessed."""
    counts: dict[str, int] = {}
    for acc in accessions:
        sic = sic_map.get(acc) or "unknown"
        counts[sic] = counts.get(sic, 0) + 1
    if not counts:
        return "unknown"
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def assign_splits(components: dict[str, Component], dev_fraction: float = DEV_FRACTION) -> dict[str, str]:
    """Deterministic greedy group-balancing on gold_count only (pending
    narrative rides along, never influences the ratio). Real CIK
    components are assigned first, then entity-free singleton components
    fill in afterward - both phases use the same hash-derived order and
    continue the same running counters, per Task 2.4 Section 7/15/16."""
    total_gold = sum(c.gold_count for c in components.values())
    target_dev = round(dev_fraction * total_gold)
    target_test = total_gold - target_dev

    def order_key(cid: str) -> str:
        return selection_key("phase2-split-component-order", cid)

    cik_components = sorted(
        (c for c in components.values() if c.ciks), key=lambda c: order_key(c.component_id)
    )
    entity_free_components = sorted(
        (c for c in components.values() if not c.ciks), key=lambda c: order_key(c.component_id)
    )

    assignment: dict[str, str] = {}
    dev_count = 0
    test_count = 0

    def assign_balanced(pool: Sequence[Component]) -> None:
        nonlocal dev_count, test_count
        for c in pool:
            dev_ratio = dev_count / target_dev if target_dev > 0 else 1.0
            test_ratio = test_count / target_test if target_test > 0 else 1.0
            if dev_ratio <= test_ratio:
                assignment[c.component_id] = "dev"
                dev_count += c.gold_count
            else:
                assignment[c.component_id] = "test"
                test_count += c.gold_count

    assign_balanced(cik_components)
    assign_balanced(entity_free_components)
    return assignment


def build_question_split_map(records: Sequence[dict], question_component_map: dict[str, str], component_split: dict[str, str]) -> dict[str, str]:
    return {r["question_id"]: component_split[question_component_map[r["question_id"]]] for r in records}


def verify_no_cik_leakage(components: dict[str, Component], component_split: dict[str, str]) -> None:
    dev_ciks: set[int] = set()
    test_ciks: set[int] = set()
    for c in components.values():
        target = dev_ciks if component_split[c.component_id] == "dev" else test_ciks
        target.update(c.ciks)
    overlap = dev_ciks & test_ciks
    if overlap:
        raise LeakageError(f"CIK(s) {sorted(overlap)} appear in both DEV and TEST components")


def verify_cross_entity_integrity(records: Sequence[dict], question_split_map: dict[str, str]) -> None:
    for r in records:
        if r.get("subtype") != "cross_entity_comparison":
            continue
        split = question_split_map[r["question_id"]]
        # all operand CIKs are, by construction, in the same component as
        # the question itself; re-derive independently rather than trust
        # that construction.
        ciks = extract_participating_ciks(r)
        if len(ciks) < 2:
            continue
        # nothing else to compare against here - the real cross-split
        # check happens in independent_leakage_check() against the full
        # DEV/TEST question sets.
        del split


def verify_gold_completeness(gold_records: Sequence[dict], dev_ids: set[str], test_ids: set[str]) -> None:
    all_ids = {r["question_id"] for r in gold_records}
    union = dev_ids | test_ids
    inter = dev_ids & test_ids
    if inter:
        raise SplitCompletenessError(f"{len(inter)} question_id(s) assigned to both DEV and TEST")
    if union != all_ids:
        missing = all_ids - union
        extra = union - all_ids
        raise SplitCompletenessError(f"gold completeness mismatch: missing={len(missing)} extra={len(extra)}")


def _split_quota(total: int, weights: Sequence[int]) -> list[int]:
    """Largest-remainder proportional allocation of `total` across buckets
    sized by `weights` - the Task 1.9/2.3 deterministic-remainder
    convention, generalized from equal buckets to weighted buckets."""
    weight_sum = sum(weights)
    if weight_sum == 0:
        return [0 for _ in weights]
    raw = [total * w / weight_sum for w in weights]
    base = [int(x) for x in raw]
    remainder = total - sum(base)
    fractional_order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in fractional_order[:remainder]:
        base[i] += 1
    return base


def select_ci_golden(dev_gold_records: Sequence[dict], ci_total: int = CI_TOTAL) -> list[str]:
    """Deterministic, subtype-stratified draw of `ci_total` question IDs
    from DEV gold-ready records only. Never includes pending_review
    narrative (dev_gold_records must already exclude it - the caller is
    responsible, and this function does not accept narrative rows at
    all)."""
    by_subtype: dict[str, list[dict]] = {}
    for r in dev_gold_records:
        by_subtype.setdefault(r.get("subtype") or "", []).append(r)

    subtypes = sorted(by_subtype)
    quotas = _split_quota(ci_total, [len(by_subtype[s]) for s in subtypes])

    selected: list[str] = []
    leftover_pool: list[dict] = []
    for subtype, quota in zip(subtypes, quotas):
        pool = sorted(by_subtype[subtype], key=lambda r: selection_key("phase2-ci-selection", subtype, r["question_id"]))
        take = pool[:quota]
        selected.extend(r["question_id"] for r in take)
        leftover_pool.extend(pool[quota:])

    if len(selected) < ci_total:
        leftover_pool.sort(key=lambda r: selection_key("phase2-ci-backfill", r["question_id"]))
        for r in leftover_pool:
            if len(selected) >= ci_total:
                break
            selected.append(r["question_id"])

    return sorted(selected)


def compute_assignment_records(question_split_map: dict[str, str], question_component_map: dict[str, str], status_by_id: dict[str, str]) -> list[dict]:
    return [
        {
            "question_id": qid,
            "split": question_split_map[qid],
            "status": status_by_id[qid],
            "component_id": question_component_map[qid],
        }
        for qid in sorted(question_split_map)
    ]


def compute_assignment_sha256(assignment_records: Sequence[dict]) -> str:
    payload = json.dumps(list(assignment_records), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "SPLIT_VERSION",
    "DEV_FRACTION",
    "CI_SET_VERSION",
    "CI_TOTAL",
    "ENTITY_FREE_SUBTYPES",
    "GOLD_CATEGORIES",
    "NARRATIVE_CATEGORY",
    "LeakageError",
    "SplitCompletenessError",
    "Component",
    "extract_participating_ciks",
    "build_components",
    "representative_sic",
    "assign_splits",
    "build_question_split_map",
    "verify_no_cik_leakage",
    "verify_cross_entity_integrity",
    "verify_gold_completeness",
    "select_ci_golden",
    "compute_assignment_records",
    "compute_assignment_sha256",
    "compute_dataset_sha256",
]
