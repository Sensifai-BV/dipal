variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., production, staging)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "artifacts_bucket_id" {
  description = "ID of the S3 bucket for pipeline artifacts"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository"
  type        = string
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service"
  type        = string
}

variable "ecs_task_family" {
  description = "Family of the ECS task definition"
  type        = string
}

variable "celery_worker_service_name" {
  description = "Name of the Celery worker ECS service"
  type        = string
}

variable "celery_worker_task_family" {
  description = "Family of the Celery worker task definition"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of Lambda execution role"
  type        = string
}

variable "codebuild_role_arn" {
  description = "ARN of CodeBuild role"
  type        = string
}

variable "codepipeline_role_arn" {
  description = "ARN of CodePipeline role"
  type        = string
}

variable "telegram_lambda_arn" {
  description = "ARN of Telegram notifier Lambda (optional)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
