# SEC RAG: Project Overview

Snapshot as of 2026-10-25, based on `Progress.md` (last entry 2026-10-14) and the
current source. `PROJECT_SPEC.md` is the original Phase 1 design and is out of date.

## 1. Overview

SEC RAG answers questions about US public company filings (10-Ks and XBRL
financial data) with cited, verifiable answers, and refuses when the evidence is
not there. It is in Phase 4 of 5: the retrieval stack is chosen and measured, the
API, guardrails and web UI run locally, and AWS deployment is deferred.

| Failure mode | Design response |
| --- | --- |
| Right company, wrong fiscal year | Metadata pre-filtering (CIK + fiscal year) before vector search |
| Hallucinated financial figures | Numeric questions answered by SQL over XBRL facts, not retrieval |
| Confident answer when retrieval failed | CRAG-style confidence grading on the top-1 score, with refusal |
| Unsupported claims in the answer | Citation and groundedness checks on the output |
| Retrieved text carrying instructions | Retrieval-security guard and delimited, untrusted context |
| Unmeasurable quality | Frozen DEV set, config-hashed ablation table, protected TEST set |

Two tracks: the benchmark track uses MS MARCO only to prove the retrieval and
evaluation code matches published baselines; the project track is the SEC corpus.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Foundation: environment, storage, logging, serving spike | Complete |
| 1 | End to end on a development corpus | Complete |
| 2 | Evaluation: truth contract, dataset, DEV/TEST split, metrics, judge validation | Complete |
| 3 | Ablations: 14 tasks, 19-row ablation table, all 9 exit criteria pass | Complete |
| 4 | Make it real: full corpus, guardrails, FastAPI, web UI, caching, security, production dense retriever (4.A) | In progress (4.11 deployment deferred; 4.15 to 4.18 not started) |
| 5 | Optional extensions: table retrieval, graphs, late interaction | Not started |

The protected TEST set has never been opened (0 of 3 official runs used). The last
recorded test run was 2,324 passed.

## 2. Architecture

Every request passes through the same guarded pipeline.

```text
User question
  -> Input guard (length, scope, advice, injection)  -> rejected with a reason code
  -> Router (rules: company, year, intent)
      |- Structured XBRL route (DuckDB facts, derived math)
      |     -> Numeric provenance check ------------------------+
      |                                                          |
      '- Dense route                                             |
            Dense retrieval (LanceDB + exact-query cache)        |
            -> Retrieval security scan (poison, duplicates)      |
            -> Context guard (untrusted, delimited evidence)     |
            -> Generation (OpenRouter or Ollama, prompt cache)   |
            -> Output guard (citations, advice, groundedness) ---+
                                                                 v
                                      Answer with citations, or a refusal
```

Numeric questions that resolve to one company and year take the structured route
and skip generation. Everything else takes the dense route. The interactive
version is the Architecture page of the local web UI
(`src/api/static/architecture-diagram.html`).

## 3. Data

About 21 GB of source data under `data/`; derived artifacts under `artifacts/` are
about 142 GB. Neither is committed.

| Source | Content | Role |
| --- | --- | --- |
| EDGAR-CORPUS | 91,086 10-K filings, 1993 to 2020, pre-sectioned, tables stripped | Narrative text |
| XBRL Financial Statement Data Sets | 90.7M facts, 218,166 submissions, 10,757 companies | Ground truth and the SQL path |
| Primary documents | 990 complete 10-Ks (2021 to 2024) with tables and inline XBRL | Parsing and evidence alignment |
| MS MARCO | 8.8M passages, 510K queries | Harness correctness only |
| FinanceBench | 150 human-annotated questions | Independent validation (eval only) |

Findings that shaped the design:

- The (cik, year) join between EDGAR-CORPUS and XBRL is 81.71% inside the overlapping
  years, so evaluation is scoped to that window. Overall CIK overlap is 26.51%.
- XBRL restates 23.56% of (cik, tag, period) keys, so questions are anchored to an
  accession number, not just a fiscal year.
- Sections 1A, 1B, 9A, 9B and 15 are only 25 to 32% populated in EDGAR-CORPUS.
- Five silent validation bugs were caught and logged in `Progress.md`.

Corpora used downstream: a development corpus (1,493 documents, 323,971 chunks) for
all Phase 3 ablations, and the full corpus (10,487,096 chunk rows, frozen Qwen3
index) for the Phase 4 production build.

## 4. Ingestion pipeline

1. Fetch (`src/ingest/`): downloaders plus validation and `DATA_READINESS_REPORT.md`.
2. Parse (`src/parse/`): primary 10-K HTML with tables kept; inline-XBRL facts aligned to text.
3. Normalize (`src/normalize/edgar_markdown.py`): one Markdown file per filing with YAML frontmatter.
4. Chunk (`src/chunk/`): fixed-window, 256 tokens, no overlap (Task 3.2, frozen by config hash).
5. Embed (`src/embeddings/`): `Qwen/Qwen3-Embedding-0.6B`, 1024 dimensions (Task 3.3), now also the live query encoder (Task 4.A).
6. Index (`src/index/`): LanceDB vector index plus a full-text index for BM25.
7. XBRL serving (`scripts/export_xbrl_serving.py`): DuckDB fact export for the SQL path.

