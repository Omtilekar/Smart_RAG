"""Task 4.9 - static (AST-based) proof that src/guards/output.py never
imports a forbidden dependency or calls a network-shaped function. Same
convention as tests/test_input_guards_static_safety.py (Task 4.7) and
tests/test_context_guards_static_safety.py (Task 4.8).
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_MODULE_PATH = REPO_ROOT / "src" / "guards" / "output.py"

FORBIDDEN_MODULE_PREFIXES = (
    "requests",
    "httpx",
    "lancedb",
    "sentence_transformers",
    "torch",
    "duckdb",
    "src.generation.openrouter",
    "src.generation.ollama_provider",
    "src.embeddings",
    "src.index",
    "src.retrieval",
    "src.eval.test_access",
)


def _imported_module_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_output_guard_module_imports_no_forbidden_dependency():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    for forbidden in FORBIDDEN_MODULE_PREFIXES:
        offenders = [name for name in imported if name == forbidden or name.startswith(forbidden + ".")]
        assert not offenders, f"src/guards/output.py imports forbidden module(s): {offenders}"


def test_output_guard_module_calls_no_network_function():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_call_names = {"post", "get", "put", "delete", "request", "connect", "urlopen"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in forbidden_call_names:
                offenders.append(node.func.attr)
    assert not offenders, f"src/guards/output.py calls network-shaped function(s): {offenders}"


def test_output_guard_module_never_calls_eval_or_exec():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    offenders = [
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}
    ]
    assert not offenders, f"src/guards/output.py calls eval/exec: {offenders}"


def test_output_guard_module_has_no_random_or_time_dependent_calls():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    assert "random" not in imported
    assert "time" not in imported
    assert "datetime" not in imported
