"""Static (AST-based) guards over scripts/run_phase3_crag.py - portable,
no LanceDB/GPU/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_crag.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",              # protected TEST split loader - DEV-only task
    "router",                   # out-of-scope Phase 3 component
    "generation", "llm_judge",  # generation is OFF for Task 3.7
    "lancedb_fts", "reranked", "rerank.cross_encoder",  # CRAG grades the unreranked dense-only pool
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


def test_script_uses_frozen_crag_and_metric_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.crag import confidence as crag" in source
    assert "from src.eval import phase3_crag as p3c" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval.metrics import" in source
