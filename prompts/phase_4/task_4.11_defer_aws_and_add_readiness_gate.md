# Task 4.11 — Defer AWS Deployment and Add a Pre-Deployment Local Readiness Gate

## Objective

Update the project documentation to reflect a new explicit user decision:

> AWS hosting is intentionally deferred until the Production RAG application
> is locally production-ready, fully integrated with the full-corpus artifacts,
> thoroughly tested, performance/reliability validated, and frozen as a release
> candidate.

This is a **documentation / roadmap amendment only**.

Do NOT implement the production retriever in this task.
Do NOT modify FastAPI code.
Do NOT provision AWS resources.
Do NOT push to ECR.
Do NOT run `terraform apply`.
Do NOT open protected TEST.
Do NOT make paid generation/API calls.
Do NOT rewrite completed historical task entries.

Modify only the minimum required documentation:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`

If a tiny cross-reference update in another planning document is absolutely
required for consistency, STOP and report it first rather than broadening scope
silently.

---

# Repository Root

`C:\Om\Codes\RAG`

Before editing, read both target files completely enough to understand their
current Phase 4 structure and preserve established terminology/style:

- `Progress.md`
- `project_plan/PROJECT_EXECUTION.md`

Also inspect:

```text
git status
git log --oneline --decorate -10
```

Do not trust this prompt over the repository if exact wording/status has changed.
The purpose of this task is to amend the **current** roadmap without destroying
historical provenance.

---

# Current Verified State to Preserve

The following historical state must remain intact:

```text
Task 4.1  Full-corpus normalization               COMPLETE
Task 4.2  Full-corpus chunking                    COMPLETE
Task 4.3  Full-corpus embedding                   COMPLETE
Task 4.4  Full-corpus vector index                COMPLETE
Task 4.5  XBRL serving representation             COMPLETE
Task 4.6  Generation production interface         COMPLETE
Task 4.7  Input guardrails                        COMPLETE
Task 4.8  Context guardrails                      COMPLETE
Task 4.9  Output guardrails                       COMPLETE
Task 4.10 FastAPI service                         COMPLETE
Task 4.11 Deployment                              PARTIAL / DEFERRED
```

Do not renumber or rewrite Tasks 4.1-4.10.

Do not claim Task 4.11 is complete.

---

# Existing Task 4.10 Production Gap — Must Remain Explicit

The current FastAPI service has a known, already-documented dense-route gap:

```text
Phase 1 development dense index:
  162,357 rows
  BAAI/bge-small-en-v1.5
  development schema

Task 4.4 production dense index:
  10,487,096 rows
  Qwen/Qwen3-Embedding-0.6B
  1024-dimensional vectors
  production chunk schema
  canonical identity uses chunk_uid
```

The existing `BaselineRetriever` / `RetrievalResult` contract is tied to the
Phase 1 development schema and is not directly compatible with the Task 4.4
production index.

Task 4.10 therefore intentionally used the 162,357-row development index rather
than pretending the full-corpus index was already integrated.

This gap is now the highest-priority local production issue and must be resolved
before final AWS deployment.

Do not soften, hide, or re-label this limitation.

---

# Task 4.11 Work Already Completed — Preserve It

Task 4.11 deployment preparation has already produced useful verified work.
Preserve that work and its commit/history.

The documentation should clearly distinguish:

```text
Deployment preparation:
  COMPLETE / preserved

Real AWS hosting:
  DEFERRED BY USER DECISION
```

Existing preparation includes, as supported by the current repository:

- production CPU-container work,
- local Docker validation,
- Terraform/ECS/Fargate preparation,
- deployment documentation/results already committed,
- no real AWS runtime infrastructure provisioned as part of the completed prep.

Do not delete the Docker/Terraform preparation merely because deployment is
being postponed.

Do not rewrite the prior Task 4.11 preparation commit as if it never happened.

---

# New Explicit User Decision — 2026-09-17

Record this decision clearly in both roadmap state and Progress history:

```text
AWS deployment is intentionally postponed.

The project will first:

1. close remaining production integration gaps,
2. switch the API dense route from the Phase 1 development index to the
   10,487,096-row Task 4.4 production index through an explicit compatible
   production retriever/adapter,
