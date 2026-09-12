"""Task 3.1 - pure logic for Phase 3's trusted DEV baseline (row 0 of the
ablation table): no I/O, no DuckDB, no LanceDB, no model loading, no
network, and - critically - no dependency on `src.eval.test_access` /
`load_test_set()` anywhere in this module. Baseline capture uses DEV only.

This module answers three questions that must be settled BEFORE any
retrieval call is made:

    1. Is a DEV question retrieval-applicable at all (`classify_applicability`)?
    2. If so, what document(s) must be retrieved to count as a hit
       (`question_target_document_ids`)?
    3. Is that target actually present in the CURRENT Phase 1 index
       (`audit_question_coverage`), or would scoring it be penalizing the
       retriever for a document that was never embedded (Section: "an
       out-of-corpus target is not a retrieval miss")?

Coverage audit (2026-09-08, user-approved): the Phase 1 index covers only
89/1,819 (4.9%) retrieval-applicable DEV questions fully - Task 2.3's eval
set was generated from the full XBRL population, independently of the
1,500-filing Phase 1 development corpus. Building an evaluation-only DEV
corpus for the 1,875 missing documents (Stage 2's "Option B") would exceed
the entire existing dev corpus in size - not "small development scale" -
so the user selected Option A: freeze DEV INTERSECT {questions fully
covered by the current Phase 1 index} as an immutable, deterministic
`phase3_dev_scope`, labeled `DEV/evaluable-subset`, never "full DEV".

Document identity rule (verified directly against the live Phase 1 index,
never assumed): `document_id = f"{cik}_{fiscal_year}.htm"` - the same
identity `src/normalize` already writes for every EDGAR-CORPUS document.

`doc_recall@10`/`doc_mrr`/`doc_ndcg@10` computation itself is NOT
reimplemented here - callers use `src.eval.baseline_metrics.evaluate_question`/
`summarize_doc_recall` (Task 1.10, exact single-target-document semantics -
a perfect fit, since every question in the frozen Option A scope has
exactly one gold target document) and `src.eval.metrics.first_hit_rank`/
`reciprocal_rank`/`ndcg_at_k`/`hit_at_k` (Task 2.6, generic granularity)
for the Phase 3 `doc_recall@50` diagnostic. This module only decides WHICH
questions are in scope and WHAT their gold target is.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.artifacts.versioning import semantic_hash

PHASE3_TASK = "3.1"
BASELINE_NAME = "vector_baseline_phase1"
PHASE3_DEV_SCOPE_KIND = "fixed_evaluable_subset_v1"
RETRIEVAL_TYPE = "vector_exact_cosine"
RETRIEVAL_TOP_K = 50
DOC_RECALL_K = 10

# The CSV/JSON sentinel for "no valid gold / not computed" - NEVER the
# number 0, which would be indistinguishable from a real zero score.
NA = "N/A"

# (category, subtype) shapes whose gold target is exactly ONE document.
SINGLE_TARGET_SHAPES: frozenset[tuple[str, str]] = frozenset({
    ("numeric", "xbrl_fact"),
    ("unanswerable", "unsupported_tag"),
})

# (category, subtype) shapes whose gold target is TWO OR MORE documents -
# retrieval-applicable, but never part of the frozen Option A scope below
# (zero of them achieved full coverage in the Stage 2 audit).
MULTI_TARGET_SHAPES: frozenset[tuple[str, str]] = frozenset({
    ("comparative", "year_over_year_difference"),
    ("comparative", "cross_entity_comparison"),
})

# (category, subtype) shapes with NO defensible retrieval target at all -
# entity-free adversarial questions, and unanswerable questions whose
# fiscal year is outside the corpus's supported 2016-2020 window by
# construction (Section: "do not invent a retrieval target when the
# metric is not applicable").
NOT_APPLICABLE_SHAPES: frozenset[tuple[str, str]] = frozenset({
    ("unanswerable", "year_outside_window"),
    ("adversarial", "prompt_injection"),
    ("adversarial", "financial_advice"),
    ("adversarial", "off_scope"),
})


class Phase3BaselineError(ValueError):
    """Raised for a malformed question record, an unrecognized (category,
    subtype) shape, an artifact-identity mismatch, or an ablation-table
    freeze violation - never silently worked around."""


# --------------------------------------------------------------- document identity

def document_id_for(cik: int, fiscal_year: int) -> str:
    """The Phase 1 EDGAR-CORPUS document identity - verified directly
    against the live index (`{cik}_{fiscal_year}.htm`), never guessed."""
    if isinstance(cik, bool) or not isinstance(cik, int):
        raise Phase3BaselineError(f"cik must be an int, got {cik!r}")
    if isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int):
        raise Phase3BaselineError(f"fiscal_year must be an int, got {fiscal_year!r}")
    return f"{cik}_{fiscal_year}.htm"


def _dedup_preserve_order(ids: Sequence[str]) -> list[str]:
    seen: list[str] = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen


def document_relevances_at_k(ranked_document_ids: Sequence[str], target_document_id: str, k: int) -> list[int]:
    """Binary relevance vector for document-level nDCG@k, over a
    CHUNK-ranked result list. A document can supply multiple chunks to
    the same top-k window - marking every occurrence relevant would let a
    single relevant document be credited more than once and push DCG past
    IDCG(num_relevant=1) (verified directly: this exact bug produced
    ndcg@10=2.28 on the first formal run). Only the FIRST occurrence of
    `target_document_id` is marked 1; every later occurrence of the same
    document is 0 - "one hit maximum", identical to Task 1.10's own
    document-hit definition and to `first_hit_rank()`'s MINIMUM-matching-
    rank convention."""
    relevances: list[int] = []
    matched = False
    for document_id in ranked_document_ids[:k]:
        if not matched and document_id == target_document_id:
            relevances.append(1)
            matched = True
        else:
            relevances.append(0)
    return relevances


# --------------------------------------------------------------- applicability

def question_shape(question: Mapping[str, Any]) -> tuple[str, str | None]:
    return (question["category"], question.get("subtype"))


def classify_applicability(question: Mapping[str, Any]) -> str:
    """Returns "applicable" or "not_applicable". Raises Phase3BaselineError
    for a (category, subtype) shape this module has never seen - never
    silently defaults an unknown shape to either bucket."""
    shape = question_shape(question)
    if shape in SINGLE_TARGET_SHAPES or shape in MULTI_TARGET_SHAPES:
        return "applicable"
    if shape in NOT_APPLICABLE_SHAPES:
        return "not_applicable"
    raise Phase3BaselineError(f"unrecognized question shape for applicability classification: {shape}")


def question_target_document_ids(question: Mapping[str, Any]) -> list[str]:
    """The gold target document_id(s) for a retrieval-applicable question,
    deduplicated, order-preserving. Raises for a not-applicable question -
    callers must call classify_applicability() first and never invent a
    target for a shape that has none."""
    shape = question_shape(question)
    if shape in (("numeric", "xbrl_fact"), ("unanswerable", "unsupported_tag")):
        return [document_id_for(question["cik"], question["fiscal_year"])]
    if shape == ("comparative", "year_over_year_difference"):
        return _dedup_preserve_order(
            [document_id_for(question["cik"], op["fiscal_year"]) for op in question["operands"]]
        )
    if shape == ("comparative", "cross_entity_comparison"):
        return _dedup_preserve_order(
            [document_id_for(op["cik"], question["fiscal_year"]) for op in question["operands"]]
        )
    raise Phase3BaselineError(
        f"question shape {shape} is not retrieval-applicable - call classify_applicability() first"
    )


# --------------------------------------------------------------- coverage audit

class CoverageResult:
    __slots__ = ("question_id", "shape", "applicability", "target_document_ids", "covered_document_ids", "coverage")

    def __init__(self, question_id: str, shape: tuple[str, str | None], applicability: str,
                 target_document_ids: tuple[str, ...], covered_document_ids: tuple[str, ...], coverage: str) -> None:
        self.question_id = question_id
        self.shape = shape
        self.applicability = applicability
        self.target_document_ids = target_document_ids
        self.covered_document_ids = covered_document_ids
        self.coverage = coverage  # "full" | "partial" | "none" | "na"


def audit_question_coverage(question: Mapping[str, Any], index_document_ids: Sequence[str] | set[str]) -> CoverageResult:
    index_ids = index_document_ids if isinstance(index_document_ids, set) else set(index_document_ids)
    applicability = classify_applicability(question)
    if applicability == "not_applicable":
        return CoverageResult(question["question_id"], question_shape(question), "not_applicable", (), (), "na")
    targets = tuple(question_target_document_ids(question))
    covered = tuple(t for t in targets if t in index_ids)
    if len(covered) == len(targets):
        coverage = "full"
    elif covered:
        coverage = "partial"
    else:
        coverage = "none"
    return CoverageResult(question["question_id"], question_shape(question), "applicable", targets, covered, coverage)


def audit_dev_coverage(dev_questions: Sequence[Mapping[str, Any]], index_document_ids: Sequence[str] | set[str]) -> dict:
    """Aggregate coverage report - overall counts plus a per-(category,
    subtype) breakdown. Never mutates the caller's inputs."""
    index_ids = index_document_ids if isinstance(index_document_ids, set) else set(index_document_ids)
    results = [audit_question_coverage(q, index_ids) for q in dev_questions]

    by_shape: dict[str, dict[str, int]] = {}
    for r in results:
        key = f"{r.shape[0]}/{r.shape[1]}"
        acc = by_shape.setdefault(key, {"applicable": 0, "full": 0, "partial": 0, "none": 0, "not_applicable": 0})
        if r.applicability == "not_applicable":
            acc["not_applicable"] += 1
        else:
            acc["applicable"] += 1
            acc[r.coverage] += 1

    summary = {
        "total_questions": len(results),
        "retrieval_applicable": sum(1 for r in results if r.applicability == "applicable"),
        "fully_covered": sum(1 for r in results if r.coverage == "full"),
        "partially_covered": sum(1 for r in results if r.coverage == "partial"),
        "not_covered": sum(1 for r in results if r.coverage == "none"),
        "not_applicable": sum(1 for r in results if r.applicability == "not_applicable"),
        "by_shape": by_shape,
    }
    return summary, results


