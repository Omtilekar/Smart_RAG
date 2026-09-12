"""Static (AST-based) guards over scripts/run_phase3_derived.py -
portable, no DuckDB/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_derived.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",                                        # protected TEST split loader - DEV-only task
    "generation", "llm_judge",                            # generation is OFF for Task 3.11
    "lancedb", "reranked", "cross_encoder", "model_registry",  # derived calculations need no retrieval/embedding
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
    assert "from src.sql.xbrl_lookup import XbrlFactIndex" in source
    assert "from src.sql.derived import compute_difference, compute_greater_than" in source
    assert "from src.router.rules import CompanyGazetteer, classify_intent" in source
    assert "from src.eval.metrics import numeric_exact_match" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval import phase3_derived as p3d" in source


def test_script_opens_xbrl_db_read_only():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "read_only=True" in source


def test_script_never_uses_oracle_ground_truth_for_extraction():
    # cik/fiscal_year/operands must come from classify_intent()'s
    # extraction, never the question record's own hidden fields (those
    # are only used afterward to score the computed result).
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'cik=q["cik"]' not in source
    assert 'fiscal_year_a=q[' not in source
