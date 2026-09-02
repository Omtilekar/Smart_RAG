"""Task 2.12 - independent benchmark validation (FinanceBench).

Pure, testable logic only - dataset validation, page-number/evidence-
alignment semantics, benchmark-specific table serialization, page-
bounded chunking, benchmark identity, and retrieval-metric computation.
No network, no filesystem PDF I/O, no model loading here - see
`scripts/run_financebench_validation.py` for orchestration.

FinanceBench is external evidence about the evaluation system - it is
never mixed into the internal SEC corpus/schema. This module never
imports `src.chunk.metadata_schema` (Task 2.9's SEC-only chunk schema)
or `src.eval.evaluation_dataset`/`dev_test_split`; it reuses only the
generic, source-agnostic primitives (`src.chunk.fixed_window.compute_token_windows`,
`src.eval.metrics`, `src.artifacts.versioning`).

Central rule: FinanceBench is external evidence about our evaluation
system. It is not a tuning set for Phase 3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from src.artifacts.versioning import semantic_hash
from src.chunk.fixed_window import compute_token_windows

BENCHMARK_NAME = "financebench"
EXPECTED_ROW_COUNT = 150
EXPECTED_UNIQUE_DOC_COUNT = 84

REQUIRED_FIELDS: tuple[str, ...] = (
    "financebench_id", "company", "doc_name", "question_type", "question_reasoning",
    "question", "answer", "justification", "evidence", "gics_sector", "doc_type",
    "doc_period", "doc_link", "dataset_subset_label",
)
REQUIRED_EVIDENCE_ITEM_FIELDS: tuple[str, ...] = (
    "evidence_text", "doc_name", "evidence_page_num",
)

# Confirmed empirically (Task 2.12 baseline check): evidence_page_num=59 on
# a real downloaded 3M 2018 10-K corresponds to pdfplumber's 0-indexed
# page list position 59 (display/printed page 60), not the printed page
# number. Never conflated with 1-indexed PDF display pages.
PAGE_NUMBER_CONVENTION = "zero_indexed_pdf_page_list_position"

ALIGNMENT_STATUSES: tuple[str, ...] = (
    "exact", "normalized_exact", "ambiguous", "unmatched", "document_missing", "parse_failure",
)

# Frozen chunking policy (Section 18) - decided before seeing any benchmark
# result. Reuses Phase 1's own tokenizer/window/stride/partial-window
# semantics exactly, but never crosses a page boundary (FinanceBench
# evidence identity is page-oriented; crossing pages would make gold
# mapping ambiguous).
WINDOW_SIZE_TOKENS = 512
STRIDE_TOKENS = 512


class FinanceBenchError(ValueError):
    """Raised for a malformed FinanceBench row/evidence item, or a
    violated leakage/alignment invariant."""


class LeakageError(FinanceBenchError):
    """Raised if a retrieval corpus construction step would leak gold
    answer/evidence/question text into the indexed document corpus."""


# --------------------------------------------------------------- dataset validation

def validate_financebench_row(row: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in row]
    if missing:
        raise FinanceBenchError(f"row missing required field(s): {missing}")
    if not isinstance(row["financebench_id"], str) or not row["financebench_id"].strip():
        raise FinanceBenchError("financebench_id must be a non-empty string")
    if not isinstance(row["question"], str) or not row["question"].strip():
        raise FinanceBenchError(f"{row['financebench_id']}: question must be non-empty")
    if not isinstance(row["answer"], str) or not str(row["answer"]).strip():
        raise FinanceBenchError(f"{row['financebench_id']}: answer must be non-empty")
    if not isinstance(row["doc_name"], str) or not row["doc_name"].strip():
        raise FinanceBenchError(f"{row['financebench_id']}: doc_name must be non-empty")
    if not isinstance(row["evidence"], list) or len(row["evidence"]) == 0:
        raise FinanceBenchError(f"{row['financebench_id']}: evidence must be a non-empty list")
    for item in row["evidence"]:
        missing_ev = [f for f in REQUIRED_EVIDENCE_ITEM_FIELDS if f not in item]
        if missing_ev:
            raise FinanceBenchError(f"{row['financebench_id']}: evidence item missing field(s): {missing_ev}")
        if not isinstance(item["evidence_page_num"], int) or item["evidence_page_num"] < 0:
            raise FinanceBenchError(f"{row['financebench_id']}: evidence_page_num must be a non-negative int")


@dataclass(frozen=True)
class DatasetAudit:
    row_count: int
    unique_id_count: int
    unique_doc_name_count: int
    doc_type_distribution: dict
    question_type_distribution: dict
    question_reasoning_distribution: dict
    gics_sector_distribution: dict
    evidence_count_distribution: dict
    zero_evidence_count: int
    null_question_count: int
    null_answer_count: int
    company_count: int


def audit_financebench_dataset(rows: Sequence[dict]) -> DatasetAudit:
    """Validates every row, then reports the dataset-shape statistics
    Section 10 requires - computed independently of any README claim."""
    for row in rows:
        validate_financebench_row(row)

    ids = [r["financebench_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise FinanceBenchError("duplicate financebench_id detected")

    def _dist(key):
        counts: dict = {}
        for r in rows:
            v = r.get(key)
            counts[v] = counts.get(v, 0) + 1
        return counts

    evidence_counts = [len(r["evidence"]) for r in rows]
    evidence_dist: dict = {}
    for c in evidence_counts:
        evidence_dist[c] = evidence_dist.get(c, 0) + 1

    return DatasetAudit(
        row_count=len(rows),
        unique_id_count=len(set(ids)),
        unique_doc_name_count=len({r["doc_name"] for r in rows}),
        doc_type_distribution=_dist("doc_type"),
        question_type_distribution=_dist("question_type"),
        question_reasoning_distribution=_dist("question_reasoning"),
        gics_sector_distribution=_dist("gics_sector"),
        evidence_count_distribution=evidence_dist,
        zero_evidence_count=sum(1 for r in rows if not r["evidence"]),
        null_question_count=sum(1 for r in rows if not r["question"].strip()),
        null_answer_count=sum(1 for r in rows if not str(r["answer"]).strip()),
        company_count=len({r["company"] for r in rows}),
    )


# --------------------------------------------------------------- leakage guard

_FORBIDDEN_SOURCE_KEYS: tuple[str, ...] = ("evidence_text", "justification", "answer", "question")


def assert_no_gold_leakage(retrieval_corpus_source: str, row: dict) -> None:
    """Hard rule (Section 13): the retrieval corpus must never be built
    from `evidence_text`/`justification`/`answer`/`question` - only from
    the benchmark's own source PDF. Raises `LeakageError` the instant a
    caller's declared corpus source matches one of those fields."""
    if retrieval_corpus_source in _FORBIDDEN_SOURCE_KEYS:
        raise LeakageError(
            f"retrieval corpus must never be built from {retrieval_corpus_source!r} - "
            f"use the source PDF only (gold evidence is for evaluation, not retrieval input)"
        )


