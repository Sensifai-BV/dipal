output "lambda_function_arn" {
  description = "ARN of the metrics collector Lambda function"
  value       = aws_lambda_function.metrics_collector.arn
}

output "lambda_function_name" {
  description = "Name of the metrics collector Lambda function"
  value       = aws_lambda_function.metrics_collector.function_name
}
