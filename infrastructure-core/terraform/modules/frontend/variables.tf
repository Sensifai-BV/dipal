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

variable "invalidation_lambda_role_arn" {
  description = "ARN of IAM role for CloudFront invalidation Lambda"
  type        = string
}

variable "domain_aliases" {
  description = "Custom domain aliases for CloudFront (e.g. app.example.com)"
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for CloudFront custom domain (must be in us-east-1)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}
