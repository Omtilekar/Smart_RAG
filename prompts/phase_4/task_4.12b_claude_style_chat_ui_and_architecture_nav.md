# Task 4.12b — Claude-style Chat UI + Project Architecture Navigation

You are enhancing the existing SEC RAG web UI.

The current UI already has a working FastAPI backend and a project showcase.
This task changes the UX structure so that:

1. the default experience feels like a polished modern AI chatbot,
2. project/engineering information is moved out of the chat screen,
3. architecture is shown as a detailed systems diagram similar in structure to a professional RAG platform diagram,
4. all existing API behavior remains unchanged.

Use the installed **UI UX Pro Max** plugin for design guidance before implementing.

Do not copy Claude's branding, logo, proprietary assets, or exact visual identity.
The goal is a **Claude-inspired interaction model**:
calm, spacious, minimal, premium, conversation-first.

---

## 1. PRODUCT STRUCTURE

The site should have a clear navigation layer.

Primary navigation:

- Chat
- Architecture
- Experiments
- Data
- Evaluation
- Roadmap

Optional secondary nav:

- API Docs
- System Status
- GitHub

The default route `/` must open the **Chat** experience.

Project details must NOT clutter the main chat screen.

The chat screen should be focused almost entirely on asking questions and reading answers.

Project information belongs in the navigation tabs/pages.

---

## 2. CHAT EXPERIENCE — CLAUDE-INSPIRED

Design the main `/` experience to feel similar to a premium AI assistant workspace.

### Desktop layout

Use:

- left sidebar for navigation/history
- large central conversation column
- spacious message area
- bottom-centered sticky composer
- subtle top bar with project name/status

Do NOT create a dashboard-style homepage.

The user should immediately feel:

> "I am inside an AI assistant."

### Sidebar

Include:

- SEC RAG logo/wordmark
- New Chat
- Chat
- Architecture
- Experiments
- Data
- Evaluation
- Roadmap
- API Docs
- System Status

Optional recent conversations can be shown as local UI-only history if easy to implement.

Do not require persistent chat storage for this task.

### Main empty state

When no messages exist, center a minimal welcome state:

SEC RAG

"Ask questions about SEC filings and financial data"

Suggested prompt chips such as:

- What was Apple's revenue in 2020?
- Compare Microsoft's assets across two years
- Summarize risk factors from a filing
- What was Tesla's operating cash flow?
- Find a filing section about cybersecurity risk

These chips must call the existing `/query` endpoint only when clicked/submitted.

### Composer

Use a large rounded composer similar in interaction style to modern AI assistants:

- multiline textarea
- send button
- Enter sends
- Shift+Enter inserts newline
- disabled loading state
- subtle keyboard hint
- character counter only near limit
- max input length consistent with backend limits

Do not add unsupported upload/tool buttons unless clearly marked as inactive.

### Messages

User messages:
- compact
- visually distinct
- right-aligned or subtly differentiated

Assistant messages:
- wider
- readable typography
- markdown-like formatting where safe
- source/citation area below answer
- route/status metadata shown unobtrusively

Show useful metadata only if returned by the API:

- route
- latency
- source count
- structured/dense mode
- abstention
- guardrail rejection

Do not fabricate metadata.

### Loading state

Use a refined assistant-thinking indicator, not a generic spinner.

Examples:

- "Retrieving SEC evidence…"
- "Resolving structured financial data…"
- "Generating grounded answer…"

Use only states that can be inferred safely from the request lifecycle.

### Error states

Design good UI for:

- backend unavailable
- query validation failure
- guardrail rejection
- generation provider error
- empty response
- timeout

Never expose internal stack traces.

---

## 3. ARCHITECTURE TAB

Create a dedicated **Architecture** page.

This page should visually resemble the supplied reference diagram in STRUCTURE:

- clear left-to-right / top-to-bottom system blocks
- arrows between components
- online RAG pipeline separated from offline ingestion/build pipeline
- visible boundaries between major subsystems
- simple professional systems-diagram aesthetic

Do NOT copy the exact colors or visual assets from the reference image.

Use the project's own visual language.

Recommended style:

- dark or light neutral background matching site theme
- thin system borders
- subtle status colors
- arrows/connectors
- grouped containers
- readable labels
- responsive SVG/CSS layout
- selectable text

---

## 4. ARCHITECTURE — ONLINE RAG PIPELINE

Show this high-level sequence:

User
  ↓
Chat UI
  ↓
FastAPI `/query`
  ↓
Request Validation
  ↓
Input Guardrails
  ↓
Intent / Route Decision

Then branch into:

