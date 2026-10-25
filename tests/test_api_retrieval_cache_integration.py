from fastapi.testclient import TestClient

from src.api.app import create_app
from src.config import Settings
from src.generation.provider import GenerationRequest, ProviderResponse
from src.retrieval.baseline import RetrievalResult
from src.router.rules import CompanyGazetteer


def _settings():
    return Settings(
        app_env="test",
        repo_root=None,
        storage_root=None,
        embedding_model="BAAI/bge-small-en-v1.5",
        device="cpu",
        generation_provider="fake",
        generation_model="fake/model",
        log_level="INFO",
        sec_user_agent=None,
        input_guard_max_length=2000,
        retrieval_cache_enabled=True,
        retrieval_cache_max_entries=16,
        retrieval_cache_ttl_seconds=900,
        retrieval_cache_schema_version="v1",
        dense_retriever_mode="dev",  # Task 4.A: this test exercises the explicit dev path with fakes
    )


def _chunk():
    return RetrievalResult(
        rank=1,
        score=0.9,
        distance=0.1,
        chunk_id="doc0.htm::chunk0",
        document_id="doc0.htm",
        text="Revenue was $1M.",
        cik=1000,
        company="ACME",
        form_type="10-K",
        fiscal_year=2019,
        source="edgar_corpus",
        source_filename="doc0.htm",
        source_split="train",
        ordinal=0,
        token_count=10,
        chunk_config_hash="abc123",
        normalizer_version="phase1-minimal-v1",
        normalization_build_sha256="x" * 64,
        development_manifest_sha256="y" * 64,
    )


class _FakeTable:
    def count_rows(self):
        return 162357


class _FakeStorage:
    def __init__(self, path):
        self._path = path
        self.xbrl_db = path / "xbrl.duckdb"

    def index_dir(self, chunk_config_hash, embedding_model):
        return self._path


class _FakeConnection:
    def close(self):
        pass


class _FakeXbrlIndex:
    def lookup(self, *, cik, fiscal_year, tag):
        raise AssertionError("dense-cache integration test should not enter structured XBRL")


class _CountingRetriever:
    instances = []

    def __init__(self, model, table):
        self.calls = []
        _CountingRetriever.instances.append(self)

    def retrieve(self, question, k=5):
        self.calls.append((question, k))
        return [_chunk()]


class _FakeProvider:
    def __init__(self):
        self.calls = []

    def generate(self, request: GenerationRequest) -> ProviderResponse:
        self.calls.append(request)
        return ProviderResponse(
            text="Revenue was $1M. [doc0.htm::chunk0]",
            requested_model="fake/model",
            response_model="fake/model",
            provider_name="fake",
            response_provider=None,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            temperature_requested=request.temperature,
            latency_ms=1.0,
        )


def test_dependency_wired_cache_hits_skip_dense_retrieval_but_not_generation(monkeypatch, tmp_path):
    import src.api.dependencies as deps_module

    _CountingRetriever.instances.clear()
    provider = _FakeProvider()

    monkeypatch.setattr(deps_module, "get_storage", lambda: _FakeStorage(tmp_path))
    monkeypatch.setattr(deps_module, "open_database", lambda path: object())
    monkeypatch.setattr(deps_module, "open_chunk_table", lambda db: _FakeTable())
    monkeypatch.setattr(deps_module, "load_model", lambda device: object())
    monkeypatch.setattr(deps_module, "BaselineRetriever", _CountingRetriever)
    monkeypatch.setattr(deps_module, "get_generation_provider", lambda settings: provider)
    monkeypatch.setattr(deps_module.duckdb, "connect", lambda path, read_only=True: _FakeConnection())
    monkeypatch.setattr(deps_module, "build_production_gazetteer", lambda con: CompanyGazetteer({}))
    monkeypatch.setattr(deps_module, "XbrlFactIndex", lambda con, tags: _FakeXbrlIndex())

    with TestClient(create_app(settings=_settings())) as client:
        first = client.post("/query", json={"question": "What was the company's total revenue?"})
        second = client.post("/query", json={"question": "What was the company's total revenue?"})
        status = client.get("/status").json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["route"] == "dense"
    assert second.json()["route"] == "dense"
    assert len(_CountingRetriever.instances) == 1
    assert len(_CountingRetriever.instances[0].calls) == 1
    assert len(provider.calls) == 2
    assert status["retrieval_cache"]["enabled"] is True
    assert status["retrieval_cache"]["misses"] == 1
    assert status["retrieval_cache"]["hits"] == 1
    assert status["retrieval_cache"]["entries"] == 1
