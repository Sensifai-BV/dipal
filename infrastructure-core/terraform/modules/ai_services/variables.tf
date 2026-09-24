variable "project_name" {
  description = "Project name"
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

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS services"
  type        = list(string)
}

variable "ecs_cluster_id" {
  description = "ECS cluster ID"
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "efs_id" {
  description = "EFS filesystem ID for shared storage"
  type        = string
}

variable "efs_arn" {
  description = "EFS filesystem ARN"
  type        = string
}

variable "efs_security_group_id" {
  description = "EFS security group ID"
  type        = string
}

variable "ai_dev_bucket_name" {
  description = "AI development S3 bucket name"
  type        = string
}

variable "ai_dev_bucket_arn" {
  description = "AI development S3 bucket ARN"
  type        = string
}

variable "app_data_bucket_name" {
  description = "Application data S3 bucket name"
  type        = string
}

variable "app_data_bucket_arn" {
  description = "Application data S3 bucket ARN"
  type        = string
}

variable "calibration_queue_arn" {
  description = "SQS calibration queue ARN"
  type        = string
}

variable "sfm_queue_arn" {
  description = "SQS SFM queue ARN"
  type        = string
}

variable "orthomosaic_queue_arn" {
  description = "SQS orthomosaic queue ARN"
  type        = string
}

variable "calibration_dlq_arn" {
  description = "SQS calibration DLQ ARN"
  type        = string
}

variable "sfm_dlq_arn" {
  description = "SQS SFM DLQ ARN"
  type        = string
}

variable "orthomosaic_dlq_arn" {
  description = "SQS orthomosaic DLQ ARN"
  type        = string
}

variable "calibration_queue_name" {
  description = "SQS calibration queue name"
  type        = string
}

variable "orthomosaic_queue_name" {
  description = "SQS orthomosaic queue name"
  type        = string
}

variable "sfm_queue_name" {
  description = "SQS SFM queue name"
  type        = string
}

# Service sizing
variable "api_gateway_cpu" {
  description = "CPU units for API Gateway task"
  type        = string
  default     = "1024"
}

variable "api_gateway_memory" {
  description = "Memory (MB) for API Gateway task"
  type        = string
  default     = "2048"
}

variable "calibration_cpu" {
  description = "CPU units for Calibration task"
  type        = string
  default     = "1024"
}

variable "calibration_memory" {
  description = "Memory (MB) for Calibration task"
  type        = string
  default     = "2048"
}

variable "orthomosaic_cpu" {
  description = "CPU units for Orthomosaic task"
  type        = string
  default     = "2048"
}

variable "orthomosaic_memory" {
  description = "Memory (MB) for Orthomosaic task"
  type        = string
  default     = "4096"
}

variable "sfm_instance_type" {
  description = "EC2 instance type for SFM Batch compute"
  type        = string
  default     = "g4dn.xlarge"
}

variable "sfm_vcpus" {
  description = "vCPUs for SFM Batch job"
  type        = number
  default     = 4
}

variable "sfm_memory" {
  description = "Memory (MB) for SFM Batch job"
  type        = number
  default     = 15360
}

variable "tags" {
  description = "Common tags"
  type        = map(string)
  default     = {}
}
