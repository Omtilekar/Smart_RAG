# Task 4.12 — Local RAG Web UI and Project Showcase

You are working in the Production RAG repository at `C:\Om\Codes\RAG`.

Build a polished local web UI for the SEC RAG project and turn the current FastAPI-only service into a professional portfolio/demo site without changing the underlying RAG behavior.

The site must do two jobs well:

1. provide a real interactive UI for querying the existing RAG API; and
2. showcase the engineering/research story of the project: datasets, architecture, experiments, model/chunking selection, evaluation, guardrails, productionization, current limitations, and roadmap.

This is a presentation/integration task, NOT a retrieval/model-tuning task.

---

## 0. Safety and scope first

Before editing anything:

- Confirm the current branch and `git status`.
- The intended branch is `main` unless the user explicitly created another branch for this task.
- Note that `CLEANUP_ANALYSIS.md` may be untracked. Do NOT stage, edit, delete, or commit it.
- Do not touch frozen/protected evaluation data.
- Protected TEST must remain unopened and usage must remain `0/3`.
- Do not call OpenRouter or any paid generation endpoint during implementation or testing.
- Do not access AWS.
- Do not rebuild embeddings, indexes, chunks, or the XBRL database.
- Do not modify frozen scientific decisions or historical result artifacts.
- Do not change the behavior or request/response contracts of `/health`, `/status`, or `/query` unless a minimal backwards-compatible change is strictly required to serve static assets.
- Do not modify retrieval ranking, routing, embedding, generation, guardrail, or evaluation logic.

Record the pre-task `git status` and baseline app/API state.

---

## 1. Use the installed UI UX Pro Max plugin

The repository owner has installed the **UI UX Pro Max** plugin specifically for this task.

Before implementing the frontend:

- Use the installed UI UX Pro Max plugin/skill to obtain design guidance for a professional AI/research/financial-data product showcase.
- Ask it for guidance on layout, information hierarchy, typography, spacing, responsive behavior, accessibility, dashboard/chat patterns, metric cards, experiment comparison displays, architecture diagrams, and dark/light visual treatment.
- Prefer a restrained, credible, engineering/research aesthetic over a flashy marketing template.
- Do not blindly follow plugin output if it conflicts with accessibility, truthful project status, repository constraints, or the existing FastAPI API contract.
- Do not invent a plugin command if the installed plugin exposes a different invocation mechanism; inspect/use the installed plugin as available.

Summarize the selected UI direction before implementation.

---

## 2. First inspect the real repository — do not invent project facts

Before writing showcase copy or metrics, inspect the authoritative project sources. At minimum inspect:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PHASE3_EXIT_AUDIT.md` if present
- relevant Phase 3 / Phase 4 documents under `project_plan/`
- `results/`
- relevant `configs/`
- current `src/api/app.py`
- current API request/response schemas
- current `/status` implementation
- full-corpus manifests/summary files that are already local and safe to read
- dataset readiness/validation reports already in the repository

Use `rg`, `git ls-files`, and targeted reads to locate the canonical files rather than guessing paths.

### Truthfulness rule

Every number shown in the UI must be traceable to an existing repository artifact/document.

For every curated showcase metric, keep a nearby code comment or structured metadata field such as:

- `source_path`
- `source_key` or section name when practical

If a number cannot be verified from the repository, omit it rather than estimating it.

Historical experiment results must be labeled as historical/frozen results, not live runtime metrics.

Live runtime metrics must come from `/status` where possible.

---

## 3. Important current-state limitation — must be represented accurately

The UI must NOT imply that the live dense HTTP route is already serving the full production corpus if it is not.

Current known state to verify from `/status` and repository docs:

- the HTTP service is healthy and ready;
- `/status` currently exposes a development dense index/runtime;
- the currently served dense index has historically reported `dense_index_row_count = 162357` with `BAAI/bge-small-en-v1.5` development metadata;
- the full Phase 4 production corpus/index is a separate Qwen3-based 1024-dimensional build with approximately 10.49M chunks/embeddings and still needs the production retriever/adapter wired into the live dense API path.

Do not hardcode these values without verifying the current repository/status response.

Present this transparently as something like:

- **Live runtime** — what `/status` says right now
- **Production artifact** — what has already been built offline
- **Remaining integration gate** — production dense retriever/adapter wiring

This transparency is a feature of the portfolio, not something to hide.

---

## 4. Frontend implementation strategy

There is currently no custom end-user frontend.

Prefer a **zero-build, low-complexity frontend** unless the repository already contains a frontend toolchain:

- semantic HTML
- modern CSS
- small modular vanilla JavaScript / ES modules
- no Node/npm requirement unless there is a strong existing repository reason
- no heavy frontend framework solely for this task

A suggested location is a clearly named static package under the existing API area, for example:

```text
src/api/static/
  index.html
  styles.css
  app.js
  project-data.js or project-data.json
  assets/
