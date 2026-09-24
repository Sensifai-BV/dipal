data "aws_caller_identity" "current" {}

locals {
  common_tags = merge(
    var.tags,
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  )
}

# Networking Module
module "networking" {
  source = "./modules/networking"

  project_name         = var.project_name
  environment          = var.environment
  region               = var.region
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway

  tags = local.common_tags
}

# Storage Module
module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  region       = var.region

  tags = local.common_tags
}

# Security Module
module "security" {
  source = "./modules/security"

  project_name         = var.project_name
  environment          = var.environment
  region               = var.region
  vpc_id               = module.networking.vpc_id
  s3_bucket_name       = module.storage.app_data_bucket_id
  artifact_bucket_name = module.storage.artifacts_bucket_id

  tags = local.common_tags
}

# Load Balancer Module
module "load_balancer" {
  source = "./modules/load_balancer"

  project_name               = var.project_name
  environment                = var.environment
  vpc_id                     = module.networking.vpc_id
  vpc_cidr                   = var.vpc_cidr
  public_subnet_ids          = module.networking.public_subnet_ids
  ecs_security_group_id      = module.security.ecs_tasks_sg_id
  container_port             = 8000
  health_check_path          = var.alb_health_check_path
  certificate_arn            = var.alb_certificate_arn
  enable_deletion_protection = var.alb_deletion_protection

  tags = local.common_tags

  depends_on = [module.networking, module.security]
}

# Update security module with ALB security group (using null resource for dependency)
resource "null_resource" "alb_sg_dependency" {
  depends_on = [module.load_balancer]

  triggers = {
    alb_sg_id = module.load_balancer.alb_security_group_id
  }
}

# Security group rule to allow ALB to ECS
resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = module.load_balancer.alb_security_group_id
  security_group_id        = module.security.ecs_tasks_sg_id
  description              = "Allow traffic from ALB"

  depends_on = [module.load_balancer, module.security]
}

# Database Module
module "database" {
  source = "./modules/database"

  project_name        = var.project_name
  environment         = var.environment
  private_subnet_ids  = module.networking.private_subnet_ids
  security_group_id   = module.security.rds_sg_id
  postgres_version    = var.postgres_version
  instance_class      = var.db_instance_class
  allocated_storage   = var.db_allocated_storage
  db_name             = var.db_name
  db_username         = var.db_username
  multi_az            = var.db_multi_az
  deletion_protection = var.db_deletion_protection
  skip_final_snapshot = var.db_skip_final_snapshot

  tags = local.common_tags
}

# Cache Module
module "cache" {
  source = "./modules/cache"

  project_name       = var.project_name
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.security.redis_sg_id
  redis_version      = var.redis_version
  node_type          = var.redis_node_type
  num_cache_nodes    = var.redis_num_cache_nodes

  tags = local.common_tags
}

# Create SSM Parameters for Celery URLs
resource "aws_ssm_parameter" "celery_broker_url" {
  name  = "/${var.project_name}/${var.environment}/celery-broker-url"
  type  = "String"
  value = "redis://${module.cache.redis_endpoint}:${module.cache.redis_port}/0"

  tags = local.common_tags
}

resource "aws_ssm_parameter" "celery_result_backend" {
  name  = "/${var.project_name}/${var.environment}/celery-result-backend"
  type  = "String"
  value = "redis://${module.cache.redis_endpoint}:${module.cache.redis_port}/1"

  tags = local.common_tags
}

