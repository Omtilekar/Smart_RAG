# Repository Structure

Established in Phase 0 Task 0.3. This document explains what each top-level
directory is for, which `src/` packages exist and why, and — critically for
anyone cloning this public repository — which paths are source-of-truth
tracked content versus generated/ignored local state.

A directory existing here does **not** mean the feature it's named for is
implemented. Most `src/` packages below contain only an empty `__init__.py`
at this point in the project. See `Progress.md` for what is actually
implemented versus planned.

## Tree

```text
SEC-RAG/
├── src/
│   ├── ingest/          # IMPLEMENTED — data acquisition + validation + audit
│   ├── normalize/       # IMPLEMENTED (Task 1.2) — EDGAR-CORPUS sections -> Markdown/frontmatter
│   ├── chunk/           # IMPLEMENTED (Task 1.3) — fixed-window tokenized chunks -> Parquet;
│   │                     # metadata_schema.py (Task 2.9) — canonical chunk record
│   │                     # schema (chunk_uid/chunk_local_id identity, field
│   │                     # types/nullability/enums), no new chunking pipeline
│   ├── embeddings/      # IMPLEMENTED (Task 1.4) — BAAI/bge-small-en-v1.5 wrapper, batch GPU embedding
│   ├── index/           # IMPLEMENTED (Task 1.5) — exact-cosine LanceDB vector index
│   ├── retrieval/       # IMPLEMENTED (Task 1.6) — baseline natural-language vector retriever
│   ├── generation/      # IMPLEMENTED (Task 1.7) — minimal grounded generation, OpenRouter adapter
│   ├── eval/            # PARTIAL (Tasks 1.8-1.10, 2.1-2.2) — citation-integrity
│   │                     # smoke helper (Task 1.8), the deterministic Phase 1
│   │                     # smoke-dataset builder (Task 1.9), the doc_recall@10
│   │                     # baseline metric logic (Task 1.10), the XBRL
│   │                     # fact-eligibility truth contract (Task 2.1), and the
│   │                     # frozen 15-tag evaluation registry loader (Task 2.2);
│   │                     # question generation, DEV/TEST split, and evidence
│   │                     # alignment NOT yet implemented
│   ├── router/          # planned responsibility: query classification, path selection
│   ├── rerank/          # planned responsibility: cross-encoder reranking
│   ├── crag/            # planned responsibility: retrieval confidence / corrective decisions
│   ├── guards/          # planned responsibility: input/context/output protections
│   ├── api/             # planned responsibility: FastAPI-facing layer
│   └── cli/             # IMPLEMENTED (Task 1.11) — phase1.py, the Phase 1
│                         # local end-to-end CLI (answer / evaluate); no
│                         # FastAPI/production API implemented here
│
├── configs/             # implemented (partial): serving_spike.json (Task 0.10),
│                         # normalize_development_corpus.json (Task 1.2),
│                         # chunk_development_corpus.json (Task 1.3),
│                         # embed_development_corpus.json (Task 1.4),
│                         # build_vector_index.json (Task 1.5),
│                         # citation_integrity_smoke.json (Task 1.8),
│                         # phase_1_9_smoke_evaluation.json (Task 1.9),
│                         # phase_1_10_baseline_metric.json (Task 1.10),
│                         # eval_tags.yaml (Task 2.2),
│                         # phase_2_3_evaluation_dataset.json (Task 2.3),
│                         # phase_2_4_dev_test_split.json (Task 2.4),
│                         # phase_2_7_msmarco_harness.json (Task 2.7),
│                         # phase_2_8_primary_evidence.json (Task 2.8)
│                         # (no new config for Task 2.9 - it defines schema,
│                         # not a runnable pipeline)
├── tests/               # implemented: Phase 0 foundation suite (Task 0.8),
│                         # see project_plan/TESTING.md
├── scripts/             # implemented: dev.py (Task 0.9), serving_spike.py (Task 0.10),
│                         # normalize_development_corpus.py (Task 1.2),
│                         # chunk_development_corpus.py (Task 1.3),
│                         # embed_development_corpus.py (Task 1.4),
│                         # build_vector_index.py (Task 1.5),
│                         # smoke_retrieval.py (Task 1.6),
│                         # smoke_generation.py (Task 1.7),
│                         # smoke_citation_integrity.py (Task 1.8),
│                         # build_smoke_evaluation.py (Task 1.9),
│                         # run_baseline_metric.py (Task 1.10, reused by
│                         # src/cli/phase1.py's evaluate subcommand),
│                         # build_truth_contract_summary.py (Task 2.1),
│                         # audit_eval_tag_registry.py (Task 2.2),
│                         # build_evaluation_dataset.py (Task 2.3),
│                         # build_dev_test_split.py (Task 2.4),
│                         # init_evaluation_schema.py (Task 2.5),
│                         # run_msmarco_harness.py (Task 2.7),
│                         # build_primary_evidence.py (Task 2.8),
│                         # audit_chunk_metadata_schema.py (Task 2.9, read-only
│                         # Phase 1 + Task 2.8 compatibility audit)
│                         # - see project_plan/DEVELOPER_COMMANDS.md, project_plan/SERVING_FEASIBILITY.md
├── results/             # planned: small committed metrics/experiment summaries
├── infra/               # planned: deployment/infrastructure definitions
│
├── prompts/             # IMPLEMENTED — task prompts that drove this project, kept for
│                         # educational/reproducibility value (data_download.md,
│                         # data_validation*.md, phase_0_Foundation/task_*.md, ...)
├── project_plan/        # IMPLEMENTED — design/planning documents (this file's home)
├── data/                # frozen datasets — see "Tracked vs generated" below
├── artifacts/           # runtime-generated, git-ignored, not created by default
├── logs/                # runtime-generated, git-ignored, not created by default
│
├── DATA_READINESS_REPORT.md   # IMPLEMENTED — frozen Phase 1 data statistics
├── Progress.md                 # IMPLEMENTED — dated engineering log
├── phase1_data_audit.log       # IMPLEMENTED — audit run log
├── stage{1..5}_*.log           # IMPLEMENTED — per-stage acquisition logs
├── .python-version              # IMPLEMENTED — "3.11"
└── .gitignore                   # IMPLEMENTED
```

