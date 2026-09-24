output "telegram_lambda_arn" {
  description = "ARN of Telegram notifier Lambda function"
  value       = aws_lambda_function.telegram_notifier.arn
}

output "telegram_lambda_name" {
  description = "Name of Telegram notifier Lambda function"
  value       = aws_lambda_function.telegram_notifier.function_name
}
