# API Gateway - Always-running ECS Fargate service
resource "aws_ecs_task_definition" "api_gateway" {
  family                   = "${var.project_name}-${var.environment}-ai-gateway-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_gateway_cpu
  memory                   = var.api_gateway_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = aws_iam_role.ai_task.arn

  volume {
    name = "shared-data"
    efs_volume_configuration {
      file_system_id     = var.efs_id
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([
    {
      name      = "api-gateway"
      image     = "${aws_ecr_repository.ai_services["api-gateway"].repository_url}:latest"
      essential = true

      command = [
        "uvicorn", "api_gateway.app.__main__:app",
        "--port", "8080", "--host", "0.0.0.0"
      ]

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
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
        { name = "API_GATEWAY_PORT", value = "8080" },
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
          name      = "SQS_CALIBRATION_QUEUE_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/sqs-calibration-queue-url"
        },
        {
          name      = "SQS_SFM_QUEUE_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/sqs-sfm-queue-url"
        },
        {
          name      = "SQS_ORTHOMOSAIC_QUEUE_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/sqs-orthomosaic-queue-url"
        },
        {
          name      = "BACKEND_API_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.project_name}/${var.environment}/backend-api-url"
        },
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8080/health/')\" || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ai_services.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api-gateway"
        }
      }
    }
  ])

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-gateway-task"
    Component = "AI-Services"
  })
}

resource "aws_ecs_service" "api_gateway" {
  name            = "${var.project_name}-${var.environment}-ai-gateway-service"
  cluster         = var.ecs_cluster_id
  task_definition = aws_ecs_task_definition.api_gateway.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api_gateway.arn
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  enable_execute_command = true

  tags = merge(var.tags, {
    Name      = "${var.project_name}-${var.environment}-ai-gateway-service"
    Component = "AI-Services"
  })

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
