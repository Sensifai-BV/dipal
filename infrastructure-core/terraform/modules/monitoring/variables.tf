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

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the backend ECS service"
  type        = string
}

variable "celery_worker_service_name" {
  description = "Name of the Celery worker ECS service"
  type        = string
}

variable "db_instance_id" {
  description = "ID of the RDS instance"
  type        = string
}

variable "redis_id" {
  description = "ID of the Redis replication group"
  type        = string
}

variable "alb_arn_suffix" {
  description = "ARN suffix of the Application Load Balancer"
  type        = string
}

variable "target_group_arn_suffix" {
  description = "ARN suffix of the ALB target group"
  type        = string
}

variable "efs_id" {
  description = "ID of the EFS file system"
  type        = string
}

variable "sqs_queue_names" {
  description = "List of SQS queue names to monitor"
  type = list(object({
    name  = string
    label = string
  }))
  default = []
}

variable "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  type        = string
}

variable "nat_gateway_ids" {
  description = "List of NAT Gateway IDs"
  type        = list(string)
  default     = []
}

variable "ai_ecs_service_names" {
  description = "List of AI ECS service names to monitor"
  type        = list(string)
  default     = []
}

variable "gpu_instance_id" {
  description = "ID of the GPU EC2 instance"
  type        = string
  default     = null
}

variable "enable_gpu_instance" {
  description = "Whether the GPU EC2 instance is enabled"
  type        = bool
  default     = false
}

variable "gpu_name" {
  description = "GPU device name as reported by nvidia-smi (e.g., Tesla T4)"
  type        = string
  default     = "Tesla T4"
}

variable "gpu_index" {
  description = "GPU device index"
  type        = string
  default     = "0"
}

variable "gpu_arch" {
  description = "GPU architecture as reported by nvidia-smi (e.g., Turing)"
  type        = string
  default     = "Turing"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