```

Use the repository's actual structure if another location fits better.

Serve the custom UI at:

```text
http://127.0.0.1:8000/
```

while preserving:

```text
/docs
/openapi.json
/health
/status
/query
```

Do not let a catch-all static route swallow API endpoints or Swagger/OpenAPI routes.

The normal local startup command should remain simple, ideally still:

```powershell
python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Do not add `--reload` as a required path.

---

## 5. Site information architecture

Build a polished single-page product/portfolio experience with persistent navigation. It should feel like a real engineering project site, not an autogenerated admin dashboard.

Required sections:

### A. Hero / overview

Communicate clearly:

- project name: SEC RAG / Production RAG
- one concise sentence describing the goal
- primary CTA: **Ask the RAG**
- secondary CTA: **Explore the architecture**
- live service-status indicator from `/health` and/or `/status`
- small technology chips only where useful, not a wall of badges

Avoid exaggerated claims such as "production deployed" while AWS deployment is deferred.

### B. Interactive RAG query experience

Create the actual end-user query UI around the existing `POST /query` endpoint.

Requirements:

- accessible textarea/input
- send button
- Enter-to-send with Shift+Enter for newline if using a textarea
- 3-5 safe example prompts that do NOT auto-submit
- loading state
- disabled duplicate submission while a request is in flight
- clear error state for validation, unavailable service, network failure, or backend error
- render the response using the exact existing `QueryResponse` schema — inspect it; do not guess fields
- answer area with readable typography
- citations/sources/provenance section when supplied by the API
- route/mode metadata when the API supplies it
- client-observed elapsed time may be displayed but label it as client-observed latency
- copy-answer action
- clear/reset action

Do NOT send a query automatically on page load.

Because generation may use OpenRouter, include a subtle note near the query form when `/status` reports a configured external generation provider. Do not show or expose API keys.

### C. Architecture

Create a clear visual architecture section using accessible HTML/CSS/SVG, not a raster screenshot.

Represent the real pipeline at a high level, such as:

```text
User Query
   ↓
Input Guardrails
   ↓
Intent / Route Decision
   ├── Dense retrieval over SEC filing text
   ├── Structured XBRL route
   └── other implemented/frozen capabilities where accurately supported
   ↓
Context Guardrails
   ↓
Generation
   ↓
Output Guardrails + Citation Validation
   ↓
FastAPI response
```

Only show capabilities that actually exist. If tree navigation is frozen but not wired into the live router/API, label it accurately as an implemented/frozen capability rather than a live route.

Show storage/artifact layers separately where helpful:

- EDGAR-CORPUS normalized/chunked text
- vector index
- XBRL DuckDB
- model/provider layer

### D. Dataset at scale

Show verified, source-backed dataset cards and/or a compact visual summary.

Candidate metrics to verify before use include:

- MS MARCO corpus and dev-small benchmark scale
- EDGAR-CORPUS filing count and CIK count
- XBRL fact/submission/tag counts
- primary SEC filing count
- full-corpus normalized document count
- full-corpus chunk count
- full-corpus embedding count
- vector dimensionality

Use the exact frozen/current values from repository evidence.

Make the distinction between:

- benchmark/evaluation data
- project corpus
- structured XBRL data
- primary filing data
- derived production artifacts

### E. "How we chose the retrieval stack" / experiments

This is a major portfolio section.

Create an experiment journey showing that architecture choices were measured rather than guessed.

At minimum, if verified from repository evidence, include:

1. **Chunking ablation**
   - candidates tested
   - winning strategy
   - why it was selected
   - winning fixed-window configuration (expected project result: 256 content tokens, 0 overlap, stride 256, final partial kept — verify before displaying)

