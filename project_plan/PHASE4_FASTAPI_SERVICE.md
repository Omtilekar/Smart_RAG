# Phase 4 Task 4.10 — FastAPI Service

Exposes the already-frozen production pipeline (input guard -> routing
-> dense or structured answer -> context/output guards -> release)
through a small, typed HTTP API.

## Authoritative requirement

`PROJECT_EXECUTION.md`'s Task 4.10 checklist is 3 items (materially
narrower than an elaborate draft prompt covering CORS/auth/rate-limits/
concurrency testing/OpenAPI contract testing/timeout policy — followed
the narrower roadmap, same pattern as Tasks 4.8/4.9):

```text
Implement a thin API layer over stable Python modules.
Initial endpoints may include: POST /query, GET /health, GET /status.

- [x] Keep retrieval/generation logic outside FastAPI.
- [x] Define request/response models.
- [x] Return citations and useful metadata.
```

Endpoint names/shapes match the roadmap's own literal suggestion
verbatim (`/health`, `/status`, `POST /query`) rather than the draft
prompt's `/ready` naming.

## Two explicit user decisions (2026-09-16)

| Decision | Chosen | Why |
|---|---|---|
| Guard-rejection HTTP status | **200 with a typed refusal body** (`status="rejected"`, `reason_code` set, no answer/citations) for every guard layer, structural or content-policy | The roadmap says nothing about status codes; this task's own prompt flags it as a must-not-guess choice. The HTTP request itself is well-formed — a guard refusal is an expected business outcome, not a transport error. One JSON shape for clients to parse regardless of outcome. |
| Dense route's index | **Phase 1 dev-corpus LanceDB index (162,357 rows, BGE-small)** — the same index/retriever every prior task (1.6–4.9) actually built and tested against | `src.retrieval.baseline.BaselineRetriever`/`RetrievalResult` hardcode a 17-column schema (`chunk_id`, `source_filename`, `normalizer_version`, `normalization_build_sha256`, `development_manifest_sha256`, ...) that does not exist on the real 10,487,096-row Task 4.4 production index (`chunk_uid` instead of `chunk_id`; several dev-only provenance fields dropped entirely by Task 4.1's full-corpus frontmatter change). No task ever built a schema-adapting retriever for the full-corpus index — verified directly: pointing `BaselineRetriever` at the real production table would raise `KeyError` immediately. Building one now would be new, previously-untested retrieval-adjacent code, outside this task's "thin API layer over stable modules" scope. |

## Route coverage (documented, not overclaimed)

This task's own "Frozen Production Stack" section names exactly two
routes for API exposure: "structured SQL/XBRL route" and "tree-
navigation route." Verified directly before wiring anything:

- **`xbrl_fact` structured route**: `src.router.rules.classify_intent()`
  (Task 3.8, unchanged) resolves cik/fiscal_year/concept from the
  question text; `src.sql.xbrl_lookup.XbrlFactIndex.lookup()` (Task
  3.10, unchanged) returns the fact. **Wired.**