# --------------------------------------------------------------- text normalization / alignment

_WHITESPACE_RE = re.compile(r"\s+")
# Empirically confirmed (Task 2.12 real-PDF checks against two independent
# real FinanceBench documents):
#   1. 3M_2018_10K page 59: FinanceBench's own evidence_text extraction and
#      pdfplumber's extraction of the identical page disagree on
#      placeholder-dash glyphs for blank/zero table cells (one tool emits
#      "Other — net", the other "Other net" with no dash at all).
#   2. AMD_2022_10K page 3: a bulleted list item - pdfplumber preserves the
#      literal bullet glyph ("• server microprocessors..."), FinanceBench's
#      evidence_text drops it entirely ("server microprocessors...").
# Both are extraction-tool-dependent list/blank-cell MARKER glyphs, never
# semantic content - both are treated as whitespace before collapsing.
# Never a general fuzzy-match escape hatch - no other character class is
# altered.
_MARKER_GLYPH_RE = re.compile(r"[‐-―−•‣◦▪]")


def normalize_whitespace(text: str) -> str:
    """Whitespace normalization plus one narrow, documented extra rule:
    dash/bullet-family marker glyphs are treated as whitespace before
    collapsing (see the two concrete real-document cases above)."""
    marker_free = _MARKER_GLYPH_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", marker_free).strip()


