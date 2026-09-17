# Task 4.11 — Deployment

## Objective

Deploy the already-implemented Phase 4 service in the serving environment
required by the authoritative roadmap, without changing the frozen RAG
semantics.

Task 4.10 established the HTTP boundary:

```text
GET  /health
GET  /status
POST /query
```

Task 4.11 owns deployment/infrastructure only.

It must answer:

```text
Can the already-tested FastAPI service be packaged, configured, started,
kept healthy, observed, and reached in the target serving environment
without weakening the frozen application contract?
```

Do NOT redesign retrieval.
Do NOT change chunking or embeddings.
Do NOT re-run scientific ablations.
Do NOT change routing semantics.
Do NOT change guardrail semantics.
Do NOT change the generation provider/model selection.
Do NOT open protected TEST.
Do NOT make paid generation calls merely to prove deployment.
Do NOT silently deploy the Phase 1 development index as if it were the
full-corpus production dense index.

The authoritative definition is the exact Task 4.11 section in:

`project_plan/PROJECT_EXECUTION.md`

Read that section before making infrastructure changes.

If the authoritative Task 4.11 checklist materially differs from this prompt,
follow `PROJECT_EXECUTION.md` and report the difference explicitly rather
than silently reconciling it.

---

# Repository

Project root:

`C:\Om\Codes\RAG`

Before changing anything, inspect at minimum:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`
- `project_plan/PROJECT_SPEC.md`
- `project_plan/GIT_CONVENTIONS.md`
- `project_plan/TESTING.md`
- `project_plan/CONFIGURATION.md`
- `project_plan/LOGGING.md`
- `project_plan/REPOSITORY_STRUCTURE.md`
- `project_plan/STORAGE.md`
- `project_plan/SERVING_FEASIBILITY.md`
- `project_plan/PHASE4_GENERATION_PRODUCTION_INTERFACE.md`
- `project_plan/PHASE4_INPUT_GUARDRAILS.md`
- `project_plan/PHASE4_CONTEXT_GUARDRAILS.md`
- `project_plan/PHASE4_OUTPUT_GUARDRAILS.md`
- `project_plan/PHASE4_FASTAPI_SERVICE.md`
- current `infra/`
- current `src/api/`
- current `src/config.py`
- current `src/storage.py`
- current `scripts/dev.py`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `requirements-gpu.txt`
- `requirements-dev.txt`
- any existing Docker/container files
- any existing AWS/Fargate/ECR/ECS documentation or scripts

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not rely on this prompt alone for repository state.

---

# Hard Precondition — Task 4.10

Task 4.11 may begin only if Task 4.10 is actually COMPLETE.

Current Progress.md records:

```text
Phase 4 — Make It Real
  4.1 Full-corpus normalization               — COMPLETE
  4.2 Full-corpus chunking                    — COMPLETE
  4.3 Full-corpus embedding                   — COMPLETE
  4.4 Full-corpus vector index                — COMPLETE
  4.5 XBRL serving representation             — COMPLETE
  4.6 Generation production interface         — COMPLETE
  4.7 Input guardrails                        — COMPLETE
  4.8 Context guardrails                      — COMPLETE
  4.9 Output guardrails                       — COMPLETE
  4.10 FastAPI service                        — COMPLETE

Next: 4.11 Deployment
```

Verify the real code/tests before proceeding.

At minimum confirm:

- `src/api/app.py` / app factory exists
- `/health`, `/status`, `/query` match Task 4.10 documentation
- FastAPI routes are thin and use the existing service/orchestration layer
- real dependencies are constructed lazily through lifespan/startup
- API tests use fakes for paid providers
- local integration passes with fake generation
- Task 4.10 made zero paid API calls
- protected TEST remains unopened

If Task 4.10 is not actually complete:

STOP.

Do not repair Task 4.10 inside Task 4.11 except for a tiny factual
documentation correction.

---

# CRITICAL KNOWN LIMITATION FROM TASK 4.10

Task 4.10 discovered a real production integration gap:

```text
BaselineRetriever / RetrievalResult:
  hard-code the Phase 1 17-column development schema