`.venv/` (project-local Python environment, Task 0.1) and `.tmp/` (orphaned
disk state, flagged for cleanup) also exist locally but are git-ignored and
intentionally omitted from the tree above.

## `src/` package responsibilities

| Package | Status | Will eventually contain |
|---|---|---|
| `ingest/` | **implemented** | MS MARCO / EDGAR-CORPUS / XBRL / primary-doc fetchers, `validate.py`, `audit_data.py` |
| `normalize/` | **implemented** | `edgar_markdown.py` — minimal EDGAR-CORPUS -> Markdown/YAML-frontmatter renderer (Task 1.2), see `project_plan/PHASE1_NORMALIZATION.md` |
| `chunk/` | **implemented** | `fixed_window.py` — minimal 512-token fixed-window chunker (Task 1.3), see `project_plan/PHASE1_CHUNKING.md`; `metadata_schema.py` — the canonical 23-field chunk record schema, `chunk_uid`/`chunk_local_id` identity algorithms, offset/section/date/accession semantics (Task 2.9), see `project_plan/PHASE2_CHUNK_METADATA_SCHEMA.md`; later section-aware chunking pipeline (Phase 3.2) |
| `embeddings/` | **implemented** | `bge.py` — BAAI/bge-small-en-v1.5 wrapper, batch GPU embedding (Task 1.4), see `project_plan/PHASE1_EMBEDDINGS.md` |
| `index/` | **implemented** | `lancedb_index.py` — exact-cosine LanceDB vector table (Task 1.5), see `project_plan/PHASE1_VECTOR_INDEX.md`; later BM25/FTS, graph tables (Phase 3.4, 5.4) |
| `retrieval/` | **implemented** | `baseline.py` — vector-only baseline retriever (Task 1.6), see `project_plan/PHASE1_RETRIEVER.md`; later hybrid fusion + metadata filtering (Phase 3.5, 3.9) |
| `generation/` | **implemented** | `provider.py` (provider-neutral interface), `openrouter.py` (adapter), `minimal.py`, `citations.py` (Task 1.7), see `project_plan/PHASE1_GENERATION.md` |
| `eval/` | **partial** | `citation_integrity.py` — mechanical citation-integrity smoke check (Task 1.8), see `project_plan/PHASE1_CITATION_INTEGRITY.md`; `smoke_dataset.py` — deterministic 200-question document-level smoke dataset builder (Task 1.9), see `project_plan/PHASE1_SMOKE_EVALUATION.md`; `baseline_metrics.py` — pure doc_recall@10 metric logic (Task 1.10), see `project_plan/PHASE1_BASELINE_METRICS.md`; `truth_contract.py` — XBRL fact-eligibility contract (Task 2.1, refactored in Task 2.2 to consume the registry), see `project_plan/PHASE2_TRUTH_CONTRACT.md`; `tag_registry.py` — loader/validator for the frozen 15-tag `configs/eval_tags.yaml` (Task 2.2), see `project_plan/PHASE2_TAG_REGISTRY.md`; `evaluation_dataset.py` — record construction/hashing/duplicate+leakage checks for the 2,810-question Phase 2 evaluation dataset (Task 2.3), see `project_plan/PHASE2_EVALUATION_DATASET.md`; `dev_test_split.py` — company-disjoint DEV/TEST connected-component splitter (Task 2.4), see `project_plan/PHASE2_DEV_TEST_SPLIT.md`; `test_access.py` — controlled TEST-set loader with hash verification and a 3-run access budget (Task 2.4); `evaluation_schema.py` — the eval_runs/eval_question_results/eval_retrieved_items/eval_metrics/eval_stage_timings DuckDB schema, metric-definition registry, and schema-hash logic (Task 2.5); `eval_store.py` — the run-lifecycle storage API (start_run/record_*/complete_run/fail_run) all future experiments must use (Task 2.5; Task 2.6 added metric_definitions resync-on-reinit), see `project_plan/PHASE2_EVALUATION_SCHEMA.md`; `metrics.py` — hand-verified deterministic metric functions (recall/hit-at-k, MRR, binary nDCG@k, numeric_exact_match, correct_refusal, rate aggregation) reusing Task 1.10's frozen `doc_recall@10` hit semantics rather than reimplementing them (Task 2.6), see `project_plan/PHASE2_METRIC_TESTS.md`; `msmarco_harness.py` — MS MARCO benchmark-specific ID normalization/qrel grouping/multi-qrel recall+MRR+nDCG aggregation, reusing Task 2.6's metric primitives (Task 2.7), see `project_plan/PHASE2_MSMARCO_HARNESS.md`; primary-document evidence alignment implemented in the new `parse/` package (Task 2.8), see below |
| `parse/` | **implemented** | `source_identity.py` — deterministic `primary:{cik}:{accession}` identity for the 990 primary 10-K filings; `primary_html.py` — Docling-based structural parsing (sections/tables), source locators honestly scoped to Docling's own `self_ref`; `inline_xbrl.py` — raw namespace-aware inline-XBRL DOM extraction (contexts/units/divide-units/continuations/numeric normalization), independent of Docling; `evidence_alignment.py` — fact-to-node alignment reusing Task 2.1's truth contract and Task 2.2's tag registry unmodified (Task 2.8), see `project_plan/PHASE2_PRIMARY_EVIDENCE.md` |
| `router/` | structure only | Rules-first query classification/path selection (Phase 3.8) |
| `rerank/` | structure only | Cross-encoder reranking (Phase 3.6) |
| `crag/` | structure only | Reranker-score-based confidence grading (Phase 3.7) |
| `guards/` | structure only | Input/context/output guardrails (Phase 4.7–4.9) |
| `api/` | structure only | FastAPI service (Phase 4.10) |
| `cli/` | **implemented** | `phase1.py` — one-command demo (`answer`) and smoke-eval entry point (`evaluate`) (Task 1.11), see `project_plan/PHASE1_END_TO_END.md`; no FastAPI/production API |

