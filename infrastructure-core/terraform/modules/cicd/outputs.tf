output "webhook_url" {
  description = "URL for GitLab webhook"
  value       = "${aws_apigatewayv2_api.webhook.api_endpoint}/webhook"
}

output "api_key_secret_arn" {
  description = "ARN of the secret containing webhook API key"
  value       = aws_secretsmanager_secret.api_key.arn
  sensitive   = true
}

output "pipeline_name" {
  description = "Name of the CodePipeline"
  value       = aws_codepipeline.app.name
}

output "codebuild_project_name" {
  description = "Name of the CodeBuild project"
  value       = aws_codebuild_project.app.name
}
