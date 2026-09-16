"""Task 4.4 - full-corpus (10,487,096-row) exact-cosine LanceDB vector index.

Companion to `src.index.lancedb_index` (Task 1.5's Phase 1/3 exact-cosine
module, left completely untouched) - same search semantics (plain LanceDB
table, exact/flat cosine, NO ANN index) are reused directly via
`exact_cosine_search()`/`exact_cosine_search_filtered()` (both already
parameterized by `expected_dimension`, never hardcoded to 384). This
module only adds the full-corpus table's own column contract and
validation, because the Task 4.2/4.3 record shape (24 columns, including
`accession`/`period_end`/`filed_date`/`sic`/`section_id`/`section_title`/
`char_start`/`char_end`/`content_type`/`table_id`, `chunk_schema_version`
frozen at 2) is materially different from Task 1.5/3.x's frozen 17-column
dev-corpus contract - see project_plan/PHASE4_FULL_CORPUS_VECTOR_INDEX.md.

Unlike Task 1.5's `validate_chunk_table()` (which requires ZERO indices of
any kind), this module's table intentionally carries scalar BTREE indexes
on `cik`/`fiscal_year` (Task 3.9's two validated discriminative
pre-filter dimensions, reused unchanged - see
project_plan/PHASE3_METADATA_PREFILTERING.md) for production filtered-scan
performance at 10.5M rows. A scalar index changes filter-scan performance
only, never vector-search results/ranking - so `validate_chunk_table()`
here asserts zero *vector/ANN* indexes specifically, not zero indexes of
any kind.

No ANN index, no quantization: Phase 3 never validated a quantization
strategy against the real ablation-selected stack (flat/exact search
throughout Phase 3, documented as an honest gap in
project_plan/SERVING_FEASIBILITY.md's Task 3.14 re-check) - so
PROJECT_EXECUTION.md's Task 4.4 "apply selected quantization strategy
only if Phase 3 validated it" resolves to: apply none.
"""

from __future__ import annotations

import pyarrow as pa

TABLE_NAME = "chunks"
DISTANCE_METRIC = "cosine"
EMBEDDING_DIMENSION = 1024
INDEX_TYPE = "exact_flat"  # same search semantics as Task 1.5 - no ANN index

# Exact 24 columns produced by Task 4.2 (chunk_schema_version=2) + Task 4.3's
# added `vector` column - nothing dropped, nothing fabricated.
EXPECTED_COLUMNS: tuple[str, ...] = (
    "chunk_schema_version", "chunk_uid", "chunk_local_id", "document_id",
    "accession", "cik", "company", "form_type", "fiscal_year", "period_end",
    "filed_date", "sic", "section_id", "section_title", "ordinal",
    "char_start", "char_end", "content_type", "table_id", "source", "text",
    "token_count", "chunk_config_hash", "vector",
)

# Scalar (non-vector, non-ANN) index columns - Task 3.9's two validated
# discriminative pre-filter dimensions. `form_type`/`section` were found
# non-discriminative or absent (see PHASE3_METADATA_PREFILTERING.md) and
# are deliberately not indexed here.
SCALAR_INDEX_COLUMNS: tuple[str, ...] = ("cik", "fiscal_year")
SCALAR_INDEX_TYPE = "BTree"  # lancedb.index.BTree()'s own list_indices() index_type string

# LanceDB index_type strings that represent an actual vector/ANN index -
# never created by this module. Used only to distinguish "no ANN index"
# from "no scalar index either" when validating table.list_indices().
_VECTOR_INDEX_TYPES = frozenset({
    "IVF_PQ", "IVF_FLAT", "IVF_SQ", "IVF_HNSW_PQ", "IVF_HNSW_FLAT",
    "IVF_HNSW_SQ", "HNSW_PQ", "HNSW_FLAT", "HNSW_SQ", "IVF_RQ",
})


class VectorIndexFullError(ValueError):
    """Raised for a malformed shard, a table that fails validation, or an
    unexpected existing index/table state - never silently worked around."""


def open_database(db_path):
    """`db_path` (storage.index_dir_full(...)) is used directly as the
    LanceDB database root - same no-nested-directory contract as Task 1.5's
    `src.index.lancedb_index.open_database()`."""
    import lancedb
    return lancedb.connect(str(db_path))


def create_chunk_table(db, data: pa.Table):
    """Creates the single application table `chunks` from the first
    ingested shard (native PyArrow ingestion). Creates no index of any
    kind - scalar indexes are built explicitly afterward, once, via
    `build_scalar_indexes()`."""
    return db.create_table(TABLE_NAME, data=data)


def open_chunk_table(db):
    return db.open_table(TABLE_NAME)


def append_shard(table, data: pa.Table) -> None:
    """Appends one already-schema-verified Task 4.3 embedding shard to the
    table. A thin, explicit wrapper (rather than calling `table.add()`
    directly at call sites) so every append in this module goes through
    one named, greppable function."""
    table.add(data)


