output "efs_id" {
  description = "ID of the AI development EFS filesystem"
  value       = aws_efs_file_system.ai.id
}

output "efs_dns_name" {
  description = "DNS name of the AI development EFS filesystem"
  value       = aws_efs_file_system.ai.dns_name
}

output "efs_arn" {
  description = "ARN of the AI development EFS filesystem"
  value       = aws_efs_file_system.ai.arn
}

output "calibration_queue_url" {
  description = "URL of the calibration SQS queue"
  value       = aws_sqs_queue.calibration.url
}

output "calibration_queue_arn" {
  description = "ARN of the calibration SQS queue"
  value       = aws_sqs_queue.calibration.arn
}

output "sfm_queue_url" {
  description = "URL of the SFM SQS queue"
  value       = aws_sqs_queue.sfm.url
}

output "sfm_queue_arn" {
  description = "ARN of the SFM SQS queue"
  value       = aws_sqs_queue.sfm.arn
}

output "orthomosaic_queue_url" {
  description = "URL of the orthomosaic SQS queue"
  value       = aws_sqs_queue.orthomosaic.url
}

output "orthomosaic_queue_arn" {
  description = "ARN of the orthomosaic SQS queue"
  value       = aws_sqs_queue.orthomosaic.arn
}

output "calibration_dlq_url" {
  description = "URL of the calibration DLQ"
  value       = aws_sqs_queue.calibration_dlq.url
}

output "sfm_dlq_url" {
  description = "URL of the SFM DLQ"
  value       = aws_sqs_queue.sfm_dlq.url
}

output "orthomosaic_dlq_url" {
  description = "URL of the orthomosaic DLQ"
  value       = aws_sqs_queue.orthomosaic_dlq.url
}

output "ai_dev_bucket_name" {
  description = "Name of the AI development S3 bucket"
  value       = aws_s3_bucket.ai_dev.id
}

output "ai_dev_bucket_arn" {
  description = "ARN of the AI development S3 bucket"
  value       = aws_s3_bucket.ai_dev.arn
}

output "aidev_user_name" {
  description = "Name of the AI development IAM user"
  value       = aws_iam_user.aidev.name
}

output "aidev_user_arn" {
  description = "ARN of the AI development IAM user"
  value       = aws_iam_user.aidev.arn
}

# GPU Instance Outputs
output "gpu_instance_id" {
  description = "ID of the GPU EC2 instance"
  value       = var.enable_gpu_instance ? aws_instance.gpu[0].id : null
}

output "gpu_instance_public_ip" {
  description = "Public IP of the GPU EC2 instance"
  value       = var.enable_gpu_instance ? aws_instance.gpu[0].public_ip : null
}

output "gpu_instance_private_ip" {
  description = "Private IP of the GPU EC2 instance"
  value       = var.enable_gpu_instance ? aws_instance.gpu[0].private_ip : null
}

output "gpu_security_group_id" {
  description = "Security group ID of the GPU instance"
  value       = var.enable_gpu_instance ? aws_security_group.gpu_instance[0].id : null
}

output "gpu_ssh_command" {
  description = "SSH command to connect to the GPU instance"
  value       = var.enable_gpu_instance ? "ssh -i ${var.gpu_ssh_key_name}.pem ubuntu@${aws_instance.gpu[0].public_ip}" : null
}

output "efs_security_group_id" {
  description = "Security group ID of the EFS filesystem"
  value       = aws_security_group.efs.id
}

output "calibration_dlq_arn" {
  description = "ARN of the calibration DLQ"
  value       = aws_sqs_queue.calibration_dlq.arn
}

output "sfm_dlq_arn" {
  description = "ARN of the SFM DLQ"
  value       = aws_sqs_queue.sfm_dlq.arn
}

output "orthomosaic_dlq_arn" {
  description = "ARN of the orthomosaic DLQ"
  value       = aws_sqs_queue.orthomosaic_dlq.arn
}

output "calibration_queue_name" {
  description = "Name of the calibration SQS queue"
  value       = aws_sqs_queue.calibration.name
}

output "sfm_queue_name" {
  description = "Name of the SFM SQS queue"
  value       = aws_sqs_queue.sfm.name
}

output "orthomosaic_queue_name" {
  description = "Name of the orthomosaic SQS queue"
  value       = aws_sqs_queue.orthomosaic.name
}