Phase 1 dense index:
  162,357 rows
  BAAI/bge-small-en-v1.5
  development-corpus metadata schema

Task 4.4 production index:
  10,487,096 rows
  Qwen/Qwen3-Embedding-0.6B
  1024 dimensions
  production chunk schema
  uses chunk_uid rather than Phase 1 chunk_id
  omits several development-only provenance fields
```

Task 4.10 therefore wired the dense HTTP route to the **Phase 1 development
index**, by explicit user decision, rather than pretending the existing
`BaselineRetriever` could query the full-corpus production index.

This limitation MUST remain visible during Task 4.11.

## Non-negotiable deployment rule

Do NOT describe or label a deployment as a fully production-ready SEC RAG
service if the dense route is still backed by the 162,357-row development
index.

Before any production deployment claim, determine what the authoritative
Task 4.11 roadmap expects:

### Case A — Task 4.11 is only a deployment-mechanics exercise

If `PROJECT_EXECUTION.md` explicitly allows deploying the current Task 4.10
service as a deployment smoke / infrastructure validation:

- deployment may proceed,
- label it clearly as using the development dense index,
- preserve the existing limitation in every deployment summary,
- do not claim full-corpus dense serving is complete.

### Case B — Task 4.11 expects the real production service

If the roadmap requires deployment of the full-corpus production RAG path:

STOP before deployment.

Report that the missing full-corpus retriever/schema adapter is a prerequisite
not implemented by Tasks 4.1–4.10.

Do NOT implement a new production retriever inside Task 4.11 unless
`PROJECT_EXECUTION.md` explicitly assigns that work to Task 4.11.

Do NOT silently point `BaselineRetriever` at Task 4.4; Task 4.10 already
verified that this raises a schema mismatch.

This is the most important stop condition in this task.

---

# Frozen Production Decisions

Do not reopen these during deployment.

## Full-corpus text artifacts

```text
full-corpus chunks:
  10,487,096

chunk_config_hash:
  ba99e2f7861c48bc66b1c3078341fa2305f9d3888df9a4d0ce03b91b58e32b06

embedding model:
  Qwen/Qwen3-Embedding-0.6B

embedding revision:
  97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3

embedding dimension:
  1024

vector dtype:
  float32

retrieval:
  dense-only selected

distance:
  cosine

index:
  exact / flat LanceDB

RRF:
  NOT selected

cross-encoder reranking:
  NOT selected

metadata prefilter:
  selected

CRAG threshold:
  0.5531
```

## Structured path

```text
XBRL serving representation:
  COMPLETE / frozen

structured SQL/XBRL route:
  selected
```

## Tree path

```text
tree navigation:
  frozen selected capability

Task 4.10 limitation:
  not currently reachable through the live router/API because the frozen
  router taxonomy has no tree-navigation intent
