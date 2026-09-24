variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "photogear"
}

variable "environment" {
  description = "Environment name (e.g., production, staging)"
  type        = string
  default     = "production"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT Gateway for private subnets"
  type        = bool
  default     = true
}

# Database variables
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "17.7"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "photogear"
}

variable "db_username" {
  description = "Master username for the database"
  type        = string
  default     = "photogear"
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment for RDS"
  type        = bool
  default     = false
}

variable "db_deletion_protection" {
  description = "Enable deletion protection for RDS"
  type        = bool
  default     = true
}

variable "db_skip_final_snapshot" {
  description = "Skip final snapshot on RDS deletion"
  type        = bool
  default     = false
}

# Cache variables
variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7.1"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 1
}

# ECS variables
variable "ecs_task_cpu" {
  description = "CPU units for ECS task (2 vCPU = 2048)"
  type        = string
  default     = "2048"
}

variable "ecs_task_memory" {
  description = "Memory for ECS task in MB (5 GB = 5120 MB)"
  type        = string
  default     = "5120"
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

# Celery Worker variables
variable "celery_worker_cpu" {
  description = "CPU units for Celery worker (2 vCPU = 2048)"
  type        = string
  default     = "2048"
}

variable "celery_worker_memory" {
  description = "Memory for Celery worker in MB (4 GB = 4096 MB)"
  type        = string
  default     = "4096"
}

variable "celery_worker_desired_count" {
  description = "Number of Celery workers"
  type        = number
  default     = 1
}

# Load Balancer variables
variable "alb_health_check_path" {
  description = "Health check path for ALB target group"
  type        = string
  default     = "/"
}

variable "alb_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS (optional)"
  type        = string
  default     = null
}

variable "alb_deletion_protection" {
  description = "Enable deletion protection for the ALB"
  type        = bool
  default     = false
}

# GPU Instance Variables
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

# Domain Configuration
variable "frontend_domain" {
  description = "Custom domain for the frontend CloudFront distribution (e.g. app.example.com)"
  type        = string
  default     = null
}

variable "frontend_certificate_arn" {
  description = "ARN of ACM certificate for frontend domain (must be in us-east-1)"
  type        = string
  default     = null
}

variable "api_domain" {
  description = "Custom domain for the backend API (e.g. api.example.com)"
  type        = string
  default     = null
}

# Tags
variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
