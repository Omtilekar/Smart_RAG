"""Static (AST-based) guards over scripts/run_phase3_reranker.py -
portable, no LanceDB/GPU/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_reranker.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",              # protected TEST split loader - DEV-only task
    "router", "crag",           # out-of-scope Phase 3 components
    "generation", "llm_judge",  # generation is OFF for Task 3.6
    "lancedb_fts", "sparse",    # reranking operates on dense-only, not sparse/hybrid
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


def test_script_base_k_is_fifty():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "BASE_K = 50" in source


def test_script_uses_frozen_metric_and_rerank_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.eval.metrics import" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval import phase3_ablation as p3a" in source
    assert "from src.eval import phase3_rerank as p3r" in source
    assert "from src.rerank import cross_encoder as ce" in source


def test_script_uses_pinned_revision_not_main():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'revision="main"' not in source
