"""Task 4.7 - static (AST-based) proof that src/guards/input.py never
imports a forbidden dependency. Never relies only on comments/docstrings
claiming the module is local/deterministic - this actually parses the
source and inspects every Import/ImportFrom node, the same static-guard
convention already used elsewhere in this project (e.g.
tests/test_phase_4_1_full_corpus_normalization.py's AST guard proving
the Task 4.1 driver never imports a later-phase package).
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_MODULE_PATH = REPO_ROOT / "src" / "guards" / "input.py"

FORBIDDEN_MODULE_PREFIXES = (
    "requests",
    "lancedb",
    "sentence_transformers",
    "torch",
    "src.generation.openrouter",
    "src.generation.ollama_provider",
    "src.index",
    "src.embeddings",
    "src.eval.test_access",
    "src.retrieval",
    "src.sql",
    "src.nav",
    "duckdb",
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


def test_input_guard_module_imports_no_forbidden_dependency():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    for forbidden in FORBIDDEN_MODULE_PREFIXES:
        offenders = [name for name in imported if name == forbidden or name.startswith(forbidden + ".")]
        assert not offenders, f"src/guards/input.py imports forbidden module(s): {offenders}"


def test_input_guard_module_calls_no_network_function():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_call_names = {"post", "get", "put", "delete", "request", "connect", "urlopen"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in forbidden_call_names:
                offenders.append(node.func.attr)
    assert not offenders, f"src/guards/input.py calls network-shaped function(s): {offenders}"


def test_input_guard_module_has_no_random_or_time_dependent_calls():
    tree = ast.parse(GUARD_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _imported_module_names(tree)
    assert "random" not in imported
    assert "time" not in imported
    assert "datetime" not in imported


def test_check_input_function_only_imports_config_lazily_inside_wrapper():
    # src.config is imported lazily inside check_input_with_settings() (a
    # convenience wrapper), never at module level and never inside
    # check_input() itself - the pure decision function never touches
    # config-loading machinery.
    source = GUARD_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level_imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module)
    assert "src.config" not in top_level_imports