# --------------------------------------------------------------- frozen Phase 3 DEV scope

def select_phase3_dev_scope(dev_questions: Sequence[Mapping[str, Any]], index_document_ids: Sequence[str] | set[str]) -> list[str]:
    """Deterministic Option A scope: every DEV question that is
    retrieval-applicable AND whose entire gold target-document set is
    present in the current Phase 1 index (coverage == "full"). A
    partially- or non-covered question is EXCLUDED from the scope, never
    scored as a miss (Section: "an out-of-corpus target is not a
    retrieval miss"). Sorted question_id order - never insertion order -
    so the returned list (and any hash over it) is reproducible
    regardless of the caller's iteration order."""
    _, results = audit_dev_coverage(dev_questions, index_document_ids)
    return sorted(r.question_id for r in results if r.coverage == "full")


def compute_phase3_dev_scope_sha256(question_ids: Sequence[str]) -> str:
    """Identity of the frozen scope DEFINITION (kind + exact ID set) -
    Task 2.10's semantic_hash(), never a second hashing implementation."""
    return semantic_hash({"phase3_dev_scope_kind": PHASE3_DEV_SCOPE_KIND, "question_ids": sorted(question_ids)})


def compute_question_ids_sha256(question_ids: Sequence[str]) -> str:
    """A simpler, independently-checkable hash of just the sorted ID list
    itself - lets a reader verify the frozen scope's membership without
    first having to trust this module's scope-selection algorithm."""
    return semantic_hash(sorted(question_ids))


