# Networking Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.networking.private_subnet_ids
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.networking.public_subnet_ids
}

# Storage Outputs
output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = module.storage.ecr_repository_url
}

output "app_data_bucket" {
  description = "Name of the S3 bucket for application data"
  value       = module.storage.app_data_bucket_id
}

output "artifacts_bucket" {
  description = "Name of the S3 bucket for pipeline artifacts"
  value       = module.storage.artifacts_bucket_id
}

# Database Outputs
output "db_endpoint" {
  description = "RDS instance endpoint"
  value       = module.database.db_endpoint
}

output "db_address" {
  description = "RDS instance address"
  value       = module.database.db_address
}

output "db_name" {
  description = "Database name"
  value       = module.database.db_name
}

# Cache Outputs
output "redis_endpoint" {
  description = "Redis endpoint address"
  value       = module.cache.redis_endpoint
}

output "redis_port" {
  description = "Redis port"
  value       = module.cache.redis_port
}

# ECS Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.compute.ecs_cluster_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.compute.ecs_service_name
}

output "celery_worker_service_name" {
  description = "Name of the Celery worker ECS service"
  value       = module.compute.celery_worker_service_name
}

output "celery_worker_task_family" {
  description = "Family of the Celery worker task definition"
  value       = module.compute.celery_worker_task_family
}

# Load Balancer Outputs
output "backend_url_http" {
  description = "Backend API URL (HTTP - will redirect to HTTPS)"
  value       = "http://${module.load_balancer.alb_dns_name}"
}

output "backend_url_https" {
  description = "Backend API URL (HTTPS)"
  value       = "https://${module.load_balancer.alb_dns_name}"
}

output "alb_dns_name" {
  description = "ALB DNS name for frontend configuration"
  value       = module.load_balancer.alb_dns_name
}

# CICD Outputs
output "webhook_url" {
  description = "URL for GitLab webhook (configure this in GitLab)"
  value       = module.cicd.webhook_url
}

output "webhook_api_key_secret_arn" {
  description = "ARN of the secret containing webhook API key"
  value       = module.cicd.api_key_secret_arn
  sensitive   = true
}

output "pipeline_name" {
  description = "Name of the CodePipeline"
  value       = module.cicd.pipeline_name
}

# Monitoring Outputs
output "cloudwatch_dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = module.monitoring.dashboard_name
}

# Important URLs and Commands
output "important_next_steps" {
  description = "Important next steps after deployment"
  sensitive = true
  value = <<-EOT

    DEPLOYMENT SUCCESSFUL! Next steps:

    1. Get the webhook API key:
       aws secretsmanager get-secret-value --secret-id ${module.cicd.api_key_secret_arn} --query SecretString --output text

    2. Configure GitLab webhook:
       - URL: ${module.cicd.webhook_url}
       - Method: POST
       - Add header: x-api-key: <API_KEY_FROM_STEP_1>
       - Events: Push events

    3. Update secrets in AWS Secrets Manager:
       - ${var.project_name}/${var.environment}/secret-key (Django SECRET_KEY)
       - ${var.project_name}/${var.environment}/aws-access-key-id
       - ${var.project_name}/${var.environment}/aws-secret-access-key
       - ${var.project_name}/${var.environment}/ai-service-secret-key

    4. Update parameters in AWS Systems Manager Parameter Store:
       - /${var.project_name}/${var.environment}/allowed-hosts
       - /${var.project_name}/${var.environment}/cors-allowed-origins

    5. Build and push initial Docker image to ECR:
       aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${module.storage.ecr_repository_url}
       docker build -t ${module.storage.ecr_repository_url}:latest .
       docker push ${module.storage.ecr_repository_url}:latest

    6. View CloudWatch Dashboard:
       https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${module.monitoring.dashboard_name}

    7. Monitor ECS service:
       aws ecs describe-services --cluster ${module.compute.ecs_cluster_name} --services ${module.compute.ecs_service_name} --region ${var.region}

    8. Access your backend API:
       Backend URL: https://${module.load_balancer.alb_dns_name}
       Note: Update ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS to include this URL

    Database Endpoint: ${module.database.db_endpoint}
    Redis Endpoint: redis://${module.cache.redis_endpoint}:${module.cache.redis_port}
  EOT
}

# Frontend Outputs
output "frontend_url" {
  description = "Frontend CloudFront URL"
  value       = "https://${module.frontend.cloudfront_domain_name}"
}

