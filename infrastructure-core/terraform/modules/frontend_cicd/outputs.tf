output "webhook_url" {
  description = "Frontend webhook URL"
  value       = "${aws_apigatewayv2_stage.frontend_webhook.invoke_url}/webhook"
}

output "api_key_secret_arn" {
  description = "ARN of frontend webhook API key secret"
  value       = aws_secretsmanager_secret.frontend_api_key.arn
}

output "pipeline_name" {
  description = "Name of frontend CodePipeline"
  value       = aws_codepipeline.frontend.name
}

output "pipeline_arn" {
  description = "ARN of frontend CodePipeline"
  value       = aws_codepipeline.frontend.arn
}
