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

variable "private_subnet_ids" {
  description = "List of private subnet IDs for EFS mount targets"
  type        = list(string)
}

variable "ecs_tasks_sg_id" {
  description = "Security group ID of ECS tasks (for EFS access)"
  type        = string
}

variable "efs_performance_mode" {
  description = "Performance mode for EFS (generalPurpose or maxIO)"
  type        = string
  default     = "generalPurpose"
}

variable "efs_throughput_mode" {
  description = "Throughput mode for EFS (bursting or provisioned)"
  type        = string
  default     = "bursting"
}

variable "queue_visibility_timeout" {
  description = "Visibility timeout for SQS queues in seconds"
  type        = number
  default     = 300
}

variable "queue_message_retention" {
  description = "Message retention period for SQS queues in seconds"
  type        = number
  default     = 1209600
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# GPU EC2 Instance Variables
variable "enable_gpu_instance" {
  description = "Enable GPU EC2 instance for AI/ML workloads"
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  description = "Instance type for GPU EC2 instance"
  type        = string
  default     = "g4dn.2xlarge"
}

variable "gpu_ami_id" {
  description = "AMI ID for GPU EC2 instance (Ubuntu Deep Learning AMI)"
  type        = string
  default     = "ami-05763e02cb3b90145"
}

variable "gpu_root_volume_size" {
  description = "Root volume size in GB for GPU EC2 instance"
  type        = number
  default     = 100
}

variable "gpu_ssh_key_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
  default     = null
}

variable "gpu_ssh_allowed_cidr" {
  description = "CIDR block allowed to SSH to GPU instance"
  type        = string
  default     = "0.0.0.0/0"
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for GPU instance placement"
  type        = list(string)
  default     = []
}

variable "app_data_bucket_arn" {
  description = "ARN of the application data S3 bucket"
  type        = string
  default     = ""
}