- **Tree-navigation route**: `classify_intent()`'s own 6-intent taxonomy
  (`xbrl_fact`, `numeric_derived`, `cross_entity`, `unanswerable`,
  `out_of_scope`, `advice`) has **no navigation intent at all** —
  `src.nav.section_navigation.extract_item_reference()` was never wired
  into it. There is no live question -> "route to tree-navigation"
  decision anywhere in this codebase. Wiring one now would mean
  inventing new routing logic ("do NOT reopen ... routing ...
  decisions"). **Not wired** — a real, confirmed gap, not an oversight.
- **`numeric_derived`/`cross_entity` structured sub-routes**: a real,
  precedented text -> answer composition pattern *does* exist
  (`scripts/run_phase3_derived.py` composes `classify_intent()` +
  `src.sql.derived.compute_difference()`/`compute_greater_than()`
  exactly this way), but was deliberately **not wired** here — the
  "Frozen Production Stack" section names only "structured SQL/XBRL
  route" (matching Task 3.10's own naming), not "derived calculations" or
  "cross-entity comparison" as separate named routes, so wiring them
  would be a scope expansion beyond this task's own 3-bullet checklist.
  Documented as available, real future work, not a hidden limitation.
- **Dense retrieval + generation**: every other `classify_intent()`
  outcome (including `out_of_scope`/`unanswerable`/`advice` — which,
  given identical frozen keyword lists, can never actually fire on a
  question that already passed Task 4.7's input guard — and any
  `xbrl_fact` lookup that didn't resolve to `outcome="found"`) falls back
  to `MinimalGenerator.answer()`, carrying Task 4.8/4.9's context/output
  guards internally. **Wired**, on the dev-corpus index (see decision
  table above).

## Implemented contract

```python
# src/api/schemas.py
class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    status: str            # "answered" | "rejected"
    answer: str | None
    citations: list[str]   # [chunk_id]-shaped for route="dense";
                            # SEC accession numbers for route="structured_xbrl"
    route: str | None      # "dense" | "structured_xbrl" | None (when rejected)
    reason_code: str | None
    request_id: str

class HealthResponse(BaseModel):
    status: str = "ok"

class StatusResponse(BaseModel):
    ready: bool
    dependencies: dict[str, bool]
    config: dict[str, str | int | None]
```

`citations` uses two different identity shapes depending on `route` —
documented explicitly in the schema's own docstring, distinguishable via
`route`, never silently mixed without a way to tell them apart.

### Guard-rejection status semantics

Only Task 4.7's **input guard** (run directly in `src.api.service.
handle_query()`, before routing) produces `status="rejected"`. A Task
4.8 (context) or Task 4.9 (output) guard rejection *inside* the dense
route is **not** re-labeled "rejected" — `MinimalGenerator.answer()`'s
existing frozen public contract already represents that as an ordinary
`GenerationResult` (an abstention-shaped answer, empty citations), and
this facade does not reach into its non-public
`_answer_with_diagnostics()` to invent a second, parallel exposure of
internal guard mechanics ("do not add new guard behavior merely because
an HTTP API now exists"). Verified by test: a context/output-guard-
triggered abstention surfaces as `status="answered"` with the guard's
existing fixed abstention message and `citations=[]`.

## Orchestration facade

`src/api/service.py`'s `handle_query()` — the **only** new business-
logic-adjacent code in this task, explicitly authorized by the roadmap
("If no single orchestration service exists yet, Task 4.10 may add a
narrow service/facade only if required to avoid embedding pipeline logic
directly in FastAPI routes"). Zero retrieval/routing/SQL/generation/
citation/guardrail logic is reimplemented — every step imports and calls
an already-frozen function/class exactly as Tasks 1.6–4.9 built it.

## Dependency construction

`src/api/dependencies.py` (imported lazily, only inside `create_app()`'s
lifespan, never at module import time — verified by a dedicated AST
test):

- `build_production_gazetteer(con)` — queries the frozen, read-only
  `data/xbrl.duckdb` `submissions` table for `(cik, name)` pairs. This is
  not a new, independently-decided data source: Task 3.8's own frozen
  config (`configs/phase_3_8_rules_first_router.json`,
  `gazetteer_source`) explicitly states *"a production router would
  instead resolve against the full SEC company/CIK submissions list"* —
  this function implements exactly that, for the first time.
- `build_production_dependencies()` — loads the real BGE model, opens
  the real Phase 1 dev-corpus LanceDB table, connects to
  `data/xbrl.duckdb`, and resolves the generation provider via Task
  4.6's `get_generation_provider()` factory (never hardcoding
  `OpenRouterProvider` the way `src.cli.phase1._construct_generator()`
  does — this is the FastAPI-service equivalent of that CLI helper,
  updated to use the more current Task 4.6 entry point).

## Startup / lifespan

`create_app(*, dependencies=None, settings=None, request_id_factory=None)`
— an application factory. `dependencies=None` (real deployment) builds
real, long-lived resources once inside FastAPI's `lifespan` context
manager; `dependencies=<fake>` (all portable tests) skips that entirely.
Verified by test: importing `src.api.app` and calling `create_app()`
never triggers the heavy import chain (embeddings/LanceDB/duckdb) at
all — only `TestClient(app)`'s own `__enter__` (which runs the lifespan)
would, and only when `dependencies=None`.

## Health vs. status

- `GET /health` — liveness only. Always `{"status": "ok"}` once the
  process is running; never touches dependency state.
- `GET /status` — readiness: `ready` reflects whether dependencies have
  finished initializing; `dependencies` is a lightweight dict of boolean
  flags (no live query); `config` exposes non-secret identity strings
  (dev index hash/model, generation provider/model name, dense index row
  count) — never a credential, never a filesystem path beyond what's
  already public in this repo's own documentation.

## Exception mapping

```text
GenerationError (Task 4.6's provider-neutral error type)  -> HTTP 503, bounded message
any other unhandled exception                              -> HTTP 500, bounded message, no traceback/exception text
Pydantic request-schema validation failure (e.g. missing "question")  -> HTTP 422 (FastAPI's own default)
```

Never a raw traceback, never the exception's own message (could contain
a local path or internal detail) — only the exception's type name is
logged, and only a fixed, stable string is returned to the client.

## Logging

One `log_event()` call per request via `src.logging_utils`:

```text
event=request_completed request_id=<uuid> route=<dense|structured_xbrl|None>
status=<answered|rejected> reason_code=<code or None> citation_count=<int> elapsed_ms=<float>
```

Never the raw question, the raw answer, retrieved context, the prompt,
embeddings, or a provider's raw response — verified by test that a
secret-looking marker embedded in a question never appears in any
emitted log record.

## Local run command

```bash
python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Development-only, with auto-reload (never used in the production
command above):

```bash
python -m uvicorn src.api.app:create_app --factory --reload
```

## Configuration

None introduced. `INPUT_GUARD_MAX_LENGTH` (Task 4.7) is reused unchanged
via `src.config.get_settings()`; no `API_HOST`/`API_PORT` setting was
added since uvicorn's own `--host`/`--port` CLI flags already cover that
without a second, redundant configuration surface ("do not add
configuration purely for symmetry"). `.env.example` was not touched —
nothing new required a value there.

## CORS / Auth / Rate limiting

None implemented — not required by the authoritative 3-item checklist.
Task 4.7 already documented rate limiting as delegated to future
infrastructure (API Gateway); this task does not reopen that decision or
invent a home-grown alternative.

## Tests

```text
tests/test_api_service.py            11 tests - pure handle_query() logic:
                                     input-guard short-circuit, dense fallback
                                     for every non-resolving router outcome,
                                     structured-route success, answer/citation
                                     preservation, provider-invocation counts
tests/test_api_app.py                32 tests - full HTTP layer via TestClient
                                     with fake dependencies: health/status,
                                     every input-guard reason code mapped to
                                     200+rejected, context/output-guard
                                     abstention via a REAL MinimalGenerator
                                     mapped to 200+answered, structured-route
                                     success, 422 schema validation, 503
                                     provider-error mapping, 500 unexpected-
                                     exception mapping (no traceback/message
                                     leak), response-field allowlist, request-
                                     ID uniqueness/injectability/determinism,
                                     OpenAPI contract, logging redaction
tests/test_api_dependencies.py        4 tests - build_production_gazetteer()
                                     (name/CIK mapping, null/blank handling,
                                     empty submissions), frozen dev-identity
                                     constants match src.cli.phase1's own
tests/test_api_static_safety.py       7 tests - AST-verified: app.py/service.py
                                     never import a forbidden dependency at
                                     the wrong scope, dependencies.py is only
                                     ever imported lazily inside app.py's
                                     lifespan closure, no outbound network
                                     call, no hardcoded credential-shaped
                                     literal, no eval/exec, schemas.py imports
                                     no pipeline logic
tests/test_api_local_integration.py   1 local_data-marked test - real BGE
                                     model + real 162,357-row dev index +
                                     real xbrl.duckdb, fake provider only:
                                     proves the full HTTP -> service ->
                                     retrieval -> generation wire-up for real,
                                     without spending any API credits (29.4s,
                                     dominated by BGE model load)
```

## Regression gates

Task 4.1–4.5 artifacts untouched (never opened). Task 4.6 provider/model
semantics unchanged (`get_generation_provider()` reused unmodified — no
provider/model selection change). Task 4.7/4.8/4.9 guard modules
untouched — only imported and composed. Frozen Phase 3 routing/retrieval
decisions, the CRAG threshold (`0.5531`), dense-only selection unchanged.
No BM25/RRF/reranker reintroduced, no re-embedding, no provider/model
change.

**Paid API calls during Task 4.10: 0.** No `generation_api`-marked test
was run or opted into; `scripts/smoke_generation.py` was not run.
Protected TEST: unopened, **0/3** official runs used.

```text
python scripts/dev.py doctor                     -> PASS
python scripts/dev.py test --portable             -> 2208 passed, 38 deselected
python -m pytest -m "not generation_api"          -> 2245 passed, 1 deselected (277.18s)
```

## Files created/modified

```text
src/api/schemas.py                            (new)
src/api/service.py                            (new)
src/api/dependencies.py                       (new)
src/api/app.py                                (new)
tests/test_api_service.py                     (new)
tests/test_api_app.py                         (new)
tests/test_api_dependencies.py                (new)
tests/test_api_static_safety.py               (new)
tests/test_api_local_integration.py           (new)
project_plan/PHASE4_FASTAPI_SERVICE.md        (this file)
project_plan/REPOSITORY_STRUCTURE.md          (updated)
project_plan/DEVELOPER_COMMANDS.md            (updated - local run command)
results/phase_4_10_fastapi_service_summary.json (new, tracked)
Progress.md                                   (updated)
```

## Known limitations

- Dense route serves the 162,357-row Phase 1 dev-corpus index, not the
  real 10,487,096-row Task 4.4 production index — a schema-adapting
  retriever for the full-corpus schema (`chunk_uid`, dropped dev-only
  provenance fields) does not exist yet and was explicitly not built in
  this task (see decision table above). This is the single most
  important limitation of this task's deliverable.
- Tree-navigation route is not wired — no live routing decision for it
  exists anywhere in this codebase.
- `numeric_derived`/`cross_entity` structured sub-routes are not wired,
  despite a real, precedented composition pattern existing in
  `scripts/run_phase3_derived.py` — deliberately deferred to keep this
  task's scope proportionate to its own checklist.
- No CORS, authentication, or rate limiting — not required by the
  authoritative checklist; rate limiting remains Task 4.7's documented
  "delegated to future infrastructure" decision.
- No deployment — Task 4.11 owns that; this task produces the
  application only, not a running deployed service.
- No concurrency/load testing — not required by the authoritative
  3-item checklist; `TestClient`-based synthetic concurrency claims
  nothing about real production throughput in any case.
- Citations for the structured route are SEC accession numbers, not
  chunk_ids — a different identity space from the dense route's
  citations, distinguishable via the `route` field, documented in the
  schema itself.

## Next roadmap task

Phase 4, Task 4.11 — Deployment.