3. validate the complete local production pipeline,
4. run regression, integration, reliability, and performance testing,
5. complete final evaluation/readiness checks,
6. clean/freeze documentation and reproducibility state,
7. freeze a local release candidate,
8. then resume Task 4.11 for real AWS deployment.
```

Reason:

```text
Do not pay for or operationalize cloud infrastructure while known
application-level production gaps remain.
```

This is a sequencing decision, not abandonment of AWS.

The intended final deployment target remains the already-selected AWS
Fargate / continuously-warm direction unless a later explicit decision changes
it.

---

# PROJECT_EXECUTION.md Amendment

Amend the authoritative execution plan **without renumbering completed tasks**
and without inventing fake historical tasks.

Keep the existing Task 4.11 title/identity as the AWS deployment task.

Do NOT move old completed work into newly numbered fake tasks.

Instead, insert a clearly labeled gate immediately before the live/cloud
execution portion of Task 4.11, for example:

```text
Pre-Deployment Local Production Readiness Gate
```

Use the repository's established formatting rather than mechanically copying
that exact heading if another style fits better.

The gate must make AWS deployment conditional on all of the following.

## Gate A — Full-Corpus Dense Serving Integration

Required before deployment:

- implement a production-compatible retriever/adapter for the frozen Task 4.4
  index,
- consume the 10,487,096-row production index,
- use the frozen Qwen/Qwen3-Embedding-0.6B query-embedding contract,
- preserve cosine semantics,
- preserve production provenance/citation identity,
- support required production metadata pre-filtering,
- remove the FastAPI dense route's dependency on the 162,357-row Phase 1
  development index,
- prove the API can run against the production schema without fabricating
  development-only fields.

Do not specify implementation details that have not yet been decided.

## Gate B — Local End-to-End Production Integration

Before AWS deployment, locally validate the real production composition:

```text
input guard
  -> router
  -> production dense retrieval OR structured XBRL path
  -> context guard where applicable
  -> generation where applicable
  -> output guard
  -> FastAPI response
```

Tree-navigation coverage should follow the actual frozen router capability and
roadmap; do not claim it is live if it is still not routable.

## Gate C — Regression / Integration Testing

Require a clean local regression state before deployment, including at minimum:

```text
python scripts/dev.py doctor
python scripts/dev.py test --portable
python -m pytest -m "not generation_api"
```

Also require production-index integration tests and API integration tests using
non-paid/fake generation where possible.

Live external generation must remain explicit opt-in only.

## Gate D — Reliability / Performance Validation

Require measured local validation of the production release candidate,
including whichever items are relevant under the current architecture:

- startup/readiness behavior,
- production retrieval latency,
- memory/RSS,
- repeated requests,
- bounded concurrency,
- provider failure handling,
- guardrail failure paths,
- restart/reinitialization behavior,
- no artifact mutation,
- no accidental network/paid calls in default test paths.

Do not invent numeric pass thresholds if the current roadmap has not frozen
them. If thresholds are required later, they must be explicit decisions.

## Gate E — Final Evaluation / Readiness

Before AWS deployment:

- run the final approved DEV/readiness evaluation,
- resolve material regressions rather than hiding them,
- preserve the protected TEST policy,
- do not consume protected TEST merely because deployment is approaching,
- use protected TEST only according to its existing frozen 0/3 policy and
  whatever final-evaluation task explicitly authorizes.

Current protected TEST usage remains:

`0 / 3`

## Gate F — Release-Candidate Freeze

Before cloud deployment:

- freeze the production configuration,
- freeze artifact identities/manifests,
- verify reproducible setup,
- ensure documentation accurately reflects the running system,
- produce a local release-candidate state suitable for containerization and
  deployment.

Only after Gates A-F pass should live AWS deployment resume.

---

# Final AWS Deployment Still Belongs to Task 4.11

Do not remove AWS from the roadmap.

The final sequence after the readiness gate should still include the existing
Task 4.11 deployment work, such as:

```text
final Docker image
  -> ECR
  -> Terraform apply
  -> ECS/Fargate
  -> health/status validation
  -> non-paid deployed smoke
  -> logging/restart validation
  -> deployment evidence
