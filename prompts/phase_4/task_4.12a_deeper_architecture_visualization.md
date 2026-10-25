Enhance the existing SEC RAG project showcase UI by adding a substantially
deeper architecture visualization.

IMPORTANT:
Do NOT replace the existing high-level architecture diagram.
Keep it as the "System Overview" / Level-1 diagram.

Add a new section immediately after it:

    Deep System Architecture

The goal is to make the site useful as a serious engineering portfolio.
A reviewer should be able to understand how data becomes searchable,
how queries are routed, how retrieval works internally, how generation
is guarded, what is evaluated offline, and which production components
are currently live versus frozen/not-yet-integrated.

Use the UI UX Pro Max plugin for layout/design guidance before implementing.

============================================================
1. ARCHITECTURE PRESENTATION
============================================================

Create TWO architecture views:

A. Level 1 — existing architecture
   Keep the current simple flow:
   Input Guards
   -> Router
   -> Retrieval routes
   -> Context Guards
   -> Generation
   -> Output Guards
   -> FastAPI

B. Level 2 — Deep Architecture
   This must be much more detailed and visually organized.

The Level-2 architecture should preferably be presented as either:

- an interactive expandable architecture diagram, or
- a tabbed architecture explorer

Suggested tabs:

    Online Query Path
    Retrieval & Data Plane
    Offline Build Pipeline
    Evaluation & Release
    Runtime / Serving

Do not make one unreadably huge diagram.

============================================================
2. ONLINE QUERY PATH
============================================================

Show the real online request flow in detail.

Include:

Browser / Client
    |
    v
FastAPI
    POST /query
    GET /health
    GET /status
    |
    v
Request Validation
    - request schema
    - query type validation
    - max input length
    |
    v
Input Guardrails
    - empty input
    - max 2,000 chars
    - disallowed control characters
    - prompt injection detection
    - financial/advice request detection
    - PII detection
    - out-of-scope detection
    |
    v
Intent / Route Decision
    - rules-first routing
    - structured financial intent detection
    - dense retrieval fallback
    - tree/navigation capability should be shown as implemented/frozen
      but NOT currently live-routed

Then branch into the actual retrieval paths.

============================================================
3. DENSE RETRIEVAL PATH
============================================================

Show dense retrieval internally, not as one box.

Query
    |
    v
Embedding Model
    |
    v
Query Vector
    |
    v
LanceDB Vector Search
    |
    v
Candidate Chunks
    |
    v
Metadata / Provenance
    |
    v
Relevance / CRAG Decision
    |
    v
Context Construction
    |
    v
Context Guardrails
    |
    v
Generation
    |
    v
Citation Validation
    |
    v
Response

Show the important frozen Phase 3 decisions alongside this path:

Chunking:
    fixed window
    256 content tokens
    0 overlap
    stride 256

Production embedding artifact:
    Qwen/Qwen3-Embedding-0.6B
    1024 dimensions
    cosine similarity / normalized embeddings

Production corpus:
    10,487,096 chunks

Production vector index:
    10,487,096 rows

IMPORTANT TRUTHFULNESS REQUIREMENT:

The live FastAPI dense route currently uses the DEVELOPMENT index:

    BAAI/bge-small-en-v1.5
    162,357 rows

The full production Qwen index exists as a frozen artifact but is NOT
yet integrated into the live retriever.

Visually distinguish:

    LIVE NOW
    FROZEN PRODUCTION ARTIFACT
    PLANNED INTEGRATION

Do not imply the Qwen 10.49M-row index is already being served.

This distinction is important and should actually make the engineering
story stronger.

============================================================
4. STRUCTURED XBRL PATH
============================================================

Show this route separately because it is fundamentally different from
dense RAG.

Query
    |
    v
Structured Intent Detection
    |
    v
Company / CIK Resolution
    |
    v
Fiscal Year / Period Resolution
    |
    v
Metric / XBRL Tag Resolution
    |
    v
DuckDB SQL Query
    |
    v
Canonical Fact Selection
    |
    v
Optional Derived Calculation
    |
    v
Structured Provenance
    |
    v
Deterministic Response

Data source:

    data/xbrl.duckdb

