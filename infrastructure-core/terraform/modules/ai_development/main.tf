# Security Group for EFS
resource "aws_security_group" "efs" {
  name        = "${var.project_name}-${var.environment}-ai-efs-sg"
  description = "Security group for AI development EFS"
  vpc_id      = var.vpc_id

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [var.ecs_tasks_sg_id]
  }

  dynamic "ingress" {
    for_each = var.enable_gpu_instance ? [1] : []
    content {
      description     = "NFS from GPU instance"
      from_port       = 2049
      to_port         = 2049
      protocol        = "tcp"
      security_groups = [aws_security_group.gpu_instance[0].id]
    }
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-efs-sg"
      Component = "AI-Development"
    }
  )
}

# EFS File System
resource "aws_efs_file_system" "ai" {
  creation_token   = "${var.project_name}-${var.environment}-ai-efs"
  encrypted        = true
  performance_mode = var.efs_performance_mode
  throughput_mode  = var.efs_throughput_mode

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-efs"
      Component = "AI-Development"
    }
  )
}

# EFS Mount Targets
resource "aws_efs_mount_target" "ai" {
  count = length(var.private_subnet_ids)

  file_system_id  = aws_efs_file_system.ai.id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

# SQS Dead Letter Queues
resource "aws_sqs_queue" "calibration_dlq" {
  name                      = "${var.project_name}-${var.environment}-ai-calibration-dlq"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-calibration-dlq"
      Component = "AI-Development"
      QueueType = "DeadLetterQueue"
    }
  )
}

resource "aws_sqs_queue" "sfm_dlq" {
  name                      = "${var.project_name}-${var.environment}-ai-sfm-dlq"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-sfm-dlq"
      Component = "AI-Development"
      QueueType = "DeadLetterQueue"
    }
  )
}

resource "aws_sqs_queue" "orthomosaic_dlq" {
  name                      = "${var.project_name}-${var.environment}-ai-orthomosaic-dlq"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-orthomosaic-dlq"
      Component = "AI-Development"
      QueueType = "DeadLetterQueue"
    }
  )
}

# SQS Main Queues
resource "aws_sqs_queue" "calibration" {
  name                      = "${var.project_name}-${var.environment}-ai-calibration-queue"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.calibration_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-calibration-queue"
      Component = "AI-Development"
      QueueType = "Main"
    }
  )
}

resource "aws_sqs_queue" "sfm" {
  name                      = "${var.project_name}-${var.environment}-ai-sfm-queue"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.sfm_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-sfm-queue"
      Component = "AI-Development"
      QueueType = "Main"
    }
  )
}

resource "aws_sqs_queue" "orthomosaic" {
  name                      = "${var.project_name}-${var.environment}-ai-orthomosaic-queue"
  message_retention_seconds  = var.queue_message_retention
  visibility_timeout_seconds = var.queue_visibility_timeout
  max_message_size           = 262144
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.orthomosaic_dlq.arn
    maxReceiveCount     = 3
  })

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-orthomosaic-queue"
      Component = "AI-Development"
      QueueType = "Main"
    }
  )
}

# S3 Bucket for AI Development
resource "aws_s3_bucket" "ai_dev" {
  bucket = "${var.project_name}-${var.environment}-ai-dev-bucket"

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-ai-dev-bucket"
      Component = "AI-Development"
    }
  )
}

resource "aws_s3_bucket_versioning" "ai_dev" {
  bucket = aws_s3_bucket.ai_dev.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ai_dev" {
  bucket = aws_s3_bucket.ai_dev.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ai_dev" {
  bucket = aws_s3_bucket.ai_dev.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "ai_dev" {
  bucket = aws_s3_bucket.ai_dev.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# IAM User for AI Development
resource "aws_iam_user" "aidev" {
  name = "${var.project_name}-${var.environment}-aidev"

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-aidev"
      Component = "AI-Development"
    }
  )
}

