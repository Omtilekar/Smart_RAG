# Task 4.11 - Deployment

## Status

**PARTIAL / DEFERRED (local-only).** Container packaging, local Docker
validation, and infrastructure-as-code preparation are complete. Real
cloud provisioning was explicitly deferred by user decision (2026-09-16) -
no AWS account, region, VPC, or budget was available in the working
session, and `PROJECT_EXECUTION.md`'s own Phase 4 "If short on time"
section explicitly names deployment (4.11) as deferrable when "a locally
reproducible system with a documented deployment design" exists. This
document is that design.

Do not read this as "another user can use the deployed system without
developer intervention" - that Phase 4 exit criterion is **not** met yet.
No live, independently-reachable endpoint exists.

## Roadmap scope actually used

`PROJECT_EXECUTION.md`'s Task 4.11 checklist (verbatim):

```text
- deploy to the selected compute target,
- configure object storage where required,
- configure secrets safely,
- configure logging,
- test cold/warm behavior,
- test system availability independently of the development machine.
```

"Test system availability independently of the development machine" is
the one bullet this pass does not satisfy - it requires a real, separately
reachable deployment, which was deferred. Everything else is addressed
below to the extent possible without real cloud resources.

## Known Task 4.10 limitation (unchanged, still true)

The dense HTTP route (`POST /query`, non-`xbrl_fact` intents) is wired to
the Phase 1 development LanceDB index:

```text
162,357 rows, BAAI/bge-small-en-v1.5, development-corpus metadata schema
```

**Not** the Task 4.4 full-corpus production index:

```text
10,487,096 rows, Qwen/Qwen3-Embedding-0.6B, 1024 dimensions, production
chunk schema (chunk_uid)
```

This container packages and deploys the Task 4.10 service exactly as it
exists - it does not add a schema-adapting retriever for the full-corpus
index (that remains out of scope, per Task 4.10's own documented
decision). Any deployment of this image, local or cloud, must be labeled
as using the **development dense index**, never as full-corpus production
dense serving. The structured XBRL route (`xbrl_fact` intent) has no such
gap - it queries the real, frozen `data/xbrl.duckdb` directly.

## A real bug found and fixed during this task

`src/api/dependencies.py`'s `build_production_dependencies()` hardcoded
`load_model(device="cuda")`, ignoring `Settings.device`/
`resolve_device()`. Invisible on the GPU dev box Tasks 1.1-4.10 were built
on; fatal on the frozen CPU-only Fargate serving target (no CUDA device
present) - the container would have crashed at startup on every real
target. Fixed (user-authorized, 2026-09-16) to
`load_model(device=resolve_device(settings.device))`. No retrieval,
routing, chunking, embedding-model-choice, or guardrail semantics changed
- only which device the same frozen BGE model loads onto. Covered by two
new portable tests in `tests/test_api_dependencies.py` (fully mocked, no
real model/CUDA/GPU required).

## Container strategy

`Dockerfile` (repo root), `.dockerignore` (repo root).

