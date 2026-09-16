# Task 4.11 - every account-specific input this configuration needs.
# Deliberately NO defaults for anything account-specific - Terraform will
# refuse to plan/apply without them being supplied explicitly, rather than
# silently guessing a real account/region/ARN. See ./README.md.

variable "aws_region" {
  description = "Target AWS region for the deployed service. Not defaulted - must be supplied explicitly."
  type        = string
}

variable "environment_name" {
  description = "Short deployment environment label (e.g. \"prod\", \"staging\"), used to namespace resource names."
  type        = string
  default     = "prod"
}

variable "vpc_id" {
  description = "VPC to deploy the ECS service into."
  type        = string
}

variable "subnet_ids" {
  description = "Subnet ids for the Fargate service's network configuration (public vs private topology is an explicit decision made outside this file)."
  type        = list(string)
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository the deployment image is pushed to."
  type        = string
  default     = "sec-rag-api"
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster the service runs in."
  type        = string
}

variable "task_cpu" {
  description = "Fargate task CPU units. Frozen Phase 4 decision is CPU-only serving (project_plan/SERVING_FEASIBILITY.md) - no GPU task definition is defined here."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory (MiB). Sized for the CPU embedding model + dependency footprint measured during Task 4.11's local container validation, not for holding the full-corpus index in memory."
  type        = number
  default     = 4096
}

variable "desired_task_count" {
  description = "Number of running tasks. Defaults to 1 - this task never authorized an autoscaling policy or a multi-instance throughput claim."
  type        = number
  default     = 1
}

variable "container_image" {
  description = "Full image reference (repository URL + tag or digest) to deploy. Supplied by the CI/CD or deploy step that pushes to ECR - never hardcoded here."
  type        = string
}

variable "openrouter_api_key_secret_arn" {
  description = "ARN of the Secrets Manager secret (or SSM Parameter Store parameter) holding OPENROUTER_API_KEY. The key value itself is never a Terraform variable."
  type        = string
}

variable "generation_provider" {
  description = "Frozen Task 4.6 production generation provider."
  type        = string
  default     = "openrouter"
}

variable "generation_model" {
  description = "Frozen Task 4.6 production generation model."
  type        = string
  default     = "openai/gpt-oss-20b"
}

variable "task_execution_role_arn" {
  description = "IAM role ARN ECS uses to pull the image, write logs, and read the secret above. Least-privilege, separate from the application task role below."
  type        = string
}

variable "task_role_arn" {
  description = "IAM role ARN the running application container assumes. Must not have write access to frozen corpus artifacts."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the service's stdout/stderr (console-only structured logging, project_plan/LOGGING.md)."
  type        = number
  default     = 30
}
