data "aws_caller_identity" "current" {}

# KMS Key for S3 encryption
resource "aws_kms_key" "s3" {
  description             = "KMS key for ${var.project_name} S3 bucket encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-kms-key"
    }
  )
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${var.project_name}-${var.environment}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# S3 Bucket for application data (user uploads, media, etc.)
resource "aws_s3_bucket" "app_data" {
  bucket = "${var.project_name}-${var.environment}-app-data"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-app-data"
    }
  )
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    id     = "transition-old-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# CORS configuration for app data bucket (required for direct browser uploads)
resource "aws_s3_bucket_cors_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 Bucket for pipeline artifacts
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-${var.environment}-pipeline-artifacts"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-pipeline-artifacts"
    }
  )
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "cleanup-old-artifacts"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# ECR Repository
resource "aws_ecr_repository" "main" {
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-ecr"
    }
  )
}

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Store S3 KMS Key ID in Secrets Manager
resource "aws_secretsmanager_secret" "s3_kms_key" {
  name                    = "${var.project_name}/${var.environment}/s3-kms-key-id"
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-kms-key-id"
    }
  )
}

resource "aws_secretsmanager_secret_version" "s3_kms_key" {
  secret_id     = aws_secretsmanager_secret.s3_kms_key.id
  secret_string = aws_kms_key.s3.id
}

# Store bucket name in Parameter Store
resource "aws_ssm_parameter" "bucket_name" {
  name  = "/${var.project_name}/${var.environment}/s3-bucket-name"
  type  = "String"
  value = aws_s3_bucket.app_data.id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-bucket-name"
    }
  )
}

resource "aws_ssm_parameter" "s3_region" {
  name  = "/${var.project_name}/${var.environment}/s3-region"
  type  = "String"
  value = var.region

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-s3-region"
    }
  )
}
