"""Task 2.7 - MS MARCO benchmark harness: pure logic (ID normalization,
qrel grouping, per-query/aggregate metric computation, canonical
hashing). No I/O - see scripts/run_msmarco_harness.py for corpus/query/
qrel loading, embedding, indexing, and retrieval orchestration.

MS MARCO exists in this repository purely as a harness-correctness
check - a standard benchmark with known queries and known qrels lets us
verify that loading, retrieval, and Task 2.6's metric implementations
agree with expected/published behavior BEFORE trusting any SEC
retrieval score. It is a BENCHMARK TRACK, never merged with the SEC
corpus, SEC chunk/index tables, or the SEC Phase 2 evaluation dataset.

MS MARCO relevance is PASSAGE-level, not SEC document/chunk-level -
metric names here are deliberately `passage_recall@k`/`passage_mrr`/
`passage_ndcg@k`, never `doc_recall@10` (that name is reserved for
Task 1.10's SEC document-level metric and must never be reused for a
different corpus/granularity).

Reuses Task 2.6's `src.eval.metrics` functions directly (`first_hit_rank`,
`reciprocal_rank`/`mean_reciprocal_rank`, `dcg_at_k`/`idcg_at_k`/
`ndcg_at_k`, `aggregate_rate`) - MS MARCO qrels are confirmed binary
(every qrels_validation.parquet row has score=1; verified directly from
the data, never assumed), so Task 2.6's binary-relevance nDCG applies
without modification. Recall here is NOT `hit_at_k` reused verbatim,
because a query can have multiple qrels (median 1, max 4, 390/6,980
queries with >1) - MS MARCO Recall@K is
`|retrieved[:k] ∩ relevant| / |relevant|` (fraction of relevant passages
retrieved), a genuinely different aggregation from SEC's single-target
`hit_at_k`. This benchmark-specific recall is implemented here, not by
misusing `src.eval.metrics.hit_at_k`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Sequence

from src.eval.metrics import (
    MetricInputError,
    reciprocal_rank,
    mean_reciprocal_rank,
    ndcg_at_k,
)

BENCHMARK_ID = "msmarco-dev-small-v1"
BENCHMARK_CONFIG_VERSION = "1.0"

# Verified directly from data/msmarco/*.parquet before any code was
# written - see project_plan/PHASE2_MSMARCO_HARNESS.md.
EXPECTED_CORPUS_COUNT = 8_841_823
EXPECTED_TOTAL_QUERY_COUNT = 509_962
EXPECTED_VALIDATION_QREL_COUNT = 7_437
EXPECTED_VALIDATION_QUERY_COUNT = 6_980


def canonical_id(raw) -> str:
    """Normalizes an MS MARCO identifier to its canonical string form.
    Corpus/query Parquet files store `_id` as VARCHAR digit strings
    ("0", "1", "1185869", ...); qrels_validation.parquet stores
    `query-id`/`corpus-id` as BIGINT. `str(int(x))` is the canonical form
    both sides must agree on - verified against real data to have no
    leading zeros or non-numeric characters before this convention was
    adopted (never assumed)."""
    return str(int(raw))


@dataclass(frozen=True)
class QrelSet:
    """Relevant passage IDs (canonical strings) for one query - MS MARCO
    qrels_validation.parquet is confirmed 100% binary relevance (every
    row score=1), so this is just a set, not a {id: grade} mapping."""
    query_id: str
    relevant_ids: frozenset[str]


def group_qrels(qrel_rows: Sequence[dict]) -> dict[str, QrelSet]:
    """qrel_rows: dicts with 'query-id' and 'corpus-id' keys (raw, any
    int/str form) - one row per (query, relevant passage) pair. Never
    drops a secondary qrel: every row for a query_id is folded into that
    query's relevant_ids set."""
    grouped: dict[str, set[str]] = {}
    for row in qrel_rows:
        qid = canonical_id(row["query-id"])
        cid = canonical_id(row["corpus-id"])
        grouped.setdefault(qid, set()).add(cid)
    return {qid: QrelSet(query_id=qid, relevant_ids=frozenset(ids)) for qid, ids in grouped.items()}


@dataclass(frozen=True)
class QueryResult:
    """One query's retrieval outcome plus per-query metric diagnostics -
    enough to independently recompute any aggregate without re-running
    retrieval."""
    query_id: str
    retrieved_ids: tuple[str, ...]  # rank-ordered, canonical, length <= top_k
    relevant_ids: frozenset[str]
    first_hit_rank: int | None
    hits_in_top_k: int
    passage_recall_at_k: float | None  # None only if relevant_ids is empty (never occurs for real qrels)
    reciprocal_rank_value: float
    ndcg_at_k_value: float | None