2. **Embedding-model benchmark**
   - candidates/models tested
   - chosen model
   - key retrieval metrics used for selection
   - expected winner: `Qwen/Qwen3-Embedding-0.6B`, 1024 dimensions — verify before displaying

3. **Sparse retrieval baseline**
   - show BM25/FTS baseline results where frozen artifacts support them

4. **Hybrid fusion experiment**
   - explain that RRF hybrid was tested and was not selected if that remains the frozen conclusion
   - negative experimental outcomes are valuable; show them neutrally

5. **Cross-encoder reranking experiment**
   - show that reranking was evaluated and not selected if verified

6. **Metadata pre-filtering**
   - show its measured impact if verified

7. **Structured XBRL routing / derived calculations**
   - summarize verified coverage/accuracy results

8. **Tree navigation**
   - summarize verified filing/section resolution and scope-leak results, while clearly labeling live-vs-frozen capability status

Use clean mini charts/tables/timelines. Prefer CSS/SVG charts or simple accessible bars over adding a large charting dependency.

Never fabricate candidate scores to make a chart look complete.

### F. Full-corpus production build

Show the Phase 4 pipeline as a build journey:

```text
Normalize → Chunk → Embed → Index → Serve
```

For each stage show only verified artifact counts/sizes/statuses.

Candidate facts to verify include:

- normalized documents
- chunk count and shard count
- embedding count / format / dimension
- full vector index status
- structured XBRL serving representation
- guardrail layers
- FastAPI service

This section should communicate that the system was scaled from development evaluation to full-corpus artifacts.

### G. Guardrails and reliability

Explain, based on project files:

- input guardrails
- retrieved context treated as untrusted
- provenance requirements
- output/citation validation
- deterministic/non-paid structured paths where relevant
- regression testing discipline
- protected TEST policy

Do not display secret values, raw API keys, private identifiers, or sensitive local paths beyond harmless project-relative paths.

### H. Evaluation / engineering results

Present verified engineering results such as:

- retrieval metrics
- structured-routing exactness/coverage
- regression test counts from the current task run
- serving/performance numbers only if their measurement context is clear

Differentiate clearly between:

- frozen evaluation result
- historical benchmark
- current runtime state
- current test-suite result

Do not combine these into one misleading "accuracy" number.

### I. Project plan / engineering process

Create a concise visual timeline of the project phases, derived from `PROJECT_EXECUTION.md` and `Progress.md`.

Show the major story:

- foundation/data readiness
- make-it-work baseline
- evaluation harness
- measured ablations / architecture selection
- full-corpus production artifact build
- guardrails/API
- local production-readiness gates
- AWS deployment deferred until local readiness is complete

Do not invent completion status. Use the actual current status from the project docs.

### J. Current status / roadmap

Create a transparent "Current status" panel.

Clearly distinguish:

- completed
- in progress / integration gap
- deferred

The full-corpus dense serving adapter/integration gap must be visible if still unresolved.

AWS should be shown as **deferred until local production readiness**, not failed and not deployed.

### K. Footer

Include useful links if verifiable:

- API docs (`/docs`)
- health (`/health`)
- status (`/status`)
- GitHub repository if `git remote -v` confirms the URL

Do not expose local secrets or machine-specific sensitive information.

---

## 6. Visual design requirements

Use UI UX Pro Max guidance, but enforce these baseline requirements:

- professional data/engineering visual language
- responsive desktop/tablet/mobile layouts
- excellent spacing and typography
- accessible color contrast
- visible keyboard focus
- semantic landmarks and headings
- no horizontal overflow on mobile
- reduced-motion support via `prefers-reduced-motion`
- animations only when they improve comprehension
- use system fonts or safe web fonts; do not introduce brittle font dependencies
- meaningful empty/loading/error states
- no giant gradients or excessive glassmorphism that reduce credibility/readability
- no fake terminal text that pretends commands were run
- no fake live counters
- no autoplay effects

A dark-first technical theme is acceptable if the plugin recommends it, but light/dark handling should remain readable and accessible.

---

## 7. Data/source architecture for the showcase content

Avoid scattering hardcoded metrics throughout HTML.

