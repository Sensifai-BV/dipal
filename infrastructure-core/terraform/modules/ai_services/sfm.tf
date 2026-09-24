# SFM - GPU-required service via AWS Batch (g4dn.2xlarge)

# Batch Compute Environment (GPU)
resource "aws_batch_compute_environment" "sfm" {
  compute_environment_name = "${var.project_name}-${var.environment}-ai-sfm-compute"
  type                     = "MANAGED"
  service_role             = aws_iam_role.batch_service.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT"

    min_vcpus = 0
    max_vcpus = var.sfm_vcpus
    desired_vcpus = 0

    instance_type = [var.sfm_instance_type]

    subnets            = var.private_subnet_ids
    security_group_ids = [aws_security_group.batch.id]

    instance_role = aws_iam_instance_profile.batch_instance.arn

    tags = merge(var.tags, {
      Name      = "${var.project_name}-${var.environment}-batch-gpu"
      Component = "AI-Services"
    })
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-sfm-compute"
    Component = "AI-Services"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# Batch Job Queue
resource "aws_batch_job_queue" "sfm" {
  name     = "${var.project_name}-${var.environment}-ai-sfm-job-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.sfm.arn
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-sfm-job-queue"
    Component = "AI-Services"
  })
}

# Batch Job Definition
resource "aws_batch_job_definition" "sfm" {
  name = "${var.project_name}-${var.environment}-ai-sfm-job"
  type = "container"

  platform_capabilities = ["EC2"]

  container_properties = jsonencode({
    image      = "${aws_ecr_repository.ai_services["sfm"].repository_url}:latest"
    vcpus      = var.sfm_vcpus
    memory     = var.sfm_memory

    command = [
      "uvicorn", "services.sfm.app.__main__:app",
      "--port", "8002", "--host", "0.0.0.0"
    ]

    resourceRequirements = [
      {
        type  = "GPU"
        value = "1"
      }
    ]

    volumes = [
      {
        name = "shared-data"
        efsVolumeConfiguration = {
          fileSystemId      = var.efs_id
          transitEncryption = "ENABLED"
        }
      }
    ]

    mountPoints = [
      {
        sourceVolume  = "shared-data"
        containerPath = "/app/data/temp"
        readOnly      = false
      }
    ]

    environment = [
      { name = "USE_AWS_ROLE", value = "true" },
      { name = "SQS_USE_AWS_ROLE", value = "true" },
      { name = "STORAGE_DRIVER", value = "s3" },
      { name = "SHARED_STORAGE_MODE", value = "local" },
      { name = "DISPATCH_MODE", value = "sqs" },
      { name = "SQS_ENABLED", value = "true" },
      { name = "SQS_REGION_NAME", value = var.region },
      { name = "TEMP_BASE_PATH", value = "/app/data/temp" },
      { name = "TEMP_CLEANUP_DAYS", value = "1" },
      { name = "REDIS_DB", value = "0" },
      { name = "REDIS_PASSWORD", value = "" },
      { name = "JOB_STATE_TTL_HOURS", value = "72" },
      { name = "BACKGROUND_TASK_USE_REDIS", value = "true" },
      { name = "BACKGROUND_TASK_CLEANUP_HOURS", value = "24" },
      { name = "SFM_SERVICE_PORT", value = "8002" },
      { name = "API_GATEWAY_CALLBACK_ENDPOINT", value = "/jobs/subservice-callback" },
      { name = "API_GATEWAY_TIMEOUT_SECONDS", value = "30" },
      { name = "BACKEND_CALLBACK_ENDPOINT", value = "/v1/api/jobs/ai-callback/" },
      { name = "APPLICATION_LEVEL", value = "production" },
      { name = "ENABLE_TRACING", value = "true" },
      { name = "ENABLE_FILE_LOGGING", value = "true" },
      { name = "IGNORE_NAN_TRACE", value = "false" },
      { name = "SQS_POLL_INTERVAL_SECONDS", value = "5" },
      { name = "SQS_VISIBILITY_TIMEOUT", value = "3600" },
      { name = "SQS_MAX_MESSAGES_PER_POLL", value = "1" },
      { name = "SQS_WAIT_TIME_SECONDS", value = "20" },
      { name = "STORAGE_REGION", value = var.region },
      { name = "STORAGE_PREFIX", value = "photogear" },
      { name = "STORAGE_PRESIGNED_URL_TIMEOUT", value = "300" },
      { name = "API_GATEWAY_URL", value = "http://gateway.ai.${var.project_name}.local:8080" },
      { name = "CALIBRATION_CLIENT_ADDRESS", value = "http://calibration.ai.${var.project_name}.local:8001" },
      { name = "SFM_CLIENT_ADDRESS", value = "http://sfm.ai.${var.project_name}.local:8002" },
      { name = "ORTHOMOSAIC_CLIENT_ADDRESS", value = "http://orthomosaic.ai.${var.project_name}.local:8003" },
      # SFM GPU-specific settings
      { name = "COLMAP_DEVICE", value = "gpu" },
      { name = "GPU_INDEX", value = "0" },
      { name = "COLMAP_MAX_IMAGE_SIZE", value = "3200" },
      { name = "COLMAP_NUM_THREADS", value = "-1" },
      { name = "COLMAP_SFM_USE_GPU", value = "1" },
      { name = "COLMAP_DENSE_USE_GPU", value = "1" },
      { name = "COLMAP_MATCHER_TYPE", value = "exhaustive" },
      { name = "COLMAP_BA_REFINE_FOCAL_LENGTH", value = "1" },
      { name = "COLMAP_BA_REFINE_PRINCIPAL_POINT", value = "0" },
      { name = "COLMAP_BA_REFINE_EXTRA_PARAMS", value = "1" },
    ]

    secrets = [
      {
        name      = "REDIS_HOST"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/redis-endpoint"
      },
      {
        name      = "REDIS_PORT"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/redis-port"
      },
      {
        name      = "AWS_S3_REGION_NAME"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/s3-region"
      },
      {
        name      = "AWS_S3_AI_BUCKET"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/s3-ai-bucket"
      },
      {
        name      = "AWS_S3_RAW_IMAGES_BUCKET"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/s3-raw-images-bucket"
      },
      {
        name      = "AWS_S3_RESULTS_BUCKET"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/s3-results-bucket"
      },
      {
        name      = "STORAGE_BUCKET_NAME"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/s3-ai-bucket"
      },
      {
        name      = "BACKEND_API_SECRET_KEY"
        valueFrom = "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}/${var.environment}/ai-service-secret-key"
      },
      {
        name      = "AI_GATEWAY_SECRET_KEY"
        valueFrom = "arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:${var.project_name}/${var.environment}/ai-gateway-secret-key"
      },
      {
        name      = "SQS_SFM_QUEUE_URL"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/sqs-sfm-queue-url"
      },
      {
        name      = "BACKEND_API_URL"
        valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/backend-api-url"
      },
    ]

    executionRoleArn = var.execution_role_arn
    jobRoleArn       = aws_iam_role.ai_task.arn

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ai_services.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "sfm"
      }
    }
  })

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-sfm-job"
    Component = "AI-Services"
  })

  lifecycle {
    ignore_changes = [container_properties]
  }
}

