data "aws_caller_identity" "current" {}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-cluster"
    }
  )
}

# CloudWatch Log Group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-ecs-logs"
    }
  )
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-${var.environment}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${var.ecr_repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DEBUG"
          value = "False"
        },
        {
          name  = "USE_AWS_ROLE"
          value = "true"
        },
        {
          name  = "APPLICATION_LEVEL"
          value = "Production"
        },
        {
          name  = "ENABLE_TRACING"
          value = "True"
        },
        {
          name  = "ENABLE_FILE_LOGGING"
          value = "True"
        },
        {
          name  = "IGNORE_NAN_TRACE"
          value = "False"
        },
        {
          name  = "ACCESS_TOKEN_EXPIRE_MINUTES"
          value = "10080"
        },
        {
          name  = "REFRESH_TOKEN_EXPIRE_DAYS"
          value = "7"
        },
        {
          name  = "AWS_S3_ENDPOINT_URL"
          value = "https://s3.${var.region}.amazonaws.com"
        },
        {
          name  = "DB_ENGINE"
          value = "django.contrib.gis.db.backends.postgis"
        },
        {
          name  = "REDIS_DB"
          value = "0"
        },
        {
          name  = "PAGE_SIZE"
          value = "100"
        }
      ]

      secrets = [
        {
          name      = "SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/secret-key"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = var.db_password_secret_arn
        },
        {
          name      = "AWS_S3_KMS_KEY_ID"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/s3-kms-key-id"
        },
        {
          name      = "AI_SERVICE_SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/ai-service-secret-key"
        },
        {
          name      = "AI_GATEWAY_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/ai-gateway-url"
        },
        {
          name      = "AI_GATEWAY_SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/ai-gateway-secret-key"
        },
        {
          name      = "WEBHOOK_SIGNING_SECRET"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/webhook-signing-secret-NsbAtT"
        },
        {
          name      = "DB_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-name"
        },
        {
          name      = "DB_USER"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-user"
        },
        {
          name      = "DB_HOST"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-host"
        },
        {
          name      = "DB_PORT"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-port"
        },
        {
          name      = "AWS_STORAGE_BUCKET_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-bucket-name"
        },
        {
          name      = "AWS_S3_RAW_IMAGES_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-raw-images-bucket"
        },
        {
          name      = "AWS_S3_AI_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-ai-bucket"
        },
        {
          name      = "AWS_S3_RESULTS_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-results-bucket"
        },
        {
          name      = "AWS_S3_REGION_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-region"
        },
        {
          name      = "CELERY_BROKER_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/celery-broker-url"
        },
        {
          name      = "CELERY_RESULT_BACKEND"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/celery-result-backend"
        },
        {
          name      = "ALLOWED_HOSTS"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/allowed-hosts"
        },
        {
          name      = "CORS_ALLOWED_ORIGINS"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/cors-allowed-origins"
        },
        {
          name      = "REDIS_HOST"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/redis-endpoint"
        },
        {
          name      = "REDIS_PORT"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/redis-port"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/ || exit 0"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-task"
    }
  )
}

# ECS Service
resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-${var.environment}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn != null ? [1] : []

    content {
      target_group_arn = var.target_group_arn
      container_name   = "backend"
      container_port   = 8000
    }
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  health_check_grace_period_seconds = var.target_group_arn != null ? 120 : 60

  enable_execute_command = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-service"
    }
  )

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}

# Celery Worker Task Definition
resource "aws_ecs_task_definition" "celery_worker" {
  family                   = "${var.project_name}-${var.environment}-celery-worker-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.celery_worker_cpu
  memory                   = var.celery_worker_memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "celery-worker"
      image     = "${var.ecr_repository_url}:latest"
      essential = true

      command = [
        "celery",
        "-A",
        "config",
        "worker",
        "-l",
        "info",
        "--concurrency=2"
      ]

      environment = [
        {
          name  = "DEBUG"
          value = "False"
        },
        {
          name  = "USE_AWS_ROLE"
          value = "true"
        },
        {
          name  = "APPLICATION_LEVEL"
          value = "Production"
        },
        {
          name  = "ENABLE_TRACING"
          value = "True"
        },
        {
          name  = "ENABLE_FILE_LOGGING"
          value = "True"
        },
        {
          name  = "IGNORE_NAN_TRACE"
          value = "False"
        },
        {
          name  = "ACCESS_TOKEN_EXPIRE_MINUTES"
          value = "10080"
        },
        {
          name  = "REFRESH_TOKEN_EXPIRE_DAYS"
          value = "7"
        },
        {
          name  = "AWS_S3_ENDPOINT_URL"
          value = "https://s3.${var.region}.amazonaws.com"
        },
        {
          name  = "DB_ENGINE"
          value = "django.contrib.gis.db.backends.postgis"
        },
        {
          name  = "REDIS_DB"
          value = "0"
        },
        {
          name  = "PAGE_SIZE"
          value = "100"
        }
      ]

      secrets = [
        {
          name      = "SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/secret-key"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = var.db_password_secret_arn
        },
        {
          name      = "AWS_S3_KMS_KEY_ID"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/s3-kms-key-id"
        },
        {
          name      = "AI_SERVICE_SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/ai-service-secret-key"
        },
        {
          name      = "AI_GATEWAY_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/ai-gateway-url"
        },
        {
          name      = "AI_GATEWAY_SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/ai-gateway-secret-key"
        },
        {
          name      = "WEBHOOK_SIGNING_SECRET"
          valueFrom = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/${var.environment}/webhook-signing-secret-NsbAtT"
        },
        {
          name      = "DB_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-name"
        },
        {
          name      = "DB_USER"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-user"
        },
        {
          name      = "DB_HOST"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-host"
        },
        {
          name      = "DB_PORT"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/db-port"
        },
        {
          name      = "AWS_STORAGE_BUCKET_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-bucket-name"
        },
        {
          name      = "AWS_S3_RAW_IMAGES_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-raw-images-bucket"
        },
        {
          name      = "AWS_S3_AI_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-ai-bucket"
        },
        {
          name      = "AWS_S3_RESULTS_BUCKET"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-results-bucket"
        },
        {
          name      = "AWS_S3_REGION_NAME"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/s3-region"
        },
        {
          name      = "CELERY_BROKER_URL"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/celery-broker-url"
        },
        {
          name      = "CELERY_RESULT_BACKEND"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/celery-result-backend"
        },
        {
          name      = "ALLOWED_HOSTS"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/allowed-hosts"
        },
        {
          name      = "CORS_ALLOWED_ORIGINS"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/cors-allowed-origins"
        },
        {
          name      = "REDIS_HOST"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/redis-endpoint"
        },
        {
          name      = "REDIS_PORT"
          valueFrom = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/redis-port"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "celery -A config inspect ping -d celery@$HOSTNAME || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "celery-worker"
        }
      }
    }
  ])

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-celery-worker-task"
    }
  )
}

# Celery Worker Service
resource "aws_ecs_service" "celery_worker" {
  name            = "${var.project_name}-${var.environment}-celery-worker-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery_worker.arn
  desired_count   = var.celery_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = false
  }

  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 50

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  enable_execute_command = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-celery-worker-service"
    }
  )

  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
