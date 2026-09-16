# Task 4.11 - Terraform skeleton (NOT APPLIED)

Status: **prepared, not provisioned**. No real AWS resource has been
created from this directory. `terraform apply` has never been run against
it. This is deliberate - see `project_plan/PHASE4_DEPLOYMENT.md` for the
full account of why real cloud provisioning was deferred for Task 4.11
(no AWS account/region/VPC/budget was specified, no live AWS credentials
were available in the working session, and the roadmap's own "if short on
time" clause explicitly allows deferring deployment with a documented
design).

## What this is

A parameterized starting point for the eventual real deployment, matching
the frozen Phase 4 serving decision (continuously-warm CPU Fargate,
`project_plan/SERVING_FEASIBILITY.md`). It defines the shape of the
resources a real deployment would need - it does not name any real
account, region, VPC, subnet, or ARN. Every account-specific value is an
unfilled Terraform variable (`variables.tf`) with no default where a real
value is required.

## What this is not

- Not applied. `terraform plan`/`terraform apply` have not been run.
- Not a complete deployment. No ALB, no autoscaling policy, no CI/CD
  wiring, no artifact-delivery mechanism (EFS/S3) for the full-corpus
  index is defined here - those are real, separate decisions this task
  explicitly deferred (see PHASE4_DEPLOYMENT.md's "Open decisions before
  a real deploy" section).
- Not a claim that Terraform state exists anywhere. `.terraform/` and
  `*.tfstate*` are gitignored (see repo-root `.gitignore`) and nothing of
  that shape has ever been generated.

## Before this can actually be applied

At minimum, someone with authority over the target AWS account must
supply (see PHASE4_DEPLOYMENT.md for the full list):

- AWS account id and region
- VPC id and subnet ids (public vs private topology decision)
- ECR repository name (or authorization to create one)
- ECS cluster name (or authorization to create one)
- secrets source (AWS Secrets Manager vs SSM Parameter Store) and the
  actual secret ARN for `OPENROUTER_API_KEY`
- desired task count, CPU units, memory
- artifact-delivery mechanism for the dev/full dense index and
  `xbrl.duckdb` (EFS is the most likely candidate given this task's local
  validation found Windows-host bind-mounts unsuitable for DuckDB's
  memory-mapped access pattern - see PHASE4_DEPLOYMENT.md)
- explicit authorization for the ongoing cost of a continuously-warm
  Fargate service

## Files

- `variables.tf` - every input this configuration needs, no invented
  defaults for account-specific values.
- `main.tf` - ECR repository, ECS cluster/task-definition/service shape
  only, CPU-only Fargate, referencing `var.*` throughout. No hardcoded
  ARNs, account IDs, or regions.
