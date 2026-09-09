"""Static (AST-based) guards over scripts/run_phase3_chunking_ablation.py -
portable, no GPU/model/network required. Complements the live run's own
runtime guards (assert_frozen_scope/assert_dev_split, CANDIDATE_K checks)
with checks that hold even without executing the script."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_chunking_ablation.py"

_FORBIDDEN_MODULE_SUBSTRINGS = (
    "test_access",       # protected TEST split loader - DEV-only ablation
    "bm25", "rerank", "router", "crag",  # out-of-scope Phase 3 components
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


def test_script_never_imports_test_access():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        assert "test_access" not in module.lower()


def test_script_never_imports_bm25_rerank_router_crag():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        lowered = module.lower()
        for forbidden in ("bm25", "rerank", "router", "crag"):
            assert forbidden not in lowered, f"unexpected import touching {forbidden!r}: {module}"


def test_script_never_imports_generation_modules():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    for module in _imported_module_names(tree):
        lowered = module.lower()
        assert "generation" not in lowered and "llm_judge" not in lowered


def test_script_candidate_depth_is_fifty():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "CANDIDATE_K = 50" in source


def test_script_uses_frozen_metric_modules_not_reimplementations():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    # Must import the frozen Task 1.10/2.6/3.1 metric implementations rather
    # than defining its own doc_recall/mrr/ndcg logic.
    assert "from src.eval.baseline_metrics import evaluate_question, summarize_doc_recall" in source
    assert "from src.eval.metrics import" in source
    assert "from src.eval import phase3_baseline as p3" in source
