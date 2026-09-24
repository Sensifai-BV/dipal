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

variable "private_subnet_ids" {
  description = "List of private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of ECS task execution role"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of ECS task role"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the ECR repository"
  type        = string
}

variable "db_password_secret_arn" {
  description = "ARN of the secret containing database password"
  type        = string
}

variable "task_cpu" {
  description = "CPU units for ECS task"
  type        = string
  default     = "256"
}

variable "task_memory" {
  description = "Memory for ECS task in MB"
  type        = string
  default     = "512"
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "target_group_arn" {
  description = "ARN of the target group (optional, for ALB integration)"
  type        = string
  default     = null
}

variable "alb_listener_arn" {
  description = "ARN of the ALB listener (optional, for dependency management)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "celery_worker_cpu" {
  description = "CPU units for Celery worker task"
  type        = string
  default     = "512"
}

variable "celery_worker_memory" {
  description = "Memory for Celery worker task (MB)"
  type        = string
  default     = "1024"
}

variable "celery_worker_desired_count" {
  description = "Number of Celery worker tasks to run"
  type        = number
  default     = 1
}
