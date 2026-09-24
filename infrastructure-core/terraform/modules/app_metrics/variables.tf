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

variable "metrics_url" {
  description = "URL of the Prometheus metrics endpoint to scrape"
  type        = string
}

variable "lambda_role_arn" {
  description = "IAM role ARN for the metrics collector Lambda"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