Show relevant scale:

    ~90.7M XBRL facts
    218,166 submissions
    10,757 CIKs
    291,429 distinct tags

Important:

This structured path can return deterministic structured answers.
Do NOT draw it as necessarily requiring LLM generation.

If the current implementation bypasses generation for structured answers,
show that correctly.

============================================================
5. TREE / SECTION NAVIGATION
============================================================

Show the tree-navigation capability separately.

Pipeline:

Filing
    |
    v
Filing Resolution
    |
    v
SEC Section Tree
    |
    v
Section Identification
    |
    v
Section Scope
    |
    v
Evidence Extraction

Label it clearly:

    IMPLEMENTED + EVALUATED
    NOT CURRENTLY LIVE-ROUTED THROUGH FASTAPI ROUTER

Mention the frozen evaluation characteristics only if verified from
project artifacts.

Do not make it appear active in the current web query flow.

============================================================
6. CONTEXT CONSTRUCTION
============================================================

Break the current "Context Guardrails" box into its actual responsibilities.

Show:

Retrieved Evidence
    |
    v
Provenance Validation
    - document identity
    - chunk identity
    - source metadata
    |
    v
Untrusted Evidence Boundary
    - retrieved content cannot override system instructions
    |
    v
Evidence Formatting
    |
    v
Generation Context

Mention:

Retrieved SEC content is treated as untrusted data, not instructions.

============================================================
7. GENERATION LAYER
============================================================

Show generation as a provider abstraction.

Context
    |
    v
Generation Interface
    |
    +--> OpenRouter provider
    |
    +--> Local Ollama provider

Current configured production/testing provider:

    openrouter
    openai/gpt-oss-20b

Do not call OpenRouter while developing this UI.

Show provider configuration as runtime/config-driven rather than
hardcoded.

============================================================
8. OUTPUT SAFETY / CITATION PIPELINE
============================================================

Expand output processing:

Generated Answer
    |
    v
Citation Parser
    |
    v
Citation Integrity Check
    - malformed citation
    - unknown citation
    |
    v
Advice / Safety Check
    |
    v
Final Response Envelope
    |
    v
FastAPI Response

Also show:

valid zero-citation abstention

when the system intentionally cannot answer.

============================================================
9. OFFLINE DATA / BUILD PIPELINE
============================================================

Add a separate architecture visualization for the offline production
pipeline.

Raw SEC Data
    |
    +--> EDGAR-CORPUS
    |
    +--> SEC XBRL
    |
    +--> Primary filings
    |
    v
Normalization
    |
    v
Chunking
    |
    v
Embedding
    |
    v
Vector Index Build
    |
    v
Production Artifacts

Show verified scale:

EDGAR-CORPUS:
    91,086 filings

Normalization:
    90,239 non-empty normalized bodies
    847 valid empty-source documents

Chunking:
    10,487,096 chunks
    54 Parquet shards

Embedding:
    Qwen3-Embedding-0.6B
    1024-d
    10,487,096 vectors
    54 embedding shards

Vector index:
    10,487,096 rows

Represent config hashes / manifests visually as "Reproducibility /
Artifact Identity" rather than dumping long hashes into the main diagram.

Allow a user to expand a details panel if they want exact hashes.

============================================================
10. MODEL / CHUNK SELECTION PIPELINE
============================================================

This is very important for the portfolio.

Add an "Architecture Decisions" subsection showing how choices were made,
not merely what choices were made.

For chunking show:

Candidate chunk strategies
    |
    v
DEV Evaluation
    |
    v
Retrieval Metrics
    |
    v
Winner Selection
    |
    v
Frozen Configuration

Winner:

    256 content tokens
    zero overlap

For embeddings show:

Candidate embedding models
    |
    v
Controlled Benchmark
    |
    v
Retrieval Evaluation
    |
    v
Winner Selection
    |
    v
Qwen3-Embedding-0.6B

For hybrid retrieval show:

Dense
+
Sparse / BM25
    |
    v
RRF Experiment
    |
    v
No measurable improvement / negative result
    |
    v
Dense-only retained

For reranking show:

Dense candidates
    |
    v
Cross-encoder reranker experiment
    |
    v
