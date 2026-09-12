"""Static (AST-based) guards over scripts/run_phase3_router.py -
portable, no LanceDB/GPU/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_router.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",                       # protected TEST split loader - DEV-only task
    "generation", "llm_judge",           # generation is OFF for Task 3.8
    "lancedb_fts", "reranked", "cross_encoder",  # router classification needs no sparse/rerank
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


def test_script_never_loads_a_model():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        assert module.lower() not in ("torch", "sentence_transformers")


def test_script_uses_frozen_router_and_registry_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.router.rules import" in source
    assert "from src.eval.tag_registry import get_registry" in source
    assert "from src.eval import phase3_router as p3rt" in source
    assert "from src.eval import phase3_baseline as p3" in source
