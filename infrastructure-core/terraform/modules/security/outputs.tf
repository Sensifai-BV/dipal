output "ecs_tasks_sg_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

output "rds_sg_id" {
  description = "Security group ID for RDS"
  value       = aws_security_group.rds.id
}

output "redis_sg_id" {
  description = "Security group ID for Redis"
  value       = aws_security_group.redis.id
}

output "ecs_task_execution_role_arn" {
  description = "ARN of ECS task execution role"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of ECS task role"
  value       = aws_iam_role.ecs_task.arn
}

output "codebuild_role_arn" {
  description = "ARN of CodeBuild role"
  value       = aws_iam_role.codebuild.arn
}

output "codepipeline_role_arn" {
  description = "ARN of CodePipeline role"
  value       = aws_iam_role.codepipeline.arn
}

output "lambda_role_arn" {
  description = "ARN of Lambda role"
  value       = aws_iam_role.lambda.arn
}

output "frontend_lambda_role_arn" {
  description = "ARN of frontend Lambda webhook role"
  value       = aws_iam_role.frontend_lambda.arn
}

output "cloudfront_invalidation_role_arn" {
  description = "ARN of CloudFront invalidation Lambda role"
  value       = aws_iam_role.cloudfront_invalidation.arn
}

output "telegram_lambda_role_arn" {
  description = "ARN of Telegram notifier Lambda role"
  value       = aws_iam_role.telegram_lambda.arn
}

output "ai_lambda_role_arn" {
  description = "ARN of AI CI/CD Lambda webhook role"
  value       = aws_iam_role.ai_lambda.arn
}

output "metrics_lambda_role_arn" {
  description = "ARN of metrics collector Lambda role"
  value       = aws_iam_role.metrics_lambda.arn
}

output "cloudwatch_readonly_user_name" {
  description = "Name of the CloudWatch read-only IAM user"
  value       = aws_iam_user.cloudwatch_readonly.name
}

output "cloudwatch_readonly_user_arn" {
  description = "ARN of the CloudWatch read-only IAM user"
  value       = aws_iam_user.cloudwatch_readonly.arn
}
