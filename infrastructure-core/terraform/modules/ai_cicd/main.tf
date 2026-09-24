data "aws_caller_identity" "current" {}

locals {
  ai_services = {
    "api-gateway" = {
      source_key      = "ai-api-gateway-source.zip"
      ecr_key         = "api-gateway"
      dockerfile_path = "api_gateway/Dockerfile"
      container_name  = "api-gateway"
      build_timeout   = 30
      has_ecs_deploy  = true
      ecs_service     = var.api_gateway_service_name
    }
    "calibration" = {
      source_key      = "ai-calibration-source.zip"
      ecr_key         = "calibration"
      dockerfile_path = "services/radiometric_calibration/Dockerfile"
      container_name  = "calibration"
      build_timeout   = 30
      has_ecs_deploy  = true
      ecs_service     = var.calibration_service_name
    }
    "sfm" = {
      source_key      = "ai-sfm-source.zip"
      ecr_key         = "sfm"
      dockerfile_path = "services/sfm/Dockerfile"
      container_name  = "sfm"
      build_timeout   = 60
      has_ecs_deploy  = false
      ecs_service     = ""
    }
    "orthomosaic" = {
      source_key      = "ai-orthomosaic-source.zip"
      ecr_key         = "orthomosaic-generation"
      dockerfile_path = "services/orthomosaic_generation/Dockerfile"
      container_name  = "orthomosaic"
      build_timeout   = 45
      has_ecs_deploy  = true
      ecs_service     = var.orthomosaic_service_name
    }
  }

  ecs_services = { for k, v in local.ai_services : k => v if v.has_ecs_deploy }
  build_only   = { for k, v in local.ai_services : k => v if !v.has_ecs_deploy }
}

# ─── API Key ───────────────────────────────────────────────────────────────────

resource "random_password" "ai_api_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "ai_api_key" {
  name                    = "${var.project_name}/${var.environment}/ai-webhook-api-key"
  recovery_window_in_days = 7

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-webhook-api-key"
  })
}

resource "aws_secretsmanager_secret_version" "ai_api_key" {
  secret_id     = aws_secretsmanager_secret.ai_api_key.id
  secret_string = random_password.ai_api_key.result
}

# ─── Lambda Webhook Processor ──────────────────────────────────────────────────

data "archive_file" "ai_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda/webhook_processor.zip"

  source {
    content  = file("${path.module}/lambda/webhook_processor.py")
    filename = "index.py"
  }
}

resource "aws_lambda_function" "ai_webhook_processor" {
  filename         = data.archive_file.ai_lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-ai-webhook-processor"
  role             = var.lambda_role_arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.ai_lambda_zip.output_base64sha256
  runtime          = "python3.12"
  timeout          = 30

  environment {
    variables = {
      S3_BUCKET           = var.artifacts_bucket_id
      PROJECT_NAME        = var.project_name
      ENVIRONMENT         = var.environment
      API_KEY_SECRET      = aws_secretsmanager_secret.ai_api_key.arn
      TELEGRAM_LAMBDA_ARN = var.telegram_lambda_arn
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-webhook-processor"
  })
}

resource "aws_cloudwatch_log_group" "ai_lambda" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-ai-webhook-processor"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-lambda-logs"
  })
}

# ─── API Gateway HTTP Endpoint ─────────────────────────────────────────────────

resource "aws_apigatewayv2_api" "ai_webhook" {
  name          = "${var.project_name}-${var.environment}-ai-webhook-api"
  protocol_type = "HTTP"

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-webhook-api"
  })
}

resource "aws_apigatewayv2_stage" "ai_webhook" {
  api_id      = aws_apigatewayv2_api.ai_webhook.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.ai_api_gateway.arn
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

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-webhook-stage"
  })
}

resource "aws_cloudwatch_log_group" "ai_api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-ai-webhook"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-api-gateway-logs"
  })
}

resource "aws_apigatewayv2_integration" "ai_webhook" {
  api_id                 = aws_apigatewayv2_api.ai_webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ai_webhook_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ai_webhook" {
  api_id    = aws_apigatewayv2_api.ai_webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.ai_webhook.id}"
}

resource "aws_lambda_permission" "ai_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ai_webhook_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ai_webhook.execution_arn}/*/*"
}

# ─── CodeBuild Projects (4, one per service) ──────────────────────────────────

resource "aws_cloudwatch_log_group" "ai_codebuild" {
  for_each          = local.ai_services
  name              = "/aws/codebuild/${var.project_name}-${var.environment}-ai-${each.key}"
  retention_in_days = 30

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-${each.key}-codebuild-logs"
  })
}

