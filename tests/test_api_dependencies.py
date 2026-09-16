"""Tests for src/api/dependencies.py (Task 4.10) - only the pure/cheap
parts (build_production_gazetteer, DependencyInitializationError). Real
build_production_dependencies() is exercised only by the local_data-
marked integration test in tests/test_api_local_integration.py, since it
loads the real BGE model and opens the real LanceDB index.

Task 4.11 adds a fully-mocked portable test for
build_production_dependencies()'s device selection: a CPU-only Fargate
container has no CUDA device, so the embedding model must load on
whatever src.config.resolve_device(settings.device) resolves to - never
a hardcoded "cuda" (the bug this guards against previously made every
deployment target that isn't this GPU dev box crash at startup).
"""

import types

from src.api.dependencies import (
    DEV_CHUNK_CONFIG_HASH,
    DEV_EMBEDDING_MODEL_REPO,
    build_production_gazetteer,
)


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        assert "SELECT DISTINCT cik, name FROM submissions" in sql
        return self

    def fetchall(self):
        return self._rows


def test_build_production_gazetteer_maps_names_to_ciks():
    con = FakeConnection([(1000, "ACME CORP"), (2000, "WIDGET INC")])
    gazetteer = build_production_gazetteer(con)
    assert gazetteer.resolve("What did ACME CORP report?") == [("ACME CORP", 1000)]


def test_build_production_gazetteer_skips_null_or_blank_names():
    con = FakeConnection([(1000, None), (2000, ""), (3000, "  "), (4000, "REAL CO")])
    gazetteer = build_production_gazetteer(con)
    assert gazetteer.resolve("REAL CO filed a 10-K") == [("REAL CO", 4000)]


def test_build_production_gazetteer_handles_empty_submissions():
    con = FakeConnection([])
    gazetteer = build_production_gazetteer(con)
    assert gazetteer.resolve("Any question at all") == []


def test_dev_identity_constants_are_the_frozen_task_1_5_values():
    # Regression guard: these must stay byte-identical to src/cli/phase1.py's
    # own CHUNK_CONFIG_HASH/MODEL_REPO constants - both name the same
    # frozen Task 1.5 dev-corpus index.
    import src.cli.phase1 as cli
    assert DEV_CHUNK_CONFIG_HASH == cli.CHUNK_CONFIG_HASH
    assert DEV_EMBEDDING_MODEL_REPO == cli.MODEL_REPO


class _FakeTable:
    def count_rows(self):
        return 0


class _FakeStorage:
    def __init__(self, index_dir_path):
        self._index_dir_path = index_dir_path
        self.xbrl_db = index_dir_path  # unused - duckdb.connect is mocked below

    def index_dir(self, chunk_config_hash, embedding_model):
        return self._index_dir_path


def _fake_settings(device):
    from src.config import Settings
    return Settings(
        app_env="test", repo_root=None, storage_root=None,
        embedding_model="BAAI/bge-small-en-v1.5", device=device,
        generation_provider="openrouter", generation_model="openai/gpt-oss-20b",
        log_level="INFO", sec_user_agent=None, input_guard_max_length=2000,
    )


def _mock_everything_except_load_model_and_device(monkeypatch, deps_module, tmp_path):
    monkeypatch.setattr(deps_module, "get_storage", lambda: _FakeStorage(tmp_path))
    monkeypatch.setattr(deps_module, "open_database", lambda path: object())
    monkeypatch.setattr(deps_module, "open_chunk_table", lambda db: _FakeTable())
    monkeypatch.setattr(deps_module, "BaselineRetriever", lambda model, table: object())
    monkeypatch.setattr(deps_module, "get_generation_provider", lambda settings: object())
    monkeypatch.setattr(deps_module, "MinimalGenerator", lambda retriever, provider: object())
    monkeypatch.setattr(deps_module, "get_registry", lambda: types.SimpleNamespace(supported_tags=lambda: ()))
    monkeypatch.setattr(deps_module, "build_production_gazetteer", lambda con: object())
    monkeypatch.setattr(deps_module, "XbrlFactIndex", lambda con, tags: object())
    monkeypatch.setattr(deps_module.duckdb, "connect", lambda path, read_only=True: object())


def test_build_production_dependencies_loads_embedding_model_on_configured_cpu_device(monkeypatch, tmp_path):
    import src.api.dependencies as deps_module

    recorded = {}

    def fake_load_model(device):
        recorded["device"] = device
        return object()

    monkeypatch.setattr(deps_module, "load_model", fake_load_model)
    _mock_everything_except_load_model_and_device(monkeypatch, deps_module, tmp_path)

    deps_module.build_production_dependencies(_fake_settings("cpu"))

    assert recorded["device"] == "cpu"


def test_build_production_dependencies_resolves_auto_device_through_resolve_device(monkeypatch, tmp_path):
    import src.api.dependencies as deps_module

    recorded = {}

    def fake_load_model(device):
        recorded["device"] = device
        return object()

    monkeypatch.setattr(deps_module, "load_model", fake_load_model)
    monkeypatch.setattr(deps_module, "resolve_device", lambda requested: f"resolved-from-{requested}")
    _mock_everything_except_load_model_and_device(monkeypatch, deps_module, tmp_path)

    deps_module.build_production_dependencies(_fake_settings("auto"))

    assert recorded["device"] == "resolved-from-auto"
