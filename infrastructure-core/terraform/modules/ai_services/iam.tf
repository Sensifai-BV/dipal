# IAM Role for AI ECS Tasks
resource "aws_iam_role" "ai_task" {
  name = "${var.project_name}-${var.environment}-ai-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-task-role"
    Component = "AI-Services"
  })
}

# S3 access for AI tasks
resource "aws_iam_role_policy" "ai_task_s3" {
  name = "${var.project_name}-${var.environment}-ai-s3-policy"
  role = aws_iam_role.ai_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.ai_dev_bucket_arn,
          "${var.ai_dev_bucket_arn}/*",
          var.app_data_bucket_arn,
          "${var.app_data_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# SQS access for AI tasks
resource "aws_iam_role_policy" "ai_task_sqs" {
  name = "${var.project_name}-${var.environment}-ai-sqs-policy"
  role = aws_iam_role.ai_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:ChangeMessageVisibility"
      ]
      Resource = [
        var.calibration_queue_arn,
        var.sfm_queue_arn,
        var.orthomosaic_queue_arn,
        var.calibration_dlq_arn,
        var.sfm_dlq_arn,
        var.orthomosaic_dlq_arn
      ]
    }]
  })
}

# EFS access for AI tasks
resource "aws_iam_role_policy" "ai_task_efs" {
  name = "${var.project_name}-${var.environment}-ai-efs-policy"
  role = aws_iam_role.ai_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "elasticfilesystem:ClientMount",
        "elasticfilesystem:ClientWrite",
        "elasticfilesystem:DescribeFileSystems"
      ]
      Resource = var.efs_arn
    }]
  })
}

# ECS Exec support (SSM)
resource "aws_iam_role_policy" "ai_task_exec_command" {
  name = "${var.project_name}-${var.environment}-ai-exec-command-policy"
  role = aws_iam_role.ai_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ]
      Resource = "*"
    }]
  })
}

# AWS Batch Service Role
resource "aws_iam_role" "batch_service" {
  name = "${var.project_name}-${var.environment}-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "batch.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-batch-service-role"
    Component = "AI-Services"
  })
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# Batch Instance Role (for EC2 instances launched by Batch)
resource "aws_iam_role" "batch_instance" {
  name = "${var.project_name}-${var.environment}-batch-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-batch-instance-role"
    Component = "AI-Services"
  })
}

resource "aws_iam_role_policy_attachment" "batch_instance_ecs" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

# Batch instance needs S3, SQS, EFS access (same as AI task role)
resource "aws_iam_role_policy" "batch_instance_s3" {
  name   = "${var.project_name}-${var.environment}-batch-s3-policy"
  role   = aws_iam_role.batch_instance.id
  policy = aws_iam_role_policy.ai_task_s3.policy
}

resource "aws_iam_role_policy" "batch_instance_sqs" {
  name   = "${var.project_name}-${var.environment}-batch-sqs-policy"
  role   = aws_iam_role.batch_instance.id
  policy = aws_iam_role_policy.ai_task_sqs.policy
}

resource "aws_iam_role_policy" "batch_instance_efs" {
  name   = "${var.project_name}-${var.environment}-batch-efs-policy"
  role   = aws_iam_role.batch_instance.id
  policy = aws_iam_role_policy.ai_task_efs.policy
}

resource "aws_iam_instance_profile" "batch_instance" {
  name = "${var.project_name}-${var.environment}-batch-instance-profile"
  role = aws_iam_role.batch_instance.name

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-batch-instance-profile"
    Component = "AI-Services"
  })
}

# Lambda role for SQS-to-Batch trigger
resource "aws_iam_role" "sfm_trigger" {
  name = "${var.project_name}-${var.environment}-sfm-trigger-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-sfm-trigger-role"
    Component = "AI-Services"
  })
}

resource "aws_iam_role_policy" "sfm_trigger" {
  name = "${var.project_name}-${var.environment}-sfm-trigger-policy"
  role = aws_iam_role.sfm_trigger.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "batch:SubmitJob",
          "batch:DescribeJobs"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.sfm_queue_arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:*"
      }
    ]
  })
}