resource "aws_codebuild_project" "ai_service" {
  for_each      = local.ai_services
  name          = "${var.project_name}-${var.environment}-ai-${each.key}-build"
  description   = "Build Docker image for AI ${each.key} service"
  build_timeout = each.value.build_timeout
  service_role  = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_MEDIUM"
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
      value = var.ecr_repository_urls[each.value.ecr_key]
    }

    environment_variable {
      name  = "ECS_CONTAINER_NAME"
      value = each.value.container_name
    }

    environment_variable {
      name  = "DOCKERFILE_PATH"
      value = each.value.dockerfile_path
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.ai_codebuild[each.key].name
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
            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com",
            "COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)",
            "IMAGE_TAG=$${COMMIT_HASH:=latest}",
            "echo Building AI service with tag $IMAGE_TAG"
          ]
        }
        build = {
          commands = [
            "echo Build started on `date`",
            "echo Cloning repository...",
            "git clone --depth 1 https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/image-analysis-core.git app",
            "cd app",
            "echo Building Docker image from $DOCKERFILE_PATH ...",
            "docker build -f $DOCKERFILE_PATH -t $ECR_REPOSITORY_URI:latest .",
            "docker tag $ECR_REPOSITORY_URI:latest $ECR_REPOSITORY_URI:$IMAGE_TAG"
          ]
        }
        post_build = {
          commands = [
            "echo Build completed on `date`",
            "echo Pushing Docker images...",
            "docker push $ECR_REPOSITORY_URI:latest",
            "docker push $ECR_REPOSITORY_URI:$IMAGE_TAG",
            "echo Writing image definitions file...",
            "cd ..",
            "printf '[{\"name\":\"%s\",\"imageUri\":\"%s\"}]' $ECS_CONTAINER_NAME $ECR_REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json",
            "cat imagedefinitions.json"
          ]
        }
      }
      artifacts = {
        files         = ["imagedefinitions.json"]
        discard-paths = "yes"
      }
    })
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-${each.key}-codebuild"
  })
}

# ─── CodePipelines — ECS-deployed services ────────────────────────────────────

resource "aws_codepipeline" "ai_ecs" {
  for_each = local.ecs_services
  name     = "${var.project_name}-${var.environment}-ai-${each.key}-pipeline"
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
        S3ObjectKey          = each.value.source_key
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
        ProjectName = aws_codebuild_project.ai_service[each.key].name
      }
    }
  }

  stage {
    name = "Deploy"

    action {
      name            = "Deploy"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "ECS"
      version         = "1"
      input_artifacts = ["build_output"]

      configuration = {
        ClusterName = var.ecs_cluster_name
        ServiceName = each.value.ecs_service
        FileName    = "imagedefinitions.json"
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-${each.key}-pipeline"
  })
}

# ─── CodePipelines — Build-only services (SFM) ────────────────────────────────

resource "aws_codepipeline" "ai_build_only" {
  for_each = local.build_only
  name     = "${var.project_name}-${var.environment}-ai-${each.key}-pipeline"
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
        S3ObjectKey          = each.value.source_key
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
        ProjectName = aws_codebuild_project.ai_service[each.key].name
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-${each.key}-pipeline"
  })
}

# ─── EventBridge Rules (4, one per service) ────────────────────────────────────

resource "aws_cloudwatch_event_rule" "ai_s3_trigger" {
  for_each    = local.ai_services
  name        = "${var.project_name}-${var.environment}-ai-${each.key}-trigger"
  description = "Trigger AI ${each.key} pipeline on S3 upload"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.artifacts_bucket_id]
      }
      object = {
        key = [each.value.source_key]
      }
    }
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-${each.key}-trigger"
  })
}

resource "aws_cloudwatch_event_target" "ai_pipeline" {
  for_each = local.ai_services
  rule     = aws_cloudwatch_event_rule.ai_s3_trigger[each.key].name
  arn      = each.value.has_ecs_deploy ? aws_codepipeline.ai_ecs[each.key].arn : aws_codepipeline.ai_build_only[each.key].arn
  role_arn = aws_iam_role.ai_eventbridge.arn
}

# ─── EventBridge IAM Role ─────────────────────────────────────────────────────

resource "aws_iam_role" "ai_eventbridge" {
  name = "${var.project_name}-${var.environment}-ai-eventbridge-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
    }]
  })

  tags = merge(var.tags, {
    Name = "${var.project_name}-${var.environment}-ai-eventbridge-role"
  })
}

resource "aws_iam_role_policy" "ai_eventbridge" {
  name = "${var.project_name}-${var.environment}-ai-eventbridge-policy"
  role = aws_iam_role.ai_eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["codepipeline:StartPipelineExecution"]
      Resource = concat(
        [for k, v in aws_codepipeline.ai_ecs : v.arn],
        [for k, v in aws_codepipeline.ai_build_only : v.arn]
      )
    }]
  })
}