# Create placeholder SSM Parameters (to be updated by user)
resource "aws_ssm_parameter" "allowed_hosts" {
  name  = "/${var.project_name}/${var.environment}/allowed-hosts"
  type  = "String"
  value = "localhost,127.0.0.1"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "cors_allowed_origins" {
  name  = "/${var.project_name}/${var.environment}/cors-allowed-origins"
  type  = "String"
  value = "http://localhost:3000"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# Create placeholder secrets (to be updated by user)
resource "aws_secretsmanager_secret" "secret_key" {
  name                    = "${var.project_name}/${var.environment}/secret-key"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = "CHANGE_ME_PLEASE_GENERATE_A_SECURE_SECRET_KEY"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "aws_access_key_id" {
  name                    = "${var.project_name}/${var.environment}/aws-access-key-id"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "aws_access_key_id" {
  secret_id     = aws_secretsmanager_secret.aws_access_key_id.id
  secret_string = "CHANGE_ME_AWS_ACCESS_KEY_ID"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "aws_secret_access_key" {
  name                    = "${var.project_name}/${var.environment}/aws-secret-access-key"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "aws_secret_access_key" {
  secret_id     = aws_secretsmanager_secret.aws_secret_access_key.id
  secret_string = "CHANGE_ME_AWS_SECRET_ACCESS_KEY"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "ai_service_secret_key" {
  name                    = "${var.project_name}/${var.environment}/ai-service-secret-key"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "ai_service_secret_key" {
  secret_id     = aws_secretsmanager_secret.ai_service_secret_key.id
  secret_string = "CHANGE_ME_AI_SERVICE_SECRET_KEY"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# AI Gateway Configuration
resource "aws_ssm_parameter" "ai_gateway_url" {
  name  = "/${var.project_name}/${var.environment}/ai-gateway-url"
  type  = "String"
  value = "http://10.0.1.75:8080"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_secretsmanager_secret" "ai_gateway_secret_key" {
  name                    = "${var.project_name}/${var.environment}/ai-gateway-secret-key"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "ai_gateway_secret_key" {
  secret_id     = aws_secretsmanager_secret.ai_gateway_secret_key.id
  secret_string = "CHANGE_ME_AI_GATEWAY_SECRET_KEY"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# S3 Bucket Parameters for backend services
resource "aws_ssm_parameter" "s3_raw_images_bucket" {
  name  = "/${var.project_name}/${var.environment}/s3-raw-images-bucket"
  type  = "String"
  value = module.storage.app_data_bucket_id

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "s3_ai_bucket" {
  name  = "/${var.project_name}/${var.environment}/s3-ai-bucket"
  type  = "String"
  value = module.ai_development.ai_dev_bucket_name

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "s3_results_bucket" {
  name  = "/${var.project_name}/${var.environment}/s3-results-bucket"
  type  = "String"
  value = module.ai_development.ai_dev_bucket_name

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# Webhook Signing Secret
resource "aws_secretsmanager_secret" "webhook_signing_secret" {
  name                    = "${var.project_name}/${var.environment}/webhook-signing-secret"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "webhook_signing_secret" {
  secret_id     = aws_secretsmanager_secret.webhook_signing_secret.id
  secret_string = "CHANGE_ME_WEBHOOK_SIGNING_SECRET"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Telegram Bot Credentials
resource "aws_secretsmanager_secret" "telegram_credentials" {
  name                    = "${var.project_name}/${var.environment}/telegram-credentials"
  recovery_window_in_days = 7

  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "telegram_credentials" {
  secret_id = aws_secretsmanager_secret.telegram_credentials.id
  secret_string = jsonencode({
    bot_token = "8200004959:AAGJfk43wgt1R7wO9B85OPzuNAH7Za1x62c"
    chat_id   = "-4920891504"
  })
}

# Compute Module
module "compute" {
  source = "./modules/compute"

  project_name           = var.project_name
  environment            = var.environment
  region                 = var.region
  private_subnet_ids     = module.networking.private_subnet_ids
  security_group_id      = module.security.ecs_tasks_sg_id
  execution_role_arn     = module.security.ecs_task_execution_role_arn
  task_role_arn          = module.security.ecs_task_role_arn
  ecr_repository_url     = module.storage.ecr_repository_url
  db_password_secret_arn = module.database.db_password_secret_arn
  task_cpu               = var.ecs_task_cpu
  task_memory            = var.ecs_task_memory
  desired_count          = var.ecs_desired_count
  target_group_arn       = module.load_balancer.target_group_arn
  alb_listener_arn       = module.load_balancer.http_listener_arn

  # Celery worker configuration
  celery_worker_cpu           = var.celery_worker_cpu
  celery_worker_memory        = var.celery_worker_memory
  celery_worker_desired_count = var.celery_worker_desired_count

  tags = local.common_tags

  depends_on = [
    aws_ssm_parameter.celery_broker_url,
    aws_ssm_parameter.celery_result_backend,
    aws_ssm_parameter.allowed_hosts,
    aws_ssm_parameter.cors_allowed_origins,
    aws_secretsmanager_secret_version.secret_key,
    aws_secretsmanager_secret_version.aws_access_key_id,
    aws_secretsmanager_secret_version.aws_secret_access_key,
    aws_secretsmanager_secret_version.ai_service_secret_key,
    aws_ssm_parameter.ai_gateway_url,
    aws_secretsmanager_secret_version.ai_gateway_secret_key,
    aws_ssm_parameter.s3_raw_images_bucket,
    aws_ssm_parameter.s3_ai_bucket,
    aws_ssm_parameter.s3_results_bucket,
    aws_secretsmanager_secret_version.webhook_signing_secret,
    module.load_balancer
  ]
}

# CICD Module
module "cicd" {
  source = "./modules/cicd"

  project_name               = var.project_name
  environment                = var.environment
  region                     = var.region
  artifacts_bucket_id        = module.storage.artifacts_bucket_id
  ecr_repository_url         = module.storage.ecr_repository_url
  ecs_cluster_name           = module.compute.ecs_cluster_name
  ecs_service_name           = module.compute.ecs_service_name
  ecs_task_family            = module.compute.ecs_task_family
  celery_worker_service_name = module.compute.celery_worker_service_name
  celery_worker_task_family  = module.compute.celery_worker_task_family
  lambda_role_arn            = module.security.lambda_role_arn
  codebuild_role_arn         = module.security.codebuild_role_arn
  codepipeline_role_arn      = module.security.codepipeline_role_arn
  telegram_lambda_arn        = ""

  tags = local.common_tags
}

# Monitoring Module
module "monitoring" {
  source = "./modules/monitoring"

  project_name               = var.project_name
  environment                = var.environment
  region                     = var.region
  ecs_cluster_name           = module.compute.ecs_cluster_name
  ecs_service_name           = module.compute.ecs_service_name
  celery_worker_service_name = module.compute.celery_worker_service_name
  db_instance_id             = module.database.db_instance_id
  redis_id                   = module.cache.redis_id
  alb_arn_suffix             = module.load_balancer.alb_arn_suffix
  target_group_arn_suffix    = module.load_balancer.target_group_arn_suffix
  efs_id                     = module.ai_development.efs_id
  cloudfront_distribution_id = module.frontend.cloudfront_distribution_id
  nat_gateway_ids            = module.networking.nat_gateway_ids

  sqs_queue_names = [
    { name = module.ai_development.calibration_queue_name, label = "Calibration" },
    { name = module.ai_development.sfm_queue_name, label = "SFM" },
    { name = module.ai_development.orthomosaic_queue_name, label = "Orthomosaic" },
  ]

  ai_ecs_service_names = [
    module.ai_services.api_gateway_service_name,
    module.ai_services.calibration_service_name,
    module.ai_services.orthomosaic_service_name,
  ]

  gpu_instance_id     = module.ai_development.gpu_instance_id
  enable_gpu_instance = var.enable_gpu_instance

  tags = local.common_tags

  depends_on = [
    module.compute,
    module.load_balancer,
    module.ai_development,
    module.ai_services,
    module.frontend,
    module.networking
  ]
}

# Frontend Module
module "frontend" {
  source = "./modules/frontend"

  project_name                 = var.project_name
  environment                  = var.environment
  region                       = var.region
  invalidation_lambda_role_arn = module.security.cloudfront_invalidation_role_arn
  domain_aliases               = var.frontend_domain != null ? [var.frontend_domain] : []
  acm_certificate_arn          = var.frontend_certificate_arn

  tags = local.common_tags
}

# Frontend CI/CD Module
module "frontend_cicd" {
  source = "./modules/frontend_cicd"

  project_name             = var.project_name
  environment              = var.environment
  region                   = var.region
  artifacts_bucket_id      = module.storage.artifacts_bucket_id
  frontend_bucket_id       = module.frontend.frontend_bucket_id
  backend_alb_url          = var.api_domain != null ? "https://${var.api_domain}" : "https://${module.load_balancer.alb_dns_name}"
  lambda_role_arn          = module.security.frontend_lambda_role_arn
  codebuild_role_arn       = module.security.codebuild_role_arn
  codepipeline_role_arn    = module.security.codepipeline_role_arn
  invalidation_lambda_name = module.frontend.invalidation_lambda_name
  invalidation_lambda_arn  = module.frontend.invalidation_lambda_arn
  telegram_lambda_arn      = ""

  tags = local.common_tags

  depends_on = [
    module.frontend,
    module.load_balancer
  ]
}

# Notifications Module
module "notifications" {
  source = "./modules/notifications"

  project_name             = var.project_name
  environment              = var.environment
  region                   = var.region
  backend_pipeline_name    = module.cicd.pipeline_name
  frontend_pipeline_name   = module.frontend_cicd.pipeline_name
  backend_build_project    = module.cicd.codebuild_project_name
  frontend_build_project   = "${var.project_name}-${var.environment}-frontend-build"
  telegram_lambda_role_arn = module.security.telegram_lambda_role_arn
  telegram_secret_arn      = aws_secretsmanager_secret.telegram_credentials.arn

  tags = local.common_tags

  depends_on = [
    module.cicd,
    module.frontend_cicd,
    aws_secretsmanager_secret_version.telegram_credentials
  ]
}

# AI Development Module
module "ai_development" {
  source = "./modules/ai_development"

  project_name        = var.project_name
  environment         = var.environment
  region              = var.region
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  public_subnet_ids   = module.networking.public_subnet_ids
  ecs_tasks_sg_id     = module.security.ecs_tasks_sg_id
  app_data_bucket_arn = module.storage.app_data_bucket_arn

  # GPU Instance Configuration
  enable_gpu_instance  = var.enable_gpu_instance
  gpu_instance_type    = var.gpu_instance_type
  gpu_ami_id           = var.gpu_ami_id
  gpu_root_volume_size = var.gpu_root_volume_size
  gpu_ssh_key_name     = var.gpu_ssh_key_name
  gpu_ssh_allowed_cidr = var.gpu_ssh_allowed_cidr

  tags = local.common_tags

  depends_on = [
    module.networking,
    module.security
  ]
}

# AI Services Module
module "ai_services" {
  source = "./modules/ai_services"

  project_name          = var.project_name
  environment           = var.environment
  region                = var.region
  account_id            = data.aws_caller_identity.current.account_id
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  ecs_cluster_id        = module.compute.ecs_cluster_id
  ecs_cluster_name      = module.compute.ecs_cluster_name
  ecs_security_group_id = module.security.ecs_tasks_sg_id
  execution_role_arn    = module.security.ecs_task_execution_role_arn
  efs_id                = module.ai_development.efs_id
  efs_arn               = module.ai_development.efs_arn
  efs_security_group_id = module.ai_development.efs_security_group_id
  ai_dev_bucket_name    = module.ai_development.ai_dev_bucket_name
  ai_dev_bucket_arn     = module.ai_development.ai_dev_bucket_arn
  app_data_bucket_name  = module.storage.app_data_bucket_id
  app_data_bucket_arn   = module.storage.app_data_bucket_arn

  # SQS queues
  calibration_queue_arn  = module.ai_development.calibration_queue_arn
  sfm_queue_arn          = module.ai_development.sfm_queue_arn
  orthomosaic_queue_arn  = module.ai_development.orthomosaic_queue_arn
  calibration_dlq_arn    = module.ai_development.calibration_dlq_arn
  sfm_dlq_arn            = module.ai_development.sfm_dlq_arn
  orthomosaic_dlq_arn    = module.ai_development.orthomosaic_dlq_arn
  calibration_queue_name = module.ai_development.calibration_queue_name
  sfm_queue_name         = module.ai_development.sfm_queue_name
  orthomosaic_queue_name = module.ai_development.orthomosaic_queue_name

  tags = local.common_tags

  depends_on = [
    module.ai_development,
    module.compute,
    module.security,
    aws_ssm_parameter.sqs_calibration_queue_url,
    aws_ssm_parameter.sqs_sfm_queue_url,
    aws_ssm_parameter.sqs_orthomosaic_queue_url,
    aws_ssm_parameter.backend_api_url,
    aws_secretsmanager_secret_version.ai_service_secret_key,
    aws_secretsmanager_secret_version.ai_gateway_secret_key,
  ]
}

# SSM Parameters for SQS Queue URLs (used by AI services)
resource "aws_ssm_parameter" "sqs_calibration_queue_url" {
  name  = "/${var.project_name}/${var.environment}/sqs-calibration-queue-url"
  type  = "String"
  value = module.ai_development.calibration_queue_url

  tags = local.common_tags
}

resource "aws_ssm_parameter" "sqs_sfm_queue_url" {
  name  = "/${var.project_name}/${var.environment}/sqs-sfm-queue-url"
  type  = "String"
  value = module.ai_development.sfm_queue_url

  tags = local.common_tags
}

resource "aws_ssm_parameter" "sqs_orthomosaic_queue_url" {
  name  = "/${var.project_name}/${var.environment}/sqs-orthomosaic-queue-url"
  type  = "String"
  value = module.ai_development.orthomosaic_queue_url

  tags = local.common_tags
}

# Backend API URL for AI services to callback
resource "aws_ssm_parameter" "backend_api_url" {
  name  = "/${var.project_name}/${var.environment}/backend-api-url"
  type  = "String"
  value = var.api_domain != null ? "https://${var.api_domain}" : "https://${module.load_balancer.alb_dns_name}"

  tags = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# AI CI/CD Module
module "ai_cicd" {
  source = "./modules/ai_cicd"

  project_name        = var.project_name
  environment         = var.environment
  region              = var.region
  artifacts_bucket_id = module.storage.artifacts_bucket_id

  ecr_repository_urls = module.ai_services.ecr_repository_urls

  ecs_cluster_name         = module.compute.ecs_cluster_name
  api_gateway_service_name = module.ai_services.api_gateway_service_name
  calibration_service_name = module.ai_services.calibration_service_name
  orthomosaic_service_name = module.ai_services.orthomosaic_service_name

  lambda_role_arn       = module.security.ai_lambda_role_arn
  codebuild_role_arn    = module.security.codebuild_role_arn
  codepipeline_role_arn = module.security.codepipeline_role_arn
  telegram_lambda_arn   = module.notifications.telegram_lambda_arn

  tags = local.common_tags

  depends_on = [
    module.ai_services,
    module.notifications
  ]
}

# Security group rule to allow GPU instance to access RDS
resource "aws_security_group_rule" "rds_from_gpu" {
  count = var.enable_gpu_instance ? 1 : 0

  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.ai_development.gpu_security_group_id
  security_group_id        = module.security.rds_sg_id
  description              = "PostgreSQL from GPU instance"

  depends_on = [module.ai_development, module.security]
}

# Security group rule to allow GPU instance to access Redis
resource "aws_security_group_rule" "redis_from_gpu" {
  count = var.enable_gpu_instance ? 1 : 0

  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = module.ai_development.gpu_security_group_id
  security_group_id        = module.security.redis_sg_id
  description              = "Redis from GPU instance"

  depends_on = [module.ai_development, module.security]
}

# App Metrics Module - Django Prometheus metrics to CloudWatch
module "app_metrics" {
  source = "./modules/app_metrics"

  project_name    = var.project_name
  environment     = var.environment
  region          = var.region
  metrics_url     = var.api_domain != null ? "https://${var.api_domain}/detailed-metrics/" : "https://${module.load_balancer.alb_dns_name}/detailed-metrics/"
  lambda_role_arn = module.security.metrics_lambda_role_arn

  tags = local.common_tags

  depends_on = [
    module.security,
    module.load_balancer
  ]
}

