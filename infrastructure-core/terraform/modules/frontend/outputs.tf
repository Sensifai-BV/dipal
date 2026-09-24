output "frontend_bucket_id" {
  description = "ID of the frontend S3 bucket"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.frontend.id
}

output "invalidation_lambda_name" {
  description = "Name of CloudFront invalidation Lambda function"
  value       = aws_lambda_function.cloudfront_invalidation.function_name
}

output "invalidation_lambda_arn" {
  description = "ARN of CloudFront invalidation Lambda function"
  value       = aws_lambda_function.cloudfront_invalidation.arn
}