output "frontend_bucket_name" {
  description = "Frontend S3 bucket name"
  value       = module.frontend.frontend_bucket_id
}

output "frontend_webhook_url" {
  description = "Frontend webhook URL for GitLab"
  value       = module.frontend_cicd.webhook_url
}

output "frontend_webhook_api_key_secret_arn" {
  description = "ARN of the secret containing frontend webhook API key"
  value       = module.frontend_cicd.api_key_secret_arn
  sensitive   = true
}

output "frontend_pipeline_name" {
  description = "Name of the frontend CodePipeline"
  value       = module.frontend_cicd.pipeline_name
}

# Notifications Outputs
output "telegram_lambda_arn" {
  description = "ARN of Telegram notifier Lambda"
  value       = module.notifications.telegram_lambda_arn
}

output "telegram_lambda_name" {
  description = "Name of Telegram notifier Lambda"
  value       = module.notifications.telegram_lambda_name
}

# AI Development Outputs
output "ai_efs_id" {
  description = "ID of the AI development EFS filesystem"
  value       = module.ai_development.efs_id
}

output "ai_efs_dns_name" {
  description = "DNS name of the AI development EFS filesystem"
  value       = module.ai_development.efs_dns_name
}

output "ai_calibration_queue_url" {
  description = "URL of the calibration SQS queue"
  value       = module.ai_development.calibration_queue_url
}

output "ai_sfm_queue_url" {
  description = "URL of the SFM SQS queue"
  value       = module.ai_development.sfm_queue_url
}

output "ai_orthomosaic_queue_url" {
  description = "URL of the orthomosaic SQS queue"
  value       = module.ai_development.orthomosaic_queue_url
}

output "ai_calibration_dlq_url" {
  description = "URL of the calibration DLQ"
  value       = module.ai_development.calibration_dlq_url
}

output "ai_sfm_dlq_url" {
  description = "URL of the SFM DLQ"
  value       = module.ai_development.sfm_dlq_url
}

output "ai_orthomosaic_dlq_url" {
  description = "URL of the orthomosaic DLQ"
  value       = module.ai_development.orthomosaic_dlq_url
}

output "ai_dev_bucket_name" {
  description = "Name of the AI development S3 bucket"
  value       = module.ai_development.ai_dev_bucket_name
}

output "aidev_user_name" {
  description = "Name of the AI development IAM user"
  value       = module.ai_development.aidev_user_name
}

# GPU Instance Outputs
output "gpu_instance_id" {
  description = "ID of the GPU EC2 instance"
  value       = module.ai_development.gpu_instance_id
}

output "gpu_instance_public_ip" {
  description = "Public IP of the GPU EC2 instance"
  value       = module.ai_development.gpu_instance_public_ip
}

output "gpu_instance_private_ip" {
  description = "Private IP of the GPU EC2 instance"
  value       = module.ai_development.gpu_instance_private_ip
}

output "gpu_ssh_command" {
  description = "SSH command to connect to the GPU instance"
  value       = module.ai_development.gpu_ssh_command
}

# AI Services Outputs
output "ai_ecr_repository_urls" {
  description = "ECR repository URLs for AI services"
  value       = module.ai_services.ecr_repository_urls
}

output "ai_gateway_service_name" {
  description = "AI API Gateway ECS service name"
  value       = module.ai_services.api_gateway_service_name
}

output "ai_gateway_dns" {
  description = "AI API Gateway Cloud Map DNS"
  value       = module.ai_services.api_gateway_dns
}

output "ai_sfm_job_queue_arn" {
  description = "SFM Batch job queue ARN"
  value       = module.ai_services.sfm_job_queue_arn
}

# AI CI/CD Outputs
output "ai_webhook_url" {
  description = "URL for AI services GitLab webhook"
  value       = module.ai_cicd.webhook_url
}

output "ai_webhook_api_key_secret_arn" {
  description = "ARN of the secret containing AI webhook API key"
  value       = module.ai_cicd.api_key_secret_arn
  sensitive   = true
}

output "ai_pipeline_names" {
  description = "Names of AI service CodePipelines"
  value       = module.ai_cicd.pipeline_names
}

# CloudWatch Read-Only User
output "cloudwatch_readonly_user_name" {
  description = "Name of the CloudWatch read-only IAM user"
  value       = module.security.cloudwatch_readonly_user_name
}

output "cloudwatch_readonly_user_arn" {
  description = "ARN of the CloudWatch read-only IAM user"
  value       = module.security.cloudwatch_readonly_user_arn
}
