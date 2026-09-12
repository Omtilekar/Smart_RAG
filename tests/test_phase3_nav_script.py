"""Static (AST-based) guards over scripts/run_phase3_nav.py - portable,
no DuckDB/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_nav.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",                                              # protected TEST split loader - DEV-only task
    "generation", "llm_judge",                                  # generation is OFF for Task 3.12
    "lancedb", "reranked", "cross_encoder", "model_registry",    # navigation needs no retrieval/embedding search
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


def test_script_uses_frozen_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.nav.section_navigation import navigate_to_section, resolve_filing_document_id" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval import phase3_nav as p3n" in source


def test_script_opens_xbrl_db_read_only():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "read_only=True" in source


def test_script_never_writes_into_the_task_2_8_parsed_corpus():
    # This task reads Task 2.8's already-parsed structural-node JSON
    # files; it must never open one for writing.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"w"' not in source
    assert "'w'" not in source
