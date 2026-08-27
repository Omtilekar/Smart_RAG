"""Verify every implemented src.ingest module still imports cleanly, with
no network side effects, and without calling any main()/download entry
point. Catches future dependency/import regressions in the (frozen, not
otherwise refactored) Data Preparation code."""

import importlib

import pytest

INGEST_MODULES = [
    "src.ingest.common",
    "src.ingest.fetch_msmarco",
    "src.ingest.fetch_edgar_corpus",
    "src.ingest.fetch_xbrl",
    "src.ingest.fetch_primary_docs",
    "src.ingest.validate",
    "src.ingest.audit_data",
]


@pytest.mark.parametrize("module_name", INGEST_MODULES)
def test_ingest_module_imports(module_name):
    importlib.import_module(module_name)
