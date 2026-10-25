"""Task 4.A - production dense retriever for the frozen full-corpus
(10,487,096-row, Qwen3-Embedding-0.6B, 1024-d) LanceDB artifact.

Why this exists separately from `src.retrieval.baseline.BaselineRetriever`:
that retriever's `RetrievalResult` hardcodes the Phase 1 dev-corpus
17-column schema (`chunk_id`, `source_filename`, `source_split`,
`normalizer_version`, ...). The Task 4.4 production table instead carries
the 24-column Task 4.2 schema (`chunk_uid`, `chunk_local_id`, `accession`,
`section_id`, ... and no dev-only provenance), so the two cannot share a
row mapping. This module builds an explicit adapter from production rows
to a result type that exposes the attribute names every downstream
consumer actually reads (`chunk_id`, `document_id`, `text`, `company`,
`fiscal_year`, `source`, `rank`, `score`, `distance`).

Nothing here rebuilds, re-embeds or re-indexes anything: the artifact is
only read, and every identity check compares against the frozen
`configs/phase_4_4_full_corpus_vector_index.json` /
`results/phase_4_4_full_corpus_vector_index_summary.json` (the existing
versioning contract - no second versioning system is introduced).

Score semantics are identical to the dev retriever: `distance` is the raw
LanceDB cosine `_distance` (lower is better) and `score = 1.0 - distance`.
The frozen CRAG threshold is NOT applied here (see
project_plan/TASK_4A_PRODUCTION_DENSE_RETRIEVER.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.artifacts.versioning import compute_index_identity_hash, embedding_identity_hash
from src.embeddings.model_registry import QWEN3_EMBEDDING, EmbeddingModelSpec, encode_queries
from src.index import lancedb_index_full as full_index
from src.index.lancedb_index import exact_cosine_search, exact_cosine_search_filtered
from src.retrieval.filtered import FilteredRetrievalStats, build_predicate

DEFAULT_K = 5
REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_INDEX_CONFIG = Path("configs") / "phase_4_4_full_corpus_vector_index.json"
PRODUCTION_INDEX_SUMMARY = Path("results") / "phase_4_4_full_corpus_vector_index_summary.json"
SCHEMA_LABEL = "phase4_full_corpus_24_column_chunk_uid"
RETRIEVER_KIND = "production_exact_cosine"

# Columns copied into the public result (everything except `vector`).
_RESULT_COLUMNS: tuple[str, ...] = (
    "chunk_schema_version", "chunk_uid", "chunk_local_id", "document_id", "accession",
    "cik", "company", "form_type", "fiscal_year", "section_id", "section_title",
    "ordinal", "char_start", "char_end", "content_type", "source", "text",
    "token_count", "chunk_config_hash",
)
_SMOKE_DISTANCE_TOLERANCE = 1e-4


class ProductionIndexError(RuntimeError):
    """The production artifact failed an identity/schema/contract check.
    Always fatal at startup - never degraded to another index."""


def derive_citation_id(document_id: str, chunk_local_id: str) -> str:
    """Stable string citation id for a production chunk, derived
    deterministically from the artifact's own columns (never stored in or
    written back to it). Matches the `<document_id>::chunk<digits>` shape
    `src.generation.citations` parses. The canonical production identity
    stays `chunk_uid`."""
    return f"{document_id}::{chunk_local_id}"


@dataclass(frozen=True)
class ProductionRetrievalResult:
    rank: int
    score: float
    distance: float
    chunk_id: str            # derived citation id (document_id::chunk_local_id)
    chunk_uid: str           # canonical production chunk identity
    document_id: str
    text: str
    cik: int
    company: str             # artifact value, else "CIK <cik>" (never None)
    form_type: str
    fiscal_year: int
    source: str
    accession: str | None
    section_id: str | None
    section_title: str | None
    ordinal: int
    char_start: int | None
    char_end: int | None
    content_type: str
    token_count: int
    chunk_config_hash: str
    chunk_schema_version: int


def to_production_results(arrow_table) -> list[ProductionRetrievalResult]:
    columns = {name: arrow_table.column(name).to_pylist() for name in _RESULT_COLUMNS}
    distances = arrow_table.column("_distance").to_pylist()
    results = []
    for i in range(arrow_table.num_rows):
        row = {name: columns[name][i] for name in _RESULT_COLUMNS}
        distance = float(distances[i])
        company = row["company"] or f"CIK {row['cik']}"
        results.append(ProductionRetrievalResult(
            rank=i + 1, score=1.0 - distance, distance=distance,
            chunk_id=derive_citation_id(row["document_id"], row["chunk_local_id"]),
            chunk_uid=row["chunk_uid"], document_id=row["document_id"], text=row["text"],
            cik=row["cik"], company=company, form_type=row["form_type"],
            fiscal_year=row["fiscal_year"], source=row["source"], accession=row["accession"],
            section_id=row["section_id"], section_title=row["section_title"],
            ordinal=row["ordinal"], char_start=row["char_start"], char_end=row["char_end"],
            content_type=row["content_type"], token_count=row["token_count"],
            chunk_config_hash=row["chunk_config_hash"],
            chunk_schema_version=row["chunk_schema_version"],
        ))
    return results


# ------------------------------------------------------------------ contract

@dataclass(frozen=True)
class ProductionIndexContract:
    phase_4_1_config_hash: str
    chunk_config_hash: str
    chunk_schema_version: int
    embedding_model: str
    embedding_model_revision: str
    embedding_dimension: int
    embedding_identity_hash: str
    index_identity_hash: str
    table_name: str
    distance_metric: str
    vector_count: int


def load_production_contract(repo_root: Path | None = None,
                             spec: EmbeddingModelSpec = QWEN3_EMBEDDING) -> ProductionIndexContract:
    """Reads the frozen Task 4.4 config + summary and cross-checks them
    against the live embedding spec. Raises ProductionIndexError on any
    disagreement - the live query encoder must be exactly the one that
    produced the stored vectors."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    try:
        config = json.loads((root / PRODUCTION_INDEX_CONFIG).read_text(encoding="utf-8"))
        summary = json.loads((root / PRODUCTION_INDEX_SUMMARY).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProductionIndexError(f"production index config/summary unreadable: {type(exc).__name__}") from None

    identity = config["index_identity"]
    if compute_index_identity_hash(identity) != config["index_identity_hash"]:
        raise ProductionIndexError("production index identity hash does not match its identity record")
    if summary.get("index_identity_hash") != config["index_identity_hash"]:
        raise ProductionIndexError("production index summary and config disagree on index identity")

    live_embedding_hash = embedding_identity_hash(spec.embedding_identity())
    if live_embedding_hash != identity["embedding_identity_hash"]:
        raise ProductionIndexError("live query encoder identity differs from the identity the index was built with")
    if (config["embedding_model"], config["embedding_model_revision"], config["embedding_dimension"]) != (
            spec.repository, spec.revision, spec.dimension):
        raise ProductionIndexError("live embedding spec differs from the frozen production embedding config")
    if config["embedding_dimension"] != full_index.EMBEDDING_DIMENSION:
        raise ProductionIndexError("frozen production dimension differs from the full-corpus index module")

    return ProductionIndexContract(
        phase_4_1_config_hash=config["phase_4_1_config_hash"],
        chunk_config_hash=config["chunk_config_hash"],
        chunk_schema_version=config["chunk_schema_version"],
        embedding_model=config["embedding_model"],
        embedding_model_revision=config["embedding_model_revision"],
        embedding_dimension=config["embedding_dimension"],
        embedding_identity_hash=live_embedding_hash,
        index_identity_hash=config["index_identity_hash"],
        table_name=config["table_name"],
        distance_metric=config["distance_metric"],
        vector_count=summary["vector_count"],
    )


def validate_production_table(table, contract: ProductionIndexContract) -> None:
    """Startup validation: metadata/schema/manifest checks plus one
    1-row peek. Never scans vectors."""
    try:
        full_index.validate_chunk_table(table, contract.vector_count)
        full_index.validate_scalar_indexes(table)
    except full_index.VectorIndexFullError as exc:
        raise ProductionIndexError(f"production table failed validation: {exc}") from None
    peek = table.search().limit(1).select(["chunk_config_hash", "chunk_schema_version"]).to_arrow().to_pylist()
    if not peek:
        raise ProductionIndexError("production table is empty")
    if peek[0]["chunk_config_hash"] != contract.chunk_config_hash:
        raise ProductionIndexError("production table chunk_config_hash differs from the frozen contract")
    if peek[0]["chunk_schema_version"] != contract.chunk_schema_version:
        raise ProductionIndexError("production table chunk_schema_version differs from the frozen contract")


def smoke_lookup(table, *, search_fn=exact_cosine_search_filtered) -> dict:
    """Tiny deterministic self-retrieval: take one stored row's own vector
    and search the (BTree-pre-filtered) cik+fiscal_year slice it belongs
    to; the nearest neighbour must be at distance ~0. Proves the table is
    searchable with the frozen metric without touching the other ~10.5M
    vectors."""
    rows = table.search().limit(1).select(["cik", "fiscal_year", "vector"]).to_arrow().to_pylist()
    row = rows[0]
    where = build_predicate(row["cik"], row["fiscal_year"])
    result = search_fn(table, np.asarray(row["vector"], dtype=np.float32), limit=1, where=where,
                       expected_dimension=full_index.EMBEDDING_DIMENSION)
    distance = float(result.column("_distance").to_pylist()[0])
    if abs(distance) > _SMOKE_DISTANCE_TOLERANCE:
        raise ProductionIndexError(f"production smoke lookup self-distance {distance} exceeds tolerance")
    return {"cik": row["cik"], "fiscal_year": row["fiscal_year"], "self_distance": distance}


def build_production_cache_identity(contract: ProductionIndexContract, *, schema_version: str,
                                    row_count: int, spec: EmbeddingModelSpec = QWEN3_EMBEDDING) -> dict:
    """Static identity for ExactRetrievalCache. Deliberately shares no
    value with the dev identity (`retriever_kind`, model, dimension,
    chunk-config hash, table schema, artifact identity and row count all
    differ), so a cached dev/BGE result can never be served by the
    production index. CRAG stays disabled (None) until its live score
    scale is verified."""
    return {
        "cache_schema_version": schema_version,
        "route": "dense",
        "retriever_kind": RETRIEVER_KIND,
        "embedding_model_identity": contract.embedding_model,
        "embedding_model_revision": contract.embedding_model_revision,
        "embedding_dimension": contract.embedding_dimension,
        "embedding_identity_hash": contract.embedding_identity_hash,
        "query_convention": spec.query_convention,
        "chunk_config_hash": contract.chunk_config_hash,
        "dense_index_table": contract.table_name,
        "dense_index_schema": SCHEMA_LABEL,
        "dense_index_artifact_identity": contract.index_identity_hash,
        "dense_index_row_count": row_count,
        "retrieval_algorithm": full_index.INDEX_TYPE,
        "similarity_metric": contract.distance_metric,
        "crag_threshold": None,
    }


# ----------------------------------------------------------------- retriever

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


class ProductionDenseRetriever:
    """Qwen3 query encoder -> exact cosine search over the production
    LanceDB table -> `ProductionRetrievalResult`s.

    `retrieve()` accepts optional `cik`/`fiscal_year` and applies them as a
    scalar PRE-filter (reusing `src.retrieval.filtered.build_predicate`
    and `exact_cosine_search_filtered` unchanged). The live router does not
    pass filters yet; with none given this is a plain global search, so the
    current service behaviour is unchanged."""

    def __init__(self, spec: EmbeddingModelSpec, model, table, *, encode_fn=encode_queries,
                 search_fn=exact_cosine_search, filtered_search_fn=exact_cosine_search_filtered):
        if spec.dimension != full_index.EMBEDDING_DIMENSION:
            raise ProductionIndexError(
                f"query encoder dimension {spec.dimension} != production index dimension "
                f"{full_index.EMBEDDING_DIMENSION}")
        self._spec = spec
        self._model = model
        self._table = table
        self._encode_fn = encode_fn
        self._search_fn = search_fn
        self._filtered_search_fn = filtered_search_fn
        self.last_stats: FilteredRetrievalStats | None = None

    def retrieve(self, question: str, k: int = DEFAULT_K, *, cik: int | None = None,
                 fiscal_year: int | None = None) -> list[ProductionRetrievalResult]:
        _validate_question(question)
        _validate_k(k)
        predicate = build_predicate(cik, fiscal_year)

        query_vector = self._encode_fn(self._spec, self._model, [question], batch_size=1)[0]
        if len(query_vector) != full_index.EMBEDDING_DIMENSION:
            raise ProductionIndexError(
                f"query vector dimension {len(query_vector)} != production index dimension "
                f"{full_index.EMBEDDING_DIMENSION}")
        if predicate is None:
            arrow = self._search_fn(self._table, query_vector, limit=k,
                                    expected_dimension=full_index.EMBEDDING_DIMENSION)
        else:
            arrow = self._filtered_search_fn(self._table, query_vector, limit=k, where=predicate,
                                             expected_dimension=full_index.EMBEDDING_DIMENSION)
        self.last_stats = FilteredRetrievalStats(filtered=predicate is not None, predicate=predicate)
        return to_production_results(arrow)


__all__ = [
    "ProductionIndexError", "ProductionIndexContract", "ProductionRetrievalResult",
    "ProductionDenseRetriever", "derive_citation_id", "to_production_results",
    "load_production_contract", "validate_production_table", "smoke_lookup",
    "build_production_cache_identity", "RETRIEVER_KIND", "SCHEMA_LABEL",
]