- Base: `python:3.11-slim`.
- CPU-only: installs `requirements-cpu.txt` (new - CPU-wheel torch,
  mirrors `requirements-gpu.txt`'s install-order contract) then
  `requirements.txt`. Never installs `requirements-gpu.txt`'s CUDA torch
  build - the frozen serving decision is continuously-warm **CPU**
  Fargate (`project_plan/SERVING_FEASIBILITY.md`), and a CPU container
  should not inherit a multi-GB CUDA runtime it cannot use (this task's
  own prompt, "Runtime dependency discipline").
- Entry point reuses the real Task 4.10 app factory unchanged:
  `python -m uvicorn src.api.app:create_app --factory --host 0.0.0.0
  --port 8000 --workers 1`. No `--reload`. One worker, explicitly not a
  throughput claim - the embedding model + LanceDB table + duckdb
  connection are heavy resident state (`ProductionDependencies`,
  constructed once at startup); a second worker would duplicate all of
  it, and nothing in this task measured whether that's safe or useful.
- Non-root (`appuser`, uid 10001). No `.env` copied in. No API keys as
  build args. Explicit `WORKDIR /app`. `EXPOSE 8000` only. No debug/admin
  port.
- Built image size: **4.07 GB**. Not "smallest possible" - `requirements.txt`
  is installed as a single, unmodified unit (docling-slim/docling-parse/
  pdfplumber/scikit-learn/pandas/scipy are included even though the
  deployed API path doesn't import them), because trimming it would mean
  inventing a new, previously-untested dependency-subsetting strategy this
  task wasn't authorized to design. Documented here as a known,
  real future optimization, not a silent gap.
- Secret scan performed on the build context/staged files before
  building (`Dockerfile`, `.dockerignore`, `requirements-cpu.txt`,
  `infra/terraform/*` - no API key, AWS credential, or PEM-shaped
  material found; `.env` is gitignored and does not exist in this
  repository as of this task).

## Model cache strategy

`BAAI/bge-small-en-v1.5` @ pinned revision
`5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` (the exact revision
`src/embeddings/bge.py` verifies) is downloaded **once, at image build
time**, to a fixed `HF_HOME=/opt/hf-cache`. `HF_HUB_OFFLINE=1` is set
immediately after that build step (not before - `huggingface_hub` refuses
its own download otherwise) and stays set for every later layer and at
runtime. The running container never makes a network call to Hugging
Face; `verify_cached_model_assets()` (unchanged) still enforces that all
required files are present before `SentenceTransformer(...)` loads. No
"latest" resolution anywhere - the revision is the same one already
frozen in `src/embeddings/bge.py`.

## Artifact strategy

Large runtime assets are **never baked into the image** - only mounted at
container run time.

| Asset | Source | Size | Container path | Read-only | Startup validation | Failure behavior |
|---|---|---|---|---|---|---|
| Dev dense LanceDB index | `artifacts/indexes/f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd/BAAI--bge-small-en-v1.5/` | 470 MB | same relative path under `/app/artifacts/...` | yes | `build_production_dependencies()` raises `DependencyInitializationError` if the directory is absent; `open_chunk_table()` validates the table opens | app never becomes ready; `/status` would 500 during lifespan and the process exits |
| `xbrl.duckdb` | `data/xbrl.duckdb` | 6.68 GB | `/app/data/xbrl.duckdb` | yes | `duckdb.connect(..., read_only=True)` + `XbrlFactIndex.__init__`'s `eligible_facts()` query | same - lifespan raises, process exits |
| `configs/eval_tags.yaml` | repo | 7.5 KB | baked into image (small, versioned, not a runtime data artifact) | n/a | `get_registry()` validates on load | import-time failure |
| Embedding model | HF cache, pinned revision | ~130 MB | baked into image (`/opt/hf-cache`) | n/a | `verify_cached_model_assets()` | `RuntimeError` naming the missing file |

**Real finding from this task's own local validation**: bind-mounting
`xbrl.duckdb` directly from the Windows host filesystem into the
container (`docker run -v C:\...\data\xbrl.duckdb:/app/data/xbrl.duckdb:ro`)
made DuckDB fail with `IOException: Could not read from file ...: Cannot
allocate memory` - ordinary file reads through that same bind mount
worked fine (verified directly with a plain Python file read at the same
byte offset), so this is specifically DuckDB's memory-mapped access
pattern hitting a Docker-Desktop-for-Windows bind-mount limitation, not
an application bug and not a memory-capacity issue (the Docker Desktop VM
had 15.1 GB available). Copying the same file into a native Docker
volume (Linux-native filesystem, not host-bind-mounted) fixed it
immediately - confirmed by opening it with real DuckDB and querying real
row counts. **This is why a real cloud deployment should plan on EFS (or
an S3-sync-to-local-disk pattern), not a literal host-path bind mount** -
EFS-backed volumes under real Fargate don't go through this Windows-host
translation layer at all, but this local finding is still a real,
recorded data point for that later decision, not a guess.

The full-corpus production index (47.6 GB) was never touched by this
task - it is out of scope per the Task 4.10 dev-index decision above, and
`project_plan/STORAGE.md` confirms no S3/cloud backend exists yet in this
repository for it regardless.

## Secrets strategy

`OPENROUTER_API_KEY` is never written into the image, `.dockerignore`, or
any committed file. For local container validation, a placeholder value
(`local-validation-placeholder-not-a-real-key`) was passed as a run-time
`-e` flag purely so `OpenRouterProvider.__init__`'s eager presence check
(`src/generation/openrouter.py`) doesn't block startup - it was never
sent to OpenRouter, because the smoke query used the non-generation
structured XBRL route (see "Local container validation" below). For a
real deployment, `infra/terraform/main.tf`'s ECS task definition reads it
via `secrets` (an ARN reference, `var.openrouter_api_key_secret_arn`) -
never a plaintext `environment` entry - matching AWS Secrets Manager/SSM
Parameter Store injection. No secret value appears anywhere in
`infra/terraform/`.

## Logging

Unchanged from Task 0.6/4.10: structured `log_event(...)` to
stderr/stdout only (`src/logging_utils.py`). The container's `CMD`
inherits this - no file handler, no new logging framework. Docker/ECS
capture stdout/stderr natively; `infra/terraform/main.tf` wires the ECS
task definition's `awslogs` driver to a dedicated CloudWatch Logs group
for when a real deployment happens, without changing what the
application itself logs.

## Health and status

Unchanged from Task 4.10. `/health` is a pure liveness check (never
touches `state`, never calls a dependency). `/status` reflects real
readiness (`ready: true/false`, dependency snapshot, dense index row
count). Neither endpoint calls OpenRouter. `infra/terraform/main.tf`'s
ECS container `healthCheck` targets `/health` only, with a 60s
`startPeriod` to allow for CPU model-load time (~1-2s observed locally,
generous margin for a colder/smaller Fargate CPU allocation).
`/query` is never used as a health check.

## Infrastructure as code

**Terraform** (user decision, 2026-09-16) - `infra/terraform/`
(`README.md`, `variables.tf`, `main.tf`). Parameterized ECR repository +
ECS Fargate task definition/service shape only. **Not applied** -
`terraform validate` passes (Terraform v1.15.5, `hashicorp/aws` >= 5.0),
but `terraform plan`/`apply` were never run, and no real AWS resource
exists because of it. No load balancer, autoscaling policy, or
artifact-delivery (EFS/S3) resource is defined - see
`infra/terraform/README.md`'s "What this is not."

## Open decisions before a real deploy

Not resolved by this task - flagged, not guessed:

- AWS account id, region
- VPC id, subnet ids, public vs private topology, whether a load balancer
  is required
- ECR repository name/creation authorization, ECS cluster
  name/creation authorization
- Artifact-delivery mechanism for `xbrl.duckdb`/dev index at cloud scale
  (EFS is the leading candidate per this task's own bind-mount finding
  above, but was never decided or provisioned)
- IAM role ARNs for `task_execution_role_arn`/`task_role_arn`
- Actual Secrets Manager/SSM ARN for `OPENROUTER_API_KEY`
- Desired task count / autoscaling policy beyond the default of 1
- Explicit authorization for ongoing Fargate compute cost (continuously
  warm, per the frozen serving decision - this is real, recurring cost
  once actually deployed, not a one-time charge)

## Local container validation (performed, PASSED)

Docker Desktop 28.5.1, built and run locally on 2026-09-16:

1. `docker build -t sec-rag-api:task-4-11 .` - succeeded, image digest
   `sha256:72fd23e204e887557a7f9df0e655e4deaaa9718b8ca92e080a1dcbdd94589541`,
   4.07 GB.
2. Ran with real dependencies (CPU device, dev index + `xbrl.duckdb` via
   native Docker volumes per the artifact-strategy finding above,
   placeholder `OPENROUTER_API_KEY`).
3. `GET /health` -> `200 {"status":"ok"}`.
4. `GET /status` -> `200`,
   `{"ready":true,"dependencies":{"embedding_model_loaded":true,"dense_index_open":true,"xbrl_connection_open":true,"generation_provider_configured":true},"config":{"dev_chunk_config_hash":"f1dc04d4b748a0f27cd80acb993b258b9f4dbaebe0093b34475d23fc1ab52bcd","dev_embedding_model":"BAAI/bge-small-en-v1.5","generation_provider":"openrouter","generation_model":"openai/gpt-oss-20b","dense_index_row_count":162357}}`
   - `dense_index_row_count: 162357` confirms this is the development
     index, exactly as documented, never silently the full-corpus count.
5. `POST /query` with a synthetic, non-paid, structured-XBRL-routing
   question ("What was the total assets for Moduslink Global Solutions
   Inc in fiscal year 2016?" - a real fact from the frozen
   `data/xbrl.duckdb`, not protected TEST) -> `200`,
   `{"status":"answered","route":"structured_xbrl","citations":["0001193125-16-738725"], ...}`.
   **Zero OpenRouter calls made** - the structured route never reaches
   `MinimalGenerator`/the provider. CPU embedding-model load (used only
   for the dense-route fallback path, not this specific query) completed
   in ~1s.
6. Container stopped and removed (`docker stop`/`rm`). No host artifact
   was mutated - the successful run used native Docker volumes (one-time
   read-only copies made via a throwaway `alpine` container), never a
   direct host bind mount, so `data/`/`artifacts/` on the host were never
   write-accessible to the container at all.

No cloud deployment smoke was performed (deferred, see "Status" above).

## Paid generation API calls during Task 4.11

**Zero.** The only `/query` smoke request used the structured XBRL route,
which never calls a `GenerationProvider`. `OPENROUTER_API_KEY` was set to
a placeholder value that was never transmitted anywhere.

## Protected TEST usage

**0/3** (unchanged). Protected TEST was never opened, inspected, or run.
The synthetic smoke question above was constructed directly from the
frozen, non-protected `data/xbrl.duckdb` (a real fact already used to
serve every other frozen structured-route request this system will ever
answer), never from the TEST split.

## Regression gates (before/after this task)

`python scripts/dev.py doctor` - PASS (unchanged).
`python scripts/dev.py test --portable` - 2208 passed (baseline, before
this task's own new tests), 0 failed.
`python -m pytest -m "not generation_api"` - run both before and after
this task's changes; see the accompanying results JSON for the final
counts. No chunking/embedding/routing/guardrail/CRAG-threshold/generation
-provider test was modified.

## Tests added this task

- `tests/test_api_dependencies.py` - two new fully-mocked portable tests
  for the device-resolution fix (no real model/CUDA required).
- `tests/test_deployment_artifacts.py` - 13 portable static checks over
  `Dockerfile`/`.dockerignore`/`infra/terraform/*` (no secrets, no
  hardcoded AWS account/ARNs, app-factory entry point, no `--reload`,
  non-root, dev-index identity stays visible, no dangerous absolute
  Windows paths, no protected-TEST references, Terraform account-specific
  variables have no invented defaults).

## Files touched

```text
Dockerfile                              (new)
.dockerignore                           (new)
requirements-cpu.txt                    (new)
infra/terraform/README.md               (new)
infra/terraform/variables.tf            (new)
infra/terraform/main.tf                 (new)
src/api/dependencies.py                 (one-line device fix)
tests/test_api_dependencies.py          (2 new tests)
tests/test_deployment_artifacts.py      (new, 13 tests)
.gitignore                              (added Terraform state/cache patterns)
project_plan/PHASE4_DEPLOYMENT.md       (this file, new)
results/phase_4_11_deployment_summary.json (new)
```

## Next roadmap task

Not started, per this task's own instructions. `PROJECT_EXECUTION.md`
lists **4.12 Observability** next. Task 4.11 itself remains
**PARTIAL / DEFERRED**, not COMPLETE - the "test system availability
independently of the development machine" bullet and the Phase 4 exit
criterion "another user can use the deployed system without developer
intervention" are both still open, pending the account-specific decisions
above and explicit authorization for real, cost-bearing AWS provisioning.
`Progress.md` is intentionally not updated with a Task 4.11 completion
entry - per this task's own instructions, that only happens once
acceptance criteria fully pass.