@dataclass(frozen=True)
class PageNode:
    doc_name: str
    page_number: int  # zero-indexed, PAGE_NUMBER_CONVENTION
    text: str
    tables: tuple[tuple[tuple[str, ...], ...], ...]  # tuple of tables, each a tuple of rows, each a tuple of cell strings


@dataclass(frozen=True)
class AlignmentResult:
    status: str
    page_number: int | None
    matched_via: str | None  # None | "stated_page" | "adjacent_page"


def align_evidence_item(evidence_page_num: int, evidence_text: str, pages_by_number: dict[int, PageNode]) -> AlignmentResult:
    """Deterministic evidence-to-page alignment (Section 16/17). Checks
    the stated page first (exact, then normalized-exact substring); if
    absent there, checks the immediately adjacent pages (a common off-by-
    one from a different PDF extraction tool than FinanceBench's own).
    Ambiguous if more than one distinct page matches. Never uses an LLM,
    never fabricates a confidence score."""
    norm_evidence = normalize_whitespace(evidence_text)

    def _check(page_number: int) -> str | None:
        page = pages_by_number.get(page_number)
        if page is None:
            return None
        if evidence_text in page.text:
            return "exact"
        if norm_evidence in normalize_whitespace(page.text):
            return "normalized_exact"
        return None

    stated_status = _check(evidence_page_num)
    if stated_status is not None:
        return AlignmentResult(status=stated_status, page_number=evidence_page_num, matched_via="stated_page")

    adjacent_matches = []
    for candidate in (evidence_page_num - 1, evidence_page_num + 1):
        if candidate < 0:
            continue
        status = _check(candidate)
        if status is not None:
            adjacent_matches.append((candidate, status))

    if len(adjacent_matches) == 0:
        return AlignmentResult(status="unmatched", page_number=None, matched_via=None)
    if len(adjacent_matches) > 1:
        return AlignmentResult(status="ambiguous", page_number=None, matched_via=None)
    page_number, status = adjacent_matches[0]
    return AlignmentResult(status=status, page_number=page_number, matched_via="adjacent_page")


def gold_chunk_ids_for_alignment(alignment: AlignmentResult, evidence_text: str,
                                  chunks_on_page: Sequence["BenchmarkChunk"]) -> tuple[str, ...]:
    """Given an aligned (exact/normalized_exact) evidence item and the
    chunks that page produced, returns the precise chunk_id(s) whose own
    text contains the evidence - falling back to every chunk on the page
    only when the evidence text spans a chunk boundary and no single
    chunk contains it whole."""
    if alignment.status not in ("exact", "normalized_exact"):
        return ()
    norm_evidence = normalize_whitespace(evidence_text)
    exact_hits = tuple(c.chunk_id for c in chunks_on_page if evidence_text in c.text)
    if exact_hits:
        return exact_hits
    normalized_hits = tuple(c.chunk_id for c in chunks_on_page if norm_evidence in normalize_whitespace(c.text))
    if normalized_hits:
        return normalized_hits
    return tuple(c.chunk_id for c in chunks_on_page)


# --------------------------------------------------------------- table serialization

def serialize_table(rows: Sequence[Sequence[str | None]]) -> str:
    """One predetermined table representation (Section 15), frozen before
    seeing any benchmark result: pipe-delimited cells per row, rows
    joined by newlines, a None cell rendered as an empty string. Never
    changed based on which representation scores better."""
    lines = []
    for row in rows:
        cells = [("" if c is None else str(c).strip()) for c in row]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


# --------------------------------------------------------------- benchmark chunking

@dataclass(frozen=True)
class BenchmarkChunk:
    chunk_id: str
    doc_name: str
    page_number: int
    ordinal: int
    text: str
    token_count: int
    benchmark_config_hash: str


