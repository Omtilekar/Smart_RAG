"""Static (AST-based) guards over scripts/run_phase3_filter.py -
portable, no LanceDB/GPU/model/network required."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_filter.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",                       # protected TEST split loader - DEV-only task
    "generation", "llm_judge",           # generation is OFF for Task 3.9
    "lancedb_fts", "reranked", "cross_encoder",  # metadata pre-filtering is dense-only
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


def test_script_uses_frozen_router_and_filter_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "from src.retrieval.filtered import MetadataFilteredRetriever" in source
    assert "from src.router.rules import CompanyGazetteer, classify_intent" in source
    assert "from src.eval import phase3_baseline as p3" in source
    assert "from src.eval import phase3_ablation as p3a" in source
    assert "from src.eval import phase3_filter as p3f" in source


def test_script_never_uses_oracle_ground_truth_cik_or_fiscal_year():
    # The filter must derive cik/fiscal_year from classify_intent()'s
    # extraction, never from the question record's own hidden fields.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'q["cik"]' not in source
    assert 'q["fiscal_year"]' not in source
