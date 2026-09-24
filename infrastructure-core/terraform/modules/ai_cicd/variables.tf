variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
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

variable "ecr_repository_urls" {
  description = "Map of ECR repository URLs for AI services"
  type        = map(string)
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "api_gateway_service_name" {
  description = "ECS service name for AI API Gateway"
  type        = string
}

variable "calibration_service_name" {
  description = "ECS service name for Calibration"
  type        = string
}

variable "orthomosaic_service_name" {
  description = "ECS service name for Orthomosaic"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of Lambda execution role for AI webhook"
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
  description = "Common tags"
  type        = map(string)
  default     = {}
}
