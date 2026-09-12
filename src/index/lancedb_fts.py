"""Task 3.4 - LanceDB-native full-text/BM25-style sparse index.

Companion to `src.index.lancedb_index` (Task 1.5's exact-cosine dense
index), never a modification of it. Deliberately a SEPARATE module and a
SEPARATE on-disk LanceDB artifact identity (see `storage.index_dir()`
called with a synthetic "model" key of `SPARSE_ARTIFACT_KEY` rather than
any embedding model name) - the frozen Task 3.3 Qwen dense artifact is
never touched, mutated, or reused for sparse scoring.

Everything below was verified empirically against the installed LanceDB
0.37.1 API with a disposable synthetic table before any real-corpus code
was written (Stage 2 of PROJECT_EXECUTION.md's Task 3.4 contract) - never
assumed from memory or from a different LanceDB version:

    - `table.create_fts_index(...)` is deprecated as of lancedb 0.25.0;
      the supported path is `table.create_index(column, config=FTS())`.
    - The installed `Table.create_index()`'s introspectable signature
      does not show a leading column-name parameter (it is dispatched
      internally), but passing the column name as the first positional
      argument alongside `config=FTS()` is the verified-working call -
      confirmed directly by building a tiny index and checking
      `table.list_indices()[0].columns == [column]` before writing this
      module.
    - Results carry the native score in a `_score` column - HIGHER is
      more relevant (verified: a chunk containing "revenue" 3x outscored
      one containing it once, for the query "revenue"). This is never
      renamed to "distance"/"cosine score" here.
    - With the frozen default `with_position=False`, a query containing a
      literal ASCII double-quote character is parsed as a phrase query
      and raises `ValueError` for entirely ordinary text - `sanitize_fts_query()`
      below is the one, documented, deterministic escaping rule this
      finding justifies (see configs/phase_3_4_bm25_fts_baseline.json's
      `query_transform`). No other character class produces this error.
    - The FTS index (and its exact configuration) persists across a
      fresh `lancedb.connect()` in a new process - verified by reopening
      a probe table from a brand-new connection object.

No embedding model is loaded or referenced anywhere in this module - the
sparse artifact's identity intentionally does not include an
`embedding_identity_hash` (unlike `src.index.lancedb_index.index_identity`,
which requires one). Reusing `src.artifacts.versioning.compute_index_identity`
here would force a fake embedding identity into a schema field that
means something real for the dense index - Task 2.10's own principle
("each identifier answers exactly one question") argues against that.
`sparse_index_identity()` below is a small, honestly-shaped identity of
its own, hashed with the same canonical `semantic_hash()` primitive
(never a second hashing implementation).
"""

from __future__ import annotations

from typing import Any, Mapping

import pyarrow as pa

from src.artifacts.versioning import semantic_hash

TABLE_NAME = "chunks"
FTS_INDEXED_COLUMN = "text"
FTS_INDEX_NAME = "chunk_text_fts"
SPARSE_ARTIFACT_KEY = "lancedb_fts_sparse"
INDEX_TYPE = "fts_lancedb_native"

# The exact installed-default `lancedb.index.FTS()` configuration this
# project uses, verified against lancedb 0.37.1 (Stage 2) - never tuned.
# Kept as a plain dict so it can be both passed to `FTS(**...)` and
# embedded verbatim in the frozen config/identity.
DEFAULT_FTS_CONFIG: dict[str, Any] = {
    "base_tokenizer": "simple",
    "language": "English",
    "lower_case": True,
    "stem": True,
    "remove_stop_words": True,
    "ascii_folding": True,
    "with_position": False,
    "max_token_length": 40,
    "ngram_min_length": 3,
    "ngram_max_length": 3,
    "prefix_only": False,
    "block_size": 128,
    "custom_stop_words": None,
}

NATIVE_SCORE_FIELD = "_score"
NATIVE_SCORE_DIRECTION = "higher_is_better"

# The one character class verified (Stage 2) to crash the installed FTS
# query parser for ordinary natural-language text under this project's
# frozen `with_position=False` config.
_PHRASE_QUERY_TRIGGER_CHARS: tuple[str, ...] = ('"',)


class SparseIndexError(ValueError):
    """Raised for a malformed sparse-search query/limit or a sparse table
    that fails validation - never silently worked around."""


def sanitize_fts_query(query: str) -> str:
    """Strips literal ASCII double-quote characters only - the single,
    deterministic, documented escaping rule Stage 6 permits (see this
    module's docstring). Never expands, stems, or rewrites terms; never
    touches any other character."""
    for ch in _PHRASE_QUERY_TRIGGER_CHARS:
        query = query.replace(ch, "")
    return query


def open_database(db_path):
    import lancedb
    return lancedb.connect(str(db_path))


def create_sparse_table(db, data: pa.Table):
    """Creates the `chunks` table for the sparse artifact directly from
    the frozen Task 3.2 chunk Parquet table - no vector column, no
    embedding step, no rechunking. Every source column is preserved
    verbatim."""
    return db.create_table(TABLE_NAME, data=data)


def open_sparse_table(db):
    return db.open_table(TABLE_NAME)