A. Dense Retrieval
B. Structured XBRL
C. Tree / Section Navigation

Then converge into the appropriate downstream response path.

### Dense Retrieval branch

Show:

Query
  ↓
Query Embedding
  ↓
LanceDB
  ↓
Candidate Chunks
  ↓
CRAG / relevance threshold
  ↓
Metadata + provenance
  ↓
Context construction
  ↓
Context guardrails
  ↓
Generation provider
  ↓
Citation validation
  ↓
Output guardrails
  ↓
FastAPI response

### Structured XBRL branch

Show:

Structured financial query
  ↓
Company / CIK resolution
  ↓
Fiscal period resolution
  ↓
Metric / tag resolution
  ↓
DuckDB SQL query
  ↓
Canonical fact selection
  ↓
Optional derived calculation
  ↓
Structured provenance
  ↓
Deterministic answer

Do not imply LLM generation is required for this path if it is not.

### Tree / Section Navigation branch

Show:

Filing resolution
  ↓
Section identification
  ↓
Section scope
  ↓
Evidence extraction

Status label:

IMPLEMENTED + EVALUATED
NOT CURRENTLY LIVE-ROUTED

---

## 5. LIVE VS PRODUCTION ARTIFACTS

This distinction must be highly visible and truthful.

### Live dense serving

Current live FastAPI dense retriever:

- BAAI/bge-small-en-v1.5
- development index
- 162,357 rows

Label:

**LIVE NOW**

### Frozen production dense artifact

Production artifact:

- Qwen/Qwen3-Embedding-0.6B
- 1024 dimensions
- normalized vectors
- 10,487,096 chunks / index rows

Label:

**PRODUCTION ARTIFACT**
**INTEGRATION PENDING**

Do not imply the production Qwen index is already serving requests.

Use consistent status styling:

- green = live
- blue = validated/frozen artifact
- amber = integration pending
- dashed/muted = implemented but not currently routed

---

## 6. ARCHITECTURE — OFFLINE INGESTION / BUILD PIPELINE

Below the online RAG pipeline, create a clearly separated:

**Offline Data & Index Build Pipeline**

This should be visually similar in concept to the lower half of the supplied reference diagram.

Show data sources first:

EDGAR-CORPUS
XBRL
Primary SEC filings

Then:

Raw SEC Data
  ↓
Validation / Data Readiness
  ↓
Normalization
  ↓
Fixed-window Chunking
  ↓
Embedding
  ↓
Embedding Shards
  ↓
LanceDB Vector Index
  ↓
Production Retrieval Artifact

Side path:

XBRL raw data
  ↓
DuckDB loading / normalization
  ↓
Structured XBRL serving representation

Show key scale where verified:

- EDGAR-CORPUS filings: 91,086
- normalized non-empty bodies: 90,239
- valid empty-source docs: 847
- chunks: 10,487,096
- chunk shards: 54
- embedding vectors: 10,487,096
- embedding dimension: 1024
- XBRL facts: 90,685,753
- XBRL submissions: 218,166
- XBRL CIKs: 10,757
- distinct XBRL tags: 291,429

Do not invent numbers.

---

## 7. EXPERIMENTS TAB

Create an **Experiments** navigation page.

This page tells the engineering decision story.

Use cards/timeline/table visualizations for:

### Chunking selection

Show tested alternatives from project artifacts.

Show final frozen winner:

- fixed window
- 256 content tokens
- zero overlap
- stride 256
- final partial retained

Explain:

Selected from controlled evaluation, not intuition.

### Embedding model selection

Show candidate benchmark results from project artifacts.

Highlight final winner:

Qwen/Qwen3-Embedding-0.6B

- revision from frozen project record
- 1024 dimensions
- cosine similarity
- normalized embeddings

Do not invent comparison scores.

### Sparse / hybrid experiment

Show:

Dense baseline
+
BM25 / FTS
+
RRF hybrid fusion

Result:

Hybrid was negative/tie relative to dense-only.

Decision:

Dense-only retained.

### Reranking experiment

Show:

Dense candidates
  ↓
Cross-encoder reranker

Result:

Large negative result.

Decision:

No reranker retained.

The purpose of this page is to show that complexity was rejected when evidence did not support it.

---

## 8. DATA TAB

Create a clean data portfolio page.

Sections:

- EDGAR-CORPUS
- XBRL
- Primary filings
- full-corpus normalized data
- chunk corpus
- embedding corpus

Use metric cards and small explanatory diagrams.

Do not expose local filesystem paths unnecessarily.

Do not expose secrets.

---

## 9. EVALUATION TAB

Create an Evaluation page showing:

