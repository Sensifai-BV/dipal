# ECR Repository URLs
output "ecr_repository_urls" {
  description = "ECR repository URLs for AI services"
  value = {
    for key, repo in aws_ecr_repository.ai_services : key => repo.repository_url
  }
}

# Service names
output "api_gateway_service_name" {
  description = "API Gateway ECS service name"
  value       = aws_ecs_service.api_gateway.name
}

output "calibration_service_name" {
  description = "Calibration ECS service name"
  value       = aws_ecs_service.calibration.name
}

output "orthomosaic_service_name" {
  description = "Orthomosaic ECS service name"
  value       = aws_ecs_service.orthomosaic.name
}

# Batch
output "sfm_job_queue_arn" {
  description = "SFM Batch job queue ARN"
  value       = aws_batch_job_queue.sfm.arn
}

output "sfm_job_definition_arn" {
  description = "SFM Batch job definition ARN"
  value       = aws_batch_job_definition.sfm.arn
}

# Service Discovery
output "api_gateway_dns" {
  description = "API Gateway Cloud Map DNS name"
  value       = "gateway.ai.${var.project_name}.local"
}

# Task Role
output "ai_task_role_arn" {
  description = "AI services task role ARN"
  value       = aws_iam_role.ai_task.arn
}
