# Project Configuration
project_name = "photogear"
environment  = "production"
region       = "eu-north-1"

# Networking Configuration
vpc_cidr             = "10.0.0.0/16"
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.20.0/24"]
enable_nat_gateway   = true

# Database Configuration
postgres_version        = "17"
db_instance_class       = "db.t3.micro"
db_allocated_storage    = 20
db_name                 = "photogear"
db_username             = "photogear"
db_multi_az             = false
db_deletion_protection  = true
db_skip_final_snapshot  = false

# Cache Configuration
redis_version        = "7.0"
redis_node_type      = "cache.t3.micro"
redis_num_cache_nodes = 1

# ECS Configuration
ecs_task_cpu       = "2048"  # 2 vCPU
ecs_task_memory    = "5120"  # 5 GB
ecs_desired_count  = 1

# Celery Worker Configuration
celery_worker_cpu           = "2048"  # 2 vCPU
celery_worker_memory        = "4096"  # 4 GB
celery_worker_desired_count = 1

# Load Balancer Configuration
# alb_certificate_arn = "arn:aws:acm:eu-north-1:897751977737:certificate/36e8a463-8380-4d06-8f65-17fd5ec18ed8"
alb_certificate_arn = "arn:aws:acm:eu-north-1:897751977737:certificate/f3381c75-89ad-4ec1-89dd-ac41b8a3e5d8"

# Domain Configuration
frontend_domain          = "app-photogear.sensifai.com"
frontend_certificate_arn = "arn:aws:acm:us-east-1:897751977737:certificate/4d3f6738-80a5-4012-9a9c-50fcb876b6ad"
api_domain               = "api-photogear.sensifai.com"

# GPU Instance Configuration
enable_gpu_instance  = true
gpu_instance_type    = "g4dn.2xlarge"
gpu_ami_id           = "ami-05763e02cb3b90145"
gpu_root_volume_size = 100
gpu_ssh_key_name     = "mbp"

# Additional Tags (optional)
tags = {
  Owner       = "DevOps Team"
  CostCenter  = "Engineering"
  Application = "PhotoGear Backend"
}
