"""Tests for src/api/dependencies.py (Task 4.10) - only the pure/cheap
parts (build_production_gazetteer, DependencyInitializationError). Real
build_production_dependencies() is exercised only by the local_data-
marked integration test in tests/test_api_local_integration.py, since it
loads the real BGE model and opens the real LanceDB index.
"""

from src.api.dependencies import DEV_CHUNK_CONFIG_HASH, DEV_EMBEDDING_MODEL_REPO, build_production_gazetteer


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
