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

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for application data"
  type        = string
}

variable "artifact_bucket_name" {
  description = "Name of the S3 bucket for pipeline artifacts"
  type        = string
}

variable "alb_security_group_id" {
  description = "Security group ID of the ALB (optional, for allowing ALB traffic to ECS)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
