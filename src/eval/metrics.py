"""Task 2.6 - deterministic, hand-verifiable evaluation metric functions
(pure, no I/O - no DuckDB, no retrieval, no models, no filesystem).

Every function here takes plain per-question evidence (ranked ID lists,
relevance sets, expected/observed values) and returns a metric value plus
enough per-question diagnostics (first_hit_rank, reciprocal rank, DCG
components) that an aggregate can always be independently recomputed by
someone who does not trust this module (Section 32/33).

Persistence belongs to `src.eval.eval_store`. This module never opens a
database connection, reads TEST, or calls a model.

**doc_recall@10 is NOT reimplemented here** - `src.eval.baseline_metrics`
(Task 1.10) remains the frozen, authoritative implementation of that one
specific metric (exact `document_id` string equality against exactly k
ranked chunk results, no dedup before cutoff, one hit maximum). This
module's `first_hit_rank()` reproduces the identical hit/first-hit-rank
definition generically (any ID granularity, any k) so it can back
`doc_mrr`, `doc_ndcg@10`, and the new `chunk_recall@k`/`chunk_mrr`
metrics without duplicating - or silently diverging from - Task 1.10's
semantics. `tests/test_metrics.py` verifies both implementations agree
on the same fixtures.

Relevance in this project is currently BINARY (a document/chunk either
is or is not gold-relevant) - no graded relevance scale exists anywhere
in Task 2.1-2.4's gold labels, so nDCG here is implemented for binary
relevance only. A future graded-relevance gold label would need a new
metric_version, not a silent change to this one (Section 14/21 of
project_plan/PHASE2_EVALUATION_SCHEMA.md's versioning policy).
"""

from __future__ import annotations

import math
from typing import Sequence


class MetricInputError(ValueError):
    """Raised for malformed metric input (empty applicable set, negative
    denominator, unparseable numeric value, ...) - never silently
    swallowed into a wrong numeric result."""


# --------------------------------------------------------------- rate aggregation
#
# The shared primitive behind doc_recall@k / chunk_recall@k /
# correct_refusal_rate / citation_format_compliance aggregation: a rate
# is numerator/denominator over ONLY the applicable, successfully-scored
# rows the caller passes in. A row that is not applicable to a metric
# (Section 23) or whose question_result.status != "success" (Section 24)
# must never appear in `flags` at all - it is excluded before this
# function is called, never counted as False.

def aggregate_rate(flags: Sequence[bool]) -> dict:
    """flags: one bool per applicable, successfully-scored question -
    True if that question counted as a hit/correct/compliant instance.
    Raises MetricInputError on empty input rather than returning a fake
    0.0 or raising ZeroDivisionError."""
    denominator = len(flags)
    if denominator == 0:
        raise MetricInputError("cannot aggregate a rate over zero applicable questions")
    numerator = sum(1 for f in flags if f)
    return {"value": numerator / denominator, "numerator": numerator, "denominator": denominator}


# --------------------------------------------------------------- first-hit rank
#
# Granularity-agnostic: pass document IDs for document-level metrics,
# gold evidence chunk IDs for chunk-level metrics. Reproduces Task 1.10's
# exact hit definition (string equality, no dedup, minimum matching
# rank) - see module docstring.

def first_hit_rank(ranked_ids: Sequence[str], relevant_ids: set[str], k: int) -> int | None:
    if k < 1:
        raise MetricInputError(f"k must be >= 1, got {k}")
    for rank, item_id in enumerate(ranked_ids[:k], start=1):
        if item_id in relevant_ids:
            return rank
    return None


