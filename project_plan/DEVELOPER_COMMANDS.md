# Developer Commands

## Overview

Routine Phase 0 foundation checks go through one cross-platform entry
point:

```bash
python scripts/dev.py <command>
```

Pure Python standard library (`argparse`, `subprocess`, `pathlib`) plus the
project's own already-tested modules (`src.config`, `src.storage`,
`pytest`, `torch`) — no CLI framework dependency, no second implementation
of config/storage/testing/GPU logic. Repository root is resolved from the
script's own file location, not the working directory, so it works when
invoked from anywhere; subprocesses always use `sys.executable`, so it
always runs against the same interpreter (and `.venv`) it was launched
with.

## Commands

| Command | Purpose | Failure semantics |
|---|---|---|
| `doctor` | environment/setup health (read-only, offline) | required-foundation checks (Python version, venv, `pip check`, core imports, `src.config`/`src.storage` load) must pass; local data / CUDA are reported as informational only — their absence never fails `doctor` |
| `test` | full `pytest` suite | delegates to `python -m pytest`, preserves its exit code exactly |
| `test -m "not generation_api"` | full suite minus the live-network test | recommended over plain `test` on any machine with real OpenRouter credentials in `.env` — see caveat below |
| `test --portable` | the public-clone-safe subset | `python -m pytest -m "not local_data and not gpu and not model"` — the exact Task 0.8 portable marker expression, not duplicated logic |
| `data` | frozen data-path validation | invoked explicitly, so missing input is a **failure** here (unlike `doctor`) — checks `is_dir()`/`is_file()` only, never scans/counts/downloads |
| `gpu` | PyTorch/CUDA kernel validation | invoked explicitly, so missing or broken CUDA is a **failure** — runs one real 512×512 CUDA matmul, never silently falls back to CPU; does *not* load the embedding model (that's `smoke`'s job, to keep this check fast) |
| `smoke` | local-capability smoke tests | `python -m pytest -m "local_data or gpu or model"` — delegates to the same marked tests `test`/`test --portable` already use |

**Known caveat, flagged 2026-09-16, not fixed here (Task 4.7)**: plain
`test` (no filter) collects `generation_api`-marked tests too - by
original Task 1.7 design, credentials merely needing to exist in `.env`
was assumed to be a rare, deliberate developer state. In practice, once
a machine has real `OPENROUTER_API_KEY`/`GENERATION_MODEL` configured
for routine local generation work, plain `test` silently makes a real,
live, credentialed network call every time - `python-dotenv` populates
`os.environ` from `.env` as a side effect of importing `src.config`
anywhere in the run, so this isn't visible from the command line at
all. This caused 3 unintended live OpenRouter calls during Task 4.7's
own regression testing (see
`project_plan/PHASE4_INPUT_GUARDRAILS.md`'s "Unintended live API calls"
section). The one test this affects
(`tests/test_openrouter_live_smoke.py`) now requires a separate,
explicit `RUN_LIVE_GENERATION_API_TEST=1` opt-in in addition to the
credentials, closing the immediate hazard. Whether `dev.py test` itself
should default to excluding `generation_api` (making the explicit `-m
"not generation_api"` form above the implicit default) is a broader
project-policy change, not made unilaterally here — left for a later
developer-command cleanup task.

## Typical workflow

After activating `.venv`:

```bash
python scripts/dev.py doctor
python scripts/dev.py test --portable
```

Before Phase 1 work on a machine with the full local stack (frozen data +
GPU + cached model):

```bash
python scripts/dev.py data
python scripts/dev.py gpu
python scripts/dev.py smoke
```

## Exit codes

```text
0        = success
non-zero = failure (pytest's own code for test/smoke; 1 for doctor/data/gpu
           failures; 130 on Ctrl+C)
```

Wrapped subprocess exit codes are never swallowed — a failing `pytest` run
inside `test`/`test --portable`/`smoke` always produces a non-zero
`dev.py` exit, which is what makes these safe to use in a future CI step.

## Safety

Commands never install packages, download data or models, require an API
key/credential, or modify `data/`. `doctor` and `data` are strictly
read-only; `gpu` operates entirely in GPU memory; `test`/`smoke` inherit
Task 0.8's temporary-write-only guarantees (`tmp_path`, or a disposable
`artifacts/` child cleaned up automatically). No command prints secrets,
`.env` contents, or a full `Settings` dump — only explicit, safe fields.

## Setup

See `project_plan/ENVIRONMENT.md` (Python/venv/CUDA) and
`project_plan/DEPENDENCIES.md` (package installation order). `dev.py` does
not create an environment or install anything — it only verifies one
already exists correctly.

## Related: serving_spike.py

`scripts/serving_spike.py` (Task 0.10) is a one-off feasibility benchmark,
invoked directly (`python scripts/serving_spike.py --target-chunks N`) —
deliberately **not** wired into `dev.py` as a subcommand, since it is
throwaway benchmark code, not a routine developer workflow step. See
`project_plan/SERVING_FEASIBILITY.md`.

## Related: the Phase 1 user-facing CLI (`src/cli/phase1.py`)

`dev.py` stays foundation/developer tooling only — it does not become the
user-facing RAG command. Task 1.11 gives the actual RAG system its own
thin local CLI, invoked directly (not a `dev.py` subcommand):

```bash
python -m src.cli.phase1 answer --question "..."
python -m src.cli.phase1 evaluate
```

See `project_plan/PHASE1_END_TO_END.md` for the full command contract,
configuration, and the Phase 1 exit-criteria evidence these two commands
produced.

## Related: the FastAPI service (`src/api/app.py`, Task 4.10)

Also not a `dev.py` subcommand — a production HTTP service, run via
`uvicorn` directly:

```bash
python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Development-only, with auto-reload (never used in the command above -
`--reload` must never be enabled for a production run):

```bash
python -m uvicorn src.api.app:create_app --factory --reload
```

See `project_plan/PHASE4_FASTAPI_SERVICE.md` for the full endpoint
contract, guard integration, and route coverage.