def evaluate_query(*, query_id: str, retrieved_ids: Sequence[str], relevant_ids: frozenset[str], k: int) -> QueryResult:
    if k < 1:
        raise MetricInputError(f"k must be >= 1, got {k}")
    if len(retrieved_ids) > k:
        raise MetricInputError(f"retrieved_ids longer than k={k}: {len(retrieved_ids)}")
    if len(set(retrieved_ids)) != len(retrieved_ids):
        raise MetricInputError(f"query {query_id!r}: duplicate passage ID in retrieved_ids")

    window = list(retrieved_ids[:k])
    hits_in_top_k = sum(1 for rid in window if rid in relevant_ids)
    first_hit = None
    for rank, rid in enumerate(window, start=1):
        if rid in relevant_ids:
            first_hit = rank
            break

    recall = (hits_in_top_k / len(relevant_ids)) if relevant_ids else None
    rr = reciprocal_rank(first_hit)
    relevances = [1 if rid in relevant_ids else 0 for rid in window]
    ndcg = ndcg_at_k(relevances, num_relevant=len(relevant_ids), k=k)

    return QueryResult(
        query_id=query_id, retrieved_ids=tuple(window), relevant_ids=relevant_ids,
        first_hit_rank=first_hit, hits_in_top_k=hits_in_top_k,
        passage_recall_at_k=recall, reciprocal_rank_value=rr, ndcg_at_k_value=ndcg,
    )


@dataclass(frozen=True)
class AggregateResult:
    query_count: int
    passage_recall_at_k: dict  # {value, numerator, denominator} - see note below
    passage_mrr: float
    passage_ndcg_at_k: float


def aggregate_results(results: Sequence[QueryResult], k: int) -> AggregateResult:
    """`passage_recall_at_k` is reported as a mean-of-per-query-recall
    (the standard MS MARCO/BEIR convention: average the per-query
    fraction-of-relevant-retrieved, not a pooled hit-count ratio) - the
    {numerator, denominator} pair here is a diagnostic sum-of-hits /
    sum-of-relevant for audit purposes, NOT what `value` is computed
    from (documented explicitly to avoid the false impression that
    value == numerator/denominator, which would only be true if every
    query had exactly one qrel)."""
    if not results:
        raise MetricInputError("cannot aggregate over zero queries")
    recalls = [r.passage_recall_at_k for r in results if r.passage_recall_at_k is not None]
    if len(recalls) != len(results):
        raise MetricInputError("every query must have at least one qrel to compute passage_recall_at_k")
    mean_recall = sum(recalls) / len(recalls)
    total_hits = sum(r.hits_in_top_k for r in results)
    total_relevant = sum(len(r.relevant_ids) for r in results)

    mrr = mean_reciprocal_rank([r.reciprocal_rank_value for r in results])

    ndcg_values = [r.ndcg_at_k_value for r in results if r.ndcg_at_k_value is not None]
    mean_ndcg = sum(ndcg_values) / len(ndcg_values) if ndcg_values else 0.0

    return AggregateResult(
        query_count=len(results),
        passage_recall_at_k={"value": mean_recall, "numerator": total_hits, "denominator": total_relevant},
        passage_mrr=mrr,
        passage_ndcg_at_k=mean_ndcg,
    )


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_config_hash(config: dict) -> str:
    return hashlib.sha256(canonical_json(config)).hexdigest()


def compute_result_hash(results: Sequence[QueryResult]) -> str:
    """SHA-256 over the canonical JSON of the logical per-query outputs
    only (query_id, retrieved_ids, first_hit_rank, hits_in_top_k,
    passage_recall_at_k, reciprocal_rank_value, ndcg_at_k_value) -
    deliberately excludes any timestamp so two independent evaluation
    passes over identical saved retrieval output produce an identical
    hash."""
    stable = [
        {
            "query_id": r.query_id,
            "retrieved_ids": list(r.retrieved_ids),
            "first_hit_rank": r.first_hit_rank,
            "hits_in_top_k": r.hits_in_top_k,
            "passage_recall_at_k": r.passage_recall_at_k,
            "reciprocal_rank_value": r.reciprocal_rank_value,
            "ndcg_at_k_value": r.ndcg_at_k_value,
        }
        for r in sorted(results, key=lambda r: r.query_id)
    ]
    return hashlib.sha256(canonical_json(stable)).hexdigest()
