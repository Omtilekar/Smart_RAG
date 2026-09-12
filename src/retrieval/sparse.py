"""Task 3.4 - LanceDB-native sparse (FTS/BM25-style) retriever.

Companion to `src.retrieval.baseline` (Task 1.6's dense vector
retriever), never a modification of it and never composed with it in
this task - Task 3.4 is sparse-only. No embedding model is imported or
loaded anywhere in this module; no LLM is called; no reranking happens.

    question -> src.index.lancedb_fts.fts_search() -> ranked chunk rows

Score contract (frozen by configs/phase_3_4_bm25_fts_baseline.json's
`score_contract`): the native LanceDB `_score` column is preserved
faithfully as `sparse_score` - higher is better, never renamed to
"distance"/"cosine score", never normalized across queries, never
combined with a dense score here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.index.lancedb_fts import fts_search

DEFAULT_K = 50

# Every column persisted on the frozen Task 3.2 chunk artifact
# (`src.chunk.fixed_window.CHUNK_SCHEMA_FIELDS`) except `text` itself is
# still returned as metadata alongside `text` - the sparse table has no
# `vector` column to worry about excluding.
METADATA_FIELDS: tuple[str, ...] = (
    "chunk_id", "document_id", "text", "cik", "company", "form_type",
    "fiscal_year", "source", "source_filename", "source_split", "ordinal",
    "token_count", "chunk_config_hash", "normalizer_version",
    "normalization_build_sha256", "development_manifest_sha256",
)


@dataclass(frozen=True)
class SparseRetrievalResult:
    rank: int
    sparse_score: float
    chunk_id: str
    document_id: str
    text: str
    cik: int
    company: str
    form_type: str
    fiscal_year: int
    source: str
    source_filename: str
    source_split: str
    ordinal: int
    token_count: int
    chunk_config_hash: str
    normalizer_version: str
    normalization_build_sha256: str
    development_manifest_sha256: str

    @property
    def score(self) -> float:
        """Alias for `sparse_score` - lets generic evaluation code that
        expects a `.score` attribute (e.g. `src.eval.baseline_metrics`)
        work unmodified, without renaming the honestly-named public field."""
        return self.sparse_score

    @property
    def distance(self) -> float:
        """`src.eval.baseline_metrics.evaluate_question()` duck-types a
        `.distance` attribute for provenance display only (it plays no
        role in hit/rank/recall computation). Sparse FTS has no distance
        concept - this is a fixed, documented sentinel (0.0), never a
        derived/fake transform of `sparse_score`. Use `sparse_score`/
        `score` for the real native ranking signal."""
        return 0.0


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


def _to_results(arrow_table) -> list[SparseRetrievalResult]:
    columns = {field: arrow_table.column(field).to_pylist() for field in METADATA_FIELDS}
    scores = arrow_table.column("_score").to_pylist()
    results = []
    for i in range(arrow_table.num_rows):
        results.append(SparseRetrievalResult(
            rank=i + 1,
            sparse_score=float(scores[i]),
            **{field: columns[field][i] for field in METADATA_FIELDS},
        ))
    return results


class SparseRetriever:
    """A retriever instance reuses its LanceDB table handle across calls -
    the table is not reopened per `retrieve()` call. `search_fn` is
    injectable for portable unit testing with a fake table (no DI
    framework - just an optional callable with a real default, matching
    `src.retrieval.baseline.BaselineRetriever`'s convention)."""

    def __init__(self, table, *, search_fn=fts_search):
        self._table = table
        self._search_fn = search_fn

    def retrieve(self, question: str, k: int = DEFAULT_K) -> list[SparseRetrievalResult]:
        _validate_question(question)
        _validate_k(k)

        arrow_results = self._search_fn(self._table, question, k)
        return _to_results(arrow_results)


__all__ = ["DEFAULT_K", "METADATA_FIELDS", "SparseRetrievalResult", "SparseRetriever"]
