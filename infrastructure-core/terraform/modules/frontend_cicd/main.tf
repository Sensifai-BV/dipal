# API Key for frontend webhook authentication
resource "random_password" "frontend_api_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "frontend_api_key" {
  name                    = "${var.project_name}/${var.environment}/frontend-webhook-api-key"
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-webhook-api-key"
    }
  )
}

resource "aws_secretsmanager_secret_version" "frontend_api_key" {
  secret_id     = aws_secretsmanager_secret.frontend_api_key.id
  secret_string = random_password.frontend_api_key.result
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}-frontend-webhook"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-webhook-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-frontend-webhook"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-webhook-api-logs"
    }
  )
}

resource "aws_cloudwatch_log_group" "codebuild" {
  name              = "/aws/codebuild/${var.project_name}-${var.environment}-frontend-build"
  retention_in_days = 30

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-codebuild-logs"
    }
  )
}

# Lambda webhook processor
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda/webhook_processor.zip"

  source {
    content  = file("${path.module}/lambda/webhook_processor.py")
    filename = "index.py"
  }
}

resource "aws_lambda_function" "frontend_webhook_processor" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-${var.environment}-frontend-webhook"
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
      API_KEY_SECRET       = aws_secretsmanager_secret.frontend_api_key.arn
      SOURCE_KEY           = "frontend-source.zip" # Different from backend's "source.zip"
      TELEGRAM_LAMBDA_ARN  = var.telegram_lambda_arn
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-webhook"
    }
  )
}

# API Gateway for frontend webhook
resource "aws_apigatewayv2_api" "frontend_webhook" {
  name          = "${var.project_name}-${var.environment}-frontend-webhook-api"
  protocol_type = "HTTP"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-webhook-api"
    }
  )
}

resource "aws_apigatewayv2_stage" "frontend_webhook" {
  api_id      = aws_apigatewayv2_api.frontend_webhook.id
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
      Name = "${var.project_name}-${var.environment}-frontend-webhook-stage"
    }
  )
}

resource "aws_apigatewayv2_integration" "frontend_webhook" {
  api_id                 = aws_apigatewayv2_api.frontend_webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.frontend_webhook_processor.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "frontend_webhook" {
  api_id    = aws_apigatewayv2_api.frontend_webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.frontend_webhook.id}"
}

resource "aws_lambda_permission" "frontend_api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.frontend_webhook_processor.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.frontend_webhook.execution_arn}/*/*"
}

# CodeBuild Project for Frontend
resource "aws_codebuild_project" "frontend" {
  name          = "${var.project_name}-${var.environment}-frontend-build"
  description   = "Build frontend for ${var.project_name}"
  build_timeout = 15 # Frontend builds are faster
  service_role  = var.codebuild_role_arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = false # No Docker needed
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "FRONTEND_BUCKET"
      value = var.frontend_bucket_id
    }

    environment_variable {
      name  = "VITE_API_BASE_URL"
      value = "${var.backend_alb_url}/v1/"
    }
    environment_variable {
      name  = "VITE_BASE_URL"
      value = "${var.backend_alb_url}/v1/"
    }

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = var.region
    }
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.codebuild.name
      stream_name = "frontend-build"
    }
  }

  source {
    type = "CODEPIPELINE"
    buildspec = yamlencode({
      version = "0.2"
      phases = {
        install = {
          runtime-versions = {
            nodejs = 22
          }
        }
        pre_build = {
          commands = [
            "echo Build started on `date`",
            "echo Cloning frontend repository...",
            "git clone https://gitlab.eclipse.org/eclipse-research-labs/spade-project/opencall-2/dipal/frontend-core.git app",
            "cd app",
            "echo Installing dependencies...",
            "npm install"
          ]
        }
        build = {
          commands = [
            "echo Building frontend with VITE_API_BASE_URL=$VITE_API_BASE_URL",
            "npm run build",
            "echo Build completed on `date`"
          ]
        }
        post_build = {
          commands = [
            "echo Preparing deployment artifacts...",
            "cd ..",
            "mkdir -p deployment",
            "cp -r app/dist/* deployment/",
            "ls -la deployment/"
          ]
        }
      }
      artifacts = {
        files = [
          "**/*"
        ]
        base-directory = "deployment"
      }
      cache = {
        paths = [
          "app/node_modules/**/*"
        ]
      }
    })
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-codebuild"
    }
  )
}

# CodePipeline for Frontend
resource "aws_codepipeline" "frontend" {
  name     = "${var.project_name}-${var.environment}-frontend-pipeline"
  role_arn = var.codepipeline_role_arn

  artifact_store {
    location = var.artifacts_bucket_id
    type     = "S3"
  }

  # STAGE 1: Source
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
        S3ObjectKey          = "frontend-source.zip" # Different from backend
        PollForSourceChanges = false
      }
    }
  }

  # STAGE 2: Build
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
        ProjectName = aws_codebuild_project.frontend.name
      }
    }
  }

  # STAGE 3: Deploy to S3
  stage {
    name = "Deploy"

    action {
      name            = "DeployToS3"
      category        = "Deploy"
      owner           = "AWS"
      provider        = "S3"
      version          = "1"
      input_artifacts = ["build_output"]

      configuration = {
        BucketName = var.frontend_bucket_id
        Extract    = "true" # Unzip the artifacts
      }
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-pipeline"
    }
  )
}

# EventBridge rule to trigger pipeline on frontend-source.zip upload
resource "aws_cloudwatch_event_rule" "frontend_s3_trigger" {
  name        = "${var.project_name}-${var.environment}-frontend-pipeline-trigger"
  description = "Trigger frontend pipeline on frontend-source.zip upload"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.artifacts_bucket_id]
      }
      object = {
        key = ["frontend-source.zip"] # Different from backend's "source.zip"
      }
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-pipeline-trigger"
    }
  )
}

resource "aws_cloudwatch_event_target" "frontend_pipeline" {
  rule     = aws_cloudwatch_event_rule.frontend_s3_trigger.name
  arn      = aws_codepipeline.frontend.arn
  role_arn = aws_iam_role.frontend_eventbridge.arn
}

# EventBridge IAM role
resource "aws_iam_role" "frontend_eventbridge" {
  name = "${var.project_name}-${var.environment}-frontend-eventbridge-role"

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
      Name = "${var.project_name}-${var.environment}-frontend-eventbridge-role"
    }
  )
}

resource "aws_iam_role_policy" "frontend_eventbridge" {
  name = "${var.project_name}-${var.environment}-frontend-eventbridge-policy"
  role = aws_iam_role.frontend_eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "codepipeline:StartPipelineExecution"
        ]
        Resource = aws_codepipeline.frontend.arn
      }
    ]
  })
}

# EventBridge rule to trigger CloudFront invalidation after pipeline success
resource "aws_cloudwatch_event_rule" "pipeline_success" {
  name        = "${var.project_name}-${var.environment}-frontend-deploy-success"
  description = "Trigger CloudFront invalidation after successful frontend deployment"

  event_pattern = jsonencode({
    source      = ["aws.codepipeline"]
    detail-type = ["CodePipeline Pipeline Execution State Change"]
    detail = {
      pipeline = [aws_codepipeline.frontend.name]
      state    = ["SUCCEEDED"]
    }
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-frontend-deploy-success"
    }
  )
}

resource "aws_cloudwatch_event_target" "invalidation_lambda" {
  rule     = aws_cloudwatch_event_rule.pipeline_success.name
  arn      = var.invalidation_lambda_arn
  role_arn = null # Lambda doesn't need a role for EventBridge invocation
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.invalidation_lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pipeline_success.arn
}