def build_fts_index(table, *, column: str = FTS_INDEXED_COLUMN, name: str = FTS_INDEX_NAME,
                     replace: bool = False) -> None:
    """Builds the native FTS index using the frozen `DEFAULT_FTS_CONFIG`
    (Stage 3 - "simplest documented/default configuration", never
    tuned). Idempotent when `replace=True`; raises if an index with this
    name already exists and `replace=False` (mirrors this project's
    general "never silently rebuild" convention)."""
    from lancedb.index import FTS
    table.create_index(column, config=FTS(**DEFAULT_FTS_CONFIG), name=name, replace=replace)


def existing_fts_index_names(table) -> list[str]:
    return [idx.name for idx in table.list_indices()]


def validate_sparse_table(table, *, expected_row_count: int, indexed_column: str = FTS_INDEXED_COLUMN,
                           index_name: str = FTS_INDEX_NAME) -> None:
    """Raises SparseIndexError on the first violated invariant:
    - row count matches expected_row_count
    - the indexed column exists in the table schema
    - the named FTS index exists and reports index_type == "FTS" and
      columns == [indexed_column]
    - no vector/ANN index exists on this table (a sparse-only artifact
      must never silently also carry a vector index)
    """
    actual_count = table.count_rows()
    if actual_count != expected_row_count:
        raise SparseIndexError(f"row count {actual_count} != expected {expected_row_count}")

    if indexed_column not in table.schema.names:
        raise SparseIndexError(f"indexed column {indexed_column!r} not present in table schema")

    indices = {idx.name: idx for idx in table.list_indices()}
    if index_name not in indices:
        raise SparseIndexError(f"expected FTS index {index_name!r} not found; found {sorted(indices)}")
    idx = indices[index_name]
    if idx.index_type != "FTS":
        raise SparseIndexError(f"index {index_name!r} has index_type={idx.index_type!r}, expected 'FTS'")
    if list(idx.columns) != [indexed_column]:
        raise SparseIndexError(f"index {index_name!r} covers columns {idx.columns!r}, expected [{indexed_column!r}]")

    non_fts = [name for name, i in indices.items() if i.index_type != "FTS"]
    if non_fts:
        raise SparseIndexError(f"sparse artifact unexpectedly carries non-FTS index(es): {non_fts}")


def fts_search(table, query: str, limit: int) -> pa.Table:
    """Validates `query`/`limit`, sanitizes the query (`sanitize_fts_query`),
    then performs a native FTS search. Returns every persisted column plus
    `_score` (higher = more relevant). Never falls back to a vector
    search, never reranks, never calls an embedding model."""
    if not isinstance(query, str):
        raise SparseIndexError(f"query must be a str, got {type(query).__name__}")
    if not query.strip():
        raise SparseIndexError("query must not be empty or whitespace-only")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise SparseIndexError(f"limit must be an int, got {type(limit).__name__}")
    if limit <= 0:
        raise SparseIndexError(f"limit must be positive, got {limit}")

    sanitized = sanitize_fts_query(query)
    return (
        table.search(sanitized, query_type="fts")
        .limit(limit)
        .to_arrow()
    )


# --------------------------------------------------------------- sparse index identity

REQUIRED_SPARSE_IDENTITY_FIELDS: tuple[str, ...] = (
    "chunk_schema_version", "chunk_config_hash", "index_type",
    "lancedb_version", "table_name", "indexed_column", "fts_index_name", "fts_config",
)


def sparse_index_identity(*, chunk_schema_version: int, chunk_config_hash: str, lancedb_version: str,
                           table_name: str = TABLE_NAME, indexed_column: str = FTS_INDEXED_COLUMN,
                           fts_index_name: str = FTS_INDEX_NAME,
                           fts_config: Mapping[str, Any] | None = None) -> dict:
    """The sparse artifact's own semantic identity - deliberately NOT
    `src.artifacts.versioning.compute_index_identity()`, which requires an
    `embedding_identity_hash` this artifact does not have (see module
    docstring). Binds chunk semantics + LanceDB version + FTS
    column/index/tokenizer configuration."""
    from src.artifacts.versioning import validate_sha256
    validate_sha256(chunk_config_hash, "chunk_config_hash")
    return {
        "sparse_index_identity_version": 1,
        "chunk_schema_version": chunk_schema_version,
        "chunk_config_hash": chunk_config_hash,
        "index_type": INDEX_TYPE,
        "lancedb_version": lancedb_version,
        "table_name": table_name,
        "indexed_column": indexed_column,
        "fts_index_name": fts_index_name,
        "fts_config": dict(fts_config if fts_config is not None else DEFAULT_FTS_CONFIG),
    }


def sparse_index_identity_hash(identity: Mapping[str, Any]) -> str:
    missing = [f for f in REQUIRED_SPARSE_IDENTITY_FIELDS if f not in identity]
    if missing:
        raise SparseIndexError(f"sparse index identity missing required field(s): {missing}")
    return semantic_hash(identity)


__all__ = [
    "TABLE_NAME", "FTS_INDEXED_COLUMN", "FTS_INDEX_NAME", "SPARSE_ARTIFACT_KEY", "INDEX_TYPE",
    "DEFAULT_FTS_CONFIG", "NATIVE_SCORE_FIELD", "NATIVE_SCORE_DIRECTION",
    "SparseIndexError", "sanitize_fts_query",
    "open_database", "create_sparse_table", "open_sparse_table",
    "build_fts_index", "existing_fts_index_names", "validate_sparse_table", "fts_search",
    "REQUIRED_SPARSE_IDENTITY_FIELDS", "sparse_index_identity", "sparse_index_identity_hash",
]
