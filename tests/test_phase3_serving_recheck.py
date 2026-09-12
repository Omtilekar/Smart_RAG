"""Task 3.14 - portable tests for scripts/run_phase3_serving_recheck.py's
pure logic (apply_decision_thresholds) and AST-based static guards over
the script. No I/O, no DuckDB, no model, no network."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_phase3_serving_recheck.py"

import sys  # noqa: E402
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.run_phase3_serving_recheck import apply_decision_thresholds  # noqa: E402


# --------------------------------------------------------------- apply_decision_thresholds

@pytest.mark.parametrize("p95_ms,expected", [
    (0.0, "proceed_with_serverless_design"),
    (499.9, "proceed_with_serverless_design"),
    (500.0, "proceed_but_constrain_reranker_and_candidate_pool"),
    (1999.9, "proceed_but_constrain_reranker_and_candidate_pool"),
    (2000.0, "change_serving_target_to_warm_compute"),
    (4014.2, "change_serving_target_to_warm_compute"),
])
def test_apply_decision_thresholds_matches_frozen_table(p95_ms, expected):
    assert apply_decision_thresholds(p95_ms) == expected


# --------------------------------------------------------------- static guards

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


def test_script_never_writes_a_new_index():
    # This task re-measures against the frozen production index - it
    # must never build or overwrite one.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "create_chunk_table" not in source
    assert "create_table" not in source


def test_script_uses_cpu_device_for_the_recheck():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'device="cpu"' in source


def test_script_uses_frozen_qwen3_embedding_candidate():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'mr.CANDIDATES_BY_ID["qwen3_embedding"]' in source


def test_script_applies_cpu_thread_constraint():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "torch.set_num_threads(CPU_THREADS)" in source


def test_script_passes_qwen3_dimension_to_exact_cosine_search():
    # exact_cosine_search()'s default expected_dimension is bge-small's
    # 384 - qwen3_embedding is 1024-dim, so every call site must pass
    # expected_dimension=spec.dimension explicitly or every query
    # raises VectorIndexError at runtime.
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    calls = [line for line in source.splitlines() if "exact_cosine_search(table" in line]
    assert calls, "expected at least one exact_cosine_search(table, ...) call"
    for line in calls:
        assert "expected_dimension=spec.dimension" in line, line