# IAM Policy for AI Development User
resource "aws_iam_user_policy" "aidev" {
  name = "${var.project_name}-${var.environment}-aidev-policy"
  user = aws_iam_user.aidev.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSFullAccess"
        Effect = "Allow"
        Action = "sqs:*"
        Resource = [
          aws_sqs_queue.calibration.arn,
          aws_sqs_queue.sfm.arn,
          aws_sqs_queue.orthomosaic.arn,
          aws_sqs_queue.calibration_dlq.arn,
          aws_sqs_queue.sfm_dlq.arn,
          aws_sqs_queue.orthomosaic_dlq.arn
        ]
      },
      {
        Sid      = "EFSFullAccess"
        Effect   = "Allow"
        Action   = "elasticfilesystem:*"
        Resource = aws_efs_file_system.ai.arn
      },
      {
        Sid    = "S3FullAccess"
        Effect = "Allow"
        Action = "s3:*"
        Resource = [
          aws_s3_bucket.ai_dev.arn,
          "${aws_s3_bucket.ai_dev.arn}/*"
        ]
      }
    ]
  })
}

# ============================================
# GPU EC2 Instance Resources
# ============================================

# Security Group for GPU EC2 Instance
resource "aws_security_group" "gpu_instance" {
  count = var.enable_gpu_instance ? 1 : 0

  name        = "${var.project_name}-${var.environment}-gpu-instance-sg"
  description = "Security group for GPU EC2 instance"
  vpc_id      = var.vpc_id

  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.gpu_ssh_allowed_cidr]
  }

  ingress {
    description     = "AI Gateway from ECS tasks"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [var.ecs_tasks_sg_id]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-gpu-instance-sg"
      Component = "AI-Development"
    }
  )
}

# IAM Role for GPU EC2 Instance
resource "aws_iam_role" "gpu_instance" {
  count = var.enable_gpu_instance ? 1 : 0

  name = "${var.project_name}-${var.environment}-gpu-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-gpu-instance-role"
      Component = "AI-Development"
    }
  )
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "gpu_instance" {
  count = var.enable_gpu_instance ? 1 : 0

  name = "${var.project_name}-${var.environment}-gpu-instance-profile"
  role = aws_iam_role.gpu_instance[0].name

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-gpu-instance-profile"
      Component = "AI-Development"
    }
  )
}

# IAM Policy for GPU Instance - S3, SQS, EFS Access
resource "aws_iam_role_policy" "gpu_instance" {
  count = var.enable_gpu_instance ? 1 : 0

  name = "${var.project_name}-${var.environment}-gpu-instance-policy"
  role = aws_iam_role.gpu_instance[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3AIDevBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.ai_dev.arn,
          "${aws_s3_bucket.ai_dev.arn}/*"
        ]
      },
      {
        Sid    = "S3AppDataBucketAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.app_data_bucket_arn,
          "${var.app_data_bucket_arn}/*"
        ]
      },
      {
        Sid    = "KMSAccess"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "SQSAccess"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.calibration.arn,
          aws_sqs_queue.sfm.arn,
          aws_sqs_queue.orthomosaic.arn
        ]
      },
      {
        Sid    = "CloudWatchAgentAccess"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      },
      {
        Sid    = "EFSAccess"
        Effect = "Allow"
        Action = [
          "elasticfilesystem:ClientMount",
          "elasticfilesystem:ClientWrite",
          "elasticfilesystem:DescribeFileSystems",
          "elasticfilesystem:DescribeMountTargets"
        ]
        Resource = aws_efs_file_system.ai.arn
      }
    ]
  })
}

# GPU EC2 Instance
resource "aws_instance" "gpu" {
  count = var.enable_gpu_instance ? 1 : 0

  ami                         = var.gpu_ami_id
  instance_type               = var.gpu_instance_type
  key_name                    = var.gpu_ssh_key_name
  subnet_id                   = var.public_subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.gpu_instance[0].id]
  iam_instance_profile        = aws_iam_instance_profile.gpu_instance[0].name
  associate_public_ip_address = true

  root_block_device {
    volume_size           = var.gpu_root_volume_size
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  user_data = <<-EOF
    #!/bin/bash
    echo "GPU instance initialized at $(date)" >> /var/log/gpu-init.log

    # Install EFS mount helper
    apt-get update -y
    apt-get install -y amazon-efs-utils nfs-common

    # Create mount point for EFS
    mkdir -p /mnt/efs
    echo "EFS mount point created" >> /var/log/gpu-init.log
  EOF

  tags = merge(
    var.tags,
    {
      Name      = "${var.project_name}-${var.environment}-gpu-instance"
      Component = "AI-Development"
    }
  )

  lifecycle {
    ignore_changes = [ami]
  }
}