Create one curated project-data structure (JSON or JS module) for static showcase facts.

Each significant metric/decision should ideally include:

```text
label
value
unit (optional)
context
source_path
source_section/source_key (when practical)
status_type: frozen | current-build | live-runtime | roadmap
```

Live runtime values such as service readiness, generation provider, model, and dense index row count should be fetched from `/status` instead of duplicated statically when feasible.

If static project-data generation is scripted, keep the script deterministic and local-only. It must not call external APIs.

---

## 8. API integration rules

Inspect the exact current schemas before coding.

Use only relative same-origin requests:

```text
GET /health
GET /status
POST /query
```

Do not hardcode `http://127.0.0.1:8000` inside frontend fetch logic.

Do not change CORS just to make this same-origin UI work.

Do not expose backend exceptions or stack traces to the UI.

If `/status` is temporarily unavailable, the showcase should still render; only live-status widgets should show an unavailable state.

If `/query` fails, the rest of the project showcase must remain usable.

---

## 9. Security / privacy

The frontend must never render or expose:

- API keys
- secrets
- environment-variable values containing credentials
- AWS credentials/account identifiers
- local secret files
- hidden protected TEST contents
- raw internal stack traces

Escape/safely insert all API-returned text. Prefer `textContent`/safe DOM creation over unsanitized `innerHTML` for dynamic content.

Do not add analytics, tracking pixels, CDN dependencies, or third-party telemetry.

---

## 10. Tests

Add focused tests for the UI serving integration without requiring browser automation unless browser tooling already exists.

At minimum verify:

- `GET /` returns `200` and HTML
- expected static assets are available
- `/docs` still works
- `/openapi.json` still works
- `/health` unchanged
- `/status` unchanged
- `/query` API contract unchanged using mocked/injected dependencies so no generation provider is called
- app factory still initializes correctly
- static routing does not shadow API paths

If practical, add small deterministic tests for any showcase-data builder/parser.

Do NOT make paid/network calls in tests.

---

## 11. Validation commands

After implementation run:

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Then start the service locally with:

```powershell
python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Perform local non-paid smoke checks:

```text
GET /
GET /health
GET /status
GET /docs
```

Do NOT submit a real `/query` that would invoke OpenRouter during this task. Validate the query UI with mocked automated tests and/or a deliberately mocked local dependency path only if one already exists.

Also manually inspect the UI at approximately:

- 1440px desktop
- 1024px tablet
- 390px mobile

Check keyboard navigation and focus states.

---

## 12. Documentation

Update documentation minimally and accurately:

- `Progress.md` — add Task 4.12 entry only after implementation/tests pass
- relevant UI/local-run section in README or project docs if needed
- document the local launch command and URLs
- document that `/` is now the custom project UI and `/docs` remains Swagger
- record that the UI is a local showcase and does not change the current production dense-integration gate

Do not rewrite historical Phase 3/Phase 4 records.

---

## 13. Acceptance criteria

Task 4.12 is complete only when all are true:

- custom UI loads at `/`
- `/docs`, `/health`, `/status`, `/query` remain compatible
- no paid/API/AWS call was made during implementation/testing
- protected TEST remains unopened at `0/3`
- RAG query form is wired to the real existing `/query` contract
- page has robust loading/error/empty states
- project showcase includes datasets, architecture, experiment-driven chunking/model selection, production build, guardrails, evaluation, planning, current status, and roadmap
- every displayed project metric is traceable to a repository source
- current live dense-index limitation is represented honestly
- responsive layout works on desktop/tablet/mobile
- accessibility basics pass manual review
- doctor passes
- portable tests pass
- full non-generation pytest passes
- no existing frozen artifact or scientific decision was modified

---

## 14. Git handling

Do NOT commit or push automatically.

At the end show:

```powershell
git status
git diff --stat
git diff
```

Also provide a concise report containing:

- files created
- files modified
- design direction chosen from UI UX Pro Max
- verified project source files used for showcase content
- UI routes/assets added
- API compatibility result
- doctor result
- portable-test result
- non-generation pytest result
- protected TEST usage (`0/3` expected)
- paid API calls made (`0` expected)
- AWS actions (`0` expected)
- any project facts you intentionally omitted because they could not be verified

Wait for explicit approval before committing or pushing.