def build_benchmark_chunk_id(doc_name: str, page_number: int, ordinal: int) -> str:
    """Deterministic, namespaced so it can never collide with SEC Phase 1
    (`{document_id}::chunk{ordinal}`) or Task 2.9 (`chunk_uid`) chunk IDs -
    always prefixed with the benchmark name."""
    return f"{BENCHMARK_NAME}:{doc_name}:page{page_number:05d}:chunk{ordinal:04d}"


def build_page_chunks(page: PageNode, *, tokenizer, benchmark_config_hash: str) -> list[BenchmarkChunk]:
    """Windows one page's text at 512 BGE tokens, zero overlap, keeping
    the final partial window - reusing Phase 1's own
    `compute_token_windows()` exactly, but never crossing a page boundary
    (Section 18). Returns [] for a page with no extractable text."""
    if not page.text or not page.text.strip():
        return []
    encoding = tokenizer(page.text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
    offsets = encoding["offset_mapping"]
    num_tokens = len(offsets)
    if num_tokens == 0:
        return []

    windows = compute_token_windows(num_tokens, WINDOW_SIZE_TOKENS, STRIDE_TOKENS)
    chunks = []
    for ordinal, (start_idx, end_idx) in enumerate(windows):
        char_start = offsets[start_idx][0]
        char_end = offsets[end_idx - 1][1]
        text = page.text[char_start:char_end]
        if not text.strip():
            continue
        chunks.append(BenchmarkChunk(
            chunk_id=build_benchmark_chunk_id(page.doc_name, page.page_number, ordinal),
            doc_name=page.doc_name, page_number=page.page_number, ordinal=ordinal,
            text=text, token_count=end_idx - start_idx, benchmark_config_hash=benchmark_config_hash,
        ))
    return chunks


# --------------------------------------------------------------- benchmark identity

def compute_benchmark_config_hash(config: dict) -> str:
    """Reuses Task 2.10's canonical semantic-hash primitive - never a
    second independent hashing implementation."""
    return semantic_hash(config)


def build_benchmark_identity(*, dataset_revision: str, dataset_file_sha256: str,
                              document_manifest_sha256: str, evidence_alignment_version: str) -> dict:
    """Section 32 - explicit semantic benchmark identity. Never includes
    a timestamp or Git SHA."""
    return {
        "benchmark_identity_version": 1,
        "benchmark_name": BENCHMARK_NAME,
        "dataset_revision": dataset_revision,
        "dataset_file_sha256": dataset_file_sha256,
        "document_manifest_sha256": document_manifest_sha256,
        "evidence_alignment_version": evidence_alignment_version,
        "question_population": "open_source_150",
    }


# --------------------------------------------------------------- retrieval metrics

@dataclass(frozen=True)
class QuestionRetrievalResult:
    financebench_id: str
    doc_recall_hit: bool
    doc_first_hit_rank: int | None
    evidence_relevant_chunk_ids: tuple[str, ...]
    evidence_hits_in_top_k: int
    evidence_first_hit_rank: int | None
    status: str  # "evaluated" | "blocked_document_missing" | "blocked_parse_failure" | "blocked_evidence_unmatched" | "infrastructure_error"


def evaluate_financebench_question(*, financebench_id: str, retrieved_doc_names: Sequence[str],
                                    retrieved_chunk_ids: Sequence[str], gold_doc_name: str,
                                    gold_chunk_ids: Sequence[str], k: int) -> QuestionRetrievalResult:
    """Document-level and evidence/chunk-level retrieval scoring for one
    question. Deliberately NOT a reuse of Task 2.6's SEC-shaped
    `hit_at_k`/`first_hit_rank` applied to a mismatched identifier
    abstraction without adaptation (Section 23) - this adapts the exact
    same rank-based mathematics to FinanceBench's own doc_name/chunk_id
    identifiers, independently, and is unit-tested against hand-derived
    fixtures exactly like Task 2.6's own metrics."""
    top_k_docs = list(retrieved_doc_names)[:k]
    doc_hit = gold_doc_name in top_k_docs
    doc_first_hit_rank = None
    for i, name in enumerate(retrieved_doc_names[:k], start=1):
        if name == gold_doc_name:
            doc_first_hit_rank = i
            break

    top_k_chunks = list(retrieved_chunk_ids)[:k]
    gold_set = set(gold_chunk_ids)
    evidence_hits_in_top_k = sum(1 for cid in top_k_chunks if cid in gold_set)
    evidence_first_hit_rank = None
    for i, cid in enumerate(retrieved_chunk_ids[:k], start=1):
        if cid in gold_set:
            evidence_first_hit_rank = i
            break

    return QuestionRetrievalResult(
        financebench_id=financebench_id, doc_recall_hit=doc_hit, doc_first_hit_rank=doc_first_hit_rank,
        evidence_relevant_chunk_ids=tuple(gold_chunk_ids), evidence_hits_in_top_k=evidence_hits_in_top_k,
        evidence_first_hit_rank=evidence_first_hit_rank, status="evaluated",
    )


@dataclass(frozen=True)
class AggregateRetrievalResult:
    evaluated_count: int
    doc_recall_at_k: float
    doc_hit_count: int
    doc_mrr: float
    evidence_recall_at_k: float
    evidence_recall_numerator_diagnostic: int
    evidence_recall_denominator_diagnostic: int
    evidence_questions_with_gold: int
    evidence_mrr: float


def aggregate_financebench_results(results: Sequence[QuestionRetrievalResult], *, k: int) -> AggregateRetrievalResult:
    """Independently derives aggregate metrics from per-question results -
    never silently drops a question from the denominator. Only
    `status == "evaluated"` questions contribute; callers must report the
    excluded-status counts separately (Section 24/38).

    `evidence_recall_at_k` is the MEAN of each question's own
    hits_in_top_k/len(gold_items) fraction (macro-average across
    questions) - the same mathematical shape Task 2.7's MS MARCO
    `passage_recall_at_k` uses for multi-relevant-item recall, not a
    pooled/micro-averaged hits/denominator ratio (Section 23: adapt only
    the identifier abstraction, not the mathematical definition). The
    `_diagnostic` numerator/denominator are a pooled sum for inspection
    only - `evidence_recall_at_k`'s own value is NOT computed from them."""
    evaluated = [r for r in results if r.status == "evaluated"]
    n = len(evaluated)
    if n == 0:
        raise FinanceBenchError("aggregate_financebench_results called with zero evaluated questions")

    doc_hit_count = sum(1 for r in evaluated if r.doc_recall_hit)
    doc_reciprocal_ranks = [1.0 / r.doc_first_hit_rank if r.doc_first_hit_rank else 0.0 for r in evaluated]

    with_evidence = [r for r in evaluated if r.evidence_relevant_chunk_ids]
    per_question_recall = [
        r.evidence_hits_in_top_k / len(r.evidence_relevant_chunk_ids) for r in with_evidence
    ]
    evidence_numerator_diagnostic = sum(r.evidence_hits_in_top_k for r in with_evidence)
    evidence_denominator_diagnostic = sum(len(r.evidence_relevant_chunk_ids) for r in with_evidence)
    evidence_reciprocal_ranks = [1.0 / r.evidence_first_hit_rank if r.evidence_first_hit_rank else 0.0 for r in with_evidence]

    return AggregateRetrievalResult(
        evaluated_count=n,
        doc_recall_at_k=doc_hit_count / n,
        doc_hit_count=doc_hit_count,
        doc_mrr=sum(doc_reciprocal_ranks) / n,
        evidence_recall_at_k=(sum(per_question_recall) / len(with_evidence)) if with_evidence else 0.0,
        evidence_recall_numerator_diagnostic=evidence_numerator_diagnostic,
        evidence_recall_denominator_diagnostic=evidence_denominator_diagnostic,
        evidence_questions_with_gold=len(with_evidence),
        evidence_mrr=(sum(evidence_reciprocal_ranks) / len(with_evidence)) if with_evidence else 0.0,
    )
