"""Task 1.10 - deterministic doc_recall@10 metric logic (pure, no I/O).

Computes the frozen Phase 1 baseline retrieval metric over the Task 1.9
smoke set: for each question, run Task 1.6's retriever at k=10 and check
whether the target document appears among the 10 returned CHUNK results'
document_ids. No document deduplication before the cutoff - the metric
considers exactly the first 10 chunk results, whatever documents they
belong to.

This module has no dependency on the real retriever, LanceDB, or the
embedding model - callers (scripts/run_baseline_metric.py) construct the
real retrieval path and pass in plain per-rank evidence objects (anything
with .rank/.chunk_id/.document_id/.score/.distance), so every function
here is testable with small synthetic fixtures.

NOT an answer-quality metric. NOT a citation-quality metric. Primary
metric name is frozen: doc_recall@10 - never renamed to recall@10,
chunk_recall@10, hit_rate@10, MRR, or accuracy@10.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Sequence


@dataclass(frozen=True)
class QuestionMetricResult:
    question_id: str
    question: str
    category: str
    target_document_id: str
    k: int
    hit: bool
    first_hit_rank: int | None
    retrieved_chunk_ids: list[str]
    retrieved_document_ids: list[str]
    retrieved_scores: list[float]
    retrieved_distances: list[float]


@dataclass(frozen=True)
class CategoryMetricResult:
    question_count: int
    hit_count: int
    doc_recall_at_k: float


@dataclass(frozen=True)
class AggregateMetricResult:
    question_count: int
    hit_count: int
    doc_recall_at_k: float
    category_results: dict[str, CategoryMetricResult] = field(default_factory=dict)
    first_hit_rank_counts: dict[int, int] = field(default_factory=dict)


def evaluate_question(
    *,
    question_id: str,
    question: str,
    category: str,
    target_document_id: str,
    retrieved_results: Sequence,
    k: int,
) -> QuestionMetricResult:
    """Builds one QuestionMetricResult from exactly `k` rank-ordered
    retrieval results (each needing only .rank/.chunk_id/.document_id/
    .score/.distance attributes - duck-typed, never imports the real
    retriever). Raises ValueError - never silently pads/truncates - if
    fewer or more than `k` results are supplied, or if the supplied ranks
    are not exactly 1..k in order.

    A hit is exact string equality of `document_id` against
    `target_document_id` on ANY of the k results - never CIK/company/year/
    fuzzy matching. `first_hit_rank` is the minimum rank among matches
    (None if no hit) - a document appearing at multiple ranks still counts
    as exactly one hit."""
    if len(retrieved_results) != k:
        raise ValueError(f"expected exactly {k} retrieved results, got {len(retrieved_results)}")
    ranks = [r.rank for r in retrieved_results]
    if ranks != list(range(1, k + 1)):
        raise ValueError(f"retrieved_results ranks must be exactly 1..{k} in order, got {ranks}")

    matching_ranks = [r.rank for r in retrieved_results if r.document_id == target_document_id]
    hit = bool(matching_ranks)
    first_hit_rank = min(matching_ranks) if matching_ranks else None

    return QuestionMetricResult(
        question_id=question_id,
        question=question,
        category=category,
        target_document_id=target_document_id,
        k=k,
        hit=hit,
        first_hit_rank=first_hit_rank,
        retrieved_chunk_ids=[r.chunk_id for r in retrieved_results],
        retrieved_document_ids=[r.document_id for r in retrieved_results],
        retrieved_scores=[float(r.score) for r in retrieved_results],
        retrieved_distances=[float(r.distance) for r in retrieved_results],
    )


def summarize_doc_recall(results: Sequence[QuestionMetricResult], *, k: int = 10) -> AggregateMetricResult:
    """Aggregates hit_count/doc_recall_at_k overall and per category, plus
    a descriptive first_hit_rank histogram over ranks 1..k. No rounding
    before returning float values - callers format for display."""
    question_count = len(results)
    hit_count = sum(1 for r in results if r.hit)
    doc_recall = (hit_count / question_count) if question_count else 0.0

    category_accum: dict[str, list[int]] = {}
    for r in results:
        acc = category_accum.setdefault(r.category, [0, 0])
        acc[0] += 1
        acc[1] += 1 if r.hit else 0
    category_results = {
        cat: CategoryMetricResult(
            question_count=qc, hit_count=hc, doc_recall_at_k=(hc / qc) if qc else 0.0,
        )
        for cat, (qc, hc) in category_accum.items()
    }

    first_hit_rank_counts: dict[int, int] = {rank: 0 for rank in range(1, k + 1)}
    for r in results:
        if r.hit and r.first_hit_rank is not None:
            first_hit_rank_counts[r.first_hit_rank] = first_hit_rank_counts.get(r.first_hit_rank, 0) + 1

    return AggregateMetricResult(
        question_count=question_count,
        hit_count=hit_count,
        doc_recall_at_k=doc_recall,
        category_results=category_results,
        first_hit_rank_counts=first_hit_rank_counts,
    )


def canonical_json(obj) -> bytes:
    """Canonical UTF-8 JSON - sorted keys, stable separators - the same
    convention already used throughout this repo for
    development_manifest_sha256/normalization_build_sha256/
    chunk_config_hash/smoke_eval_sha256."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_config_hash(config: dict) -> str:
    """SHA-256 over the canonical JSON of a stable (no-timestamp) config
    dict - metric_run_config_hash. Provenance only, not itself a metric."""
    return hashlib.sha256(canonical_json(config)).hexdigest()


def compute_result_hash(results: Sequence[QuestionMetricResult]) -> str:
    """SHA-256 over the canonical JSON of the logical per-question outputs
    only (question_id, target_document_id, hit, first_hit_rank,
    retrieved_chunk_ids, retrieved_document_ids) - metric_result_sha256.
    Deliberately excludes question/category/scores/distances/timestamps/
    latency so a second fresh-process run with identical retrieval
    identity produces an identical hash even if float score/distance
    values carry GPU floating-point noise across runs."""
    stable = [
        {
            "question_id": r.question_id,
            "target_document_id": r.target_document_id,
            "hit": r.hit,
            "first_hit_rank": r.first_hit_rank,
            "retrieved_chunk_ids": r.retrieved_chunk_ids,
            "retrieved_document_ids": r.retrieved_document_ids,
        }
        for r in results
    ]
    return hashlib.sha256(canonical_json(stable)).hexdigest()
