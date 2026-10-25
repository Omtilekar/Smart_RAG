"""Task 4.10 - real production dependency construction. Deliberately
separate from `src/api/app.py`/`create_app()` so importing the API layer
never loads Qwen/BGE, opens LanceDB, or connects to `xbrl.duckdb` -
`build_production_dependencies()` is only ever called from inside
`create_app()`'s lifespan, and only when the caller did not inject fakes.

Task 4.A (Gate A): the live dense route now defaults to the frozen
full-corpus production artifact (Qwen/Qwen3-Embedding-0.6B, 1024-d,
10,487,096 rows) through `src.retrieval.production.ProductionDenseRetriever`,
which adapts the 24-column `chunk_uid` production schema explicitly. The
Phase 1 dev path (BGE-small, 162,357 rows, `BaselineRetriever`) remains
available ONLY as an explicit `DENSE_RETRIEVER_MODE=dev` opt-in. Production
initialization is fail-closed: any model/index/identity failure raises
DependencyInitializationError - it never silently falls back to the dev
index. See project_plan/TASK_4A_PRODUCTION_DENSE_RETRIEVER.md.

The structured-XBRL route, by contrast, already operates on the real,
frozen `data/xbrl.duckdb` (Task 3.10) - no schema gap there.
"""

from __future__ import annotations

import duckdb

from src.config import Settings, get_settings, resolve_device
from src.embeddings.bge import EMBEDDING_DIMENSION, MODEL_REVISION, load_model
from src.embeddings.model_registry import QWEN3_EMBEDDING
from src.embeddings.model_registry import load_model as load_embedding_model
from src.eval.tag_registry import get_registry
from src.generation.factory import get_generation_provider
from src.generation.minimal import MinimalGenerator
from src.index.lancedb_index import DISTANCE_METRIC, INDEX_TYPE, TABLE_NAME, open_chunk_table, open_database
from src.index.lancedb_index_full import open_chunk_table as open_production_table
from src.index.lancedb_index_full import open_database as open_production_database
from src.retrieval.baseline import BaselineRetriever
from src.retrieval.cache import CachedRetriever, ExactRetrievalCache
from src.retrieval.production import (
    ProductionDenseRetriever, ProductionIndexError, build_production_cache_identity,
    load_production_contract, smoke_lookup, validate_production_table,
)
from src.router.rules import CompanyGazetteer
from src.security import RetrievalSecurityGuard
from src.storage import get_storage
from src.sql.xbrl_lookup import XbrlFactIndex

# Task 1.5/1.6/1.11's frozen dev-corpus identity - reused verbatim
# (matches src/cli/phase1.py's own CHUNK_CONFIG_HASH/MODEL_REPO
# constants), never re-derived.
DEV_CHUNK_CONFIG_HASH = "f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd"
DEV_EMBEDDING_MODEL_REPO = "BAAI/bge-small-en-v1.5"


class DependencyInitializationError(RuntimeError):
    """Raised when a required production dependency cannot be
    constructed (e.g. the dev index is absent on this machine) - a clear,
    early failure, never silently downgraded to a degraded app."""


def build_live_dense_retrieval_cache_identity(settings: Settings, *, dense_row_count: int) -> dict:
    """Artifact/config identity for the currently live dense retriever.

    Future production full-corpus integration should build the analogous
    identity from its own Qwen/table/schema/build hashes so stale dev-index
    cache entries cannot collide with production-index retrieval.
    """
    return {
        "cache_schema_version": settings.retrieval_cache_schema_version,
        "route": "dense",
        "retriever_kind": "baseline_dev_exact_cosine",
        "embedding_model_identity": DEV_EMBEDDING_MODEL_REPO,
        "embedding_model_revision": MODEL_REVISION,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "chunk_config_hash": DEV_CHUNK_CONFIG_HASH,
        "dense_index_table": TABLE_NAME,
        "dense_index_schema": "phase1_dev_17_column_chunk_id",
        "dense_index_artifact_identity": DEV_CHUNK_CONFIG_HASH,
        "dense_index_row_count": dense_row_count,
        "retrieval_algorithm": INDEX_TYPE,
        "similarity_metric": DISTANCE_METRIC,
        "crag_threshold": None,
    }