# --------------------------------------------------------------- baseline config

def build_phase3_config(
    *, eval_set_version: str, source_dataset_sha256: str, split_version: str, split_assignment_sha256: str,
    phase3_dev_scope_sha256: str, question_count: int, question_ids_sha256: str,
    normalizer_version: str, normalization_build_sha256: str,
    chunk_config_hash: str, chunk_schema_version: int,
    embedding_model: str, embedding_revision: str, embedding_identity_hash: str,
    index_identity_hash: str, distance_metric: str, index_type: str,
    metric_schema_version: int, evaluation_schema_hash: str, git_sha: str,
) -> dict:
    return {
        "phase3_task": PHASE3_TASK,
        "baseline_name": BASELINE_NAME,
        "evaluation_source": "internal_phase2",
        "split": "dev",
        "eval_set_version": eval_set_version,
        "source_dataset_sha256": source_dataset_sha256,
        "split_version": split_version,
        "split_assignment_sha256": split_assignment_sha256,
        "phase3_dev_scope_kind": PHASE3_DEV_SCOPE_KIND,
        "phase3_dev_scope_sha256": phase3_dev_scope_sha256,
        "question_count": question_count,
        "question_ids_sha256": question_ids_sha256,
        "normalizer_version": normalizer_version,
        "normalization_build_sha256": normalization_build_sha256,
        "chunk_config_hash": chunk_config_hash,
        "chunk_schema_version": chunk_schema_version,
        "embedding_model": embedding_model,
        "embedding_revision": embedding_revision,
        "embedding_identity_hash": embedding_identity_hash,
        "index_identity_hash": index_identity_hash,
        "distance_metric": distance_metric,
        "index_type": index_type,
        "retrieval_type": RETRIEVAL_TYPE,
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "generation_enabled": False,
        "metric_schema_version": metric_schema_version,
        "evaluation_schema_hash": evaluation_schema_hash,
        "metrics_requested": ["doc_recall@10", "doc_mrr", "doc_ndcg@10", "doc_recall@50 (Phase 3 diagnostic)"],
        "git_sha": git_sha,
    }


