"""Task 4.10 - real production dependency construction. Deliberately
separate from `src/api/app.py`/`create_app()` so importing the API layer
never loads Qwen/BGE, opens LanceDB, or connects to `xbrl.duckdb` -
`build_production_dependencies()` is only ever called from inside
`create_app()`'s lifespan, and only when the caller did not inject fakes.

2026-09-16 explicit user decision: the dense route is wired to the same
Phase 1 dev-corpus index (162,357 rows, BGE-small) every prior task
(1.6-4.9) actually built and tested against -
`src.retrieval.baseline.BaselineRetriever`/`RetrievalResult` hardcode a
17-column schema that does not exist on the real 10,487,096-row Task 4.4
production index (which uses `chunk_uid` instead of `chunk_id` and drops
several dev-only provenance fields entirely - Task 4.1's full-corpus
frontmatter contract). No task ever built a schema-adapting retriever
for the full-corpus index; writing one now would mean new, previously-
untested retrieval-adjacent code, which is out of this task's "thin API
layer over stable modules" scope. See
project_plan/PHASE4_FASTAPI_SERVICE.md for the full account - this is a
documented, real limitation, not a silently narrowed claim.

The structured-XBRL route, by contrast, already operates on the real,
frozen `data/xbrl.duckdb` (Task 3.10) - no schema gap there.
"""

from __future__ import annotations

import duckdb

from src.config import Settings, get_settings, resolve_device
from src.embeddings.bge import load_model
from src.eval.tag_registry import get_registry
from src.generation.factory import get_generation_provider
from src.generation.minimal import MinimalGenerator
from src.index.lancedb_index import open_chunk_table, open_database
from src.retrieval.baseline import BaselineRetriever
from src.router.rules import CompanyGazetteer
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
                 xbrl_con, lancedb_table):
        self.generator = generator
        self.gazetteer = gazetteer
        self.registry = registry
        self.xbrl_index = xbrl_index
        self.settings = settings
        self._xbrl_con = xbrl_con
        self._lancedb_table = lancedb_table

    def close(self) -> None:
        self._xbrl_con.close()

    def status_snapshot(self) -> dict:
        return {
            "dependencies": {
                "embedding_model_loaded": True,
                "dense_index_open": True,
                "xbrl_connection_open": True,
                "generation_provider_configured": bool(self.settings.generation_provider and self.settings.generation_model),
            },
            "config": {
                "dev_chunk_config_hash": DEV_CHUNK_CONFIG_HASH,
                "dev_embedding_model": DEV_EMBEDDING_MODEL_REPO,
                "generation_provider": self.settings.generation_provider,
                "generation_model": self.settings.generation_model,
                "dense_index_row_count": self._lancedb_table.count_rows(),
            },
        }


def build_production_dependencies(settings: Settings | None = None) -> ProductionDependencies:
    """Loads the real BGE embedding model, opens the real Phase 1 dev-
    corpus LanceDB table, connects to the real `data/xbrl.duckdb`, and
    resolves the real generation provider via Task 4.6's
    `get_generation_provider()` factory (never hardcoding a provider
    class the way `src.cli.phase1._construct_generator()` does - this
    function is the FastAPI-service equivalent of that CLI helper, but
    resolves the provider through the more current Task 4.6 entry point).
    Raises DependencyInitializationError with a clear message if the dev
    index is not present on this machine."""
    if settings is None:
        settings = get_settings()

    storage = get_storage()
    db_path = storage.index_dir(DEV_CHUNK_CONFIG_HASH, DEV_EMBEDDING_MODEL_REPO)
    if not db_path.is_dir():
        raise DependencyInitializationError(
            f"Phase 1 dev-corpus LanceDB index not found at {db_path} - "
            f"run scripts/build_vector_index.py first."
        )
    db = open_database(db_path)
    table = open_chunk_table(db)

    embed_model = load_model(device=resolve_device(settings.device))
    retriever = BaselineRetriever(model=embed_model, table=table)
    provider = get_generation_provider(settings)
    generator = MinimalGenerator(retriever, provider)

    registry = get_registry()
    xbrl_con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    gazetteer = build_production_gazetteer(xbrl_con)
    xbrl_index = XbrlFactIndex(xbrl_con, registry.supported_tags())

    return ProductionDependencies(
        generator=generator, gazetteer=gazetteer, registry=registry, xbrl_index=xbrl_index,
        settings=settings, xbrl_con=xbrl_con, lancedb_table=table,
    )


__all__ = [
    "DEV_CHUNK_CONFIG_HASH", "DEV_EMBEDDING_MODEL_REPO",
    "DependencyInitializationError", "ProductionDependencies",
    "build_production_gazetteer", "build_production_dependencies",
]
