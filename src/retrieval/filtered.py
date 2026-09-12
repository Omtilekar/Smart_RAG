"""Task 3.9 - metadata-pre-filtered dense retriever. Composes Task 1.6/
3.3's dense encode step with Task 3.9's `exact_cosine_search_filtered()`
(a scalar SQL pre-filter applied before the exact/brute-force cosine
search, never after - see `src.index.lancedb_index.exact_cosine_search_filtered`'s
own docstring for the verified LanceDB prefilter semantics this
depends on).

Frozen scope (PROJECT_EXECUTION.md Task 3.9, verified against the real
frozen chunk artifact before this was written): the chunk schema has a
`form_type` column, but every one of the 323,971 rows is `"10-K"` (the
Phase 1 baseline constraint) - filtering on it is a no-op, never
implemented as a real filter dimension here. There is no `section`
column at all - Task 3.2 selected FIXED (non-section-aware) splitting,
so no chunk carries section metadata. Only `cik` and `fiscal_year` are
real, discriminative pre-filter dimensions given the current frozen
artifacts; this is a "where possible" scoping the roadmap's own wording
anticipates, not a silently reduced contract.

This module does not extract `cik`/`fiscal_year` from question text
itself - that is Task 3.8's `src.router.rules.classify_intent()`'s job.
Callers pass already-extracted values (or `None`) to `retrieve()`.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.model_registry import encode_queries
from src.index.lancedb_index import exact_cosine_search, exact_cosine_search_filtered
from src.retrieval.baseline import _to_results


class FilterError(ValueError):
    """Raised for a malformed cik/fiscal_year filter value - never
    silently coerced or string-interpolated from untrusted input."""


def build_predicate(cik: int | None, fiscal_year: int | None) -> str | None:
    """Builds a safe scalar SQL predicate from already-validated Python
    ints only (never raw question text) - immune to SQL injection by
    construction, since no string ever flows through unescaped. Returns
    `None` (meaning "no pre-filter, fall back to unfiltered search") if
    neither value is given."""
    clauses = []
    for name, value in (("cik", cik), ("fiscal_year", fiscal_year)):
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise FilterError(f"{name} must be an int or None, got {type(value).__name__}")
        clauses.append(f"{name} = {value}")
    return " AND ".join(clauses) if clauses else None


def _validate_question(question) -> None:
    if not isinstance(question, str):
        raise TypeError(f"question must be a str, got {type(question).__name__}")
    if not question.strip():
        raise ValueError("question must not be empty or whitespace-only")


def _validate_k(k) -> None:
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")


@dataclass(frozen=True)
class FilteredRetrievalStats:
    """Diagnostic record of whether a given call actually applied a
    pre-filter - never silently indistinguishable from an unfiltered
    call in the caller's own logs."""
    filtered: bool
    predicate: str | None


class MetadataFilteredRetriever:
    """`spec`/`model`/`table` are the same frozen Task 3.3 dense
    embedding spec/model/LanceDB table Tasks 3.5-3.8 already use -
    neither is rebuilt or retrained here."""

    def __init__(self, spec, model, table, *, encode_fn=encode_queries,
                 filtered_search_fn=exact_cosine_search_filtered, unfiltered_search_fn=exact_cosine_search):
        self._spec = spec
        self._model = model
        self._table = table
        self._encode_fn = encode_fn
        self._filtered_search_fn = filtered_search_fn
        self._unfiltered_search_fn = unfiltered_search_fn
        self.last_stats: FilteredRetrievalStats | None = None

    def retrieve(self, question: str, k: int = 50, *, cik: int | None = None, fiscal_year: int | None = None):
        _validate_question(question)
        _validate_k(k)
        predicate = build_predicate(cik, fiscal_year)

        query_vector = self._encode_fn(self._spec, self._model, [question], batch_size=1)[0]
        if predicate is None:
            arrow = self._unfiltered_search_fn(self._table, query_vector, limit=k, expected_dimension=self._spec.dimension)
        else:
            arrow = self._filtered_search_fn(self._table, query_vector, limit=k, where=predicate,
                                              expected_dimension=self._spec.dimension)
        self.last_stats = FilteredRetrievalStats(filtered=predicate is not None, predicate=predicate)
        return _to_results(arrow)


__all__ = ["FilterError", "build_predicate", "FilteredRetrievalStats", "MetadataFilteredRetriever"]