Artifact versioning (`src/artifacts/versioning.py`) hashes each stage's config.
All paths go through `src/storage.py`.

## 5. Retrieval

The selected stack is dense-only search with a CIK and fiscal-year pre-filter.
Hybrid fusion and reranking were measured and rejected. Since Task 4.A (2026-10-25) the
live dense route serves the full 10,487,096-row Qwen3 production index. The live
service does not yet use the pre-filter, the CRAG threshold or the full router: it
runs the input guard, then the structured XBRL route if it applies, then plain dense
retrieval, and unscoped search takes about 33 s.

| Component | Module | Result on DEV | Decision |
| --- | --- | --- | --- |
| Dense (Qwen3-Embedding-0.6B) | `src/retrieval/baseline.py` | Recall@10 0.9888 (88/89), MRR 0.9251 | Selected |
| BM25 / full-text | `src/retrieval/sparse.py` | Sparse baseline | Baseline only |
| RRF hybrid fusion | `src/retrieval/fusion.py`, `hybrid.py` | Practical tie with dense | Not adopted |
| Cross-encoder reranking | `src/rerank/`, `src/retrieval/reranked.py` | CIs below zero on MRR, nDCG@10, Recall@5 | Not adopted |
| Metadata pre-filter | `src/retrieval/filtered.py` | Recall@10 88/89 to 89/89 | Selected (not live) |
| CRAG-style grading | `src/crag/confidence.py` | Threshold 0.5531 (Youden's J 0.7644) | Selected (not live) |
| Rules-first router | `src/router/rules.py` | Accuracy 85.82% (1658/1932), macro F1 0.8871, 6 of 10 intents | Selected |
| XBRL SQL path | `src/sql/xbrl_lookup.py` | Trap leak rate 0.00% on 139 questions | Selected, live |
| Derived calculations | `src/sql/derived.py` | 100% exact match once attempted | Selected |
| Section navigation | `src/nav/section_navigation.py` | Scope leak rate 0.00% | Selected (not live) |

An exact-query retrieval cache (Task 4.13) wraps dense retrieval: in-process LRU
with TTL, evidence only. Locally a cached hit took 0.24 ms against 178 ms cold.

## 6. Generation, guardrails and security

- `GenerationProvider` is a provider-neutral protocol; `factory.py` reads
  `GENERATION_PROVIDER` and `GENERATION_MODEL` and never silently picks a default.
- `openrouter.py` is the live adapter (frozen model `openai/gpt-oss-20b`);
  `ollama_provider.py` is the free local adapter.
- Opt-in prompt-prefix caching (`PROMPT_CACHE_ENABLED=true`): locally, prompt
  processing for a same-evidence, new-question request fell from 3.7 s to 0.22 s.
  Live OpenRouter cache hits were not verified.

| Layer | Module | Checks |
| --- | --- | --- |
| Input (4.7) | `src/guards/input.py` | Length, scope, injection, financial-advice requests |
| Retrieval security (4.14) | `src/security/` | Poisoned, duplicate, provenance-less chunks; Unicode obfuscation |
| Context (4.8) | `src/guards/context.py` | Retrieved text is untrusted data, delimited, raw evidence preserved |
| Output (4.9) | `src/guards/output.py` | Citations must be supplied chunks; numeric provenance; advice refused |

None of the guards calls a model or the network. During Task 4.7, three unintended
live OpenRouter calls happened because loading `src.config` populates credentials
from `.env`; the live smoke test now needs its own explicit opt-in.

## 7. Evaluation

The harness was built before the retrieval stack (`src/eval/`): truth contract and
tag registry, accession-anchored dataset with unanswerable trap questions,
company-disjoint DEV/TEST split with an access log, retrieval metrics with paired
bootstrap CIs, MS MARCO harness validation, FinanceBench and LLM-judge validation,
and run logging keyed by config hash and git SHA.

The 19-row Phase 3 ablation table (`src/eval/phase3_ablation.py`) keeps every
experiment including negative results. Row 0 is the untouched trusted baseline.

| Metric (89-question frozen DEV scope) | Dense only | With CIK + year pre-filter |
| --- | --- | --- |
| Recall@10 | 0.9888 (88/89) | 1.0000 (89/89) |
| Recall@50 | 1.0000 | 1.0000 |
| MRR | 0.9251 | 1.0000 |
| nDCG@10 | 0.9407 | 1.0000 |

These show the stack is wired correctly and the filter helps; they are not an
estimate of production accuracy. That waits for the locked TEST run (Task 4.16).

Recorded limits: router scoped to 6 of 10 intents; derived calculations cover
difference and greater-than only; tree navigation has no DEV questions of its target
shape; no quantization on the production index; cold start reasoned, not measured.

## 8. API and web UI

FastAPI (`src/api/app.py`, `create_app`) wraps the logic in `src/api/service.py` and
serves the zero-build UI from `src/api/static/`.

| Endpoint | Purpose |
| --- | --- |
| `POST /query` | `{"question": "..."}` returns `status`, `answer`, `citations`, `route`, `reason_code`, `request_id` |
| `GET /health` | Liveness only |
| `GET /status` | Readiness plus config, cache, retrieval-security and prompt-cache snapshot |
| `GET /docs`, `/openapi.json` | Swagger UI and schema |
| `GET /` | Showcase and "Ask the RAG" chat UI |
| `/architecture`, `/experiments`, `/data`, `/evaluation`, `/roadmap` | Pages of the same single-page app |

Run locally:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/. Add `--reload` for development only. The default
provider is a local Ollama server; OpenRouter needs `OPENROUTER_API_KEY` and
`GENERATION_MODEL` in `.env`.

## 9. Repository layout and developer guide

| Path | Contents |
| --- | --- |
| `src/ingest`, `parse`, `normalize`, `chunk`, `embeddings`, `index` | Pipeline stages |
| `src/retrieval`, `rerank`, `crag`, `router`, `sql`, `nav` | Retrieval paths and routing |
| `src/generation` | Providers, citations, prompt cache |
| `src/guards`, `src/security` | Input, context, output guards; poisoning defense |
| `src/api` | FastAPI app, schemas, service, static UI |
| `src/eval`, `src/artifacts` | Evaluation harness, config hashing, versioning |
| `scripts/` | 47 scripts: `build_*`, `run_phase3_*` (frozen), `smoke_*`, `audit_*`, `dev.py` |
| `configs/`, `results/` | Experiment configs and small result JSON per run |
| `tests/` | Unit, integration, static-safety tests |
| `project_plan/`, `prompts/` | Design docs and agent task prompts |
| `infra/terraform/` | Fargate skeleton, never applied |
| `data/`, `artifacts/` | Gitignored data and derived artifacts |
| `Progress.md` | Engineering log |

```powershell
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
python scripts/smoke_retrieval_cache.py
python scripts/smoke_retrieval_security.py
python scripts/benchmark_prompt_cache.py --provider ollama --model gpt-oss:20b --repeats 3
```

Conventions: every experiment writes a config JSON and a result JSON keyed by config
hash and git SHA; frozen artifacts are never edited; protected TEST data is opened
only through `src/eval/test_access.py`; tests that could reach a paid API need an
explicit opt-in. Detailed rules: `GIT_CONVENTIONS.md`, `TESTING.md`, `LOGGING.md`,
`DEVELOPER_COMMANDS.md`.

## 10. Deployment, known gaps and roadmap

Gate A is done (Task 4.A): the live dense route serves the frozen 10,487,096-row
`Qwen/Qwen3-Embedding-0.6B` index through `ProductionDenseRetriever`, and fails
closed rather than falling back to the old 162,357-row BGE dev index
(`DENSE_RETRIEVER_MODE=dev` is an explicit opt-in). The next priority is routing the
selected company/year pre-filter into the live retriever: unscoped exact search was
measured at about 33 s per query, versus about 60 to 80 ms when scoped.

Deployment: `Dockerfile`, `.dockerignore`, `requirements-cpu.txt` and a Fargate
Terraform skeleton exist. Task 4.11 is deferred; no AWS resources have been created.
Fargate is recommended (Phase 3 warm p95 1,163 ms; cold start favors warm compute).

| Gap | Detail |
| --- | --- |
| Unscoped dense search is slow | About 33 s per query on 10.5M vectors; pre-filter not routed live yet |
| Production performance unmeasured | Task 4.15 not started |
| TEST never run | Task 4.16 is the first honest accuracy claim |
| No quantization | Exact search; larger memory than designed |
| Router / derived-calc scope | 6 of 10 intents, two operations |
| Tables | EDGAR-CORPUS has none; testable only on 990 primary docs |
| Sparse Items | 1A, 1B, 9A, 9B, 15 mostly empty in the source |
| Live provider cache | Verified with Ollama only |
| Scope | English, 10-K only, point-in-time |

Remaining Phase 4: route the pre-filter live (Gate B); 4.11 deployment (deferred);
4.15 performance evaluation; 4.16 locked TEST milestone; 4.17 failure analysis;
4.18 README and final documentation.

Phase 5 candidates: table-aware retrieval, Exhibit 21 subsidiary graph, XBRL
presentation hierarchy, SIC relationships, ColBERT late interaction, multi-hop
query decomposition, alternative models.

Deliberately excluded: Kubernetes, an always-on vector database, a local LLM in the
serving path, a web-search fallback (breaks provenance), LLM reranking, full-corpus
LLM graph extraction.