def compute_phase3_config_hash(config: Mapping[str, Any]) -> str:
    """git_sha is provenance (when/where), never semantic (what) - excluded
    from the hash exactly like Task 2.10's PROVENANCE_FIELDS convention,
    so re-running the identical configuration from a later commit (e.g. a
    docs-only commit) still reproduces the same config hash."""
    semantic = {k: v for k, v in config.items() if k != "git_sha"}
    return semantic_hash(semantic)


def verify_artifact_identities(config: Mapping[str, Any], *, live_chunk_config_hash: str,
                                live_embedding_identity_hash: str, live_index_identity_hash: str) -> None:
    """Hard-fails (Phase3BaselineError) the instant a frozen config
    disagrees with the live Phase 1 artifacts it claims to describe -
    never a silent fallback to whichever artifact happens to be on disk."""
    if config["chunk_config_hash"] != live_chunk_config_hash:
        raise Phase3BaselineError(
            f"config chunk_config_hash={config['chunk_config_hash']} != live artifact {live_chunk_config_hash}"
        )
    if config["embedding_identity_hash"] != live_embedding_identity_hash:
        raise Phase3BaselineError(
            f"config embedding_identity_hash={config['embedding_identity_hash']} != "
            f"live artifact {live_embedding_identity_hash}"
        )
    if config["index_identity_hash"] != live_index_identity_hash:
        raise Phase3BaselineError(
            f"config index_identity_hash={config['index_identity_hash']} != live artifact {live_index_identity_hash}"
        )


# --------------------------------------------------------------- ablation table

_ABLATION_TABLE_COLUMNS_V1: tuple[str, ...] = (
    "row_id", "configuration", "status", "run_id", "git_sha", "phase3_config_hash",
    "eval_split", "eval_scope_kind", "eval_scope_sha256", "question_count",
    "corpus_document_count", "chunk_count", "chunk_config_hash", "embedding_model",
    "embedding_revision", "embedding_identity", "index_identity",
    "retrieval", "candidate_k",
    "doc_recall_at_10", "doc_recall_at_50", "doc_mrr", "doc_ndcg_at_10", "precision_at_5", "refusal_metric",
    "retrieval_latency_p50_ms", "retrieval_latency_p95_ms", "query_embedding_latency_p50_ms",
    "search_latency_p50_ms", "index_size_bytes", "notes",
)