`src/config.py` (Task 0.5 — implemented, see `project_plan/CONFIGURATION.md`),
`src/logging_utils.py` (Task 0.6 — implemented, see
`project_plan/LOGGING.md`), and `src/storage.py` (Task 0.7 — implemented,
see `project_plan/STORAGE.md`) were deliberately not stubbed out in
Task 0.3, so an empty
file never got mistaken for a completed feature ahead of time.

## Top-level directories

- **`configs/`** — versioned experiment/system configuration (e.g. chunk
  configs, `configs/eval_tags.yaml`). Contains `serving_spike.json` (Task
  0.10, see `project_plan/SERVING_FEASIBILITY.md`) as of this task; still
  otherwise empty pending Phase 1+.
- **`tests/`** — Phase 0 foundation suite implemented in Task 0.8 (66
  portable tests as of Task 0.10: config/logging/storage/dependency/
  ingest-import/LanceDB/serving-spike-helper portable tests, plus
  `local_data`/`gpu`/`model`-marked local capability smoke tests). See
  `project_plan/TESTING.md`. The injection-resistance test and other
  Phase 2+ tests don't exist yet — added when those features do.
- **`scripts/`** — `dev.py`, the developer command interface implemented
  in Task 0.9 (`doctor`/`test`/`test --portable`/`data`/`gpu`/`smoke`). See
  `project_plan/DEVELOPER_COMMANDS.md`. Also `serving_spike.py` (Task
  0.10), throwaway feasibility-benchmark code — not a `dev.py` subcommand,
  invoked directly. See `project_plan/SERVING_FEASIBILITY.md`.