```

Do not invent new routing during deployment.

## Generation

```text
GENERATION_PROVIDER=openrouter
GENERATION_MODEL=openai/gpt-oss-20b
```

Local/offline Ollama remains an experiment provider.

Do not bake provider credentials into images, infrastructure code, or Git.

## Serving target

Task 0.10 selected:

```text
Fargate / continuously warm compute preferred
```

because the measured warm vector+rerank p95 and process-cold proxy made the
serverless target unsuitable at that time.

Phase 3 later removed reranking from the selected production stack, but the
recorded serving direction remains continuously warm compute unless the
authoritative roadmap explicitly instructs Task 4.11 to revisit the target.

Do not silently switch to Lambda because it is easier to deploy.

---

# First Step — Extract the Exact Task 4.11 Contract

Before writing Dockerfiles, Terraform, CloudFormation, CDK, ECS definitions,
or deployment scripts, read the exact Task 4.11 section.

Write down internally:

```text
Task 4.11 exact title:
Required deployment target:
Required cloud/provider:
Required artifact transport:
Required container strategy:
Required CPU/GPU assumptions:
Required memory:
Required persistent storage:
Required secrets mechanism:
Required networking:
Required health checks:
Required logs/metrics:
Required deployment validation:
Required rollback behavior:
Required cost constraints:
Required infrastructure-as-code format:
Required tests:
Required results/documentation:
Explicit non-goals:
```

Do not invent cloud/account decisions.

If the roadmap requires AWS/Fargate but essential account-specific choices
are missing, STOP AND ASK rather than guessing.

Examples:

- AWS account
- region
- VPC/subnets
- public vs private service
- ECS cluster
- ECR repository
- desired task count
- CPU units
- memory
- load balancer
- domain name
- TLS certificate
- secrets source
- artifact bucket
- IAM roles
- monthly budget

Do not create real paid cloud resources without explicit user authorization
for the concrete deployment action.

Preparing infrastructure code is different from provisioning it.

---

# Deployment Authorization Boundary

A prompt to "complete Task 4.11" authorizes implementation/testing of the
deployment task as defined by the roadmap, but real cloud provisioning can
create cost.

Before executing any command that creates or mutates billable external
resources, verify the user's explicit authorization exists in the current
task context.

Examples include:

```text
aws ecs create-service
aws ecs update-service
aws ecr create-repository
aws elbv2 create-load-balancer
terraform apply
cdk deploy
cloudformation deploy
```

If the task prompt/roadmap only asks for deployable infrastructure code and
a local container validation, do not provision cloud resources.

If explicit authorization is absent:

- prepare the exact commands/infrastructure,
- validate locally where possible,
- stop before the billable mutation,
- report what remains to be run.

Do not claim deployed status.

---

# Protected TEST

Protected TEST remains sealed.

Official usage before Task 4.11:

`0 / 3`

Rules:

- do not open TEST,
- do not inspect TEST questions,
- do not run TEST,
- do not use TEST for deployment smoke checks,
- do not consume an official TEST run.

At task completion explicitly report:

`official TEST usage: 0/3`

If deployment validation appears to require protected TEST:

STOP.

Use synthetic or non-protected SEC-style smoke questions instead.

---

# Paid Generation Safety

Deployment validation must not casually spend generation credits.

Requirements:

- health/status checks must never call OpenRouter,
- readiness checks must never call OpenRouter unless the authoritative
  roadmap explicitly defines external-provider reachability as readiness,
- ordinary deployment smoke should use a fake generation provider where
  architecture permits,
- if a real deployed `/query` generation call is explicitly required, STOP
  and ask for authorization before spending credits unless the user has
  already explicitly authorized that live call,
- do not set `RUN_LIVE_GENERATION_API_TEST=1` as part of deployment.

Preferred regression commands remain:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Record Task 4.11 paid generation API calls precisely.

Do not claim zero historical project calls.

---

# Containerization

If the roadmap requires a container, create the smallest honest runtime image
that can run the selected service.

Do not copy:

- `data/` wholesale
- `artifacts/` wholesale
- `.venv/`
- `.env`
- `.git/`
- `.tmp/`
- model caches unrelated to runtime
- test fixtures not needed at runtime
- development benchmark artifacts

Use a `.dockerignore`.

## Runtime dependency discipline

The development environment currently includes a CUDA PyTorch stack.

A Fargate CPU service should not blindly inherit a multi-GB CUDA runtime
unless the authoritative service actually requires GPU inference in Fargate.

Inspect the selected deployment path:

- If query embedding/model inference is required inside the service and the
  chosen target is CPU Fargate, determine whether a CPU-only runtime package
  strategy already exists.
- If GPU Fargate/ECS is required, confirm the roadmap/cloud target supports
  it and do not assume standard Fargate GPU support.
- If the model is externalized or embeddings are produced elsewhere, follow
  the actual architecture.

Do not silently create a new runtime dependency strategy that conflicts with
`requirements-gpu.txt`.

If CPU-vs-GPU deployment is undefined and materially affects image size,
cost, or viability:

STOP AND ASK.

---

# Container Security

Use sane production defaults where compatible with the roadmap:

- non-root user where practical,
- no secrets in image layers,
- no `.env` copied into image,
- no API keys in build args,
- no writable source tree requirement,
- explicit working directory,
- deterministic entrypoint,
- bounded exposed port,
- no development auto-reload,
- no shell debug server.

Do not add an arbitrary security framework or reverse proxy unless required.

Run a secret scan against the Docker build context / staged files before
building.

---

# Application Entry Point

Task 4.10 implemented an app factory.

Reuse it.

Do not create a second FastAPI app solely for deployment.

The runtime command should use the existing factory, conceptually:

```text
uvicorn src.api.app:create_app --factory ...
```

Use the real module path from the repository.

Do not use `--reload` in the production container.

Do not invent worker counts without a reason.

Heavy model/index memory means multiple workers may duplicate large resident
state; inspect the actual lifecycle before setting `--workers > 1`.

If worker count is undefined and materially affects memory:

prefer one worker for the first deployment smoke unless the roadmap says
otherwise, and document that this is not a throughput claim.

---

# Artifact Strategy

Deployment must define how required runtime artifacts reach the service.

Potential runtime assets include:

```text
dense LanceDB index
embedding model files/cache
XBRL serving representation
router gazetteer source
configuration
```

Do not assume local Windows artifact paths exist inside the container.

For each runtime asset, document:

```text
source
identity/hash/version
container/runtime location
read-only vs writable
startup validation
failure behavior
```

## Production artifacts

If deploying the real production stack, use the frozen artifact identities.

For Task 4.3, the final embedding manifest is:

```text
a4d1421bb287ea6aa21398f1fca99f1e11650b7c0d49979077140bb17456fbc8
```

Do not mutate the canonical manifest merely to fix machine-specific paths.

## Development-index deployment smoke

If the authoritative task allows the current Task 4.10 dev-index-backed
service to be deployed only as an infrastructure smoke, label the asset as:

```text
development dense index
162,357 rows
NOT full-corpus production dense serving
```

This distinction must appear in deployment docs/results.

---

# Persistent Storage

Do not assume an ECS/Fargate container filesystem is durable.

If the service requires a LanceDB directory too large or inappropriate to
bake into the image, inspect the authoritative deployment design for:

- EFS
- S3 sync-to-ephemeral storage
- baked image layer
- another approved mechanism

Do not invent a storage architecture if the roadmap already froze one.

If no artifact-delivery mechanism is defined and the full-corpus index is too
large to package sensibly:

STOP AND ASK.

Do not redesign LanceDB persistence inside Task 4.11 without authorization.

---

# Model Cache

Avoid runtime downloads from Hugging Face unless explicitly approved.

The service should not become unready because a fresh task unexpectedly
downloads model files from the Internet.

Prefer an explicitly versioned/pre-staged model asset strategy consistent
with the repository's existing revision pinning.

If model files are baked into the image, document image-size implications.

If model files live on mounted storage, verify exact revision identity at
startup where practical.

Do not resolve "latest" at deployment time.

---

# Secrets

Provider secrets must remain external to Git and image layers.

Use the mechanism required by the roadmap, e.g. AWS Secrets Manager or SSM
Parameter Store if AWS deployment is specified.

Do not hard-code:

```text
OPENROUTER_API_KEY
AWS access keys
database passwords
tokens
```

into:

- Dockerfile
- ECS task definition committed to Git
- Terraform variables committed with values
- shell scripts
- `.env.example`

If using ECS secrets injection, keep only secret identifiers/ARN references
in infrastructure definitions where appropriate.

Do not print secret values during deployment diagnostics.

---

# IAM

If AWS is the target, apply least privilege.

Separate where appropriate:

```text
task execution role
application task role
deployment/user role
```

Do not grant broad `AdministratorAccess` in committed infrastructure.

Only permit runtime access actually required for:

- pulling image
- writing logs
- reading approved secrets
- reading approved artifact storage

Do not give the application permission to mutate frozen corpus artifacts
unless required.

If exact IAM resources are unavailable, parameterize rather than inventing
real ARNs.

---

# Networking

Follow the authoritative roadmap.

Do not guess public/private topology.

If a load balancer is required:

- health checks must use the frozen health endpoint,
- do not use `/query` as a health check,
- configure a realistic startup grace period for heavyweight initialization,
- readiness should reflect dependency initialization.

If no load balancer is required for the task, do not add one merely because
it is common.

Do not expose debug/admin ports.

---

# Health and Status

Task 4.10 defined:

```text
GET /health
GET /status
```

Preserve their semantics.

Container orchestrator health checks should be lightweight.

Do not make the orchestrator's health check execute:

- full-corpus search,
- XBRL query,
- model generation,
- OpenRouter request.

If `/status` reflects readiness/dependencies, use it only if its semantics
match the target orchestrator's readiness expectations.

Do not change endpoint semantics solely for ECS convenience without updating
Task 4.10's documented contract and tests.

---

# Startup Validation

At process startup or deployment smoke time, validate only cheap, meaningful
runtime invariants required by the frozen architecture.

Examples:

```text
required artifact path exists
index/table opens
expected table name exists
embedding model/revision matches expected configuration
XBRL serving artifact exists
config loads
provider configuration is syntactically present
```

Do not run a paid provider call during startup.

Do not scan all 10.49M vectors at startup.

If a failure occurs, fail readiness clearly rather than accepting requests
with half-initialized state.

---

# Infrastructure as Code

Use the repository's chosen infrastructure tool if one already exists.

If `infra/` is still empty and the roadmap mandates a specific choice, follow
it.

If the roadmap merely says "deploy to Fargate" but does not choose between:

```text
Terraform
CloudFormation
AWS CDK
raw AWS CLI
```

STOP AND ASK before committing to a long-lived IaC technology.

Do not create multiple competing implementations.

Whatever approach is selected must be:

- parameterized,
- reproducible,
- documented,
- secret-free,
- reviewable before apply.

---

# Local Container Validation

Before any cloud deployment, if Docker is available:

1. build the image,
2. run it locally with safe/fake configuration where possible,
3. check `/health`,
4. check `/status`,
5. issue a synthetic `/query` using a fake provider or the approved
   non-paid route,
6. stop the container,
7. verify no host artifact mutation.

If Docker daemon is unavailable:

- do not falsely mark container validation PASS,
- report the limitation,
- continue only if the authoritative task permits validation another way.

Do not install Docker or alter system virtualization settings without
authorization.

---

# Deployment Smoke

If explicit cloud deployment is authorized and completed, validate:

```text
task/container reaches RUNNING/healthy
health endpoint responds
status endpoint reflects ready state
one non-paid safe query path works
logs appear in the expected sink
restart/rollout behavior works
```

If the only route that proves end-to-end functionality would incur a paid
OpenRouter call, ask before doing it.

A structured XBRL query may be a preferable non-paid end-to-end deployed
smoke if it exercises the live API without generation and is supported by
the deployed service.

Do not use protected TEST.

---

# Rollback

Deployment must have a safe rollback story.

At minimum document:

- previous image/task-definition revision,
- how to revert,
- how failed health checks prevent/undo rollout if the platform supports it.

If the task performs a real mutable deployment, record the deployed revision
or image digest.

Do not automatically delete old working revisions needed for rollback.

---

# Observability

Use existing application logging.

If AWS/Fargate is the target and CloudWatch is required, configure the
standard log sink without changing the application's structured logging
contract.

Do not log:

- secrets
- raw Authorization headers
- full prompts
- full retrieved evidence
- full generated answers
- vectors

Capture useful deployment metadata such as:

```text
service revision
image digest
task/container start
health transition
route/status
latency
reason_code
```

only where already safe under Task 4.10's logging contract.

Do not build a full observability stack unless the roadmap requires it.

---

# Cost Safety

Cloud deployment can create ongoing cost.

If real infrastructure is created:

- identify billable resources,
- record desired count,
- record whether service is intentionally left running,
- provide teardown commands,
- do not create autoscaling/minimum-capacity settings that exceed the
  authorized scope.

Do not estimate an exact dollar amount unless based on verified current
pricing and the user asked for it.

Do not leave accidental test resources running.

If the roadmap requires a continuously warm service, explicitly record that
it is expected to incur ongoing compute cost.

---

# No Scientific Claims From Deployment Metrics

Deployment timings are operational diagnostics, not retrieval-quality
metrics.

Do not reopen DEV.
Do not open TEST.
Do not change the selected scientific stack based on a single cloud latency
observation unless a later roadmap task explicitly owns such reconsideration.

Record:

```text
container startup time
readiness time
health status
endpoint latency
```

only as deployment measurements.

Do not call them model-quality improvements.

---

# Tests

Add portable tests for deployment helpers/configuration where practical.

Potential areas:

- Docker/IaC templates contain no secrets
- required env names are represented without values
- container command targets the app factory
- health path is correct
- deployment config serialization deterministic
- resource names parameterized
- development-index vs production-index mode cannot be mislabeled
- dangerous absolute Windows paths not embedded
- IaC does not include broad wildcard IAM unless explicitly justified
- deployment helper dry-run produces expected commands
- no protected TEST references

Do not make portable pytest depend on Docker, AWS credentials, or network.

Cloud integration tests must be separately marked and opt-in if introduced.

Do not add any default test that creates cloud resources.

---

# Developer Commands

If useful and consistent with repository conventions, add deployment-oriented
developer commands such as:

```text
python scripts/dev.py api
python scripts/dev.py container-check
```

only if Task 4.11 requires them.

Do not overload `scripts/dev.py test` with cloud access.

Do not let `doctor` mutate infrastructure.

---

# Documentation

Create a deployment document consistent with current Phase 4 docs, likely:

`project_plan/PHASE4_DEPLOYMENT.md`

Document:

- exact Task 4.11 roadmap checklist
- deployment mode actually achieved
- target environment
- known Task 4.10 dev-index limitation
- container strategy
- artifact strategy
- model strategy
- secrets strategy
- IAM/networking
- health/readiness
- logs
- deployment commands
- rollback
- teardown
- cost-bearing resources
- test/smoke results
- known limitations
- whether cloud resources were actually created

Do not write "deployed" if only deployment code was prepared.

Update `project_plan/REPOSITORY_STRUCTURE.md`,
`project_plan/CONFIGURATION.md`,
`project_plan/DEVELOPER_COMMANDS.md`,
and other docs only where implementation actually changes them.

---

# Results Artifact

Write a small tracked summary following repository conventions, likely:

`results/phase_4_11_deployment_summary.json`

Use the actual naming pattern if different.

Include:

```text
task
status
deployment_mode
target
container_image/build identity
image digest if available
artifact mode: development-index-smoke OR full-production
dense index identity
structured serving artifact identity
health/status validation
cloud resources created: yes/no
deployment revision if applicable
paid generation API calls during Task 4.11
protected TEST usage
tests
known limitations
rollback/teardown status
files modified
```

Do not include:

- secrets
- credentials
- account tokens
- raw user questions
- provider responses
- private keys

---

# Progress.md

Only after the authoritative Task 4.11 acceptance criteria pass, append a
detailed Task 4.11 entry.

Record:

- objective
- exact roadmap scope
- whether this was local deployability validation or real cloud deployment
- target
- app/container/IaC implementation
- artifact delivery approach
- **development dense index vs full-production index status**
- secrets mechanism
- health/status behavior
- validation performed
- cloud resources created
- image/task revision
- rollback/teardown
- paid API calls during Task 4.11
- protected TEST usage = 0/3
- test counts
- known limitations
- Git commit
- final status
- exact next roadmap task from `PROJECT_EXECUTION.md`

Do not guess the next task.

Do not start it.

---

# Regression Gates

Before and after Task 4.11 verify:

- Task 4.1 normalization artifact unchanged
- Task 4.2 chunk artifact unchanged
- Task 4.3 embedding artifact unchanged
- Task 4.4 vector index unchanged
- Task 4.5 XBRL serving artifact unchanged
- Task 4.6 generation-provider semantics unchanged
- Task 4.7 input guard semantics unchanged
- Task 4.8 context guard semantics unchanged
- Task 4.9 output guard semantics unchanged
- Task 4.10 HTTP contract unchanged unless authoritative deployment work
  explicitly requires a minimal configuration-only adjustment
- CRAG threshold remains `0.5531`
- dense-only selection remains frozen
- no BM25/RRF reintroduced
- no reranker reintroduced
- no re-embedding
- no provider/model change
- protected TEST unopened

Run:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

If deployment-specific opt-in tests are introduced, run them only when the
required environment is explicitly available and authorized.

Do not run a test merely because AWS/OpenRouter credentials happen to be
present.

---

# Git Safety

Follow `project_plan/GIT_CONVENTIONS.md`.

Before committing:

```text
git status
git diff
git diff --staged
```

Verify:

- no `data/` content staged
- no `artifacts/` content staged
- no model weights staged unless the repository explicitly chose tracked
  model packaging, which would be unusual and must be justified
- no `.env` staged
- no AWS credentials staged
- no OpenRouter key staged
- no account-specific secret values staged
- no local absolute Windows paths in portable deployment definitions
- no Docker build caches staged
- no generated Terraform state staged
- no `.terraform/` staged
- no cloud credentials/cache staged

If Terraform is selected, ensure at minimum:

```text
.terraform/
*.tfstate
*.tfstate.*
```

are ignored.

Commit Task 4.11 as one coherent commit only after its acceptance gate passes.

Suggested commit message:

`Add production deployment configuration`

If a real deploy happened, the commit message still describes repository
changes; do not encode ephemeral resource IDs into the message.

Do not push unless current repository/user policy explicitly authorizes it.

---

# Stop Conditions

STOP and report rather than guessing if:

1. Task 4.10 is not actually complete.
2. `PROJECT_EXECUTION.md` defines Task 4.11 materially differently.
3. The roadmap expects full-production dense serving but no full-corpus
   retriever/schema adapter exists.
4. The only available API service still uses the Phase 1 development index
   and the task expects a production deployment claim.
5. The deployment cloud/provider/region is required but unspecified.
6. The infrastructure-as-code tool is a material long-lived decision and
   unspecified.
7. CPU vs GPU serving strategy is unresolved and materially affects the
   image/target.
8. Required artifact-delivery/persistent-storage strategy is unresolved.
9. Real cloud provisioning would incur cost but explicit authorization is
   absent.
10. Required secrets source is unspecified.
11. A paid OpenRouter call would be required for validation without explicit
    authorization.
12. Protected TEST access would be required.
13. Deployment would require changing frozen routing/retrieval/guardrail
    semantics.
14. Regression tests fail for an unexplained reason.
15. Git/secret safety cannot be established.

When stopping, report:

```text
TASK:
STEP:
EXPECTED:
OBSERVED:
WHY BLOCKING:
SAFE STATE:
DECISION NEEDED:
```

Do not mark Task 4.11 complete.

---

# Acceptance Criteria

Task 4.11 is COMPLETE only when the authoritative roadmap criteria pass and,
at minimum:

- deployment scope is explicitly identified
- current Task 4.10 application contract is preserved
- deployment does not hide the dev-index/full-production-index distinction
- target environment matches the frozen serving decision unless the roadmap
  explicitly changes it
- container/runtime strategy is reproducible
- required artifacts have an explicit delivery/mount strategy
- model revision/configuration remains pinned
- secrets are external to Git/image
- health/readiness behavior works in the target runtime
- application dependencies are not recreated per request
- deployment validation does not use protected TEST
- paid generation calls are zero unless separately and explicitly authorized
- rollback/teardown instructions exist for any real cloud deployment
- billable resources are identified if created
- portable regression suite still passes
- Tasks 4.1–4.10 remain intact
- documentation and result summary are written
- Progress.md is updated honestly
- one coherent Task 4.11 commit is created

If only deployment code/local container validation is completed but the
authoritative roadmap requires a real live cloud deployment, record the task
as BLOCKED / PARTIAL rather than COMPLETE.

If a dev-index-backed infrastructure smoke is permitted, state that exact
limitation prominently.

Then, and only then, record:

`Task 4.11 — Deployment — COMPLETE`

and identify the exact next roadmap task from
`project_plan/PROJECT_EXECUTION.md`.

Do not start the next task.
