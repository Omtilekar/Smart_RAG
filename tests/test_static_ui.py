"""Task 4.12 - static project-showcase/query-UI serving. Reuses Task
4.10's own fake-dependency pattern (no network/model/LanceDB/GPU) - the
only thing under test here is that mounting StaticFiles at "/" never
shadows an API route or the Swagger/OpenAPI routes, and that the existing
API contract is completely unchanged.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import STATIC_DIR, create_app
from src.eval.tag_registry import get_registry
from src.generation.minimal import MinimalGenerator
from src.generation.provider import GenerationRequest, ProviderResponse
from src.retrieval.baseline import RetrievalResult
from src.router.rules import CompanyGazetteer
from src.sql.xbrl_lookup import XbrlLookupResult


class _FakeRetriever:
    def retrieve(self, question, k=5):
        return [RetrievalResult(
            rank=1, score=0.9, distance=0.1, chunk_id="doc0.htm::chunk0", document_id="doc0.htm",
            text="Revenue was $1M.", cik=1000, company="ACME", form_type="10-K", fiscal_year=2019,
            source="edgar_corpus", source_filename="doc0.htm", source_split="train", ordinal=0,
            token_count=10, chunk_config_hash="abc123", normalizer_version="phase1-minimal-v1",
            normalization_build_sha256="x" * 64, development_manifest_sha256="y" * 64,
        )]


class _FakeProvider:
    def generate(self, request: GenerationRequest) -> ProviderResponse:
        return ProviderResponse(
            text="Revenue was $1M. [doc0.htm::chunk0]", requested_model="fake/model", response_model="fake/model",
            provider_name="fake", response_provider=None, prompt_tokens=1, completion_tokens=1,
            total_tokens=2, temperature_requested=request.temperature, latency_ms=0.1,
        )


class _FakeXbrlIndex:
    def lookup(self, *, cik, fiscal_year, tag):
        return XbrlLookupResult(outcome="not_found", cik=cik, fiscal_year=fiscal_year, tag=tag)


class _FakeDependencies:
    def __init__(self):
        self.generator = MinimalGenerator(_FakeRetriever(), _FakeProvider())
        self.gazetteer = CompanyGazetteer({})
        self.registry = get_registry()
        self.xbrl_index = _FakeXbrlIndex()
        self.closed = False

    def status_snapshot(self):
        return {"dependencies": {"fake": True}, "config": {"generation_model": "fake/model"}}

    def close(self):
        self.closed = True


def _client():
    app = create_app(dependencies=_FakeDependencies())
    return TestClient(app)


# --------------------------------------------------------- static dir sanity

def test_static_dir_exists_with_required_assets():
    assert STATIC_DIR.is_dir()
    for name in ("index.html", "styles.css", "app.js", "project-data.js"):
        assert (STATIC_DIR / name).is_file(), f"missing required static asset: {name}"


# ------------------------------------------------------------ UI is served

def test_root_serves_html():
    with _client() as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<title>" in r.text


def test_static_assets_are_reachable():
    with _client() as client:
        for path in ("/styles.css", "/app.js", "/project-data.js"):
            r = client.get(path)
            assert r.status_code == 200, f"{path} did not serve"


# ---------------------------------------------------- API routes untouched

def test_docs_still_works():
    with _client() as client:
        r = client.get("/docs")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


def test_openapi_json_still_works_and_paths_unchanged():
    with _client() as client:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        # Static mount adds no OpenAPI schema entries - only real APIRoutes do.
        assert set(spec["paths"].keys()) == {"/health", "/status", "/query"}


def test_health_endpoint_unchanged():
    with _client() as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_status_endpoint_unchanged():
    with _client() as client:
        r = client.get("/status")
        assert r.status_code == 200
        body = r.json()
        assert body["ready"] is True
        assert body["dependencies"] == {"fake": True}


def test_query_contract_unchanged_with_mocked_dependencies():
    with _client() as client:
        r = client.post("/query", json={"question": "What was the company's total revenue?"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "answered"
        assert body["route"] == "dense"
        assert set(body.keys()) == {"status", "answer", "citations", "route", "reason_code", "request_id"}


def test_app_factory_still_initializes_with_static_mount():
    app = create_app(dependencies=_FakeDependencies())
    assert app is not None


# -------------------------------------------------- static never shadows API

def test_static_mount_does_not_shadow_health_status_query_or_docs():
    with _client() as client:
        for path, method in (("/health", "get"), ("/status", "get"), ("/docs", "get"), ("/openapi.json", "get")):
            r = getattr(client, method)(path)
            assert r.status_code == 200
            assert "text/html" not in r.headers.get("content-type", "") or path == "/docs"
        r = client.post("/query", json={"question": "revenue?"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")


# -------------------------------------------------- static content safety

_SECRET_PATTERNS = ("sk-", "AKIA", "-----BEGIN", "OPENROUTER_API_KEY=")
_DANGEROUS_PATH_MARKERS = ("C:\\Om\\Codes\\RAG", "C:/Om/Codes/RAG", "C:\\Users\\")


@pytest.mark.parametrize("filename", ["index.html", "styles.css", "app.js", "project-data.js"])
def test_static_file_has_no_secrets_or_local_paths(filename):
    text = (STATIC_DIR / filename).read_text(encoding="utf-8")
    for pattern in _SECRET_PATTERNS:
        assert pattern not in text, f"{filename} contains a secret-shaped value: {pattern!r}"
    for marker in _DANGEROUS_PATH_MARKERS:
        assert marker not in text, f"{filename} embeds a local absolute path: {marker!r}"


def test_index_html_uses_relative_same_origin_requests_only():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "127.0.0.1" not in text
    assert "localhost" not in text
    assert "0.0.0.0" not in text


def test_app_js_uses_relative_same_origin_requests_only():
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "127.0.0.1" not in text
    assert "localhost" not in text
    assert "http://" not in text
    assert "https://" not in text


def test_static_files_never_use_innerhtml_for_dynamic_content():
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert ".innerHTML" not in text


def test_project_data_declares_github_url_matching_real_remote():
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert "github.com/Omtilekar/Smart_RAG" in text


# --------------------------------------------------- Task 4.12a: deep architecture

def test_index_html_has_deep_architecture_section_and_tab_scaffold():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-view="architecture"' in text
    assert 'id="deep-arch-tablist"' in text
    assert 'role="tablist"' in text
    assert 'id="deep-arch-tabpanels"' in text
    assert 'id="arch-detail-panel"' in text


def test_architecture_view_embeds_the_archify_diagram():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # The hand-drawn Level-1 SVG was replaced by the archify-generated
    # diagram, served as a same-origin static page inside an iframe.
    assert 'data-view="architecture"' in text
    assert 'src="/architecture-diagram.html?embed=1"' in text
    assert 'viewBox="0 0 920 620"' not in text
    # The embedded Archify diagram predates Task 4.A (it still shows the BGE dev
    # index as live) and has not been regenerated; the page must say so.
    assert "data-arch-stale-notice" in text and "Diagram refresh pending" in text
    diagram = (STATIC_DIR / "architecture-diagram.html").read_text(encoding="utf-8")
    assert "SEC RAG System Diagram" in diagram


def test_architecture_diagram_page_is_served():
    with _client() as client:
        r = client.get("/architecture-diagram.html")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


def test_project_data_declares_deep_architecture_with_five_tabs():
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert "deepArchitecture" in text
    for tab_id in ("query", "retrieval", "offline", "evaluation", "runtime"):
        assert f'id: "{tab_id}"' in text


def test_deep_architecture_marks_crag_and_metadata_prefilter_as_not_routed():
    # Real finding verified against source during this task: neither is
    # actually wired into the live dense retriever - the showcase must not
    # imply otherwise.
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert "CRAG confidence gating" in text
    assert "Metadata pre-filtering" in text
    crag_idx = text.index("CRAG confidence gating")
    surrounding = text[crag_idx - 200:crag_idx + 400]
    assert '"not-routed"' in surrounding


def test_deep_architecture_reports_the_production_index_as_live_and_dev_as_historical():
    # Task 4.A: the production Qwen3 index is now the live dense route; the
    # BGE dev index must be labelled historical, and the remaining gap
    # (pre-filter not routed, slow unscoped search) must stay visible.
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert 'label: "LIVE", sublabel: "Qwen3-Embedding-0.6B production index"' in text
    assert "HISTORICAL / DEV" in text
    assert "REMAINING GAP" in text
    assert "Live dense index rows" in text and 'value: "10,487,096"' in text
    assert "FROZEN PRODUCTION ARTIFACT" not in text and "PLANNED INTEGRATION" not in text


def test_deep_architecture_shows_exact_retrieval_cache_without_semantic_claim():
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert "Exact Retrieval Cache" in text
    assert "exact-query LRU + TTL" in text
    assert "in-process" in text
    assert "not semantic" in text


def test_deep_architecture_shows_retrieval_security_after_cache_and_xbrl_exception():
    text = (STATIC_DIR / "project-data.js").read_text(encoding="utf-8")
    assert "Retrieval Security Guard" in text
    assert "runs after cache HIT or MISS" in text
    assert "retrieval_security" in text
    assert "XBRL semantics unchanged" in text
    assert "scripts/smoke_retrieval_security.py" in text


def test_styles_css_defines_four_arch_status_colors_in_dark_and_light():
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    for token in ("--color-arch-live", "--color-arch-frozen", "--color-arch-planned", "--color-arch-not-routed"):
        assert text.count(token) >= 3, f"{token} should be defined for dark root + both light overrides"


def test_app_js_defines_accessible_tab_and_detail_panel_behavior():
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "initDeepArchitecture" in text
    assert "ArrowRight" in text and "ArrowLeft" in text
    assert "aria-selected" in text
    assert "showArchDetail" in text


# ---------------------------------------- Task 4.12b: chat UI + page routes

@pytest.mark.parametrize("path", ["/", "/architecture", "/experiments", "/data", "/evaluation", "/roadmap"])
def test_spa_routes_all_serve_200_html(path):
    with _client() as client:
        r = client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<title>" in r.text


def test_spa_page_routes_are_hidden_from_openapi_schema():
    with _client() as client:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        # /architecture etc. are not API endpoints - they must never appear
        # in the schema, and /health,/status,/query must stay the only 3.
        assert set(spec["paths"].keys()) == {"/health", "/status", "/query"}


def test_spa_routes_do_not_shadow_health_status_query_or_docs():
    with _client() as client:
        for path in ("/architecture", "/experiments", "/data", "/evaluation", "/roadmap"):
            r = client.get(path)
            assert r.status_code == 200
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/status").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.post("/query", json={"question": "revenue?"}).status_code == 200


def test_index_html_default_route_is_chat():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-view="chat"' in text
    # The chat view must not carry a `hidden` attribute of its own in the
    # markup - it's the default visible view before app.js's router runs.
    chat_section_start = text.index('data-view="chat"')
    line_start = text.rfind("<section", 0, chat_section_start)
    line_end = text.index(">", chat_section_start)
    chat_tag = text[line_start:line_end]
    assert "hidden" not in chat_tag


def test_index_html_has_sidebar_navigation_for_all_pages():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="sidebar"' in text
    assert 'id="new-chat-btn"' in text
    for route in ("/", "/architecture", "/experiments", "/data", "/evaluation", "/roadmap"):
        assert f'data-route="{route}"' in text
    assert 'href="/docs"' in text
    assert 'href="/status"' in text


def test_index_html_has_claude_style_chat_composer():
    text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="chat-form"' in text
    assert 'id="chat-input"' in text
    assert 'id="chat-messages"' in text
    assert 'id="chat-empty"' in text
    assert "suggestion-chip" in text
    # Example prompts must never auto-submit - they only exist as buttons
    # with a data-prompt, filled by app.js on click.
    assert 'data-prompt="What was Apple' in text


def test_app_js_defines_router_and_chat_behavior():
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "initRouter" in text
    assert "initChat" in text
    assert "popstate" in text
    assert "pushState" in text
    assert "AbortController" in text  # timeout handling for the chat request


def test_app_js_never_auto_submits_a_query_on_load():
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    # requestSubmit must only ever be called from inside a user-triggered
    # keydown handler, never at module init time.
    assert "requestSubmit" in text
    init_fn_start = text.index("function init()")
    init_fn_end = text.index("\n}\n", init_fn_start)
    assert "requestSubmit" not in text[init_fn_start:init_fn_end]


def test_styles_css_defines_chat_and_sidebar_components():
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    for selector in (".app-shell", ".sidebar", ".chat-composer", ".chat-msg-user", ".chat-msg-assistant"):
        assert selector in text