Negative result
    |
    v
No reranker retained

This is important:
SHOW NEGATIVE EXPERIMENTS.

The portfolio should demonstrate that architecture choices came from
evaluation rather than blindly adding complexity.

============================================================
11. EVALUATION / RELEASE PIPELINE
============================================================

Add a separate control-plane style diagram:

Frozen DEV Evaluation Set
    |
    v
Ablation / Experiment
    |
    v
Metrics
    |
    v
Regression Tests
    |
    v
Decision Record
    |
    v
Frozen Configuration
    |
    v
Production Artifact Build
    |
    v
Local Production Readiness Gates
    |
    v
AWS Deployment (deferred)

Show that protected TEST remains isolated.

Do NOT display or inspect protected TEST records.

Show only:

    Protected TEST usage: 0 / 3

if that value is still verified from project records.

============================================================
12. PRODUCTION READINESS / DEPLOYMENT
============================================================

Show runtime/deployment architecture separately:

Browser
    |
    v
FastAPI Application
    |
    +--> Dense index
    +--> XBRL DuckDB
    +--> Embedding model
    +--> Generation provider

Local runtime today

and below it:

Planned AWS deployment

    ECR
    ECS Fargate
    EFS / persistent artifact storage
    CloudWatch
    Terraform

AWS deployment is currently DEFERRED until local production-readiness
gates pass.

Do not suggest that AWS resources are currently running.

============================================================
13. VISUAL LANGUAGE
============================================================

Use a professional systems-engineering visual style.

Use consistent status styling:

Green:
    live / validated

Blue:
    frozen production artifact

Amber:
    planned / integration pending

Muted / dashed:
    implemented but not currently routed

Avoid excessive glowing/neon effects.

Architecture should feel like:

    Stripe engineering docs
    Vercel systems diagrams
    Datadog architecture pages
    modern ML infrastructure documentation

not like a gaming dashboard.

Use responsive SVG/CSS-based diagrams where practical.

Avoid embedding architecture as a static image because:
- text should remain selectable
- responsive layout matters
- tooltips should work
- future metrics should be easy to update

============================================================
14. INTERACTIVITY
============================================================

Add useful interactions.

Examples:

Hover over:
    Qwen embedding model

shows:
    model revision
    dimension
    similarity function

Hover over:
    Chunking

shows:
    256 tokens
    zero overlap
    why selected

Hover over:
    Dense index

shows both:

    LIVE
    BGE development index
    162,357 rows

    PRODUCTION ARTIFACT
    Qwen index
    10,487,096 rows
    integration pending

Clickable architecture boxes may open a side panel containing:

    Purpose
    Input
    Output
    Implementation
    Evaluation evidence
    Current status

============================================================
15. DATA SOURCING
============================================================

Do NOT invent architecture facts.

Before rendering project metrics, inspect:

    Progress.md
    project_plan/
    results/
    configs/
    artifact manifests
    current /status behavior
    existing source code

Every displayed project metric or architecture claim must be traceable to
one of those sources.

If multiple historic metrics differ, prefer the final/frozen project
decision and clearly label historical experiments as historical.

============================================================
16. DO NOT CHANGE CORE SYSTEM
============================================================

This task is UI/documentation visualization only.

Do not:

- change retrieval behavior
- replace embedding models
- rebuild embeddings
- rebuild the vector index
- modify routing
- modify guardrails
- change generation providers
- access AWS
- make paid API calls
- open protected TEST
- modify frozen evaluation results

============================================================
17. VALIDATION
============================================================

After implementation verify:

GET /
    200

GET /health
    200

GET /status
    200

GET /docs
    200

Architecture renders correctly on:

    desktop
    tablet
    mobile

Verify visually that:

- diagrams do not overlap
- labels are readable
- arrows remain correctly connected
- architecture boxes remain inside their containers
- horizontal overflow is handled gracefully
- live vs frozen vs planned states are visually obvious

Run:

python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"

Do NOT run generation_api tests.

Finally report:

- files modified
- architecture components added
- project metrics displayed
- source files used to verify those metrics
- test results
- screenshots or browser verification summary
- git diff --stat

Do not commit until explicitly approved.