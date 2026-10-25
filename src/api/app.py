"""Task 4.10 - FastAPI application factory.

    def create_app(*, dependencies=None, settings=None, request_id_factory=None) -> FastAPI

Importing this module (or calling `create_app()`) never loads the BGE
model, never opens LanceDB, never connects to `xbrl.duckdb` - real
production dependencies are constructed lazily, once, inside the app's
`lifespan`, and only when the caller did not inject a fake
`dependencies` object. This is what lets portable tests construct the
app and exercise every endpoint with zero GPU/model/index/network
dependency.

Local run (real dependencies):

    python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000

Development-only, with auto-reload (never use --reload in production):

    python -m uvicorn src.api.app:create_app --factory --reload
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.generation.provider import GenerationError
from src.logging_utils import get_logger, log_event

from .schemas import HealthResponse, QueryRequest, QueryResponse, StatusResponse
from .service import handle_query

log = get_logger(__name__)

# Task 4.12 - local project showcase + query UI, served as static files.
# Resolved relative to this module's own file, never the process's working
# directory, so `uvicorn src.api.app:create_app` works from any launch
# directory. Reading this constant performs no filesystem I/O.
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(*, dependencies=None, settings=None, request_id_factory=None) -> FastAPI:
    """`dependencies`: a `src.api.dependencies.ProductionDependencies`-shaped
    object (duck-typed: `.generator`, `.gazetteer`, `.registry`,
    `.xbrl_index`, and a `.status_snapshot()` method), or a test fake with
    the same shape. `None` (the real-deployment default) builds real
    dependencies inside the lifespan via
    `src.api.dependencies.build_production_dependencies()` - imported
    lazily, right here, so a portable test that always injects a fake
    never triggers that import chain (embeddings/LanceDB/duckdb) at all.

    `settings` defaults to `src.config.get_settings()` (cheap - no
    filesystem/network I/O). `request_id_factory` defaults to
    `uuid.uuid4`; injectable for deterministic tests.
    """
    settings = settings or get_settings()
    request_id_factory = request_id_factory or (lambda: str(uuid.uuid4()))
    state: dict = {"deps": dependencies}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if state["deps"] is None:
            from .dependencies import build_production_dependencies
            state["deps"] = build_production_dependencies(settings)
        try:
            yield
        finally:
            deps = state["deps"]
            close = getattr(deps, "close", None)
            if close is not None:
                close()

    app = FastAPI(title="SEC RAG Query Service", lifespan=lifespan)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        # Liveness only - the process is running. Never touches `state`,
        # never fails just because the lifespan hasn't finished yet.
        return HealthResponse()

    @app.get("/status", response_model=StatusResponse)
    async def status_endpoint() -> StatusResponse:
        deps = state.get("deps")
        if deps is None:
            return StatusResponse(ready=False, dependencies={}, config={})
        snapshot = deps.status_snapshot()
        retrieval_cache = snapshot["retrieval_cache"] if "retrieval_cache" in snapshot else None
        retrieval_security = snapshot["retrieval_security"] if "retrieval_security" in snapshot else None
        prompt_cache = snapshot["prompt_cache"] if "prompt_cache" in snapshot else None
        return StatusResponse(
            ready=True,
            dependencies=snapshot["dependencies"],
            config=snapshot["config"],
            retrieval_cache=retrieval_cache,
            retrieval_security=retrieval_security,
            prompt_cache=prompt_cache,
        )

    @app.post("/query", response_model=QueryResponse)
    async def query(request: QueryRequest) -> QueryResponse:
        request_id = request_id_factory()
        deps = state["deps"]
        start = time.perf_counter()
        outcome = handle_query(
            request.question, max_length=settings.input_guard_max_length,
            generator=deps.generator, gazetteer=deps.gazetteer,
            registry=deps.registry, xbrl_index=deps.xbrl_index,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_event(
            log, logging.INFO, "request_completed", request_id=request_id, route=outcome.route,
            status=outcome.status, reason_code=outcome.reason_code,
            citation_count=len(outcome.citations), elapsed_ms=round(elapsed_ms, 1),
        )
        return QueryResponse(
            status=outcome.status, answer=outcome.answer, citations=outcome.citations,
            route=outcome.route, reason_code=outcome.reason_code, request_id=request_id,
        )

    @app.exception_handler(GenerationError)
    async def generation_error_handler(_request: Request, exc: GenerationError) -> JSONResponse:
        # Reuses Task 4.6's provider-neutral error type unchanged - never
        # special-cases OpenRouter/Ollama here. Never leaks the exception
        # message (it could, in principle, echo request details) - a
        # bounded, stable public message only.
        log_event(log, logging.ERROR, "provider_error", exception_type=type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "error", "detail": "generation provider unavailable"})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Never a raw traceback, never the exception message (could
        # contain a local path or internal detail) - only the type name,
        # safe to log.
        log_event(log, logging.ERROR, "unexpected_error", exception_type=type(exc).__name__)
        return JSONResponse(status_code=500, content={"status": "error", "detail": "internal server error"})

    # Task 4.12b - client-side-routed pages of the same single-page app.
    # Each of these paths must return the identical index.html shell (the
    # in-page router in app.js then shows the right view from
    # location.pathname) so a hard refresh or a shared link to e.g.
    # /architecture works exactly like navigating there from the sidebar.
    # include_in_schema=False keeps openapi.json's path set unchanged at
    # exactly {"/health", "/status", "/query"} - these are not API
    # endpoints, just alternate entry points into the same static shell.
    @app.get("/architecture", include_in_schema=False)
    @app.get("/experiments", include_in_schema=False)
    @app.get("/data", include_in_schema=False)
    @app.get("/evaluation", include_in_schema=False)
    @app.get("/roadmap", include_in_schema=False)
    async def spa_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    # Mounted LAST, after every API route above (including the SPA page
    # routes) and after FastAPI's own __init__-time /docs, /redoc,
    # /openapi.json routes. Starlette matches routes in registration order
    # and returns the first match, so this catch-all "/" mount can never
    # shadow an API path or the Swagger/OpenAPI routes - it only ever
    # serves a request that none of those already claimed. html=True
    # serves static/index.html for "/" and any other directory-shaped
    # request, and also serves the real static assets (styles.css, app.js,
    # project-data.js) by their real filenames.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


__all__ = ["create_app"]
