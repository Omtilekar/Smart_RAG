"""Task 1.6 - baseline natural-language vector retriever.

Composes Task 1.4's BGE query encoder with Task 1.5's exact-cosine LanceDB
search:

    question -> encode_queries() -> 384-d normalized float32 vector
             -> exact_cosine_search() -> ranked chunk rows

Frozen Phase 1 retrieval contract (all user-approved before this task
began - see project_plan/PHASE1_RETRIEVER.md):

- default k = 5, caller-configurable, must be a positive int
- both `distance` (raw LanceDB cosine _distance, lower is better) and
  `score` (1.0 - distance, higher is better) are returned - `score` is
  never clamped, `distance` is never dropped or renamed away
- the 384-d vector is never included in the public result
- rank follows LanceDB's own result order exactly (1-based)

No LLM prompt is formatted here, no generation happens here - Task 1.7
owns that. No BM25/FTS/reranking/CRAG/routing - vector path only.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.embeddings.bge import encode_queries
from src.index.lancedb_index import exact_cosine_search

DEFAULT_K = 5

# Exact Decision-3 public schema - 16 metadata fields plus rank/score/distance.
# 'vector' and the internal '_distance' LanceDB column name are never exposed.
METADATA_FIELDS: tuple[str, ...] = (
    "chunk_id", "document_id", "text", "cik", "company", "form_type",
    "fiscal_year", "source", "source_filename", "source_split", "ordinal",
    "token_count", "chunk_config_hash", "normalizer_version",
    "normalization_build_sha256", "development_manifest_sha256",
)


@dataclass(frozen=True)
class RetrievalResult:
    rank: int
    score: float
    distance: float
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


def _to_results(arrow_table) -> list[RetrievalResult]:
    columns = {field: arrow_table.column(field).to_pylist() for field in METADATA_FIELDS}
    distances = arrow_table.column("_distance").to_pylist()
    results = []
    for i in range(arrow_table.num_rows):
        distance = float(distances[i])
        score = 1.0 - distance  # no clamping, no rounding
        results.append(RetrievalResult(
            rank=i + 1,
            score=score,
            distance=distance,
            **{field: columns[field][i] for field in METADATA_FIELDS},
        ))
    return results


class BaselineRetriever:
    """A retriever instance reuses its model and LanceDB table handle
    across calls - the model is not reloaded and the table is not
    reopened per retrieve() call.

    `encode_fn`/`search_fn` are injectable for portable unit testing with
    fake components (no DI framework - just optional callables with real
    defaults)."""

    def __init__(self, model, table, *, encode_fn=encode_queries, search_fn=exact_cosine_search):
        self._model = model
        self._table = table
        self._encode_fn = encode_fn
        self._search_fn = search_fn

    def retrieve(self, question: str, k: int = DEFAULT_K) -> list[RetrievalResult]:
        _validate_question(question)
        _validate_k(k)

        vectors = self._encode_fn(self._model, [question], batch_size=1)
        query_vector = vectors[0]

        arrow_results = self._search_fn(self._table, query_vector, limit=k)
        return _to_results(arrow_results)
