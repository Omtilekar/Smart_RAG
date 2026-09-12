"""Static (AST-based) guards over scripts/run_phase3_bm25_fts_baseline.py -
portable, no LanceDB build/GPU/model/network required. Mirrors
tests/test_phase3_chunking_ablation_script.py's convention."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_bm25_fts_baseline.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",                          # protected TEST split loader - DEV-only baseline
    "rerank", "router", "crag",             # out-of-scope Phase 3 components
    "generation", "llm_judge",              # generation is OFF for Task 3.4
    "sentence_transformers", "model_registry",  # no dense embedding model is loaded
)


def _imported_module_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_script_exists():
    assert SCRIPT_PATH.is_file()


def test_script_never_imports_forbidden_modules():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        lowered = module.lower()
        for forbidden in _FORBIDDEN_MODULE_SUBSTRINGS:
            assert forbidden not in lowered, f"unexpected import touching {forbidden!r}: {module}"


def test_script_candidate_depth_is_fifty():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "CANDIDATE_K = 50" in source


def test_script_uses_frozen_metric_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.eval.metrics import" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval import phase3_ablation as p3a" in source
    assert "from src.eval import phase3_sparse as p3s" in source


def test_script_never_uses_lancedb_deprecated_fts_api():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "create_fts_index" not in source


def test_script_never_calls_torch_or_loads_a_model():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        assert module.lower() != "torch"
