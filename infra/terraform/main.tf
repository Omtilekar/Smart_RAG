# Task 4.11 - parameterized ECS Fargate (CPU-only) shape for the Task 4.10
# FastAPI service. NOT APPLIED - see ./README.md. Every account-specific
# value comes from variables.tf; nothing here hardcodes a real account,
# region, ARN, or secret value.
#
# Deliberately does NOT define: a load balancer, an autoscaling policy, an
# artifact-delivery mechanism (EFS/S3) for the dense index / xbrl.duckdb,
# or CI/CD wiring - those are real, separate decisions this task explicitly
# deferred (project_plan/PHASE4_DEPLOYMENT.md, "Open decisions before a
# real deploy").

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_ecr_repository" "sec_rag_api" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "sec_rag_api" {
  name              = "/ecs/${var.environment_name}/${var.ecr_repository_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "sec_rag_api" {
  family                   = "${var.environment_name}-${var.ecr_repository_name}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  # CPU-only container - no GPU device requirement, matching the frozen
  # Phase 4 serving decision (project_plan/SERVING_FEASIBILITY.md).
  container_definitions = jsonencode([
    {
      name      = var.ecr_repository_name
      image     = var.container_image
      essential = true
      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]
      environment = [
        { name = "DEVICE", value = "cpu" },
        { name = "APP_ENV", value = "production" },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "GENERATION_PROVIDER", value = var.generation_provider },
        { name = "GENERATION_MODEL", value = var.generation_model },
      ]
      secrets = [
        { name = "OPENROUTER_API_KEY", valueFrom = var.openrouter_api_key_secret_arn },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.sec_rag_api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
      # /health is a lightweight liveness check only (src/api/app.py) -
      # never runs retrieval/generation. See PHASE4_DEPLOYMENT.md's
      # "Health and status" section for why this is safe as an
      # orchestrator-level check.
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

resource "aws_ecs_service" "sec_rag_api" {
  name            = "${var.environment_name}-${var.ecr_repository_name}"
  cluster         = var.ecs_cluster_name
  task_definition = aws_ecs_task_definition.sec_rag_api.arn
  desired_count   = var.desired_task_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = false
  }

  # No load balancer target group here - not defined by this task
  # (project_plan/PHASE4_DEPLOYMENT.md, "Open decisions before a real
  # deploy"). Add one only when public/private topology is decided.

  lifecycle {
    ignore_changes = [desired_count]
  }
}

output "ecr_repository_url" {
  value = aws_ecr_repository.sec_rag_api.repository_url
}

output "ecs_service_name" {
  value = aws_ecs_service.sec_rag_api.name
}