```

Preserve the current selected serving direction:

`AWS ECS/Fargate / continuously warm compute`

unless the existing roadmap now says otherwise.

The fact that deployment is deferred should be explicit, not ambiguous.

---

# Progress.md Amendment

Append a new dated decision/update entry.

Do NOT rewrite the historical Task 4.10 entry.

Do NOT delete or rewrite the existing Task 4.11 deployment-preparation record.

The new entry should state clearly:

## Decision

```text
User decision: defer real AWS hosting until the local project is production
ready and thoroughly validated.
```

## Why

- known full-corpus dense-serving integration gap still exists,
- deploying now would operationalize a development-index-backed dense route,
- cloud spend is unnecessary while application-level work remains,
- Docker/Terraform preparation is preserved for later reuse.

## Task 4.11 Status

Record something equivalent to:

```text
Task 4.11 — Deployment — PARTIAL / DEFERRED BY USER DECISION

Completed/preserved:
- container/deployment preparation
- local Docker validation
- Terraform/Fargate preparation

Deferred:
- ECR push for final release image
- terraform apply / live AWS infrastructure
- ECS/Fargate live service
- deployed smoke/restart/logging validation
```

Use only facts supported by the repository's actual Task 4.11 work.
Do not fabricate completion items.

## New Immediate Priority

The next active engineering priority should be recorded as:

```text
Full-corpus production dense-serving integration
```

with the purpose:

```text
make the FastAPI dense route consume the frozen 10,487,096-row Task 4.4
production index instead of the 162,357-row Phase 1 development index.
```

Do not call AWS deployment the next active task while the new readiness gate is
open.

## Phase Status

Keep Phase 4 as **IN PROGRESS**.

Do not mark Phase 4 COMPLETE.

Do not mark Task 4.11 COMPLETE.

---

# AWS Setup Note

A concise operational note may be added only if consistent with the existing
Progress style:

- AWS account access has been prepared,
- a non-root CLI/deployment identity has been configured locally,
- default deployment region selected: `us-east-1`,
- no final Production RAG ECS/Fargate service has been provisioned,
- credentials/secrets are NOT recorded in repository documentation.

Do not record:

- access key IDs,
- secret keys,
- account credentials,
- downloaded credential CSV contents,
- local credential-file contents.

This note is optional if it would clutter Progress.md; the roadmap decision is
the important part.

---

# Protected TEST

This documentation amendment must preserve:

```text
Protected TEST official usage: 0 / 3
```

Do not open or inspect protected TEST.

Do not change the TEST policy simply because deployment has moved later.

---

# No Implementation Work

This task must NOT:

- implement the production retriever,
- change `BaselineRetriever`,
- change FastAPI,
- rebuild Task 4.4,
- re-embed anything,
- change generation providers,
- run live OpenRouter calls,
- deploy AWS infrastructure,
- push images to ECR,
- run Terraform apply,
- change frozen Phase 3 scientific decisions.

This is documentation/roadmap sequencing only.

---

# Validation After Editing

After edits, verify:

1. Tasks 4.1-4.10 historical status is unchanged.
2. Task 4.11 is NOT marked complete.
3. Task 4.11 deployment preparation remains documented/preserved.
4. AWS deployment is explicitly deferred, not deleted.
5. The 162,357-row vs 10,487,096-row dense-index gap is still clearly stated.
6. `PROJECT_EXECUTION.md` requires the local readiness gate before AWS.
7. Phase 4 remains IN PROGRESS.
8. Protected TEST remains 0/3.
9. No credentials/secrets were added.
10. No source code or generated artifacts were modified.

Then inspect:

```text
git diff -- Progress.md project_plan/PROJECT_EXECUTION.md
git status --short
```

---

# Git

If and only if the documentation amendment is internally consistent and the
working tree contains no unrelated user changes, create one documentation-only
commit.

Suggested commit message:

`Defer AWS deployment until local production readiness`

Before committing, verify no unrelated files are staged.

Do not push unless explicitly authorized by the user/repository policy.

If unrelated working-tree changes exist, do not overwrite or stage them; report
them instead.

---

# Required Final Report

Report concisely:

```text
Progress.md updated: yes/no
PROJECT_EXECUTION.md updated: yes/no
Task 4.11 status:
AWS deployment status:
New pre-deployment readiness gate added: yes/no
Immediate engineering priority:
Protected TEST usage:
Files changed:
Commit hash (if committed):
Working tree status:
```

Do not start implementation of the production retriever after finishing this
documentation amendment.