- **`results/`** — small, human-readable experiment outputs meant to be
  public (`.csv`/`.json`/`.md`). The directory itself is tracked
  (`results/.gitkeep`); its contents are ignored by default except those
  three extensions — see `.gitignore`.
- **`infra/`** — deployment/infrastructure definitions (Phase 4.11). Empty
  as of Task 0.3.
- **`artifacts/`, `logs/`** — runtime-generated locations for build
  artifacts and (future) log files. Task 0.6 established the application
  logging convention (`src/logging_utils.py`) as console/stderr-only —
  `logs/` stays unused until a file or cloud sink is actually justified.
  `artifacts/` layout and creation policy (`normalized/`, `chunks/`,
  `indexes/`, `eval/`) are owned by `src/storage.py` (Task 0.7), see
  `project_plan/STORAGE.md`. Both are git-ignored and are *not* created as empty
  directories by default — they appear only when something actually writes
  to them.

## Tracked vs generated/ignored

### Tracked (source of truth)

```text
src/                    (including the empty __init__.py placeholders above)
infra/                  (currently just .gitkeep)
configs/                (serving_spike.json, Task 0.10; otherwise just .gitkeep)
scripts/                (implemented — dev.py Task 0.9, serving_spike.py Task 0.10)
tests/                  (implemented — conftest.py + 10 test_*.py, Tasks 0.8/0.10)
results/*.csv, results/*.json, results/*.md   (results/.gitkeep tracked too)
project_plan/
prompts/
Progress.md
DATA_READINESS_REPORT.md
phase1_data_audit.log, stage{1..5}_*.log
.python-version
.gitignore
pytest.ini              (Task 0.8)
requirements.txt, requirements-gpu.txt, requirements-dev.txt   (Task 0.4)
.env.example             (Task 0.5)
```

### Local/generated and git-ignored

```text
data/*                  (everything except data/.gitkeep — see DATA_READINESS_REPORT.md)
.venv/                  (Task 0.1 — project-local Python environment)
.tmp/                   (orphaned DuckDB spill — flagged for cleanup, not deleted yet)
artifacts/, logs/       (not created by default; ignored when they do appear)
*.duckdb, *.duckdb.wal, *.parquet, *.zip, *.idx, *.part, *.lance/
models/, .cache/, **/.huggingface/, *.onnx, *.safetensors, *.bin
.env* (except .env.example), *.pem, *.key, credentials*, secrets*
__pycache__/, *.py[cod], .pytest_cache/, .ipynb_checkpoints/
.claude/                (local coding-assistant tooling state)
results/* other than the tracked exceptions above
```

Full detail: `.gitignore` at the repository root.
