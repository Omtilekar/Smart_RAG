"""Verify critical dependencies (Task 0.4) import successfully. This checks
installation consistency, not GPU capability - torch is expected to import
in a CPU-only public environment too, so no CUDA assertion belongs here
(see tests/test_gpu_smoke.py for that)."""

import importlib

import pytest

CORE_PACKAGES = [
    "requests",
    "duckdb",
    "pyarrow",
    "bs4",
    "lxml",
    "sentence_transformers",
    "lancedb",
    "fastapi",
    "pytest",
    "torch",
]


@pytest.mark.parametrize("package", CORE_PACKAGES)
def test_core_package_imports(package):
    importlib.import_module(package)
