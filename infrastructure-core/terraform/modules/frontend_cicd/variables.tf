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
  description = "ID of the S3 artifacts bucket"
  type        = string
}

variable "frontend_bucket_id" {
  description = "ID of the frontend S3 bucket"
  type        = string
}

variable "backend_alb_url" {
  description = "Backend ALB URL for VITE_API_BASE_URL"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of Lambda execution role"
  type        = string
}

variable "codebuild_role_arn" {
  description = "ARN of CodeBuild execution role"
  type        = string
}

variable "codepipeline_role_arn" {
  description = "ARN of CodePipeline execution role"
  type        = string
}

variable "invalidation_lambda_name" {
  description = "Name of CloudFront invalidation Lambda"
  type        = string
}

variable "invalidation_lambda_arn" {
  description = "ARN of CloudFront invalidation Lambda"
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
