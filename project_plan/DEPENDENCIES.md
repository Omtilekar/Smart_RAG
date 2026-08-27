# Dependency Management

## Python

Python 3.11 (see `project_plan/ENVIRONMENT.md` for why 3.11 over the
machine's global 3.14).

## Why dependencies are split into three files

```text
requirements-gpu.txt    tested CUDA-enabled PyTorch installation only
requirements.txt        direct runtime/project dependencies
requirements-dev.txt    development/testing dependencies
```

`torch` gets its own file and its own install step, installed **first**,
because `sentence-transformers`/`transformers` declare a generic `torch`
dependency. If `requirements.txt` were installed before the GPU build, or
`torch` were listed inside it without the special index, pip could satisfy
that generic dependency with a default PyPI wheel (frequently CPU-only) and
silently replace the CUDA 13.0 build validated in Task 0.2 on this exact
RTX 5060 / driver combination.

No `environment.yml`, `Pipfile`, `poetry.lock`, or `requirements.in` — plain
pip with three purpose-scoped files is sufficient for this project and
avoids a second competing dependency system.

## Installation

### 1. Create / activate `.venv`

See `project_plan/ENVIRONMENT.md` (Task 0.1).

### 2. Install GPU runtime (must be first)

```powershell
python -m pip install -r requirements-gpu.txt
```

### 3. Install project dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Install development dependencies

```powershell
python -m pip install -r requirements-dev.txt
```

## Verify

```powershell
python -m pip check

python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())"
# expected: 2.13.0+cu130 / 13.0 / True

python -c "import duckdb, pyarrow, requests, lancedb, fastapi, pytest, sentence_transformers, bs4; print('all core imports OK')"
```

## Why PyTorch is separate

Task 0.2 validated `torch==2.13.0+cu130` (official
`https://download.pytorch.org/whl/cu130` index) against this machine's RTX
5060 Laptop GPU (driver 610.74, driver-supported CUDA 13.3): real CUDA
kernel execution, CPU/GPU numerical parity, FP16/BF16, and a GPU
`bge-small-en-v1.5` embedding smoke test all passed. That specific build is
what every later phase's GPU work (embedding, later reranking/quantization
experiments) is validated against. Installing runtime/dev dependencies
after the GPU file — never before, never in the same command — is what
keeps a fresh clone from silently downgrading to CPU-only torch.

## Dependency policy

- Direct dependencies are pinned to the exact version that was actually
  installed and verified inside `.venv` (Python 3.11.9) — not copied from
  the machine's global environment, and not a raw `pip freeze` dump.
- Transitive dependencies are left to pip's resolver; they are not manually
  pinned unless a specific reproducibility problem demands it.
- The special GPU index/build is explicit in `requirements-gpu.txt`, never
  implicit.
- Every direct dependency in `requirements.txt` is either (a) actually
  imported by current code in `src/ingest/`, or (b) explicitly required by
  the near-term `PROJECT_EXECUTION.md` plan (Phase 0/1: PyArrow for
  Parquet chunk output, LanceDB for the vector index, FastAPI for later
  serving, python-dotenv for Task 0.5's configuration system). Phase 5
  research dependencies (Docling, ColBERT, graph libraries) are
  deliberately deferred until their feature is actually scheduled.
- No formatter/linter (black/ruff/mypy/pre-commit) has been adopted by this
  project, so none was added to `requirements-dev.txt` just because this
  task exists.

## Direct dependencies (as of Task 0.4)

| Group | Package | Version | Why |
|---|---|---:|---|
| GPU | torch | 2.13.0+cu130 | Embeddings, later reranking — validated Task 0.2 |
| Runtime | requests | 2.34.2 | `src/ingest/common.py` HTTP session |
| Runtime | huggingface_hub | 1.28.0 | `src/ingest/fetch_msmarco.py` direct import |
| Runtime | duckdb | 1.5.5 | XBRL facts DB, validation, audit (`src/ingest/*`) |
| Runtime | pyarrow | 25.0.1 | Parquet chunk output (Phase 1.3), LanceDB dependency |
| Runtime | beautifulsoup4 | 4.15.0 | `validate.py`/`audit_data.py` table/inline-XBRL checks |
| Runtime | lxml | 6.1.2 | bs4 parser backend used by the above |
| Runtime | sentence-transformers | 6.0.0 | Embedding pipeline (Phase 1.4) — validated Task 0.2 |
| Runtime | lancedb | 0.37.1 | Vector index (Phase 1.5) |
| Runtime | fastapi | 0.141.1 | API serving (Phase 4.10) |
| Runtime | uvicorn | 0.52.4 | ASGI server to actually run fastapi |
| Runtime | python-dotenv | 1.2.3 | `.env` loading — implemented in `src/config.py` (Task 0.5) |
| Dev | pytest | 9.1.1 | Test suite — implemented, 70 tests as of Task 0.10 (Task 0.8) |
| Dev | onnxruntime | 1.29.0 | CPU reranker inference, serving-spike benchmark only (Task 0.10) |
| Dev | psutil | 7.2.2 | Process RSS measurement, serving-spike benchmark only (Task 0.10) |

Transitive dependencies (numpy, transformers, tokenizers, pydantic, scipy,
scikit-learn, etc.) are installed automatically by the above and are not
individually pinned here — see `python -m pip list` inside `.venv` for the
full resolved set.

## Reproducibility verification

The documented three-file install sequence was reconstructed from scratch
in a temporary environment (`.tmp/dependency_check_venv/`, removed after
verification) — not just re-checked against the already-mutated working
`.venv`. `pip check` passed, `torch.__version__`/`torch.version.cuda`
matched exactly, `torch.cuda.is_available()` was `True`, a real CUDA tensor
operation succeeded, and every core package (`duckdb`, `pyarrow`,
`lancedb`, `fastapi`, `pytest`, `sentence_transformers`) imported
successfully. Full detail in `Progress.md`'s Task 0.4 entry.