def build_production_gazetteer(con) -> CompanyGazetteer:
    """Task 3.8's own frozen config (`configs/phase_3_8_rules_first_router.json`,
    `gazetteer_source`) explicitly names this as the production stand-in:
    "a production router would instead resolve against the full SEC
    company/CIK submissions list." Queries the frozen, read-only
    `data/xbrl.duckdb` `submissions` table (the same table
    `src.nav.section_navigation.resolve_filing_document_id()` already
    reads) - never a new, independently-decided company-name source."""
    rows = con.execute("SELECT DISTINCT cik, name FROM submissions WHERE name IS NOT NULL").fetchall()
    entries: dict[str, int] = {}
    for cik, name in rows:
        if name and name.strip():
            entries[name] = cik
    return CompanyGazetteer(entries)


class ProductionDependencies:
    """Long-lived resources held for the app's lifetime - constructed
    once at startup, reused across requests, never per-request."""

    def __init__(self, *, generator: MinimalGenerator, gazetteer: CompanyGazetteer,
                 registry, xbrl_index: XbrlFactIndex, settings: Settings,
                 xbrl_con, lancedb_table, retrieval_cache: ExactRetrievalCache | None = None,
                 retrieval_security_guard: RetrievalSecurityGuard | None = None,
                 dense_runtime: dict | None = None):
        self.generator = generator
        self.gazetteer = gazetteer
        self.registry = registry
        self.xbrl_index = xbrl_index
        self.settings = settings
        self._xbrl_con = xbrl_con
        self._lancedb_table = lancedb_table
        self.retrieval_cache = retrieval_cache
        self.dense_runtime = dense_runtime
        self.retrieval_security_guard = (
            retrieval_security_guard
            or getattr(generator, "retrieval_security_guard", None)
            or RetrievalSecurityGuard()
        )

    def close(self) -> None:
        self._xbrl_con.close()

    def _config_snapshot(self) -> dict:
        config = {
            "generation_provider": self.settings.generation_provider,
            "generation_model": self.settings.generation_model,
        }
        runtime = self.dense_runtime
        if runtime is None:
            # Legacy construction (tests/injected fakes): dev-shaped snapshot.
            config.update({
                "dev_chunk_config_hash": DEV_CHUNK_CONFIG_HASH,
                "dev_embedding_model": DEV_EMBEDDING_MODEL_REPO,
                "dense_index_row_count": self._lancedb_table.count_rows(),
            })
            return config
        config.update(runtime)
        if runtime.get("dense_retriever_mode") == "dev":
            config["dev_chunk_config_hash"] = DEV_CHUNK_CONFIG_HASH
            config["dev_embedding_model"] = DEV_EMBEDDING_MODEL_REPO
        return config

    def status_snapshot(self) -> dict:
        snapshot = {
            "dependencies": {
                "embedding_model_loaded": True,
                "dense_index_open": True,
                "xbrl_connection_open": True,
                "generation_provider_configured": bool(self.settings.generation_provider and self.settings.generation_model),
            },
            "config": self._config_snapshot(),
        }
        if self.retrieval_cache is not None:
            snapshot["retrieval_cache"] = self.retrieval_cache.stats()
        snapshot["retrieval_security"] = self.retrieval_security_guard.status_snapshot()
        prompt_cache_metrics = getattr(getattr(self.generator, "provider", None), "metrics", None)
        snapshot["prompt_cache"] = {
            "enabled": self.settings.prompt_cache_enabled,
            "provider_mode": self.settings.prompt_cache_provider_mode,
            **(prompt_cache_metrics.snapshot() if prompt_cache_metrics is not None else {}),
        }
        return snapshot


def _build_dev_dense(settings: Settings, storage):
    """Phase 1 dev path (explicit DENSE_RETRIEVER_MODE=dev only)."""
    db_path = storage.index_dir(DEV_CHUNK_CONFIG_HASH, DEV_EMBEDDING_MODEL_REPO)
    if not db_path.is_dir():
        raise DependencyInitializationError(
            f"Phase 1 dev-corpus LanceDB index not found at {db_path} - "
            f"run scripts/build_vector_index.py first."
        )
    db = open_database(db_path)
    table = open_chunk_table(db)

    embed_model = load_model(device=resolve_device(settings.device))
    base_retriever = BaselineRetriever(model=embed_model, table=table)
    dense_row_count = table.count_rows()
    cache_identity = build_live_dense_retrieval_cache_identity(settings, dense_row_count=dense_row_count)
    runtime = {
        "dense_retriever_mode": "dev",
        "embedding_model": DEV_EMBEDDING_MODEL_REPO,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "dense_index_row_count": dense_row_count,
        "artifact_status": "development",
    }
    return base_retriever, table, cache_identity, runtime