# Task 3.4 - additive sparse-baseline columns, single source of truth
# (`src.eval.phase3_sparse` imports this tuple rather than redefining it).
# `_row_to_csv_dict()` below already defaults any column absent from an
# existing row's dict to `NA`, so every prior row (0, A0-C1, the four
# Task 3.3 embedding candidates) keeps its own values byte-for-byte
# identical and simply gains these columns with value `NA` - never a
# breaking schema change.
ABLATION_TABLE_SPARSE_EXTRA_COLUMNS: tuple[str, ...] = (
    "retrieval_mode", "sparse_backend", "lancedb_version", "fts_indexed_column",
    "dense_used_in_this_row",
    "delta_vs_qwen_dense_recall10", "delta_vs_qwen_dense_recall50",
    "delta_vs_qwen_dense_mrr", "delta_vs_qwen_dense_ndcg10",
    "dense_only_hits_at_10", "sparse_only_hits_at_10",
    "dense_only_hits_at_50", "sparse_only_hits_at_50",
    "fts_build_seconds", "fts_index_size_bytes",
    "fts_search_latency_p50_ms", "fts_search_latency_p95_ms",
)

ABLATION_TABLE_COLUMNS: tuple[str, ...] = _ABLATION_TABLE_COLUMNS_V1 + ABLATION_TABLE_SPARSE_EXTRA_COLUMNS


def build_row0(
    *, run_id: str, git_sha: str, phase3_config_hash: str, eval_scope_sha256: str, question_count: int,
    corpus_document_count: int, chunk_count: int, chunk_config_hash: str, embedding_model: str,
    embedding_revision: str, embedding_identity: str, index_identity: str, candidate_k: int,
    doc_recall_at_10: float, doc_recall_at_50: float, doc_mrr: float, doc_ndcg_at_10: float,
    retrieval_latency_p50_ms: float, retrieval_latency_p95_ms: float,
    query_embedding_latency_p50_ms: float, search_latency_p50_ms: float,
    index_size_bytes: int | str, notes: str,
) -> dict:
    """Row 0: the pre-optimization Phase 1 architecture, trusted-baseline
    status. `precision_at_5`/`refusal_metric` are always N/A here -
    neither is available with generation disabled - never a fake 0."""
    return {
        "row_id": 0,
        "configuration": BASELINE_NAME,
        "status": "trusted_baseline",
        "run_id": run_id,
        "git_sha": git_sha,
        "phase3_config_hash": phase3_config_hash,
        "eval_split": "dev",
        "eval_scope_kind": PHASE3_DEV_SCOPE_KIND,
        "eval_scope_sha256": eval_scope_sha256,
        "question_count": question_count,
        "corpus_document_count": corpus_document_count,
        "chunk_count": chunk_count,
        "chunk_config_hash": chunk_config_hash,
        "embedding_model": embedding_model,
        "embedding_revision": embedding_revision,
        "embedding_identity": embedding_identity,
        "index_identity": index_identity,
        "retrieval": RETRIEVAL_TYPE,
        "candidate_k": candidate_k,
        "doc_recall_at_10": doc_recall_at_10,
        "doc_recall_at_50": doc_recall_at_50,
        "doc_mrr": doc_mrr,
        "doc_ndcg_at_10": doc_ndcg_at_10,
        "precision_at_5": NA,
        "refusal_metric": NA,
        "retrieval_latency_p50_ms": retrieval_latency_p50_ms,
        "retrieval_latency_p95_ms": retrieval_latency_p95_ms,
        "query_embedding_latency_p50_ms": query_embedding_latency_p50_ms,
        "search_latency_p50_ms": search_latency_p50_ms,
        "index_size_bytes": index_size_bytes,
        "notes": notes,
    }


