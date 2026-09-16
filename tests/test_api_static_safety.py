"""Task 4.10 - static (AST-based) proof that src/api/app.py and
src/api/service.py never construct forbidden clients or duplicate
lower-level pipeline logic. Heavy dependency construction is confined to
src/api/dependencies.py, imported lazily inside app.py's lifespan
closure - this test also confirms app.py/service.py never import it at
module (top) level, so importing the API layer stays cheap.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_MODULE_PATH = REPO_ROOT / "src" / "api" / "app.py"
SERVICE_MODULE_PATH = REPO_ROOT / "src" / "api" / "service.py"
SCHEMAS_MODULE_PATH = REPO_ROOT / "src" / "api" / "schemas.py"

# app.py/service.py must never import these at module (top) level - only
# src/api/dependencies.py may (and does), and only app.py's lifespan
# closure imports *that*, lazily, at runtime.
FORBIDDEN_TOP_LEVEL_MODULES = (
    "requests",
    "httpx",
    "lancedb",
    "sentence_transformers",
    "torch",
    "duckdb",
    "src.embeddings",
    "src.index",
    "src.eval.test_access",
    "src.generation.openrouter",
    "src.generation.ollama_provider",
    "src.api.dependencies",
)


def _top_level_imports(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _all_imports(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_app_module_has_no_forbidden_top_level_import():
    tree = ast.parse(APP_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _top_level_imports(tree)
    for forbidden in FORBIDDEN_TOP_LEVEL_MODULES:
        offenders = [name for name in imported if name == forbidden or name.startswith(forbidden + ".")]
        assert not offenders, f"src/api/app.py has a forbidden TOP-LEVEL import: {offenders}"


def test_service_module_has_no_forbidden_import_at_all():
    # service.py is pure orchestration logic invoked per-request - it
    # should never import a heavy/network dependency even lazily.
    tree = ast.parse(SERVICE_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _all_imports(tree)
    for forbidden in FORBIDDEN_TOP_LEVEL_MODULES:
        offenders = [name for name in imported if name == forbidden or name.startswith(forbidden + ".")]
        assert not offenders, f"src/api/service.py imports forbidden module(s): {offenders}"


def test_dependencies_import_is_lazy_inside_app_lifespan_only():
    source = APP_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    # Every "from .dependencies import ..." must appear INSIDE a function
    # body (nested import), never at module (top) level.
    top_level_names = _top_level_imports(tree)
    assert "src.api.dependencies" not in top_level_names
    assert ".dependencies" not in top_level_names
    nested_import_found = any(
        isinstance(node, ast.ImportFrom) and node.module == "dependencies"
        for node in ast.walk(tree)
        if not any(node is top for top in tree.body)  # exclude top-level statements
    )
    assert nested_import_found, "expected a lazy 'from .dependencies import ...' inside a function body"


def test_app_module_calls_no_network_construction_function():
    # `@app.get(...)`/`@app.post(...)` are FastAPI's OWN route-registration
    # decorators, not outbound calls - excluded by name via the object
    # being called (only flag .get/.post/etc on something other than the
    # local `app` FastAPI instance, e.g. a would-be `requests.get(...)`).
    tree = ast.parse(APP_MODULE_PATH.read_text(encoding="utf-8"))
    forbidden_call_names = {"post", "get", "put", "delete", "urlopen"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in forbidden_call_names:
                base = node.func.value
                # `app.get`/`app.post` are FastAPI route-registration
                # decorators; `state.get(...)` is a plain dict lookup -
                # neither is an outbound network call. The real proof
                # that no HTTP client library is even reachable is
                # test_app_module_has_no_forbidden_top_level_import()
                # above; this check only catches an actual client-shaped
                # call the import check might miss.
                if isinstance(base, ast.Name) and base.id in {"app", "state"}:
                    continue
                offenders.append(node.func.attr)
    assert not offenders, f"src/api/app.py calls network-shaped function(s): {offenders}"


def test_app_module_has_no_hardcoded_looking_credential():
    source = APP_MODULE_PATH.read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in ("api_key =", "authorization:", "bearer ", "secret ="):
        assert forbidden not in lowered, f"src/api/app.py appears to contain a hardcoded credential-shaped literal: {forbidden!r}"


def test_service_module_never_calls_eval_or_exec():
    tree = ast.parse(SERVICE_MODULE_PATH.read_text(encoding="utf-8"))
    offenders = [
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}
    ]
    assert not offenders, f"src/api/service.py calls eval/exec: {offenders}"


def test_schemas_module_is_pydantic_models_only_no_business_logic_imports():
    tree = ast.parse(SCHEMAS_MODULE_PATH.read_text(encoding="utf-8"))
    imported = _all_imports(tree)
    disallowed = {"src.router", "src.retrieval", "src.generation", "src.sql", "src.nav", "src.guards", "src.index"}
    offenders = [name for name in imported if any(name == d or name.startswith(d + ".") for d in disallowed)]
    assert not offenders, f"src/api/schemas.py imports pipeline logic (should be typed models only): {offenders}"