def _build_production_dense(settings: Settings, storage):
    """Task 4.A production path: frozen Qwen3 + 10,487,096-row LanceDB
    artifact. Fail-closed - every failure becomes a concise
    DependencyInitializationError; there is no dev fallback."""
    try:
        contract = load_production_contract(settings.repo_root)
        db_path = storage.index_dir_full(
            contract.phase_4_1_config_hash, contract.chunk_config_hash,
            contract.embedding_model, contract.embedding_model_revision,
        )
        if not db_path.is_dir():
            raise DependencyInitializationError("production dense index directory not found")
        db = open_production_database(db_path)
        table = open_production_table(db)
        validate_production_table(table, contract)
        smoke = smoke_lookup(table)
        embed_model = load_embedding_model(QWEN3_EMBEDDING, device=resolve_device(settings.device))
    except DependencyInitializationError:
        raise
    except ProductionIndexError as exc:
        raise DependencyInitializationError(f"production dense retriever unavailable: {exc}") from None
    except Exception as exc:  # noqa: BLE001 - concise reason only, never a raw stack trace
        raise DependencyInitializationError(
            f"production dense retriever unavailable: {type(exc).__name__}"
        ) from None

    row_count = table.count_rows()
    retriever = ProductionDenseRetriever(QWEN3_EMBEDDING, embed_model, table)
    cache_identity = build_production_cache_identity(
        contract, schema_version=settings.retrieval_cache_schema_version, row_count=row_count,
    )
    runtime = {
        "dense_retriever_mode": "production",
        "embedding_model": contract.embedding_model,
        "embedding_model_revision": contract.embedding_model_revision,
        "embedding_dimension": contract.embedding_dimension,
        "dense_index_row_count": row_count,
        "dense_index_identity_hash": contract.index_identity_hash,
        "artifact_status": "production",
        "startup_smoke_self_distance": smoke["self_distance"],
    }
    return retriever, table, cache_identity, runtime


def build_production_dependencies(settings: Settings | None = None) -> ProductionDependencies:
    """Opens the dense retriever selected by `settings.dense_retriever_mode`
    (default "production": the frozen Qwen3/10,487,096-row artifact; "dev":
    the Phase 1 BGE dev index), connects to the real `data/xbrl.duckdb`,
    and resolves the real generation provider via Task 4.6's
    `get_generation_provider()` factory. Raises
    DependencyInitializationError with a concise message on any failure -
    production mode never falls back to the dev index."""
    if settings is None:
        settings = get_settings()

    storage = get_storage()
    if settings.dense_retriever_mode == "dev":
        base_retriever, table, cache_identity, dense_runtime = _build_dev_dense(settings, storage)
    else:
        base_retriever, table, cache_identity, dense_runtime = _build_production_dense(settings, storage)

    retrieval_cache = ExactRetrievalCache(
        enabled=settings.retrieval_cache_enabled,
        max_entries=settings.retrieval_cache_max_entries,
        ttl_seconds=settings.retrieval_cache_ttl_seconds,
    )
    if settings.retrieval_cache_enabled:
        retriever = CachedRetriever(base_retriever, cache=retrieval_cache, static_identity=cache_identity)
    else:
        retriever = base_retriever
    provider = get_generation_provider(settings)
    generator = MinimalGenerator(retriever, provider, cache_friendly_prompt=settings.prompt_cache_enabled)

    registry = get_registry()
    xbrl_con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    gazetteer = build_production_gazetteer(xbrl_con)
    xbrl_index = XbrlFactIndex(xbrl_con, registry.supported_tags())

    return ProductionDependencies(
        generator=generator, gazetteer=gazetteer, registry=registry, xbrl_index=xbrl_index,
        settings=settings, xbrl_con=xbrl_con, lancedb_table=table,
        retrieval_cache=retrieval_cache,
        retrieval_security_guard=getattr(generator, "retrieval_security_guard", None),
        dense_runtime=dense_runtime,
    )


__all__ = [
    "DEV_CHUNK_CONFIG_HASH", "DEV_EMBEDDING_MODEL_REPO",
    "DependencyInitializationError", "ProductionDependencies",
    "build_live_dense_retrieval_cache_identity", "build_production_gazetteer",
    "build_production_dependencies",
]
