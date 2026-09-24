output "webhook_url" {
  description = "URL for AI services GitLab webhook"
  value       = "${aws_apigatewayv2_api.ai_webhook.api_endpoint}/webhook"
}

output "api_key_secret_arn" {
  description = "ARN of the secret containing AI webhook API key"
  value       = aws_secretsmanager_secret.ai_api_key.arn
}

output "pipeline_names" {
  description = "Names of all AI CodePipelines"
  value = merge(
    { for k, v in aws_codepipeline.ai_ecs : k => v.name },
    { for k, v in aws_codepipeline.ai_build_only : k => v.name }
  )
}