def _row_to_csv_dict(row: Mapping[str, Any]) -> dict:
    out = {}
    for col in ABLATION_TABLE_COLUMNS:
        v = row.get(col, NA)
        out[col] = NA if v is None else v
    return out


def load_ablation_table(path: Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_ablation_table(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ABLATION_TABLE_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(_row_to_csv_dict(r))


def upsert_row(rows: Sequence[Mapping[str, Any]], new_row: Mapping[str, Any]) -> list[dict]:
    """Freeze-aware upsert (Section: "No future task may overwrite row 0",
    generalized to every row_id). A row_id that already exists must carry
    an identical `phase3_config_hash` - the write is then a safe,
    idempotent no-op (the table is returned unchanged). A different
    `phase3_config_hash` for an existing row_id is refused outright
    (Phase3BaselineError) - a row is never silently replaced with a
    different configuration. A brand-new row_id is appended."""
    rows = list(rows)
    new_row_id = str(new_row["row_id"])
    matches = [r for r in rows if str(r["row_id"]) == new_row_id]
    if len(matches) > 1:
        raise Phase3BaselineError(f"corrupt ablation table: duplicate row_id {new_row_id} already present")
    if matches:
        existing = matches[0]
        existing_hash = existing.get("phase3_config_hash")
        new_hash = new_row.get("phase3_config_hash")
        if existing_hash != new_hash:
            raise Phase3BaselineError(
                f"row_id={new_row_id} is already frozen with phase3_config_hash={existing_hash!r}; "
                f"refusing to silently replace it with phase3_config_hash={new_hash!r}"
            )
        return rows  # idempotent no-op - identical configuration, nothing to change
    return rows + [dict(new_row)]


# --------------------------------------------------------------- result summary

def build_result_summary(
    *, run_id: str, git_sha: str, phase3_config: Mapping[str, Any], phase3_config_hash: str,
    question_count: int, metrics: Mapping[str, Any], stage_timings_ms: Mapping[str, Any],
    question_ids: Sequence[str],
) -> dict:
    """The tracked `results/phase_3_1_trusted_baseline.json` payload.
    Deliberately carries `run_id`/`git_sha`/`phase3_config_hash` explicitly
    (Section: "result JSON contains config hash + git SHA + run_id") even
    though they are also derivable from the linked Task 2.11 run record."""
    return {
        "task": PHASE3_TASK,
        "run_id": run_id,
        "git_sha": git_sha,
        "phase3_config": dict(phase3_config),
        "phase3_config_hash": phase3_config_hash,
        "eval_split": "dev",
        "eval_scope_kind": PHASE3_DEV_SCOPE_KIND,
        "question_count": question_count,
        "question_ids": sorted(question_ids),
        "metrics": dict(metrics),
        "stage_timings_ms": dict(stage_timings_ms),
    }


__all__ = [
    "PHASE3_TASK", "BASELINE_NAME", "PHASE3_DEV_SCOPE_KIND", "RETRIEVAL_TYPE",
    "RETRIEVAL_TOP_K", "DOC_RECALL_K", "NA",
    "SINGLE_TARGET_SHAPES", "MULTI_TARGET_SHAPES", "NOT_APPLICABLE_SHAPES",
    "Phase3BaselineError", "document_id_for", "question_shape",
    "classify_applicability", "question_target_document_ids",
    "document_relevances_at_k",
    "CoverageResult", "audit_question_coverage", "audit_dev_coverage",
    "select_phase3_dev_scope", "compute_phase3_dev_scope_sha256", "compute_question_ids_sha256",
    "build_phase3_config", "compute_phase3_config_hash", "verify_artifact_identities",
    "ABLATION_TABLE_COLUMNS", "ABLATION_TABLE_SPARSE_EXTRA_COLUMNS",
    "build_row0", "load_ablation_table", "write_ablation_table", "upsert_row",
    "build_result_summary",
]