- retrieval methodology
- frozen DEV discipline
- regression testing
- citation integrity
- guardrail testing
- structured routing evaluation
- production-readiness gates

Show protected TEST only as:

Protected TEST usage: 0 / 3

Do not open or inspect protected TEST.

Do not display protected TEST questions.

---

## 10. ROADMAP TAB

Create a Roadmap page showing:

Completed:
- data preparation
- baseline RAG
- evaluation harness
- architecture optimization
- full-corpus production artifacts
- XBRL serving
- generation abstraction
- guardrails
- FastAPI
- local UI

Current gap:
- production Qwen dense retriever integration into live serving

Then:
- local end-to-end production integration
- regression/integration gate
- reliability/performance gate
- final evaluation/readiness
- release candidate freeze
- AWS deployment

AWS should be labeled:

**DEFERRED UNTIL LOCAL PRODUCTION READINESS**

Do not imply AWS runtime is currently deployed.

---

## 11. TOP-LEVEL VISUAL STYLE

The overall UI should feel:

- premium
- calm
- minimal
- research-engineering focused
- modern AI assistant
- portfolio-grade

Use UI UX Pro Max for design guidance.

Aim for a visual feel in the family of:

- modern AI chat products
- Linear
- Vercel
- Stripe engineering docs
- Anthropic-style calm spacing

But do NOT copy proprietary branding/assets exactly.

### Typography

Prioritize reading comfort.

Avoid:
- giant marketing headlines on chat screen
- excessive gradients
- gaming-style neon
- excessive glassmorphism
- dense dashboard cards everywhere

### Color

Use a restrained neutral palette.

One accent color is enough.

System status colors may use green/blue/amber.

### Motion

Use subtle motion only:

- sidebar transitions
- hover states
- message appearance
- architecture panel expansion

Respect `prefers-reduced-motion`.

---

## 12. RESPONSIVE DESIGN

Desktop:
- persistent sidebar
- centered chat column

Tablet:
- collapsible sidebar

Mobile:
- drawer navigation
- full-width chat
- composer pinned safely above browser chrome
- architecture diagrams horizontally scrollable or stacked

Do not allow architecture labels to overlap.

---

## 13. IMPLEMENTATION CONSTRAINTS

Prefer:

- existing FastAPI app
- HTML templates/static files already introduced by the UI task
- CSS
- lightweight vanilla JavaScript

Do NOT introduce React/Vite/npm unless there is a strong technical reason and it is explicitly justified before implementation.

The site should continue to run with:

python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000

Expected routes:

/                    Chat
/architecture        Architecture
/experiments         Experiments
/data                Data
/evaluation          Evaluation
/roadmap             Roadmap
/docs                 FastAPI Swagger
/health               API health
/status               Runtime status

A client-side tab/router is acceptable if cleaner, but deep links should still behave sensibly.

---

## 14. DATA / CLAIM TRACEABILITY

Before writing project claims, inspect:

- Progress.md
- project_plan/
- results/
- configs/
- manifests
- source code
- live `/status` schema

Every metric shown in the UI must be traceable to project evidence.

Prefer frozen/final values over older historical values.

If historical values differ, label them as historical experiment results.

Do not create attractive fake metrics.

---

## 15. DO NOT CHANGE CORE RAG BEHAVIOR

This is a UI / documentation / visualization task.

Do not modify:

- retrieval algorithms
- production artifacts
- embeddings
- vector indexes
- routing semantics
- XBRL logic
- generation provider behavior
- guardrails
- frozen experiment results

Do not:

- call OpenRouter during implementation/testing
- access AWS
- rebuild embeddings
- rebuild the vector index
- inspect protected TEST
- make paid API calls

---

## 16. VALIDATION

Verify:

GET /                 -> 200
GET /architecture     -> 200
GET /experiments      -> 200
GET /data             -> 200
GET /evaluation       -> 200
GET /roadmap          -> 200
GET /health           -> 200
GET /status           -> 200
GET /docs             -> 200

Run:

python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"

Do not run generation_api tests.

Manually verify:

- chat feels conversation-first
- project information is no longer mixed into the chat screen
- navigation works
- architecture resembles a professional system architecture diagram
- online RAG and offline ingestion pipelines are clearly separated
- live vs frozen vs planned statuses are obvious
- architecture arrows remain aligned on desktop/tablet/mobile
- mobile nav works
- chat composer works
- no horizontal layout breakage

Finally report:

- files created
- files modified
- routes/pages added
- metrics displayed and their project sources
- architecture sections added
- responsive behavior
- tests run/results
- git diff --stat

Do not commit or push until explicitly approved.
