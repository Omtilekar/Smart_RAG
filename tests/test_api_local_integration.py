"""Task 4.10 - optional local real-pipeline integration test
(`local_data`-marked). Real BGE embedding model + real Phase 1 dev-corpus
LanceDB index + real `data/xbrl.duckdb` connection/gazetteer, but the
generation PROVIDER is a deterministic fake - proves the full HTTP ->
service -> router -> retrieval -> generation wiring without spending any
API credits. Never uses protected TEST. Never claims this is production
load testing (a single small request against a fake provider, nothing
more).
"""

import duckdb
import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dependencies import (
    DEV_CHUNK_CONFIG_HASH,
    DEV_EMBEDDING_MODEL_REPO,
    ProductionDependencies,
    build_production_gazetteer,
)
from src.config import get_settings
from src.eval.tag_registry import get_registry
from src.generation.minimal import MinimalGenerator
from src.generation.provider import GenerationRequest, ProviderResponse
from src.index.lancedb_index import open_chunk_table, open_database
from src.retrieval.baseline import BaselineRetriever
from src.sql.xbrl_lookup import XbrlFactIndex
from src.storage import get_storage


class _DeterministicFakeProvider:
    """Never a real network/model call - always returns the same fixed
    text regardless of the (real) retrieved context, citing the first
    real chunk_id it's given so citation validation has something real
    to check against."""

    def generate(self, request: GenerationRequest) -> ProviderResponse:
        return ProviderResponse(
            text="This is a deterministic fake answer for local integration testing.",
            requested_model="fake/local-integration", response_model="fake/local-integration",
            provider_name="fake", response_provider=None, prompt_tokens=1, completion_tokens=1,
            total_tokens=2, temperature_requested=request.temperature, latency_ms=0.1,
        )


@pytest.mark.local_data
def test_real_pipeline_wiring_with_fake_provider():
    storage = get_storage()
    db_path = storage.index_dir(DEV_CHUNK_CONFIG_HASH, DEV_EMBEDDING_MODEL_REPO)
    if not db_path.is_dir():
        pytest.skip(f"Phase 1 dev-corpus LanceDB index not present at {db_path}")
    if not storage.xbrl_db.is_file():
        pytest.skip(f"xbrl.duckdb not present at {storage.xbrl_db}")

    from src.embeddings.bge import load_model

    db = open_database(db_path)
    table = open_chunk_table(db)
    embed_model = load_model(device="cuda")
    retriever = BaselineRetriever(model=embed_model, table=table)
    generator = MinimalGenerator(retriever, _DeterministicFakeProvider())

    registry = get_registry()
    xbrl_con = duckdb.connect(str(storage.xbrl_db), read_only=True)
    try:
        gazetteer = build_production_gazetteer(xbrl_con)
        xbrl_index = XbrlFactIndex(xbrl_con, registry.supported_tags())

        deps = ProductionDependencies(
            generator=generator, gazetteer=gazetteer, registry=registry, xbrl_index=xbrl_index,
            settings=get_settings(),
            xbrl_con=xbrl_con, lancedb_table=table,
        )
        app = create_app(dependencies=deps)
        with TestClient(app) as client:
            r = client.get("/health")
            assert r.status_code == 200

            r = client.get("/status")
            assert r.status_code == 200
            assert r.json()["ready"] is True
            assert r.json()["config"]["dense_index_row_count"] == 162357

            r = client.post("/query", json={"question": "What was the company's total revenue?"})
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "answered"
            assert body["route"] == "dense"
            assert body["answer"] == "This is a deterministic fake answer for local integration testing."
    finally:
        xbrl_con.close()
