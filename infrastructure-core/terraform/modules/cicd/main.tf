data "aws_caller_identity" "current" {}

# Generate API Key for webhook authentication
resource "random_password" "api_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "api_key" {
  name                    = "${var.project_name}/${var.environment}/webhook-api-key"
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-webhook-api-key"
    }
  )
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id     = aws_secretsmanager_secret.api_key.id
  secret_string = random_password.api_key.result
}

# Lambda function to process GitLab webhook
resource "aws_lambda_function" "webhook_processor" {
  filename         = "${path.module}/lambda/webhook_processor.zip"
  function_name    = "${var.project_name}-${var.environment}-webhook-processor"
  role             = var.lambda_role_arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET            = var.artifacts_bucket_id
      PROJECT_NAME         = var.project_name
      ENVIRONMENT          = var.environment
      API_KEY_SECRET       = aws_secretsmanager_secret.api_key.arn
      TELEGRAM_LAMBDA_ARN  = var.telegram_lambda_arn
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-webhook-processor"
    }
  )
}

# Package Lambda function
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda/webhook_processor.zip"

  source {
    content  = file("${path.module}/lambda/webhook_processor.py")
    filename = "index.py"
  }
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.webhook_processor.function_name}"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-logs"
    }
  )
}

# API Gateway
resource "aws_apigatewayv2_api" "webhook" {
  name          = "${var.project_name}-${var.environment}-webhook-api"
  protocol_type = "HTTP"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-webhook-api"
    }
  )
}

resource "aws_apigatewayv2_stage" "webhook" {
  api_id      = aws_apigatewayv2_api.webhook.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-webhook-stage"
    }
  )
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-webhook"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-api-gateway-logs"
    }
  )
}

resource "aws_apigatewayv2_integration" "webhook" {
  api_id                 = aws_apigatewayv2_api.webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.webhook_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "webhook" {
  api_id    = aws_apigatewayv2_api.webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.webhook.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.webhook.execution_arn}/*/*"
}

# CodeBuild Project
resource "aws_codebuild_project" "app" {
  name          = "${var.project_name}-${var.environment}-build"
  description   = "Build Docker image for ${var.project_name}"
  build_timeout = 30
  service_role  = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.region
    }

    environment_variable {
      name  = "AWS_ACCOUNT_ID"
      value = data.aws_caller_identity.current.account_id
    }

    environment_variable {
      name  = "ECR_REPOSITORY_URI"
      value = var.ecr_repository_url
    }

    environment_variable {
      name  = "ECS_CONTAINER_NAME"
      value = "backend"
    }

    environment_variable {
      name  = "ECS_TASK_FAMILY"
      value = var.ecs_task_family
    }

    environment_variable {
      name  = "CELERY_TASK_FAMILY"
      value = var.celery_worker_task_family
    }

    environment_variable {
      name  = "ECS_CLUSTER_NAME"
      value = var.ecs_cluster_name
    }

    environment_variable {
      name  = "ECS_SERVICE_NAME"
      value = var.ecs_service_name
    }

    environment_variable {
      name  = "CELERY_SERVICE_NAME"
      value = var.celery_worker_service_name
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.codebuild.name
      stream_name = "build"
    }
  }

  source {
    type = "CODEPIPELINE"
    buildspec = yamlencode({
      version = "0.2"
      phases = {
        pre_build = {
          commands = [
            "echo Logging in to Amazon ECR...",
            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $ECR_REPOSITORY_URI",
            "COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)",
            "IMAGE_TAG=$${COMMIT_HASH:=latest}",
            "echo Building Docker image with tag $IMAGE_TAG"
          ]
        }
        build = {
          commands = [
            "echo Build started on `date`",
            "echo Cloning repository...",
            "git clone https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/backend-core.git app",
            "cd app",
            "echo Building the Docker image...",
            "docker build -t $ECR_REPOSITORY_URI:latest .",
            "docker tag $ECR_REPOSITORY_URI:latest $ECR_REPOSITORY_URI:$IMAGE_TAG"
          ]
        }
        post_build = {
          commands = [
            "echo Build completed on `date`",
            "echo Pushing the Docker images...",
            "docker push $ECR_REPOSITORY_URI:latest",
            "docker push $ECR_REPOSITORY_URI:$IMAGE_TAG",
            "cd ..",
            "echo Deploying backend service...",
            "BACKEND_TASKDEF=$(aws ecs describe-task-definition --task-definition $ECS_TASK_FAMILY --query 'taskDefinition' --output json)",
            "NEW_BACKEND_TASKDEF=$(echo $BACKEND_TASKDEF | jq --arg IMAGE \"$ECR_REPOSITORY_URI:$IMAGE_TAG\" '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')",
            "BACKEND_REV=$(echo $NEW_BACKEND_TASKDEF | jq -r '.family')",
            "echo Registering new backend task definition revision for $BACKEND_REV...",
            "NEW_BACKEND_ARN=$(aws ecs register-task-definition --cli-input-json \"$NEW_BACKEND_TASKDEF\" --query 'taskDefinition.taskDefinitionArn' --output text)",
            "echo Updating backend service to $NEW_BACKEND_ARN...",
            "aws ecs update-service --cluster $ECS_CLUSTER_NAME --service $ECS_SERVICE_NAME --task-definition $NEW_BACKEND_ARN --force-new-deployment",
            "echo Deploying celery worker service...",
            "CELERY_TASKDEF=$(aws ecs describe-task-definition --task-definition $CELERY_TASK_FAMILY --query 'taskDefinition' --output json)",
            "NEW_CELERY_TASKDEF=$(echo $CELERY_TASKDEF | jq --arg IMAGE \"$ECR_REPOSITORY_URI:$IMAGE_TAG\" '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')",
            "CELERY_REV=$(echo $NEW_CELERY_TASKDEF | jq -r '.family')",
            "echo Registering new celery task definition revision for $CELERY_REV...",
            "NEW_CELERY_ARN=$(aws ecs register-task-definition --cli-input-json \"$NEW_CELERY_TASKDEF\" --query 'taskDefinition.taskDefinitionArn' --output text)",
            "echo Updating celery service to $NEW_CELERY_ARN...",
            "aws ecs update-service --cluster $ECS_CLUSTER_NAME --service $CELERY_SERVICE_NAME --task-definition $NEW_CELERY_ARN --force-new-deployment",
            "echo Deployment complete!"
          ]
        }
      }
      artifacts = {
        files = [
          "**/*"
        ]
      }
      cache = {
        paths = [
          "/root/.m2/**/*",
          "/root/.npm/**/*"
        ]
      }
    })
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-codebuild"
    }
  )
}

