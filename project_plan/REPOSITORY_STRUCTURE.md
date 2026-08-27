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
│   ├── chunk/           # planned responsibility: normalized docs -> chunks
│   ├── embeddings/      # planned responsibility: embedding model wrappers, batch embedding
│   ├── index/           # planned responsibility: vector/sparse/graph index construction
│   ├── retrieval/       # planned responsibility: retrieval execution, hybrid fusion, filtering
│   ├── generation/      # planned responsibility: LLM generation/provider interface
│   ├── eval/            # planned responsibility: truth contract, benchmark sets, metrics
│   ├── router/          # planned responsibility: query classification, path selection
│   ├── rerank/          # planned responsibility: cross-encoder reranking
│   ├── crag/            # planned responsibility: retrieval confidence / corrective decisions
│   ├── guards/          # planned responsibility: input/context/output protections
│   ├── api/             # planned responsibility: FastAPI-facing layer
│   └── cli/             # planned responsibility: command-line entry points
│
├── configs/             # implemented (partial): serving_spike.json (Task 0.10),
│                         # normalize_development_corpus.json (Task 1.2)
├── tests/               # implemented: Phase 0 foundation suite (Task 0.8),
│                         # see project_plan/TESTING.md
├── scripts/             # implemented: dev.py (Task 0.9), serving_spike.py (Task 0.10),
│                         # normalize_development_corpus.py (Task 1.2)
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
| `chunk/` | structure only | Fixed-window baseline chunker (Phase 1.3), later section-aware (Phase 3.2) |
| `embeddings/` | structure only | Embedding model wrapper, batch GPU embedding (Phase 1.4) |
| `index/` | structure only | LanceDB vector index, BM25/FTS, graph tables (Phase 1.5, 3.4, 5.4) |
| `retrieval/` | structure only | Vector-only baseline retriever (Phase 1.6), hybrid fusion + metadata filtering (Phase 3.5, 3.9) |
| `generation/` | structure only | `generate(prompt, context) -> answer` provider interface (Phase 1.7) |
| `eval/` | structure only | `truth_contract.py`, tag registry, ~3,000-question benchmark, metrics (Phase 1.9, 2.1–2.6) |
| `router/` | structure only | Rules-first query classification/path selection (Phase 3.8) |
| `rerank/` | structure only | Cross-encoder reranking (Phase 3.6) |
| `crag/` | structure only | Reranker-score-based confidence grading (Phase 3.7) |
| `guards/` | structure only | Input/context/output guardrails (Phase 4.7–4.9) |
| `api/` | structure only | FastAPI service (Phase 4.10) |
| `cli/` | structure only | One-command demo / smoke-eval entry points (Phase 1.11) |

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