def validate_shard_schema(shard_table: pa.Table, *, reference_schema: pa.Schema) -> None:
    """Raises VectorIndexFullError if `shard_table`'s schema (fields, types,
    nullability) differs from `reference_schema` - every one of the 54
    Task 4.3 shards must be byte-for-byte schema-identical before it is
    safe to concatenate them into one LanceDB table."""
    if shard_table.schema != reference_schema:
        raise VectorIndexFullError(
            f"shard schema differs from reference schema:\n"
            f"got:      {shard_table.schema}\n"
            f"expected: {reference_schema}"
        )


def validate_chunk_table(table, expected_row_count: int) -> None:
    """Raises VectorIndexFullError on the first violated invariant:
    - row count matches expected_row_count
    - schema contains exactly EXPECTED_COLUMNS (order-independent, set
      equality - PyArrow/Lance schema field order is not itself a contract)
    - zero vector/ANN indexes exist on the table (scalar BTREE indexes on
      SCALAR_INDEX_COLUMNS are expected and NOT an error here - see module
      docstring for why this differs from Task 1.5's stricter check)
    """
    actual_count = table.count_rows()
    if actual_count != expected_row_count:
        raise VectorIndexFullError(f"row count {actual_count} != expected {expected_row_count}")

    schema_columns = set(table.schema.names)
    expected = set(EXPECTED_COLUMNS)
    if schema_columns != expected:
        missing = expected - schema_columns
        extra = schema_columns - expected
        raise VectorIndexFullError(f"schema mismatch - missing: {sorted(missing)}, extra: {sorted(extra)}")

    vector_field = table.schema.field("vector").type
    if not pa.types.is_fixed_size_list(vector_field) or vector_field.list_size != EMBEDDING_DIMENSION:
        raise VectorIndexFullError(f"unexpected vector field type: {vector_field}")

    indices = table.list_indices()
    vector_indices = [idx for idx in indices if idx.index_type in _VECTOR_INDEX_TYPES]
    if vector_indices:
        raise VectorIndexFullError(f"expected 0 vector/ANN indexes, found {len(vector_indices)}: {vector_indices}")


def existing_scalar_index_columns(table) -> set[str]:
    """The set of columns already carrying a (single-column) scalar index,
    used to make `build_scalar_indexes()` idempotent/resumable rather than
    raising on a rerun after a partially-completed prior attempt."""
    result = set()
    for idx in table.list_indices():
        if idx.index_type not in _VECTOR_INDEX_TYPES and list(idx.columns) and len(idx.columns) == 1:
            result.add(idx.columns[0])
    return result


def build_scalar_indexes(table, columns: tuple[str, ...] = SCALAR_INDEX_COLUMNS) -> list[str]:
    """Builds a BTree scalar index on each of `columns` not already
    indexed. Returns the list of columns actually (re)built this call.

    Uses `table.create_index(column, config=BTree(), ...)` rather than the
    shorter `table.create_scalar_index(column, index_type="BTREE")` -
    `create_scalar_index()` is deprecated as of lancedb 0.25.0 (this
    project is pinned to 0.37.1), mirroring the same deprecated-vs-current
    API distinction `src.index.lancedb_fts.build_fts_index()` already
    documents for `create_fts_index()`/`create_index(config=FTS())`.
    Verified empirically against the installed 0.37.1 API on a disposable
    synthetic table before writing this: `table.list_indices()[0].index_type
    == "BTree"` (not the deprecated call's "BTREE" string) and
    `.columns == [column]`.

    Mirrors this project's general "never silently rebuild" convention
    (`lancedb_fts.build_fts_index`'s own `replace=False` default) -
    `replace=False` here too, so a genuine conflicting index raises rather
    than being silently discarded."""
    from lancedb.index import BTree

    already = existing_scalar_index_columns(table)
    built = []
    for column in columns:
        if column in already:
            continue
        table.create_index(column, config=BTree(), name=f"{column}_btree", replace=False)
        built.append(column)
    return built


def validate_scalar_indexes(table, columns: tuple[str, ...] = SCALAR_INDEX_COLUMNS) -> None:
    present = existing_scalar_index_columns(table)
    missing = [c for c in columns if c not in present]
    if missing:
        raise VectorIndexFullError(f"expected scalar index(es) missing for column(s): {missing}")


__all__ = [
    "TABLE_NAME", "DISTANCE_METRIC", "EMBEDDING_DIMENSION", "INDEX_TYPE",
    "EXPECTED_COLUMNS", "SCALAR_INDEX_COLUMNS", "SCALAR_INDEX_TYPE",
    "VectorIndexFullError",
    "open_database", "create_chunk_table", "open_chunk_table", "append_shard",
    "validate_shard_schema", "validate_chunk_table",
    "existing_scalar_index_columns", "build_scalar_indexes", "validate_scalar_indexes",
]