# Lambda function to trigger Batch jobs from SQS
data "archive_file" "sfm_trigger" {
  type        = "zip"
  output_path = "${path.module}/lambda/sfm_trigger.zip"

  source {
    content  = <<-PYTHON
import json
import os
import boto3

batch = boto3.client('batch')

JOB_QUEUE = os.environ['JOB_QUEUE']
JOB_DEFINITION = os.environ['JOB_DEFINITION']

def handler(event, context):
    for record in event['Records']:
        body = record['body']
        message_id = record['messageId']

        response = batch.submit_job(
            jobName=f"sfm-{message_id[:8]}",
            jobQueue=JOB_QUEUE,
            jobDefinition=JOB_DEFINITION,
            containerOverrides={
                'environment': [
                    {'name': 'SQS_MESSAGE_BODY', 'value': body},
                    {'name': 'SQS_MESSAGE_ID', 'value': message_id},
                ]
            }
        )

        print(f"Submitted Batch job {response['jobId']} for SQS message {message_id}")

    return {'statusCode': 200}
    PYTHON
    filename = "index.py"
  }
}

resource "aws_lambda_function" "sfm_trigger" {
  function_name    = "${var.project_name}-${var.environment}-sfm-batch-trigger"
  role             = aws_iam_role.sfm_trigger.arn
  handler          = "index.handler"
  runtime          = "python3.12"
  timeout          = 30
  filename         = data.archive_file.sfm_trigger.output_path
  source_code_hash = data.archive_file.sfm_trigger.output_base64sha256

  environment {
    variables = {
      JOB_QUEUE      = aws_batch_job_queue.sfm.name
      JOB_DEFINITION = aws_batch_job_definition.sfm.name
    }
  }

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-sfm-batch-trigger"
    Component = "AI-Services"
  })
}

# SQS event source mapping for Lambda
resource "aws_lambda_event_source_mapping" "sfm_sqs" {
  event_source_arn = var.sfm_queue_arn
  function_name    = aws_lambda_function.sfm_trigger.arn
  batch_size       = 1
  enabled          = true
}