def hit_at_k(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


# --------------------------------------------------------------- MRR

def reciprocal_rank(rank: int | None) -> float:
    """RR = 1/rank if a relevant result was found, else 0. Never mean
    rank, never 1/mean-rank - those are not MRR (Section 10)."""
    if rank is None:
        return 0.0
    if rank < 1:
        raise MetricInputError(f"rank must be >= 1 or None, got {rank}")
    return 1.0 / rank


def mean_reciprocal_rank(reciprocal_ranks: Sequence[float]) -> float:
    if not reciprocal_ranks:
        raise MetricInputError("cannot compute MRR over zero questions")
    return sum(reciprocal_ranks) / len(reciprocal_ranks)


# --------------------------------------------------------------- precision@k (binary relevance)
#
# Task 3.6 - reuses the same binary relevance vector convention as
# dcg_at_k/idcg_at_k (one hit maximum per relevant item - callers pass a
# relevance vector already deduplicated by e.g.
# `src.eval.phase3_baseline.document_relevances_at_k`, never a second
# dedup implementation here).

def precision_at_k(relevances: Sequence[int], k: int) -> float:
    """Precision@k = (# relevant items in the top k) / k. Requires
    exactly `k` relevance values (never silently pads/truncates a
    shorter list - a caller with fewer than k candidates must decide how
    to represent the missing ranks, not this function)."""
    if k < 1:
        raise MetricInputError(f"k must be >= 1, got {k}")
    if len(relevances) != k:
        raise MetricInputError(f"expected exactly {k} relevance values, got {len(relevances)}")
    for rank, rel in enumerate(relevances, start=1):
        if rel not in (0, 1):
            raise MetricInputError(f"binary relevance required, got {rel!r} at rank {rank}")
    return sum(relevances) / k


# --------------------------------------------------------------- nDCG@k (binary relevance)
#
# Frozen discount convention: gain_i / log2(rank_i + 1) for rank_i
# starting at 1 - the standard convention, adopted explicitly here (not
# silently guessed) because no prior task in this repository defines a
# different one. Binary relevance only (gain in {0, 1}) - this project's
# gold labels do not define relevance grades.

def dcg_at_k(relevances: Sequence[int], k: int) -> float:
    if k < 1:
        raise MetricInputError(f"k must be >= 1, got {k}")
    total = 0.0
    for rank, rel in enumerate(relevances[:k], start=1):
        if rel not in (0, 1):
            raise MetricInputError(f"binary relevance required, got {rel!r} at rank {rank}")
        if rel:
            total += rel / math.log2(rank + 1)
    return total


def idcg_at_k(num_relevant: int, k: int) -> float:
    if k < 1:
        raise MetricInputError(f"k must be >= 1, got {k}")
    if num_relevant < 0:
        raise MetricInputError(f"num_relevant must be >= 0, got {num_relevant}")
    total = 0.0
    for rank in range(1, min(num_relevant, k) + 1):
        total += 1.0 / math.log2(rank + 1)
    return total


def ndcg_at_k(relevances: Sequence[int], num_relevant: int, k: int) -> float | None:
    """None (not applicable) when the gold has zero relevant items for
    this question - a documented, deliberate convention (Section 13),
    never a silent 0.0 that would be indistinguishable from "retrieved
    nothing relevant despite gold existing"."""
    if num_relevant == 0:
        return None
    idcg = idcg_at_k(num_relevant, k)
    if idcg == 0:
        return None
    return dcg_at_k(relevances, k) / idcg


# --------------------------------------------------------------- numeric exact match
#
# Compares CANONICAL parsed numeric values (Task 2.3 stores
# repr(float(...)) strings), never display-formatted strings. Unit
# equality is required - "100 USD" never matches "100 shares" merely
# because the magnitude matches (Section 17 currency/unit safety). No
# currency conversion, no unit inference.

def numeric_exact_match(*, gold_value: str, gold_unit: str, predicted_value: str, predicted_unit: str) -> bool:
    """Raises MetricInputError if either value string is not parseable
    as a float - an invalid/malformed prediction is a real scoring
    event (the caller records numeric_parse_status="invalid" and
    exact_match=False), never silently coerced into a match or a crash."""
    try:
        gold = float(gold_value)
    except (TypeError, ValueError) as exc:
        raise MetricInputError(f"gold_value {gold_value!r} is not a parseable number") from exc
    try:
        predicted = float(predicted_value)
    except (TypeError, ValueError) as exc:
        raise MetricInputError(f"predicted_value {predicted_value!r} is not a parseable number") from exc
    if gold_unit != predicted_unit:
        return False
    return gold == predicted


# --------------------------------------------------------------- correct refusal
#
# Structured comparison only - never fragile substring matching on free
# text (Section 22). `observed_behavior` must be produced by a later,
# separate evaluator/classifier; this function only compares two already-
# structured labels.

def correct_refusal(*, expected_behavior: str, observed_behavior: str) -> bool:
    return expected_behavior == observed_behavior
