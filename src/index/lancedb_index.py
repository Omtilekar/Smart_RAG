"""Task 1.5 - minimal exact-cosine LanceDB vector index.

Frozen Phase 1 vector-index contract (Decisions 1-4 explicitly approved
before this task began - see project_plan/PHASE1_VECTOR_INDEX.md):

- plain LanceDB table, exact/flat search, NO ANN index
- cosine distance metric, requested explicitly (LanceDB's default is L2)
- table name: "chunks"
- all 17 Task 1.4 columns retained (self-contained - no join back to
  chunks.parquet needed for text/metadata)

Empirically verified LanceDB 0.37.1 behavior (see PHASE1_VECTOR_INDEX.md
for the synthetic-vector verification this was based on):

- `lancedb.connect(path)` treats `path` itself as the database root - no
  nested "db"/"store" subdirectory is created or needed
- `create_table()` creates zero ANN indexes automatically
  (`table.list_indices() == []` immediately after creation) - exact/flat
  search is simply what `.search()` does until `.create_index()` is
  explicitly called, which this module never does
- `.distance_type("cosine")` (not the deprecated `.metric()` alias) must be
  called explicitly per query - the untouched default is "l2"
- results carry the distance in a `_distance` column; LOWER is more
  similar (identical vectors -> ~0.0, orthogonal -> ~1.0, opposite -> ~2.0)

No embedding model is loaded here - see scripts/build_vector_index.py for
orchestration and src/embeddings/bge.py for the (separate) query-encoding
path Task 1.6 will use.
"""

from __future__ import annotations

import numpy as np
import pyarrow as pa

TABLE_NAME = "chunks"
DISTANCE_METRIC = "cosine"
EMBEDDING_DIMENSION = 384

# Exact column order expected from Task 1.4's embeddings.parquet - all 17
# retained, nothing dropped, nothing fabricated.
EXPECTED_COLUMNS: tuple[str, ...] = (
    "chunk_id", "document_id", "cik", "company", "form_type", "fiscal_year",
    "source", "source_filename", "source_split", "ordinal", "text",
    "token_count", "chunk_config_hash", "normalizer_version",
    "normalization_build_sha256", "development_manifest_sha256", "vector",
)


INDEX_TYPE = "exact_flat"  # no ANN index - matches this module's frozen Phase 1 contract


class VectorIndexError(ValueError):
    """Raised for a malformed query vector or a table that fails validation."""


def index_identity(*, chunk_schema_version: int, chunk_config_hash: str,
                    embedding_identity_hash_value: str) -> dict:
    """Task 2.10 - the structured semantic identity of this exact Phase 1
    LanceDB index configuration (exact/flat search, cosine, table
    "chunks"), bound to the chunk and embedding semantics that produced it.
    `INDEX_TYPE`/`DISTANCE_METRIC`/`TABLE_NAME` are this module's own
    frozen constants - never duplicated/guessed elsewhere. Extensible for
    Phase 3 (IVF_PQ/FTS/hybrid) via a different `index_type` computed the
    same way, without changing this module's Phase 1 contract."""
    from src.artifacts.versioning import compute_index_identity
    return compute_index_identity(
        chunk_schema_version=chunk_schema_version,
        chunk_config_hash=chunk_config_hash,
        embedding_identity_hash=embedding_identity_hash_value,
        distance_metric=DISTANCE_METRIC,
        index_type=INDEX_TYPE,
        table_name=TABLE_NAME,
    )


def open_database(db_path):
    """`db_path` (typically storage.index_dir(chunk_config_hash,
    embedding_model)) is used directly as the LanceDB database root - no
    additional nested directory layer."""
    import lancedb
    return lancedb.connect(str(db_path))


def create_chunk_table(db, data: pa.Table):
    """Creates the single application table `chunks` from a PyArrow table
    (native ingestion, no per-row Python conversion). Creates no ANN
    index - callers must never call .create_index() for the Phase 1
    baseline."""
    return db.create_table(TABLE_NAME, data=data)


def open_chunk_table(db):
    return db.open_table(TABLE_NAME)


def validate_chunk_table(table, expected_row_count: int) -> None:
    """Raises VectorIndexError on the first violated invariant:
    - row count matches expected_row_count
    - schema contains exactly EXPECTED_COLUMNS (order-independent check,
      set equality - PyArrow/Lance schema field order is not itself a
      contract)
    - zero ANN/vector indexes exist on the table
    """
    actual_count = table.count_rows()
    if actual_count != expected_row_count:
        raise VectorIndexError(f"row count {actual_count} != expected {expected_row_count}")

    schema_columns = set(table.schema.names)
    expected = set(EXPECTED_COLUMNS)
    if schema_columns != expected:
        missing = expected - schema_columns
        extra = schema_columns - expected
        raise VectorIndexError(f"schema mismatch - missing: {sorted(missing)}, extra: {sorted(extra)}")

    indices = table.list_indices()
    if len(indices) != 0:
        raise VectorIndexError(f"expected 0 ANN indexes, found {len(indices)}: {indices}")


def validate_query_vector(vector, expected_dimension: int = EMBEDDING_DIMENSION) -> np.ndarray:
    """Rejects (never truncates/pads) a malformed query vector. Returns a
    validated (expected_dimension,) float32 numpy array.

    `expected_dimension` defaults to this module's own frozen 384 (BGE-
    small) - Task 3.3 callers benchmarking a different-dimension model
    MUST pass their own spec.dimension explicitly, or a legitimate
    768/1024-dim query vector is rejected as "malformed" (verified: this
    exact bug raised VectorIndexError for bge_base's 768-dim queries mid-
    run)."""
    arr = np.asarray(vector, dtype=np.float32)
    if arr.ndim != 1 or arr.shape[0] != expected_dimension:
        raise VectorIndexError(f"expected a 1D vector of length {expected_dimension}, got shape {arr.shape}")
    if arr.size == 0:
        raise VectorIndexError("query vector is empty")
    if not np.isfinite(arr).all():
        raise VectorIndexError("query vector contains NaN or +-Inf")
    return arr


def get_chunk_by_id(table, chunk_id: str) -> pa.Table:
    """Task 1.8 - exact scalar-filter identity lookup, NOT a vector search.
    Returns a PyArrow table with 0 or 1 rows. Uses table.search().where(...)
    with no vector argument (a pure metadata scan/filter, verified directly
    against the installed LanceDB 0.37.1 to perform no similarity search at
    all) - never embeds the ID, never fuzzy-matches, never falls back to a
    document_id-only match."""
    escaped = chunk_id.replace("'", "''")
    return table.search().where(f"chunk_id = '{escaped}'").to_arrow()


def exact_cosine_search(table, query_vector, limit: int, expected_dimension: int = EMBEDDING_DIMENSION) -> pa.Table:
    """Validates `query_vector` (raises VectorIndexError if malformed),
    then performs an exact (no ANN index exists) cosine-distance search.
    Returns a PyArrow table with all persisted columns plus `_distance`
    (lower = more similar). Accepts only a numeric vector - never a
    natural-language question (that is Task 1.6's job, via
    src.embeddings.bge.encode_queries -> this function).

    `expected_dimension` defaults to 384 (BGE-small) - pass the real
    model dimension explicitly for any non-BGE-small candidate."""
    if limit <= 0:
        raise VectorIndexError(f"limit must be positive, got {limit}")
    validated = validate_query_vector(query_vector, expected_dimension=expected_dimension)
    return (
        table.search(validated)
        .distance_type(DISTANCE_METRIC)
        .limit(limit)
        .to_arrow()
    )
