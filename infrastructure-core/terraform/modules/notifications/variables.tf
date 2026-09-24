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

variable "backend_pipeline_name" {
  description = "Name of the backend CodePipeline"
  type        = string
}

variable "frontend_pipeline_name" {
  description = "Name of the frontend CodePipeline"
  type        = string
}

variable "backend_build_project" {
  description = "Name of the backend CodeBuild project"
  type        = string
}

variable "frontend_build_project" {
  description = "Name of the frontend CodeBuild project"
  type        = string
}

variable "telegram_lambda_role_arn" {
  description = "ARN of Lambda execution role for Telegram notifier"
  type        = string
}

variable "telegram_secret_arn" {
  description = "ARN of Secrets Manager secret containing Telegram credentials"
  type        = string
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}