resource "aws_cloudwatch_log_group" "codebuild" {
  name              = "/aws/codebuild/${var.project_name}-${var.environment}"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-codebuild-logs"
    }
  )
}

# CodePipeline
resource "aws_codepipeline" "app" {
  name     = "${var.project_name}-${var.environment}-pipeline"
  role_arn = var.codepipeline_role_arn

  artifact_store {
    location = var.artifacts_bucket_id
    type     = "S3"
  }

  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "S3"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        S3Bucket             = var.artifacts_bucket_id
        S3ObjectKey          = "source.zip"
        PollForSourceChanges = false
      }
    }
  }

  stage {
    name = "Build"

    action {
      name             = "Build"
      category         = "Build"
      owner            = "AWS"
      provider         = "CodeBuild"
      version          = "1"
      input_artifacts  = ["source_output"]
      output_artifacts = ["build_output"]

      configuration = {
        ProjectName = aws_codebuild_project.app.name
      }
    }
  }


  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-pipeline"
    }
  )
}

# EventBridge rule to trigger pipeline on S3 upload
resource "aws_cloudwatch_event_rule" "s3_trigger" {
  name        = "${var.project_name}-${var.environment}-pipeline-trigger"
  description = "Trigger CodePipeline on source.zip upload"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.artifacts_bucket_id]
      }
      object = {
        key = ["source.zip"]
      }
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-pipeline-trigger"
    }
  )
}

resource "aws_cloudwatch_event_target" "pipeline" {
  rule     = aws_cloudwatch_event_rule.s3_trigger.name
  arn      = aws_codepipeline.app.arn
  role_arn = aws_iam_role.eventbridge.arn
}

# IAM role for EventBridge to start pipeline
resource "aws_iam_role" "eventbridge" {
  name = "${var.project_name}-${var.environment}-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-eventbridge-role"
    }
  )
}

resource "aws_iam_role_policy" "eventbridge" {
  name = "${var.project_name}-${var.environment}-eventbridge-policy"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "codepipeline:StartPipelineExecution"
        ]
        Resource = aws_codepipeline.app.arn
      }
    ]
  })
}

# Enable S3 EventBridge notifications
resource "aws_s3_bucket_notification" "artifacts" {
  bucket      = var.artifacts_bucket_id
  eventbridge = true
}
